"""
Transformer: Calcular KPIs desde Silver hacia Gold
Pipeline: etl_gold
Calcula KPIs y metricas desde Silver hacia Gold.
"""
import pandas as pd
import numpy as np
from datetime import datetime

if 'transformer' not in dir():
    from mage_ai.data_preparation.decorators import transformer
if 'test' not in dir():
    from mage_ai.data_preparation.decorators import test


@transformer
def calcular_kpis_gold(data, *args, **kwargs):
    """
    Calcula KPIs desde Silver y los prepara para Gold.
    - KPIs de ventas
    - Metricas por agencia
    - Metricas por producto
    """
    
    print(f"\n{'='*70}")
    print(f"CALCULO DE KPIs - SILVER A GOLD")
    print(f"{'='*70}\n")
    
    # Extraer datos del input
    if isinstance(data, dict):
        dfs = data.get('dfs', {})
        batch_id = data.get('batch_id')
        pipeline_id = data.get('pipeline_id', 'etl_gold')
    else:
        dfs = {}
        batch_id = None
        pipeline_id = 'etl_gold'
    
    print(f"Pipeline: {pipeline_id}")
    print(f"Batch: {batch_id}")
    print(f"Tablas recibidas: {list(dfs.keys())}")
    
    resultados = {}
    
    # =========================================================================
    # CALCULAR KPIs DE VENTAS
    # =========================================================================
    
    if 'kronos_ventas' in dfs:
        print("[1] Calculando KPIs de ventas...")
        
        df = dfs['kronos_ventas']
        
        # Convertir a DataFrame si es lista
        if isinstance(df, list):
            df = pd.DataFrame(df)
        elif not isinstance(df, pd.DataFrame):
            df = pd.DataFrame()
        
        print(f"    Registros: {len(df)}")
        print(f"    Columnas: {df.columns.tolist()}")
        
        if len(df) > 0:
            # Convertir columnas a numeric
            for col in ['cant_venta', 'total_venta', 'cant_devolucion', 'total_devolucion', 
                        'cant_neto', 'total_neto', 'rentabilidad']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
            # Calcular KPIs agregados por centro de costo y producto
            group_cols = [c for c in ['centro_costo', 'producto'] if c in df.columns]
            
            if group_cols:
                kpis_ventas = df.groupby(group_cols).agg({
                    'cant_venta': 'sum',
                    'total_venta': 'sum',
                    'cant_devolucion': 'sum',
                    'total_devolucion': 'sum',
                    'cant_neto': 'sum',
                    'total_neto': 'sum',
                    'rentabilidad': 'sum',
                }).reset_index()
                
                print(f"    KPIs agrupados: {len(kpis_ventas)}")
                
                # Calcular tasas
                kpis_ventas['tasa_devolucion_cant'] = np.where(
                    kpis_ventas['cant_venta'] > 0,
                    kpis_ventas['cant_devolucion'] / kpis_ventas['cant_venta'],
                    0
                )
                
                kpis_ventas['prc_rentabilidad'] = np.where(
                    kpis_ventas['total_neto'] > 0,
                    kpis_ventas['rentabilidad'] / kpis_ventas['total_neto'] * 100,
                    0
                )
                
                kpis_ventas['ticket_promedio'] = np.where(
                    kpis_ventas['cant_neto'] > 0,
                    kpis_ventas['total_neto'] / kpis_ventas['cant_neto'],
                    0
                )
                
                kpis_ventas['fecha_calculo'] = datetime.now()
                kpis_ventas['pipeline_id'] = pipeline_id
                kpis_ventas['batch_id'] = batch_id
                
                resultados['kpis_ventas'] = kpis_ventas
                print(f"    KPIs calculados: {len(kpis_ventas)}")
            else:
                print("    [WARNING] No se encontraron columnas para agrupar")
    
    # =========================================================================
    # CALCULAR METRICAS POR AGENCIA
    # =========================================================================
    
    if 'kronos_ventas' in dfs:
        print("[2] Calculando metricas por agencia...")
        
        df = dfs['kronos_ventas']
        
        if isinstance(df, list):
            df = pd.DataFrame(df)
        
        if len(df) > 0 and 'centro_costo' in df.columns:
            # Rellenar NaN con 0 antes de calcular
            df['total_venta'] = pd.to_numeric(df['total_venta'], errors='coerce').fillna(0)
            df['total_neto'] = pd.to_numeric(df['total_neto'], errors='coerce').fillna(0)
            df['total_devolucion'] = pd.to_numeric(df['total_devolucion'], errors='coerce').fillna(0)
            df['rentabilidad'] = pd.to_numeric(df['rentabilidad'], errors='coerce').fillna(0)
            
            metricas_agencias = df.groupby('centro_costo').agg({
                'total_venta': 'sum',
                'total_neto': 'sum',
                'cant_venta': 'count',
                'total_devolucion': 'sum',
                'rentabilidad': 'sum',
            }).reset_index()
            
            metricas_agencias['ticket_promedio'] = np.where(
                metricas_agencias['cant_venta'] > 0,
                metricas_agencias['total_neto'] / metricas_agencias['cant_venta'],
                0
            )
            
            metricas_agencias['tasa_devolucion'] = np.where(
                metricas_agencias['total_venta'] > 0,
                metricas_agencias['total_devolucion'] / metricas_agencias['total_venta'],
                0
            )
            
            metricas_agencias['rentabilidad_promedio'] = np.where(
                metricas_agencias['total_neto'] > 0,
                metricas_agencias['rentabilidad'] / metricas_agencias['total_neto'] * 100,
                0
            )
            
            metricas_agencias['fecha_calculo'] = datetime.now()
            metricas_agencias['pipeline_id'] = pipeline_id
            metricas_agencias['batch_id'] = batch_id
            
            resultados['metricas_agencias'] = metricas_agencias
            print(f"    Agencias calculadas: {len(metricas_agencias)}")
    
    # =========================================================================
    # CALCULAR METRICAS POR PRODUCTO
    # =========================================================================
    
    if 'kronos_ventas' in dfs:
        print("[3] Calculando metricas por producto...")
        
        df = dfs['kronos_ventas']
        
        if isinstance(df, list):
            df = pd.DataFrame(df)
        
        if len(df) > 0 and 'producto' in df.columns:
            # Rellenar NaN con 0
            df['total_venta'] = pd.to_numeric(df['total_venta'], errors='coerce').fillna(0)
            df['total_neto'] = pd.to_numeric(df['total_neto'], errors='coerce').fillna(0)
            df['total_devolucion'] = pd.to_numeric(df['total_devolucion'], errors='coerce').fillna(0)
            df['rentabilidad'] = pd.to_numeric(df['rentabilidad'], errors='coerce').fillna(0)
            
            metricas_productos = df.groupby('producto').agg({
                'total_venta': 'sum',
                'total_neto': 'sum',
                'cant_venta': 'count',
                'total_devolucion': 'sum',
                'rentabilidad': 'sum',
            }).reset_index()
            
            metricas_productos['ticket_promedio'] = np.where(
                metricas_productos['cant_venta'] > 0,
                metricas_productos['total_neto'] / metricas_productos['cant_venta'],
                0
            )
            
            metricas_productos['tasa_devolucion'] = np.where(
                metricas_productos['total_venta'] > 0,
                metricas_productos['total_devolucion'] / metricas_productos['total_venta'],
                0
            )
            
            metricas_productos['rentabilidad_promedio'] = np.where(
                metricas_productos['total_neto'] > 0,
                metricas_productos['rentabilidad'] / metricas_productos['total_neto'] * 100,
                0
            )
            
            metricas_productos['fecha_calculo'] = datetime.now()
            metricas_productos['pipeline_id'] = pipeline_id
            metricas_productos['batch_id'] = batch_id
            
            resultados['metricas_productos'] = metricas_productos
            print(f"    Productos calculados: {len(metricas_productos)}")

    # =========================================================================
    # CALCULAR KPIs DE PRODUCCION (QuickBooks)
    # =========================================================================

    if 'quickbooks_produccion' in dfs:
        print("[4] Calculando KPIs de produccion...")

        df = dfs['quickbooks_produccion']
        if isinstance(df, list):
            df = pd.DataFrame(df)

        if len(df) > 0:
            # Convertir columnas numericas
            for col in ['qty_planificada', 'qty_despachada', 'num_lineas', 'desviacion_absoluta', 'tasa_cumplimiento']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

            # Agregar por cliente
            if 'cliente' in df.columns:
                kpis_produccion = df.groupby('cliente').agg({
                    'qty_planificada': 'sum',
                    'qty_despachada': 'sum',
                    'num_lineas': 'sum',
                    'idsales': 'count'
                }).reset_index()

                kpis_produccion.columns = ['cliente', 'qty_total_planificada', 'qty_total_despachada', 'total_lineas', 'num_ordenes']

                kpis_produccion['tasa_cumplimiento'] = np.where(
                    kpis_produccion['qty_total_planificada'] > 0,
                    (kpis_produccion['qty_total_despachada'] / kpis_produccion['qty_total_planificada']) * 100,
                    0
                )

                kpis_produccion['desviacion_total'] = kpis_produccion['qty_total_planificada'] - kpis_produccion['qty_total_despachada']

                kpis_produccion['fecha_calculo'] = datetime.now()
                kpis_produccion['pipeline_id'] = pipeline_id
                kpis_produccion['batch_id'] = batch_id

                resultados['kpis_produccion'] = kpis_produccion
                print(f"    Clientes con produccion: {len(kpis_produccion)}")
                print(f"    Tasa cumplimiento promedio: {kpis_produccion['tasa_cumplimiento'].mean():.2f}%")

    # =========================================================================
    # CALCULAR KPIs DE VENTAS QUICKBOOKS
    # =========================================================================

    if 'quickbooks_ventas' in dfs:
        print("[5] Calculando KPIs de ventas QuickBooks...")

        df = dfs['quickbooks_ventas']
        if isinstance(df, list):
            df = pd.DataFrame(df)

        if len(df) > 0:
            # Convertir columnas numericas
            for col in ['qty_pedida', 'qty_despachada', 'num_lineas', 'productos_unicos']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

            # Agregar por cliente
            if 'cliente' in df.columns:
                kpis_qb_ventas = df.groupby('cliente').agg({
                    'qty_pedida': 'sum',
                    'qty_despachada': 'sum',
                    'num_lineas': 'sum',
                    'productos_unicos': 'sum',
                    'idsales': 'count'
                }).reset_index()

                kpis_qb_ventas.columns = ['cliente', 'qty_total_pedida', 'qty_total_despachada', 'total_lineas', 'total_productos', 'num_ordenes']

                kpis_qb_ventas['tasa_cumplimiento'] = np.where(
                    kpis_qb_ventas['qty_total_pedida'] > 0,
                    (kpis_qb_ventas['qty_total_despachada'] / kpis_qb_ventas['qty_total_pedida']) * 100,
                    0
                )

                kpis_qb_ventas['fecha_calculo'] = datetime.now()
                kpis_qb_ventas['pipeline_id'] = pipeline_id
                kpis_qb_ventas['batch_id'] = batch_id

                resultados['kpis_quickbooks_ventas'] = kpis_qb_ventas
                print(f"    Clientes con ventas QB: {len(kpis_qb_ventas)}")

    # =========================================================================
    # RESUMEN FINAL
    # =========================================================================

    print(f"\n{'='*70}")
    print(f"RESUMEN KPIs CALCULADOS")
    print(f"{'='*70}")
    for tabla, df in resultados.items():
        print(f"  {tabla}: {len(df)} registros")
    print(f"{'='*70}\n")

    return {
        'dfs': resultados,
        'pipeline_id': pipeline_id,
        'batch_id': batch_id,
        'status': 'KPIS_CALCULATED'
    }


@test
def test_output(output, *args) -> None:
    assert output is not None, 'Calculo de KPIs fallo'
    print(f"OK: KPIs calculados")
