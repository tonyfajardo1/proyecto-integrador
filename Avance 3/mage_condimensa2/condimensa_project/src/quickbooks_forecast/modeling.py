from __future__ import annotations

import os
import warnings
from pathlib import Path
from typing import Any

# Evita un warning ruidoso de joblib/loky en macOS al consultar cores fisicos.
os.environ["LOKY_MAX_CPU_COUNT"] = os.environ.get("LOKY_MAX_CPU_COUNT", "1")
warnings.filterwarnings("ignore", message="Could not find the number of physical cores.*")
warnings.filterwarnings("ignore", category=UserWarning, module=r"joblib\.externals\.loky\.backend\.context")

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import TransformedTargetRegressor
from sklearn.ensemble import ExtraTreesRegressor, HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import LinearRegression, Ridge, SGDRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .exogenous import add_exogenous_features
from .features import EXOGENOUS_FEATURE_COLUMNS, FEATURE_COLUMNS, make_features
from .inventory import apply_inventory_adjustments


ML_MODEL_NAMES = {
    "extra_trees",
    "hist_gradient_boosting",
    "hist_gradient_boosting_tuned",
    "linear_regression",
    "random_forest",
    "random_forest_conservative",
    "ridge_regression",
    "sgd_gradient_regression",
}


def _metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    abs_error = np.abs(y_true - y_pred)
    mae = float(abs_error.mean()) if len(y_true) else 0.0
    rmse = float(np.sqrt(np.mean((y_true - y_pred) ** 2))) if len(y_true) else 0.0
    denominator = np.abs(y_true) + np.abs(y_pred)
    smape_terms = np.zeros_like(abs_error)
    nonzero = denominator != 0
    smape_terms[nonzero] = 2 * abs_error[nonzero] / denominator[nonzero]
    smape = float(np.mean(smape_terms)) if len(y_true) else 0.0
    wape = float(abs_error.sum() / y_true.sum()) if y_true.sum() else 0.0
    return {"mae": mae, "rmse": rmse, "smape": smape, "wape": wape}


def _cap_predictions(config: dict[str, Any], eval_df: pd.DataFrame, y_pred: np.ndarray) -> np.ndarray:
    multiplier = float(config["model"].get("prediction_cap_multiplier", 3.0))
    history_cap = eval_df[["expanding_max", "rolling_max_12", "rolling_mean_12"]].max(axis=1)
    cap = np.where(history_cap.gt(0), history_cap.to_numpy() * multiplier, np.inf)
    clean_pred = np.clip(np.nan_to_num(y_pred, nan=0.0, posinf=0.0, neginf=0.0), 0.0, None)
    return np.minimum(clean_pred, cap)


def _evaluate_predictions(
    config: dict[str, Any],
    source: str,
    eval_df: pd.DataFrame,
    predictions: dict[str, np.ndarray],
    split_name: str,
    selected_model_name: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    y_true = eval_df["target_qty"].to_numpy()
    comparison_rows = []
    backtest = eval_df[
        [
            "source_type",
            "product_id",
            "product_name",
            "periodo",
            "target_qty",
            "estado_producto",
            "es_estacional",
            "meses_estacionales",
        ]
    ].copy()

    for model_name, y_pred in predictions.items():
        clean_pred = _cap_predictions(config, eval_df, y_pred)
        metric_values = _metrics(y_true, clean_pred)
        metric_values.update(
            {
                "source": source,
                "model_name": model_name,
                "split": split_name,
                "rows": int(eval_df.shape[0]),
                "period_from": eval_df["periodo"].min().date().isoformat(),
                "period_until": eval_df["periodo"].max().date().isoformat(),
                "selected_for_forecast": model_name == selected_model_name,
            }
        )
        comparison_rows.append(metric_values)
        backtest[f"prediction_{model_name}"] = clean_pred
        backtest[f"abs_error_{model_name}"] = (backtest["target_qty"] - clean_pred).abs()

    backtest["meses_estacionales"] = backtest["meses_estacionales"].fillna("")
    backtest["estado_producto"] = backtest["estado_producto"].fillna("sin_estado")
    backtest["es_estacional"] = backtest["es_estacional"].fillna(False)
    comparison = pd.DataFrame(comparison_rows).sort_values("wape").reset_index(drop=True)
    comparison["rank_wape"] = range(1, comparison.shape[0] + 1)
    return comparison, backtest


def _high_error_products(backtest: pd.DataFrame, source: str, model_name: str) -> pd.DataFrame:
    error_col = f"abs_error_{model_name}"
    pred_col = f"prediction_{model_name}"
    grouped = (
        backtest.groupby(
            ["source_type", "product_id", "product_name", "estado_producto", "es_estacional", "meses_estacionales"],
            as_index=False,
        )
        .agg(
            periodos_evaluados=("periodo", "nunique"),
            cantidad_real_total=("target_qty", "sum"),
            cantidad_predicha_total=(pred_col, "sum"),
            error_absoluto_total=(error_col, "sum"),
            mae_producto=(error_col, "mean"),
        )
    )
    grouped["wape_producto"] = np.where(
        grouped["cantidad_real_total"].gt(0),
        grouped["error_absoluto_total"] / grouped["cantidad_real_total"],
        np.nan,
    )
    grouped["source"] = source
    grouped["prioridad_revision"] = np.where(
        grouped["error_absoluto_total"].rank(ascending=False, pct=True).le(0.2),
        "alta",
        "normal",
    )
    return grouped.sort_values(
        ["error_absoluto_total", "cantidad_real_total"],
        ascending=[False, False],
    ).reset_index(drop=True)


def _load_processed(config: dict[str, Any], source: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    processed_dir = config["resolved_paths"]["processed_dir"]
    monthly = pd.read_csv(processed_dir / f"{source.lower()}_mensual_model.csv", parse_dates=["periodo"])
    monthly["target_qty"] = pd.to_numeric(monthly["target_qty"], errors="coerce").fillna(0.0).clip(lower=0.0)
    products = pd.read_csv(
        processed_dir / f"{source.lower()}_productos_model.csv",
        parse_dates=["primera_actividad", "ultima_actividad", "periodo_referencia", "corte_inactividad"],
    )
    return monthly, products


def _make_hgb_model(
    config: dict[str, Any],
    params: dict[str, Any] | None = None,
) -> TransformedTargetRegressor:
    model_cfg = config["model"]
    params = params or {}
    base_model = HistGradientBoostingRegressor(
        loss="squared_error",
        learning_rate=float(params.get("learning_rate", model_cfg["learning_rate"])),
        max_iter=int(params.get("max_iter", model_cfg["max_iter"])),
        max_leaf_nodes=int(params.get("max_leaf_nodes", 31)),
        min_samples_leaf=int(params.get("min_samples_leaf", 20)),
        l2_regularization=float(params.get("l2_regularization", 0.05)),
        random_state=int(model_cfg["random_state"]),
    )
    return TransformedTargetRegressor(
        regressor=base_model,
        func=np.log1p,
        inverse_func=np.expm1,
        check_inverse=False,
    )


def _make_tree_ensemble_model(config: dict[str, Any], model_name: str) -> TransformedTargetRegressor:
    model_cfg = config["model"]
    params = dict(model_cfg.get(model_name, {}))
    common = {
        "n_estimators": int(params.get("n_estimators", 180)),
        "max_depth": int(params["max_depth"]) if params.get("max_depth") is not None else None,
        "min_samples_leaf": int(params.get("min_samples_leaf", 3)),
        "max_features": float(params.get("max_features", 1.0)),
        "random_state": int(model_cfg["random_state"]),
        "n_jobs": int(params.get("n_jobs", -1)),
    }

    if model_name in {"random_forest", "random_forest_conservative"}:
        estimator = RandomForestRegressor(**common)
    elif model_name == "extra_trees":
        estimator = ExtraTreesRegressor(**common)
    else:
        raise ValueError(f"Modelo de arboles no soportado: {model_name}")

    return TransformedTargetRegressor(
        regressor=estimator,
        func=np.log1p,
        inverse_func=np.expm1,
        check_inverse=False,
    )


def _make_linear_model(config: dict[str, Any], model_name: str) -> TransformedTargetRegressor:
    model_cfg = config["model"]
    if model_name == "linear_regression":
        estimator = LinearRegression()
    elif model_name == "ridge_regression":
        estimator = Ridge(alpha=float(model_cfg.get("ridge_alpha", 1.0)))
    elif model_name == "sgd_gradient_regression":
        estimator = SGDRegressor(
            loss="squared_error",
            penalty="l2",
            alpha=float(model_cfg.get("sgd_alpha", 0.0001)),
            max_iter=int(model_cfg.get("sgd_max_iter", 3000)),
            tol=1e-4,
            random_state=int(model_cfg["random_state"]),
        )
    else:
        raise ValueError(f"Modelo lineal no soportado: {model_name}")

    pipeline = Pipeline(
        [
            ("scaler", StandardScaler()),
            ("model", estimator),
        ]
    )
    return TransformedTargetRegressor(
        regressor=pipeline,
        func=np.log1p,
        inverse_func=np.expm1,
        check_inverse=False,
    )


def _active_feature_columns(features: pd.DataFrame) -> list[str]:
    active_columns = []
    for col in FEATURE_COLUMNS:
        if col not in features.columns:
            continue
        if col in EXOGENOUS_FEATURE_COLUMNS:
            values = pd.to_numeric(features[col], errors="coerce").fillna(0.0)
            if not values.abs().sum() > 0:
                continue
        active_columns.append(col)
    return active_columns


def _fit_predict(
    model: TransformedTargetRegressor,
    train_df: pd.DataFrame,
    eval_df: pd.DataFrame,
    feature_columns: list[str],
) -> np.ndarray:
    model.fit(train_df[feature_columns], train_df["target_qty"])
    return np.clip(model.predict(eval_df[feature_columns]), 0, None)


def _hgb_tuning_candidates(config: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = config["model"].get("hgb_tuning_candidates", [])
    if candidates:
        return [dict(candidate) for candidate in candidates]

    return [
        {"learning_rate": 0.03, "max_iter": 250, "max_leaf_nodes": 15, "min_samples_leaf": 20, "l2_regularization": 0.05},
        {"learning_rate": 0.06, "max_iter": 250, "max_leaf_nodes": 31, "min_samples_leaf": 20, "l2_regularization": 0.05},
        {"learning_rate": 0.10, "max_iter": 200, "max_leaf_nodes": 15, "min_samples_leaf": 30, "l2_regularization": 0.20},
    ]


def _tune_hgb(
    config: dict[str, Any],
    train_df: pd.DataFrame,
    validation_df: pd.DataFrame,
    source: str,
    feature_columns: list[str],
) -> tuple[dict[str, Any], pd.DataFrame]:
    metric = str(config["model"].get("selection_metric", "wape"))
    rows = []

    for idx, params in enumerate(_hgb_tuning_candidates(config), start=1):
        model = _make_hgb_model(config, params)
        pred = _fit_predict(model, train_df, validation_df, feature_columns)
        pred = _cap_predictions(config, validation_df, pred)
        metric_values = _metrics(validation_df["target_qty"].to_numpy(), pred)
        rows.append(
            {
                "source": source,
                "candidate": idx,
                **params,
                **metric_values,
                "rows_train": int(train_df.shape[0]),
                "rows_validation": int(validation_df.shape[0]),
            }
        )

    tuning_results = pd.DataFrame(rows).sort_values(metric).reset_index(drop=True)
    tuning_results["rank_validation"] = range(1, tuning_results.shape[0] + 1)
    param_cols = ["learning_rate", "max_iter", "max_leaf_nodes", "min_samples_leaf", "l2_regularization"]
    best_params = tuning_results.loc[0, param_cols].to_dict()
    return best_params, tuning_results


def _choose_model_from_comparisons(
    config: dict[str, Any],
    validation_comparison: pd.DataFrame,
    test_comparison: pd.DataFrame,
) -> str:
    configured = str(config["model"].get("forecast_model", "best_ml_stable"))
    metric = str(config["model"].get("selection_metric", "wape"))

    if configured in ML_MODEL_NAMES:
        return configured
    if configured in {"best_ml_validation", "best_validation"}:
        validation_ml = validation_comparison[validation_comparison["model_name"].isin(ML_MODEL_NAMES)]
        return str(validation_ml.sort_values(metric).iloc[0]["model_name"])
    if configured in {"best_ml_test", "best_test"}:
        test_ml = test_comparison[test_comparison["model_name"].isin(ML_MODEL_NAMES)]
        return str(test_ml.sort_values(metric).iloc[0]["model_name"])
    if configured != "best_ml_stable":
        raise ValueError(f"Estrategia forecast_model no soportada: {configured}")
    validation_comparison = validation_comparison[validation_comparison["model_name"].isin(ML_MODEL_NAMES)].copy()
    test_comparison = test_comparison[test_comparison["model_name"].isin(ML_MODEL_NAMES)].copy()

    validation = validation_comparison[["model_name", metric, "rank_wape"]].rename(
        columns={metric: "validation_metric", "rank_wape": "validation_rank"}
    )
    test = test_comparison[["model_name", metric, "rank_wape"]].rename(
        columns={metric: "test_metric", "rank_wape": "test_rank"}
    )
    combined = validation.merge(test, on="model_name", how="inner")
    combined["avg_rank"] = (combined["validation_rank"] + combined["test_rank"]) / 2
    combined["avg_metric"] = (combined["validation_metric"] + combined["test_metric"]) / 2
    combined["worst_metric"] = combined[["validation_metric", "test_metric"]].max(axis=1)
    selected = combined.sort_values(["worst_metric", "avg_metric", "avg_rank"]).iloc[0]
    return str(selected["model_name"])


def _candidate_predictions(
    config: dict[str, Any],
    train_df: pd.DataFrame,
    eval_df: pd.DataFrame,
    hgb_tuned_params: dict[str, Any],
    feature_columns: list[str],
) -> dict[str, np.ndarray]:
    return _ml_predictions(config, train_df, eval_df, hgb_tuned_params, feature_columns)


def _ml_predictions(
    config: dict[str, Any],
    train_df: pd.DataFrame,
    eval_df: pd.DataFrame,
    hgb_tuned_params: dict[str, Any],
    feature_columns: list[str],
) -> dict[str, np.ndarray]:
    models = {
        "extra_trees": _make_tree_ensemble_model(config, "extra_trees"),
        "hist_gradient_boosting": _make_hgb_model(config),
        "hist_gradient_boosting_tuned": _make_hgb_model(config, hgb_tuned_params),
        "linear_regression": _make_linear_model(config, "linear_regression"),
        "random_forest": _make_tree_ensemble_model(config, "random_forest"),
        "random_forest_conservative": _make_tree_ensemble_model(config, "random_forest_conservative"),
        "ridge_regression": _make_linear_model(config, "ridge_regression"),
        "sgd_gradient_regression": _make_linear_model(config, "sgd_gradient_regression"),
    }
    return {name: _fit_predict(model, train_df, eval_df, feature_columns) for name, model in models.items()}


def _train_final_ml_models(
    config: dict[str, Any],
    features: pd.DataFrame,
    hgb_tuned_params: dict[str, Any],
    feature_columns: list[str],
) -> dict[str, TransformedTargetRegressor]:
    models = {
        "extra_trees": _make_tree_ensemble_model(config, "extra_trees"),
        "hist_gradient_boosting": _make_hgb_model(config),
        "hist_gradient_boosting_tuned": _make_hgb_model(config, hgb_tuned_params),
        "linear_regression": _make_linear_model(config, "linear_regression"),
        "random_forest": _make_tree_ensemble_model(config, "random_forest"),
        "random_forest_conservative": _make_tree_ensemble_model(config, "random_forest_conservative"),
        "ridge_regression": _make_linear_model(config, "ridge_regression"),
        "sgd_gradient_regression": _make_linear_model(config, "sgd_gradient_regression"),
    }
    for model in models.values():
        model.fit(features[feature_columns], features["target_qty"])
    return models


def train_source(config: dict[str, Any], source: str) -> dict[str, Any]:
    monthly, products = _load_processed(config, source)
    features = make_features(monthly, products)
    feature_columns = _active_feature_columns(features)

    latest_period = features["periodo"].max()
    test_start = latest_period - pd.DateOffset(months=int(config["model"]["test_months"]) - 1)
    pre_test_df = features[features["periodo"].lt(test_start)].copy()
    test_df = features[features["periodo"].ge(test_start)].copy()
    validation_latest = pre_test_df["periodo"].max()
    validation_start = validation_latest - pd.DateOffset(months=int(config["model"].get("validation_months", 3)) - 1)
    train_df = pre_test_df[pre_test_df["periodo"].lt(validation_start)].copy()
    validation_df = pre_test_df[pre_test_df["periodo"].ge(validation_start)].copy()

    if train_df.shape[0] < int(config["model"]["min_rows_to_train"]):
        raise ValueError(f"No hay suficientes filas para entrenar {source}: {train_df.shape[0]}")

    hgb_tuned_params, tuning_results = _tune_hgb(config, train_df, validation_df, source, feature_columns)
    validation_predictions = _candidate_predictions(config, train_df, validation_df, hgb_tuned_params, feature_columns)
    validation_comparison, _ = _evaluate_predictions(
        config,
        source,
        validation_df,
        validation_predictions,
        split_name="validation",
    )
    selection_metric = str(config["model"].get("selection_metric", "wape"))

    test_predictions = _candidate_predictions(config, pre_test_df, test_df, hgb_tuned_params, feature_columns)
    comparison, backtest = _evaluate_predictions(
        config,
        source,
        test_df,
        test_predictions,
        split_name="test",
    )
    selected_model_name = _choose_model_from_comparisons(config, validation_comparison, comparison)
    validation_comparison["selected_for_forecast"] = validation_comparison["model_name"].eq(selected_model_name)
    comparison["selected_for_forecast"] = comparison["model_name"].eq(selected_model_name)
    high_error = _high_error_products(backtest, source, selected_model_name)
    selected_pred = _cap_predictions(config, test_df, test_predictions[selected_model_name])
    metric_values = _metrics(test_df["target_qty"].to_numpy(), selected_pred)
    metric_values.update(
        {
            "source": source,
            "selected_model_name": selected_model_name,
            "selection_metric": selection_metric,
            "train_rows": int(pre_test_df.shape[0]),
            "validation_rows": int(validation_df.shape[0]),
            "test_rows": int(test_df.shape[0]),
            "train_until": pre_test_df["periodo"].max().date().isoformat(),
            "validation_from": validation_start.date().isoformat(),
            "validation_until": validation_latest.date().isoformat(),
            "test_from": test_start.date().isoformat(),
            "test_until": latest_period.date().isoformat(),
        }
    )

    final_models = _train_final_ml_models(config, features, hgb_tuned_params, feature_columns)

    artifact = {
        "source": source,
        "models": final_models,
        "production_model_name": selected_model_name,
        "hgb_tuned_params": hgb_tuned_params,
        "feature_columns": feature_columns,
        "latest_period": latest_period,
        "metric_values": metric_values,
    }

    models_dir = config["resolved_paths"]["models_dir"]
    reports_dir = config["resolved_paths"]["reports_dir"]
    models_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    joblib.dump(artifact, models_dir / f"model_{source.lower()}.joblib")
    pd.DataFrame([metric_values]).to_csv(reports_dir / f"metrics_{source.lower()}.csv", index=False)
    backtest.to_csv(reports_dir / f"backtest_{source.lower()}.csv", index=False, encoding="utf-8")
    validation_comparison.to_csv(
        reports_dir / f"validation_model_comparison_{source.lower()}.csv",
        index=False,
        encoding="utf-8",
    )
    comparison.to_csv(reports_dir / f"model_comparison_{source.lower()}.csv", index=False, encoding="utf-8")
    tuning_results.to_csv(reports_dir / f"hgb_tuning_{source.lower()}.csv", index=False, encoding="utf-8")
    high_error.to_csv(reports_dir / f"high_error_products_{source.lower()}.csv", index=False, encoding="utf-8")
    return artifact


def train_all(config: dict[str, Any]) -> dict[str, Any]:
    artifacts = {"PT": train_source(config, "PT"), "PP": train_source(config, "PP")}
    reports_dir = config["resolved_paths"]["reports_dir"]
    comparisons = [
        pd.read_csv(reports_dir / f"model_comparison_{source.lower()}.csv")
        for source in artifacts
    ]
    validation_comparisons = [
        pd.read_csv(reports_dir / f"validation_model_comparison_{source.lower()}.csv")
        for source in artifacts
    ]
    tuning_results = [
        pd.read_csv(reports_dir / f"hgb_tuning_{source.lower()}.csv")
        for source in artifacts
    ]
    high_errors = [
        pd.read_csv(reports_dir / f"high_error_products_{source.lower()}.csv")
        for source in artifacts
    ]
    pd.concat(comparisons, ignore_index=True).to_csv(
        reports_dir / "model_comparison_all.csv",
        index=False,
        encoding="utf-8",
    )
    pd.concat(validation_comparisons, ignore_index=True).to_csv(
        reports_dir / "validation_model_comparison_all.csv",
        index=False,
        encoding="utf-8",
    )
    pd.concat(tuning_results, ignore_index=True).to_csv(
        reports_dir / "hgb_tuning_all.csv",
        index=False,
        encoding="utf-8",
    )
    pd.concat(high_errors, ignore_index=True).to_csv(
        reports_dir / "high_error_products_all.csv",
        index=False,
        encoding="utf-8",
    )
    return artifacts


def _future_periods(latest_period: pd.Timestamp, horizon: int) -> list[pd.Timestamp]:
    return [latest_period + pd.DateOffset(months=i) for i in range(1, horizon + 1)]


def _selected_forecast_model(config: dict[str, Any], source: str) -> str:
    configured = str(config["model"].get("forecast_model", "best_ml_stable"))
    reports_dir = config["resolved_paths"]["reports_dir"]
    if configured in ML_MODEL_NAMES:
        return configured

    comparison_path = reports_dir / f"model_comparison_{source.lower()}.csv"
    if not comparison_path.exists():
        return "hist_gradient_boosting_tuned"

    metric = str(config["model"].get("selection_metric", "wape"))
    test_comparison = pd.read_csv(comparison_path)

    if configured in {"best_ml_test", "best_test"}:
        test_ml = test_comparison[test_comparison["model_name"].isin(ML_MODEL_NAMES)]
        return str(test_ml.sort_values(metric).iloc[0]["model_name"])
    if configured in {"best_ml_validation", "best_validation"}:
        validation_path = reports_dir / f"validation_model_comparison_{source.lower()}.csv"
        if not validation_path.exists():
            test_ml = test_comparison[test_comparison["model_name"].isin(ML_MODEL_NAMES)]
            return str(test_ml.sort_values(metric).iloc[0]["model_name"])
        validation_comparison = pd.read_csv(validation_path)
        validation_ml = validation_comparison[validation_comparison["model_name"].isin(ML_MODEL_NAMES)]
        return str(validation_ml.sort_values(metric).iloc[0]["model_name"])
    if configured == "best_ml_stable":
        validation_path = reports_dir / f"validation_model_comparison_{source.lower()}.csv"
        if not validation_path.exists():
            test_ml = test_comparison[test_comparison["model_name"].isin(ML_MODEL_NAMES)]
            return str(test_ml.sort_values(metric).iloc[0]["model_name"])
        validation_comparison = pd.read_csv(validation_path)
        return _choose_model_from_comparisons(config, validation_comparison, test_comparison)

    raise ValueError(f"Estrategia forecast_model no soportada: {configured}")


def _predict_future_values(
    config: dict[str, Any],
    selected_model: str,
    models: dict[str, TransformedTargetRegressor],
    future_features: pd.DataFrame,
    feature_columns: list[str],
) -> np.ndarray:
    if selected_model in ML_MODEL_NAMES:
        model = models[selected_model]
        return np.clip(model.predict(future_features[feature_columns]), 0, None)
    raise ValueError(f"Modelo de forecast no soportado: {selected_model}")


def _add_decision_fields(
    config: dict[str, Any],
    source: str,
    predictions_df: pd.DataFrame,
    selected_model: str,
) -> pd.DataFrame:
    reports_dir = config["resolved_paths"]["reports_dir"]
    comparison = pd.read_csv(reports_dir / f"model_comparison_{source.lower()}.csv")
    selected_metric = comparison[comparison["model_name"].eq(selected_model)]
    model_wape = float(selected_metric["wape"].iloc[0]) if not selected_metric.empty else float(comparison["wape"].min())

    high_error_path = reports_dir / f"high_error_products_{source.lower()}.csv"
    if high_error_path.exists():
        high_error = pd.read_csv(high_error_path)
        risk_cols = [
            "product_id",
            "error_absoluto_total",
            "wape_producto",
            "prioridad_revision",
        ]
        predictions_df = predictions_df.merge(high_error[risk_cols], on="product_id", how="left")
    else:
        predictions_df["error_absoluto_total"] = np.nan
        predictions_df["wape_producto"] = np.nan
        predictions_df["prioridad_revision"] = "normal"

    predictions_df["wape_producto"] = predictions_df["wape_producto"].fillna(model_wape)
    predictions_df["prioridad_revision"] = predictions_df["prioridad_revision"].fillna("normal")
    predictions_df["error_relativo_estimado"] = predictions_df["wape_producto"].clip(lower=0.0, upper=2.0)
    predictions_df["prediccion_min"] = (
        predictions_df["cantidad_predicha"] * (1 - predictions_df["error_relativo_estimado"])
    ).clip(lower=0.0)
    predictions_df["prediccion_max"] = predictions_df["cantidad_predicha"] * (
        1 + predictions_df["error_relativo_estimado"]
    )
    predictions_df["confianza_prediccion"] = np.select(
        [
            predictions_df["estado_producto"].eq("inactivo"),
            predictions_df["error_relativo_estimado"].le(0.30),
            predictions_df["error_relativo_estimado"].le(0.60),
        ],
        ["no_aplica", "alta", "media"],
        default="baja",
    )
    predictions_df["requiere_revision"] = (
        predictions_df["confianza_prediccion"].eq("baja")
        | predictions_df["prioridad_revision"].eq("alta")
        | predictions_df["es_estacional"].fillna(False).astype(bool)
    ) & predictions_df["estado_producto"].ne("inactivo")
    predictions_df["cantidad_sugerida_sin_inventario"] = predictions_df["cantidad_predicha"]
    predictions_df["recomendacion_decision"] = np.select(
        [
            predictions_df["estado_producto"].eq("inactivo"),
            predictions_df["requiere_revision"],
        ],
        [
            "no producir por inactividad",
            "revisar antes de ordenar",
        ],
        default="usar como cantidad sugerida",
    )

    for col in [
        "cantidad_predicha",
        "prediccion_min",
        "prediccion_max",
        "cantidad_sugerida_sin_inventario",
        "error_relativo_estimado",
    ]:
        predictions_df[col] = predictions_df[col].round(2)
    return predictions_df


def predict_source(config: dict[str, Any], source: str) -> pd.DataFrame:
    monthly, products = _load_processed(config, source)
    artifact_path = config["resolved_paths"]["models_dir"] / f"model_{source.lower()}.joblib"
    artifact = joblib.load(artifact_path)
    models = artifact.get("models")
    if models is None and "model" in artifact:
        models = {"hist_gradient_boosting": artifact["model"]}
    feature_columns = artifact["feature_columns"]
    selected_model = _selected_forecast_model(config, source)
    horizon = int(config["dataset"]["forecast_horizon_months"])

    history_cols = ["source_type", "product_id", "product_name", "periodo", "target_qty"]
    optional_cols = [
        "estado_producto",
        "es_estacional",
        "share_top_3_meses",
        "meses_estacionales_num",
        "meses_estacionales",
        *EXOGENOUS_FEATURE_COLUMNS,
    ]
    history_cols += [col for col in optional_cols if col in monthly.columns]
    history = monthly[history_cols].copy()
    history["periodo"] = pd.to_datetime(history["periodo"])

    prediction_rows = []
    latest_period = history["periodo"].max()
    for next_period in _future_periods(latest_period, horizon):
        future = products[["source_type", "product_id", "product_name"]].copy()
        future["periodo"] = next_period
        future["target_qty"] = np.nan
        future = add_exogenous_features(config, future, source)
        extended = pd.concat([history, future], ignore_index=True, sort=False)
        feature_frame = make_features(extended, products)
        future_features = feature_frame[feature_frame["periodo"].eq(next_period)].copy()

        predictions = _predict_future_values(config, selected_model, models, future_features, feature_columns)
        predictions = _cap_predictions(config, future_features, predictions)
        future_features["cantidad_predicha"] = predictions
        inactive_mask = future_features["estado_producto"].eq("inactivo")
        future_features.loc[inactive_mask, "cantidad_predicha"] = 0.0
        future_features["modelo_usado"] = np.where(
            inactive_mask,
            "inactive_zero_rule",
            selected_model,
        )
        future_features["ultimo_periodo_entrenamiento"] = latest_period
        future_features["anio"] = future_features["periodo"].dt.year
        future_features["mes"] = future_features["periodo"].dt.month

        output_cols = [
            "source_type",
            "product_id",
            "product_name",
            "periodo",
            "anio",
            "mes",
            "cantidad_predicha",
            "estado_producto",
            "es_estacional",
            "meses_estacionales",
            "ultima_actividad",
            "modelo_usado",
            "ultimo_periodo_entrenamiento",
        ]
        future_output = future_features.merge(
            products[["product_id", "ultima_actividad"]],
            on="product_id",
            how="left",
        )
        prediction_rows.append(future_output[output_cols])

        future_history = future_features[history.columns.intersection(future_features.columns)].copy()
        future_history["target_qty"] = future_features["cantidad_predicha"].to_numpy()
        history = pd.concat([history, future_history[history.columns]], ignore_index=True, sort=False)

    predictions_df = pd.concat(prediction_rows, ignore_index=True)
    predictions_df["cantidad_predicha"] = predictions_df["cantidad_predicha"].round(2)
    predictions_df = _add_decision_fields(config, source, predictions_df, selected_model)
    predictions_df = apply_inventory_adjustments(config, source, predictions_df)
    reports_dir = config["resolved_paths"]["reports_dir"]
    predictions_df.to_csv(reports_dir / f"predicciones_{source.lower()}.csv", index=False, encoding="utf-8")
    return predictions_df


def predict_all(config: dict[str, Any]) -> dict[str, pd.DataFrame]:
    reports_dir = config["resolved_paths"]["reports_dir"]
    pt = predict_source(config, "PT")
    pp = predict_source(config, "PP")
    workbook_path = reports_dir / "predicciones_quickbooks.xlsx"
    with pd.ExcelWriter(workbook_path) as writer:
        pt.to_excel(writer, sheet_name="PT", index=False)
        pp.to_excel(writer, sheet_name="PP", index=False)
    return {"PT": pt, "PP": pp}
