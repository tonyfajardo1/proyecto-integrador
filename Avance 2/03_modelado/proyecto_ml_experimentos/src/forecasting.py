import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor, GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import ElasticNet, LinearRegression, Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .evaluation import regression_metrics, temporal_split_by_period


def _build_features(df):
    d = df.copy().sort_values(["producto", "periodo"]).reset_index(drop=True)
    grp = d.groupby("producto")

    d["lag_1"] = grp["qty_fabricada"].shift(1)
    d["lag_2"] = grp["qty_fabricada"].shift(2)
    d["lag_3"] = grp["qty_fabricada"].shift(3)
    d["rolling_3"] = grp["qty_fabricada"].shift(1).rolling(3, min_periods=1).mean()
    d["target_t1"] = grp["qty_fabricada"].shift(-1)
    d["mes_num"] = d["periodo"].dt.month
    d["anio_num"] = d["periodo"].dt.year
    d["producto_id"] = pd.factorize(d["producto"])[0]

    d = d.dropna(subset=["lag_1", "target_t1"]).copy()
    return d


def _naive_metrics(eval_df):
    y_true = eval_df["target_t1"].astype(float)
    y_pred = eval_df["lag_1"].fillna(0).astype(float)
    return regression_metrics(y_true, y_pred)


def _evaluate_model(name, model, train_df, eval_df, features):
    X_train = train_df[features].replace([np.inf, -np.inf], np.nan).fillna(0)
    y_train = train_df["target_t1"].astype(float)

    X_eval = eval_df[features].replace([np.inf, -np.inf], np.nan).fillna(0)
    y_eval = eval_df["target_t1"].astype(float)

    model.fit(X_train, y_train)
    y_pred = np.maximum(model.predict(X_eval), 0)
    m = regression_metrics(y_eval, y_pred)
    return {"modelo": name, **m}


def _evaluate_on_split(model, train_df, eval_df, features):
    X_train = train_df[features].replace([np.inf, -np.inf], np.nan).fillna(0)
    y_train = train_df["target_t1"].astype(float)
    X_eval = eval_df[features].replace([np.inf, -np.inf], np.nan).fillna(0)
    y_eval = eval_df["target_t1"].astype(float)

    model.fit(X_train, y_train)
    pred_train = np.maximum(model.predict(X_train), 0)
    pred_eval = np.maximum(model.predict(X_eval), 0)

    return regression_metrics(y_train, pred_train), regression_metrics(y_eval, pred_eval)


def _iter_forecasting_candidates(random_state=42):
    tree_candidates = [
        (
            "RandomForest",
            RandomForestRegressor(
                n_estimators=300,
                random_state=random_state,
                n_jobs=-1,
                min_samples_leaf=2,
            ),
        ),
        (
            "RandomForest",
            RandomForestRegressor(
                n_estimators=500,
                random_state=random_state,
                n_jobs=-1,
                min_samples_leaf=2,
            ),
        ),
        (
            "ExtraTrees",
            ExtraTreesRegressor(
                n_estimators=300,
                random_state=random_state,
                n_jobs=-1,
                min_samples_leaf=2,
            ),
        ),
        (
            "ExtraTrees",
            ExtraTreesRegressor(
                n_estimators=500,
                random_state=random_state,
                n_jobs=-1,
                min_samples_leaf=1,
            ),
        ),
        (
            "GradientBoosting",
            GradientBoostingRegressor(random_state=random_state),
        ),
        (
            "GradientBoosting",
            GradientBoostingRegressor(
                random_state=random_state,
                learning_rate=0.05,
                n_estimators=400,
            ),
        ),
    ]

    linear_candidates = [
        (
            "LinearRegression",
            Pipeline(
                [
                    ("scaler", StandardScaler()),
                    ("model", LinearRegression()),
                ]
            ),
        ),
    ]

    for alpha in [0.1, 1.0, 10.0, 25.0]:
        linear_candidates.append(
            (
                "Ridge",
                Pipeline(
                    [
                        ("scaler", StandardScaler()),
                        ("model", Ridge(alpha=alpha, random_state=random_state)),
                    ]
                ),
            )
        )

    for alpha in [0.001, 0.01, 0.1, 1.0]:
        for l1_ratio in [0.2, 0.5, 0.8]:
            linear_candidates.append(
                (
                    "ElasticNet",
                    Pipeline(
                        [
                            ("scaler", StandardScaler()),
                            (
                                "model",
                                ElasticNet(
                                    alpha=alpha,
                                    l1_ratio=l1_ratio,
                                    random_state=random_state,
                                    max_iter=10000,
                                ),
                            ),
                        ]
                    ),
                )
            )

    return tree_candidates + linear_candidates


def _build_feature_set():
    return [
        "producto_id",
        "anio_num",
        "mes_num",
        "lag_1",
        "lag_2",
        "lag_3",
        "rolling_3",
        "qty_planificada",
        "n_ordenes",
    ]


def benchmark_forecasting(df):
    d = _build_features(df)
    features = _build_feature_set()
    train_df, val_df, test_df, split_info = temporal_split_by_period(d, "periodo", train_frac=0.6, val_frac=0.2)

    candidates = {}
    for model_name, model in _iter_forecasting_candidates(random_state=42):
        candidates.setdefault(model_name, []).append(model)

    val_rows = [{"modelo": "Baseline_Lag1", **_naive_metrics(val_df)}]
    best_models = {}
    for name, model_list in candidates.items():
        best_row = None
        best_model = None
        for model in model_list:
            row = _evaluate_model(name, model, train_df, val_df, features)
            row["config"] = str(model)
            if best_row is None or row["WAPE"] < best_row["WAPE"]:
                best_row = row
                best_model = model
        if best_row is None or best_model is None:
            continue
        best_models[name] = best_model
        val_rows.append(best_row)

    val_table = pd.DataFrame(val_rows).sort_values("WAPE").reset_index(drop=True)
    val_baseline_wape = float(val_table.loc[val_table["modelo"] == "Baseline_Lag1", "WAPE"].iloc[0])
    val_table["split"] = "validation"
    val_table["mejora_vs_baseline_wape"] = val_baseline_wape - val_table["WAPE"]

    train_val_df = pd.concat([train_df, val_df], ignore_index=True)
    test_rows = [{"modelo": "Baseline_Lag1", **_naive_metrics(test_df)}]
    for name, model in best_models.items():
        row = _evaluate_model(name, model, train_val_df, test_df, features)
        row["config"] = str(model)
        test_rows.append(row)

    test_table = pd.DataFrame(test_rows).sort_values("WAPE").reset_index(drop=True)
    test_baseline_wape = float(test_table.loc[test_table["modelo"] == "Baseline_Lag1", "WAPE"].iloc[0])
    test_table["split"] = "test"
    test_table["mejora_vs_baseline_wape"] = test_baseline_wape - test_table["WAPE"]

    out = pd.concat([val_table, test_table], ignore_index=True)
    out["n_train"] = len(train_df)
    out["n_val"] = len(val_df)
    out["n_test"] = len(test_df)
    out["periodos_train"] = str(split_info["train_periods"])
    out["periodos_val"] = str(split_info["val_periods"])
    out["periodos_test"] = str(split_info["test_periods"])
    return out


def benchmark_forecasting_sensitivity(df):
    d = _build_features(df)
    features = _build_feature_set()
    train_df, val_df, test_df, split_info = temporal_split_by_period(d, "periodo", train_frac=0.6, val_frac=0.2)

    baseline_train = _naive_metrics(train_df)
    baseline_val = _naive_metrics(val_df)
    baseline_test = _naive_metrics(test_df)

    rows = [
        {
            "modelo": "Baseline_Lag1",
            "config": "lag_1",
            "MAE_train": baseline_train["MAE"],
            "RMSE_train": baseline_train["RMSE"],
            "WAPE_train": baseline_train["WAPE"],
            "MAE_val": baseline_val["MAE"],
            "RMSE_val": baseline_val["RMSE"],
            "WAPE_val": baseline_val["WAPE"],
            "MAE_test": baseline_test["MAE"],
            "RMSE_test": baseline_test["RMSE"],
            "WAPE_test": baseline_test["WAPE"],
        }
    ]

    train_val_df = pd.concat([train_df, val_df], ignore_index=True)
    for name, model in _iter_forecasting_candidates(random_state=42):
        train_m, val_m = _evaluate_on_split(model, train_df, val_df, features)
        _, test_m = _evaluate_on_split(model, train_val_df, test_df, features)
        rows.append(
            {
                "modelo": name,
                "config": str(model),
                "MAE_train": train_m["MAE"],
                "RMSE_train": train_m["RMSE"],
                "WAPE_train": train_m["WAPE"],
                "MAE_val": val_m["MAE"],
                "RMSE_val": val_m["RMSE"],
                "WAPE_val": val_m["WAPE"],
                "MAE_test": test_m["MAE"],
                "RMSE_test": test_m["RMSE"],
                "WAPE_test": test_m["WAPE"],
            }
        )

    out = pd.DataFrame(rows)
    base_val = float(out.loc[out["modelo"] == "Baseline_Lag1", "WAPE_val"].iloc[0])
    base_test = float(out.loc[out["modelo"] == "Baseline_Lag1", "WAPE_test"].iloc[0])

    out["gap_wape_train_val"] = out["WAPE_val"] - out["WAPE_train"]
    out["gap_wape_val_test"] = out["WAPE_test"] - out["WAPE_val"]
    out["mejora_vs_baseline_val_wape"] = base_val - out["WAPE_val"]
    out["mejora_vs_baseline_test_wape"] = base_test - out["WAPE_test"]
    out["n_train"] = len(train_df)
    out["n_val"] = len(val_df)
    out["n_test"] = len(test_df)
    out["periodos_train"] = str(split_info["train_periods"])
    out["periodos_val"] = str(split_info["val_periods"])
    out["periodos_test"] = str(split_info["test_periods"])

    return out.sort_values(["WAPE_val", "WAPE_test"], ascending=[True, True]).reset_index(drop=True)
