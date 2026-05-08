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


TABLE_DDL = {
    'kpis_ventas': '''
        CREATE TABLE IF NOT EXISTS gold.kpis_ventas (
            id SERIAL PRIMARY KEY,
            centro_costo VARCHAR(100),
            codigo_producto VARCHAR(50),
            producto VARCHAR(255),
            mes VARCHAR(20),
            anio INTEGER,
            cant_venta NUMERIC(15,2),
            total_venta NUMERIC(15,2),
            cant_neto NUMERIC(15,2),
            total_neto NUMERIC(15,2),
            cant_devolucion NUMERIC(15,2),
            total_devolucion NUMERIC(15,2),
            tasa_devolucion_cant NUMERIC(8,4),
            tasa_devolucion_valor NUMERIC(8,4),
            nivel_devolucion VARCHAR(20),
            costo_venta NUMERIC(15,2),
            rentabilidad NUMERIC(15,2),
            prc_rentabilidad NUMERIC(8,4),
            margen_bruto NUMERIC(8,4),
            nivel_rentabilidad VARCHAR(20),
            ticket_promedio NUMERIC(15,2),
            margen_contribucion NUMERIC(8,4),
            fecha_calculo TIMESTAMP,
            pipeline_id VARCHAR(50),
            batch_id VARCHAR(50)
        )
    ''',
    'metricas_agencias': '''
        CREATE TABLE IF NOT EXISTS gold.metricas_agencias (
            id SERIAL PRIMARY KEY,
            centro_costo VARCHAR(100),
            total_venta NUMERIC(15,2),
            total_neto NUMERIC(15,2),
            cant_venta INTEGER,
            total_devolucion NUMERIC(15,2),
            rentabilidad NUMERIC(15,2),
            ticket_promedio NUMERIC(15,2),
            tasa_devolucion NUMERIC(8,4),
            rentabilidad_promedio NUMERIC(8,4),
            fecha_calculo TIMESTAMP,
            pipeline_id VARCHAR(50),
            batch_id VARCHAR(50)
        )
    ''',
    'metricas_productos': '''
        CREATE TABLE IF NOT EXISTS gold.metricas_productos (
            id SERIAL PRIMARY KEY,
            producto VARCHAR(255),
            total_venta NUMERIC(15,2),
            total_neto NUMERIC(15,2),
            cant_venta INTEGER,
            total_devolucion NUMERIC(15,2),
            rentabilidad NUMERIC(15,2),
            ticket_promedio NUMERIC(15,2),
            tasa_devolucion NUMERIC(8,4),
            rentabilidad_promedio NUMERIC(8,4),
            fecha_calculo TIMESTAMP,
            pipeline_id VARCHAR(50),
            batch_id VARCHAR(50)
        )
    ''',
    'kpis_produccion': '''
        CREATE TABLE IF NOT EXISTS gold.kpis_produccion (
            id SERIAL PRIMARY KEY,
            cliente VARCHAR(255),
            numero_orden VARCHAR(50),
            qty_total_planificada NUMERIC(15,2),
            qty_total_despachada NUMERIC(15,2),
            total_lineas NUMERIC(15,2),
            num_ordenes INTEGER,
            tasa_cumplimiento NUMERIC(8,4),
            desviacion_total NUMERIC(15,2),
            fecha_calculo TIMESTAMP,
            pipeline_id VARCHAR(50),
            batch_id VARCHAR(50)
        )
    ''',
    'kpis_quickbooks_ventas': '''
        CREATE TABLE IF NOT EXISTS gold.kpis_quickbooks_ventas (
            id SERIAL PRIMARY KEY,
            cliente VARCHAR(255),
            qty_total_pedida NUMERIC(15,2),
            qty_total_despachada NUMERIC(15,2),
            total_lineas NUMERIC(15,2),
            total_productos NUMERIC(15,2),
            num_ordenes INTEGER,
            tasa_cumplimiento NUMERIC(8,4),
            fecha_calculo TIMESTAMP,
            pipeline_id VARCHAR(50),
            batch_id VARCHAR(50)
        )
    ''',
}


def _normalize_df(df):
    if isinstance(df, list):
        return pd.DataFrame(df)
    if isinstance(df, pd.DataFrame):
        return df.copy()
    return pd.DataFrame()


def _ensure_and_truncate(loader, table_name):
    """Garantiza existencia de tabla destino y la deja vacia para recarga."""
    loader.execute('CREATE SCHEMA IF NOT EXISTS gold')
    loader.execute(TABLE_DDL[table_name])
    loader.execute(f'TRUNCATE TABLE gold.{table_name}')


@data_exporter
def cargar_gold(data, *args, **kwargs):
    """
    Carga KPIs y metricas a la capa Gold en PostgreSQL.

    Flujo del bloque:
    1) Lee dataframes calculados por el transformador de KPIs.
    2) Sincroniza estructura destino y limpia tablas de salida.
    3) Exporta cada KPI con trazabilidad de pipeline/batch.
    4) Valida que las tablas criticas de Gold se hayan cargado.
    """
    
    print(f"\n[DEBUG] Tipo de data recibida: {type(data)}")
    
    # Extraer payload estandar del pipeline.
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
        # [1] CARGAR: KPIs de Ventas
        # =========================================================================
        
        if 'kpis_ventas' in dfs:
            print("[1] Cargando KPIs de ventas a gold.kpis_ventas...")
            
            df = _normalize_df(dfs['kpis_ventas'])
            
            print(f"[DEBUG] DataFrame shape: {df.shape}")
            _ensure_and_truncate(loader, 'kpis_ventas')
            
            if len(df) > 0:
                loader.export(
                    df,
                    schema_name='gold',
                    table_name='kpis_ventas',
                    if_exists='append'
                )
                print(f"    Registros cargados: {len(df)}")
                resultados['kpis_ventas'] = len(df)
        
        # =========================================================================
        # [2] CARGAR: Metricas por Agencia
        # =========================================================================
        
        if 'metricas_agencias' in dfs:
            print("[2] Cargando metricas por agencia a gold.metricas_agencias...")
            
            df = _normalize_df(dfs['metricas_agencias'])
            _ensure_and_truncate(loader, 'metricas_agencias')
            
            if len(df) > 0:
                loader.export(
                    df,
                    schema_name='gold',
                    table_name='metricas_agencias',
                    if_exists='append'
                )
                print(f"    Registros cargados: {len(df)}")
                resultados['metricas_agencias'] = len(df)
        
        # =========================================================================
        # [3] CARGAR: Metricas por Producto
        # =========================================================================
        
        if 'metricas_productos' in dfs:
            print("[3] Cargando metricas por producto a gold.metricas_productos...")
            
            df = _normalize_df(dfs['metricas_productos'])
            _ensure_and_truncate(loader, 'metricas_productos')
            
            if len(df) > 0:
                loader.export(
                    df,
                    schema_name='gold',
                    table_name='metricas_productos',
                    if_exists='append'
                )
                print(f"    Registros cargados: {len(df)}")
                resultados['metricas_productos'] = len(df)

        # =====================================================================
        # [4] CARGAR: KPIs de Produccion (QuickBooks)
        # =====================================================================

        if 'kpis_produccion' in dfs:
            print("[4] Cargando KPIs de produccion a gold.kpis_produccion...")

            df = _normalize_df(dfs['kpis_produccion'])
            _ensure_and_truncate(loader, 'kpis_produccion')

            if len(df) > 0:
                loader.export(df, schema_name='gold', table_name='kpis_produccion', if_exists='append')
                print(f"    Registros cargados: {len(df)}")
                resultados['kpis_produccion'] = len(df)

        # =====================================================================
        # [5] CARGAR: KPIs de Ventas QuickBooks
        # =====================================================================

        if 'kpis_quickbooks_ventas' in dfs:
            print("[5] Cargando KPIs de ventas QuickBooks a gold.kpis_quickbooks_ventas...")

            df = _normalize_df(dfs['kpis_quickbooks_ventas'])
            _ensure_and_truncate(loader, 'kpis_quickbooks_ventas')

            if len(df) > 0:
                loader.export(df, schema_name='gold', table_name='kpis_quickbooks_ventas', if_exists='append')
                print(f"    Registros cargados: {len(df)}")
                resultados['kpis_quickbooks_ventas'] = len(df)
        else:
            print("[5] Sin datos de QuickBooks ventas en este batch; limpiando tabla destino...")
            _ensure_and_truncate(loader, 'kpis_quickbooks_ventas')
            resultados['kpis_quickbooks_ventas'] = 0

    print(f"\n{'='*70}")
    print(f"RESUMEN CARGA A GOLD")
    print(f"{'='*70}")
    for tabla, registros in resultados.items():
        print(f"  {tabla}: {registros} registros")
    print(f"{'='*70}")

    required_loaded = [
        'kpis_ventas',
        'metricas_agencias',
        'metricas_productos',
        'kpis_produccion',
        'kpis_quickbooks_ventas',
    ]
    missing_loaded = [t for t in required_loaded if t not in resultados]
    if missing_loaded:
        raise RuntimeError(
            'Carga Gold incompleta. Tablas criticas no cargadas: '
            + ', '.join(missing_loaded)
        )

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
