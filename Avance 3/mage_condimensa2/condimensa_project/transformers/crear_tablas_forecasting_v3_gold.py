"""
Transformer: Crear tabla Gold esencial para Forecasting V3 QuickBooks
Pipeline: forecasting_v3_quickbooks
"""
from os import path

from mage_ai.io.config import ConfigFileLoader
from mage_ai.io.postgres import Postgres
from mage_ai.settings.repo import get_repo_path

if 'transformer' not in dir():
    from mage_ai.data_preparation.decorators import transformer
if 'test' not in dir():
    from mage_ai.data_preparation.decorators import test


@transformer
def crear_tablas_forecasting_v3_gold(*args, **kwargs):
    """
    Mantiene Gold liviano para dashboard.

    El pipeline Forecasting V3 genera todos los reportes tecnicos como CSV en
    `data/forecasting_v3/reports`; en Gold solo publica la tabla operacional
    que consume el dashboard: `gold.pronostico_produccion_unificado_v1`.
    """
    config_path = path.join(get_repo_path(), 'io_config.yaml')
    config_profile = 'local_dwh'

    sql = '''
    CREATE SCHEMA IF NOT EXISTS gold;

    -- Limpieza de tablas tecnicas creadas por la primera version del pipeline.
    DROP TABLE IF EXISTS gold.forecasting_v3_predicciones_pp;
    DROP TABLE IF EXISTS gold.forecasting_v3_predicciones_pt;
    DROP TABLE IF EXISTS gold.forecasting_v3_metricas_modelo;
    DROP TABLE IF EXISTS gold.forecasting_v3_validacion_modelos;
    DROP TABLE IF EXISTS gold.forecasting_v3_comparacion_modelos;
    DROP TABLE IF EXISTS gold.forecasting_v3_backtest;
    DROP TABLE IF EXISTS gold.forecasting_v3_hgb_tuning;
    DROP TABLE IF EXISTS gold.forecasting_v3_productos_error_alto;
    DROP TABLE IF EXISTS gold.forecasting_v3_model_runs;

    CREATE TABLE IF NOT EXISTS gold.pronostico_produccion_unificado_v1 (
        id SERIAL PRIMARY KEY,
        tipo_producto VARCHAR(20),
        categoria_producto VARCHAR(255),
        producto_base TEXT,
        producto TEXT,
        producto_dashboard TEXT,
        periodo DATE,
        periodo_prediccion DATE,
        qty_fabricada NUMERIC,
        qty_planificada NUMERIC,
        pronostico_qty NUMERIC,
        stock_actual NUMERIC,
        qty_recomendada NUMERIC,
        qty_min_recomendada NUMERIC,
        qty_max_recomendada NUMERIC,
        nivel_confianza VARCHAR(30),
        rolling_std_3 NUMERIC,
        n_ordenes INTEGER,
        sugerencia_accion TEXT,
        posibles_causas TEXT,
        es_vigente_operativo BOOLEAN,
        razon_vigencia VARCHAR(80),
        pipeline_id VARCHAR(80),
        fecha_ejecucion TIMESTAMP,
        modelo_ganador VARCHAR(80),
        fuente_modelo VARCHAR(80)
    );

    ALTER TABLE gold.pronostico_produccion_unificado_v1
        ADD COLUMN IF NOT EXISTS stock_actual NUMERIC;

    TRUNCATE TABLE gold.pronostico_produccion_unificado_v1;
    '''

    print("\n" + "=" * 70)
    print("CREANDO GOLD ESENCIAL - FORECASTING V3 QUICKBOOKS")
    print("=" * 70)

    with Postgres.with_config(ConfigFileLoader(config_path, config_profile)) as loader:
        loader.execute(sql)
        loader.conn.commit()

    return {'status': 'SUCCESS', 'tabla_gold': 'gold.pronostico_produccion_unificado_v1'}


@test
def test_output(output, *args) -> None:
    assert output is not None, 'Fallo al preparar Gold Forecasting V3'
    assert output.get('status') == 'SUCCESS', 'Status no es SUCCESS'
