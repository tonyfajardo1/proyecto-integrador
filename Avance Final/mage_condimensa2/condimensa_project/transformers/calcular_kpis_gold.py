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


MONTH_NAMES_ES = {
    1: 'ENERO',
    2: 'FEBRERO',
    3: 'MARZO',
    4: 'ABRIL',
    5: 'MAYO',
    6: 'JUNIO',
    7: 'JULIO',
    8: 'AGOSTO',
    9: 'SEPTIEMBRE',
    10: 'OCTUBRE',
    11: 'NOVIEMBRE',
    12: 'DICIEMBRE',
}


@transformer
def calcular_kpis_gold(data, *args, **kwargs):
    """
    Calcula KPIs desde Silver y los prepara para Gold.

    Bloques de calculo:
    [1] KPIs de ventas (Kronos)
    [2] Metricas por agencia
    [3] Metricas por producto

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
    # [0] RESUMEN EJECUTIVO KRONOS
    # Agrega ventas por agencia y periodo sin depender de producto.
    # =========================================================================

    if 'kronos_resumen_ejecutivo' in dfs:
        print("[0] Calculando resumen ejecutivo Kronos...")

        df = dfs['kronos_resumen_ejecutivo']

        if isinstance(df, list):
            df = pd.DataFrame(df)
        elif not isinstance(df, pd.DataFrame):
            df = pd.DataFrame()

        if len(df) > 0:
            for col in [
                'cant_venta', 'total_venta', 'cant_devolucion', 'total_devolucion',
                'cant_neto', 'total_neto', 'costo_venta', 'rentabilidad',
            ]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

            group_cols = [c for c in ['centro_costo', 'anio', 'mes'] if c in df.columns]
            if group_cols:
                resumen_exec = df.groupby(group_cols).agg({
                    'cant_venta': 'sum',
                    'total_venta': 'sum',
                    'cant_devolucion': 'sum',
                    'total_devolucion': 'sum',
                    'cant_neto': 'sum',
                    'total_neto': 'sum',
                    'costo_venta': 'sum',
                    'rentabilidad': 'sum',
                }).reset_index()

                resumen_exec['ticket_promedio'] = np.where(
                    resumen_exec['cant_neto'] > 0,
                    resumen_exec['total_neto'] / resumen_exec['cant_neto'],
                    0,
                )
                resumen_exec['tasa_devolucion'] = np.where(
                    resumen_exec['total_venta'] > 0,
                    np.minimum(resumen_exec['total_devolucion'] / resumen_exec['total_venta'] * 100, 100),
                    0,
                )
                resumen_exec['rentabilidad_promedio'] = np.where(
                    resumen_exec['total_neto'] > 0,
                    resumen_exec['rentabilidad'] / resumen_exec['total_neto'] * 100,
                    0,
                )
                resumen_exec['fecha_calculo'] = datetime.now()
                resumen_exec['pipeline_id'] = pipeline_id
                resumen_exec['batch_id'] = batch_id

                resultados['resumen_ejecutivo_kronos'] = resumen_exec
                print(f"    Resumen ejecutivo Kronos: {len(resumen_exec)}")
    
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
    # [4] INDICADORES COMERCIALES QUICKBOOKS
    # Curacion orientada a dashboard comercial por fecha/cliente/producto.
    # =========================================================================

    if 'apriori_transacciones' in dfs or 'ventas_econespecias_mensual_clean' in dfs:
        print("[4] Calculando indicadores comerciales QuickBooks...")

        partes_qb = []
        periodos_transaccionales = set()

        df = dfs.get('apriori_transacciones')

        if isinstance(df, list):
            df = pd.DataFrame(df)
        elif not isinstance(df, pd.DataFrame):
            df = pd.DataFrame()

        if len(df) > 0:
            df = df.copy()
            if 'fuente' in df.columns:
                df = df[df['fuente'].astype(str).str.lower().eq('quickbooks')].copy()

            if len(df) > 0:
                df['fecha'] = pd.to_datetime(df.get('fecha'), errors='coerce').dt.date
                df['anio'] = pd.to_datetime(df.get('fecha'), errors='coerce').dt.year
                df['mes'] = pd.to_datetime(df.get('fecha'), errors='coerce').dt.month
                df['mes_nombre'] = pd.to_datetime(df.get('fecha'), errors='coerce').dt.month.map(MONTH_NAMES_ES)
                df['agencia'] = df.get('agencia', '').fillna('sin_agencia').astype(str).str.strip()
                df['cliente'] = df.get('cliente', '').fillna('sin_cliente').astype(str).str.strip()
                df['familia'] = df.get('categoria', '').fillna('SIN_FAMILIA').astype(str).str.strip().str.upper()
                df['producto'] = df.get('producto', '').fillna('SIN_PRODUCTO').astype(str).str.strip()
                df['cantidad'] = pd.to_numeric(df.get('qty'), errors='coerce').fillna(0)
                df['venta_neta'] = pd.to_numeric(df.get('amount'), errors='coerce').fillna(0)
                df['transaccion_id'] = df.get('transaccion_id', '').fillna('').astype(str).str.strip()

                df = df[
                    pd.notna(df['fecha'])
                    & df['cliente'].ne('')
                    & df['producto'].ne('')
                ].copy()

                indicadores_qb = df.groupby(
                    ['fecha', 'anio', 'mes', 'mes_nombre', 'agencia', 'cliente', 'familia', 'producto'],
                    as_index=False,
                ).agg(
                    cantidad=('cantidad', 'sum'),
                    venta_neta=('venta_neta', 'sum'),
                    transacciones=('transaccion_id', 'nunique'),
                )

                indicadores_qb['fuente_dato'] = 'Transaccional QuickBooks'
                periodos_transaccionales = set(
                    indicadores_qb[['anio', 'mes']]
                    .dropna()
                    .astype(int)
                    .itertuples(index=False, name=None)
                )
                partes_qb.append(indicadores_qb)

        df_hist = dfs.get('ventas_econespecias_mensual_clean')

        if isinstance(df_hist, list):
            df_hist = pd.DataFrame(df_hist)
        elif not isinstance(df_hist, pd.DataFrame):
            df_hist = pd.DataFrame()

        if len(df_hist) > 0:
            hist = df_hist.copy()
            hist['fecha'] = pd.to_datetime(hist.get('periodo'), errors='coerce').dt.date
            periodo_ts = pd.to_datetime(hist.get('periodo'), errors='coerce')
            hist['anio'] = pd.to_numeric(hist.get('anio'), errors='coerce').fillna(periodo_ts.dt.year)
            hist['mes'] = periodo_ts.dt.month
            hist['mes_nombre'] = hist['mes'].map(MONTH_NAMES_ES)
            hist['agencia'] = 'QuickBooks mensual'
            hist['cliente'] = 'HISTORICO_MENSUAL'
            hist['familia'] = hist.get('familia', '').fillna('SIN_FAMILIA').astype(str).str.strip().str.upper()
            hist['producto'] = hist.get('producto', '').fillna('SIN_PRODUCTO').astype(str).str.strip()
            hist['cantidad'] = pd.to_numeric(hist.get('cantidad'), errors='coerce').fillna(0)
            hist['venta_neta'] = pd.to_numeric(hist.get('ventas'), errors='coerce').fillna(0)
            hist['transacciones'] = pd.to_numeric(hist.get('recuento_cliente'), errors='coerce').fillna(0).astype(int)

            hist = hist[
                pd.notna(hist['fecha'])
                & hist['producto'].ne('')
                & hist['anio'].notna()
                & hist['mes'].notna()
            ].copy()
            hist['anio'] = hist['anio'].astype(int)
            hist['mes'] = hist['mes'].astype(int)

            if periodos_transaccionales:
                period_key = list(zip(hist['anio'], hist['mes']))
                missing_period_mask = [key not in periodos_transaccionales for key in period_key]
                hist = hist.loc[missing_period_mask].copy()

            if len(hist) > 0:
                historico_qb = hist.groupby(
                    ['fecha', 'anio', 'mes', 'mes_nombre', 'agencia', 'cliente', 'familia', 'producto'],
                    as_index=False,
                ).agg(
                    cantidad=('cantidad', 'sum'),
                    venta_neta=('venta_neta', 'sum'),
                    transacciones=('transacciones', 'sum'),
                )

                historico_qb['fuente_dato'] = 'Historico mensual ventas Econespecias'
                partes_qb.append(historico_qb)

        if partes_qb:
            indicadores_qb = pd.concat(partes_qb, ignore_index=True, sort=False)
            indicadores_qb['fecha_calculo'] = datetime.now()
            indicadores_qb['pipeline_id'] = pipeline_id
            indicadores_qb['batch_id'] = batch_id

            resultados['quickbooks_indicadores_comerciales'] = indicadores_qb
            print(f"    Indicadores comerciales QuickBooks: {len(indicadores_qb)}")

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
