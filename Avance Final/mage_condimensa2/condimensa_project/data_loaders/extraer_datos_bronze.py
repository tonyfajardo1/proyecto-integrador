"""
Data Loader: Extraer datos de Kronos y QuickBooks hacia Bronze
Pipeline: etl_bronze
Extraccion cruda y trazable desde las 6 tablas fuente vigentes.
"""
from datetime import datetime
from os import path
import os
import uuid

import pandas as pd
from mage_ai.io.config import ConfigFileLoader
from mage_ai.io.postgres import Postgres
from mage_ai.settings.repo import get_repo_path

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


def _add_metadata(df: pd.DataFrame, fuente: str, origen: str, pipeline_id: str, batch_id: str) -> pd.DataFrame:
    out = df.copy()
    out['fuente'] = fuente
    out['nombre_tabla_origen'] = origen
    out['pipeline_id'] = pipeline_id
    out['batch_id'] = batch_id
    out['fecha_ingesta'] = datetime.now()
    return out


def _table_has_column(loader, schema_name: str, table_name: str, column_name: str) -> bool:
    query = f"""
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = '{schema_name}'
              AND table_name = '{table_name}'
              AND column_name = '{column_name}'
        ) AS has_column
    """
    df = loader.load(query)
    if df.empty:
        return False

    value = df.iloc[0]['has_column']
    if pd.isna(value):
        return False
    if isinstance(value, str):
        return value.strip().lower() in {'true', 't', '1', 'yes', 'y'}
    return bool(value)


@data_loader
def extraer_kronos_bronze(*args, **kwargs):
    """
    Extrae las fuentes operacionales vigentes hacia Bronze.

    Fuentes actuales:
    - Kronos: raw_kronos_ventas, raw_kronos_rentabilidad
    - QuickBooks: raw_produccion, sales, raw_catalogo, raw_ventas
    """

    start_ts = datetime.now()
    batch_id = str(uuid.uuid4())
    pipeline_id = kwargs.get('pipeline_id', 'etl_bronze')
    require_kronos = bool(kwargs.get('require_kronos', False))

    print(f"\n{'=' * 70}")
    print("EXTRACCION - FUENTES A BRONZE")
    print(f"{'=' * 70}")
    print(f"Batch ID: {batch_id}")
    print(f"Pipeline ID: {pipeline_id}")
    print(f"{'=' * 70}\n")

    config_path = path.join(get_repo_path(), 'io_config.yaml')
    dfs = {}

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
            + '. Actualiza mage_condimensa2/.env y reinicia contenedores.'
        )
    if missing_kronos:
        print(
            '[WARN] Variables faltantes para Kronos: '
            + ', '.join(missing_kronos)
            + '. Si la conexion Kronos falla, revisa el .env y reinicia contenedores.'
        )

    kronos_loaded = set()

    print('[1] EXTRAYENDO KRONOS DESDE public.raw_kronos_ventas...')
    try:
        with Postgres.with_config(ConfigFileLoader(config_path, 'kronos')) as loader:
            use_json_contract = _table_has_column(
                loader,
                'public',
                'raw_kronos_ventas',
                'data',
            )
            if use_json_contract:
                query = """
                    WITH mapped AS (
                        SELECT
                            NULLIF(BTRIM(data->>'FECHA DE FACTURA'), '') AS fecha_factura,
                            NULLIF(BTRIM(data->>'ZONAS'), '') AS zonas,
                            NULLIF(BTRIM(COALESCE(data->>'marca', data->>'MARCA')), '') AS marca,
                            NULLIF(BTRIM(data->>'NOMBRE_PRODUCTO'), '') AS nombre_producto,
                            NULLIF(BTRIM(data->>'Venta Neta'), '') AS venta_neta,
                            NULLIF(BTRIM(data->>'CANTIDAD'), '') AS cantidad,
                            'raw_kronos_ventas'::text AS source_file,
                            extracted_at
                        FROM public.raw_kronos_ventas
                        WHERE NULLIF(BTRIM(data->>'NOMBRE_PRODUCTO'), '') IS NOT NULL
                    ),
                    latest AS (
                        SELECT DISTINCT ON (
                            fecha_factura,
                            zonas,
                            marca,
                            nombre_producto,
                            venta_neta,
                            cantidad
                        )
                            fecha_factura,
                            zonas,
                            marca,
                            nombre_producto,
                            venta_neta,
                            cantidad,
                            source_file,
                            extracted_at
                        FROM mapped
                        ORDER BY
                            fecha_factura,
                            zonas,
                            marca,
                            nombre_producto,
                            venta_neta,
                            cantidad,
                            extracted_at DESC
                    )
                    SELECT *
                    FROM latest
                """
            else:
                query = """
                    WITH latest AS (
                        SELECT DISTINCT ON (
                            "FECHA DE FACTURA",
                            "ZONAS",
                            "marca",
                            "NOMBRE_PRODUCTO",
                            "Venta Neta",
                            "CANTIDAD"
                        )
                            "FECHA DE FACTURA" AS fecha_factura,
                            "ZONAS" AS zonas,
                            "marca" AS marca,
                            "NOMBRE_PRODUCTO" AS nombre_producto,
                            "Venta Neta" AS venta_neta,
                            "CANTIDAD" AS cantidad,
                            source_file,
                            extracted_at
                        FROM public.raw_kronos_ventas
                        ORDER BY
                            "FECHA DE FACTURA",
                            "ZONAS",
                            "marca",
                            "NOMBRE_PRODUCTO",
                            "Venta Neta",
                            "CANTIDAD",
                            extracted_at DESC
                    )
                    SELECT *
                    FROM latest
                """
            df = loader.load(query)
        dfs['kronos.ventas'] = _add_metadata(
            df,
            'kronos',
            'raw_kronos_ventas',
            pipeline_id,
            batch_id,
        )
        kronos_loaded.add('kronos.ventas')
        print(f"    Registros extraidos: {len(df)}")
    except Exception as exc:
        print(f"    [WARN] No se pudo extraer raw_kronos_ventas: {exc}")

    print('[2] EXTRAYENDO KRONOS DESDE public.raw_kronos_rentabilidad...')
    try:
        with Postgres.with_config(ConfigFileLoader(config_path, 'kronos')) as loader:
            use_json_contract = _table_has_column(
                loader,
                'public',
                'raw_kronos_rentabilidad',
                'data',
            )
            if use_json_contract:
                query = """
                    WITH mapped AS (
                        SELECT
                            NULLIF(BTRIM(data->>'FECHA DE FACTURA'), '') AS fecha_factura,
                            NULLIF(BTRIM(data->>'ZONAS'), '') AS zonas,
                            NULLIF(BTRIM(data->>'MARCA_PRODUCTO'), '') AS marca_producto,
                            NULLIF(BTRIM(data->>'NOMBRE_PRODUCTO'), '') AS nombre_producto,
                            NULLIF(BTRIM(data->>'Venta neta'), '') AS venta_neta,
                            NULLIF(BTRIM(data->>'Costo'), '') AS costo,
                            NULLIF(BTRIM(data->>'Rentabilidad'), '') AS rentabilidad,
                            'raw_kronos_rentabilidad'::text AS source_file,
                            extracted_at
                        FROM public.raw_kronos_rentabilidad
                        WHERE NULLIF(BTRIM(data->>'NOMBRE_PRODUCTO'), '') IS NOT NULL
                    ),
                    latest AS (
                        SELECT DISTINCT ON (
                            fecha_factura,
                            zonas,
                            marca_producto,
                            nombre_producto,
                            venta_neta,
                            costo,
                            rentabilidad
                        )
                            fecha_factura,
                            zonas,
                            marca_producto,
                            nombre_producto,
                            venta_neta,
                            costo,
                            rentabilidad,
                            source_file,
                            extracted_at
                        FROM mapped
                        ORDER BY
                            fecha_factura,
                            zonas,
                            marca_producto,
                            nombre_producto,
                            venta_neta,
                            costo,
                            rentabilidad,
                            extracted_at DESC
                    )
                    SELECT *
                    FROM latest
                """
            else:
                query = """
                    WITH latest AS (
                        SELECT DISTINCT ON (
                            "FECHA DE FACTURA",
                            "ZONAS",
                            "MARCA_PRODUCTO",
                            "NOMBRE_PRODUCTO",
                            "Venta neta",
                            "Costo",
                            "Rentabilidad"
                        )
                            "FECHA DE FACTURA" AS fecha_factura,
                            "ZONAS" AS zonas,
                            "MARCA_PRODUCTO" AS marca_producto,
                            "NOMBRE_PRODUCTO" AS nombre_producto,
                            "Venta neta" AS venta_neta,
                            "Costo" AS costo,
                            "Rentabilidad" AS rentabilidad,
                            source_file,
                            extracted_at
                        FROM public.raw_kronos_rentabilidad
                        ORDER BY
                            "FECHA DE FACTURA",
                            "ZONAS",
                            "MARCA_PRODUCTO",
                            "NOMBRE_PRODUCTO",
                            "Venta neta",
                            "Costo",
                            "Rentabilidad",
                            extracted_at DESC
                    )
                    SELECT *
                    FROM latest
                """
            df = loader.load(query)
        dfs['kronos.rentabilidad'] = _add_metadata(
            df,
            'kronos',
            'raw_kronos_rentabilidad',
            pipeline_id,
            batch_id,
        )
        kronos_loaded.add('kronos.rentabilidad')
        print(f"    Registros extraidos: {len(df)}")
    except Exception as exc:
        print(f"    [WARN] No se pudo extraer raw_kronos_rentabilidad: {exc}")

    print('\n[3] EXTRAYENDO QUICKBOOKS DESDE public.raw_produccion...')
    try:
        with Postgres.with_config(ConfigFileLoader(config_path, 'quickbooks')) as loader:
            query = """
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
            df = loader.load(query)
        dfs['quickbooks.produccion'] = _add_metadata(
            df,
            'quickbooks',
            'raw_produccion',
            pipeline_id,
            batch_id,
        )
        print(f"    Registros extraidos: {len(df)}")
    except Exception as exc:
        print(f"    [ERROR] No se pudo extraer raw_produccion: {exc}")

    print('\n[4] EXTRAYENDO QUICKBOOKS DESDE sales...')
    try:
        with Postgres.with_config(ConfigFileLoader(config_path, 'quickbooks')) as loader:
            df = loader.load("SELECT * FROM quickbooks.sales")
        dfs['quickbooks.sales'] = _add_metadata(
            df,
            'quickbooks',
            'sales',
            pipeline_id,
            batch_id,
        )
        print(f"    Registros extraidos: {len(df)}")
    except Exception as exc:
        print(f"    [ERROR] No se pudo extraer sales: {exc}")

    print('\n[5] EXTRAYENDO QUICKBOOKS DESDE public.raw_catalogo...')
    try:
        with Postgres.with_config(ConfigFileLoader(config_path, 'quickbooks')) as loader:
            query = """
                SELECT
                    NULLIF(BTRIM(data->>'ean_13_ean_14[Item]'), '') AS item,
                    NULLIF(BTRIM(data->>'ean_13_ean_14[Description]'), '') AS description,
                    NULLIF(BTRIM(data->>'ean_13_ean_14[U/M]'), '') AS um,
                    NULLIF(BTRIM(data->>'ean_13_ean_14[Price]'), '')::numeric AS price,
                    NULLIF(BTRIM(data->>'ean_13_ean_14[EAN13]'), '') AS ean13,
                    NULLIF(BTRIM(data->>'ean_13_ean_14[EAN14]'), '') AS ean14,
                    source_file,
                    source_sheet,
                    load_ts,
                    row_hash
                FROM (
                    SELECT
                        data,
                        'raw_catalogo'::text AS source_file,
                        'jsonb.data'::text AS source_sheet,
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
                ) src
                WHERE NULLIF(BTRIM(data->>'ean_13_ean_14[Item]'), '') IS NOT NULL
            """
            df = loader.load(query)
        dfs['quickbooks.catalogo_ean'] = _add_metadata(
            df,
            'quickbooks',
            'raw_catalogo',
            pipeline_id,
            batch_id,
        )
        print(f"    Registros extraidos: {len(df)}")
    except Exception as exc:
        print(f"    [ERROR] No se pudo extraer raw_catalogo: {exc}")

    print('\n[6] EXTRAYENDO QUICKBOOKS DESDE public.raw_ventas...')
    try:
        with Postgres.with_config(ConfigFileLoader(config_path, 'quickbooks')) as loader:
            query = """
                WITH mapped AS (
                    SELECT
                        NULLIF(BTRIM(data->>'Ventas Econespecias[Marca]'), '') AS marca,
                        NULLIF(BTRIM(data->>'Ventas Econespecias[Familia]'), '') AS familia,
                        NULLIF(BTRIM(data->>'Ventas Econespecias[Producto]'), '') AS producto,
                        NULLIF(BTRIM(data->>'Ventas Econespecias[Recuento de Cliente]'), '')::integer AS recuento_cliente,
                        NULLIF(BTRIM(data->>'Ventas Econespecias[Cantidad]'), '')::numeric AS cantidad,
                        NULLIF(BTRIM(data->>'Ventas Econespecias[Ventas]'), '')::numeric AS ventas,
                        CASE
                            WHEN BTRIM(COALESCE(
                                data->>U&'Ventas Econespecias[A\\00F1o]',
                                data->>U&'Ventas Econespecias[A\\00C3\\00B1o]',
                                ''
                            )) ~ '^\d{4}$'
                            THEN BTRIM(COALESCE(
                                data->>U&'Ventas Econespecias[A\\00F1o]',
                                data->>U&'Ventas Econespecias[A\\00C3\\00B1o]',
                                ''
                            ))::integer
                            ELSE NULL
                        END AS anio,
                        LOWER(NULLIF(BTRIM(data->>'Ventas Econespecias[Mes]'), '')) AS mes,
                        'raw_ventas'::text AS source_file,
                        'jsonb.data'::text AS source_sheet,
                        extracted_at AS load_ts,
                        md5(CONCAT_WS(
                            '|',
                            COALESCE(data->>'Ventas Econespecias[Marca]', ''),
                            COALESCE(data->>'Ventas Econespecias[Familia]', ''),
                            COALESCE(data->>'Ventas Econespecias[Producto]', ''),
                            COALESCE(data->>'Ventas Econespecias[Recuento de Cliente]', ''),
                            COALESCE(data->>'Ventas Econespecias[Cantidad]', ''),
                            COALESCE(data->>'Ventas Econespecias[Ventas]', ''),
                            COALESCE(
                                data->>U&'Ventas Econespecias[A\\00F1o]',
                                data->>U&'Ventas Econespecias[A\\00C3\\00B1o]',
                                ''
                            ),
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
            df = loader.load(query)
            missing_years = int(df['anio'].isna().sum()) if 'anio' in df.columns else len(df)
            missing_periods = int(df['periodo'].isna().sum()) if 'periodo' in df.columns else len(df)
            if missing_years or missing_periods:
                raise RuntimeError(
                    'raw_ventas contiene filas sin anio/periodo valido despues de extraer: '
                    f'anio_null={missing_years}, periodo_null={missing_periods}. '
                    'Revisar llave JSON Ventas Econespecias[Año] y nombres de mes.'
                )
            marcas = sorted(df['marca'].dropna().astype(str).unique().tolist())
            anio_min = int(df['anio'].min()) if len(df) else None
            anio_max = int(df['anio'].max()) if len(df) else None
            print(f"    Cobertura raw_ventas: anios={anio_min}-{anio_max}, marcas={marcas}")
        dfs['quickbooks.ventas_econespecias'] = _add_metadata(
            df,
            'quickbooks',
            'raw_ventas',
            pipeline_id,
            batch_id,
        )
        print(f"    Registros extraidos: {len(df)}")
    except Exception as exc:
        print(f"    [ERROR] No se pudo extraer raw_ventas: {exc}")

    print(f"\n{'=' * 70}")
    print("RESUMEN DE EXTRACCION")
    print(f"{'=' * 70}")
    for tabla, df in dfs.items():
        print(f"  {tabla}: {len(df)} registros")
    print(f"{'=' * 70}")
    print(f"Total tablas: {len(dfs)}")
    print(f"Total registros: {sum(len(df) for df in dfs.values())}")
    print(f"{'=' * 70}\n")

    required_tables = [
        'quickbooks.produccion',
        'quickbooks.sales',
        'quickbooks.catalogo_ean',
        'quickbooks.ventas_econespecias',
    ]
    missing_required = [t for t in required_tables if t not in dfs]
    if missing_required:
        raise RuntimeError(
            'Extraccion incompleta en Bronze. Tablas QuickBooks faltantes: '
            + ', '.join(missing_required)
        )

    if require_kronos:
        kronos_required = ['kronos.ventas', 'kronos.rentabilidad']
        missing_kronos_tables = [t for t in kronos_required if t not in dfs]
        if missing_kronos_tables:
            raise RuntimeError(
                'Extraccion incompleta en Bronze. Tablas Kronos faltantes: '
                + ', '.join(missing_kronos_tables)
            )

    return {
        'dfs': dfs,
        'batch_id': batch_id,
        'pipeline_id': pipeline_id,
        'metadata': {
            'tablas': list(dfs.keys()),
            'fecha_inicio': start_ts.isoformat(),
            'fecha_fin': datetime.now().isoformat(),
            'registros': sum(len(df) for df in dfs.values()),
        },
    }


@test
def test_output(output, *args) -> None:
    assert output is not None, 'No se extrajeron datos'
    assert 'dfs' in output, 'Falta diccionario de dataframes'
    assert len(output['dfs']) > 0, 'No hay tablas extraidas'
    print(f"OK: Extraccion completada - {output['metadata']['registros']} registros")
