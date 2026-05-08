import numpy as np
import pandas as pd


def z_score_from_alpha(alpha: float) -> float:
    mapping = {
        0.80: 0.84,
        0.85: 1.04,
        0.90: 1.28,
        0.95: 1.65,
        0.98: 2.05,
        0.99: 2.33,
    }
    a = float(alpha)
    if a in mapping:
        return mapping[a]
    keys = np.array(sorted(mapping.keys()))
    idx = (np.abs(keys - a)).argmin()
    return mapping[float(keys[idx])]


def build_temporal_features(df: pd.DataFrame, alpha: float = 0.95, lead_time: float = 1.0) -> pd.DataFrame:
    d = df.copy().sort_values(["producto", "periodo"]).reset_index(drop=True)
    grp = d.groupby("producto")

    d["lag_1"] = grp["qty_fabricada"].shift(1)
    d["lag_2"] = grp["qty_fabricada"].shift(2)
    d["lag_3"] = grp["qty_fabricada"].shift(3)

    d["rolling_mean_3"] = grp["qty_fabricada"].shift(1).rolling(3, min_periods=1).mean()
    d["rolling_std_3"] = grp["qty_fabricada"].shift(1).rolling(3, min_periods=1).std().fillna(0)
    d["delta_1"] = d["lag_1"] - d["lag_2"]

    d["qty_planificada_lag_1"] = grp["qty_planificada"].shift(1)
    d["n_ordenes_lag_1"] = grp["n_ordenes"].shift(1)

    d["target_t1"] = grp["qty_fabricada"].shift(-1)
    d["next_period"] = grp["periodo"].shift(-1)

    d["mes_num"] = d["periodo"].dt.month
    d["anio_num"] = d["periodo"].dt.year
    d["producto_id"] = pd.factorize(d["producto"])[0]

    z = z_score_from_alpha(alpha)
    d["stock_respaldo"] = z * d["rolling_std_3"].fillna(0) * np.sqrt(max(float(lead_time), 1e-6))

    d = d.dropna(subset=["lag_1", "target_t1", "next_period"]).copy()
    return d


def feature_columns():
    return [
        "producto_id",
        "anio_num",
        "mes_num",
        "lag_1",
        "lag_2",
        "lag_3",
        "rolling_mean_3",
        "rolling_std_3",
        "delta_1",
        "qty_planificada_lag_1",
        "n_ordenes_lag_1",
    ]
