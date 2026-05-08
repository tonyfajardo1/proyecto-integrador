"""
Data Exporter: Cargar KPIs y resultados a Gold
Pipeline: etl_gold
Persiste KPIs calculados en la capa Gold.
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


GOLD_LOAD_ORDER = [
    ('resumen_ejecutivo_kronos', '[0] Cargando resumen ejecutivo Kronos a gold.resumen_ejecutivo_kronos...'),
    ('kpis_ventas', '[1] Cargando KPIs de ventas a gold.kpis_ventas...'),
    ('metricas_agencias', '[2] Cargando metricas por agencia a gold.metricas_agencias...'),
    ('metricas_productos', '[3] Cargando metricas por producto a gold.metricas_productos...'),
    ('quickbooks_indicadores_comerciales', '[4] Cargando indicadores comerciales QuickBooks a gold.quickbooks_indicadores_comerciales...'),
]


def _normalize_df(df):
    if isinstance(df, list):
        return pd.DataFrame(df)
    if isinstance(df, pd.DataFrame):
        return df.copy()
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
    query = f"""
        SELECT column_name, data_type, numeric_precision, numeric_scale
        FROM information_schema.columns
        WHERE table_schema = 'gold'
          AND table_name = '{table_name}'
        ORDER BY ordinal_position
    """
    return loader.load(query)


def _table_columns(loader, table_name):
    schema_df = _table_schema(loader, table_name)
    columns = [col for col in schema_df['column_name'].tolist() if col != 'id']
    if not columns:
        raise RuntimeError(
            f"No existe contrato de columnas para gold.{table_name}. "
            "Ejecuta primero el bloque crear_tablas_gold."
        )
    return columns


def _prepare_for_export(df, columns, source_key):
    prepared = _deduplicate_columns(_normalize_df(df), source_key)
    for column in columns:
        if column not in prepared.columns:
            prepared[column] = None
    return prepared[columns]


def _truncate(loader, table_name):
    loader.execute(f'TRUNCATE TABLE gold.{table_name}')


def _manual_insert_dataframe(loader, table_name, df_export, columns):
    placeholders = ', '.join(['%s'] * len(columns))
    insert_sql = (
        f"INSERT INTO gold.{table_name} ({', '.join(columns)}) "
        f"VALUES ({placeholders})"
    )
    rows_to_insert = [
        tuple(None if pd.isna(v) else v for v in row)
        for row in df_export.itertuples(index=False, name=None)
    ]
    with loader.conn.cursor() as cur:
        cur.executemany(insert_sql, rows_to_insert)
    loader.conn.commit()


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


def _load_gold_table(loader, table_name, raw_df):
    schema_df = _table_schema(loader, table_name)
    columns = [col for col in schema_df['column_name'].tolist() if col != 'id']
    df = _prepare_for_export(raw_df, columns, f"gold.{table_name}")
    df = _sanitize_numeric_for_table(df, schema_df, f"gold.{table_name}")

    _truncate(loader, table_name)

    if len(df) > 0:
        try:
            loader.export(
                df,
                schema_name='gold',
                table_name=table_name,
                if_exists='append'
            )
        except ValueError as exc:
            if 'truth value of a Series is ambiguous' not in str(exc):
                raise
            print(
                f"[WARN] loader.export fallo para gold.{table_name}: {exc}. "
                "Se aplica insercion manual por filas."
            )
            _manual_insert_dataframe(loader, table_name, df, columns)

    return len(df)


@data_exporter
def cargar_gold(data, *args, **kwargs):
    """
    Carga KPIs y metricas a la capa Gold en PostgreSQL.

    Flujo del bloque:
    1) Lee dataframes calculados por el transformador de KPIs.
    2) Usa el contrato creado por crear_tablas_gold y limpia tablas de salida.
    3) Exporta cada KPI con trazabilidad de pipeline/batch.
    4) Valida que las tablas criticas de Gold se hayan cargado.
    """
    
    print(f"\n[DEBUG] Tipo de data recibida: {type(data)}")
    
    # Extraer payload estandar del pipeline.
    if isinstance(data, dict):
        dfs = data.get('dfs') or {}
        pipeline_id = data.get('pipeline_id', 'etl_gold')
        batch_id = data.get('batch_id')
    else:
        dfs = {}
        pipeline_id = 'etl_gold'
        batch_id = None
    
    print(f"\n{'='*70}")
    print(f"CARGA - A CAPA GOLD")
    print(f"{'='*70}")
    print(f"Pipeline: {pipeline_id}")
    print(f"Batch: {batch_id}")
    print(f"Keys en dfs: {list(dfs.keys())}")
    print(f"{'='*70}\n")
    
    # Configurar conexion a DWH local
    config_path = path.join(get_repo_path(), 'io_config.yaml')
    config_profile = 'local_dwh'
    
    resultados = {}
    
    with Postgres.with_config(ConfigFileLoader(config_path, config_profile)) as loader:
        for table_name, message in GOLD_LOAD_ORDER:
            if table_name not in dfs:
                print(f"[WARN] No se recibio dataframe para gold.{table_name}")
                continue

            print(message)
            df = _normalize_df(dfs[table_name])
            print(f"    DataFrame shape: {df.shape}")

            registros = _load_gold_table(loader, table_name, df)
            print(f"    Registros cargados: {registros}")
            resultados[table_name] = registros

    print(f"\n{'='*70}")
    print(f"RESUMEN CARGA A GOLD")
    print(f"{'='*70}")
    for tabla, registros in resultados.items():
        print(f"  {tabla}: {registros} registros")
    print(f"{'='*70}")

    required_loaded = [table_name for table_name, _ in GOLD_LOAD_ORDER]
    missing_loaded = [t for t in required_loaded if t not in resultados]
    if missing_loaded:
        raise RuntimeError(
            'Carga Gold incompleta. Tablas criticas no cargadas: '
            + ', '.join(missing_loaded)
        )

    return {
        'tablas': list(resultados.keys()),
        'registros': resultados,
        'pipeline_id': pipeline_id,
        'batch_id': batch_id,
        'status': 'SUCCESS'
    }


@test
def test_output(output, *args) -> None:
    assert output is not None, 'Carga fallo'
    assert 'status' in output, 'Falta status'
    assert output['status'] == 'SUCCESS', 'Status no es SUCCESS'
    print(f"OK: Carga completada - {output['registros']}")
