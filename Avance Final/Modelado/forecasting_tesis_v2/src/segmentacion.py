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
    _fit_predict_by_categoria,
    _fit_predict_by_tipo,
    _fit_predict_hierarchical,
    _metrics,
    _prep_x,
    _temporal_split,
)


@dataclass
class SegmentedModelingConfig:
    source: str = "dwh"
    min_periods_product: int = 4
    train_frac: float = 0.6
    val_frac: float = 0.2
    seasonal_active_months: int = 3
    seasonal_active_share: float = 0.45
    cap_quantile: float = 0.995
    min_rows_segment_train: int = 60
    min_rows_segment_val: int = 10
    min_rows_segment_test: int = 10
    fallback_model: str = "LinearRegression"


def _build_candidate_predictions(train_df, val_df, test_df, features):
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

    pred_val_map["RandomForest_ByTipo"] = _fit_predict_by_tipo(train_df, val_df, features, model_name="RandomForest")
    pred_test_map["RandomForest_ByTipo"] = _fit_predict_by_tipo(
        train_val_df, test_df, features, model_name="RandomForest"
    )

    pred_val_map["RandomForest_ByCategoria"] = _fit_predict_by_categoria(
        train_df, val_df, features, model_name="RandomForest"
    )
    pred_test_map["RandomForest_ByCategoria"] = _fit_predict_by_categoria(
        train_val_df, test_df, features, model_name="RandomForest"
    )

    pred_val_h, _ = _fit_predict_hierarchical(train_df, val_df, features, model_name="RandomForest")
    pred_test_h, _ = _fit_predict_hierarchical(train_val_df, test_df, features, model_name="RandomForest")
    pred_val_map["RandomForest_Hierarquico"] = pred_val_h
    pred_test_map["RandomForest_Hierarquico"] = pred_test_h

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


def _candidate_metrics_for_subset(df_subset: pd.DataFrame, pred_map: dict, full_index, suffix: str = "val"):
    rows = []
    y_true = df_subset["target_t1"].astype(float)

    for model_name, preds in pred_map.items():
        pred_series = pd.Series(np.asarray(preds, dtype=float), index=full_index)
        y_pred = pred_series.loc[df_subset.index].to_numpy(dtype=float)

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
                f"n_rows_{suffix}": len(df_subset),
                f"n_productos_{suffix}": df_subset["producto"].nunique(),
            }
        )
    return pd.DataFrame(rows)


def _select_segment_champion(segment_val_df: pd.DataFrame, pred_val_map: dict, full_val_index, fallback_model: str):
    bench = _candidate_metrics_for_subset(
        segment_val_df,
        pred_val_map,
        full_index=full_val_index,
        suffix="val",
    )
    bench = bench.sort_values(
        ["WAPE_val", "ABS_BIAS_PCT_val", "SMAPE_val"]
    ).reset_index(drop=True)

    if len(bench) == 0:
        return fallback_model, bench

    winner = bench.iloc[0]["modelo"]
    return winner, bench


def _build_segmented_predictions(test_df: pd.DataFrame, segment_winners: pd.DataFrame, pred_test_map: dict):
    out = test_df[
        ["tipo_producto", "categoria_producto", "producto", "periodo", "next_period", "target_t1"]
    ].copy()

    winner_map = dict(zip(segment_winners["tipo_producto"], segment_winners["winner_model"]))
    out["winner_model_segment"] = out["tipo_producto"].map(winner_map)

    pred_final = []
    full_test_index = test_df.index

    for idx, row in out.iterrows():
        model_name = row["winner_model_segment"]
        if pd.isna(model_name) or model_name not in pred_test_map:
            model_name = "LinearRegression"

        pred_series = pd.Series(np.asarray(pred_test_map[model_name], dtype=float), index=full_test_index)
        pred_value = float(pred_series.loc[idx])
        pred_final.append(max(pred_value, 0))

    out["pronostico_qty"] = pred_final
    return out


def _evaluate_global_champion(test_df: pd.DataFrame, pred_test_map: dict):
    rows = []
    y_true = test_df["target_t1"].astype(float)
    full_test_index = test_df.index

    for model_name, preds in pred_test_map.items():
        pred_series = pd.Series(np.asarray(preds, dtype=float), index=full_test_index)
        y_pred = pred_series.loc[test_df.index].to_numpy(dtype=float)
        m = _metrics(y_true, y_pred)
        rows.append(
            {
                "modelo": model_name,
                "WAPE_test": m["WAPE"],
                "BIAS_PCT_test": m["BIAS_PCT"],
                "ABS_BIAS_PCT_test": abs(m["BIAS_PCT"]) if pd.notna(m["BIAS_PCT"]) else np.nan,
                "SMAPE_test": m["SMAPE"],
                "MAE_test": m["MAE"],
                "RMSE_test": m["RMSE"],
            }
        )

    bench = pd.DataFrame(rows).sort_values(
        ["WAPE_test", "ABS_BIAS_PCT_test", "SMAPE_test"]
    ).reset_index(drop=True)
    return bench


def run_segmented_modeling(config: SegmentedModelingConfig | None = None):
    cfg = config or SegmentedModelingConfig()

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

    pred_val_map, pred_test_map = _build_candidate_predictions(train_df, val_df, test_df, features)

    global_val_rows = []
    full_val_index = val_df.index
    for model_name, preds in pred_val_map.items():
        pred_series = pd.Series(np.asarray(preds, dtype=float), index=full_val_index)
        m = _metrics(val_df["target_t1"], pred_series.loc[val_df.index].to_numpy(dtype=float))
        global_val_rows.append(
            {
                "modelo": model_name,
                "WAPE_val": m["WAPE"],
                "BIAS_PCT_val": m["BIAS_PCT"],
                "ABS_BIAS_PCT_val": abs(m["BIAS_PCT"]) if pd.notna(m["BIAS_PCT"]) else np.nan,
                "SMAPE_val": m["SMAPE"],
                "MAE_val": m["MAE"],
                "RMSE_val": m["RMSE"],
            }
        )

    global_val_benchmark = pd.DataFrame(global_val_rows).sort_values(
        ["WAPE_val", "ABS_BIAS_PCT_val", "SMAPE_val"]
    ).reset_index(drop=True)

    global_winner = global_val_benchmark.iloc[0]["modelo"]

    segment_rows = []
    segment_benchmark_rows = []

    tipos = sorted(val_df["tipo_producto"].dropna().astype(str).unique().tolist())

    for tipo in tipos:
        tr_sub = train_df[train_df["tipo_producto"].astype(str) == tipo].copy()
        va_sub = val_df[val_df["tipo_producto"].astype(str) == tipo].copy()
        te_sub = test_df[test_df["tipo_producto"].astype(str) == tipo].copy()

        use_fallback = (
            len(tr_sub) < cfg.min_rows_segment_train
            or len(va_sub) < cfg.min_rows_segment_val
            or len(te_sub) < cfg.min_rows_segment_test
        )

        if use_fallback:
            winner = global_winner if global_winner else cfg.fallback_model
            bench = _candidate_metrics_for_subset(
                va_sub,
                pred_val_map,
                full_index=full_val_index,
                suffix="val",
            )
            if len(bench) > 0:
                bench["tipo_producto"] = tipo
                bench["winner_model"] = winner
                bench["selection_mode"] = "fallback_global"
                segment_benchmark_rows.append(bench)

            segment_rows.append(
                {
                    "tipo_producto": tipo,
                    "winner_model": winner,
                    "selection_mode": "fallback_global",
                    "n_rows_train": len(tr_sub),
                    "n_rows_val": len(va_sub),
                    "n_rows_test": len(te_sub),
                    "n_productos_train": tr_sub["producto"].nunique(),
                    "n_productos_val": va_sub["producto"].nunique(),
                    "n_productos_test": te_sub["producto"].nunique(),
                }
            )
            continue

        winner, bench = _select_segment_champion(
            va_sub,
            pred_val_map,
            full_val_index=full_val_index,
            fallback_model=cfg.fallback_model,
        )

        bench["tipo_producto"] = tipo
        bench["winner_model"] = winner
        bench["selection_mode"] = "segment_specific"
        segment_benchmark_rows.append(bench)

        segment_rows.append(
            {
                "tipo_producto": tipo,
                "winner_model": winner,
                "selection_mode": "segment_specific",
                "n_rows_train": len(tr_sub),
                "n_rows_val": len(va_sub),
                "n_rows_test": len(te_sub),
                "n_productos_train": tr_sub["producto"].nunique(),
                "n_productos_val": va_sub["producto"].nunique(),
                "n_productos_test": te_sub["producto"].nunique(),
            }
        )

    segment_winners = pd.DataFrame(segment_rows).sort_values("tipo_producto").reset_index(drop=True)
    segment_benchmark = pd.concat(segment_benchmark_rows, ignore_index=True) if segment_benchmark_rows else pd.DataFrame()

    pred_segmented = _build_segmented_predictions(test_df, segment_winners, pred_test_map)

    plan_t1 = wrangled[["producto", "periodo", "qty_planificada"]].rename(
        columns={"periodo": "next_period", "qty_planificada": "qty_planificada_t1"}
    )
    pred_segmented = pred_segmented.merge(plan_t1, on=["producto", "next_period"], how="left")

    train_val_like = wrangled[
        wrangled["periodo"].isin(split_info["train_periods"] + split_info["val_periods"])
    ].copy()
    pred_segmented = _cap_predictions_by_history(
        pred_segmented,
        train_val_like,
        cap_quantile=cfg.cap_quantile,
    )
    pred_segmented["pronostico_qty"] = pred_segmented["pronostico_qty"].clip(lower=0)

    segmented_metrics = _metrics(pred_segmented["target_t1"], pred_segmented["pronostico_qty"])
    segmented_summary = pd.DataFrame(
        [
            {
                "scope": "segmentado_final",
                "WAPE_test": segmented_metrics["WAPE"],
                "BIAS_PCT_test": segmented_metrics["BIAS_PCT"],
                "ABS_BIAS_PCT_test": abs(segmented_metrics["BIAS_PCT"])
                if pd.notna(segmented_metrics["BIAS_PCT"])
                else np.nan,
                "SMAPE_test": segmented_metrics["SMAPE"],
                "MAE_test": segmented_metrics["MAE"],
                "RMSE_test": segmented_metrics["RMSE"],
                "n_rows_test": len(pred_segmented),
                "n_productos_test": pred_segmented["producto"].nunique(),
            }
        ]
    )

    global_test_benchmark = _evaluate_global_champion(test_df, pred_test_map)

    comparison_vs_global = segmented_summary.copy()
    comparison_vs_global["global_winner_val"] = global_winner
    if len(global_test_benchmark) > 0:
        global_test_row = global_test_benchmark[global_test_benchmark["modelo"] == global_winner]
        if len(global_test_row) > 0:
            comparison_vs_global["WAPE_test_global_winner"] = float(global_test_row.iloc[0]["WAPE_test"])
            comparison_vs_global["BIAS_PCT_test_global_winner"] = float(global_test_row.iloc[0]["BIAS_PCT_test"])
            comparison_vs_global["SMAPE_test_global_winner"] = float(global_test_row.iloc[0]["SMAPE_test"])
            comparison_vs_global["delta_wape_segmentado_menos_global"] = (
                comparison_vs_global["WAPE_test"] - comparison_vs_global["WAPE_test_global_winner"]
            )

    segment_test_eval_rows = []
    for tipo, sub in pred_segmented.groupby("tipo_producto", dropna=False):
        m = _metrics(sub["target_t1"], sub["pronostico_qty"])
        segment_test_eval_rows.append(
            {
                "tipo_producto": tipo,
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

    segment_test_eval = pd.DataFrame(segment_test_eval_rows).sort_values("WAPE_test").reset_index(drop=True)

    return {
        "wrangling_report": wr_report,
        "global_val_benchmark": global_val_benchmark,
        "global_test_benchmark": global_test_benchmark,
        "global_winner": global_winner,
        "segment_winners": segment_winners,
        "segment_benchmark_val": segment_benchmark,
        "predicciones_segmentadas": pred_segmented,
        "segmentado_summary_test": segmented_summary,
        "comparison_vs_global": comparison_vs_global,
        "segment_test_eval": segment_test_eval,
    }


def save_segmented_outputs(result: dict, artifacts_dir: Path):
    artifacts_dir.mkdir(exist_ok=True, parents=True)

    result["wrangling_report"].to_csv(artifacts_dir / "wrangling_report_segmented.csv", index=False)
    result["global_val_benchmark"].to_csv(artifacts_dir / "global_val_benchmark_segmented.csv", index=False)
    result["global_test_benchmark"].to_csv(artifacts_dir / "global_test_benchmark_segmented.csv", index=False)
    result["segment_winners"].to_csv(artifacts_dir / "segment_winners.csv", index=False)
    result["segment_benchmark_val"].to_csv(artifacts_dir / "segment_benchmark_val.csv", index=False)
    result["predicciones_segmentadas"].to_csv(artifacts_dir / "predicciones_segmentadas.csv", index=False)
    result["segmentado_summary_test"].to_csv(artifacts_dir / "segmentado_summary_test.csv", index=False)
    result["comparison_vs_global"].to_csv(artifacts_dir / "comparison_segmentado_vs_global.csv", index=False)
    result["segment_test_eval"].to_csv(artifacts_dir / "segment_test_eval.csv", index=False)