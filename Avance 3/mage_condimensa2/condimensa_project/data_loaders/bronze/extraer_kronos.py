"""
Data Loader: Extraer datos de Kronos hacia Bronze
Pipeline: etl_bronze_kronos
Extraccion de datos crudos desde Supabase hacia la capa Bronze.
"""
from mage_ai.settings.repo import get_repo_path
from mage_ai.io.config import ConfigFileLoader
from mage_ai.io.postgres import Postgres
from os import path
import pandas as pd
import uuid
from datetime import datetime

if 'data_loader' not in dir():
    from mage_ai.data_preparation.decorators import data_loader
if 'test' not in dir():
    from mage_ai.data_preparation.decorators import test


@data_loader
def extraer_kronos_bronze(*args, **kwargs):
    """
    Extrae datos crudos de Kronos desde Supabase y los carga a Bronze.
    Mantiene los datos tal como vienen sin transformaciones.
    """
    
    # Generar IDs de lote y pipeline
    batch_id = str(uuid.uuid4())
    pipeline_id = kwargs.get('pipeline_id', 'etl_bronze_kronos')
    
    print(f"\n{'='*70}")
    print(f"EXTRACCION - KRONOS A BRONZE")
    print(f"{'='*70}")
    print(f"Batch ID: {batch_id}")
    print(f"Pipeline ID: {pipeline_id}")
    print(f"{'='*70}\n")
    
    # =========================================================================
    # EXTRAER: Leer desde Kronos (Supabase)
    # =========================================================================
    
    config_path = path.join(get_repo_path(), 'io_config.yaml')
    config_profile = 'kronos'
    
    # Tablas a extraer
    tablas = ['ventas_general_4']
    
    dfs = {}
    
    with Postgres.with_config(ConfigFileLoader(config_path, config_profile)) as loader:
        for tabla in tablas:
            print(f"Extrayendo tabla: kronos.{tabla}...")
            
            # Query simple - obtener todos los datos
            query = f"SELECT * FROM {tabla}"
            df = loader.load(query)
            
            # Agregar metadatos de ingesta
            df['fuente'] = 'kronos'
            df['nombre_tabla_origen'] = tabla
            df['pipeline_id'] = pipeline_id
            df['batch_id'] = batch_id
            df['fecha_ingesta'] = datetime.now()
            
            dfs[tabla] = df
            print(f"  - Registros extraidos: {len(df)}")
    
    print(f"\n[OK] Extraccion completada")
    print(f"Total tablas: {len(dfs)}")
    print(f"Total registros: {sum(len(df) for df in dfs.values())}")
    
    # Retornar diccionario de dataframes
    return {
        'dfs': dfs,
        'batch_id': batch_id,
        'pipeline_id': pipeline_id,
        'metadata': {
            'tablas': tablas,
            'fecha_inicio': datetime.now().isoformat(),
            'registros': sum(len(df) for df in dfs.values())
        }
    }


@test
def test_output(output, *args) -> None:
    assert output is not None, 'No se extrajeron datos'
    assert 'dfs' in output, 'Falta diccionario de dataframes'
    assert len(output['dfs']) > 0, 'No hay tablas extraidas'
    print(f"OK: Extraccion completada - {output['metadata']['registros']} registros")
