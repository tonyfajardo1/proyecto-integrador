"""
Data Loader: Verificar estructura de Silver
Extrae datos y muestra las columnas disponibles.
"""
from mage_ai.settings.repo import get_repo_path
from mage_ai.io.config import ConfigFileLoader
from mage_ai.io.postgres import Postgres
from os import path
import pandas as pd

if 'data_loader' not in dir():
    from mage_ai.data_preparation.decorators import data_loader
if 'test' not in dir():
    from mage_ai.data_preparation.decorators import test


@data_loader
def verificar_columnas_silver(*args, **kwargs):
    """
    Extrae datos de Silver y muestra las columnas disponibles.
    """
    
    print(f"\n{'='*70}")
    print(f"VERIFICANDO COLUMNAS - SILVER.KRONOS_VENTAS")
    print(f"{'='*70}\n")
    
    config_path = path.join(get_repo_path(), 'io_config.yaml')
    config_profile = 'local_dwh'
    
    with Postgres.with_config(ConfigFileLoader(config_path, config_profile)) as loader:
        
        # Ver columnas
        print("[1] Columnas en silver.kronos_ventas:")
        query_cols = """
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_schema = 'silver' 
            AND table_name = 'kronos_ventas'
            ORDER BY ordinal_position
        """
        df_cols = loader.load(query_cols)
        print(df_cols.to_string())
        
        # Ver algunos datos
        print("\n[2] Primeras 3 filas:")
        query = "SELECT * FROM silver.kronos_ventas LIMIT 3"
        df = loader.load(query)
        print(f"Columnas: {df.columns.tolist()}")
        print(df.head(3).to_string())
        
        # Contar registros
        print("\n[3] Total registros:")
        query_count = "SELECT COUNT(*) as total FROM silver.kronos_ventas"
        df_count = loader.load(query_count)
        print(f"Total: {df_count['total'].iloc[0]}")
    
    print(f"\n{'='*70}\n")
    
    # Retornar datos para siguiente bloque
    return {
        'df': df,
        'columnas': df.columns.tolist(),
        'total_registros': int(df_count['total'].iloc[0])
    }


@test
def test_output(output, *args) -> None:
    assert output is not None, 'Fallo al extraer'
    print(f"OK: {output['total_registros']} registros, {len(output['columnas'])} columnas")
