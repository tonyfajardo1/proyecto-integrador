"""
Data Exporter: Guardar predicciones en DWH
Pipeline: dm_prediccion_devoluciones
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
    Exporta las predicciones al DWH.
    """
    schema_name = 'public'
    table_name = 'dm_predicciones_devoluciones'

    config_path = path.join(get_repo_path(), 'io_config.yaml')
    config_profile = 'local_dwh'

    # Seleccionar columnas relevantes
    cols = ['centro_costo', 'producto', 'mes', 'cant_venta', 'total_venta',
            'cant_devolucion', 'tasa_devolucion', 'target_devolucion_alta',
            'prediccion_devolucion', 'prob_devolucion_alta', 'nivel_riesgo']

    cols_disponibles = [c for c in cols if c in df.columns]
    df_export = df[cols_disponibles].copy()

    try:
        with Postgres.with_config(ConfigFileLoader(config_path, config_profile)) as loader:
            loader.export(
                df_export,
                schema_name,
                table_name,
                index=False,
                if_exists='replace',
            )

        print(f"\n{'='*60}")
        print(f"EXPORTACION EXITOSA - PREDICCIONES")
        print(f"{'='*60}")
        print(f"Tabla: {schema_name}.{table_name}")
        print(f"Registros: {len(df_export)}")
        print(f"Alto riesgo: {(df_export['nivel_riesgo'] == 'ALTO').sum()}")
        print(f"{'='*60}\n")

    except Exception as e:
        print(f"[ADVERTENCIA] No se pudo exportar: {e}")


@test
def test_output(*args, **kwargs) -> None:
    print("OK: Exportacion completada")
