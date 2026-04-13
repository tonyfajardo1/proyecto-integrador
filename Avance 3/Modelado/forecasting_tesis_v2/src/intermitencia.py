from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .data_source import load_monthly_dataset
from .wrangling import prepare_for_modeling
from .modeling import (
    _build_features,
    _build_models,
    _cap_predictions_by_history,
    _encode_column_train_only,
    _encode_producto_train_only,
    _metrics,
    _prep_x,
    _temporal_split,
)


@dataclass
class IntermittentModelingConfig:
    source: str = "dwh"
    min_periods_product: int = 4
    train_frac: float = 0.6
    val_frac: float = 0.2
    seasonal_active_months: int = 3
    seasonal_active_share: float = 0.45
    cap_quantile: float = 0.995

    intermittent_zero_share_threshold: float = 0.50
    intermittent_avg_gap_threshold: float = 1.50
    low_history_threshold: int = 12

    regular_model: str = "LinearRegression"
    intermittent_model: str = "Baseline_Lag1"


def _classify_product_intermittency(train_like: pd.DataFrame, cfg: IntermittentModelingConfig) -> pd.DataFrame:
    rows = []

    for producto, sub in train_like.groupby("producto", dropna=False):
        s = sub.sort_values("periodo").copy()

        qty = pd.to_numeric(s["qty_fabricada"], errors="coerce").fillna(0).clip(lower=0)
        n = len(qty)

        if n == 0:
            rows.append(
                {
                    "producto": producto,
                    "n_periods_train": 0,
                    "n_positive_periods": 0,
                    "zero_share_train": np.nan,
                    "avg_gap_positive_train": np.nan,
                    "is_low_history": True,
                    "is_intermittent": True,
                    "demand_class": "INTERMITTENT",
                }
            )
            continue

        positive_mask = qty > 0
        n_positive = int(positive_mask.sum())
        zero_share = float((qty == 0).mean())

        pos_idx = np.where(positive_mask.to_numpy())[0]
        if len(pos_idx) >= 2:
            gaps = np.diff(pos_idx)
            avg_gap = float(np.mean(gaps))
        else:
            avg_gap = np.inf if n_positive == 1 else np.nan

        is_low_history = n < int(cfg.low_history_threshold)

        is_intermittent = (
            zero_share >= float(cfg.intermittent_zero_share_threshold)
            or (pd.notna(avg_gap) and avg_gap >= float(cfg.intermittent_avg_gap_threshold))
            or is_low_history
        )

        demand_class = "INTERMITTENT" if is_intermittent else "REGULAR"

        rows.append(
            {
                "producto": producto,
                "n_periods_train": int(n),
                "n_positive_periods": int(n_positive),
                "zero_share_train": zero_share,
                "avg_gap_positive_train": avg_gap,
                "is_low_history": bool(is_low_history),
                "is_intermittent": bool(is_intermittent),
                "demand_class": demand_class,
            }
        )

    return pd.DataFrame(rows)


def _build_candidate_predictions_for_intermittency(train_df, val_df, test_df, features):
    pred_val_map = {}
    pred_test_map = {}

    pred_val_map["Baseline_Lag1"] = np.maximum(val_df["lag_1"].fillna(0).to_numpy(dtype=float), 0)
    pred_test_map["Baseline_Lag1"] = np.maximum(test_df["lag_1"].fillna(0).to_numpy(dtype=float), 0)

    pred_val_map["Baseline_Lag12_Seasonal"] = np.maximum(
        val_df["lag_12"].fillna(val_df["lag_1"]).fillna(0).to_numpy(dtype=float), 0
    )
    pred_test_map["Baseline_Lag12_Seasonal"] = np.maximum(
        test_df["lag_12"].fillna(test_df["lag_1"]).fillna(0).to_numpy(dtype=float), 0
    )

    train_val_df = pd.concat([train_df, val_df], ignore_index=True)

    models = _build_models()
    for name, model in models.items():
        model.fit(_prep_x(train_df, features), train_df["target_t1"].astype(float))
        pred_val_map[name] = np.maximum(model.predict(_prep_x(val_df, features)), 0)

        model.fit(_prep_x(train_val_df, features), train_val_df["target_t1"].astype(float))
        pred_test_map[name] = np.maximum(model.predict(_prep_x(test_df, features)), 0)

    if all(k in pred_val_map for k in ["LinearRegression", "RandomForest", "ExtraTrees"]):
        pred_val_map["Ensemble_RF_ET_LR"] = (
            0.2 * pred_val_map["LinearRegression"]
            + 0.4 * pred_val_map["RandomForest"]
            + 0.4 * pred_val_map["ExtraTrees"]
        )
        pred_test_map["Ensemble_RF_ET_LR"] = (
            0.2 * pred_test_map["LinearRegression"]
            + 0.4 * pred_test_map["RandomForest"]
            + 0.4 * pred_test_map["ExtraTrees"]
        )

    return pred_val_map, pred_test_map


def _evaluate_group_candidates(group_df: pd.DataFrame, pred_map: dict, full_index, suffix="val") -> pd.DataFrame:
    rows = []
    y_true = group_df["target_t1"].astype(float)
    row_ids = group_df["_row_id"].to_numpy()

    for model_name, preds in pred_map.items():
        pred_series = pd.Series(np.asarray(preds, dtype=float), index=full_index)
        y_pred = pred_series.loc[row_ids].to_numpy(dtype=float)

        m = _metrics(y_true, y_pred)
        rows.append(
            {
                "modelo": model_name,
                f"WAPE_{suffix}": m["WAPE"],
                f"BIAS_PCT_{suffix}": m["BIAS_PCT"],
                f"ABS_BIAS_PCT_{suffix}": abs(m["BIAS_PCT"]) if pd.notna(m["BIAS_PCT"]) else np.nan,
                f"SMAPE_{suffix}": m["SMAPE"],
                f"MAE_{suffix}": m["MAE"],
                f"RMSE_{suffix}": m["RMSE"],
                f"n_rows_{suffix}": len(group_df),
                f"n_productos_{suffix}": group_df["producto"].nunique(),
            }
        )
    return pd.DataFrame(rows)


def _assemble_mixed_predictions(
    test_df: pd.DataFrame,
    product_class_map: pd.DataFrame,
    pred_test_map: dict,
    regular_model: str,
    intermittent_model: str,
) -> pd.DataFrame:
    out = test_df[
        ["tipo_producto", "categoria_producto", "producto", "periodo", "next_period", "target_t1"]
    ].copy()
    out["_row_id"] = test_df.index

    out = out.merge(
        product_class_map[["producto", "demand_class", "is_intermittent"]],
        on="producto",
        how="left",
    )

    out["demand_class"] = out["demand_class"].fillna("INTERMITTENT")
    out["is_intermittent"] = out["is_intermittent"].astype("boolean").fillna(True).astype(bool)

    full_test_index = test_df.index
    pred_regular = pd.Series(np.asarray(pred_test_map[regular_model], dtype=float), index=full_test_index)
    pred_intermittent = pd.Series(np.asarray(pred_test_map[intermittent_model], dtype=float), index=full_test_index)

    out["modelo_asignado"] = np.where(out["is_intermittent"], intermittent_model, regular_model)
    out["pronostico_qty"] = np.where(
        out["is_intermittent"],
        pred_intermittent.loc[out["_row_id"]].to_numpy(dtype=float),
        pred_regular.loc[out["_row_id"]].to_numpy(dtype=float),
    )
    out["pronostico_qty"] = np.maximum(out["pronostico_qty"].astype(float), 0)

    return out.drop(columns=["_row_id"])


def run_intermittent_modeling(config: IntermittentModelingConfig | None = None):
    cfg = config or IntermittentModelingConfig()

    raw = load_monthly_dataset(source=cfg.source, fallback_quickbooks=True)
    wrangled, wr_report = prepare_for_modeling(
        raw,
        min_periods_product=cfg.min_periods_product,
        seasonality_max_active_months=cfg.seasonal_active_months,
        seasonality_max_active_share=cfg.seasonal_active_share,
    )

    feat = _build_features(wrangled)

    train_df, val_df, test_df, split_info = _temporal_split(
        feat,
        train_frac=cfg.train_frac,
        val_frac=cfg.val_frac,
    )

    (train_df, val_df, test_df), _ = _encode_producto_train_only(train_df, val_df, test_df)
    (train_df, val_df, test_df), _ = _encode_column_train_only(
        train_df, val_df, test_df, column="tipo_producto", out_col="tipo_id"
    )
    (train_df, val_df, test_df), _ = _encode_column_train_only(
        train_df, val_df, test_df, column="categoria_producto", out_col="categoria_id"
    )

    features = [
        "producto_id",
        "tipo_id",
        "categoria_id",
        "anio_num",
        "mes_num",
        "lag_1",
        "lag_2",
        "lag_3",
        "rolling_mean_3",
        "rolling_std_3",
        "delta_1",
        "n_ordenes_lag_1",
    ]

    pred_val_map, pred_test_map = _build_candidate_predictions_for_intermittency(
        train_df, val_df, test_df, features
    )

    train_like = wrangled[wrangled["periodo"].isin(split_info["train_periods"])].copy()
    train_val_like = wrangled[
        wrangled["periodo"].isin(split_info["train_periods"] + split_info["val_periods"])
    ].copy()

    product_class_map = _classify_product_intermittency(train_like, cfg)

    val_eval = val_df.copy()
    val_eval["_row_id"] = val_df.index
    val_eval = val_eval.merge(
        product_class_map[["producto", "demand_class", "is_intermittent"]],
        on="producto",
        how="left",
    )

    test_eval = test_df.copy()
    test_eval["_row_id"] = test_df.index
    test_eval = test_eval.merge(
        product_class_map[["producto", "demand_class", "is_intermittent"]],
        on="producto",
        how="left",
    )

    val_eval["demand_class"] = val_eval["demand_class"].fillna("INTERMITTENT")
    val_eval["is_intermittent"] = val_eval["is_intermittent"].astype("boolean").fillna(True).astype(bool)

    test_eval["demand_class"] = test_eval["demand_class"].fillna("INTERMITTENT")
    test_eval["is_intermittent"] = test_eval["is_intermittent"].astype("boolean").fillna(True).astype(bool)

    full_val_index = val_df.index

    regular_val = val_eval[val_eval["demand_class"] == "REGULAR"].copy()
    intermittent_val = val_eval[val_eval["demand_class"] == "INTERMITTENT"].copy()

    regular_val_benchmark = _evaluate_group_candidates(
        regular_val, pred_val_map, full_val_index, suffix="val"
    ).sort_values(["WAPE_val", "ABS_BIAS_PCT_val", "SMAPE_val"]).reset_index(drop=True)

    intermittent_val_benchmark = _evaluate_group_candidates(
        intermittent_val, pred_val_map, full_val_index, suffix="val"
    ).sort_values(["WAPE_val", "ABS_BIAS_PCT_val", "SMAPE_val"]).reset_index(drop=True)

    regular_model = cfg.regular_model
    intermittent_model = cfg.intermittent_model

    pred_mixed = _assemble_mixed_predictions(
        test_df=test_df,
        product_class_map=product_class_map,
        pred_test_map=pred_test_map,
        regular_model=regular_model,
        intermittent_model=intermittent_model,
    )

    plan_t1 = wrangled[["producto", "periodo", "qty_planificada"]].rename(
        columns={"periodo": "next_period", "qty_planificada": "qty_planificada_t1"}
    )
    pred_mixed = pred_mixed.merge(plan_t1, on=["producto", "next_period"], how="left")

    pred_mixed = _cap_predictions_by_history(
        pred_mixed,
        train_val_like,
        cap_quantile=cfg.cap_quantile,
    )
    pred_mixed["pronostico_qty"] = pred_mixed["pronostico_qty"].clip(lower=0)

    mixed_metrics = _metrics(pred_mixed["target_t1"], pred_mixed["pronostico_qty"])
    mixed_summary = pd.DataFrame(
        [
            {
                "scope": "mixed_regular_vs_intermittent",
                "regular_model": regular_model,
                "intermittent_model": intermittent_model,
                "WAPE_test": mixed_metrics["WAPE"],
                "BIAS_PCT_test": mixed_metrics["BIAS_PCT"],
                "ABS_BIAS_PCT_test": abs(mixed_metrics["BIAS_PCT"]) if pd.notna(mixed_metrics["BIAS_PCT"]) else np.nan,
                "SMAPE_test": mixed_metrics["SMAPE"],
                "MAE_test": mixed_metrics["MAE"],
                "RMSE_test": mixed_metrics["RMSE"],
                "n_rows_test": len(pred_mixed),
                "n_productos_test": pred_mixed["producto"].nunique(),
            }
        ]
    )

    full_test_index = test_df.index
    global_pred = pd.Series(np.asarray(pred_test_map[regular_model], dtype=float), index=full_test_index)
    global_metrics = _metrics(test_df["target_t1"], global_pred.loc[test_df.index].to_numpy(dtype=float))
    comparison_vs_global = pd.DataFrame(
        [
            {
                "global_model": regular_model,
                "mixed_regular_model": regular_model,
                "mixed_intermittent_model": intermittent_model,
                "WAPE_test_mixed": mixed_metrics["WAPE"],
                "WAPE_test_global": global_metrics["WAPE"],
                "delta_wape_mixed_menos_global": mixed_metrics["WAPE"] - global_metrics["WAPE"],
                "BIAS_PCT_test_mixed": mixed_metrics["BIAS_PCT"],
                "BIAS_PCT_test_global": global_metrics["BIAS_PCT"],
                "SMAPE_test_mixed": mixed_metrics["SMAPE"],
                "SMAPE_test_global": global_metrics["SMAPE"],
            }
        ]
    )

    demand_class_test_eval_rows = []
    for demand_class, sub in pred_mixed.groupby("demand_class", dropna=False):
        m = _metrics(sub["target_t1"], sub["pronostico_qty"])
        demand_class_test_eval_rows.append(
            {
                "demand_class": demand_class,
                "WAPE_test": m["WAPE"],
                "BIAS_PCT_test": m["BIAS_PCT"],
                "ABS_BIAS_PCT_test": abs(m["BIAS_PCT"]) if pd.notna(m["BIAS_PCT"]) else np.nan,
                "SMAPE_test": m["SMAPE"],
                "MAE_test": m["MAE"],
                "RMSE_test": m["RMSE"],
                "n_rows_test": len(sub),
                "n_productos_test": sub["producto"].nunique(),
            }
        )
    demand_class_test_eval = pd.DataFrame(demand_class_test_eval_rows).sort_values("WAPE_test").reset_index(drop=True)

    class_distribution = (
        product_class_map.groupby("demand_class", as_index=False)
        .agg(
            n_productos=("producto", "nunique"),
            avg_zero_share_train=("zero_share_train", "mean"),
            avg_gap_positive_train=("avg_gap_positive_train", "mean"),
            avg_periods_train=("n_periods_train", "mean"),
        )
        .sort_values("demand_class")
        .reset_index(drop=True)
    )

    return {
        "wrangling_report": wr_report,
        "product_class_map": product_class_map,
        "class_distribution": class_distribution,
        "regular_val_benchmark": regular_val_benchmark,
        "intermittent_val_benchmark": intermittent_val_benchmark,
        "predicciones_mixtas": pred_mixed,
        "mixed_summary_test": mixed_summary,
        "comparison_vs_global": comparison_vs_global,
        "demand_class_test_eval": demand_class_test_eval,
    }


def save_intermittent_outputs(result: dict, artifacts_dir: Path):
    artifacts_dir.mkdir(exist_ok=True, parents=True)

    result["wrangling_report"].to_csv(artifacts_dir / "wrangling_report_intermittent.csv", index=False)
    result["product_class_map"].to_csv(artifacts_dir / "product_class_map.csv", index=False)
    result["class_distribution"].to_csv(artifacts_dir / "class_distribution.csv", index=False)
    result["regular_val_benchmark"].to_csv(artifacts_dir / "regular_val_benchmark.csv", index=False)
    result["intermittent_val_benchmark"].to_csv(artifacts_dir / "intermittent_val_benchmark.csv", index=False)
    result["predicciones_mixtas"].to_csv(artifacts_dir / "predicciones_mixtas.csv", index=False)
    result["mixed_summary_test"].to_csv(artifacts_dir / "mixed_summary_test.csv", index=False)
    result["comparison_vs_global"].to_csv(artifacts_dir / "comparison_intermittent_vs_global.csv", index=False)
    result["demand_class_test_eval"].to_csv(artifacts_dir / "demand_class_test_eval.csv", index=False)