"""
Data Exporter: Cargar datos a Silver
Pipeline: etl_silver
Persiste los datos transformados en la capa Silver.
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


@data_exporter
def cargar_silver(data, *args, **kwargs):
    """
    Carga datos transformados a la capa Silver en PostgreSQL.
    """
    
    print(f"\n[DEBUG] Tipo de data recibida: {type(data)}")
    
    # Extraer dataframes
    if isinstance(data, dict):
        dfs = data.get('dfs', {})
        pipeline_id = data.get('pipeline_id', 'etl_silver')
        batch_id = data.get('batch_id')
    else:
        dfs = {}
        pipeline_id = 'etl_silver'
        batch_id = None
    
    print(f"\n{'='*70}")
    print(f"CARGA - A CAPA SILVER")
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

        # =====================================================================
        # 1. CARGAR: Kronos Ventas
        # =====================================================================
        if 'kronos_ventas' in dfs:
            print(f"[1] Cargando kronos_ventas a silver.kronos_ventas...")

            dato = dfs['kronos_ventas']
            if isinstance(dato, list):
                df = pd.DataFrame(dato)
            elif isinstance(dato, pd.DataFrame):
                df = dato.copy()
            else:
                df = pd.DataFrame()

            if len(df) > 0:
                loader.export(df, schema_name='silver', table_name='kronos_ventas', if_exists='replace')
                print(f"    Registros cargados: {len(df)}")
                resultados['kronos_ventas'] = len(df)

        # =====================================================================
        # 2. CARGAR: QuickBooks Produccion
        # =====================================================================
        if 'quickbooks_produccion' in dfs:
            print(f"[2] Cargando quickbooks_produccion a silver.quickbooks_produccion...")

            dato = dfs['quickbooks_produccion']
            if isinstance(dato, list):
                df = pd.DataFrame(dato)
            elif isinstance(dato, pd.DataFrame):
                df = dato.copy()
            else:
                df = pd.DataFrame()

            if len(df) > 0:
                loader.export(df, schema_name='silver', table_name='quickbooks_produccion', if_exists='replace')
                print(f"    Registros cargados: {len(df)}")
                resultados['quickbooks_produccion'] = len(df)

        # =====================================================================
        # 3. CARGAR: QuickBooks Ventas
        # =====================================================================
        if 'quickbooks_ventas' in dfs:
            print(f"[3] Cargando quickbooks_ventas a silver.quickbooks_ventas...")

            dato = dfs['quickbooks_ventas']
            if isinstance(dato, list):
                df = pd.DataFrame(dato)
            elif isinstance(dato, pd.DataFrame):
                df = dato.copy()
            else:
                df = pd.DataFrame()

            if len(df) > 0:
                loader.export(df, schema_name='silver', table_name='quickbooks_ventas', if_exists='replace')
                print(f"    Registros cargados: {len(df)}")
                resultados['quickbooks_ventas'] = len(df)

    print(f"\n{'='*70}")
    print(f"RESUMEN CARGA A SILVER")
    print(f"{'='*70}")
    for tabla, registros in resultados.items():
        print(f"  {tabla}: {registros} registros")
    print(f"{'='*70}")
    
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
