"""
Data Loader: Extraer datos desde Bronze hacia Silver
Pipeline: etl_silver
Extrae datos de la capa Bronze para transformarlos.
"""
from mage_ai.settings.repo import get_repo_path
from mage_ai.io.config import ConfigFileLoader
from mage_ai.io.postgres import Postgres
from os import path
import pandas as pd
import uuid

if 'data_loader' not in dir():
    from mage_ai.data_preparation.decorators import data_loader
if 'test' not in dir():
    from mage_ai.data_preparation.decorators import test


@data_loader
def extraer_desde_bronze(*args, **kwargs):
    """
    Extrae datos desde la capa Bronze para transformarlos en Silver.
    """
    
    batch_id = str(uuid.uuid4())
    pipeline_id = kwargs.get('pipeline_id', 'etl_silver')
    
    print(f"\n{'='*70}")
    print(f"EXTRACCION - DESDE BRONZE")
    print(f"{'='*70}")
    print(f"Batch ID: {batch_id}")
    print(f"Pipeline ID: {pipeline_id}")
    print(f"{'='*70}\n")
    
    config_path = path.join(get_repo_path(), 'io_config.yaml')
    config_profile = 'local_dwh'
    
    dfs = {}
    
    with Postgres.with_config(ConfigFileLoader(config_path, config_profile)) as loader:

        # Extraer: kronos_ventas_raw
        print("Extrayendo bronze.kronos_ventas_raw...")
        try:
            query = "SELECT * FROM bronze.kronos_ventas_raw"
            df = loader.load(query)
            dfs['kronos_ventas_raw'] = df
            print(f"  Registros: {len(df)}")
        except Exception as e:
            print(f"  [WARN] No se pudo extraer kronos_ventas_raw: {e}")

        # Extraer: quickbooks_produccion_raw (opcional)
        print("Extrayendo bronze.quickbooks_produccion_raw...")
        try:
            query = "SELECT * FROM bronze.quickbooks_produccion_raw"
            df = loader.load(query)
            dfs['quickbooks_produccion_raw'] = df
            print(f"  Registros: {len(df)}")
        except Exception as e:
            print(f"  [WARN] Tabla no existe aun: {e}")

        # Extraer: quickbooks_ventas_raw (opcional)
        print("Extrayendo bronze.quickbooks_ventas_raw...")
        try:
            query = "SELECT * FROM bronze.quickbooks_ventas_raw"
            df = loader.load(query)
            dfs['quickbooks_ventas_raw'] = df
            print(f"  Registros: {len(df)}")
        except Exception as e:
            print(f"  [WARN] Tabla no existe aun: {e}")
    
    print(f"\n[OK] Extraccion desde Bronze completada")
    print(f"Total tablas: {len(dfs)}")
    print(f"Total registros: {sum(len(df) for df in dfs.values())}")
    
    return {
        'dfs': dfs,
        'batch_id': batch_id,
        'pipeline_id': pipeline_id,
        'metadata': {
            'tablas': list(dfs.keys()),
            'registros': sum(len(df) for df in dfs.values())
        }
    }


@test
def test_output(output, *args) -> None:
    assert output is not None, 'No se extrajeron datos'
    assert 'dfs' in output, 'Falta diccionario de dataframes'
    assert len(output['dfs']) > 0, 'No hay tablas extraidas'
    print(f"OK: Extraccion completada - {output['metadata']['registros']} registros")
