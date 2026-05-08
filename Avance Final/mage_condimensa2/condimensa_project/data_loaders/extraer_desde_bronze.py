"""
Data Loader: Extraer datos desde Bronze hacia Silver
Pipeline: etl_silver
Lee tablas raw de Bronze y prepara datasets derivados en memoria.
"""
from os import path
import re
import uuid
import unicodedata

import numpy as np
import pandas as pd
from mage_ai.io.config import ConfigFileLoader
from mage_ai.io.postgres import Postgres
from mage_ai.settings.repo import get_repo_path

if 'data_loader' not in dir():
    from mage_ai.data_preparation.decorators import data_loader
if 'test' not in dir():
    from mage_ai.data_preparation.decorators import test


SUMMARY_COLUMNS = [
    'centro_costo',
    'codigo_producto',
    'codigo_alterno',
    'producto',
    'mes',
    'anio',
    'cant_venta',
    'total_venta',
    'cant_nc',
    'total_nc',
    'cant_devolucion',
    'total_devolucion',
    'cant_neto',
    'total_neto',
    'costo_venta',
    'rentabilidad',
    'prc_rentabilidad',
]

EXEC_SUMMARY_COLUMNS = [
    'centro_costo',
    'mes',
    'anio',
    'cant_venta',
    'total_venta',
    'cant_devolucion',
    'total_devolucion',
    'cant_neto',
    'total_neto',
    'costo_venta',
    'rentabilidad',
    'prc_rentabilidad',
]

MONTH_NAMES_ES = {
    1: 'ENERO',
    2: 'FEBRERO',
    3: 'MARZO',
    4: 'ABRIL',
    5: 'MAYO',
    6: 'JUNIO',
    7: 'JULIO',
    8: 'AGOSTO',
    9: 'SEPTIEMBRE',
    10: 'OCTUBRE',
    11: 'NOVIEMBRE',
    12: 'DICIEMBRE',
}


def _parse_kronos_number(value):
    if pd.isna(value):
        return np.nan
    if isinstance(value, (int, float, np.number)):
        return float(value)

    text = str(value).strip()
    if not text:
        return np.nan

    text_upper = text.upper()
    if text_upper in {'NULL', 'NONE', 'NAN'}:
        return np.nan

    negative = text.startswith('(') and text.endswith(')')
    text = text.replace('(', '').replace(')', '')
    text = text.replace('$', '').replace('%', '').replace(' ', '')
    text = text.replace('−', '-').replace('\u00a0', '')

    has_dot = '.' in text
    has_comma = ',' in text

    if 'E' in text.upper():
        text = text.replace(',', '.')
    elif has_dot and has_comma:
        # Usa el ultimo separador como decimal y trata el otro como miles.
        if text.rfind(',') > text.rfind('.'):
            text = text.replace('.', '').replace(',', '.')
        else:
            text = text.replace(',', '')
    elif has_comma:
        if text.count(',') > 1:
            parts = text.split(',')
            if all(len(part) == 3 for part in parts[1:]):
                text = ''.join(parts)
            else:
                text = ''.join(parts[:-1]) + '.' + parts[-1]
        else:
            text = text.replace(',', '.')
    elif has_dot and text.count('.') > 1:
        parts = text.split('.')
        if all(len(part) == 3 for part in parts[1:]):
            text = ''.join(parts)
        else:
            text = ''.join(parts[:-1]) + '.' + parts[-1]

    try:
        number = float(text)
    except Exception:
        return np.nan
    return -number if negative else number


def _normalize_text(series, uppercase=False):
    result = series.fillna('').astype(str).str.strip()
    return result.str.upper() if uppercase else result


def _normalize_zone_text(series):
    normalized = _normalize_text(series, uppercase=True)
    normalized = normalized.apply(
        lambda value: ''.join(
            ch for ch in unicodedata.normalize('NFKD', value)
            if not unicodedata.combining(ch)
        )
    )
    return normalized.str.replace(r'\s+', ' ', regex=True).str.strip()


def _is_excluded_kronos_zone(series):
    normalized = _normalize_zone_text(series)
    return normalized.str.contains(r'SIN ASIGNAR|FALTA ASIGNAR', regex=True, na=False)


def _extract_product_code(value):
    text = '' if value is None else str(value).strip()
    if not text:
        return ''
    paren_codes = re.findall(r'\((\d{3,6})\)', text)
    if paren_codes:
        return paren_codes[-1]
    codes = re.findall(r'(?<!\d)(\d{3,6})(?!\d)', text)
    return codes[-1] if codes else ''


def _build_kronos_resumen(df_ventas, df_rentabilidad):
    if len(df_ventas) == 0 and len(df_rentabilidad) == 0:
        return pd.DataFrame(columns=SUMMARY_COLUMNS)

    base_keys = ['centro_costo', 'codigo_producto', 'codigo_alterno', 'producto', 'mes', 'anio']

    ventas = df_ventas.copy()
    if len(ventas) > 0:
        ventas['fecha_factura'] = pd.to_datetime(ventas.get('fecha_factura'), errors='coerce')
        ventas['centro_costo'] = _normalize_text(ventas.get('zonas', pd.Series(dtype=str)), uppercase=True)
        ventas['producto'] = _normalize_text(ventas.get('nombre_producto', pd.Series(dtype=str)))
        ventas['codigo_producto'] = ventas['producto'].map(_extract_product_code)
        ventas['codigo_alterno'] = ventas['codigo_producto']
        ventas['mes'] = ventas['fecha_factura'].dt.month.map(MONTH_NAMES_ES).fillna('')
        ventas['anio'] = pd.to_numeric(ventas['fecha_factura'].dt.year, errors='coerce').fillna(0).astype(int)
        ventas['venta_neta_num'] = ventas.get('venta_neta', pd.Series(dtype=object)).apply(_parse_kronos_number).fillna(0.0)
        ventas['cantidad_num'] = ventas.get('cantidad', pd.Series(dtype=object)).apply(_parse_kronos_number).fillna(0.0)
        ventas = ventas[
            ventas['fecha_factura'].notna()
            & ventas['centro_costo'].ne('')
            & ventas['producto'].ne('')
            & ventas['mes'].ne('')
        ].copy()
        excluded_ventas = _is_excluded_kronos_zone(ventas['centro_costo'])
        if excluded_ventas.any():
            print(
                f"Filtrando {int(excluded_ventas.sum())} filas de kronos_ventas_raw "
                "con zona sin asignar/falta asignar."
            )
            ventas = ventas.loc[~excluded_ventas].copy()

        is_negative = (ventas['venta_neta_num'] < 0) | (ventas['cantidad_num'] < 0)
        ventas['cant_venta'] = np.where(is_negative, 0.0, ventas['cantidad_num'].abs())
        ventas['total_venta'] = np.where(is_negative, 0.0, ventas['venta_neta_num'].abs())
        ventas['cant_devolucion'] = np.where(is_negative, ventas['cantidad_num'].abs(), 0.0)
        ventas['total_devolucion'] = np.where(is_negative, ventas['venta_neta_num'].abs(), 0.0)

        ventas_summary = (
            ventas.groupby(base_keys, as_index=False)
            .agg(
                cant_venta=('cant_venta', 'sum'),
                total_venta=('total_venta', 'sum'),
                cant_devolucion=('cant_devolucion', 'sum'),
                total_devolucion=('total_devolucion', 'sum'),
            )
        )
    else:
        ventas_summary = pd.DataFrame(columns=base_keys + ['cant_venta', 'total_venta', 'cant_devolucion', 'total_devolucion'])

    renta = df_rentabilidad.copy()
    if len(renta) > 0:
        renta['fecha_factura'] = pd.to_datetime(renta.get('fecha_factura'), errors='coerce')
        renta['centro_costo'] = _normalize_text(renta.get('zonas', pd.Series(dtype=str)), uppercase=True)
        renta['producto'] = _normalize_text(renta.get('nombre_producto', pd.Series(dtype=str)))
        renta['codigo_producto'] = renta['producto'].map(_extract_product_code)
        renta['codigo_alterno'] = renta['codigo_producto']
        renta['mes'] = renta['fecha_factura'].dt.month.map(MONTH_NAMES_ES).fillna('')
        renta['anio'] = pd.to_numeric(renta['fecha_factura'].dt.year, errors='coerce').fillna(0).astype(int)
        renta['venta_neta_num'] = renta.get('venta_neta', pd.Series(dtype=object)).apply(_parse_kronos_number).fillna(0.0)
        renta['costo_num'] = renta.get('costo', pd.Series(dtype=object)).apply(_parse_kronos_number).fillna(0.0)
        renta['rentabilidad_num'] = renta.get('rentabilidad', pd.Series(dtype=object)).apply(_parse_kronos_number).fillna(0.0)
        renta = renta[
            renta['fecha_factura'].notna()
            & renta['centro_costo'].ne('')
            & renta['producto'].ne('')
            & renta['mes'].ne('')
        ].copy()
        excluded_renta = _is_excluded_kronos_zone(renta['centro_costo'])
        if excluded_renta.any():
            print(
                f"Filtrando {int(excluded_renta.sum())} filas de kronos_rentabilidad_raw "
                "con zona sin asignar/falta asignar."
            )
            renta = renta.loc[~excluded_renta].copy()

        is_negative_margin = renta['venta_neta_num'] < 0
        renta['total_venta_margin'] = np.where(is_negative_margin, 0.0, renta['venta_neta_num'].abs())
        renta['total_devolucion_margin'] = np.where(is_negative_margin, renta['venta_neta_num'].abs(), 0.0)
        renta['costo_venta'] = renta['costo_num'].abs()

        renta_summary = (
            renta.groupby(base_keys, as_index=False)
            .agg(
                total_venta_margin=('total_venta_margin', 'sum'),
                total_devolucion_margin=('total_devolucion_margin', 'sum'),
                costo_venta=('costo_venta', 'sum'),
                rentabilidad=('rentabilidad_num', 'sum'),
            )
        )
    else:
        renta_summary = pd.DataFrame(columns=base_keys + ['total_venta_margin', 'total_devolucion_margin', 'costo_venta', 'rentabilidad'])

    resumen = ventas_summary.merge(renta_summary, on=base_keys, how='outer')
    for column in [
        'cant_venta',
        'total_venta',
        'cant_devolucion',
        'total_devolucion',
        'total_venta_margin',
        'total_devolucion_margin',
        'costo_venta',
        'rentabilidad',
    ]:
        if column not in resumen.columns:
            resumen[column] = 0.0
        resumen[column] = pd.to_numeric(resumen[column], errors='coerce').fillna(0.0)

    resumen['total_venta'] = np.where(
        resumen['total_venta'] > 0,
        resumen['total_venta'],
        resumen['total_venta_margin'],
    )
    resumen['total_devolucion'] = np.where(
        resumen['total_devolucion'] > 0,
        resumen['total_devolucion'],
        resumen['total_devolucion_margin'],
    )
    resumen['cant_nc'] = 0.0
    resumen['total_nc'] = 0.0
    resumen['cant_neto'] = (resumen['cant_venta'] - resumen['cant_devolucion']).clip(lower=0.0)
    resumen['total_neto'] = resumen['total_venta'] - resumen['total_devolucion']
    resumen['prc_rentabilidad'] = np.where(
        resumen['total_neto'].abs() > 1e-9,
        (resumen['rentabilidad'] / resumen['total_neto']) * 100.0,
        0.0,
    )
    resumen['prc_rentabilidad'] = pd.to_numeric(
        resumen['prc_rentabilidad'],
        errors='coerce',
    ).fillna(0.0).clip(-9999, 9999)

    for column in base_keys:
        if column not in resumen.columns:
            resumen[column] = ''

    resumen['centro_costo'] = _normalize_text(resumen['centro_costo'], uppercase=True)
    resumen['codigo_producto'] = _normalize_text(resumen['codigo_producto'])
    resumen['codigo_alterno'] = _normalize_text(resumen['codigo_alterno'])
    resumen['producto'] = _normalize_text(resumen['producto'])
    resumen['mes'] = _normalize_text(resumen['mes'], uppercase=True)
    resumen['anio'] = pd.to_numeric(resumen['anio'], errors='coerce').fillna(0).astype(int)

    resumen = resumen[
        resumen['centro_costo'].ne('')
        & resumen['producto'].ne('')
        & resumen['mes'].ne('')
        & resumen['anio'].gt(0)
    ].copy()

    return resumen[SUMMARY_COLUMNS].copy()


def _build_kronos_resumen_ejecutivo(df_ventas, df_rentabilidad):
    if len(df_ventas) == 0 and len(df_rentabilidad) == 0:
        return pd.DataFrame(columns=EXEC_SUMMARY_COLUMNS)

    base_keys = ['centro_costo', 'mes', 'anio']

    ventas = df_ventas.copy()
    if len(ventas) > 0:
        ventas['fecha_factura'] = pd.to_datetime(ventas.get('fecha_factura'), errors='coerce')
        ventas['centro_costo'] = _normalize_text(ventas.get('zonas', pd.Series(dtype=str)), uppercase=True)
        ventas['mes'] = ventas['fecha_factura'].dt.month.map(MONTH_NAMES_ES).fillna('')
        ventas['anio'] = pd.to_numeric(ventas['fecha_factura'].dt.year, errors='coerce').fillna(0).astype(int)
        ventas['venta_neta_num'] = ventas.get('venta_neta', pd.Series(dtype=object)).apply(_parse_kronos_number).fillna(0.0)
        ventas['cantidad_num'] = ventas.get('cantidad', pd.Series(dtype=object)).apply(_parse_kronos_number).fillna(0.0)
        ventas = ventas[
            ventas['fecha_factura'].notna()
            & ventas['centro_costo'].ne('')
            & ventas['mes'].ne('')
        ].copy()
        excluded_ventas = _is_excluded_kronos_zone(ventas['centro_costo'])
        if excluded_ventas.any():
            print(
                f"Filtrando {int(excluded_ventas.sum())} filas de kronos_ventas_raw "
                "del resumen ejecutivo por zona sin asignar/falta asignar."
            )
            ventas = ventas.loc[~excluded_ventas].copy()

        is_negative = (ventas['venta_neta_num'] < 0) | (ventas['cantidad_num'] < 0)
        ventas['cant_venta'] = np.where(is_negative, 0.0, ventas['cantidad_num'].abs())
        ventas['total_venta'] = np.where(is_negative, 0.0, ventas['venta_neta_num'].abs())
        ventas['cant_devolucion'] = np.where(is_negative, ventas['cantidad_num'].abs(), 0.0)
        ventas['total_devolucion'] = np.where(is_negative, ventas['venta_neta_num'].abs(), 0.0)

        ventas_summary = (
            ventas.groupby(base_keys, as_index=False)
            .agg(
                cant_venta=('cant_venta', 'sum'),
                total_venta=('total_venta', 'sum'),
                cant_devolucion=('cant_devolucion', 'sum'),
                total_devolucion=('total_devolucion', 'sum'),
            )
        )
    else:
        ventas_summary = pd.DataFrame(
            columns=base_keys + ['cant_venta', 'total_venta', 'cant_devolucion', 'total_devolucion']
        )

    renta = df_rentabilidad.copy()
    if len(renta) > 0:
        renta['fecha_factura'] = pd.to_datetime(renta.get('fecha_factura'), errors='coerce')
        renta['centro_costo'] = _normalize_text(renta.get('zonas', pd.Series(dtype=str)), uppercase=True)
        renta['mes'] = renta['fecha_factura'].dt.month.map(MONTH_NAMES_ES).fillna('')
        renta['anio'] = pd.to_numeric(renta['fecha_factura'].dt.year, errors='coerce').fillna(0).astype(int)
        renta['venta_neta_num'] = renta.get('venta_neta', pd.Series(dtype=object)).apply(_parse_kronos_number).fillna(0.0)
        renta['costo_num'] = renta.get('costo', pd.Series(dtype=object)).apply(_parse_kronos_number).fillna(0.0)
        renta['rentabilidad_num'] = renta.get('rentabilidad', pd.Series(dtype=object)).apply(_parse_kronos_number).fillna(0.0)
        renta = renta[
            renta['fecha_factura'].notna()
            & renta['centro_costo'].ne('')
            & renta['mes'].ne('')
        ].copy()
        excluded_renta = _is_excluded_kronos_zone(renta['centro_costo'])
        if excluded_renta.any():
            print(
                f"Filtrando {int(excluded_renta.sum())} filas de kronos_rentabilidad_raw "
                "del resumen ejecutivo por zona sin asignar/falta asignar."
            )
            renta = renta.loc[~excluded_renta].copy()

        is_negative_margin = renta['venta_neta_num'] < 0
        renta['costo_venta'] = renta['costo_num'].abs()
        renta['rentabilidad'] = renta['rentabilidad_num']
        renta['total_venta_margin'] = np.where(is_negative_margin, 0.0, renta['venta_neta_num'].abs())
        renta['total_devolucion_margin'] = np.where(is_negative_margin, renta['venta_neta_num'].abs(), 0.0)

        renta_summary = (
            renta.groupby(base_keys, as_index=False)
            .agg(
                total_venta_margin=('total_venta_margin', 'sum'),
                total_devolucion_margin=('total_devolucion_margin', 'sum'),
                costo_venta=('costo_venta', 'sum'),
                rentabilidad=('rentabilidad', 'sum'),
            )
        )
    else:
        renta_summary = pd.DataFrame(
            columns=base_keys + ['total_venta_margin', 'total_devolucion_margin', 'costo_venta', 'rentabilidad']
        )

    resumen = ventas_summary.merge(renta_summary, on=base_keys, how='outer')
    for column in [
        'cant_venta',
        'total_venta',
        'cant_devolucion',
        'total_devolucion',
        'total_venta_margin',
        'total_devolucion_margin',
        'costo_venta',
        'rentabilidad',
    ]:
        if column not in resumen.columns:
            resumen[column] = 0.0
        resumen[column] = pd.to_numeric(resumen[column], errors='coerce').fillna(0.0)

    resumen['total_venta'] = np.where(
        resumen['total_venta'] > 0,
        resumen['total_venta'],
        resumen['total_venta_margin'],
    )
    resumen['total_devolucion'] = np.where(
        resumen['total_devolucion'] > 0,
        resumen['total_devolucion'],
        resumen['total_devolucion_margin'],
    )
    resumen['cant_neto'] = (resumen['cant_venta'] - resumen['cant_devolucion']).clip(lower=0.0)
    resumen['total_neto'] = resumen['total_venta'] - resumen['total_devolucion']
    resumen['prc_rentabilidad'] = np.where(
        resumen['total_neto'].abs() > 1e-9,
        (resumen['rentabilidad'] / resumen['total_neto']) * 100.0,
        0.0,
    )
    resumen['prc_rentabilidad'] = pd.to_numeric(
        resumen['prc_rentabilidad'],
        errors='coerce',
    ).fillna(0.0).clip(-9999, 9999)

    for column in base_keys:
        if column not in resumen.columns:
            resumen[column] = ''

    resumen['centro_costo'] = _normalize_text(resumen['centro_costo'], uppercase=True)
    resumen['mes'] = _normalize_text(resumen['mes'], uppercase=True)
    resumen['anio'] = pd.to_numeric(resumen['anio'], errors='coerce').fillna(0).astype(int)

    resumen = resumen[
        resumen['centro_costo'].ne('')
        & resumen['mes'].ne('')
        & resumen['anio'].gt(0)
    ].copy()

    return resumen[EXEC_SUMMARY_COLUMNS].copy()


@data_loader
def extraer_desde_bronze(*args, **kwargs):
    """
    Extrae tablas raw desde Bronze y prepara datasets intermedios para Silver.

    Reglas de la capa:
    - Bronze solo lee raw fisico.
    - Resumenes y ayudas de modelado se derivan en memoria dentro de Silver.
    """

    batch_id = str(uuid.uuid4())
    pipeline_id = kwargs.get('pipeline_id', 'etl_silver')

    print(f"\n{'='*70}")
    print('EXTRACCION - DESDE BRONZE')
    print(f"{'='*70}")
    print(f'Batch ID: {batch_id}')
    print(f'Pipeline ID: {pipeline_id}')
    print(f"{'='*70}\n")

    config_path = path.join(get_repo_path(), 'io_config.yaml')
    config_profile = 'local_dwh'
    dfs = {}

    with Postgres.with_config(ConfigFileLoader(config_path, config_profile)) as loader:
        table_map = {
            'kronos_ventas_raw': 'SELECT * FROM bronze.kronos_ventas_raw',
            'kronos_rentabilidad_raw': 'SELECT * FROM bronze.kronos_rentabilidad_raw',
            'quickbooks_produccion_raw': 'SELECT * FROM bronze.quickbooks_produccion_raw',
            'quickbooks_ventas_raw': 'SELECT * FROM bronze.quickbooks_ventas_raw',
            'quickbooks_catalogo_ean_raw': 'SELECT * FROM bronze.quickbooks_catalogo_ean_raw',
            'quickbooks_ventas_econespecias_raw': 'SELECT * FROM bronze.quickbooks_ventas_econespecias_raw',
        }

        for key, query in table_map.items():
            print(f'Extrayendo bronze.{key}...')
            try:
                df = loader.load(query)
                dfs[key] = df
                print(f'    Registros: {len(df)}')
            except Exception as exc:
                print(f'    [WARN] No se pudo extraer {key}: {exc}')

    required_raw = [
        'kronos_ventas_raw',
        'kronos_rentabilidad_raw',
        'quickbooks_produccion_raw',
        'quickbooks_ventas_raw',
        'quickbooks_catalogo_ean_raw',
        'quickbooks_ventas_econespecias_raw',
    ]
    missing_required = [table for table in required_raw if table not in dfs]
    if missing_required:
        raise RuntimeError(
            'Extraccion Silver incompleta. Tablas Bronze faltantes: '
            + ', '.join(missing_required)
        )

    kronos_resumen = _build_kronos_resumen(
        dfs['kronos_ventas_raw'],
        dfs['kronos_rentabilidad_raw'],
    )
    dfs['kronos_ventas_resumen_raw'] = kronos_resumen
    print(f"kronos_ventas_resumen_raw derivada en memoria: {len(kronos_resumen)}")

    kronos_exec = _build_kronos_resumen_ejecutivo(
        dfs['kronos_ventas_raw'],
        dfs['kronos_rentabilidad_raw'],
    )
    dfs['kronos_resumen_ejecutivo_raw'] = kronos_exec
    print(f"kronos_resumen_ejecutivo_raw derivada en memoria: {len(kronos_exec)}")

    # Mantiene compatibilidad con la transformacion actual de Apriori sin volver
    # a consultar la fuente operacional.
    dfs['quickbooks_sales_local_raw'] = dfs['quickbooks_ventas_raw'].copy()

    print(f"\n[OK] Extraccion desde Bronze completada")
    print(f'Total tablas/dataframes: {len(dfs)}')
    print(f"Total registros: {sum(len(df) for df in dfs.values())}")

    return {
        'dfs': dfs,
        'batch_id': batch_id,
        'pipeline_id': pipeline_id,
        'metadata': {
            'tablas': list(dfs.keys()),
            'registros': sum(len(df) for df in dfs.values()),
        },
    }


@test
def test_output(output, *args) -> None:
    assert output is not None, 'No se extrajeron datos'
    assert 'dfs' in output, 'Falta diccionario de dataframes'
    assert len(output['dfs']) > 0, 'No hay tablas extraidas'
    print(f"OK: Extraccion completada - {output['metadata']['registros']} registros")
