"""
Transformer: Deteccion de anomalias con Isolation Forest
Pipeline: dm_deteccion_anomalias
Detecta agencias con comportamiento atipico usando ML.
"""
import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

if 'transformer' not in dir():
    from mage_ai.data_preparation.decorators import transformer
if 'test' not in dir():
    from mage_ai.data_preparation.decorators import test


@transformer
def detectar_anomalias(data, *args, **kwargs):
    """
    Aplica Isolation Forest para detectar anomalias en agencias.
    """
    df = data.copy()

    # =========================================================================
    # 1. SELECCIONAR FEATURES PARA DETECCION
    # =========================================================================

    features = ['ratio_devolucion', 'ratio_rentabilidad', 'ratio_costo', 'ticket_promedio']
    X = df[features].copy()

    # =========================================================================
    # 2. ESCALAR DATOS
    # =========================================================================

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # =========================================================================
    # 3. APLICAR ISOLATION FOREST
    # =========================================================================

    # contamination = proporcion esperada de anomalias (10%)
    iso_forest = IsolationForest(
        n_estimators=100,
        contamination=0.1,
        random_state=42,
        n_jobs=-1
    )

    # Fit y predict
    df['anomaly_label'] = iso_forest.fit_predict(X_scaled)
    df['anomaly_score'] = iso_forest.decision_function(X_scaled)

    # Convertir labels: -1 = anomalia, 1 = normal
    df['es_anomalia'] = df['anomaly_label'] == -1
    df['tipo_anomalia'] = df['anomaly_label'].map({-1: 'ANOMALIA', 1: 'NORMAL'})

    # =========================================================================
    # 4. CALCULAR Z-SCORES PARA INTERPRETABILIDAD
    # =========================================================================

    for feat in features:
        mean_val = df[feat].mean()
        std_val = df[feat].std()
        df[f'zscore_{feat}'] = (df[feat] - mean_val) / std_val if std_val > 0 else 0

    # =========================================================================
    # 5. CLASIFICAR TIPO DE ANOMALIA (POSITIVA o NEGATIVA)
    # =========================================================================

    def clasificar_anomalia(row):
        if not row['es_anomalia']:
            return 'NORMAL', 'NORMAL', 'Comportamiento dentro de los parametros esperados'

        razones = []
        puntos_positivos = 0
        puntos_negativos = 0

        # Evaluar cada metrica
        # DEVOLUCION: menor es mejor
        if abs(row['zscore_ratio_devolucion']) > 1.0:
            if row['zscore_ratio_devolucion'] > 1.0:
                razones.append('ALTA_DEVOLUCION')
                puntos_negativos += 2  # Alta devolucion es muy negativo
            elif row['zscore_ratio_devolucion'] < -1.0:
                razones.append('BAJA_DEVOLUCION')
                puntos_positivos += 1  # Baja devolucion es positivo

        # RENTABILIDAD: mayor es mejor
        if abs(row['zscore_ratio_rentabilidad']) > 1.0:
            if row['zscore_ratio_rentabilidad'] > 1.0:
                razones.append('ALTA_RENTABILIDAD')
                puntos_positivos += 2  # Alta rentabilidad es muy positivo
            elif row['zscore_ratio_rentabilidad'] < -1.0:
                razones.append('BAJA_RENTABILIDAD')
                puntos_negativos += 2  # Baja rentabilidad es muy negativo

        # COSTO: menor es mejor
        if abs(row['zscore_ratio_costo']) > 1.0:
            if row['zscore_ratio_costo'] > 1.0:
                razones.append('ALTO_COSTO')
                puntos_negativos += 1
            elif row['zscore_ratio_costo'] < -1.0:
                razones.append('BAJO_COSTO')
                puntos_positivos += 1

        # TICKET PROMEDIO: mayor generalmente es mejor (clientes premium)
        if abs(row['zscore_ticket_promedio']) > 1.5:
            if row['zscore_ticket_promedio'] > 1.5:
                razones.append('ALTO_TICKET')
                puntos_positivos += 1
            elif row['zscore_ticket_promedio'] < -1.5:
                razones.append('BAJO_TICKET')
                puntos_negativos += 1

        # Determinar si es POSITIVA o NEGATIVA
        if puntos_positivos > puntos_negativos:
            sentido = 'POSITIVA'
            interpretacion = 'Rendimiento superior al promedio - REPLICAR PRACTICAS'
        elif puntos_negativos > puntos_positivos:
            sentido = 'NEGATIVA'
            interpretacion = 'Rendimiento inferior al promedio - REQUIERE ATENCION'
        else:
            sentido = 'MIXTA'
            interpretacion = 'Patron inusual con aspectos positivos y negativos'

        razon = ', '.join(razones) if razones else 'PATRON_INUSUAL'
        return razon, sentido, interpretacion

    # Aplicar clasificacion
    resultados = df.apply(clasificar_anomalia, axis=1)
    df['razon_anomalia'] = [r[0] for r in resultados]
    df['sentido_anomalia'] = [r[1] for r in resultados]
    df['interpretacion'] = [r[2] for r in resultados]

    # =========================================================================
    # 6. IMPRIMIR RESULTADOS
    # =========================================================================

    print(f"\n{'='*70}")
    print(f"DETECCION DE ANOMALIAS - ISOLATION FOREST")
    print(f"{'='*70}")

    print(f"\n[1] CONFIGURACION DEL MODELO")
    print(f"    Algoritmo: Isolation Forest")
    print(f"    n_estimators: 100")
    print(f"    contamination: 0.1 (10%)")
    print(f"    Features: {features}")

    print(f"\n[2] RESULTADOS")
    print(f"    Total agencias: {len(df)}")
    print(f"    Anomalias detectadas: {df['es_anomalia'].sum()}")
    print(f"    Normales: {(~df['es_anomalia']).sum()}")

    print(f"\n[3] DETALLE DE ANOMALIAS")
    anomalias = df[df['es_anomalia']].sort_values('anomaly_score')
    if len(anomalias) > 0:
        for _, row in anomalias.iterrows():
            emoji = "🟢" if row['sentido_anomalia'] == 'POSITIVA' else "🔴" if row['sentido_anomalia'] == 'NEGATIVA' else "🟡"
            print(f"\n    {emoji} AGENCIA: {row['agencia'].upper()}")
            print(f"    Tipo: ANOMALIA {row['sentido_anomalia']}")
            print(f"    Score: {row['anomaly_score']:.4f}")
            print(f"    Razon: {row['razon_anomalia']}")
            print(f"    Interpretacion: {row['interpretacion']}")
            print(f"    - Ratio Devolucion: {row['ratio_devolucion']:.2f}% (Z={row['zscore_ratio_devolucion']:.2f})")
            print(f"    - Ratio Rentabilidad: {row['ratio_rentabilidad']:.2f}% (Z={row['zscore_ratio_rentabilidad']:.2f})")
            print(f"    - Ratio Costo: {row['ratio_costo']:.2f}% (Z={row['zscore_ratio_costo']:.2f})")
            print(f"    - Ticket Promedio: ${row['ticket_promedio']:.2f} (Z={row['zscore_ticket_promedio']:.2f})")
    else:
        print("    No se detectaron anomalias significativas")

    print(f"\n[4] RANKING DE AGENCIAS (por score de anomalia)")
    ranking = df.sort_values('anomaly_score')[['agencia', 'anomaly_score', 'tipo_anomalia', 'ratio_devolucion']]
    print(ranking.to_string(index=False))

    print(f"\n{'='*70}")
    print(f"INTERPRETACION:")
    print(f"- Score mas negativo = mas anomalo")
    print(f"- Score positivo = comportamiento normal")
    print(f"- Las anomalias requieren investigacion adicional")
    print(f"{'='*70}\n")

    return df


@test
def test_output(output, *args) -> None:
    assert output is not None, 'Transformacion fallo'
    assert 'es_anomalia' in output.columns, 'Falta columna es_anomalia'
    assert 'anomaly_score' in output.columns, 'Falta columna anomaly_score'
    print(f"OK: Deteccion completada. Anomalias: {output['es_anomalia'].sum()}")
