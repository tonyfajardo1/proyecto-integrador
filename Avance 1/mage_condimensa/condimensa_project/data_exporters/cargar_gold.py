"""
Data Exporter: Cargar KPIs y resultados a Gold
Pipeline: etl_gold
Persiste KPIs calculados en la capa Gold.
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
def cargar_gold(data, *args, **kwargs):
    """
    Carga KPIs y metricas a la capa Gold en PostgreSQL.
    """
    
    print(f"\n[DEBUG] Tipo de data recibida: {type(data)}")
    
    # Extraer datos
    if isinstance(data, dict):
        dfs = data.get('dfs', {})
        pipeline_id = data.get('pipeline_id', 'etl_gold')
        batch_id = data.get('batch_id')
    else:
        dfs = {}
        pipeline_id = 'etl_gold'
        batch_id = None
    
    print(f"\n{'='*70}")
    print(f"CARGA - A CAPA GOLD")
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
        # CARGAR: KPIs de Ventas
        # =========================================================================
        
        if 'kpis_ventas' in dfs:
            print("[1] Cargando KPIs de ventas a gold.kpis_ventas...")
            
            df = dfs['kpis_ventas']
            
            # Convertir a DataFrame si es lista
            if isinstance(df, list):
                print(f"[DEBUG] Convirtiendo lista a DataFrame...")
                df = pd.DataFrame(df)
            elif isinstance(df, pd.DataFrame):
                df = df.copy()
            else:
                print(f"[ERROR] Tipo de dato no reconocido: {type(df)}")
                df = pd.DataFrame()
            
            print(f"[DEBUG] DataFrame shape: {df.shape}")
            
            if len(df) > 0:
                loader.export(
                    df,
                    schema_name='gold',
                    table_name='kpis_ventas',
                    if_exists='replace'
                )
                print(f"    Registros cargados: {len(df)}")
                resultados['kpis_ventas'] = len(df)
        
        # =========================================================================
        # CARGAR: Metricas por Agencia
        # =========================================================================
        
        if 'metricas_agencias' in dfs:
            print("[2] Cargando metricas por agencia a gold.metricas_agencias...")
            
            df = dfs['metricas_agencias']
            
            if isinstance(df, list):
                df = pd.DataFrame(df)
            elif not isinstance(df, pd.DataFrame):
                df = pd.DataFrame()
            
            if len(df) > 0:
                loader.export(
                    df,
                    schema_name='gold',
                    table_name='metricas_agencias',
                    if_exists='replace'
                )
                print(f"    Registros cargados: {len(df)}")
                resultados['metricas_agencias'] = len(df)
        
        # =========================================================================
        # CARGAR: Metricas por Producto
        # =========================================================================
        
        if 'metricas_productos' in dfs:
            print("[3] Cargando metricas por producto a gold.metricas_productos...")
            
            df = dfs['metricas_productos']
            
            if isinstance(df, list):
                df = pd.DataFrame(df)
            elif not isinstance(df, pd.DataFrame):
                df = pd.DataFrame()
            
            if len(df) > 0:
                loader.export(
                    df,
                    schema_name='gold',
                    table_name='metricas_productos',
                    if_exists='replace'
                )
                print(f"    Registros cargados: {len(df)}")
                resultados['metricas_productos'] = len(df)

        # =====================================================================
        # CARGAR: KPIs de Produccion (QuickBooks)
        # =====================================================================

        if 'kpis_produccion' in dfs:
            print("[4] Cargando KPIs de produccion a gold.kpis_produccion...")

            df = dfs['kpis_produccion']
            if isinstance(df, list):
                df = pd.DataFrame(df)
            elif not isinstance(df, pd.DataFrame):
                df = pd.DataFrame()

            if len(df) > 0:
                loader.export(df, schema_name='gold', table_name='kpis_produccion', if_exists='replace')
                print(f"    Registros cargados: {len(df)}")
                resultados['kpis_produccion'] = len(df)

        # =====================================================================
        # CARGAR: KPIs de Ventas QuickBooks
        # =====================================================================

        if 'kpis_quickbooks_ventas' in dfs:
            print("[5] Cargando KPIs de ventas QuickBooks a gold.kpis_quickbooks_ventas...")

            df = dfs['kpis_quickbooks_ventas']
            if isinstance(df, list):
                df = pd.DataFrame(df)
            elif not isinstance(df, pd.DataFrame):
                df = pd.DataFrame()

            if len(df) > 0:
                loader.export(df, schema_name='gold', table_name='kpis_quickbooks_ventas', if_exists='replace')
                print(f"    Registros cargados: {len(df)}")
                resultados['kpis_quickbooks_ventas'] = len(df)

    print(f"\n{'='*70}")
    print(f"RESUMEN CARGA A GOLD")
    print(f"{'='*70}")
    for tabla, registros in resultados.items():
        print(f"  {tabla}: {registros} registros")
    print(f"{'='*70}")

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
