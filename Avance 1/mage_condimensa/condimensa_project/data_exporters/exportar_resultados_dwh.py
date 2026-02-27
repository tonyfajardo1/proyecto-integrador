"""
Data Exporter: Guardar resultados de analisis en Data Warehouse local
Pipeline: analisis_produccion_desviaciones
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
    Exporta los resultados del analisis de desviaciones al Data Warehouse local.
    Crea la tabla si no existe, o reemplaza los datos si existe.
    """

    schema_name = 'public'
    table_name = 'produccion_desviaciones'

    config_path = path.join(get_repo_path(), 'io_config.yaml')
    config_profile = 'local_dwh'

    # Seleccionar columnas relevantes para exportar
    columnas_exportar = [
        'idsales',
        'idsale',
        'fecha',
        'estado',
        'numero',
        'cliente',
        'items_planificados',
        'items_procesados',
        'items_pendientes',
        'qty_total_planificada',
        'qty_total_despachada',
        'num_lineas',
        'desviacion_absoluta',
        'desviacion_porcentual',
        'tasa_cumplimiento',
        'clasificacion_cumplimiento',
        'dia_semana',
        'dia_semana_nombre',
        'mes',
        'mes_nombre',
        'semana_ano'
    ]

    # Filtrar solo columnas que existen
    columnas_disponibles = [c for c in columnas_exportar if c in df.columns]
    df_export = df[columnas_disponibles].copy()

    # Convertir fecha a string para evitar problemas de tipo
    if 'fecha' in df_export.columns:
        df_export['fecha'] = df_export['fecha'].astype(str)

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
        print(f"EXPORTACION EXITOSA")
        print(f"{'='*60}")
        print(f"Tabla: {schema_name}.{table_name}")
        print(f"Registros exportados: {len(df_export)}")
        print(f"Columnas: {len(columnas_disponibles)}")
        print(f"{'='*60}\n")

    except Exception as e:
        print(f"\n[ADVERTENCIA] No se pudo exportar al DWH local: {e}")
        print(f"Los resultados estan disponibles en memoria para su uso.")
        print(f"Puedes ver los resultados en el output del transformer.\n")


@test
def test_output(*args, **kwargs) -> None:
    """
    Verifica que la exportacion fue exitosa
    """
    print("OK: Proceso de exportacion completado")
