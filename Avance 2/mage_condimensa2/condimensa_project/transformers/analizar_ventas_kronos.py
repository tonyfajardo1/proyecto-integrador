"""
Transformer: Analizar ventas de Kronos
Pipeline: analisis_kronos_ventas
Analiza devoluciones, rentabilidad por agencia y detecta anomalias.
"""
import pandas as pd
import numpy as np

if 'transformer' not in dir():
    from mage_ai.data_preparation.decorators import transformer
if 'test' not in dir():
    from mage_ai.data_preparation.decorators import test


@transformer
def analizar_ventas_kronos(data, *args, **kwargs):
    """
    Analiza los datos de ventas de Kronos:
    - Calcula tasa de devoluciones
    - Analiza rentabilidad por agencia
    - Detecta anomalias
    """
    df = data.copy()

    # =========================================================================
    # 1. CALCULAR METRICAS DE DEVOLUCIONES
    # =========================================================================

    # Tasa de devolucion (cantidad)
    df['tasa_devolucion_cant'] = np.where(
        df['cant_venta'] > 0,
        (df['cant_devolucion'] / df['cant_venta']) * 100,
        0
    )

    # Tasa de devolucion (valor)
    df['tasa_devolucion_valor'] = np.where(
        df['total_venta'] > 0,
        (df['total_devolucion'] / df['total_venta']) * 100,
        0
    )

    # Clasificar nivel de devolucion
    def clasificar_devolucion(tasa):
        if tasa == 0:
            return 'SIN_DEVOLUCION'
        elif tasa < 5:
            return 'NORMAL'
        elif tasa < 15:
            return 'ELEVADA'
        else:
            return 'CRITICA'

    df['nivel_devolucion'] = df['tasa_devolucion_cant'].apply(clasificar_devolucion)

    # =========================================================================
    # 2. CALCULAR METRICAS DE RENTABILIDAD
    # =========================================================================

    # Margen de rentabilidad
    df['margen_rentabilidad'] = np.where(
        df['total_neto'] > 0,
        (df['rentabilidad'] / df['total_neto']) * 100,
        0
    )

    # Clasificar rentabilidad
    def clasificar_rentabilidad(margen):
        if margen < 0:
            return 'PERDIDA'
        elif margen < 20:
            return 'BAJA'
        elif margen < 35:
            return 'NORMAL'
        else:
            return 'ALTA'

    df['nivel_rentabilidad'] = df['margen_rentabilidad'].apply(clasificar_rentabilidad)

    # =========================================================================
    # 3. DETECTAR ANOMALIAS (Z-Score simple)
    # =========================================================================

    # Calcular Z-Score para tasa de devolucion
    mean_dev = df['tasa_devolucion_cant'].mean()
    std_dev = df['tasa_devolucion_cant'].std()

    df['zscore_devolucion'] = np.where(
        std_dev > 0,
        (df['tasa_devolucion_cant'] - mean_dev) / std_dev,
        0
    )

    df['es_anomalia_devolucion'] = abs(df['zscore_devolucion']) > 2

    # =========================================================================
    # 4. IMPRIMIR ANALISIS
    # =========================================================================

    print(f"\n{'='*70}")
    print(f"ANALISIS DE VENTAS - KRONOS")
    print(f"{'='*70}")

    print(f"\n[1] RESUMEN GENERAL")
    print(f"    Total registros: {len(df):,}")
    print(f"    Total ventas: ${df['total_venta'].sum():,.2f}")
    print(f"    Total devoluciones: ${df['total_devolucion'].sum():,.2f}")
    print(f"    Rentabilidad total: ${df['rentabilidad'].sum():,.2f}")

    # Tasa global de devoluciones
    tasa_global = (df['total_devolucion'].sum() / df['total_venta'].sum()) * 100 if df['total_venta'].sum() > 0 else 0
    print(f"    Tasa devolucion global: {tasa_global:.2f}%")

    print(f"\n[2] DISTRIBUCION NIVEL DE DEVOLUCION")
    for nivel, count in df['nivel_devolucion'].value_counts().items():
        pct = (count / len(df)) * 100
        print(f"    {nivel}: {count:,} ({pct:.1f}%)")

    print(f"\n[3] ANALISIS POR AGENCIA (Centro de Costo)")
    agencia_stats = df.groupby('centro_costo').agg({
        'total_venta': 'sum',
        'total_devolucion': 'sum',
        'rentabilidad': 'sum',
        'producto': 'count'
    }).round(2)
    agencia_stats.columns = ['Ventas', 'Devoluciones', 'Rentabilidad', 'Num_Productos']
    agencia_stats['Tasa_Dev_%'] = (agencia_stats['Devoluciones'] / agencia_stats['Ventas'] * 100).round(2)
    agencia_stats = agencia_stats.sort_values('Ventas', ascending=False)
    print(agencia_stats.head(10).to_string())

    print(f"\n[4] TOP 10 PRODUCTOS CON MAS DEVOLUCIONES")
    top_dev = df.nlargest(10, 'cant_devolucion')[
        ['producto', 'centro_costo', 'cant_venta', 'cant_devolucion', 'tasa_devolucion_cant']
    ]
    print(top_dev.to_string(index=False))

    print(f"\n[5] ANOMALIAS DETECTADAS")
    anomalias = df[df['es_anomalia_devolucion']]
    print(f"    Registros con anomalia: {len(anomalias)}")
    if len(anomalias) > 0:
        print(f"    Top 5 anomalias:")
        top_anomalias = anomalias.nlargest(5, 'zscore_devolucion')[
            ['producto', 'centro_costo', 'tasa_devolucion_cant', 'zscore_devolucion']
        ]
        print(top_anomalias.to_string(index=False))

    print(f"\n{'='*70}")
    print(f"INSIGHTS PARA DATA MINING:")
    print(f"- Variable objetivo: nivel_devolucion, es_anomalia_devolucion")
    print(f"- Features: centro_costo, producto, mes, total_venta, rentabilidad")
    print(f"- Se pueden entrenar modelos para predecir devoluciones")
    print(f"{'='*70}\n")

    return df


@test
def test_output(output, *args) -> None:
    """
    Verifica que las transformaciones se aplicaron correctamente
    """
    assert output is not None, 'Transformacion fallo'
    assert 'tasa_devolucion_cant' in output.columns, 'Falta columna tasa_devolucion_cant'
    assert 'nivel_devolucion' in output.columns, 'Falta columna nivel_devolucion'
    assert 'es_anomalia_devolucion' in output.columns, 'Falta columna es_anomalia_devolucion'
    print(f"OK: Transformacion completada con {len(output)} registros")
