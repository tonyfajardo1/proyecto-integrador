"""
Data Exporter: Publicar Forecasting V3 en Gold para dashboard
Pipeline: forecasting_v3_quickbooks
"""
from datetime import datetime
from os import path

import pandas as pd

from mage_ai.io.config import ConfigFileLoader
from mage_ai.io.postgres import Postgres
from mage_ai.settings.repo import get_repo_path

if 'data_exporter' not in dir():
    from mage_ai.data_preparation.decorators import data_exporter
if 'test' not in dir():
    from mage_ai.data_preparation.decorators import test

repo_src = path.join(get_repo_path(), 'src')
if repo_src not in __import__('sys').path:
    __import__('sys').path.insert(0, repo_src)

from forecasting_v3_mage import (
    GOLD_PREDICTION_KEY_COLUMNS,
    PREDICTION_KEY_COLUMNS,
    assert_unique_keys,
    ensure_dataframe,
)


DASHBOARD_TABLE = 'pronostico_produccion_unificado_v1'
SEASONAL_TABLE = 'forecasting_productos_estacionales_v1'
INACTIVE_TABLE = 'forecasting_productos_inactivos_v1'
DASHBOARD_COLUMNS = [
    'tipo_producto',
    'categoria_producto',
    'producto_base',
    'producto',
    'producto_dashboard',
    'product_id',
    'periodo',
    'periodo_prediccion',
    'qty_fabricada',
    'qty_planificada',
    'pronostico_qty',
    'stock_actual',
    'qty_recomendada',
    'qty_min_recomendada',
    'qty_max_recomendada',
    'nivel_confianza',
    'rolling_std_3',
    'n_ordenes',
    'sugerencia_accion',
    'posibles_causas',
    'es_vigente_operativo',
    'razon_vigencia',
    'pipeline_id',
    'fecha_ejecucion',
    'modelo_ganador',
    'fuente_modelo',
]


def _clean_value(value):
    if pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    if hasattr(value, 'item'):
        return value.item()
    return value


def _insert_dataframe(loader, table_name, df, columns):
    if df.empty:
        return
    quoted_columns = ', '.join([f'"{col}"' for col in columns])
    placeholders = ', '.join(['%s'] * len(columns))
    sql = f'INSERT INTO gold.{table_name} ({quoted_columns}) VALUES ({placeholders})'
    rows = [
        tuple(_clean_value(value) for value in row)
        for row in df[columns].itertuples(index=False, name=None)
    ]
    with loader.conn.cursor() as cur:
        cur.executemany(sql, rows)


def _sql_literal(value):
    if value is None:
        return 'NULL'
    return "'" + str(value).replace("'", "''") + "'"


def _publish_product_status_tables(loader, pipeline_id: str, batch_id):
    batch_sql = _sql_literal(batch_id)
    pipeline_sql = _sql_literal(pipeline_id)

    loader.execute(f'TRUNCATE TABLE gold.{SEASONAL_TABLE}')
    loader.execute(f'TRUNCATE TABLE gold.{INACTIVE_TABLE}')

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
        INSERT INTO gold.{SEASONAL_TABLE} (
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
        INSERT INTO gold.{INACTIVE_TABLE} (
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

    seasonal = loader.load(f'SELECT COUNT(*) AS n FROM gold.{SEASONAL_TABLE}')
    inactive = loader.load(f'SELECT COUNT(*) AS n FROM gold.{INACTIVE_TABLE}')
    return {
        SEASONAL_TABLE: int(seasonal.iloc[0]['n']) if len(seasonal) else 0,
        INACTIVE_TABLE: int(inactive.iloc[0]['n']) if len(inactive) else 0,
    }


def _dashboard_rows(predictions: pd.DataFrame, pipeline_id: str, fecha_ejecucion: datetime) -> pd.DataFrame:
    df = predictions.copy()
    df['periodo'] = pd.to_datetime(df['periodo'], errors='coerce')
    df['ultimo_periodo_entrenamiento'] = pd.to_datetime(
        df['ultimo_periodo_entrenamiento'],
        errors='coerce',
    )

    out = pd.DataFrame()
    out['tipo_producto'] = df['source_type'].astype(str).str.upper()
    out['categoria_producto'] = out['tipo_producto']
    out['producto_base'] = df['product_name']
    out['producto'] = df['product_name']
    out['producto_dashboard'] = df['product_name']
    out['product_id'] = df['product_id'].astype(str)
    out['periodo'] = df['ultimo_periodo_entrenamiento']
    out['periodo_prediccion'] = df['periodo']
    out['qty_fabricada'] = 0.0
    out['qty_planificada'] = 0.0
    out['pronostico_qty'] = pd.to_numeric(df['cantidad_predicha'], errors='coerce').fillna(0.0)
    out['stock_actual'] = pd.to_numeric(df.get('stock_actual', 0.0), errors='coerce').fillna(0.0)
    out['qty_recomendada'] = pd.to_numeric(
        df.get('cantidad_a_producir_ajustada', df['cantidad_predicha']),
        errors='coerce',
    ).fillna(out['pronostico_qty'])
    min_source_col = (
        'cantidad_min_a_producir_ajustada'
        if 'cantidad_min_a_producir_ajustada' in df.columns
        else 'prediccion_min'
    )
    max_source_col = (
        'cantidad_max_a_producir_ajustada'
        if 'cantidad_max_a_producir_ajustada' in df.columns
        else 'prediccion_max'
    )
    out['qty_min_recomendada'] = pd.to_numeric(
        df[min_source_col],
        errors='coerce',
    ).fillna(out['qty_recomendada'])
    out['qty_max_recomendada'] = pd.to_numeric(
        df[max_source_col],
        errors='coerce',
    ).fillna(out['qty_recomendada'])
    out['qty_min_recomendada'] = out['qty_min_recomendada'].where(
        out['qty_min_recomendada'].le(out['qty_recomendada']),
        out['qty_recomendada'],
    )
    out['qty_max_recomendada'] = out['qty_max_recomendada'].where(
        out['qty_max_recomendada'].ge(out['qty_recomendada']),
        out['qty_recomendada'],
    )
    out['nivel_confianza'] = df.get('confianza_prediccion', 'sin_confianza')
    out['rolling_std_3'] = pd.to_numeric(df.get('error_relativo_estimado', 0.0), errors='coerce').fillna(0.0)
    out['n_ordenes'] = 0
    out['sugerencia_accion'] = df.get('recomendacion_decision', '')
    out['posibles_causas'] = (
        df.get('alerta_inventario', '').fillna('').astype(str)
        + ' | '
        + df.get('stock_match_status', '').fillna('').astype(str)
    ).str.strip(' |')
    out['es_vigente_operativo'] = ~df.get('estado_producto', '').fillna('').astype(str).str.lower().eq('inactivo')
    out['razon_vigencia'] = df.get('estado_producto', 'sin_estado')
    out['pipeline_id'] = pipeline_id
    out['fecha_ejecucion'] = fecha_ejecucion
    out['modelo_ganador'] = df.get('modelo_usado', '')
    out['fuente_modelo'] = 'FORECASTING_V3_QUICKBOOKS'

    return out[DASHBOARD_COLUMNS].copy()


@data_exporter
def cargar_forecasting_v3_gold(data, *args, **kwargs):
    config_path = path.join(get_repo_path(), 'io_config.yaml')
    config_profile = 'local_dwh'
    pipeline_id = data.get('pipeline_id', 'forecasting_v3_quickbooks')
    batch_id = data.get('batch_id')
    fecha_ejecucion = datetime.now()
    report_outputs = data.get('report_outputs', {})

    predicciones = []
    for key in ['predicciones_pt', 'predicciones_pp']:
        if key in report_outputs:
            predicciones.append(ensure_dataframe(report_outputs[key]))

    if not predicciones:
        raise RuntimeError('No hay predicciones PT/PP para publicar en Gold.')

    prediction_df = pd.concat(predicciones, ignore_index=True, sort=False)
    assert_unique_keys(prediction_df, PREDICTION_KEY_COLUMNS, 'predicciones consolidadas para Gold')
    dashboard_df = _dashboard_rows(
        prediction_df,
        pipeline_id,
        fecha_ejecucion,
    )
    assert_unique_keys(dashboard_df, GOLD_PREDICTION_KEY_COLUMNS, f'gold.{DASHBOARD_TABLE}')

    print("\n" + "=" * 70)
    print("PUBLICANDO GOLD DASHBOARD - FORECASTING V3 QUICKBOOKS")
    print("=" * 70)

    with Postgres.with_config(ConfigFileLoader(config_path, config_profile)) as loader:
        loader.execute(f'TRUNCATE TABLE gold.{DASHBOARD_TABLE}')
        _insert_dataframe(loader, DASHBOARD_TABLE, dashboard_df, DASHBOARD_COLUMNS)
        status_counts = _publish_product_status_tables(loader, pipeline_id, batch_id)
        loader.conn.commit()

    print(f"  gold.{DASHBOARD_TABLE}: {len(dashboard_df)} registros")
    print(f"  gold.{SEASONAL_TABLE}: {status_counts[SEASONAL_TABLE]} registros")
    print(f"  gold.{INACTIVE_TABLE}: {status_counts[INACTIVE_TABLE]} registros")
    print("  Reportes tecnicos conservados como CSV en data/forecasting_v3/reports")

    return {
        'status': 'SUCCESS',
        'loaded': {
            DASHBOARD_TABLE: int(dashboard_df.shape[0]),
            **status_counts,
        },
        'duplicate_checks': {
            'prediction_key': '+'.join(PREDICTION_KEY_COLUMNS),
            'gold_key': '+'.join(GOLD_PREDICTION_KEY_COLUMNS),
        },
        'csv_reports_dir': 'data/forecasting_v3/reports',
        'pipeline_id': pipeline_id,
        'batch_id': batch_id,
    }


@test
def test_output(output, *args) -> None:
    assert output is not None, 'Carga Gold Forecasting V3 no genero salida'
    assert output.get('status') == 'SUCCESS', 'Carga Gold Forecasting V3 fallo'
    assert output.get('loaded', {}).get(DASHBOARD_TABLE, 0) > 0, 'No se cargo tabla dashboard'
    assert output.get('duplicate_checks', {}).get('gold_key'), 'No se valido unicidad de Gold'
