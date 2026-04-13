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

if 'data_exporter' not in dir():
    from mage_ai.data_preparation.decorators import data_exporter
if 'test' not in dir():
    from mage_ai.data_preparation.decorators import test


TABLE_LOADS = [
    ('kronos_ventas', 'kronos_ventas', 'kronos_ventas'),
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


def _normalize_df(value):
    if isinstance(value, list):
        return pd.DataFrame(value)
    if isinstance(value, pd.DataFrame):
        return value.copy()
    return pd.DataFrame()


def _table_columns(loader, table_name):
    cols = loader.load(
        f"""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'silver'
          AND table_name = '{table_name}'
        ORDER BY ordinal_position
        """
    )['column_name'].tolist()
    return [c for c in cols if c != 'id']


def _prepare_for_export(df, columns):
    df_export = df.copy()
    for col in columns:
        if col not in df_export.columns:
            df_export[col] = None
    return df_export[columns].copy()


def _truncate(loader, table_name):
    loader.execute(f'TRUNCATE TABLE silver.{table_name}')


def _load_standard_table(loader, dfs, source_key, table_name, result_key):
    print(f"Cargando {source_key} a silver.{table_name}...")
    df = _normalize_df(dfs[source_key])

    if result_key == 'product_quality_metrics':
        if 'value' in df.columns and 'metric_value' not in df.columns:
            df = df.rename(columns={'value': 'metric_value'})
        if 'metric_value' in df.columns:
            df['metric_value'] = df['metric_value'].astype(str)

    columns = _table_columns(loader, table_name)
    df_export = _prepare_for_export(df, columns)

    _truncate(loader, table_name)
    if len(df_export) > 0:
        loader.export(df_export, schema_name='silver', table_name=table_name, if_exists='append')

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

    _truncate(loader, 'quickbooks_ventas')
    if len(df_export) > 0:
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

    missing_loaded = [t for t in REQUIRED_LOADED if t not in resultados]
    if missing_loaded:
        raise RuntimeError(
            'Carga Silver incompleta. Tablas criticas no cargadas: '
            + ', '.join(missing_loaded)
        )

    return {
        'tablas': list(resultados.keys()),
        'registros': resultados,
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
