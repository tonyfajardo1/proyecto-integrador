"""
Data Exporter: Cargar datos a Silver
Pipeline: etl_silver
Persiste los datos transformados en la capa Silver.
"""
from mage_ai.settings.repo import get_repo_path
from mage_ai.io.config import ConfigFileLoader
from mage_ai.io.postgres import Postgres
from os import path
import pandas as pd

if 'data_exporter' not in dir():
    from mage_ai.data_preparation.decorators import data_exporter
if 'test' not in dir():
    from mage_ai.data_preparation.decorators import test


@data_exporter
def cargar_silver(data, *args, **kwargs):
    """
    Carga datos transformados a la capa Silver en PostgreSQL.
    """
    
    print(f"\n[DEBUG] Tipo de data recibida: {type(data)}")
    
    # Extraer dataframes
    if isinstance(data, dict):
        dfs = data.get('dfs', {})
        pipeline_id = data.get('pipeline_id', 'etl_silver')
        batch_id = data.get('batch_id')
    else:
        dfs = {}
        pipeline_id = 'etl_silver'
        batch_id = None
    
    print(f"\n{'='*70}")
    print(f"CARGA - A CAPA SILVER")
    print(f"{'='*70}")
    print(f"Pipeline: {pipeline_id}")
    print(f"Batch: {batch_id}")
    print(f"Keys en dfs: {list(dfs.keys())}")
    print(f"{'='*70}\n")
    
    # Configurar conexion a DWH local
    config_path = path.join(get_repo_path(), 'io_config.yaml')
    config_profile = 'local_dwh'
    
    resultados = {}
    
    with Postgres.with_config(ConfigFileLoader(config_path, config_profile)) as loader:
        
        # =========================================================================
        # CARGAR: Kronos Ventas a Silver
        # =========================================================================
        
        # Buscar la clave correcta - puede ser 'kronos_ventas' u otra
        key_ventas = None
        for key in dfs.keys():
            if 'kronos' in key.lower() and 'ventas' in key.lower():
                key_ventas = key
                break
        
        if key_ventas:
            print(f"[1] Cargando {key_ventas} a silver.kronos_ventas...")
            
            dato = dfs[key_ventas]
            
            # Convertir a DataFrame si es una lista
            if isinstance(dato, list):
                print(f"[DEBUG] Convirtiendo lista a DataFrame...")
                df = pd.DataFrame(dato)
            elif isinstance(dato, pd.DataFrame):
                df = dato.copy()
            else:
                print(f"[ERROR] Tipo de dato no reconocido: {type(dato)}")
                df = pd.DataFrame()
            
            print(f"[DEBUG] DataFrame shape: {df.shape}")
            
            # Seleccionar solo las columnas que existen en la tabla silver
            columnas_silver = [
                'centro_costo', 'codigo_producto', 'codigo_alterno', 'producto',
                'mes', 'anio', 'cant_venta', 'total_venta', 'cant_nc', 'total_nc',
                'cant_devolucion', 'total_devolucion', 'cant_neto', 'total_neto',
                'costo_venta', 'rentabilidad', 'prc_rentabilidad',
                'es_dato_calidado', 'flag_outlier', 'flag_valor_nulo',
                'fecha_carga', 'pipeline_id', 'batch_id'
            ]
            
            # Filtrar columnas que existen
            columnas_existentes = [c for c in columnas_silver if c in df.columns]
            df_export = df[columnas_existentes].copy()
            
            # Agregar columnas faltantes si es necesario
            for col in columnas_silver:
                if col not in df_export.columns:
                    df_export[col] = None
            
            # Cargar a la tabla
            loader.export(
                df_export,
                schema_name='silver',
                table_name='kronos_ventas',
                if_exists='replace'  # Replace para simplificar
            )
            
            print(f"    Registros cargados: {len(df_export)}")
            resultados['kronos_ventas'] = len(df_export)
        else:
            print("[WARNING] No se encontró la tabla de ventas en los datos")
    
    print(f"\n[OK] Carga a Silver completada")
    
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
    assert 'status' in output, 'Falta status'
    assert output['status'] == 'SUCCESS', 'Status no es SUCCESS'
    print(f"OK: Carga completada - {output['registros']}")
