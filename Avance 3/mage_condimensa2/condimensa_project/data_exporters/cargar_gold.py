"""
Data Exporter: Cargar KPIs y resultados a Gold
Pipeline: etl_gold
Persiste KPIs calculados en la capa Gold.
"""
from mage_ai.settings.repo import get_repo_path
from mage_ai.io.config import ConfigFileLoader
from mage_ai.io.postgres import Postgres
from os import path
import pandas as pd

if 'data_exporter' not in dir():
    from mage_ai.data_preparation.decorators import data_exporter
if 'test' not in dir():
    from mage_ai.data_preparation.decorators import test


GOLD_LOAD_ORDER = [
    ('kpis_ventas', '[1] Cargando KPIs de ventas a gold.kpis_ventas...'),
    ('metricas_agencias', '[2] Cargando metricas por agencia a gold.metricas_agencias...'),
    ('metricas_productos', '[3] Cargando metricas por producto a gold.metricas_productos...'),
    ('kpis_produccion', '[4] Cargando KPIs de produccion a gold.kpis_produccion...'),
    ('kpis_quickbooks_ventas', '[5] Cargando KPIs de ventas QuickBooks a gold.kpis_quickbooks_ventas...'),
]

TABLES_ALLOW_EMPTY_WHEN_MISSING = {'kpis_quickbooks_ventas'}


def _normalize_df(df):
    if isinstance(df, list):
        return pd.DataFrame(df)
    if isinstance(df, pd.DataFrame):
        return df.copy()
    return pd.DataFrame()


def _table_columns(loader, table_name):
    query = f"""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'gold'
          AND table_name = '{table_name}'
        ORDER BY ordinal_position
    """
    df = loader.load(query)
    columns = [col for col in df['column_name'].tolist() if col != 'id']
    if not columns:
        raise RuntimeError(
            f"No existe contrato de columnas para gold.{table_name}. "
            "Ejecuta primero el bloque crear_tablas_gold."
        )
    return columns


def _prepare_for_export(df, columns):
    prepared = _normalize_df(df)
    for column in columns:
        if column not in prepared.columns:
            prepared[column] = None
    return prepared[columns]


def _truncate(loader, table_name):
    loader.execute(f'TRUNCATE TABLE gold.{table_name}')


def _load_gold_table(loader, table_name, raw_df):
    columns = _table_columns(loader, table_name)
    df = _prepare_for_export(raw_df, columns)

    _truncate(loader, table_name)

    if len(df) > 0:
        loader.export(
            df,
            schema_name='gold',
            table_name=table_name,
            if_exists='append'
        )

    return len(df)


@data_exporter
def cargar_gold(data, *args, **kwargs):
    """
    Carga KPIs y metricas a la capa Gold en PostgreSQL.

    Flujo del bloque:
    1) Lee dataframes calculados por el transformador de KPIs.
    2) Usa el contrato creado por crear_tablas_gold y limpia tablas de salida.
    3) Exporta cada KPI con trazabilidad de pipeline/batch.
    4) Valida que las tablas criticas de Gold se hayan cargado.
    """
    
    print(f"\n[DEBUG] Tipo de data recibida: {type(data)}")
    
    # Extraer payload estandar del pipeline.
    if isinstance(data, dict):
        dfs = data.get('dfs') or {}
        pipeline_id = data.get('pipeline_id', 'etl_gold')
        batch_id = data.get('batch_id')
    else:
        dfs = {}
        pipeline_id = 'etl_gold'
        batch_id = None
    
    print(f"\n{'='*70}")
    print(f"CARGA - A CAPA GOLD")
    print(f"{'='*70}")
    print(f"Pipeline: {pipeline_id}")
    print(f"Batch: {batch_id}")
    print(f"Keys en dfs: {list(dfs.keys())}")
    print(f"{'='*70}\n")
    
    # Configurar conexion a DWH local
    config_path = path.join(get_repo_path(), 'io_config.yaml')
    config_profile = 'local_dwh'
    
    resultados = {}
    
    with Postgres.with_config(ConfigFileLoader(config_path, config_profile)) as loader:
        for table_name, message in GOLD_LOAD_ORDER:
            if table_name not in dfs:
                if table_name in TABLES_ALLOW_EMPTY_WHEN_MISSING:
                    print(f"{message}")
                    print("    Sin datos en este batch; limpiando tabla destino...")
                    resultados[table_name] = _load_gold_table(loader, table_name, pd.DataFrame())
                else:
                    print(f"[WARN] No se recibio dataframe para gold.{table_name}")
                continue

            print(message)
            df = _normalize_df(dfs[table_name])
            print(f"    DataFrame shape: {df.shape}")

            registros = _load_gold_table(loader, table_name, df)
            print(f"    Registros cargados: {registros}")
            resultados[table_name] = registros

    print(f"\n{'='*70}")
    print(f"RESUMEN CARGA A GOLD")
    print(f"{'='*70}")
    for tabla, registros in resultados.items():
        print(f"  {tabla}: {registros} registros")
    print(f"{'='*70}")

    required_loaded = [table_name for table_name, _ in GOLD_LOAD_ORDER]
    missing_loaded = [t for t in required_loaded if t not in resultados]
    if missing_loaded:
        raise RuntimeError(
            'Carga Gold incompleta. Tablas criticas no cargadas: '
            + ', '.join(missing_loaded)
        )

    return {
        'tablas': list(resultados.keys()),
        'registros': resultados,
        'pipeline_id': pipeline_id,
        'batch_id': batch_id,
        'status': 'SUCCESS'
    }


@test
def test_output(output, *args) -> None:
    assert output is not None, 'Carga fallo'
    assert 'status' in output, 'Falta status'
    assert output['status'] == 'SUCCESS', 'Status no es SUCCESS'
    print(f"OK: Carga completada - {output['registros']}")
