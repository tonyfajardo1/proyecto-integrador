"""
Data Loader: Extraer datos de Kronos y QuickBooks hacia Bronze
Pipeline: etl_bronze
Extraccion de datos crudos hacia la capa Bronze.
"""
from mage_ai.settings.repo import get_repo_path
from mage_ai.io.config import ConfigFileLoader
from mage_ai.io.postgres import Postgres
from os import path
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

    Contrato del bloque:
    - No aplicar transformaciones de negocio.
    - Anexar metadata tecnica de ingesta (fuente, batch, pipeline, timestamp).
    - Fallar si no se obtienen tablas criticas para preservar integridad del lote.
    """

    # Generar IDs de lote y pipeline
    start_ts = datetime.now()
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
    # 1) KRONOS: detalle transaccional + resumen mensual
    # =========================================================================

    print("[1] EXTRAYENDO DATOS DE KRONOS...")

    try:
        with Postgres.with_config(ConfigFileLoader(config_path, 'kronos')) as loader:
            # Fuente transaccional (detalle) para Apriori
            tabla_detalle = None
            df_det = None
            for candidata in ['kronos.ventas_detalle', 'kronos.ventas_general_4']:
                try:
                    print(f"    Extrayendo {candidata}...")
                    df_det = loader.load(f"SELECT * FROM {candidata}")
                    tabla_detalle = candidata
                    break
                except Exception:
                    continue

            if tabla_detalle is None:
                raise Exception('No se encontro tabla transaccional Kronos (ventas_detalle/ventas_general_4)')

            if df_det is not None:
                df_det['fuente'] = 'kronos'
                df_det['nombre_tabla_origen'] = tabla_detalle
                df_det['pipeline_id'] = pipeline_id
                df_det['batch_id'] = batch_id
                df_det['fecha_ingesta'] = datetime.now()
                dfs['kronos.ventas_detalle'] = df_det
                print(f"    Registros detalle extraidos: {len(df_det)}")

            # Fuente resumen normalizada para KPIs
            tabla_resumen = None
            df_res = None
            for candidata in ['kronos.ventas_resumen', 'kronos.ventas_general_resumen']:
                try:
                    print(f"    Extrayendo {candidata}...")
                    df_res = loader.load(f"SELECT * FROM {candidata}")
                    tabla_resumen = candidata
                    break
                except Exception:
                    continue

            if tabla_resumen is not None and df_res is not None:
                df_res['fuente'] = 'kronos'
                df_res['nombre_tabla_origen'] = tabla_resumen
                df_res['pipeline_id'] = pipeline_id
                df_res['batch_id'] = batch_id
                df_res['fecha_ingesta'] = datetime.now()
                dfs['kronos.ventas_resumen'] = df_res
                print(f"    Registros resumen extraidos: {len(df_res)}")
            else:
                print("    [WARN] No se encontro tabla resumen Kronos en Supabase")
    except Exception as e:
        print(f"    [ERROR] No se pudo extraer Kronos: {e}")

    # =========================================================================
    # 2) QUICKBOOKS: produccion
    # =========================================================================

    print("\n[2] EXTRAYENDO DATOS DE QUICKBOOKS PRODUCCION (SUPABASE)...")

    try:
        with Postgres.with_config(ConfigFileLoader(config_path, 'quickbooks')) as loader_qb:
            query_prod = "SELECT * FROM quickbooks.produccion"
            df_produccion = loader_qb.load(query_prod)

        df_produccion['fuente'] = 'quickbooks'
        df_produccion['nombre_tabla_origen'] = 'quickbooks.produccion'
        df_produccion['pipeline_id'] = pipeline_id
        df_produccion['batch_id'] = batch_id
        df_produccion['fecha_ingesta'] = datetime.now()

        dfs['quickbooks.produccion'] = df_produccion
        print(f"    Registros extraidos: {len(df_produccion)}")
    except Exception as e:
        print(f"    [ERROR] No se pudo extraer QuickBooks Produccion desde Supabase: {e}")

    # =========================================================================
    # 3) QUICKBOOKS: ventas
    # =========================================================================

    print("\n[3] EXTRAYENDO DATOS DE QUICKBOOKS VENTAS (SUPABASE)...")

    try:
        with Postgres.with_config(ConfigFileLoader(config_path, 'quickbooks')) as loader_qb:
            query_sales = "SELECT * FROM quickbooks.sales"
            df_ventas = loader_qb.load(query_sales)

        df_ventas['fuente'] = 'quickbooks'
        df_ventas['nombre_tabla_origen'] = 'quickbooks.sales'
        df_ventas['pipeline_id'] = pipeline_id
        df_ventas['batch_id'] = batch_id
        df_ventas['fecha_ingesta'] = datetime.now()

        dfs['quickbooks.sales'] = df_ventas
        print(f"    Registros extraidos: {len(df_ventas)}")
    except Exception as e:
        print(f"    [ERROR] No se pudo extraer QuickBooks Ventas desde Supabase: {e}")

    # =========================================================================
    # 4) QUICKBOOKS STAGING: catalogo EAN
    # =========================================================================

    print("\n[4] EXTRAYENDO CATALOGO EAN DESDE STAGING QUICKBOOKS (SUPABASE)...")

    try:
        with Postgres.with_config(ConfigFileLoader(config_path, 'quickbooks')) as loader_qb:
            query_cat = "SELECT * FROM quickbooks.stg_catalogo_ean_raw"
            df_catalogo = loader_qb.load(query_cat)

        df_catalogo['fuente'] = 'quickbooks'
        df_catalogo['nombre_tabla_origen'] = 'quickbooks.stg_catalogo_ean_raw'
        df_catalogo['pipeline_id'] = pipeline_id
        df_catalogo['batch_id'] = batch_id
        df_catalogo['fecha_ingesta'] = datetime.now()

        dfs['quickbooks.stg_catalogo_ean_raw'] = df_catalogo
        print(f"    Registros extraidos: {len(df_catalogo)}")
    except Exception as e:
        print(f"    [ERROR] No se pudo extraer staging catalogo EAN desde Supabase: {e}")

    # =========================================================================
    # 5) QUICKBOOKS STAGING: ventas Econespecias
    # =========================================================================

    print("\n[5] EXTRAYENDO VENTAS ECONESPECIAS DESDE STAGING QUICKBOOKS (SUPABASE)...")

    try:
        with Postgres.with_config(ConfigFileLoader(config_path, 'quickbooks')) as loader_qb:
            query_ven = "SELECT * FROM quickbooks.stg_ventas_econespecias_raw"
            df_ventas_ec = loader_qb.load(query_ven)

        df_ventas_ec['fuente'] = 'quickbooks'
        df_ventas_ec['nombre_tabla_origen'] = 'quickbooks.stg_ventas_econespecias_raw'
        df_ventas_ec['pipeline_id'] = pipeline_id
        df_ventas_ec['batch_id'] = batch_id
        df_ventas_ec['fecha_ingesta'] = datetime.now()

        dfs['quickbooks.stg_ventas_econespecias_raw'] = df_ventas_ec
        print(f"    Registros extraidos: {len(df_ventas_ec)}")
    except Exception as e:
        print(f"    [ERROR] No se pudo extraer staging ventas econespecias desde Supabase: {e}")

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

    # Validacion de completitud minima del lote.
    # Si falta una tabla critica, se corta el pipeline para evitar cargas parciales.
    required_tables = [
        'kronos.ventas_detalle',
        'quickbooks.produccion',
        'quickbooks.stg_catalogo_ean_raw',
        'quickbooks.stg_ventas_econespecias_raw',
    ]
    missing_required = [t for t in required_tables if t not in dfs]
    if missing_required:
        raise RuntimeError(
            'Extraccion incompleta en Bronze. Tablas criticas faltantes: '
            + ', '.join(missing_required)
        )

    return {
        'dfs': dfs,
        'batch_id': batch_id,
        'pipeline_id': pipeline_id,
        'metadata': {
            'tablas': list(dfs.keys()),
            'fecha_inicio': start_ts.isoformat(),
            'fecha_fin': datetime.now().isoformat(),
            'registros': sum(len(df) for df in dfs.values())
        }
    }


@test
def test_output(output, *args) -> None:
    assert output is not None, 'No se extrajeron datos'
    assert 'dfs' in output, 'Falta diccionario de dataframes'
    assert len(output['dfs']) > 0, 'No hay tablas extraidas'
    print(f"OK: Extraccion completada - {output['metadata']['registros']} registros")
