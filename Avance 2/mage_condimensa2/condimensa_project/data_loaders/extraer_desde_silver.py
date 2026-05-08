"""
Data Loader: Extraer datos desde Silver hacia Gold
Pipeline: etl_gold
Extrae datos de la capa Silver para calcular KPIs.
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
def extraer_desde_silver(*args, **kwargs):
    """
    Extrae datos desde Silver para el calculo de KPIs en Gold.

    Flujo del bloque:
    - Genera identificadores de trazabilidad (`batch_id`, `pipeline_id`).
    - Extrae tablas curadas necesarias para agregaciones Gold.
    - Valida presencia de tablas criticas antes de transformar.

    Salida:
    - Diccionario `dfs` con dataframes fuente.
    - Metadata de tablas y total de registros extraidos.
    """
    
    batch_id = str(uuid.uuid4())
    pipeline_id = kwargs.get('pipeline_id', 'etl_gold')
    
    print(f"\n{'='*70}")
    print(f"EXTRACCION - DESDE SILVER")
    print(f"{'='*70}")
    print(f"Batch ID: {batch_id}")
    print(f"Pipeline ID: {pipeline_id}")
    print(f"{'='*70}\n")
    
    config_path = path.join(get_repo_path(), 'io_config.yaml')
    config_profile = 'local_dwh'
    
    dfs = {}
    
    # Conexion unica al DWH local para lectura de tablas Silver.
    with Postgres.with_config(ConfigFileLoader(config_path, config_profile)) as loader:

        # Extraer: kronos_ventas (Silver)
        print("[1] Extrayendo silver.kronos_ventas...")
        try:
            query = "SELECT * FROM silver.kronos_ventas"
            df = loader.load(query)
            dfs['kronos_ventas'] = df
            print(f"    Registros: {len(df)}")
        except Exception as e:
            print(f"    [WARN] No se pudo extraer: {e}")

        # Extraer: quickbooks_produccion (Silver)
        print("[2] Extrayendo silver.quickbooks_produccion...")
        try:
            query = "SELECT * FROM silver.quickbooks_produccion"
            df = loader.load(query)
            dfs['quickbooks_produccion'] = df
            print(f"    Registros: {len(df)}")
        except Exception as e:
            print(f"    [WARN] No se pudo extraer: {e}")

        # Extraer: quickbooks_ventas (Silver)
        print("[3] Extrayendo silver.quickbooks_ventas...")
        try:
            query = "SELECT * FROM silver.quickbooks_ventas"
            df = loader.load(query)
            dfs['quickbooks_ventas'] = df
            print(f"    Registros: {len(df)}")
        except Exception as e:
            print(f"    [WARN] No se pudo extraer: {e}")
    
    required_tables = ['kronos_ventas', 'quickbooks_produccion', 'quickbooks_ventas']
    missing_required = [t for t in required_tables if t not in dfs]
    if missing_required:
        raise RuntimeError(
            'Extraccion Gold incompleta. Tablas Silver criticas faltantes: '
            + ', '.join(missing_required)
        )

    print(f"\n[OK] Extraccion desde Silver completada")
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
