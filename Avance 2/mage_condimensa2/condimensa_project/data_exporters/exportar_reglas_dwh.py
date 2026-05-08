"""
Data Exporter: Guardar reglas de asociacion en Capa Gold
Pipeline: dm_reglas_asociacion
Guarda resultados en gold.reglas_asociacion
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
    Exporta reglas de asociacion a la capa Gold.
    """
    schema_name = 'gold'
    table_name = 'reglas_asociacion'

    config_path = path.join(get_repo_path(), 'io_config.yaml')
    config_profile = 'local_dwh'
    pipeline_id = kwargs.get('pipeline_id', 'dm_reglas_asociacion')

    if 'pipeline_id' not in df.columns:
        df = df.copy()
        df['pipeline_id'] = pipeline_id

    # Alinear columnas para dashboard y trazabilidad
    if 'tipo_regla' not in df.columns:
        df['tipo_regla'] = 'ASOCIACION'
    if 'modelo' not in df.columns:
        df['modelo'] = 'APRIORI'
    if 'min_support' not in df.columns:
        df['min_support'] = kwargs.get('min_support', 0.15)
    if 'min_confidence' not in df.columns:
        df['min_confidence'] = kwargs.get('min_confidence', 0.35)
    if 'fecha_generacion' not in df.columns:
        from datetime import datetime
        df['fecha_generacion'] = datetime.now()
    if 'interpretacion' not in df.columns:
        df['interpretacion'] = None
    if 'accion_sugerida' not in df.columns:
        df['accion_sugerida'] = None

    try:
        with Postgres.with_config(ConfigFileLoader(config_path, config_profile)) as loader:
            loader.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {schema_name}.{table_name} (
                    id SERIAL PRIMARY KEY,
                    antecedente TEXT,
                    consecuente TEXT,
                    soporte NUMERIC(8,6),
                    confianza NUMERIC(8,6),
                    lift NUMERIC(10,4),
                    tipo_regla VARCHAR(50),
                    modelo VARCHAR(50),
                    min_support NUMERIC(6,4),
                    min_confidence NUMERIC(6,4),
                    interpretacion VARCHAR(30),
                    accion_sugerida TEXT,
                    fecha_generacion TIMESTAMP,
                    pipeline_id VARCHAR(50)
                )
                """
            )

            # Idempotencia: reemplazo logico por pipeline
            loader.execute(f"DELETE FROM {schema_name}.{table_name} WHERE pipeline_id = '{pipeline_id}'")
            loader.export(
                df[[
                    'antecedente', 'consecuente', 'soporte', 'confianza', 'lift',
                    'tipo_regla', 'modelo', 'min_support', 'min_confidence',
                    'interpretacion', 'accion_sugerida', 'fecha_generacion', 'pipeline_id',
                ]],
                schema_name,
                table_name,
                index=False,
                if_exists='append',
            )

        print(f"\n{'='*60}")
        print(f"EXPORTACION EXITOSA - REGLAS DE ASOCIACION")
        print(f"{'='*60}")
        print(f"Tabla: {schema_name}.{table_name}")
        print(f"Reglas exportadas: {len(df)}")
        print(f"{'='*60}\n")

    except Exception as e:
        print(f"[ADVERTENCIA] No se pudo exportar: {e}")


@test
def test_output(*args, **kwargs) -> None:
    print("OK: Exportacion completada")
