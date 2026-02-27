"""
Data Loader: Extraer datos de Kronos y QuickBooks hacia Bronze
Pipeline: etl_bronze
Extraccion de datos crudos desde Supabase hacia la capa Bronze.
"""
from mage_ai.settings.repo import get_repo_path
from mage_ai.io.config import ConfigFileLoader
from mage_ai.io.postgres import Postgres
from os import path
import pandas as pd
import uuid
from datetime import datetime

if 'data_loader' not in dir():
    from mage_ai.data_preparation.decorators import data_loader
if 'test' not in dir():
    from mage_ai.data_preparation.decorators import test


@data_loader
def extraer_kronos_bronze(*args, **kwargs):
    """
    Extrae datos crudos de Kronos y QuickBooks desde Supabase hacia Bronze.
    Mantiene los datos tal como vienen sin transformaciones.
    """

    # Generar IDs de lote y pipeline
    batch_id = str(uuid.uuid4())
    pipeline_id = kwargs.get('pipeline_id', 'etl_bronze')

    print(f"\n{'='*70}")
    print(f"EXTRACCION - KRONOS Y QUICKBOOKS A BRONZE")
    print(f"{'='*70}")
    print(f"Batch ID: {batch_id}")
    print(f"Pipeline ID: {pipeline_id}")
    print(f"{'='*70}\n")

    config_path = path.join(get_repo_path(), 'io_config.yaml')
    dfs = {}

    # =========================================================================
    # 1. EXTRAER: Kronos (Supabase)
    # =========================================================================

    print("[1] EXTRAYENDO DATOS DE KRONOS...")

    try:
        with Postgres.with_config(ConfigFileLoader(config_path, 'kronos')) as loader:
            print("    Extrayendo kronos.ventas_general_4...")
            query = "SELECT * FROM kronos.ventas_general_4"
            df = loader.load(query)

            df['fuente'] = 'kronos'
            df['nombre_tabla_origen'] = 'kronos.ventas_general_4'
            df['pipeline_id'] = pipeline_id
            df['batch_id'] = batch_id
            df['fecha_ingesta'] = datetime.now()

            dfs['kronos.ventas_general_4'] = df
            print(f"    Registros extraidos: {len(df)}")
    except Exception as e:
        print(f"    [ERROR] No se pudo extraer Kronos: {e}")

    # =========================================================================
    # 2. EXTRAER: QuickBooks Produccion (Supabase)
    # =========================================================================

    print("\n[2] EXTRAYENDO DATOS DE QUICKBOOKS PRODUCCION...")

    try:
        with Postgres.with_config(ConfigFileLoader(config_path, 'quickbooks')) as loader:
            # Produccion - cabecera
            print("    Extrayendo quickbooks.produccion...")
            query_prod = """
            SELECT
                p.idsales, p.idsale, p.numero, p.fecha, p.estado,
                p.cliente, p.idcliente, p.status,
                p.numitems, p.numitemsprocesados, p.numitemsopen
            FROM quickbooks.produccion p
            """
            df_prod = loader.load(query_prod)

            # Produccion - lineas (agregadas por orden)
            print("    Extrayendo quickbooks.produccion_lineas...")
            query_lineas = """
            SELECT
                pl.idsales,
                COUNT(*) as num_lineas,
                SUM(COALESCE(pl.qty, 0)) as qty_planificada,
                SUM(COALESCE(pl.qtydespachada, 0)) as qty_despachada
            FROM quickbooks.produccion_lineas pl
            GROUP BY pl.idsales
            """
            df_lineas = loader.load(query_lineas)

            # Unir produccion con lineas agregadas
            df_produccion = df_prod.merge(df_lineas, on='idsales', how='left')
            df_produccion['num_lineas'] = df_produccion['num_lineas'].fillna(0)
            df_produccion['qty_planificada'] = df_produccion['qty_planificada'].fillna(0)
            df_produccion['qty_despachada'] = df_produccion['qty_despachada'].fillna(0)

            df_produccion['fuente'] = 'quickbooks'
            df_produccion['nombre_tabla_origen'] = 'quickbooks.produccion'
            df_produccion['pipeline_id'] = pipeline_id
            df_produccion['batch_id'] = batch_id
            df_produccion['fecha_ingesta'] = datetime.now()

            dfs['quickbooks.produccion'] = df_produccion
            print(f"    Registros extraidos: {len(df_produccion)}")
    except Exception as e:
        print(f"    [ERROR] No se pudo extraer QuickBooks Produccion: {e}")

    # =========================================================================
    # 3. EXTRAER: QuickBooks Ventas (Supabase)
    # =========================================================================

    print("\n[3] EXTRAYENDO DATOS DE QUICKBOOKS VENTAS...")

    try:
        with Postgres.with_config(ConfigFileLoader(config_path, 'quickbooks')) as loader:
            # Ventas - cabecera
            print("    Extrayendo quickbooks.sales...")
            query_sales = """
            SELECT
                s.idsales, s.idsale, s.numero, s.fecha, s.estado,
                s.cliente, s.idcliente, s.status,
                s.numitems, s.numitemsprocesados
            FROM quickbooks.sales s
            """
            df_sales = loader.load(query_sales)

            # Ventas - lineas (agregadas por orden)
            print("    Extrayendo quickbooks.sales_lineas...")
            query_lineas = """
            SELECT
                sl.idsales,
                COUNT(*) as num_lineas,
                COUNT(DISTINCT sl.name) as productos_unicos,
                SUM(COALESCE(sl.qty, 0)) as qty_pedida,
                SUM(COALESCE(sl.qtydespachada, 0)) as qty_despachada
            FROM quickbooks.sales_lineas sl
            GROUP BY sl.idsales
            """
            df_lineas = loader.load(query_lineas)

            # Unir ventas con lineas agregadas
            df_ventas = df_sales.merge(df_lineas, on='idsales', how='left')
            df_ventas['num_lineas'] = df_ventas['num_lineas'].fillna(0)
            df_ventas['productos_unicos'] = df_ventas['productos_unicos'].fillna(0)
            df_ventas['qty_pedida'] = df_ventas['qty_pedida'].fillna(0)
            df_ventas['qty_despachada'] = df_ventas['qty_despachada'].fillna(0)

            df_ventas['fuente'] = 'quickbooks'
            df_ventas['nombre_tabla_origen'] = 'quickbooks.sales'
            df_ventas['pipeline_id'] = pipeline_id
            df_ventas['batch_id'] = batch_id
            df_ventas['fecha_ingesta'] = datetime.now()

            dfs['quickbooks.sales'] = df_ventas
            print(f"    Registros extraidos: {len(df_ventas)}")
    except Exception as e:
        print(f"    [ERROR] No se pudo extraer QuickBooks Ventas: {e}")

    # =========================================================================
    # RESUMEN
    # =========================================================================

    print(f"\n{'='*70}")
    print(f"RESUMEN DE EXTRACCION")
    print(f"{'='*70}")
    for tabla, df in dfs.items():
        print(f"  {tabla}: {len(df)} registros")
    print(f"{'='*70}")
    print(f"Total tablas: {len(dfs)}")
    print(f"Total registros: {sum(len(df) for df in dfs.values())}")
    print(f"{'='*70}\n")

    return {
        'dfs': dfs,
        'batch_id': batch_id,
        'pipeline_id': pipeline_id,
        'metadata': {
            'tablas': list(dfs.keys()),
            'fecha_inicio': datetime.now().isoformat(),
            'registros': sum(len(df) for df in dfs.values())
        }
    }


@test
def test_output(output, *args) -> None:
    assert output is not None, 'No se extrajeron datos'
    assert 'dfs' in output, 'Falta diccionario de dataframes'
    assert len(output['dfs']) > 0, 'No hay tablas extraidas'
    print(f"OK: Extraccion completada - {output['metadata']['registros']} registros")
