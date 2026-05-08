import warnings

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


def baseline_lag1_predict(eval_df: pd.DataFrame):
    return eval_df["lag_1"].fillna(0).astype(float).to_numpy()


def build_candidates(random_state=42):
    return {
        "LinearRegression": Pipeline(
            [
                ("scaler", StandardScaler()),
                ("model", LinearRegression()),
            ]
        ),
        "RandomForest": RandomForestRegressor(
            n_estimators=500,
            random_state=random_state,
            n_jobs=-1,
            min_samples_leaf=2,
        ),
        "ExtraTrees": ExtraTreesRegressor(
            n_estimators=500,
            random_state=random_state,
            n_jobs=-1,
            min_samples_leaf=1,
        ),
    }


def fit_predict_tabular(model, train_df: pd.DataFrame, eval_df: pd.DataFrame, features, impute_strategy="zero"):
    X_train = train_df[features].replace([np.inf, -np.inf], np.nan)
    y_train = train_df["target_t1"].astype(float)
    X_eval = eval_df[features].replace([np.inf, -np.inf], np.nan)

    strategy = str(impute_strategy).lower().strip()
    if strategy == "zero":
        X_train_fit = X_train.fillna(0)
        X_eval_fit = X_eval.fillna(0)
    else:
        imp = SimpleImputer(strategy="median")
        X_train_fit = imp.fit_transform(X_train)
        X_eval_fit = imp.transform(X_eval)

    model.fit(X_train_fit, y_train)
    pred = np.maximum(model.predict(X_eval_fit), 0)
    return pred


def fit_predict_prophet(train_base: pd.DataFrame, eval_df: pd.DataFrame, max_products=150):
    try:
        from prophet import Prophet
    except Exception:
        warnings.warn("Prophet no instalado; se omite candidato Prophet.")
        return None

    pred_list = []
    idx_list = []

    prods = eval_df["producto"].dropna().astype(str).unique().tolist()
    prods = prods[: max(int(max_products), 0)]

    for prod in prods:
        sub_eval = eval_df[eval_df["producto"] == prod]
        sub_train = train_base[train_base["producto"] == prod].copy()
        if len(sub_train) < 4:
            pred_vals = sub_eval["lag_1"].fillna(0).astype(float).to_numpy()
            pred_list.append(pred_vals)
            idx_list.extend(sub_eval.index.tolist())
            continue

        sub_train = sub_train.sort_values("periodo")
        fit_df = sub_train[["periodo", "qty_fabricada"]].rename(columns={"periodo": "ds", "qty_fabricada": "y"})

        m = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=False,
            daily_seasonality=False,
            seasonality_mode="additive",
        )
        m.fit(fit_df)

        future = pd.DataFrame({"ds": pd.to_datetime(sub_eval["next_period"])})
        fcst = m.predict(future)
        pred_vals = np.maximum(fcst["yhat"].to_numpy(), 0)

        pred_list.append(pred_vals)
        idx_list.extend(sub_eval.index.tolist())

    out = pd.Series(index=idx_list, data=np.concatenate(pred_list) if idx_list else np.array([], dtype=float))
    out = out.reindex(eval_df.index)
    return out.fillna(eval_df["lag_1"].fillna(0)).to_numpy()


def blend_predictions(pred_map: dict, weights=None):
    required = ["LinearRegression", "RandomForest", "ExtraTrees"]
    if any(k not in pred_map for k in required):
        return None

    if weights is None:
        weights = {"LinearRegression": 0.2, "RandomForest": 0.4, "ExtraTrees": 0.4}

    blend = np.zeros_like(pred_map[required[0]], dtype=float)
    for k in required:
        blend += float(weights.get(k, 0.0)) * pred_map[k]
    return np.maximum(blend, 0)
