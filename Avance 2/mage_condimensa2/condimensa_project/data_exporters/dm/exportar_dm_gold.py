"""
Data Exporter: Cargar resultados de Data Mining a Gold
Pipeline: dm_*
Guarda resultados de anomalias, clustering y reglas en Gold.
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
def exportar_anomalias_gold(data, *args, **kwargs):
    """
    Exporta resultados de deteccion de anomalias a gold.anomalias_agencias.
    """
    pipeline_id = kwargs.get('pipeline_id', 'dm_deteccion_anomalias')
    
    print(f"\n{'='*70}")
    print(f"EXPORTAR ANOMALIAS A GOLD")
    print(f"{'='*70}\n")
    
    config_path = path.join(get_repo_path(), 'io_config.yaml')
    config_profile = 'local_dwh'
    
    with Postgres.with_config(ConfigFileLoader(config_path, config_profile)) as loader:
        
        # Preparar dataframe para exportar
        df = data.copy()
        
        # Seleccionar columnas para gold.anomalias_agencias
        output_cols = [
            'agencia', 'ratio_devolucion', 'ratio_rentabilidad', 'ratio_costo',
            'ticket_promedio', 'anomaly_score', 'es_anomalia', 'nivel_alerta',
            'zscore_devolucion', 'zscore_rentabilidad', 'zscore_costo',
            'razon_alerta', 'pipeline_id'
        ]
        
        # Agregar columnas que existan
        available_cols = [c for c in output_cols if c in df.columns]
        
        # Agregar columnas de Z-score
        for col in ['ratio_devolucion', 'ratio_rentabilidad', 'ratio_costo', 'ticket_promedio']:
            zscore_col = f'zscore_{col}'
            if zscore_col in df.columns and zscore_col not in available_cols:
                available_cols.append(zscore_col)
        
        df_export = df[available_cols].copy()
        
        # Asegurar que es_anomalia sea booleano
        if 'es_anomalia' in df_export.columns:
            df_export['es_anomalia'] = df_export['es_anomalia'].astype(bool)
        
        # Agregar metadatos del modelo
        df_export['modelo'] = 'IsolationForest'
        df_export['n_estimators'] = 100
        df_export['contamination'] = 0.10
        
        # Exportar
        loader.export(
            df_export,
            schema_name='gold',
            table_name='anomalias_agencias',
            if_exists='replace'
        )
        
        print(f"[OK] Anomalias exportadas: {len(df_export)} registros")
    
    return {'status': 'SUCCESS', 'tabla': 'gold.anomalias_agencias'}


@data_exporter
def exportar_clusters_gold(data, *args, **kwargs):
    """
    Exporta resultados de clustering a gold.clusters_productos.
    """
    pipeline_id = kwargs.get('pipeline_id', 'dm_clustering_productos')
    
    print(f"\n{'='*70}")
    print(f"EXPORTAR CLUSTERS A GOLD")
    print(f"{'='*70}\n")
    
    config_path = path.join(get_repo_path(), 'io_config.yaml')
    config_profile = 'local_dwh'
    
    with Postgres.with_config(ConfigFileLoader(config_path, config_profile)) as loader:
        
        df = data.copy()
        
        # Columnas para gold.clusters_productos
        output_cols = [
            'producto', 'tasa_devolucion', 'margen_rentabilidad', 'ticket_promedio',
            'penetracion', 'total_ventas', 'cluster', 'cluster_nombre',
            'pipeline_id'
        ]
        
        available_cols = [c for c in output_cols if c in df.columns]
        df_export = df[available_cols].copy()
        
        # Agregar metadatos
        df_export['modelo'] = 'KMeans'
        df_export['n_clusters'] = df.get('n_clusters', df_export['cluster'].nunique())
        df_export['silhouette_score'] = df.get('silhouette_score', 0)
        
        # Exportar
        loader.export(
            df_export,
            schema_name='gold',
            table_name='clusters_productos',
            if_exists='replace'
        )
        
        print(f"[OK] Clusters exportados: {len(df_export)} registros")
    
    return {'status': 'SUCCESS', 'tabla': 'gold.clusters_productos'}


@data_exporter
def exportar_reglas_gold(data, *args, **kwargs):
    """
    Exporta reglas de asociacion a gold.reglas_asociacion.
    """
    pipeline_id = kwargs.get('pipeline_id', 'dm_reglas_asociacion')
    
    print(f"\n{'='*70}")
    print(f"EXPORTAR REGLAS A GOLD")
    print(f"{'='*70}\n")
    
    config_path = path.join(get_repo_path(), 'io_config.yaml')
    config_profile = 'local_dwh'
    
    with Postgres.with_config(ConfigFileLoader(config_path, config_profile)) as loader:
        
        df = data.copy()
        
        if len(df) > 0:
            # Columnas para gold.reglas_asociacion
            output_cols = ['antecedente', 'consecuente', 'soporte', 'confianza', 'lift']
            available_cols = [c for c in output_cols if c in df.columns]
            
            if available_cols:
                df_export = df[available_cols].copy()
                
                # Agregar metadatos
                df_export['modelo'] = 'Apriori'
                df_export['min_support'] = 0.05
                df_export['min_confidence'] = 0.5
                df_export['pipeline_id'] = pipeline_id
                
                # Agregar tipo de regla
                def clasificar_regla(consecente):
                    if 'DEVOLUCION' in str(consecente).upper():
                        return 'DEVOLUCION'
                    elif 'RENTAB' in str(consecente).upper():
                        return 'RENTABILIDAD'
                    else: 
                        return 'OTROS'
                
                if 'consecuente' in df_export.columns:
                    df_export['tipo_regla'] = df_export['consecuente'].apply(clasificar_regla)
                
                # Exportar
                loader.export(
                    df_export,
                    schema_name='gold',
                    table_name='reglas_asociacion',
                    if_exists='replace'
                )
                
                print(f"[OK] Reglas exportadas: {len(df_export)}")
            else:
                print("[WARN] No hay columnas validas para exportar")
        else:
            print("[WARN] No hay reglas para exportar")
    
    return {'status': 'SUCCESS', 'tabla': 'gold.reglas_asociacion'}


@test
def test_output(output, *args) -> None:
    assert output is not None, 'Export fallo'
    print(f"OK: Export completado - {output.get('tabla', 'N/A')}")
