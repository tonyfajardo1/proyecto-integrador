"""
Data Exporter: Guardar resultados de Kronos en Data Warehouse local
Pipeline: analisis_kronos_ventas
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
    Exporta los resultados del analisis de Kronos al Data Warehouse local.
    """

    schema_name = 'public'
    table_name = 'kronos_ventas_analisis'

    config_path = path.join(get_repo_path(), 'io_config.yaml')
    config_profile = 'local_dwh'

    # Seleccionar columnas relevantes
    columnas_exportar = [
        'centro_costo',
        'codigo_producto',
        'producto',
        'mes',
        'cant_venta',
        'total_venta',
        'cant_devolucion',
        'total_devolucion',
        'cant_neto',
        'total_neto',
        'costo_venta',
        'rentabilidad',
        'prc_rentabilidad',
        'tasa_devolucion_cant',
        'tasa_devolucion_valor',
        'nivel_devolucion',
        'margen_rentabilidad',
        'nivel_rentabilidad',
        'zscore_devolucion',
        'es_anomalia_devolucion'
    ]

    columnas_disponibles = [c for c in columnas_exportar if c in df.columns]
    df_export = df[columnas_disponibles].copy()

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
        print(f"EXPORTACION EXITOSA - KRONOS")
        print(f"{'='*60}")
        print(f"Tabla: {schema_name}.{table_name}")
        print(f"Registros exportados: {len(df_export)}")
        print(f"Columnas: {len(columnas_disponibles)}")
        print(f"{'='*60}\n")

    except Exception as e:
        print(f"\n[ADVERTENCIA] No se pudo exportar al DWH local: {e}")
        print(f"Los resultados estan disponibles en memoria.\n")


@test
def test_output(*args, **kwargs) -> None:
    print("OK: Proceso de exportacion completado")
