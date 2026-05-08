from pathlib import Path

import numpy as np
import pandas as pd

from .dataset import load_monthly_production_dataset
from .evaluation import psi, regression_metrics, temporal_split_by_period
from .features import build_temporal_features, feature_columns
from .models import (
    baseline_lag1_predict,
    blend_predictions,
    build_candidates,
    fit_predict_prophet,
    fit_predict_tabular,
)
from .wrangling import prepare_modeling_table


def _try_mlflow():
    try:
        import mlflow  # type: ignore

        return mlflow
    except Exception:
        return None


def _eval_split(y_true, y_pred):
    return regression_metrics(y_true.astype(float), np.maximum(np.asarray(y_pred, dtype=float), 0))


def run_forecasting_thesis(
    alpha=0.95,
    lead_time=1.0,
    use_mlflow=False,
    max_prophet_products=150,
    source="dwh",
    wrangling_mode="zero",
    model_imputer_strategy="zero",
):
    raw = load_monthly_production_dataset(source=source, fallback_quickbooks=True)
    wrangled, wrangling_report = prepare_modeling_table(
        raw,
        min_periods_product=4,
        imputation_mode=wrangling_mode,
    )
    feat = build_temporal_features(wrangled, alpha=alpha, lead_time=lead_time)
    features = feature_columns()

    train_df, val_df, test_df, split_info = temporal_split_by_period(
        feat, period_col="periodo", train_frac=0.6, val_frac=0.2
    )
    train_val_df = pd.concat([train_df, val_df], ignore_index=True)

    train_base = wrangled[wrangled["periodo"].isin(split_info["train_periods"])].copy()
    train_val_base = wrangled[wrangled["periodo"].isin(split_info["train_periods"] + split_info["val_periods"])].copy()

    rows = []
    pred_test_map = {}

    # Baseline
    base_val_pred = baseline_lag1_predict(val_df)
    base_test_pred = baseline_lag1_predict(test_df)
    base_train_pred = baseline_lag1_predict(train_df)

    base_train_m = _eval_split(train_df["target_t1"], base_train_pred)
    base_val_m = _eval_split(val_df["target_t1"], base_val_pred)
    base_test_m = _eval_split(test_df["target_t1"], base_test_pred)

    rows.append(
        {
            "modelo": "Baseline_Lag1",
            "MAE_train": base_train_m["MAE"],
            "RMSE_train": base_train_m["RMSE"],
            "WAPE_train": base_train_m["WAPE"],
            "MAE_val": base_val_m["MAE"],
            "RMSE_val": base_val_m["RMSE"],
            "WAPE_val": base_val_m["WAPE"],
            "MAE_test": base_test_m["MAE"],
            "RMSE_test": base_test_m["RMSE"],
            "WAPE_test": base_test_m["WAPE"],
        }
    )

    pred_test_map["Baseline_Lag1"] = base_test_pred

    # Tabular candidates
    candidates = build_candidates(random_state=42)
    for name, model in candidates.items():
        pred_train = fit_predict_tabular(model, train_df, train_df, features, impute_strategy=model_imputer_strategy)
        pred_val = fit_predict_tabular(model, train_df, val_df, features, impute_strategy=model_imputer_strategy)
        pred_test = fit_predict_tabular(model, train_val_df, test_df, features, impute_strategy=model_imputer_strategy)

        m_train = _eval_split(train_df["target_t1"], pred_train)
        m_val = _eval_split(val_df["target_t1"], pred_val)
        m_test = _eval_split(test_df["target_t1"], pred_test)

        rows.append(
            {
                "modelo": name,
                "MAE_train": m_train["MAE"],
                "RMSE_train": m_train["RMSE"],
                "WAPE_train": m_train["WAPE"],
                "MAE_val": m_val["MAE"],
                "RMSE_val": m_val["RMSE"],
                "WAPE_val": m_val["WAPE"],
                "MAE_test": m_test["MAE"],
                "RMSE_test": m_test["RMSE"],
                "WAPE_test": m_test["WAPE"],
            }
        )
        pred_test_map[name] = pred_test

    # Prophet optional
    pred_val_prophet = fit_predict_prophet(train_base, val_df, max_products=max_prophet_products)
    pred_test_prophet = fit_predict_prophet(train_val_base, test_df, max_products=max_prophet_products)
    if pred_val_prophet is not None and pred_test_prophet is not None:
        pred_train_prophet = baseline_lag1_predict(train_df)
        m_train = _eval_split(train_df["target_t1"], pred_train_prophet)
        m_val = _eval_split(val_df["target_t1"], pred_val_prophet)
        m_test = _eval_split(test_df["target_t1"], pred_test_prophet)
        rows.append(
            {
                "modelo": "Prophet",
                "MAE_train": m_train["MAE"],
                "RMSE_train": m_train["RMSE"],
                "WAPE_train": m_train["WAPE"],
                "MAE_val": m_val["MAE"],
                "RMSE_val": m_val["RMSE"],
                "WAPE_val": m_val["WAPE"],
                "MAE_test": m_test["MAE"],
                "RMSE_test": m_test["RMSE"],
                "WAPE_test": m_test["WAPE"],
            }
        )
        pred_test_map["Prophet"] = pred_test_prophet

    # Ensemble
    ensemble_test = blend_predictions(pred_test_map)
    if ensemble_test is not None:
        ensemble_val = blend_predictions(
            {
                "LinearRegression": fit_predict_tabular(candidates["LinearRegression"], train_df, val_df, features, impute_strategy=model_imputer_strategy),
                "RandomForest": fit_predict_tabular(candidates["RandomForest"], train_df, val_df, features, impute_strategy=model_imputer_strategy),
                "ExtraTrees": fit_predict_tabular(candidates["ExtraTrees"], train_df, val_df, features, impute_strategy=model_imputer_strategy),
            }
        )
        ensemble_train = blend_predictions(
            {
                "LinearRegression": fit_predict_tabular(candidates["LinearRegression"], train_df, train_df, features, impute_strategy=model_imputer_strategy),
                "RandomForest": fit_predict_tabular(candidates["RandomForest"], train_df, train_df, features, impute_strategy=model_imputer_strategy),
                "ExtraTrees": fit_predict_tabular(candidates["ExtraTrees"], train_df, train_df, features, impute_strategy=model_imputer_strategy),
            }
        )

        m_train = _eval_split(train_df["target_t1"], ensemble_train)
        m_val = _eval_split(val_df["target_t1"], ensemble_val)
        m_test = _eval_split(test_df["target_t1"], ensemble_test)

        rows.append(
            {
                "modelo": "Ensemble_RF_ET_LR",
                "MAE_train": m_train["MAE"],
                "RMSE_train": m_train["RMSE"],
                "WAPE_train": m_train["WAPE"],
                "MAE_val": m_val["MAE"],
                "RMSE_val": m_val["RMSE"],
                "WAPE_val": m_val["WAPE"],
                "MAE_test": m_test["MAE"],
                "RMSE_test": m_test["RMSE"],
                "WAPE_test": m_test["WAPE"],
            }
        )
        pred_test_map["Ensemble_RF_ET_LR"] = ensemble_test

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
    out = out.sort_values(["WAPE_val", "WAPE_test"], ascending=[True, True]).reset_index(drop=True)

    winner = out.iloc[0]["modelo"]
    pred_test = np.maximum(pred_test_map[winner], 0)

    pred_table = test_df[["producto", "periodo", "next_period", "target_t1", "stock_respaldo"]].copy()
    pred_table["modelo_ganador"] = winner
    pred_table["pronostico_qty"] = pred_test
    pred_table["qty_recomendada"] = np.ceil(pred_table["pronostico_qty"] + pred_table["stock_respaldo"].fillna(0))

    # Drift log (PSI)
    drift_rows = []
    for col in ["lag_1", "lag_2", "lag_3", "rolling_mean_3", "rolling_std_3", "qty_planificada_lag_1", "n_ordenes_lag_1"]:
        drift_rows.append(
            {
                "feature": col,
                "psi_train_vs_test": psi(train_df[col], test_df[col]),
            }
        )
    drift_log = pd.DataFrame(drift_rows).sort_values("psi_train_vs_test", ascending=False).reset_index(drop=True)

    if use_mlflow:
        mlflow = _try_mlflow()
        if mlflow is not None:
            tracking_dir = Path(__file__).resolve().parents[1] / "mlruns"
            mlflow.set_tracking_uri(f"file:///{tracking_dir.as_posix()}")
            mlflow.set_experiment("tesis_forecasting_quickbooks")
            with mlflow.start_run(run_name="benchmark_forecasting_thesis"):
                mlflow.log_param("alpha", alpha)
                mlflow.log_param("lead_time", lead_time)
                mlflow.log_param("max_prophet_products", max_prophet_products)
                mlflow.log_param("source", source)
                mlflow.log_param("wrangling_mode", wrangling_mode)
                mlflow.log_param("model_imputer_strategy", model_imputer_strategy)
                mlflow.log_param("winner", winner)
                mlflow.log_metric("wrangled_rows", float(len(wrangled)))
                mlflow.log_metric("wrangled_products", float(wrangled["producto"].nunique()))

                best = out.iloc[0]
                mlflow.log_metric("best_wape_val", float(best["WAPE_val"]))
                mlflow.log_metric("best_wape_test", float(best["WAPE_test"]))
                mlflow.log_metric("best_gap_wape_train_val", float(best["gap_wape_train_val"]))
                mlflow.log_metric("best_gap_wape_val_test", float(best["gap_wape_val_test"]))

                artifacts = Path(__file__).resolve().parents[1] / "artifacts"
                artifacts.mkdir(exist_ok=True)
                out.to_csv(artifacts / "benchmark_forecasting_thesis.csv", index=False)
                pred_table.to_csv(artifacts / "predicciones_ganador.csv", index=False)
                drift_log.to_csv(artifacts / "drift_log.csv", index=False)
                wrangled.to_csv(artifacts / "dataset_wrangled_forecasting.csv", index=False)
                wrangling_report.to_csv(artifacts / "wrangling_report.csv", index=False)
                mlflow.log_artifact(str(artifacts / "benchmark_forecasting_thesis.csv"))
                mlflow.log_artifact(str(artifacts / "predicciones_ganador.csv"))
                mlflow.log_artifact(str(artifacts / "drift_log.csv"))
                mlflow.log_artifact(str(artifacts / "dataset_wrangled_forecasting.csv"))
                mlflow.log_artifact(str(artifacts / "wrangling_report.csv"))

    return {
        "benchmark": out,
        "predicciones": pred_table,
        "drift": drift_log,
        "dataset_wrangled": wrangled,
        "wrangling_report": wrangling_report,
        "winner": winner,
    }


def run_imputation_ab_test(alpha=0.95, lead_time=1.0, source="dwh"):
    configs = [
        {"id": "A_zero", "wrangling_mode": "zero", "model_imputer_strategy": "zero"},
        {"id": "B_temporal_median", "wrangling_mode": "temporal", "model_imputer_strategy": "median"},
    ]

    rows = []
    details = {}
    for cfg in configs:
        res = run_forecasting_thesis(
            alpha=alpha,
            lead_time=lead_time,
            use_mlflow=False,
            max_prophet_products=120,
            source=source,
            wrangling_mode=cfg["wrangling_mode"],
            model_imputer_strategy=cfg["model_imputer_strategy"],
        )
        bench = res["benchmark"].copy()
        best = bench.iloc[0]
        rows.append(
            {
                "config_id": cfg["id"],
                "wrangling_mode": cfg["wrangling_mode"],
                "model_imputer_strategy": cfg["model_imputer_strategy"],
                "best_model": best["modelo"],
                "best_wape_val": best["WAPE_val"],
                "best_wape_test": best["WAPE_test"],
                "best_mae_test": best["MAE_test"],
                "best_rmse_test": best["RMSE_test"],
                "rows_wrangled": len(res["dataset_wrangled"]),
                "products_wrangled": res["dataset_wrangled"]["producto"].nunique(),
            }
        )
        details[cfg["id"]] = res

    summary = pd.DataFrame(rows).sort_values(["best_wape_val", "best_wape_test"], ascending=[True, True]).reset_index(drop=True)
    return summary, details
