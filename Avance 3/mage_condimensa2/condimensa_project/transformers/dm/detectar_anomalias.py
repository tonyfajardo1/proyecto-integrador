"""
Transformer: Deteccion de anomalias con Isolation Forest
Pipeline: dm_deteccion_anomalias
Detecta agencias con comportamiento atipico usando ML.
Guarda resultados en gold.anomalias_agencias.
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
    Usa gold.metricas_agencias como entrada.
    """
    df = data.copy()
    pipeline_id = kwargs.get('pipeline_id', 'dm_deteccion_anomalias')

    # =========================================================================
    # 1. SELECCIONAR FEATURES PARA DETECCION
    # =========================================================================

    features = ['ratio_devolucion', 'ratio_rentabilidad', 'ratio_costo', 'ticket_promedio']
    
    # Verificar que las columnas existan
    missing_cols = [c for c in features if c not in df.columns]
    if missing_cols:
        print(f"WARNING: Columnas faltantes: {missing_cols}")
        # Mapear nombres de columnas si es necesario
        col_mapping = {
            'tasa_devolucion': 'ratio_devolucion',
            'rentabilidad_promedio': 'ratio_rentabilidad',
            'margen_promedio': 'ratio_rentabilidad',
            'costo_total': 'ratio_costo'
        }
        for old, new in col_mapping.items():
            if old in df.columns and new not in df.columns:
                df[new] = df[old]
    
    # Usar columnas disponibles
    available_features = [c for c in features if c in df.columns]
    if not available_features:
        available_features = ['tasa_devolucion', 'rentabilidad_promedio', 'ratio_costo', 'ticket_promedio']
        available_features = [c for c in available_features if c in df.columns]
    
    X = df[available_features].copy()

    # =========================================================================
    # 2. ESCALAR DATOS
    # =========================================================================

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # =========================================================================
    # 3. APLICAR ISOLATION FOREST
    # =========================================================================

    iso_forest = IsolationForest(
        n_estimators=100,
        contamination=0.1,
        random_state=42,
        n_jobs=-1
    )

    df['anomaly_label'] = iso_forest.fit_predict(X_scaled)
    df['anomaly_score'] = iso_forest.decision_function(X_scaled)
    df['es_anomalia'] = df['anomaly_label'] == -1

    # =========================================================================
    # 4. CALCULAR Z-SCORES PARA INTERPRETABILIDAD
    # =========================================================================

    for feat in available_features:
        mean_val = df[feat].mean()
        std_val = df[feat].std()
        df[f'zscore_{feat}'] = (df[feat] - mean_val) / std_val if std_val > 0 else 0

    # =========================================================================
    # 5. CLASIFICAR TIPO DE ANOMALIA
    # =========================================================================

    def clasificar_anomalia(row):
        if not row.get('es_anomalia', False):
            return 'NORMAL'

        razones = []
        zscore_dev = row.get('zscore_ratio_devolucion', 0)
        zscore_rent = row.get('zscore_ratio_rentabilidad', 0)
        zscore_costo = row.get('zscore_ratio_costo', 0)
        
        if abs(zscore_dev) > 1.5:
            razones.append('ALTA_DEVOLUCION' if zscore_dev > 0 else 'BAJA_DEVOLUCION')

        if abs(zscore_rent) > 1.5:
            razones.append('BAJA_RENTABILIDAD' if zscore_rent < 0 else 'ALTA_RENTABILIDAD')

        if abs(zscore_costo) > 1.5:
            razones.append('ALTO_COSTO')

        return ', '.join(razones) if razones else 'PATRON_INUSUAL'

    df['razon_alerta'] = df.apply(clasificar_anomalia, axis=1)

    # =========================================================================
    # 6. CLASIFICAR NIVEL DE ALERTA
    # =========================================================================

    def nivel_alerta(row):
        score = row.get('anomaly_score', 0)
        if row.get('es_anomalia', False):
            if score < -0.1:
                return 'CRITICO'
            elif score < 0:
                return 'ALTO'
            else:
                return 'MEDIO'
        return 'NORMAL'

    df['nivel_alerta'] = df.apply(nivel_alerta, axis=1)

    # =========================================================================
    # 7. PREPARAR OUTPUT PARA GOLD
    # =========================================================================

    # Seleccionar columnas para gold.anomalias_agencias
    output_cols = ['centro_costo', 'agencia']
    for col in available_features:
        output_cols.append(col)
    
    output_cols.extend([
        'anomaly_score', 'es_anomalia', 'nivel_alerta',
        'razon_alerta', 'pipeline_id'
    ])
    
    # Renombrar centro_costo a agencia si es necesario
    if 'centro_costo' in df.columns and 'agencia' not in df.columns:
        df['agencia'] = df['centro_costo']
    
    df['pipeline_id'] = pipeline_id
    
    # Agregar Z-scores
    for feat in available_features:
        df[f'zscore_{feat}'] = df.get(f'zscore_{feat}', 0)

    # =========================================================================
    # 8. IMPRIMIR RESULTADOS
    # =========================================================================

    print(f"\n{'='*70}")
    print(f"DETECCION DE ANOMALIAS - ISOLATION FOREST")
    print(f"{'='*70}")

    print(f"\n[CONFIGURACION]")
    print(f"    Algoritmo: Isolation Forest")
    print(f"    n_estimators: 100")
    print(f"    contamination: 0.1 (10%)")
    print(f"    Features: {available_features}")

    print(f"\n[RESULTADOS]")
    print(f"    Total agencias: {len(df)}")
    print(f"    Anomalias detectadas: {df['es_anomalia'].sum()}")
    print(f"    Normales: {(~df['es_anomalia']).sum()}")

    print(f"\n[DETALLE DE ANOMALIAS]")
    anomalias = df[df['es_anomalia']].sort_values('anomaly_score')
    if len(anomalias) > 0:
        for _, row in anomalias.head(10).iterrows():
            agencia = row.get('agencia', row.get('centro_costo', 'N/A'))
            print(f"\n    AGENCIA: {agencia}")
            print(f"    Score: {row['anomaly_score']:.4f}")
            print(f"    Nivel: {row['nivel_alerta']}")
            print(f"    Razon: {row['razon_alerta']}")

    print(f"\n{'='*70}")

    return df


@test
def test_output(output, *args) -> None:
    assert output is not None, 'Transformacion fallo'
    assert 'es_anomalia' in output.columns, 'Falta columna es_anomalia'
    assert 'anomaly_score' in output.columns, 'Falta columna anomaly_score'
    print(f"OK: Deteccion completada. Anomalias: {output['es_anomalia'].sum()}")
