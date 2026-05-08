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
import numpy as np

if 'data_exporter' not in dir():
    from mage_ai.data_preparation.decorators import data_exporter
if 'test' not in dir():
    from mage_ai.data_preparation.decorators import test


TABLE_LOADS = [
    ('kronos_ventas', 'kronos_ventas', 'kronos_ventas'),
    ('kronos_resumen_ejecutivo', 'kronos_resumen_ejecutivo', 'kronos_resumen_ejecutivo'),
    ('quickbooks_produccion', 'quickbooks_produccion', 'quickbooks_produccion'),
    ('apriori_transacciones', 'apriori_transacciones', 'apriori_transacciones'),
    ('catalogo_ean_clean', 'catalogo_ean_clean', 'catalogo_ean_clean'),
    ('ventas_econespecias_mensual_clean', 'ventas_econespecias_mensual_clean', 'ventas_econespecias_mensual_clean'),
    ('dim_producto_canonico', 'dim_producto_canonico', 'dim_producto_canonico'),
    ('forecasting_base_mensual_v1', 'forecasting_base_mensual_v1', 'forecasting_base_mensual_v1'),
    ('dim_producto_master', 'dim_producto_master', 'dim_producto_master'),
    ('product_name_mapping', 'product_name_mapping', 'product_name_mapping'),
    ('product_code_conflicts', 'product_code_conflicts', 'product_code_conflicts'),
    ('product_quality_metrics', 'product_quality_metrics', 'product_quality_metrics'),
    ('pp_pt_mapping_manual', 'pp_pt_mapping_manual', 'pp_pt_mapping_manual'),
    ('pp_universe_produccion_2025', 'pp_universe_produccion_2025', 'pp_universe_produccion_2025'),
    ('forecasting_base_pp_produccion_v1', 'forecasting_base_pp_produccion_v1', 'forecasting_base_pp_produccion_v1'),
    ('forecasting_base_mensual_integrada_v1', 'forecasting_base_mensual_integrada_v1', 'forecasting_base_mensual_integrada_v1'),
    ('forecasting_v3_catalogo_pt_limpio', 'forecasting_v3_catalogo_pt_limpio', 'forecasting_v3_catalogo_pt_limpio'),
    ('forecasting_v3_pt_catalog_match_report', 'forecasting_v3_pt_catalog_match_report', 'forecasting_v3_pt_catalog_match_report'),
    ('forecasting_v3_pt_productos_no_catalogo', 'forecasting_v3_pt_productos_no_catalogo', 'forecasting_v3_pt_productos_no_catalogo'),
    ('forecasting_v3_pt_mensual_model', 'forecasting_v3_pt_mensual_model', 'forecasting_v3_pt_mensual_model'),
    ('forecasting_v3_pt_productos_model', 'forecasting_v3_pt_productos_model', 'forecasting_v3_pt_productos_model'),
    ('forecasting_v3_pp_mensual_model', 'forecasting_v3_pp_mensual_model', 'forecasting_v3_pp_mensual_model'),
    ('forecasting_v3_pp_productos_model', 'forecasting_v3_pp_productos_model', 'forecasting_v3_pp_productos_model'),
]

REQUIRED_LOADED = [
    'kronos_ventas',
    'kronos_resumen_ejecutivo',
    'quickbooks_produccion',
    'quickbooks_ventas',
    'apriori_transacciones',
    'catalogo_ean_clean',
    'ventas_econespecias_mensual_clean',
    'dim_producto_canonico',
    'forecasting_base_mensual_v1',
    'dim_producto_master',
    'product_name_mapping',
    'product_code_conflicts',
    'product_quality_metrics',
    'pp_universe_produccion_2025',
    'forecasting_v3_catalogo_pt_limpio',
    'forecasting_v3_pt_catalog_match_report',
    'forecasting_v3_pt_productos_no_catalogo',
    'forecasting_v3_pt_mensual_model',
    'forecasting_v3_pt_productos_model',
    'forecasting_v3_pp_mensual_model',
    'forecasting_v3_pp_productos_model',
]

REQUIRED_SOURCE_KEYS = set(REQUIRED_LOADED)
REQUIRED_SOURCE_KEYS.discard('quickbooks_ventas')
REQUIRED_SOURCE_KEYS.update(source_key for source_key, _, _ in TABLE_LOADS)
REQUIRED_SOURCE_KEYS.add('quickbooks_ventas')


def _normalize_df(value):
    if isinstance(value, list):
        return pd.DataFrame(value)
    if isinstance(value, pd.DataFrame):
        return value.copy()
    return pd.DataFrame()


def _deduplicate_columns(df, source_key):
    if df.columns.duplicated().any():
        duplicated = df.columns[df.columns.duplicated()].tolist()
        print(
            f"[WARN] {source_key}: columnas duplicadas detectadas antes de exportar. "
            f"Se conserva la primera aparicion: {duplicated}"
        )
        df = df.loc[:, ~df.columns.duplicated()].copy()
    return df


def _table_schema(loader, table_name):
    return loader.load(
        f"""
        SELECT column_name, data_type, numeric_precision, numeric_scale
        FROM information_schema.columns
        WHERE table_schema = 'silver'
          AND table_name = '{table_name}'
        ORDER BY ordinal_position
        """
    )


def _table_columns(loader, table_name):
    cols = _table_schema(loader, table_name)['column_name'].tolist()
    return [c for c in cols if c != 'id']


def _prepare_for_export(df, columns, source_key):
    df_export = _deduplicate_columns(df.copy(), source_key)
    for col in columns:
        if col not in df_export.columns:
            df_export[col] = None
    return df_export[columns].copy()


def _truncate(loader, table_name):
    loader.execute(f'TRUNCATE TABLE silver.{table_name}')


def _manual_insert_dataframe(loader, table_name, df_export, columns):
    placeholders = ', '.join(['%s'] * len(columns))
    insert_sql = (
        f"INSERT INTO silver.{table_name} ({', '.join(columns)}) "
        f"VALUES ({placeholders})"
    )
    rows_to_insert = [
        tuple(None if pd.isna(v) else v for v in row)
        for row in df_export.itertuples(index=False, name=None)
    ]
    with loader.conn.cursor() as cur:
        cur.executemany(insert_sql, rows_to_insert)
    loader.conn.commit()


def _sanitize_kronos_ventas_metrics(df_export):
    if 'rentabilidad' not in df_export.columns:
        return df_export

    total_neto = pd.to_numeric(df_export.get('total_neto'), errors='coerce')
    costo_venta = pd.to_numeric(df_export.get('costo_venta'), errors='coerce')
    rentabilidad = pd.to_numeric(df_export.get('rentabilidad'), errors='coerce')

    recalculated = total_neto.fillna(0) - costo_venta.fillna(0)
    overflow_mask = ~np.isfinite(rentabilidad) | (rentabilidad.abs() >= 1e13)

    if overflow_mask.any():
        print(
            f"[WARN] silver.kronos_ventas: {int(overflow_mask.sum())} filas con "
            "rentabilidad invalida o fuera de rango. Se recalcula como total_neto - costo_venta."
        )
        df_export.loc[overflow_mask, 'rentabilidad'] = recalculated.loc[overflow_mask]
        if 'flag_outlier' in df_export.columns:
            df_export.loc[overflow_mask, 'flag_outlier'] = True

    if 'prc_rentabilidad' in df_export.columns:
        rentabilidad_final = pd.to_numeric(df_export['rentabilidad'], errors='coerce').fillna(0)
        total_neto_safe = pd.to_numeric(df_export.get('total_neto'), errors='coerce').fillna(0)
        df_export['prc_rentabilidad'] = np.where(
            total_neto_safe.abs() > 1e-9,
            (rentabilidad_final / total_neto_safe) * 100,
            0.0,
        )

    return df_export


def _sanitize_numeric_for_table(df_export, schema_df, source_key):
    numeric_schema = schema_df[
        schema_df['data_type'].isin(['numeric', 'double precision', 'real', 'integer', 'bigint', 'smallint'])
    ].copy()
    if numeric_schema.empty:
        return df_export

    for row in numeric_schema.to_dict(orient='records'):
        col = row['column_name']
        if col == 'id' or col not in df_export.columns:
            continue

        series = pd.to_numeric(df_export[col], errors='coerce')
        finite_mask = np.isfinite(series.fillna(np.nan).astype(float))
        non_finite_count = int((~finite_mask & series.notna()).sum())
        if non_finite_count:
            print(f"[WARN] {source_key}: {non_finite_count} valores no finitos en {col}. Se convierten a NULL.")
            series.loc[~finite_mask] = np.nan

        has_precision = pd.notna(row.get('numeric_precision'))
        has_scale = pd.notna(row.get('numeric_scale'))

        if row['data_type'] == 'numeric' and has_precision and has_scale:
            precision = int(row['numeric_precision'])
            scale = int(row['numeric_scale'])
            max_abs = (10 ** (precision - scale)) - (10 ** (-scale))
            overflow_mask = series.abs() > max_abs
            if overflow_mask.any():
                print(
                    f"[WARN] {source_key}: {int(overflow_mask.sum())} valores fuera de rango en {col}. "
                    f"Se limitan a +/-{max_abs}."
                )
                series = series.clip(lower=-max_abs, upper=max_abs)
            series = series.round(scale)
        elif row['data_type'] in ('integer', 'bigint', 'smallint'):
            series = series.round(0)

        df_export[col] = series

    return df_export


def _load_standard_table(loader, dfs, source_key, table_name, result_key):
    print(f"Cargando {source_key} a silver.{table_name}...")
    df = _normalize_df(dfs[source_key])

    if result_key == 'product_quality_metrics':
        if 'value' in df.columns and 'metric_value' not in df.columns:
            df = df.rename(columns={'value': 'metric_value'})
        if 'metric_value' in df.columns:
            df['metric_value'] = df['metric_value'].astype(str)

    schema_df = _table_schema(loader, table_name)
    columns = [c for c in schema_df['column_name'].tolist() if c != 'id']
    df_export = _prepare_for_export(df, columns, f"silver.{table_name}")

    if table_name == 'kronos_ventas':
        df_export = _sanitize_kronos_ventas_metrics(df_export)

    df_export = _sanitize_numeric_for_table(df_export, schema_df, f"silver.{table_name}")

    if len(df_export) == 0:
        print(
            f"    [WARN] {source_key} llego sin registros. "
            f"No se trunca silver.{table_name} para no borrar datos existentes."
        )
        return 0

    _truncate(loader, table_name)
    try:
        loader.export(df_export, schema_name='silver', table_name=table_name, if_exists='append')
    except ValueError as exc:
        if 'truth value of a Series is ambiguous' not in str(exc):
            raise
        print(
            f"[WARN] loader.export fallo para silver.{table_name}: {exc}. "
            "Se aplica insercion manual por filas."
        )
        _manual_insert_dataframe(loader, table_name, df_export, columns)

    print(f"    Registros cargados: {len(df_export)}")
    return len(df_export)


def _load_quickbooks_ventas(loader, dfs):
    print("Cargando quickbooks_ventas a silver.quickbooks_ventas...")
    df = _normalize_df(dfs['quickbooks_ventas'])

    cols_qv = [
        'idsales', 'idsale', 'numero',
        'fecha', 'estado', 'cliente',
        'idcliente', 'status', '_status',
        'numitems', 'numitemsprocesados',
        'num_lineas', 'productos_unicos',
        'qty_pedida', 'qty_despachada',
        'qty_pendiente', 'tasa_cumplimiento',
        'es_dato_calidado',
        'fecha_carga', 'pipeline_id', 'batch_id',
    ]
    for col in cols_qv:
        if col not in df.columns:
            df[col] = None

    if 'status' in df.columns and '_status' in df.columns:
        df['status'] = df['status'].fillna(df['_status'])
    elif '_status' in df.columns:
        df['status'] = df['_status']
    df['status'] = df['status'].fillna('')
    df['_status'] = df['status']

    rows = df.to_dict(orient='records')
    df_export = pd.DataFrame(
        [{c: row.get(c) for c in cols_qv} for row in rows],
        columns=cols_qv,
    )
    df_export = pd.DataFrame(df_export.to_numpy(), columns=cols_qv)
    df_export.columns = pd.Index([str(c).strip() for c in df_export.columns])
    if df_export.columns.duplicated().any():
        raise RuntimeError(
            'quickbooks_ventas tiene columnas duplicadas antes de exportar: '
            + str(df_export.columns[df_export.columns.duplicated()].tolist())
        )

    if len(df_export) == 0:
        print(
            "    [WARN] quickbooks_ventas llego sin registros. "
            "No se trunca silver.quickbooks_ventas para no borrar datos existentes."
        )
        return 0

    _truncate(loader, 'quickbooks_ventas')
    placeholders = ', '.join(['%s'] * len(cols_qv))
    insert_sql = (
        f"INSERT INTO silver.quickbooks_ventas ({', '.join(cols_qv)}) "
        f"VALUES ({placeholders})"
    )
    rows_to_insert = [
        tuple(None if pd.isna(v) else v for v in row)
        for row in df_export.itertuples(index=False, name=None)
    ]
    with loader.conn.cursor() as cur:
        cur.executemany(insert_sql, rows_to_insert)
    loader.conn.commit()

    print(f"    Registros cargados: {len(df_export)}")
    return len(df_export)


@data_exporter
def cargar_silver(data, *args, **kwargs):
    """
    Carga datos transformados a la capa Silver.

    El contrato fisico de tablas vive en `crear_tablas_silver`.
    Este bloque solo trunca tablas destino, adapta columnas al contrato y carga.
    """

    print(f"\n[DEBUG] Tipo de data recibida: {type(data)}")

    if isinstance(data, dict):
        dfs = data.get('dfs', {})
        pipeline_id = data.get('pipeline_id', 'etl_silver')
        batch_id = data.get('batch_id')
    else:
        dfs = {}
        pipeline_id = 'etl_silver'
        batch_id = None

    print(f"\n{'='*70}")
    print("CARGA - A CAPA SILVER")
    print(f"{'='*70}")
    print(f"Pipeline: {pipeline_id}")
    print(f"Batch: {batch_id}")
    print(f"Keys en dfs: {list(dfs.keys())}")
    print(f"{'='*70}\n")

    config_path = path.join(get_repo_path(), 'io_config.yaml')
    config_profile = 'local_dwh'
    resultados = {}

    with Postgres.with_config(ConfigFileLoader(config_path, config_profile)) as loader:
        if 'quickbooks_ventas' in dfs:
            resultados['quickbooks_ventas'] = _load_quickbooks_ventas(loader, dfs)

        for source_key, table_name, result_key in TABLE_LOADS:
            if source_key in dfs:
                resultados[result_key] = _load_standard_table(
                    loader,
                    dfs,
                    source_key,
                    table_name,
                    result_key,
                )

    print(f"\n{'='*70}")
    print("RESUMEN CARGA A SILVER")
    print(f"{'='*70}")
    for tabla, registros in resultados.items():
        print(f"  {tabla}: {registros} registros")
    print(f"{'='*70}")

    requested_sources = set(dfs.keys())
    full_run_requested = REQUIRED_SOURCE_KEYS.issubset(requested_sources)
    missing_loaded = [t for t in REQUIRED_LOADED if t not in resultados]
    if missing_loaded and full_run_requested:
        raise RuntimeError(
            'Carga Silver incompleta. Tablas criticas no cargadas: '
            + ', '.join(missing_loaded)
        )
    if missing_loaded:
        print(
            "[WARN] Carga Silver parcial detectada. "
            "No se valida el contrato completo porque esta ejecucion recibio solo: "
            + ', '.join(sorted(requested_sources))
        )

    return {
        'tablas': list(resultados.keys()),
        'registros': resultados,
        'modo_carga': 'completa' if full_run_requested else 'parcial',
        'missing_loaded': missing_loaded,
        'pipeline_id': pipeline_id,
        'batch_id': batch_id,
        'status': 'SUCCESS',
    }


@test
def test_output(output, *args) -> None:
    assert output is not None, 'Carga fallo'
    assert 'status' in output, 'Falta status'
    assert output['status'] == 'SUCCESS', 'Status no es SUCCESS'
    print(f"OK: Carga completada - {output['registros']}")
