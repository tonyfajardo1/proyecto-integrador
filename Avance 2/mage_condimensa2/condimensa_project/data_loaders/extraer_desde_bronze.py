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
    Extrae datos desde Bronze y fuentes operacionales para Silver.

    Flujo del bloque:
    - Genera trazabilidad de ejecucion (`batch_id`, `pipeline_id`).
    - Lee tablas raw de Bronze por dominio (Kronos y QuickBooks).
    - Lee dataset transaccional de QuickBooks para reglas de asociacion.
    - Valida que tablas criticas existan antes de transformar.

    Salida:
    - Diccionario `dfs` con dataframes fuente.
    - Metadata de conteo de tablas y registros.
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
    
    # Conexion 1: tablas Bronze de Kronos.
    with Postgres.with_config(ConfigFileLoader(config_path, config_profile)) as loader:

        # Extraer: kronos_ventas_raw
        print("[1] Extrayendo bronze.kronos_ventas_raw...")
        try:
            query = "SELECT * FROM bronze.kronos_ventas_raw"
            df = loader.load(query)
            dfs['kronos_ventas_raw'] = df
            print(f"    Registros: {len(df)}")
        except Exception as e:
            print(f"    [WARN] No se pudo extraer: {e}")

        # Extraer: kronos_ventas_detalle_raw (transaccional)
        print("[1b] Extrayendo bronze.kronos_ventas_detalle_raw...")
        try:
            query = "SELECT * FROM bronze.kronos_ventas_detalle_raw"
            df = loader.load(query)
            dfs['kronos_ventas_detalle_raw'] = df
            print(f"    Registros: {len(df)}")
        except Exception as e:
            print(f"    [WARN] No se pudo extraer detalle Kronos: {e}")

        # Extraer: kronos_ventas_resumen_raw (reporte normalizado)
        print("[1c] Extrayendo bronze.kronos_ventas_resumen_raw...")
        try:
            query = "SELECT * FROM bronze.kronos_ventas_resumen_raw"
            df = loader.load(query)
            dfs['kronos_ventas_resumen_raw'] = df
            print(f"    Registros: {len(df)}")
        except Exception as e:
            print(f"    [WARN] No se pudo extraer resumen Kronos: {e}")

    # Conexion 2: tablas Bronze de QuickBooks.
    # Se mantiene separada para aislar errores por dominio y facilitar diagnostico.
    # Extraer: quickbooks_produccion_raw
    print("[2] Extrayendo bronze.quickbooks_produccion_raw...")
    with Postgres.with_config(ConfigFileLoader(config_path, config_profile)) as loader:
        try:
            query = "SELECT * FROM bronze.quickbooks_produccion_raw"
            df = loader.load(query)
            dfs['quickbooks_produccion_raw'] = df
            print(f"    Registros: {len(df)}")
        except Exception as e:
            print(f"    [WARN] No se pudo extraer quickbooks_produccion_raw: {e}")

        # Extraer: quickbooks_ventas_raw
        print("[3] Extrayendo bronze.quickbooks_ventas_raw...")
        try:
            query = "SELECT * FROM bronze.quickbooks_ventas_raw"
            df = loader.load(query)
            dfs['quickbooks_ventas_raw'] = df
            print(f"    Registros: {len(df)}")
        except Exception as e:
            print(f"    [WARN] No se pudo extraer quickbooks_ventas_raw: {e}")

        # Extraer: quickbooks_catalogo_ean_raw
        print("[3b] Extrayendo bronze.quickbooks_catalogo_ean_raw...")
        try:
            query = "SELECT * FROM bronze.quickbooks_catalogo_ean_raw"
            df = loader.load(query)
            dfs['quickbooks_catalogo_ean_raw'] = df
            print(f"    Registros: {len(df)}")
        except Exception as e:
            print(f"    [WARN] No se pudo extraer quickbooks_catalogo_ean_raw: {e}")

        # Extraer: quickbooks_ventas_econespecias_raw
        print("[3c] Extrayendo bronze.quickbooks_ventas_econespecias_raw...")
        try:
            query = "SELECT * FROM bronze.quickbooks_ventas_econespecias_raw"
            df = loader.load(query)
            dfs['quickbooks_ventas_econespecias_raw'] = df
            print(f"    Registros: {len(df)}")
        except Exception as e:
            print(f"    [WARN] No se pudo extraer quickbooks_ventas_econespecias_raw: {e}")

    # Conexion 3: fuente operacional QuickBooks para Apriori (ticket-item).
    # Este dataset complementa Bronze cuando se requiere granularidad transaccional.
    print("[4] Extrayendo quickbooks.sales (transaccional) para Apriori...")
    try:
        with Postgres.with_config(ConfigFileLoader(config_path, 'quickbooks')) as loader_qb:
            query = """
            SELECT
                numero,
                fecha,
                asesor,
                cliente,
                item,
                qty,
                sales_price,
                amount,
                tipo_documento
            FROM quickbooks.sales
            WHERE numero IS NOT NULL
              AND item IS NOT NULL
              AND fecha IS NOT NULL
            """
            df_qb = loader_qb.load(query)
            dfs['quickbooks_sales_local_raw'] = df_qb
            print(f"    Registros: {len(df_qb)}")
    except Exception as e:
        print(f"    [WARN] No se pudo extraer quickbooks.sales: {e}")

    # Tablas minimas para que la transformacion Silver sea valida.
    required_tables = [
        'kronos_ventas_detalle_raw',
        'quickbooks_produccion_raw',
        'quickbooks_ventas_raw',
        'quickbooks_catalogo_ean_raw',
        'quickbooks_ventas_econespecias_raw',
    ]
    missing_required = [t for t in required_tables if t not in dfs]
    if missing_required:
        raise RuntimeError(
            'Extraccion Silver incompleta. Tablas Bronze criticas faltantes: '
            + ', '.join(missing_required)
        )

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
