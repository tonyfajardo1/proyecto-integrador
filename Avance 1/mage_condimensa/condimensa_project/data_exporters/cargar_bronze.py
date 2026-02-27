"""
Data Exporter: Cargar datos a Bronze
Pipeline: etl_bronze
Persiste los datos crudos extraidos en la capa Bronze.
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
def cargar_bronze(data, *args, **kwargs):
    """
    Carga datos crudos a la capa Bronze en PostgreSQL.
    """
    
    # Extraer dfs del data
    if isinstance(data, dict):
        if 'dfs' in data:
            dfs = data.get('dfs', {})
            pipeline_id = data.get('pipeline_id', 'etl_bronze')
            batch_id = data.get('batch_id')
        else:
            dfs = data
            pipeline_id = kwargs.get('pipeline_id', 'etl_bronze')
            batch_id = None
    else:
        dfs = {}
        pipeline_id = 'etl_bronze'
        batch_id = None
    
    print(f"\n{'='*70}")
    print(f"CARGA - A CAPA BRONZE")
    print(f"{'='*70}")
    print(f"Pipeline: {pipeline_id}")
    print(f"Batch: {batch_id}")
    print(f"Tablas a cargar: {list(dfs.keys())}")
    print(f"{'='*70}\n")
    
    config_path = path.join(get_repo_path(), 'io_config.yaml')
    config_profile = 'local_dwh'
    
    resultados = {}
    
    with Postgres.with_config(ConfigFileLoader(config_path, config_profile)) as loader:

        # =====================================================================
        # 1. CARGAR: Kronos Ventas Raw
        # =====================================================================
        if 'kronos.ventas_general_4' in dfs:
            print(f"[1] Cargando kronos.ventas_general_4 a bronze.kronos_ventas_raw...")
            dato = dfs['kronos.ventas_general_4']

            if isinstance(dato, list):
                df = pd.DataFrame(dato)
            elif isinstance(dato, pd.DataFrame):
                df = dato.copy()
            else:
                df = pd.DataFrame()

            if len(df) > 0:
                # Renombrar columnas a formato Bronze
                if len(df.columns) > 15:
                    columnas_bronze = {}
                    for i, col in enumerate(df.columns[:15]):
                        columnas_bronze[col] = f'columna_{i + 1}'
                    df = df.rename(columns=columnas_bronze)

                for col in [f'columna_{i}' for i in range(1, 16)]:
                    if col not in df.columns:
                        df[col] = None

                columnas_finales = [f'columna_{i}' for i in range(1, 16)]
                columnas_finales += ['fuente', 'nombre_tabla_origen', 'fecha_ingesta', 'pipeline_id', 'batch_id']
                columnas_existentes = [c for c in columnas_finales if c in df.columns]
                df_export = df[columnas_existentes].copy()

                loader.export(df_export, schema_name='bronze', table_name='kronos_ventas_raw', if_exists='replace')
                print(f"    Registros cargados: {len(df_export)}")
                resultados['kronos_ventas_raw'] = len(df_export)

        # =====================================================================
        # 2. CARGAR: QuickBooks Produccion Raw
        # =====================================================================
        if 'quickbooks.produccion' in dfs:
            print(f"[2] Cargando quickbooks.produccion a bronze.quickbooks_produccion_raw...")
            dato = dfs['quickbooks.produccion']

            if isinstance(dato, list):
                df = pd.DataFrame(dato)
            elif isinstance(dato, pd.DataFrame):
                df = dato.copy()
            else:
                df = pd.DataFrame()

            if len(df) > 0:
                loader.export(df, schema_name='bronze', table_name='quickbooks_produccion_raw', if_exists='replace')
                print(f"    Registros cargados: {len(df)}")
                resultados['quickbooks_produccion_raw'] = len(df)

        # =====================================================================
        # 3. CARGAR: QuickBooks Ventas Raw
        # =====================================================================
        if 'quickbooks.sales' in dfs:
            print(f"[3] Cargando quickbooks.sales a bronze.quickbooks_ventas_raw...")
            dato = dfs['quickbooks.sales']

            if isinstance(dato, list):
                df = pd.DataFrame(dato)
            elif isinstance(dato, pd.DataFrame):
                df = dato.copy()
            else:
                df = pd.DataFrame()

            if len(df) > 0:
                loader.export(df, schema_name='bronze', table_name='quickbooks_ventas_raw', if_exists='replace')
                print(f"    Registros cargados: {len(df)}")
                resultados['quickbooks_ventas_raw'] = len(df)

    print(f"\n{'='*70}")
    print(f"RESUMEN CARGA A BRONZE")
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
    assert output.get('status') == 'SUCCESS', 'Status no es SUCCESS'
    print(f"OK: Carga a Bronze completada - {output['registros']}")
