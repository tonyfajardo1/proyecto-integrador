"""
Data Exporter: Cargar datos a Bronze
Pipeline: etl_bronze
Persiste las 6 tablas raw vigentes de Kronos y QuickBooks.
"""
from os import path

import pandas as pd
from mage_ai.io.config import ConfigFileLoader
from mage_ai.io.postgres import Postgres
from mage_ai.settings.repo import get_repo_path

if 'data_exporter' not in dir():
    from mage_ai.data_preparation.decorators import data_exporter
if 'test' not in dir():
    from mage_ai.data_preparation.decorators import test


TABLE_MAPPINGS = [
    ('kronos.ventas', 'kronos_ventas_raw'),
    ('kronos.rentabilidad', 'kronos_rentabilidad_raw'),
    ('quickbooks.produccion', 'quickbooks_produccion_raw'),
    ('quickbooks.sales', 'quickbooks_ventas_raw'),
    ('quickbooks.catalogo_ean', 'quickbooks_catalogo_ean_raw'),
    ('quickbooks.ventas_econespecias', 'quickbooks_ventas_econespecias_raw'),
]


def _normalize_df(value):
    if isinstance(value, list):
        return pd.DataFrame(value)
    if isinstance(value, pd.DataFrame):
        return value.copy()
    return pd.DataFrame()


def _deduplicate_columns(df: pd.DataFrame, source_key: str) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    prepared = df.copy()
    prepared.columns = pd.Index([str(col).strip() for col in prepared.columns])

    if not prepared.columns.duplicated().any():
        return prepared

    duplicated = prepared.columns[prepared.columns.duplicated()].tolist()
    print(
        f"[WARN] {source_key} tiene columnas duplicadas antes de exportar. "
        f"Se conserva la ultima ocurrencia: {duplicated}"
    )
    return prepared.loc[:, ~prepared.columns.duplicated(keep='last')].copy()


def _table_columns(loader, table_name):
    query = f"""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'bronze'
          AND table_name = '{table_name}'
        ORDER BY ordinal_position
    """
    cols = loader.load(query)['column_name'].tolist()
    return [col for col in cols if col != 'id']


def _prepare_for_export(df, columns, source_key):
    prepared = _deduplicate_columns(df, source_key)
    for column in columns:
        if column not in prepared.columns:
            prepared[column] = None

    rows = prepared.to_dict(orient='records')
    df_export = pd.DataFrame(
        [{column: row.get(column) for column in columns} for row in rows],
        columns=columns,
    )
    df_export.columns = pd.Index([str(col).strip() for col in df_export.columns])

    if df_export.columns.duplicated().any():
        duplicated = df_export.columns[df_export.columns.duplicated()].tolist()
        raise RuntimeError(
            f'{source_key} mantiene columnas duplicadas despues de preparar exportacion: '
            + str(duplicated)
        )

    return df_export


def _manual_insert_dataframe(loader, table_name, df_export, columns):
    placeholders = ', '.join(['%s'] * len(columns))
    insert_sql = (
        f"INSERT INTO bronze.{table_name} ({', '.join(columns)}) "
        f"VALUES ({placeholders})"
    )
    rows_to_insert = [
        tuple(None if pd.isna(value) else value for value in row)
        for row in df_export[columns].itertuples(index=False, name=None)
    ]
    with loader.conn.cursor() as cur:
        cur.executemany(insert_sql, rows_to_insert)
    loader.conn.commit()


@data_exporter
def cargar_bronze(data, *args, **kwargs):
    """
    Carga completa a Bronze.

    Cada tabla raw se trunca y se recarga para mantener una foto consistente
    del ultimo lote operativo.
    """

    if isinstance(data, dict):
        dfs = data.get('dfs', {})
        pipeline_id = data.get('pipeline_id', 'etl_bronze')
        batch_id = data.get('batch_id')
    else:
        dfs = {}
        pipeline_id = 'etl_bronze'
        batch_id = None

    print(f"\n{'='*70}")
    print('CARGA - A CAPA BRONZE')
    print(f"{'='*70}")
    print(f'Pipeline: {pipeline_id}')
    print(f'Batch: {batch_id}')
    print(f"Tablas recibidas: {list(dfs.keys())}")
    print(f"{'='*70}\n")

    config_path = path.join(get_repo_path(), 'io_config.yaml')
    config_profile = 'local_dwh'
    resultados = {}

    with Postgres.with_config(ConfigFileLoader(config_path, config_profile)) as loader:
        for source_key, table_name in TABLE_MAPPINGS:
            if source_key not in dfs:
                print(f'[WARN] No se recibio {source_key}; se omite bronze.{table_name}')
                continue

            print(f'Cargando {source_key} a bronze.{table_name}...')
            df = _normalize_df(dfs[source_key])
            columns = _table_columns(loader, table_name)
            df_export = _prepare_for_export(df, columns, source_key)

            loader.execute(f'TRUNCATE TABLE bronze.{table_name}')
            if len(df_export) > 0:
                try:
                    loader.export(
                        df_export,
                        schema_name='bronze',
                        table_name=table_name,
                        if_exists='append',
                    )
                except ValueError as exc:
                    if 'truth value of a Series is ambiguous' not in str(exc):
                        raise
                    print(
                        f"[WARN] loader.export fallo para bronze.{table_name}. "
                        "Se aplica insercion manual por filas."
                    )
                    _manual_insert_dataframe(loader, table_name, df_export, columns)

            resultados[table_name] = len(df_export)
            print(f'    Registros cargados: {len(df_export)}')

    print(f"\n{'='*70}")
    print('RESUMEN CARGA A BRONZE')
    print(f"{'='*70}")
    for table_name, total in resultados.items():
        print(f'  {table_name}: {total} registros')
    print(f"{'='*70}")

    missing = [table_name for _, table_name in TABLE_MAPPINGS if table_name not in resultados]
    if missing:
        raise RuntimeError(
            'Carga Bronze incompleta. Tablas criticas no cargadas: '
            + ', '.join(missing)
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
    assert output.get('status') == 'SUCCESS', 'Status no es SUCCESS'
    print(f"OK: Carga a Bronze completada - {output['registros']}")
