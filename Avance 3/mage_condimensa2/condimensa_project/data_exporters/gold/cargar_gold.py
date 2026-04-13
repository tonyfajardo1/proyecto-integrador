"""
Data Exporter: Cargar KPIs y resultados a Gold
Pipeline: etl_gold_kpis
Persiste KPIs calculados en la capa Gold.
"""
from mage_ai.settings.repo import get_repo_path
from mage_ai.io.config import ConfigFileLoader
from mage_ai.io.postgres import Postgres
from os import path

if 'data_exporter' not in dir():
    from mage_ai.data_preparation.decorators import data_exporter
if 'test' not in dir():
    from mage_ai.data_preparation.decorators import test


@data_exporter
def cargar_gold(data, *args, **kwargs):
    """
    Carga KPIs y metricas a la capa Gold en PostgreSQL.
    """
    
    pipeline_id = kwargs.get('pipeline_id', 'etl_gold_kpis')
    
    print(f"\n{'='*70}")
    print(f"CARGA - A CAPA GOLD")
    print(f"{'='*70}")
    print(f"Pipeline: {pipeline_id}")
    print(f"{'='*70}\n")
    
    # Configurar conexion a DWH local
    config_path = path.join(get_repo_path(), 'io_config.yaml')
    config_profile = 'local_dwh'
    
    with Postgres.with_config(ConfigFileLoader(config_path, config_profile)) as loader:
        
        # =========================================================================
        # CARGAR: KPIs de Ventas
        # =========================================================================
        
        if 'sql_kpis_ventas' in data:
            print("[1] Calculando y cargando KPIs de ventas...")
            
            # Ejecutar SQL de KPIs
            loader.execute(data['sql_kpis_ventas'], {'pipeline_id': pipeline_id})
            
            print("    [OK] KPIs de ventas cargados")
        
        # =========================================================================
        # CARGAR: Metricas por Agencia
        # =========================================================================
        
        if 'sql_metricas_agencias' in data:
            print("[2] Calculando y cargando metricas por agencia...")
            
            loader.execute(data['sql_metricas_agencias'], {'pipeline_id': pipeline_id})
            
            print("    [OK] Metricas por agencia cargadas")
        
        # =========================================================================
        # CARGAR: Metricas por Producto
        # =========================================================================
        
        if 'sql_metricas_productos' in data:
            print("[3] Calculando y cargando metricas por producto...")
            
            loader.execute(data['sql_metricas_productos'], {'pipeline_id': pipeline_id})
            
            print("    [OK] Metricas por producto cargadas")
    
    print(f"\n[OK] Carga a Gold completada")
    
    return {
        'pipeline_id': pipeline_id,
        'status': 'SUCCESS'
    }


@test
def test_output(output, *args) -> None:
    assert output is not None, 'Carga fallo'
    assert output.get('status') == 'SUCCESS', 'Status no es SUCCESS'
    print(f"OK: Carga a Gold completada")
