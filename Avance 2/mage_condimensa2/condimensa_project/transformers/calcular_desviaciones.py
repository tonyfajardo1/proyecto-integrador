"""
Transformer: Calcular desviaciones plan vs real en produccion
Pipeline: analisis_produccion_desviaciones
Responde: Existen patrones de produccion que expliquen desviaciones plan vs real?
"""
import pandas as pd
import numpy as np

if 'transformer' not in dir():
    from mage_ai.data_preparation.decorators import transformer
if 'test' not in dir():
    from mage_ai.data_preparation.decorators import test


@transformer
def calcular_desviaciones(data, *args, **kwargs):
    """
    Calcula metricas de desviacion entre plan y real.
    Identifica patrones que explican las desviaciones.
    """
    df = data.copy()

    # Convertir fecha a datetime
    df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce')

    # =========================================================================
    # 1. CALCULAR DESVIACIONES
    # =========================================================================

    # Desviacion absoluta (real - plan)
    df['desviacion_absoluta'] = df['qty_total_despachada'] - df['qty_total_planificada']

    # Desviacion porcentual
    df['desviacion_porcentual'] = np.where(
        df['qty_total_planificada'] > 0,
        ((df['qty_total_despachada'] - df['qty_total_planificada']) / df['qty_total_planificada']) * 100,
        0
    )

    # Tasa de cumplimiento (%)
    df['tasa_cumplimiento'] = np.where(
        df['qty_total_planificada'] > 0,
        (df['qty_total_despachada'] / df['qty_total_planificada']) * 100,
        0
    )

    # Clasificar cumplimiento
    def clasificar_cumplimiento(tasa):
        if tasa >= 95:
            return 'CUMPLE'
        elif tasa >= 80:
            return 'PARCIAL'
        elif tasa > 0:
            return 'BAJO'
        else:
            return 'SIN_DESPACHO'

    df['clasificacion_cumplimiento'] = df['tasa_cumplimiento'].apply(clasificar_cumplimiento)

    # =========================================================================
    # 2. EXTRAER CARACTERISTICAS TEMPORALES (Para encontrar patrones)
    # =========================================================================

    df['dia_semana'] = df['fecha'].dt.dayofweek
    df['dia_semana_nombre'] = df['fecha'].dt.day_name()
    df['mes'] = df['fecha'].dt.month
    df['mes_nombre'] = df['fecha'].dt.month_name()
    df['semana_ano'] = df['fecha'].dt.isocalendar().week.astype(int)
    df['es_inicio_mes'] = df['fecha'].dt.day <= 7
    df['es_fin_mes'] = df['fecha'].dt.day >= 24

    # =========================================================================
    # 3. ANALISIS DE PATRONES
    # =========================================================================

    print(f"\n{'='*70}")
    print(f"ANALISIS DE DESVIACIONES PLAN VS REAL")
    print(f"{'='*70}")

    # Estadisticas generales
    print(f"\n[1] ESTADISTICAS GENERALES")
    print(f"    Total ordenes analizadas: {len(df)}")
    print(f"    Rango de fechas: {df['fecha'].min().date()} a {df['fecha'].max().date()}")

    # Distribucion de cumplimiento
    print(f"\n[2] DISTRIBUCION DE CUMPLIMIENTO")
    cumplimiento_dist = df['clasificacion_cumplimiento'].value_counts()
    for cat, count in cumplimiento_dist.items():
        pct = (count / len(df)) * 100
        print(f"    {cat}: {count} ordenes ({pct:.1f}%)")

    # Estadisticas de desviacion
    print(f"\n[3] ESTADISTICAS DE DESVIACION")
    print(f"    Desviacion promedio: {df['desviacion_porcentual'].mean():.2f}%")
    print(f"    Desviacion mediana: {df['desviacion_porcentual'].median():.2f}%")
    print(f"    Desviacion std: {df['desviacion_porcentual'].std():.2f}%")
    print(f"    Tasa cumplimiento promedio: {df['tasa_cumplimiento'].mean():.2f}%")

    # Patrones por dia de la semana
    print(f"\n[4] PATRONES POR DIA DE LA SEMANA")
    dias_analisis = df.groupby('dia_semana_nombre').agg({
        'tasa_cumplimiento': 'mean',
        'desviacion_porcentual': 'mean',
        'idsales': 'count'
    }).round(2)
    dias_analisis.columns = ['Tasa_Cumpl_%', 'Desv_%', 'Num_Ordenes']
    print(dias_analisis.to_string())

    # Patrones por estado
    print(f"\n[5] PATRONES POR ESTADO DE ORDEN")
    estado_analisis = df.groupby('estado').agg({
        'tasa_cumplimiento': 'mean',
        'desviacion_porcentual': 'mean',
        'idsales': 'count'
    }).round(2)
    estado_analisis.columns = ['Tasa_Cumpl_%', 'Desv_%', 'Num_Ordenes']
    print(estado_analisis.to_string())

    # Ordenes con mayor desviacion negativa (problematicas)
    print(f"\n[6] TOP 5 ORDENES CON MAYOR DESVIACION NEGATIVA")
    problematicas = df.nsmallest(5, 'desviacion_porcentual')[
        ['numero', 'fecha', 'qty_total_planificada', 'qty_total_despachada', 'desviacion_porcentual', 'estado']
    ]
    print(problematicas.to_string(index=False))

    print(f"\n{'='*70}")
    print(f"INSIGHTS PARA DATA MINING:")
    print(f"- Se pueden usar estas caracteristicas para entrenar modelos predictivos")
    print(f"- Variables objetivo: clasificacion_cumplimiento, desviacion_porcentual")
    print(f"- Features: dia_semana, mes, estado, num_lineas, qty_total_planificada")
    print(f"{'='*70}\n")

    return df


@test
def test_output(output, *args) -> None:
    """
    Verifica que las transformaciones se aplicaron correctamente
    """
    assert output is not None, 'Transformacion fallo'
    assert 'desviacion_porcentual' in output.columns, 'Falta columna desviacion_porcentual'
    assert 'clasificacion_cumplimiento' in output.columns, 'Falta columna clasificacion_cumplimiento'
    assert 'tasa_cumplimiento' in output.columns, 'Falta columna tasa_cumplimiento'
    print(f"OK: Transformacion completada con {len(output)} registros")
