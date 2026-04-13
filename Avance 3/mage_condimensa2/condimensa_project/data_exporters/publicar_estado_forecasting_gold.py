"""
Data Exporter: Publicar tablas de estado de forecasting
Pipeline: etl_gold
Construye tablas derivadas para productos estacionales e inactivos.
"""
from mage_ai.settings.repo import get_repo_path
from mage_ai.io.config import ConfigFileLoader
from mage_ai.io.postgres import Postgres
from os import path

if 'data_exporter' not in dir():
    from mage_ai.data_preparation.decorators import data_exporter
if 'test' not in dir():
    from mage_ai.data_preparation.decorators import test


def _sql_literal(value):
    if value is None:
        return 'NULL'
    return "'" + str(value).replace("'", "''") + "'"


@data_exporter
def publicar_estado_forecasting_gold(data, *args, **kwargs):
    """
    Publica tablas auxiliares para analitica de pronostico:
    - gold.forecasting_productos_estacionales_v1
    - gold.forecasting_productos_inactivos_v1

    Fuente: silver.forecasting_base_mensual_v1
    """
    if isinstance(data, dict):
        pipeline_id = data.get('pipeline_id', 'etl_gold')
        batch_id = data.get('batch_id')
    else:
        pipeline_id = 'etl_gold'
        batch_id = None

    config_path = path.join(get_repo_path(), 'io_config.yaml')
    config_profile = 'local_dwh'

    print(f"\n{'=' * 70}")
    print("PUBLICANDO TABLAS DE ESTADO FORECASTING")
    print(f"Pipeline: {pipeline_id}")
    print(f"Batch: {batch_id}")
    print(f"{'=' * 70}")

    with Postgres.with_config(ConfigFileLoader(config_path, config_profile)) as loader:
        loader.execute("TRUNCATE TABLE gold.forecasting_productos_estacionales_v1")
        loader.execute("TRUNCATE TABLE gold.forecasting_productos_inactivos_v1")

        batch_sql = _sql_literal(batch_id)
        pipeline_sql = _sql_literal(pipeline_id)

        loader.execute(
            f"""
            WITH base AS (
                SELECT
                    COALESCE(NULLIF(TRIM(producto_dashboard), ''), NULLIF(TRIM(producto_item), ''), 'SIN_NOMBRE') AS producto_dashboard,
                    UPPER(COALESCE(NULLIF(TRIM(tipo_producto), ''), 'OTRO')) AS tipo_producto,
                    DATE_TRUNC('month', periodo)::date AS periodo,
                    COALESCE(qty_vendida, 0)::numeric AS qty_vendida
                FROM silver.forecasting_base_mensual_v1
                WHERE periodo IS NOT NULL
            ),
            agg AS (
                SELECT
                    producto_dashboard,
                    tipo_producto,
                    COUNT(DISTINCT periodo) AS meses_observados,
                    COUNT(DISTINCT CASE WHEN qty_vendida > 0 THEN EXTRACT(MONTH FROM periodo)::int END) AS meses_activos,
                    STRING_AGG(
                        DISTINCT LPAD(EXTRACT(MONTH FROM periodo)::int::text, 2, '0'),
                        ',' ORDER BY LPAD(EXTRACT(MONTH FROM periodo)::int::text, 2, '0')
                    ) FILTER (WHERE qty_vendida > 0) AS temporada_meses,
                    SUM(GREATEST(qty_vendida, 0)) AS total_qty_historica
                FROM base
                GROUP BY producto_dashboard, tipo_producto
            )
            INSERT INTO gold.forecasting_productos_estacionales_v1 (
                producto_dashboard, tipo_producto, temporada_meses,
                meses_activos, meses_observados, active_share, total_qty_historica,
                producto_baja_rotacion, pipeline_id, batch_id, fecha_ejecucion
            )
            SELECT
                producto_dashboard,
                tipo_producto,
                COALESCE(temporada_meses, ''),
                meses_activos,
                meses_observados,
                CASE WHEN meses_observados > 0 THEN (meses_activos::numeric / meses_observados::numeric) ELSE 0 END AS active_share,
                total_qty_historica,
                (total_qty_historica < 500)::boolean AS producto_baja_rotacion,
                {pipeline_sql} AS pipeline_id,
                {batch_sql} AS batch_id,
                NOW() AS fecha_ejecucion
            FROM agg
            WHERE meses_activos > 0
              AND meses_activos <= 3
              AND (CASE WHEN meses_observados > 0 THEN (meses_activos::numeric / meses_observados::numeric) ELSE 0 END) <= 0.45
              AND total_qty_historica >= 500
            ORDER BY total_qty_historica DESC, producto_dashboard;
            """
        )

        loader.execute(
            f"""
            WITH base AS (
                SELECT
                    COALESCE(NULLIF(TRIM(producto_dashboard), ''), NULLIF(TRIM(producto_item), ''), 'SIN_NOMBRE') AS producto_dashboard,
                    UPPER(COALESCE(NULLIF(TRIM(tipo_producto), ''), 'OTRO')) AS tipo_producto,
                    DATE_TRUNC('month', periodo)::date AS periodo,
                    COALESCE(qty_vendida, 0)::numeric AS qty_vendida
                FROM silver.forecasting_base_mensual_v1
                WHERE periodo IS NOT NULL
            ),
            max_p AS (
                SELECT MAX(periodo) AS max_period FROM base
            ),
            last_active AS (
                SELECT
                    producto_dashboard,
                    tipo_producto,
                    MAX(periodo) FILTER (WHERE qty_vendida > 0) AS last_active_period
                FROM base
                GROUP BY producto_dashboard, tipo_producto
            ),
            calc AS (
                SELECT
                    l.producto_dashboard,
                    l.tipo_producto,
                    l.last_active_period,
                    CASE
                        WHEN l.last_active_period IS NULL THEN 9999
                        ELSE (
                            (EXTRACT(YEAR FROM m.max_period)::int * 12 + EXTRACT(MONTH FROM m.max_period)::int)
                            - (EXTRACT(YEAR FROM l.last_active_period)::int * 12 + EXTRACT(MONTH FROM l.last_active_period)::int)
                        )
                    END AS months_since_last_active
                FROM last_active l
                CROSS JOIN max_p m
            )
            INSERT INTO gold.forecasting_productos_inactivos_v1 (
                producto_dashboard, tipo_producto, last_active_period,
                months_since_last_active, razon_vigencia, pipeline_id, batch_id, fecha_ejecucion
            )
            SELECT
                producto_dashboard,
                tipo_producto,
                last_active_period,
                months_since_last_active,
                'SIN_ACTIVIDAD_RECIENTE' AS razon_vigencia,
                {pipeline_sql} AS pipeline_id,
                {batch_sql} AS batch_id,
                NOW() AS fecha_ejecucion
            FROM calc
            WHERE months_since_last_active >= 12
            ORDER BY months_since_last_active DESC, producto_dashboard;
            """
        )

        # Persistir cambios para que las tablas queden disponibles fuera de la
        # sesion del bloque.
        loader.conn.commit()

        est = loader.load("SELECT COUNT(*) AS n FROM gold.forecasting_productos_estacionales_v1")
        ina = loader.load("SELECT COUNT(*) AS n FROM gold.forecasting_productos_inactivos_v1")
        n_est = int(est.iloc[0]['n']) if len(est) else 0
        n_ina = int(ina.iloc[0]['n']) if len(ina) else 0

    print(f"[OK] Estacionales publicados: {n_est}")
    print(f"[OK] Inactivos publicados: {n_ina}")
    print(f"{'=' * 70}\n")

    return {
        'status': 'SUCCESS',
        'pipeline_id': pipeline_id,
        'batch_id': batch_id,
        'registros': {
            'forecasting_productos_estacionales_v1': n_est,
            'forecasting_productos_inactivos_v1': n_ina,
        },
    }


@test
def test_output(output, *args) -> None:
    assert output is not None, 'Fallo al publicar estado de forecasting'
    assert output.get('status') == 'SUCCESS', 'Publicacion de estado no fue SUCCESS'
    assert 'registros' in output, 'Faltan conteos de registros en salida'
    print(f"OK: Estado forecasting publicado - {output['registros']}")
