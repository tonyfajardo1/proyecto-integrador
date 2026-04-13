"""
Transformer: Analizar ventas de QuickBooks
Pipeline: analisis_quickbooks_ventas
Analiza cumplimiento de pedidos, patrones por cliente y eficiencia.
"""
import pandas as pd
import numpy as np

if 'transformer' not in dir():
    from mage_ai.data_preparation.decorators import transformer
if 'test' not in dir():
    from mage_ai.data_preparation.decorators import test


@transformer
def analizar_ventas_quickbooks(data, *args, **kwargs):
    """
    Analiza los datos de ventas de QuickBooks:
    - Calcula tasa de cumplimiento de despacho
    - Analiza patrones por cliente
    - Identifica ordenes problematicas
    """
    df = data.copy()

    # =========================================================================
    # 1. PREPARAR DATOS
    # =========================================================================

    df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce')
    df['dia_semana'] = df['fecha'].dt.dayofweek
    df['dia_semana_nombre'] = df['fecha'].dt.day_name()
    df['mes'] = df['fecha'].dt.month

    # =========================================================================
    # 2. CALCULAR METRICAS DE CUMPLIMIENTO
    # =========================================================================

    # Tasa de cumplimiento de despacho
    df['tasa_cumplimiento'] = np.where(
        df['qty_pedida'] > 0,
        (df['qty_despachada'] / df['qty_pedida']) * 100,
        0
    )

    # Cantidad pendiente
    df['qty_pendiente'] = df['qty_pedida'] - df['qty_despachada']

    # Clasificar cumplimiento
    def clasificar_cumplimiento(row):
        if row['estado'] == 'PENDIENTE':
            return 'PENDIENTE'
        elif row['tasa_cumplimiento'] >= 95:
            return 'COMPLETO'
        elif row['tasa_cumplimiento'] >= 50:
            return 'PARCIAL'
        elif row['tasa_cumplimiento'] > 0:
            return 'BAJO'
        else:
            return 'SIN_DESPACHO'

    df['clasificacion_cumplimiento'] = df.apply(clasificar_cumplimiento, axis=1)

    # =========================================================================
    # 3. EXTRAER NOMBRE DE CLIENTE LIMPIO
    # =========================================================================

    df['cliente_corto'] = df['cliente'].str.split(':').str[0].str.strip()
    df['cliente_corto'] = df['cliente_corto'].str[:50]

    # =========================================================================
    # 4. DETECTAR ANOMALIAS
    # =========================================================================

    # Solo para ordenes procesadas
    df_procesadas = df[df['estado'] == 'PROCESADA']

    if len(df_procesadas) > 0:
        mean_tasa = df_procesadas['tasa_cumplimiento'].mean()
        std_tasa = df_procesadas['tasa_cumplimiento'].std()

        df['zscore_cumplimiento'] = np.where(
            (df['estado'] == 'PROCESADA') & (std_tasa > 0),
            (df['tasa_cumplimiento'] - mean_tasa) / std_tasa,
            0
        )
    else:
        df['zscore_cumplimiento'] = 0

    df['es_anomalia'] = abs(df['zscore_cumplimiento']) > 2

    # =========================================================================
    # 5. IMPRIMIR ANALISIS
    # =========================================================================

    print(f"\n{'='*70}")
    print(f"ANALISIS DE VENTAS - QUICKBOOKS")
    print(f"{'='*70}")

    print(f"\n[1] RESUMEN GENERAL")
    print(f"    Total ordenes: {len(df)}")
    print(f"    Qty total pedida: {df['qty_pedida'].sum():,.0f}")
    print(f"    Qty total despachada: {df['qty_despachada'].sum():,.0f}")
    tasa_global = (df['qty_despachada'].sum() / df['qty_pedida'].sum()) * 100 if df['qty_pedida'].sum() > 0 else 0
    print(f"    Tasa cumplimiento global: {tasa_global:.2f}%")

    print(f"\n[2] DISTRIBUCION POR ESTADO")
    for estado, count in df['estado'].value_counts().items():
        qty_ped = df[df['estado'] == estado]['qty_pedida'].sum()
        qty_desp = df[df['estado'] == estado]['qty_despachada'].sum()
        tasa = (qty_desp / qty_ped * 100) if qty_ped > 0 else 0
        print(f"    {estado}: {count} ordenes | Pedido: {qty_ped:,.0f} | Despachado: {qty_desp:,.0f} | Tasa: {tasa:.1f}%")

    print(f"\n[3] CLASIFICACION DE CUMPLIMIENTO")
    for clasif, count in df['clasificacion_cumplimiento'].value_counts().items():
        pct = (count / len(df)) * 100
        print(f"    {clasif}: {count} ({pct:.1f}%)")

    print(f"\n[4] TOP 5 CLIENTES POR VOLUMEN")
    clientes = df.groupby('cliente_corto').agg({
        'idsales': 'count',
        'qty_pedida': 'sum',
        'qty_despachada': 'sum'
    }).round(0)
    clientes.columns = ['Ordenes', 'Pedido', 'Despachado']
    clientes['Tasa_%'] = (clientes['Despachado'] / clientes['Pedido'] * 100).round(1)
    clientes = clientes.sort_values('Pedido', ascending=False).head(5)
    print(clientes.to_string())

    print(f"\n[5] ANALISIS POR DIA DE LA SEMANA")
    dias = df.groupby('dia_semana_nombre').agg({
        'idsales': 'count',
        'tasa_cumplimiento': 'mean'
    }).round(2)
    dias.columns = ['Ordenes', 'Tasa_Cumpl_%']
    print(dias.to_string())

    print(f"\n{'='*70}")
    print(f"INSIGHTS PARA DATA MINING:")
    print(f"- Variable objetivo: clasificacion_cumplimiento, tasa_cumplimiento")
    print(f"- Features: cliente, estado, dia_semana, qty_pedida, num_lineas")
    print(f"- Se pueden predecir ordenes con riesgo de bajo cumplimiento")
    print(f"{'='*70}\n")

    return df


@test
def test_output(output, *args) -> None:
    """
    Verifica que las transformaciones se aplicaron correctamente
    """
    assert output is not None, 'Transformacion fallo'
    assert 'tasa_cumplimiento' in output.columns, 'Falta columna tasa_cumplimiento'
    assert 'clasificacion_cumplimiento' in output.columns, 'Falta columna clasificacion_cumplimiento'
    print(f"OK: Transformacion completada con {len(output)} registros")
