"""
Transformer: Entrenar modelo predictivo Random Forest
Pipeline: dm_prediccion_devoluciones
Predice probabilidad de devolucion alta.
"""
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    roc_auc_score,
    precision_score,
    recall_score,
    f1_score,
    accuracy_score,
    average_precision_score,
)

if 'transformer' not in dir():
    from mage_ai.data_preparation.decorators import transformer
if 'test' not in dir():
    from mage_ai.data_preparation.decorators import test


@transformer
def entrenar_modelo(data, *args, **kwargs):
    """
    Entrena Random Forest para predecir devoluciones altas.
    """
    df = data.copy()

    # =========================================================================
    # 1. PREPARAR DATOS PARA ENTRENAMIENTO
    # =========================================================================

    features = ['agencia_encoded', 'mes_encoded', 'log_cant_venta',
                'log_total_venta', 'margen_rentabilidad', 'ratio_costo']

    X = df[features].copy()
    y = df['target_devolucion_alta'].copy()

    # Manejar valores infinitos o NaN
    X = X.replace([np.inf, -np.inf], np.nan).fillna(0)

    # =========================================================================
    # 2. DIVIDIR EN TRAIN/TEST (preferencia temporal)
    # =========================================================================

    temporal_split = False
    if 'periodo_id' in df.columns and df['periodo_id'].nunique() >= 3:
        periodos = sorted(df['periodo_id'].dropna().unique())
        test_periodos = periodos[-max(1, int(len(periodos) * 0.2)):]
        train_mask = ~df['periodo_id'].isin(test_periodos)

        X_train, X_test = X[train_mask], X[~train_mask]
        y_train, y_test = y[train_mask], y[~train_mask]
        temporal_split = True
        print(f"[INFO] Split temporal aplicado. Test periodos: {test_periodos}")
    else:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y if y.nunique() > 1 else None
        )
        print("[WARNING] No hay periodos suficientes, se usa split aleatorio estratificado.")

    print(f"\n{'='*70}")
    print(f"MODELO PREDICTIVO - RANDOM FOREST")
    print(f"{'='*70}")

    print(f"\n[1] DATOS")
    print(f"    Total registros: {len(df)}")
    print(f"    Train: {len(X_train)} | Test: {len(X_test)}")
    print(f"    Clase positiva (devolucion alta): {y.sum()} ({y.mean()*100:.1f}%)")
    print(f"    Split temporal: {'SI' if temporal_split else 'NO'}")

    # =========================================================================
    # 3. ENTRENAR MODELO
    # =========================================================================

    print(f"\n[2] ENTRENANDO MODELO...")

    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        min_samples_split=5,
        min_samples_leaf=2,
        random_state=42,
        n_jobs=-1,
        class_weight='balanced'  # Para manejar desbalance de clases
    )

    model.fit(X_train, y_train)

    # =========================================================================
    # 4. EVALUAR MODELO
    # =========================================================================

    print(f"\n[3] EVALUACION DEL MODELO")

    # Predicciones
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]

    # Metricas
    print(f"\n    Matriz de Confusion:")
    cm = confusion_matrix(y_test, y_pred)
    if cm.shape == (2, 2):
        print(f"    [[TN={cm[0,0]:4d}  FP={cm[0,1]:4d}]")
        print(f"     [FN={cm[1,0]:4d}  TP={cm[1,1]:4d}]]")
    else:
        print(f"    {cm}")

    print(f"\n    Classification Report:")
    if y_test.nunique() > 1:
        report = classification_report(y_test, y_pred, target_names=['Normal', 'Devolucion Alta'])
    else:
        report = classification_report(y_test, y_pred)
    print(report)

    # Metricas obligatorias para clase minoritaria
    acc = accuracy_score(y_test, y_pred)
    prec = precision_score(y_test, y_pred, zero_division=0)
    rec = recall_score(y_test, y_pred, zero_division=0)
    f1 = f1_score(y_test, y_pred, zero_division=0)
    auc = roc_auc_score(y_test, y_prob) if y_test.nunique() > 1 else np.nan
    auprc = average_precision_score(y_test, y_prob) if y_test.nunique() > 1 else np.nan

    print(f"    Accuracy: {acc:.4f}")
    print(f"    Precision (+): {prec:.4f}")
    print(f"    Recall (+): {rec:.4f}")
    print(f"    F1 (+): {f1:.4f}")
    print(f"    AUC-ROC: {auc:.4f}" if not np.isnan(auc) else "    AUC-ROC: N/A")
    print(f"    AUPRC: {auprc:.4f}" if not np.isnan(auprc) else "    AUPRC: N/A")

    # =========================================================================
    # 5. IMPORTANCIA DE FEATURES
    # =========================================================================

    print(f"\n[4] IMPORTANCIA DE FEATURES")
    importances = pd.DataFrame({
        'feature': features,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)

    for _, row in importances.iterrows():
        bar = '█' * int(row['importance'] * 50)
        print(f"    {row['feature']:25s} {row['importance']:.4f} {bar}")

    # =========================================================================
    # 6. AGREGAR PREDICCIONES AL DATAFRAME
    # =========================================================================

    df['prediccion_devolucion'] = model.predict(X)
    df['prob_devolucion_alta'] = model.predict_proba(X)[:, 1]

    # Clasificar riesgo
    def clasificar_riesgo(prob):
        if prob >= 0.7:
            return 'ALTO'
        elif prob >= 0.4:
            return 'MEDIO'
        else:
            return 'BAJO'

    df['nivel_riesgo'] = df['prob_devolucion_alta'].apply(clasificar_riesgo)

    print(f"\n[5] DISTRIBUCION DE RIESGO PREDICHO")
    for nivel, count in df['nivel_riesgo'].value_counts().items():
        print(f"    {nivel}: {count} ({count/len(df)*100:.1f}%)")

    print(f"\n{'='*70}")
    print(f"MODELO GUARDADO Y PREDICCIONES GENERADAS")
    print(f"{'='*70}\n")

    # Guardar metricas del modelo en el dataframe
    df.attrs['model_accuracy'] = acc
    df.attrs['model_precision_pos'] = prec
    df.attrs['model_recall_pos'] = rec
    df.attrs['model_f1_pos'] = f1
    df.attrs['model_auc'] = auc
    df.attrs['model_auprc'] = auprc
    df.attrs['split_temporal'] = temporal_split

    return df


@test
def test_output(output, *args) -> None:
    assert output is not None, 'Transformacion fallo'
    assert 'prob_devolucion_alta' in output.columns, 'Falta probabilidad'
    assert 'nivel_riesgo' in output.columns, 'Falta nivel de riesgo'
    print(f"OK: Modelo entrenado. AUC: {output.attrs.get('model_auc', 'N/A')}")
