"""
Data Exporter: Cargar datos a Bronze
Pipeline: etl_bronze
Persiste los datos crudos extraidos en la capa Bronze.
"""
from mage_ai.settings.repo import get_repo_path
from mage_ai.io.config import ConfigFileLoader
from mage_ai.io.postgres import Postgres
from os import path

if 'data_exporter' not in dir():
    from mage_ai.data_preparation.decorators import data_exporter
if 'test' not in dir():
    from mage_ai.data_preparation.decorators import test


@data_exporter
def cargar_bronze(data, *args, **kwargs):
    """
    Carga datos crudos a la capa Bronze en PostgreSQL.
    """

    dfs = data.get('dfs', {})
    pipeline_id = data.get('pipeline_id', 'etl_bronze')
    batch_id = data.get('batch_id')

    print(f"\n{'='*70}")
    print(f"CARGA - A CAPA BRONZE")
    print(f"{'='*70}")
    print(f"Pipeline: {pipeline_id}")
    print(f"Batch: {batch_id}")
    print(f"Tablas a cargar: {list(dfs.keys())}")
    print(f"{'='*70}\n")

    config_path = path.join(get_repo_path(), 'io_config.yaml')
    config_profile = 'local_dwh'

    resultados = {}

    # Columnas de metadata que se agregan en el data_loader
    METADATA_COLS = ['fuente', 'nombre_tabla_origen', 'pipeline_id', 'batch_id', 'fecha_ingesta']

    with Postgres.with_config(ConfigFileLoader(config_path, config_profile)) as loader:

        # Cargar: kronos_ventas_raw
        if 'ventas_general_4' in dfs:
            print("[1] Cargando ventas Kronos a bronze.kronos_ventas_raw...")
            df = dfs['ventas_general_4'].copy()

            # Separar columnas de datos y metadata
            cols_datos = [c for c in df.columns if c not in METADATA_COLS]
            cols_metadata = [c for c in df.columns if c in METADATA_COLS]

            print(f"    Columnas de datos: {len(cols_datos)}")
            print(f"    Columnas de metadata: {len(cols_metadata)}")

            # Renombrar SOLO columnas de datos a formato Bronze (columna_1, columna_2, ...)
            columnas_bronze = {}
            for i, col in enumerate(cols_datos, 1):
                columnas_bronze[col] = f'columna_{i}'

            df = df.rename(columns=columnas_bronze)

            # Verificar que tenemos 16 columnas de datos (incluyendo MES)
            num_cols_datos = len(cols_datos)
            print(f"    Columnas de datos renombradas: {num_cols_datos}")

            # Agregar columnas faltantes si hay menos de 16
            for i in range(1, 17):
                col_name = f'columna_{i}'
                if col_name not in df.columns:
                    df[col_name] = None
                    print(f"    [WARN] Agregando columna faltante: {col_name}")

            # Seleccionar columnas en orden: 16 datos + 5 metadata
            columnas_finales = [f'columna_{i}' for i in range(1, 17)] + cols_metadata

            df_export = df[columnas_finales].copy()

            # Mostrar muestra de columna_16 (MES)
            mes_valores = df_export['columna_16'].value_counts().head(5)
            print(f"    Valores en columna_16 (MES): {dict(mes_valores)}")
            
            loader.export(
                df_export,
                schema_name='bronze',
                table_name='kronos_ventas_raw',
                if_exists='replace'
            )
            
            print(f"    Registros cargados: {len(df_export)}")
            resultados['kronos_ventas_raw'] = len(df_export)
    
    print(f"\n[OK] Carga a Bronze completada")
    
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
    assert output.get('status') == 'SUCCESS', 'Status no es SUCCESS'
    print(f"OK: Carga a Bronze completada - {output['registros']}")
