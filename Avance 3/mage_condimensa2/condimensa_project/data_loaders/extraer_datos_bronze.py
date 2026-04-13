"""
Data Loader: Extraer datos de Kronos y QuickBooks hacia Bronze
Pipeline: etl_bronze
Extraccion de datos crudos hacia la capa Bronze.
"""
from mage_ai.settings.repo import get_repo_path
from mage_ai.io.config import ConfigFileLoader
from mage_ai.io.postgres import Postgres
from os import path
import os
import uuid
from datetime import datetime

if 'data_loader' not in dir():
    from mage_ai.data_preparation.decorators import data_loader
if 'test' not in dir():
    from mage_ai.data_preparation.decorators import test


def _missing_env_vars(prefix: str) -> list:
    required = [
        f'{prefix}_HOST',
        f'{prefix}_PORT',
        f'{prefix}_DB',
        f'{prefix}_USER',
        f'{prefix}_PASSWORD',
    ]
    return [name for name in required if not str(os.getenv(name, '')).strip()]


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
    require_kronos = bool(kwargs.get('require_kronos', False))

    missing_qb = _missing_env_vars('QUICKBOOKS')
    if missing_qb:
        raise RuntimeError(
            'Variables de entorno faltantes para QuickBooks: '
            + ', '.join(missing_qb)
            + '. Actualiza mage_condimensa2/.env y reinicia contenedores.'
        )

    missing_kronos = _missing_env_vars('KRONOS')
    if missing_kronos and require_kronos:
        raise RuntimeError(
            'Variables de entorno faltantes para Kronos: '
            + ', '.join(missing_kronos)
            + '. Con require_kronos=True no se puede continuar sin estas credenciales.'
        )
    if missing_kronos and not require_kronos:
        print(
            '[WARN] Variables faltantes para Kronos: '
            + ', '.join(missing_kronos)
            + '. Se omite Kronos y se continua con QuickBooks.'
        )

    # =========================================================================
    # 1) KRONOS: detalle transaccional + resumen mensual
    # =========================================================================

    print("[1] EXTRAYENDO DATOS DE KRONOS...")

    if missing_kronos and not require_kronos:
        print("    [WARN] Se omite extraccion Kronos por credenciales incompletas.")
    else:
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
    # 2) QUICKBOOKS: produccion desde public.raw_produccion
    # =========================================================================

    print("\n[2] EXTRAYENDO PRODUCCION DESDE public.raw_produccion (SUPABASE)...")

    try:
        with Postgres.with_config(ConfigFileLoader(config_path, 'quickbooks')) as loader_qb:
            query_prod = """
                SELECT
                    NULLIF(BTRIM(data->>'PRODUCCION 2025[No.]'), '') AS id_registro,
                    CASE
                        WHEN NULLIF(BTRIM(data->>'PRODUCCION 2025[FECHA]'), '') IS NULL THEN NULL
                        ELSE (data->>'PRODUCCION 2025[FECHA]')::timestamp::date
                    END AS fecha,
                    NULLIF(BTRIM(data->>'PRODUCCION 2025[NUMERO]'), '') AS numero,
                    NULLIF(BTRIM(data->>'PRODUCCION 2025[LOTE]'), '') AS lote,
                    NULLIF(BTRIM(data->>'PRODUCCION 2025[PRODUCTO]'), '') AS producto,
                    NULLIF(BTRIM(data->>'PRODUCCION 2025[Q. PANIFICDA]'), '')::numeric AS qty_planificada,
                    NULLIF(BTRIM(data->>'PRODUCCION 2025[Q. LIBERADA]'), '')::numeric AS qty_liberada,
                    NULLIF(BTRIM(data->>'PRODUCCION 2025[Q. FABRICADA]'), '')::numeric AS qty_fabricada
                FROM public.raw_produccion
                WHERE NULLIF(BTRIM(data->>'PRODUCCION 2025[PRODUCTO]'), '') IS NOT NULL
            """
            df_produccion = loader_qb.load(query_prod)

        df_produccion['fuente'] = 'quickbooks'
        df_produccion['nombre_tabla_origen'] = 'public.raw_produccion'
        df_produccion['pipeline_id'] = pipeline_id
        df_produccion['batch_id'] = batch_id
        df_produccion['fecha_ingesta'] = datetime.now()

        dfs['quickbooks.produccion'] = df_produccion
        print(f"    Registros extraidos: {len(df_produccion)}")
    except Exception as e:
        print(f"    [ERROR] No se pudo extraer produccion desde public.raw_produccion: {e}")

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
    # 4) QUICKBOOKS STAGING: catalogo EAN desde public.raw_catalogo
    # =========================================================================

    print("\n[4] EXTRAYENDO CATALOGO EAN DESDE public.raw_catalogo (SUPABASE)...")

    try:
        with Postgres.with_config(ConfigFileLoader(config_path, 'quickbooks')) as loader_qb:
            query_cat = """
                SELECT
                    NULLIF(BTRIM(data->>'ean_13_ean_14[Item]'), '') AS item,
                    NULLIF(BTRIM(data->>'ean_13_ean_14[Description]'), '') AS description,
                    NULLIF(BTRIM(data->>'ean_13_ean_14[U/M]'), '') AS um,
                    NULLIF(BTRIM(data->>'ean_13_ean_14[Price]'), '')::numeric AS price,
                    NULLIF(BTRIM(data->>'ean_13_ean_14[EAN13]'), '') AS ean13,
                    NULLIF(BTRIM(data->>'ean_13_ean_14[EAN14]'), '') AS ean14,
                    'public.raw_catalogo' AS source_file,
                    'jsonb.data' AS source_sheet,
                    extracted_at AS load_ts,
                    md5(CONCAT_WS(
                        '|',
                        COALESCE(data->>'ean_13_ean_14[Item]', ''),
                        COALESCE(data->>'ean_13_ean_14[Description]', ''),
                        COALESCE(data->>'ean_13_ean_14[U/M]', ''),
                        COALESCE(data->>'ean_13_ean_14[Price]', ''),
                        COALESCE(data->>'ean_13_ean_14[EAN13]', ''),
                        COALESCE(data->>'ean_13_ean_14[EAN14]', '')
                    )) AS row_hash
                FROM public.raw_catalogo
                WHERE NULLIF(BTRIM(data->>'ean_13_ean_14[Item]'), '') IS NOT NULL
            """
            df_catalogo = loader_qb.load(query_cat)

        df_catalogo['fuente'] = 'quickbooks'
        df_catalogo['nombre_tabla_origen'] = 'public.raw_catalogo'
        df_catalogo['pipeline_id'] = pipeline_id
        df_catalogo['batch_id'] = batch_id
        df_catalogo['fecha_ingesta'] = datetime.now()

        dfs['quickbooks.stg_catalogo_ean_raw'] = df_catalogo
        print(f"    Registros extraidos: {len(df_catalogo)}")
    except Exception as e:
        print(f"    [ERROR] No se pudo extraer catalogo EAN desde public.raw_catalogo: {e}")

    # =========================================================================
    # 5) QUICKBOOKS STAGING: ventas Econespecias desde public.raw_ventas
    # =========================================================================

    print("\n[5] EXTRAYENDO VENTAS ECONESPECIAS DESDE public.raw_ventas (SUPABASE)...")

    try:
        with Postgres.with_config(ConfigFileLoader(config_path, 'quickbooks')) as loader_qb:
            query_ven = """
                WITH mapped AS (
                    SELECT
                        NULLIF(BTRIM(data->>'Ventas Econespecias[Marca]'), '') AS marca,
                        NULLIF(BTRIM(data->>'Ventas Econespecias[Familia]'), '') AS familia,
                        NULLIF(BTRIM(data->>'Ventas Econespecias[Producto]'), '') AS producto,
                        NULLIF(BTRIM(data->>'Ventas Econespecias[Recuento de Cliente]'), '')::integer AS recuento_cliente,
                        NULLIF(BTRIM(data->>'Ventas Econespecias[Cantidad]'), '')::numeric AS cantidad,
                        NULLIF(BTRIM(data->>'Ventas Econespecias[Ventas]'), '')::numeric AS ventas,
                        NULLIF(BTRIM(data->>'Ventas Econespecias[A\u00f1o]'), '')::integer AS anio,
                        LOWER(NULLIF(BTRIM(data->>'Ventas Econespecias[Mes]'), '')) AS mes,
                        'public.raw_ventas' AS source_file,
                        'jsonb.data' AS source_sheet,
                        extracted_at AS load_ts,
                        md5(CONCAT_WS(
                            '|',
                            COALESCE(data->>'Ventas Econespecias[Marca]', ''),
                            COALESCE(data->>'Ventas Econespecias[Familia]', ''),
                            COALESCE(data->>'Ventas Econespecias[Producto]', ''),
                            COALESCE(data->>'Ventas Econespecias[Recuento de Cliente]', ''),
                            COALESCE(data->>'Ventas Econespecias[Cantidad]', ''),
                            COALESCE(data->>'Ventas Econespecias[Ventas]', ''),
                            COALESCE(data->>'Ventas Econespecias[A\u00f1o]', ''),
                            COALESCE(data->>'Ventas Econespecias[Mes]', '')
                        )) AS row_hash
                    FROM public.raw_ventas
                    WHERE NULLIF(BTRIM(data->>'Ventas Econespecias[Producto]'), '') IS NOT NULL
                )
                SELECT
                    marca,
                    familia,
                    producto,
                    recuento_cliente,
                    cantidad,
                    ventas,
                    anio,
                    mes,
                    CASE mes
                        WHEN 'enero' THEN make_date(anio, 1, 1)
                        WHEN 'febrero' THEN make_date(anio, 2, 1)
                        WHEN 'marzo' THEN make_date(anio, 3, 1)
                        WHEN 'abril' THEN make_date(anio, 4, 1)
                        WHEN 'mayo' THEN make_date(anio, 5, 1)
                        WHEN 'junio' THEN make_date(anio, 6, 1)
                        WHEN 'julio' THEN make_date(anio, 7, 1)
                        WHEN 'agosto' THEN make_date(anio, 8, 1)
                        WHEN 'septiembre' THEN make_date(anio, 9, 1)
                        WHEN 'setiembre' THEN make_date(anio, 9, 1)
                        WHEN 'octubre' THEN make_date(anio, 10, 1)
                        WHEN 'noviembre' THEN make_date(anio, 11, 1)
                        WHEN 'diciembre' THEN make_date(anio, 12, 1)
                        ELSE NULL
                    END AS periodo,
                    source_file,
                    source_sheet,
                    load_ts,
                    row_hash
                FROM mapped
            """
            df_ventas_ec = loader_qb.load(query_ven)

        df_ventas_ec['fuente'] = 'quickbooks'
        df_ventas_ec['nombre_tabla_origen'] = 'public.raw_ventas'
        df_ventas_ec['pipeline_id'] = pipeline_id
        df_ventas_ec['batch_id'] = batch_id
        df_ventas_ec['fecha_ingesta'] = datetime.now()

        dfs['quickbooks.stg_ventas_econespecias_raw'] = df_ventas_ec
        print(f"    Registros extraidos: {len(df_ventas_ec)}")
    except Exception as e:
        print(f"    [ERROR] No se pudo extraer ventas econespecias desde public.raw_ventas: {e}")

    # =========================================================================
    # 6) QUICKBOOKS STAGING: categorias PP (produccion 2025)
    # =========================================================================

    print("\n[6] EXTRAYENDO CATEGORIAS PP DESDE STAGING QUICKBOOKS (SUPABASE)...")

    try:
        with Postgres.with_config(ConfigFileLoader(config_path, 'quickbooks')) as loader_qb:
            query_pp = """
                SELECT
                    familia,
                    categoria_pp,
                    source_file,
                    source_sheet,
                    load_ts,
                    row_hash
                FROM quickbooks.stg_produccion_categorias_pp_raw
            """
            df_pp = loader_qb.load(query_pp)

        df_pp['fuente'] = 'quickbooks'
        df_pp['nombre_tabla_origen'] = 'quickbooks.stg_produccion_categorias_pp_raw'
        df_pp['pipeline_id'] = pipeline_id
        df_pp['batch_id'] = batch_id
        df_pp['fecha_ingesta'] = datetime.now()

        dfs['quickbooks.stg_produccion_categorias_pp_raw'] = df_pp
        print(f"    Registros extraidos: {len(df_pp)}")
    except Exception as e:
        print(f"    [ERROR] No se pudo extraer staging categorias PP desde Supabase: {e}")

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
        'quickbooks.produccion',
        'quickbooks.stg_catalogo_ean_raw',
        'quickbooks.stg_ventas_econespecias_raw',
        'quickbooks.stg_produccion_categorias_pp_raw',
    ]
    if require_kronos:
        required_tables.append('kronos.ventas_detalle')
    missing_required = [t for t in required_tables if t not in dfs]
    if missing_required:
        raise RuntimeError(
            'Extraccion incompleta en Bronze. Tablas criticas faltantes: '
            + ', '.join(missing_required)
        )

    if 'kronos.ventas_detalle' not in dfs:
        print('[WARN] Kronos no disponible. Se continua con QuickBooks para flujo PP/PT.')

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
