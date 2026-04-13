"""
Transformer: Analizar rendimiento comercial por agencia y producto
Pipeline: dm_analisis_comercial_kronos
Tecnicas: Agregaciones, Rankings, Analisis de Pareto
"""
import pandas as pd
import numpy as np

if 'transformer' not in dir():
    from mage_ai.data_preparation.decorators import transformer
if 'test' not in dir():
    from mage_ai.data_preparation.decorators import test


@transformer
def analizar_rendimiento_comercial(data, *args, **kwargs):
    """
    Analiza el rendimiento comercial de Kronos:
    - KPIs por agencia
    - Top productos por rentabilidad
    - Analisis de devoluciones
    - Rankings y comparativas
    """
    df = data.copy()

    print(f"\n{'='*70}")
    print(f"ANALISIS DE RENDIMIENTO COMERCIAL - KRONOS")
    print(f"{'='*70}\n")

    # =========================================================================
    # 1. KPIs POR AGENCIA
    # =========================================================================

    print("[1] CALCULANDO KPIs POR AGENCIA...")

    kpis_agencia = df.groupby('centro_costo').agg({
        'total_venta': 'sum',
        'cant_venta': 'sum',
        'total_devolucion': 'sum',
        'cant_devolucion': 'sum',
        'rentabilidad': 'sum',
        'costo_venta': 'sum',
        'producto': 'nunique',
        'prc_rentabilidad': 'mean'
    }).reset_index()

    kpis_agencia.columns = [
        'agencia', 'total_ventas', 'unidades_vendidas',
        'total_devoluciones', 'unidades_devueltas',
        'rentabilidad_total', 'costo_total', 'productos_vendidos',
        'margen_promedio'
    ]

    # Calcular metricas derivadas
    kpis_agencia['tasa_devolucion'] = np.where(
        kpis_agencia['unidades_vendidas'] > 0,
        (kpis_agencia['unidades_devueltas'] / kpis_agencia['unidades_vendidas']) * 100,
        0
    )

    kpis_agencia['ticket_promedio'] = np.where(
        kpis_agencia['unidades_vendidas'] > 0,
        kpis_agencia['total_ventas'] / kpis_agencia['unidades_vendidas'],
        0
    )

    kpis_agencia['margen_neto'] = np.where(
        kpis_agencia['total_ventas'] > 0,
        (kpis_agencia['rentabilidad_total'] / kpis_agencia['total_ventas']) * 100,
        0
    )

    # Ranking por ventas
    kpis_agencia['ranking_ventas'] = kpis_agencia['total_ventas'].rank(ascending=False).astype(int)

    # Ranking por rentabilidad
    kpis_agencia['ranking_rentabilidad'] = kpis_agencia['rentabilidad_total'].rank(ascending=False).astype(int)

    # Participacion de mercado
    total_ventas_global = kpis_agencia['total_ventas'].sum()
    kpis_agencia['participacion_mercado'] = (kpis_agencia['total_ventas'] / total_ventas_global) * 100

    print(f"    Agencias analizadas: {len(kpis_agencia)}")
    print(f"    Venta total: ${total_ventas_global:,.2f}")

    # =========================================================================
    # 2. TOP PRODUCTOS POR RENTABILIDAD
    # =========================================================================

    print("\n[2] ANALIZANDO TOP PRODUCTOS...")

    kpis_producto = df.groupby(['producto', 'codigo_producto']).agg({
        'total_venta': 'sum',
        'cant_venta': 'sum',
        'rentabilidad': 'sum',
        'cant_devolucion': 'sum',
        'prc_rentabilidad': 'mean',
        'centro_costo': 'nunique'
    }).reset_index()

    kpis_producto.columns = [
        'producto', 'codigo', 'total_ventas', 'unidades',
        'rentabilidad', 'devoluciones', 'margen_promedio', 'agencias_venta'
    ]

    # Calcular metricas
    kpis_producto['tasa_devolucion'] = np.where(
        kpis_producto['unidades'] > 0,
        (kpis_producto['devoluciones'] / kpis_producto['unidades']) * 100,
        0
    )

    kpis_producto['precio_promedio'] = np.where(
        kpis_producto['unidades'] > 0,
        kpis_producto['total_ventas'] / kpis_producto['unidades'],
        0
    )

    # Rankings
    kpis_producto['ranking_ventas'] = kpis_producto['total_ventas'].rank(ascending=False).astype(int)
    kpis_producto['ranking_rentabilidad'] = kpis_producto['rentabilidad'].rank(ascending=False).astype(int)

    # Participacion
    kpis_producto['participacion'] = (kpis_producto['total_ventas'] / total_ventas_global) * 100

    # Analisis Pareto (80/20)
    kpis_producto = kpis_producto.sort_values('total_ventas', ascending=False)
    kpis_producto['participacion_acumulada'] = kpis_producto['participacion'].cumsum()
    kpis_producto['es_pareto_80'] = kpis_producto['participacion_acumulada'] <= 80

    productos_pareto = kpis_producto['es_pareto_80'].sum()
    print(f"    Productos totales: {len(kpis_producto)}")
    print(f"    Productos Pareto (80% ventas): {productos_pareto}")

    # =========================================================================
    # 3. ANALISIS DE DEVOLUCIONES
    # =========================================================================

    print("\n[3] ANALIZANDO DEVOLUCIONES...")

    # Productos con alta devolucion
    productos_alta_devolucion = kpis_producto[kpis_producto['tasa_devolucion'] > 10].copy()

    # Agencias con alta devolucion
    agencias_alta_devolucion = kpis_agencia[kpis_agencia['tasa_devolucion'] > 10].copy()

    print(f"    Productos con devolucion >10%: {len(productos_alta_devolucion)}")
    print(f"    Agencias con devolucion >10%: {len(agencias_alta_devolucion)}")

    # =========================================================================
    # 4. ANALISIS POR MES
    # =========================================================================

    print("\n[4] ANALIZANDO TENDENCIA MENSUAL...")

    kpis_mes = df.groupby(['mes', 'anio']).agg({
        'total_venta': 'sum',
        'cant_venta': 'sum',
        'rentabilidad': 'sum',
        'cant_devolucion': 'sum'
    }).reset_index()

    kpis_mes.columns = ['mes', 'anio', 'total_ventas', 'unidades', 'rentabilidad', 'devoluciones']

    kpis_mes['margen'] = np.where(
        kpis_mes['total_ventas'] > 0,
        (kpis_mes['rentabilidad'] / kpis_mes['total_ventas']) * 100,
        0
    )

    print(f"    Meses analizados: {len(kpis_mes)}")

    # =========================================================================
    # 5. RESUMEN EJECUTIVO
    # =========================================================================

    print(f"\n{'='*70}")
    print(f"RESUMEN EJECUTIVO - ANALISIS COMERCIAL KRONOS")
    print(f"{'='*70}")

    # Mejor agencia
    mejor_agencia = kpis_agencia.loc[kpis_agencia['total_ventas'].idxmax()]
    print(f"\n[MEJOR AGENCIA POR VENTAS]")
    print(f"  - Agencia: {mejor_agencia['agencia']}")
    print(f"  - Ventas: ${mejor_agencia['total_ventas']:,.2f}")
    print(f"  - Participacion: {mejor_agencia['participacion_mercado']:.1f}%")

    # Agencia mas rentable
    mas_rentable = kpis_agencia.loc[kpis_agencia['margen_neto'].idxmax()]
    print(f"\n[AGENCIA MAS RENTABLE]")
    print(f"  - Agencia: {mas_rentable['agencia']}")
    print(f"  - Margen: {mas_rentable['margen_neto']:.1f}%")

    # Top 5 productos
    print(f"\n[TOP 5 PRODUCTOS POR VENTAS]")
    for i, row in kpis_producto.head(5).iterrows():
        print(f"  {row['ranking_ventas']}. {row['producto'][:40]}... - ${row['total_ventas']:,.2f}")

    # Productos problematicos (alta devolucion y ventas significativas)
    problematicos = kpis_producto[
        (kpis_producto['tasa_devolucion'] > 15) &
        (kpis_producto['unidades'] > 100)
    ].head(5)

    if len(problematicos) > 0:
        print(f"\n[PRODUCTOS CON ALTA DEVOLUCION (>15%)]")
        for i, row in problematicos.iterrows():
            print(f"  - {row['producto'][:40]}... - Devolucion: {row['tasa_devolucion']:.1f}%")

    print(f"\n{'='*70}\n")

    # =========================================================================
    # RETORNAR RESULTADOS
    # =========================================================================

    return {
        'datos_detalle': df,
        'kpis_agencia': kpis_agencia,
        'kpis_producto': kpis_producto,
        'kpis_mes': kpis_mes,
        'productos_alta_devolucion': productos_alta_devolucion,
        'resumen': {
            'total_ventas': total_ventas_global,
            'total_agencias': len(kpis_agencia),
            'total_productos': len(kpis_producto),
            'productos_pareto': productos_pareto,
            'mejor_agencia': mejor_agencia['agencia'],
            'margen_promedio': kpis_agencia['margen_neto'].mean()
        }
    }


@test
def test_output(output, *args) -> None:
    assert output is not None, 'Transformacion fallo'
    assert 'kpis_agencia' in output, 'Falta kpis_agencia'
    assert 'kpis_producto' in output, 'Falta kpis_producto'
    print(f"OK: Analisis comercial completado")
