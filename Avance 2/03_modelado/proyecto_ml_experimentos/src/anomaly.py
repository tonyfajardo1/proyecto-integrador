import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.preprocessing import StandardScaler
from sklearn.svm import OneClassSVM


FEATURES = ["ratio_devolucion", "ratio_rentabilidad", "ratio_costo", "ticket_promedio"]


def _scores_to_binary(score, contamination):
    n = len(score)
    if n == 0:
        return np.array([], dtype=int)
    n_anom = max(1, int(round(n * contamination)))
    idx = np.argsort(score)[-n_anom:]
    pred = np.ones(n, dtype=int)
    pred[idx] = -1
    return pred


def _fit_predict_scores(model_name, model, Xs, contamination):
    if model_name == "LOF":
        pred = model.fit_predict(Xs)
        score = -model.negative_outlier_factor_
    elif model_name == "PCA_Reconstruction":
        pca = model
        Xp = pca.fit_transform(Xs)
        Xr = pca.inverse_transform(Xp)
        score = np.mean((Xs - Xr) ** 2, axis=1)
        pred = _scores_to_binary(score, contamination)
    elif model_name == "PCA_IsolationForest":
        pca, iso = model
        Xp = pca.fit_transform(Xs)
        pred = iso.fit_predict(Xp)
        score = -iso.decision_function(Xp)
    else:
        pred = model.fit_predict(Xs)
        if hasattr(model, "decision_function"):
            score = -model.decision_function(Xs)
        else:
            score = np.zeros(len(Xs))
    return pred, score


def _top_anomaly_indices(score, k):
    if len(score) == 0:
        return set()
    k = min(k, len(score))
    idx = np.argsort(score)[-k:]
    return set(idx.tolist())


def _jaccard(a, b):
    if not a and not b:
        return 1.0
    den = len(a | b)
    if den == 0:
        return 0.0
    return len(a & b) / den


def _bootstrap_stability(model_name, model_factory, Xs, contamination, top_k=3, n_boot=30, random_state=42):
    rng = np.random.default_rng(random_state)
    model_full = model_factory()
    _, score_full = _fit_predict_scores(model_name, model_full, Xs, contamination=contamination)
    top_full = _top_anomaly_indices(score_full, top_k)

    jaccards = []
    n = len(Xs)
    if n == 0:
        return np.nan

    for _ in range(n_boot):
        idx = rng.choice(n, size=n, replace=True)
        Xb = Xs[idx]
        model_b = model_factory()
        _, score_b = _fit_predict_scores(model_name, model_b, Xb, contamination=contamination)
        top_b_local = _top_anomaly_indices(score_b, top_k)
        top_b_original = set(idx[list(top_b_local)].tolist())
        jaccards.append(_jaccard(top_full, top_b_original))

    return float(np.mean(jaccards))


def benchmark_anomaly(df, contamination=0.1):
    d = df.copy()
    X = d[FEATURES].replace([np.inf, -np.inf], np.nan).fillna(0)
    scaler = StandardScaler()
    Xs = scaler.fit_transform(X)

    n_neighbors = max(2, min(20, len(Xs) - 1))

    n_components = max(1, min(3, Xs.shape[1] - 1)) if Xs.shape[1] > 1 else 1

    model_factories = {
        "IsolationForest": lambda: IsolationForest(
            n_estimators=100,
            contamination=contamination,
            random_state=42,
            n_jobs=-1,
        ),
        "LOF": lambda: LocalOutlierFactor(n_neighbors=n_neighbors, contamination=contamination),
        "OneClassSVM": lambda: OneClassSVM(nu=contamination, kernel="rbf", gamma="scale"),
        "PCA_Reconstruction": lambda: PCA(n_components=n_components),
        "PCA_IsolationForest": lambda: (
            PCA(n_components=n_components),
            IsolationForest(
                n_estimators=200,
                contamination=contamination,
                random_state=42,
                n_jobs=-1,
            ),
        ),
    }

    rows = []
    target = contamination
    for name, model_factory in model_factories.items():
        model = model_factory()
        pred, score = _fit_predict_scores(name, model, Xs, contamination=contamination)

        es_anom = pred == -1
        pct = float(es_anom.mean())
        stability = _bootstrap_stability(
            name,
            model_factory,
            Xs,
            contamination=contamination,
            top_k=max(1, int(round(len(Xs) * contamination))),
            n_boot=30,
        )
        rows.append(
            {
                "algoritmo": name,
                "n_anomalias": int(es_anom.sum()),
                "pct_anomalias": pct,
                "score_prom": float(np.mean(score)),
                "score_p95": float(np.percentile(score, 95)),
                "desviacion_target_contamination": abs(pct - target),
                "bootstrap_jaccard_top_anomalias": stability,
            }
        )

    out = pd.DataFrame(rows)
    out["score_general"] = (
        out["bootstrap_jaccard_top_anomalias"].fillna(0) * 0.6
        - out["desviacion_target_contamination"].fillna(1) * 0.4
    )
    return out.sort_values("score_general", ascending=False).reset_index(drop=True)


def benchmark_anomaly_sensitivity(df, contamination_grid=(0.05, 0.10, 0.15)):
    rows = []
    for cont in contamination_grid:
        try:
            res = benchmark_anomaly(df, contamination=float(cont)).copy()
            res["contamination"] = float(cont)
            rows.append(res)
        except Exception:
            continue

    if not rows:
        return pd.DataFrame()

    out = pd.concat(rows, ignore_index=True)
    cols = [
        "algoritmo",
        "contamination",
        "n_anomalias",
        "pct_anomalias",
        "desviacion_target_contamination",
        "bootstrap_jaccard_top_anomalias",
        "score_general",
    ]
    cols = [c for c in cols if c in out.columns]
    return out[cols].sort_values(["score_general", "desviacion_target_contamination"], ascending=[False, True]).reset_index(drop=True)
