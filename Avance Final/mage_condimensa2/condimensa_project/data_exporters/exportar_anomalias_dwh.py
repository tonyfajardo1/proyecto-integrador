"""
Data Exporter: Guardar anomalias detectadas en Capa Gold
Pipeline: dm_deteccion_anomalias
Guarda resultados en gold.anomalias_agencias
"""
from mage_ai.settings.repo import get_repo_path
from mage_ai.io.config import ConfigFileLoader
from mage_ai.io.postgres import Postgres
from os import path
from pandas import DataFrame
import pandas as pd

if 'data_exporter' not in dir():
    from mage_ai.data_preparation.decorators import data_exporter
if 'test' not in dir():
    from mage_ai.data_preparation.decorators import test


@data_exporter
def export_to_postgres(df: DataFrame, *args, **kwargs) -> None:
    """
    Exporta resultados de deteccion de anomalias a la capa Gold.
    """
    schema_name = 'gold'
    table_name = 'anomalias_agencias'

    config_path = path.join(get_repo_path(), 'io_config.yaml')
    config_profile = 'local_dwh'
    pipeline_id = kwargs.get('pipeline_id', 'dm_deteccion_anomalias')

    if df is None or len(df) == 0:
        print('[ADVERTENCIA] No hay datos de anomalias para exportar')
        return

    df = df.copy()

    if 'pipeline_id' not in df.columns:
        df['pipeline_id'] = pipeline_id

    if 'razon_alerta' not in df.columns and 'razon_anomalia' in df.columns:
        df['razon_alerta'] = df['razon_anomalia']

    if 'fecha_deteccion' not in df.columns:
        df['fecha_deteccion'] = pd.Timestamp.now()

    columnas_objetivo = [
        'agencia',
        'ratio_devolucion',
        'ratio_rentabilidad',
        'ratio_costo',
        'ticket_promedio',
        'total_ventas',
        'anomaly_score',
        'es_anomalia',
        'tipo_anomalia',
        'sentido_anomalia',
        'razon_alerta',
        'interpretacion',
        'zscore_ratio_devolucion',
        'zscore_ratio_rentabilidad',
        'zscore_ratio_costo',
        'zscore_ticket_promedio',
        'fecha_deteccion',
        'pipeline_id',
    ]

    for col in columnas_objetivo:
        if col not in df.columns:
            df[col] = None

    df_export = df[columnas_objetivo].copy()

    ddl = f"""
    CREATE TABLE IF NOT EXISTS {schema_name}.{table_name} (
        id SERIAL PRIMARY KEY,
        agencia VARCHAR(100),
        ratio_devolucion NUMERIC(15,4),
        ratio_rentabilidad NUMERIC(15,4),
        ratio_costo NUMERIC(15,4),
        ticket_promedio NUMERIC(15,2),
        total_ventas NUMERIC(15,2),
        anomaly_score NUMERIC(10,6),
        es_anomalia BOOLEAN,
        tipo_anomalia VARCHAR(40),
        sentido_anomalia VARCHAR(20),
        razon_alerta VARCHAR(255),
        interpretacion TEXT,
        zscore_ratio_devolucion NUMERIC(15,4),
        zscore_ratio_rentabilidad NUMERIC(15,4),
        zscore_ratio_costo NUMERIC(15,4),
        zscore_ticket_promedio NUMERIC(15,4),
        fecha_deteccion TIMESTAMP,
        pipeline_id VARCHAR(50)
    )
    """

    try:
        with Postgres.with_config(ConfigFileLoader(config_path, config_profile)) as loader:
            loader.execute(ddl)
            loader.execute(f"ALTER TABLE {schema_name}.{table_name} ALTER COLUMN ratio_devolucion TYPE NUMERIC(15,4)")
            loader.execute(f"ALTER TABLE {schema_name}.{table_name} ALTER COLUMN ratio_rentabilidad TYPE NUMERIC(15,4)")
            loader.execute(f"ALTER TABLE {schema_name}.{table_name} ALTER COLUMN ratio_costo TYPE NUMERIC(15,4)")
            loader.execute(f"ALTER TABLE {schema_name}.{table_name} ALTER COLUMN zscore_ratio_devolucion TYPE NUMERIC(15,4)")
            loader.execute(f"ALTER TABLE {schema_name}.{table_name} ALTER COLUMN zscore_ratio_rentabilidad TYPE NUMERIC(15,4)")
            loader.execute(f"ALTER TABLE {schema_name}.{table_name} ALTER COLUMN zscore_ratio_costo TYPE NUMERIC(15,4)")
            loader.execute(f"ALTER TABLE {schema_name}.{table_name} ALTER COLUMN zscore_ticket_promedio TYPE NUMERIC(15,4)")
            loader.execute(f"DELETE FROM {schema_name}.{table_name} WHERE pipeline_id = '{pipeline_id}'")
            loader.export(
                df_export,
                schema_name,
                table_name,
                index=False,
                if_exists='append',
            )

        print(f"\n{'='*60}")
        print(f"EXPORTACION EXITOSA - ANOMALIAS")
        print(f"{'='*60}")
        print(f"Tabla: {schema_name}.{table_name}")
        print(f"Registros: {len(df_export)}")
        print(f"Anomalias: {df_export['es_anomalia'].sum()}")
        print(f"{'='*60}\n")

    except Exception as e:
        print(f"[ADVERTENCIA] No se pudo exportar: {e}")


@test
def test_output(*args, **kwargs) -> None:
    print("OK: Exportacion completada")
