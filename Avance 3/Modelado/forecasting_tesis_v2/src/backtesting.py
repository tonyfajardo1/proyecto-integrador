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
    _build_pilot_report,
    _build_segment_error_report,
    _cap_predictions_by_history,
    _encode_column_train_only,
    _encode_producto_train_only,
    _fit_predict_by_categoria,
    _fit_predict_by_tipo,
    _fit_predict_hierarchical,
    _metrics,
    _prep_x,
)


@dataclass
class BacktestingConfig:
    source: str = "dwh"
    min_periods_product: int = 4
    initial_train_periods: int = 18
    val_window: int = 3
    test_window: int = 3
    step_size: int = 3
    seasonal_active_months: int = 3
    seasonal_active_share: float = 0.45
    cap_quantile: float = 0.995
    top_n_pilot: int = 100
    pilot_tipo: str = "PT"


def _generate_rolling_folds(
    periods,
    initial_train_periods=18,
    val_window=3,
    test_window=3,
    step_size=3,
):
    periods = sorted(pd.to_datetime(pd.Series(periods).dropna().unique()).tolist())
    n = len(periods)

    folds = []
    fold_id = 1
    train_end = int(initial_train_periods)

    while True:
        val_end = train_end + int(val_window)
        test_end = val_end + int(test_window)

        if test_end > n:
            break

        train_periods = periods[:train_end]
        val_periods = periods[train_end:val_end]
        test_periods = periods[val_end:test_end]

        folds.append(
            {
                "fold": fold_id,
                "train_periods": train_periods,
                "val_periods": val_periods,
                "test_periods": test_periods,
                "train_start": train_periods[0],
                "train_end": train_periods[-1],
                "val_start": val_periods[0],
                "val_end": val_periods[-1],
                "test_start": test_periods[0],
                "test_end": test_periods[-1],
            }
        )

        fold_id += 1
        train_end += int(step_size)

    return folds


def _seasonal_baseline_predictions(df: pd.DataFrame) -> np.ndarray:
    return np.maximum(df["lag_12"].fillna(df["lag_1"]).fillna(0).to_numpy(dtype=float), 0)


def _evaluate_one_fold(
    feat: pd.DataFrame,
    wrangled: pd.DataFrame,
    fold_meta: dict,
    cfg: BacktestingConfig,
):
    train_periods = set(fold_meta["train_periods"])
    val_periods = set(fold_meta["val_periods"])
    test_periods = set(fold_meta["test_periods"])

    train_df = feat[feat["periodo"].isin(train_periods)].copy()
    val_df = feat[feat["periodo"].isin(val_periods)].copy()
    test_df = feat[feat["periodo"].isin(test_periods)].copy()

    if len(train_df) == 0 or len(val_df) == 0 or len(test_df) == 0:
        return None

    (train_df, val_df, test_df), _ = _encode_producto_train_only(train_df, val_df, test_df)
    (train_df, val_df, test_df), _ = _encode_column_train_only(
        train_df, val_df, test_df, column="tipo_producto", out_col="tipo_id"
    )
    (train_df, val_df, test_df), _ = _encode_column_train_only(
        train_df, val_df, test_df, column="categoria_producto", out_col="categoria_id"
    )

    train_val_df = pd.concat([train_df, val_df], ignore_index=True)

    train_val_like = wrangled[
        wrangled["periodo"].isin(list(train_periods) + list(val_periods))
    ].copy()

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

    rows = []
    pred_test_map = {}

    # =========================
    # Baseline Lag 1
    # =========================
    p_test_lag1 = np.maximum(test_df["lag_1"].fillna(0).to_numpy(dtype=float), 0)
    m_test = _metrics(test_df["target_t1"], p_test_lag1)

    rows.append(
        {
            "fold": fold_meta["fold"],
            "modelo": "Baseline_Lag1",
            "WAPE_test": m_test["WAPE"],
            "BIAS_PCT_test": m_test["BIAS_PCT"],
            "SMAPE_test": m_test["SMAPE"],
            "MAE_test": m_test["MAE"],
            "RMSE_test": m_test["RMSE"],
            "n_rows_test": len(test_df),
            "n_productos_test": test_df["producto"].nunique(),
            "train_start": fold_meta["train_start"],
            "train_end": fold_meta["train_end"],
            "val_start": fold_meta["val_start"],
            "val_end": fold_meta["val_end"],
            "test_start": fold_meta["test_start"],
            "test_end": fold_meta["test_end"],
        }
    )
    pred_test_map["Baseline_Lag1"] = p_test_lag1

    # =========================
    # Baseline Lag 12
    # =========================
    p_test_lag12 = _seasonal_baseline_predictions(test_df)
    m_test = _metrics(test_df["target_t1"], p_test_lag12)

    rows.append(
        {
            "fold": fold_meta["fold"],
            "modelo": "Baseline_Lag12_Seasonal",
            "WAPE_test": m_test["WAPE"],
            "BIAS_PCT_test": m_test["BIAS_PCT"],
            "SMAPE_test": m_test["SMAPE"],
            "MAE_test": m_test["MAE"],
            "RMSE_test": m_test["RMSE"],
            "n_rows_test": len(test_df),
            "n_productos_test": test_df["producto"].nunique(),
            "train_start": fold_meta["train_start"],
            "train_end": fold_meta["train_end"],
            "val_start": fold_meta["val_start"],
            "val_end": fold_meta["val_end"],
            "test_start": fold_meta["test_start"],
            "test_end": fold_meta["test_end"],
        }
    )
    pred_test_map["Baseline_Lag12_Seasonal"] = p_test_lag12

    # =========================
    # Modelos globales
    # =========================
    models = _build_models()

    for name, model in models.items():
        model.fit(_prep_x(train_val_df, features), train_val_df["target_t1"].astype(float))
        p_test = np.maximum(model.predict(_prep_x(test_df, features)), 0)
        p_test = np.asarray(p_test, dtype=float)
        p_test = np.maximum(p_test, 0)

        m_test = _metrics(test_df["target_t1"], p_test)

        rows.append(
            {
                "fold": fold_meta["fold"],
                "modelo": name,
                "WAPE_test": m_test["WAPE"],
                "BIAS_PCT_test": m_test["BIAS_PCT"],
                "SMAPE_test": m_test["SMAPE"],
                "MAE_test": m_test["MAE"],
                "RMSE_test": m_test["RMSE"],
                "n_rows_test": len(test_df),
                "n_productos_test": test_df["producto"].nunique(),
                "train_start": fold_meta["train_start"],
                "train_end": fold_meta["train_end"],
                "val_start": fold_meta["val_start"],
                "val_end": fold_meta["val_end"],
                "test_start": fold_meta["test_start"],
                "test_end": fold_meta["test_end"],
            }
        )

        pred_test_map[name] = p_test

    # =========================
    # Segmentados
    # =========================
    p_test_tipo = _fit_predict_by_tipo(train_val_df, test_df, features, model_name="RandomForest")
    m_test = _metrics(test_df["target_t1"], p_test_tipo)

    rows.append(
        {
            "fold": fold_meta["fold"],
            "modelo": "RandomForest_ByTipo",
            "WAPE_test": m_test["WAPE"],
            "BIAS_PCT_test": m_test["BIAS_PCT"],
            "SMAPE_test": m_test["SMAPE"],
            "MAE_test": m_test["MAE"],
            "RMSE_test": m_test["RMSE"],
            "n_rows_test": len(test_df),
            "n_productos_test": test_df["producto"].nunique(),
            "train_start": fold_meta["train_start"],
            "train_end": fold_meta["train_end"],
            "val_start": fold_meta["val_start"],
            "val_end": fold_meta["val_end"],
            "test_start": fold_meta["test_start"],
            "test_end": fold_meta["test_end"],
        }
    )
    pred_test_map["RandomForest_ByTipo"] = p_test_tipo

    p_test_cat = _fit_predict_by_categoria(train_val_df, test_df, features, model_name="RandomForest")
    m_test = _metrics(test_df["target_t1"], p_test_cat)

    rows.append(
        {
            "fold": fold_meta["fold"],
            "modelo": "RandomForest_ByCategoria",
            "WAPE_test": m_test["WAPE"],
            "BIAS_PCT_test": m_test["BIAS_PCT"],
            "SMAPE_test": m_test["SMAPE"],
            "MAE_test": m_test["MAE"],
            "RMSE_test": m_test["RMSE"],
            "n_rows_test": len(test_df),
            "n_productos_test": test_df["producto"].nunique(),
            "train_start": fold_meta["train_start"],
            "train_end": fold_meta["train_end"],
            "val_start": fold_meta["val_start"],
            "val_end": fold_meta["val_end"],
            "test_start": fold_meta["test_start"],
            "test_end": fold_meta["test_end"],
        }
    )
    pred_test_map["RandomForest_ByCategoria"] = p_test_cat

    p_test_h, _ = _fit_predict_hierarchical(train_val_df, test_df, features, model_name="RandomForest")
    m_test = _metrics(test_df["target_t1"], p_test_h)

    rows.append(
        {
            "fold": fold_meta["fold"],
            "modelo": "RandomForest_Hierarquico",
            "WAPE_test": m_test["WAPE"],
            "BIAS_PCT_test": m_test["BIAS_PCT"],
            "SMAPE_test": m_test["SMAPE"],
            "MAE_test": m_test["MAE"],
            "RMSE_test": m_test["RMSE"],
            "n_rows_test": len(test_df),
            "n_productos_test": test_df["producto"].nunique(),
            "train_start": fold_meta["train_start"],
            "train_end": fold_meta["train_end"],
            "val_start": fold_meta["val_start"],
            "val_end": fold_meta["val_end"],
            "test_start": fold_meta["test_start"],
            "test_end": fold_meta["test_end"],
        }
    )
    pred_test_map["RandomForest_Hierarquico"] = p_test_h

    # =========================
    # Ensemble
    # =========================
    if all(k in pred_test_map for k in ["LinearRegression", "RandomForest", "ExtraTrees"]):
        p_test_ens = (
            0.2 * pred_test_map["LinearRegression"]
            + 0.4 * pred_test_map["RandomForest"]
            + 0.4 * pred_test_map["ExtraTrees"]
        )
        m_test = _metrics(test_df["target_t1"], p_test_ens)

        rows.append(
            {
                "fold": fold_meta["fold"],
                "modelo": "Ensemble_RF_ET_LR",
                "WAPE_test": m_test["WAPE"],
                "BIAS_PCT_test": m_test["BIAS_PCT"],
                "SMAPE_test": m_test["SMAPE"],
                "MAE_test": m_test["MAE"],
                "RMSE_test": m_test["RMSE"],
                "n_rows_test": len(test_df),
                "n_productos_test": test_df["producto"].nunique(),
                "train_start": fold_meta["train_start"],
                "train_end": fold_meta["train_end"],
                "val_start": fold_meta["val_start"],
                "val_end": fold_meta["val_end"],
                "test_start": fold_meta["test_start"],
                "test_end": fold_meta["test_end"],
            }
        )
        pred_test_map["Ensemble_RF_ET_LR"] = p_test_ens

    # =========================
    # Orden del fold
    # =========================
    fold_benchmark = pd.DataFrame(rows)
    fold_benchmark["ABS_BIAS_PCT_test"] = fold_benchmark["BIAS_PCT_test"].abs()
    fold_benchmark = fold_benchmark.sort_values(
        ["WAPE_test", "ABS_BIAS_PCT_test", "SMAPE_test"]
    ).reset_index(drop=True)

    winner = fold_benchmark.iloc[0]["modelo"]

    pred_table = test_df[
        [
            "tipo_producto",
            "categoria_producto",
            "producto",
            "periodo",
            "next_period",
            "target_t1",
        ]
    ].copy()
    pred_table["pronostico_qty"] = np.maximum(np.asarray(pred_test_map[winner], dtype=float), 0)
    pred_table["modelo_ganador_fold"] = winner
    pred_table["fold"] = fold_meta["fold"]

    pred_table = _cap_predictions_by_history(
        pred_table,
        train_val_like,
        cap_quantile=cfg.cap_quantile,
    )
    pred_table["pronostico_qty"] = pred_table["pronostico_qty"].clip(lower=0)

    pilot = _build_pilot_report(
        pred_table,
        pilot_tipo=cfg.pilot_tipo,
        top_n=cfg.top_n_pilot,
    )
    pilot["fold"] = fold_meta["fold"]

    seg = _build_segment_error_report(pred_table)
    if len(seg) > 0:
        seg["fold"] = fold_meta["fold"]

    return {
        "fold_benchmark": fold_benchmark,
        "winner": winner,
        "pred_table": pred_table,
        "pilot": pilot,
        "segment_error": seg,
    }


def run_rolling_backtesting(config: BacktestingConfig | None = None):
    cfg = config or BacktestingConfig()

    raw = load_monthly_dataset(source=cfg.source, fallback_quickbooks=True)
    wrangled, wr_report = prepare_for_modeling(
        raw,
        min_periods_product=cfg.min_periods_product,
        seasonality_max_active_months=cfg.seasonal_active_months,
        seasonality_max_active_share=cfg.seasonal_active_share,
    )

    feat = _build_features(wrangled)

    periods = sorted(feat["periodo"].dropna().unique().tolist())
    folds = _generate_rolling_folds(
        periods,
        initial_train_periods=cfg.initial_train_periods,
        val_window=cfg.val_window,
        test_window=cfg.test_window,
        step_size=cfg.step_size,
    )

    if not folds:
        raise ValueError(
            "No se pudieron generar folds rolling. Reduce initial_train_periods o las ventanas."
        )

    fold_results = []
    pred_tables = []
    pilot_rows = []
    segment_rows = []
    winner_rows = []

    for fold_meta in folds:
        out = _evaluate_one_fold(feat, wrangled, fold_meta, cfg)
        if out is None:
            continue

        fold_results.append(out["fold_benchmark"])
        pred_tables.append(out["pred_table"])
        pilot_rows.append(out["pilot"])

        if len(out["segment_error"]) > 0:
            segment_rows.append(out["segment_error"])

        winner_rows.append(
            {
                "fold": fold_meta["fold"],
                "winner": out["winner"],
                "train_start": fold_meta["train_start"],
                "train_end": fold_meta["train_end"],
                "val_start": fold_meta["val_start"],
                "val_end": fold_meta["val_end"],
                "test_start": fold_meta["test_start"],
                "test_end": fold_meta["test_end"],
            }
        )

    detail = pd.concat(fold_results, ignore_index=True)
    winner_by_fold = pd.DataFrame(winner_rows)
    pred_detail = pd.concat(pred_tables, ignore_index=True)
    pilot_detail = pd.concat(pilot_rows, ignore_index=True)
    segment_detail = pd.concat(segment_rows, ignore_index=True) if segment_rows else pd.DataFrame()

    summary = (
        detail.groupby("modelo", as_index=False)
        .agg(
            folds_evaluados=("fold", "nunique"),
            WAPE_test_mean=("WAPE_test", "mean"),
            WAPE_test_median=("WAPE_test", "median"),
            WAPE_test_std=("WAPE_test", "std"),
            BIAS_PCT_test_mean=("BIAS_PCT_test", "mean"),
            ABS_BIAS_PCT_test_mean=("ABS_BIAS_PCT_test", "mean"),
            SMAPE_test_mean=("SMAPE_test", "mean"),
            MAE_test_mean=("MAE_test", "mean"),
            RMSE_test_mean=("RMSE_test", "mean"),
        )
    )

    summary = summary.sort_values(
        ["WAPE_test_mean", "ABS_BIAS_PCT_test_mean", "SMAPE_test_mean"]
    ).reset_index(drop=True)

    winner_counts = (
        winner_by_fold["winner"]
        .value_counts(dropna=False)
        .rename_axis("modelo")
        .reset_index(name="folds_ganados")
    )

    summary = summary.merge(winner_counts, on="modelo", how="left")
    summary["folds_ganados"] = summary["folds_ganados"].fillna(0).astype(int)

    fold_meta_df = pd.DataFrame(
        [
            {
                "fold": f["fold"],
                "train_start": f["train_start"],
                "train_end": f["train_end"],
                "val_start": f["val_start"],
                "val_end": f["val_end"],
                "test_start": f["test_start"],
                "test_end": f["test_end"],
                "n_train_periods": len(f["train_periods"]),
                "n_val_periods": len(f["val_periods"]),
                "n_test_periods": len(f["test_periods"]),
            }
            for f in folds
        ]
    )

    return {
        "config": cfg,
        "wrangling_report": wr_report,
        "folds": fold_meta_df,
        "backtesting_detail": detail,
        "backtesting_summary": summary,
        "winner_by_fold": winner_by_fold,
        "predicciones_backtesting": pred_detail,
        "pilot_backtesting": pilot_detail,
        "segment_error_backtesting": segment_detail,
    }


def save_backtesting_outputs(result: dict, artifacts_dir: Path):
    artifacts_dir.mkdir(exist_ok=True, parents=True)

    result["folds"].to_csv(artifacts_dir / "backtesting_folds.csv", index=False)
    result["backtesting_detail"].to_csv(artifacts_dir / "backtesting_rolling_detail.csv", index=False)
    result["backtesting_summary"].to_csv(artifacts_dir / "backtesting_rolling_summary.csv", index=False)
    result["winner_by_fold"].to_csv(artifacts_dir / "backtesting_winner_by_fold.csv", index=False)
    result["predicciones_backtesting"].to_csv(artifacts_dir / "predicciones_backtesting_rolling.csv", index=False)
    result["pilot_backtesting"].to_csv(artifacts_dir / "pilot_backtesting_pt_top.csv", index=False)

    if isinstance(result["segment_error_backtesting"], pd.DataFrame) and len(result["segment_error_backtesting"]) > 0:
        result["segment_error_backtesting"].to_csv(
            artifacts_dir / "segment_error_backtesting.csv",
            index=False,
        )

    result["wrangling_report"].to_csv(artifacts_dir / "wrangling_report_backtesting.csv", index=False)