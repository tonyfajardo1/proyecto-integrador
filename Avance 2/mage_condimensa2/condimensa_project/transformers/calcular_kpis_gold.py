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

    Bloques de calculo:
    [1] KPIs de ventas (Kronos)
    [2] Metricas por agencia
    [3] Metricas por producto
    [4] KPIs de produccion (QuickBooks)
    [5] KPIs de ventas QuickBooks

    Cada salida agrega trazabilidad con `pipeline_id`, `batch_id` y
    `fecha_calculo` para auditoria y reproduccion.
    """
    
    print(f"\n{'='*70}")
    print(f"CALCULO DE KPIs - SILVER A GOLD")
    print(f"{'='*70}\n")
    
    # Entrada estandar del pipeline: `dfs` + metadata de ejecucion.
    # Se mantiene fallback defensivo para pruebas unitarias/ejecuciones manuales.
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
    # [1] CALCULAR KPIs DE VENTAS
    # Agrega ventas/devoluciones por centro, producto y periodo.
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
                        'cant_neto', 'total_neto', 'costo_venta', 'rentabilidad']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
            # Calcular KPIs agregados por centro de costo, producto y periodo
            group_cols = [c for c in ['centro_costo', 'producto', 'anio', 'mes'] if c in df.columns]
            
            if group_cols:
                kpis_ventas = df.groupby(group_cols).agg({
                    'cant_venta': 'sum',
                    'total_venta': 'sum',
                    'cant_devolucion': 'sum',
                    'total_devolucion': 'sum',
                    'cant_neto': 'sum',
                    'total_neto': 'sum',
                    'costo_venta': 'sum',
                    'rentabilidad': 'sum',
                }).reset_index()
                
                print(f"    KPIs agrupados: {len(kpis_ventas)}")
                
                # Calcular tasas
                tasa_dev_cant_raw = np.where(
                    kpis_ventas['cant_venta'] > 0,
                    kpis_ventas['cant_devolucion'] / kpis_ventas['cant_venta'],
                    0
                )
                kpis_ventas['tasa_devolucion_cant'] = np.minimum(tasa_dev_cant_raw, 1)

                tasa_dev_valor_raw = np.where(
                    kpis_ventas['total_venta'] > 0,
                    kpis_ventas['total_devolucion'] / kpis_ventas['total_venta'],
                    0
                )
                kpis_ventas['tasa_devolucion_valor'] = np.minimum(tasa_dev_valor_raw, 1)

                kpis_ventas['nivel_devolucion'] = np.select(
                    [
                        kpis_ventas['tasa_devolucion_cant'] >= 0.15,
                        kpis_ventas['tasa_devolucion_cant'] >= 0.08,
                        kpis_ventas['tasa_devolucion_cant'] >= 0.03,
                    ],
                    ['CRITICO', 'ALTO', 'MEDIO'],
                    default='BAJO'
                )
                
                kpis_ventas['prc_rentabilidad'] = np.where(
                    kpis_ventas['total_neto'] > 0,
                    kpis_ventas['rentabilidad'] / kpis_ventas['total_neto'] * 100,
                    0
                )

                kpis_ventas['margen_bruto'] = np.where(
                    kpis_ventas['total_venta'] > 0,
                    (kpis_ventas['total_neto'] - kpis_ventas['costo_venta']) / kpis_ventas['total_venta'] * 100,
                    0
                )

                kpis_ventas['margen_contribucion'] = np.where(
                    kpis_ventas['total_venta'] > 0,
                    kpis_ventas['rentabilidad'] / kpis_ventas['total_venta'] * 100,
                    0
                )

                kpis_ventas['nivel_rentabilidad'] = np.select(
                    [
                        kpis_ventas['prc_rentabilidad'] < 0,
                        kpis_ventas['prc_rentabilidad'] < 15,
                        kpis_ventas['prc_rentabilidad'] < 30,
                    ],
                    ['NEGATIVA', 'BAJA', 'MEDIA'],
                    default='ALTA'
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
    # [2] CALCULAR METRICAS POR AGENCIA
    # Resume desempeno comercial por centro de costo.
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
            
            # Calcular tasa de devolucion como PORCENTAJE y limitar a 100% máximo
            metricas_agencias['tasa_devolucion'] = np.where(
                metricas_agencias['total_venta'] > 0,
                np.minimum(metricas_agencias['total_devolucion'] / metricas_agencias['total_venta'] * 100, 100),
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
    # [3] CALCULAR METRICAS POR PRODUCTO
    # Resume desempeno comercial por producto.
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
            
            # Calcular tasa de devolucion como PORCENTAJE y limitar a 100% máximo
            metricas_productos['tasa_devolucion'] = np.where(
                metricas_productos['total_venta'] > 0,
                np.minimum(metricas_productos['total_devolucion'] / metricas_productos['total_venta'] * 100, 100),
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
    # [4] CALCULAR KPIs DE PRODUCCION (QuickBooks)
    # Mide cumplimiento de ordenes planificadas vs despachadas.
    # =========================================================================

    if 'quickbooks_produccion' in dfs:
        print("[4] Calculando KPIs de produccion...")

        df = dfs['quickbooks_produccion']
        if isinstance(df, list):
            df = pd.DataFrame(df)

        if len(df) > 0:
            # Compatibilidad de nombres entre versiones de Silver
            if 'qty_planificada' not in df.columns and 'qty_total_planificada' in df.columns:
                df['qty_planificada'] = df['qty_total_planificada']
            if 'qty_despachada' not in df.columns and 'qty_total_despachada' in df.columns:
                df['qty_despachada'] = df['qty_total_despachada']

            # Convertir columnas numericas
            for col in ['qty_planificada', 'qty_despachada', 'num_lineas', 'desviacion_absoluta', 'tasa_cumplimiento']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

            # Agregar por cliente; si cliente esta vacio, usar numero_orden como fallback
            group_field = None
            if 'cliente' in df.columns:
                cliente_clean = df['cliente'].astype(str).str.strip().str.lower()
                if ((cliente_clean != '') & (~cliente_clean.isin(['nan', 'none']))).any():
                    group_field = 'cliente'

            if group_field is None and 'numero_orden' in df.columns:
                group_field = 'numero_orden'

            if group_field is not None:
                count_field = 'idsales' if 'idsales' in df.columns else group_field
                kpis_produccion = df.groupby(group_field).agg({
                    'qty_planificada': 'sum',
                    'qty_despachada': 'sum',
                    'num_lineas': 'sum',
                    count_field: 'count'
                }).reset_index()

                kpis_produccion.columns = [group_field, 'qty_total_planificada', 'qty_total_despachada', 'total_lineas', 'num_ordenes']
                if group_field != 'cliente':
                    kpis_produccion['cliente'] = kpis_produccion[group_field].astype(str)

                kpis_produccion['tasa_cumplimiento'] = np.where(
                    kpis_produccion['qty_total_planificada'] > 0,
                    np.minimum((kpis_produccion['qty_total_despachada'] / kpis_produccion['qty_total_planificada']) * 100, 100),
                    0
                )

                kpis_produccion['desviacion_total'] = kpis_produccion['qty_total_planificada'] - kpis_produccion['qty_total_despachada']

                kpis_produccion['fecha_calculo'] = datetime.now()
                kpis_produccion['pipeline_id'] = pipeline_id
                kpis_produccion['batch_id'] = batch_id

                resultados['kpis_produccion'] = kpis_produccion
                etiqueta = 'clientes' if group_field == 'cliente' else group_field
                print(f"    Registros KPI produccion por {etiqueta}: {len(kpis_produccion)}")
                print(f"    Tasa cumplimiento promedio: {kpis_produccion['tasa_cumplimiento'].mean():.2f}%")

    # =========================================================================
    # [5] CALCULAR KPIs DE VENTAS QUICKBOOKS
    # Mide cumplimiento comercial agregado por cliente.
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

            # Agregar por cliente. Si no existe `idsales`, usa una columna
            # disponible como contador de ordenes para mantener compatibilidad.
            if 'cliente' in df.columns:
                count_field = 'idsales' if 'idsales' in df.columns else ('numero' if 'numero' in df.columns else 'cliente')
                kpis_qb_ventas = df.groupby('cliente').agg({
                    'qty_pedida': 'sum',
                    'qty_despachada': 'sum',
                    'num_lineas': 'sum',
                    'productos_unicos': 'sum',
                    count_field: 'count'
                }).reset_index()

                kpis_qb_ventas.columns = ['cliente', 'qty_total_pedida', 'qty_total_despachada', 'total_lineas', 'total_productos', 'num_ordenes']

                kpis_qb_ventas['tasa_cumplimiento'] = np.where(
                    kpis_qb_ventas['qty_total_pedida'] > 0,
                    np.minimum((kpis_qb_ventas['qty_total_despachada'] / kpis_qb_ventas['qty_total_pedida']) * 100, 100),
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
