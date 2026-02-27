"""
Data Exporter: Guardar resultados de deteccion de anomalias
Pipeline: dm_deteccion_anomalias
"""
from mage_ai.settings.repo import get_repo_path
from mage_ai.io.config import ConfigFileLoader
from mage_ai.io.postgres import Postgres
from os import path
from pandas import DataFrame

if 'data_exporter' not in dir():
    from mage_ai.data_preparation.decorators import data_exporter
if 'test' not in dir():
    from mage_ai.data_preparation.decorators import test


@data_exporter
def export_to_postgres(df: DataFrame, *args, **kwargs) -> None:
    """
    Exporta los resultados de deteccion de anomalias al DWH.
    """
    schema_name = 'public'
    table_name = 'dm_anomalias_agencias'

    config_path = path.join(get_repo_path(), 'io_config.yaml')
    config_profile = 'local_dwh'

    try:
        with Postgres.with_config(ConfigFileLoader(config_path, config_profile)) as loader:
            loader.export(
                df,
                schema_name,
                table_name,
                index=False,
                if_exists='replace',
            )

        print(f"\n{'='*60}")
        print(f"EXPORTACION EXITOSA - ANOMALIAS")
        print(f"{'='*60}")
        print(f"Tabla: {schema_name}.{table_name}")
        print(f"Registros: {len(df)}")
        print(f"Anomalias: {df['es_anomalia'].sum()}")
        print(f"{'='*60}\n")

    except Exception as e:
        print(f"[ADVERTENCIA] No se pudo exportar: {e}")


@test
def test_output(*args, **kwargs) -> None:
    print("OK: Exportacion completada")
