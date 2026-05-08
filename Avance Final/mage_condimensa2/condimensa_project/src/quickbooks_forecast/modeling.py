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

try:
    import shap
except Exception:  # pragma: no cover - dependencia opcional en runtime
    shap = None

try:
    import matplotlib.pyplot as plt
except Exception:  # pragma: no cover - dependencia opcional en runtime
    plt = None

from .exogenous import add_exogenous_features
from .features import EXOGENOUS_FEATURE_COLUMNS, FEATURE_COLUMNS, MISSING_SIGNAL_COLUMNS, make_features
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

PREDICTION_KEY_COLUMNS = ["source_type", "product_id", "periodo"]


def _last_non_null(series: pd.Series) -> Any:
    clean = series.dropna()
    if clean.empty:
        return np.nan
    return clean.iloc[-1]


def _any_true(series: pd.Series) -> bool:
    clean = series.dropna()
    if clean.empty:
        return False
    return bool(clean.map(lambda value: str(value).strip().lower() in {"1", "true", "si", "sí", "yes"}).any())


def _join_unique_strings(series: pd.Series) -> str:
    values: list[str] = []
    for value in series.dropna():
        for part in str(value).split(","):
            clean = part.strip()
            if clean and clean.lower() != "nan" and clean not in values:
                values.append(clean)
    return ",".join(values)


def _priority_for_product(series: pd.Series) -> str:
    priorities = series.fillna("normal").astype(str).str.strip().str.lower()
    return "alta" if priorities.eq("alta").any() else "normal"


def _dedupe_high_error_for_merge(high_error: pd.DataFrame) -> pd.DataFrame:
    if high_error.empty:
        return pd.DataFrame(columns=["product_id", "error_absoluto_total", "wape_producto", "prioridad_revision"])
    required = {"product_id", "error_absoluto_total", "wape_producto", "prioridad_revision"}
    missing = sorted(required - set(high_error.columns))
    if missing:
        raise ValueError(f"high_error_products no tiene columnas requeridas: {missing}")

    clean = high_error.copy()
    clean["error_absoluto_total"] = pd.to_numeric(clean["error_absoluto_total"], errors="coerce").fillna(0.0)
    clean["wape_producto"] = pd.to_numeric(clean["wape_producto"], errors="coerce")
    if "cantidad_real_total" in clean.columns:
        clean["cantidad_real_total"] = pd.to_numeric(clean["cantidad_real_total"], errors="coerce").fillna(0.0)

    grouped = (
        clean.groupby("product_id", as_index=False)
        .agg(
            error_absoluto_total=("error_absoluto_total", "sum"),
            wape_producto=("wape_producto", "max"),
            prioridad_revision=("prioridad_revision", _priority_for_product),
        )
    )
    if "cantidad_real_total" in clean.columns:
        totals = clean.groupby("product_id", as_index=False)["cantidad_real_total"].sum()
        grouped = grouped.merge(totals, on="product_id", how="left", validate="1:1")
        grouped["wape_producto"] = np.where(
            grouped["cantidad_real_total"].gt(0),
            grouped["error_absoluto_total"] / grouped["cantidad_real_total"],
            grouped["wape_producto"],
        )
        grouped = grouped.drop(columns=["cantidad_real_total"])
    return grouped[["product_id", "error_absoluto_total", "wape_producto", "prioridad_revision"]]


def _assert_unique_prediction_keys(predictions_df: pd.DataFrame, context: str) -> None:
    missing = [col for col in PREDICTION_KEY_COLUMNS if col not in predictions_df.columns]
    if missing:
        raise ValueError(f"{context} no tiene columnas llave requeridas: {missing}")
    duplicates = predictions_df.duplicated(PREDICTION_KEY_COLUMNS, keep=False)
    if duplicates.any():
        sample = predictions_df.loc[duplicates, PREDICTION_KEY_COLUMNS].head(10).to_dict("records")
        raise ValueError(
            f"{context} contiene {int(duplicates.sum())} filas duplicadas por "
            f"{' + '.join(PREDICTION_KEY_COLUMNS)}. Ejemplos: {sample}"
        )


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
            ["source_type", "product_id"],
            as_index=False,
        )
        .agg(
            product_name=("product_name", _last_non_null),
            estado_producto=("estado_producto", _last_non_null),
            es_estacional=("es_estacional", _any_true),
            meses_estacionales=("meses_estacionales", _join_unique_strings),
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


def _automation_thresholds(config: dict[str, Any]) -> dict[str, Any]:
    cfg = dict(config.get("decision", {}).get("automation_thresholds", {}))
    return {
        "max_segment_wape": float(cfg.get("max_segment_wape", 0.10)),
        "max_segment_wape_std": float(cfg.get("max_segment_wape_std", 0.03)),
        "min_folds_below_wape_threshold": float(cfg.get("min_folds_below_wape_threshold", 0.67)),
        "min_confidence": str(cfg.get("min_confidence", "media")).strip().lower(),
        "allow_seasonal_auto": bool(cfg.get("allow_seasonal_auto", False)),
    }


def _confidence_thresholds(config: dict[str, Any]) -> dict[str, float]:
    cfg = dict(config.get("decision", {}).get("confidence_thresholds", {}))
    return {
        "alta_max_risk": float(cfg.get("alta_max_risk", 0.09)),
        "media_max_risk": float(cfg.get("media_max_risk", 0.16)),
        "segment_std_weight": float(cfg.get("segment_std_weight", 1.0)),
        "seasonal_penalty": float(cfg.get("seasonal_penalty", 0.01)),
        "priority_penalty": float(cfg.get("priority_penalty", 0.01)),
    }


def _make_model_by_name(
    config: dict[str, Any],
    model_name: str,
    hgb_tuned_params: dict[str, Any],
) -> TransformedTargetRegressor:
    if model_name == "hist_gradient_boosting_tuned":
        return _make_hgb_model(config, hgb_tuned_params)
    if model_name == "hist_gradient_boosting":
        return _make_hgb_model(config)
    if model_name in {"random_forest", "random_forest_conservative", "extra_trees"}:
        return _make_tree_ensemble_model(config, model_name)
    if model_name in {"linear_regression", "ridge_regression", "sgd_gradient_regression"}:
        return _make_linear_model(config, model_name)
    raise ValueError(f"Modelo no soportado para walk-forward: {model_name}")


def _walk_forward_folds(
    config: dict[str, Any],
    features: pd.DataFrame,
) -> list[tuple[int, pd.DataFrame, pd.DataFrame, pd.Timestamp, pd.Timestamp]]:
    wf_cfg = dict(config["model"].get("walk_forward", {}))
    if not bool(wf_cfg.get("enabled", True)):
        return []

    windows = int(wf_cfg.get("windows", 6))
    step_months = int(wf_cfg.get("step_months", 1))
    test_months = int(wf_cfg.get("test_months", config["model"].get("test_months", 3)))
    min_train_rows = int(config["model"]["min_rows_to_train"])
    if windows <= 0 or step_months <= 0 or test_months <= 0:
        return []

    periods = sorted(pd.to_datetime(features["periodo"].dropna()).unique())
    if not periods:
        return []
    latest_period = pd.Timestamp(periods[-1])

    folds = []
    for idx in range(windows):
        shift = (windows - 1 - idx) * step_months
        test_start = latest_period - pd.DateOffset(months=(test_months - 1) + shift)
        test_end = test_start + pd.DateOffset(months=test_months - 1)
        train_df = features[features["periodo"].lt(test_start)].copy()
        test_df = features[features["periodo"].ge(test_start) & features["periodo"].le(test_end)].copy()
        if train_df.shape[0] < min_train_rows or test_df.empty:
            continue
        folds.append((idx + 1, train_df, test_df, test_start, test_end))
    return folds


def _segment_masks(backtest: pd.DataFrame) -> dict[str, pd.Series]:
    active = backtest["estado_producto"].eq("activo")
    seasonal = backtest["es_estacional"].fillna(False).astype(bool)
    product_volume = (
        backtest.groupby("product_id", as_index=False)["target_qty"]
        .sum()
        .sort_values("target_qty", ascending=False)
    )
    if product_volume["target_qty"].sum() > 0:
        product_volume["cum_share"] = product_volume["target_qty"].cumsum() / product_volume["target_qty"].sum()
    else:
        product_volume["cum_share"] = 0.0
    top20 = set(product_volume[product_volume["cum_share"].le(0.20)]["product_id"])
    top50 = set(product_volume[product_volume["cum_share"].le(0.50)]["product_id"])

    return {
        "todos": backtest["product_id"].notna(),
        "activos": active,
        "inactivos": backtest["estado_producto"].eq("inactivo"),
        "estacionales": seasonal,
        "no_estacionales": ~seasonal,
        "activos_estacionales": active & seasonal,
        "activos_no_estacionales": active & ~seasonal,
        "top_20pct_volumen": backtest["product_id"].isin(top20),
        "top_50pct_volumen": backtest["product_id"].isin(top50),
    }


def _walk_forward_backtest(
    config: dict[str, Any],
    source: str,
    features: pd.DataFrame,
    selected_model_name: str,
    hgb_tuned_params: dict[str, Any],
    feature_columns: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    folds = _walk_forward_folds(config, features)
    if not folds:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    model_factory = lambda: _make_model_by_name(config, selected_model_name, hgb_tuned_params)
    row_frames = []
    for fold_id, train_df, test_df, test_start, test_end in folds:
        model = model_factory()
        pred = _fit_predict(model, train_df, test_df, feature_columns)
        pred = _cap_predictions(config, test_df, pred)
        fold = test_df[
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
        fold["prediction"] = pred
        fold["abs_error"] = (fold["target_qty"] - fold["prediction"]).abs()
        fold["model_name"] = selected_model_name
        fold["source"] = source
        fold["fold_id"] = int(fold_id)
        fold["test_from"] = test_start.date().isoformat()
        fold["test_until"] = test_end.date().isoformat()
        row_frames.append(fold)

    backtest = pd.concat(row_frames, ignore_index=True)
    thresholds = _automation_thresholds(config)
    segment_rows = []
    for fold_id, fold_df in backtest.groupby("fold_id", sort=True):
        for segment, mask in _segment_masks(fold_df).items():
            seg_df = fold_df[mask]
            if seg_df.empty:
                continue
            metrics = _metrics(seg_df["target_qty"].to_numpy(), seg_df["prediction"].to_numpy())
            metrics.update(
                {
                    "source": source,
                    "model_name": selected_model_name,
                    "fold_id": int(fold_id),
                    "segmento": segment,
                    "rows": int(seg_df.shape[0]),
                    "test_from": str(seg_df["test_from"].iloc[0]),
                    "test_until": str(seg_df["test_until"].iloc[0]),
                    "wape_threshold": thresholds["max_segment_wape"],
                    "fold_below_wape_threshold": float(metrics["wape"] <= thresholds["max_segment_wape"]),
                }
            )
            segment_rows.append(metrics)

    segment_by_fold = pd.DataFrame(segment_rows)
    if segment_by_fold.empty:
        return backtest, pd.DataFrame(), pd.DataFrame()

    summary = (
        segment_by_fold.groupby(["source", "model_name", "segmento"], as_index=False)
        .agg(
            folds=("fold_id", "nunique"),
            rows_total=("rows", "sum"),
            mean_wape=("wape", "mean"),
            std_wape=("wape", "std"),
            max_wape=("wape", "max"),
            min_wape=("wape", "min"),
            mean_mae=("mae", "mean"),
            mean_rmse=("rmse", "mean"),
            pct_folds_below_wape_threshold=("fold_below_wape_threshold", "mean"),
        )
    )
    summary["std_wape"] = summary["std_wape"].fillna(0.0)
    summary["wape_threshold"] = thresholds["max_segment_wape"]
    summary["std_wape_threshold"] = thresholds["max_segment_wape_std"]
    summary["pct_folds_threshold"] = thresholds["min_folds_below_wape_threshold"]
    summary["segmento_apto_automatizacion"] = (
        summary["mean_wape"].le(thresholds["max_segment_wape"])
        & summary["std_wape"].le(thresholds["max_segment_wape_std"])
        & summary["pct_folds_below_wape_threshold"].ge(thresholds["min_folds_below_wape_threshold"])
    )
    if not thresholds["allow_seasonal_auto"]:
        seasonal_mask = summary["segmento"].isin(["estacionales", "activos_estacionales"])
        summary.loc[seasonal_mask, "segmento_apto_automatizacion"] = False
    summary = summary.sort_values(["source", "segmento"]).reset_index(drop=True)
    return backtest, segment_by_fold, summary


def _write_operational_thresholds_report(config: dict[str, Any], reports_dir: Path) -> None:
    summary_path = reports_dir / "walk_forward_segment_summary_all.csv"
    if not summary_path.exists():
        return
    summary = pd.read_csv(summary_path)
    if summary.empty:
        return
    thresholds = _automation_thresholds(config)
    lines = [
        "# Umbrales operativos de automatizacion",
        "",
        "## Reglas formales",
        f"- max_segment_wape: {thresholds['max_segment_wape']:.3f}",
        f"- max_segment_wape_std: {thresholds['max_segment_wape_std']:.3f}",
        f"- min_folds_below_wape_threshold: {thresholds['min_folds_below_wape_threshold']:.2f}",
        f"- min_confidence: {thresholds['min_confidence']}",
        f"- allow_seasonal_auto: {thresholds['allow_seasonal_auto']}",
        "",
        "## Segmentos aptos segun walk-forward",
    ]
    for source in sorted(summary["source"].unique()):
        rows = summary[summary["source"].eq(source)].copy()
        apt = rows[rows["segmento_apto_automatizacion"].astype(bool)]
        no_apt = rows[~rows["segmento_apto_automatizacion"].astype(bool)]
        lines.append("")
        lines.append(f"### {source}")
        lines.append(f"- Aptos: {', '.join(apt['segmento'].tolist()) if not apt.empty else 'ninguno'}")
        lines.append(f"- No aptos: {', '.join(no_apt['segmento'].tolist()) if not no_apt.empty else 'ninguno'}")
    (reports_dir / "operational_thresholds_policy.md").write_text("\n".join(lines), encoding="utf-8")


def _write_shap_reports(
    config: dict[str, Any],
    source: str,
    selected_model_name: str,
    selected_model: TransformedTargetRegressor,
    eval_df: pd.DataFrame,
    feature_columns: list[str],
) -> None:
    reports_dir = config["resolved_paths"]["reports_dir"]
    top_products = int(config.get("decision", {}).get("explainability", {}).get("top_products", 20))
    top_features = int(config.get("decision", {}).get("explainability", {}).get("top_features_per_product", 5))

    base_lines = [
        f"# SHAP de modelo {source}",
        "",
        f"- Modelo seleccionado: `{selected_model_name}`",
        f"- Filas explicadas: {int(eval_df.shape[0])}",
        f"- Features activas: {len(feature_columns)}",
    ]

    supported_models = (RandomForestRegressor, ExtraTreesRegressor, HistGradientBoostingRegressor)
    fitted = getattr(selected_model, "regressor_", None)
    if shap is None:
        base_lines += [
            "",
            "No se genero SHAP porque la libreria `shap` no esta instalada en el entorno.",
            "Instala con: `pip install shap` y vuelve a correr entrenamiento.",
        ]
        (reports_dir / f"shap_explainability_{source.lower()}.md").write_text("\n".join(base_lines), encoding="utf-8")
        return
    if fitted is None or not isinstance(fitted, supported_models):
        base_lines += [
            "",
            "No se genero SHAP porque el modelo seleccionado no es de arboles compatible con TreeExplainer.",
        ]
        (reports_dir / f"shap_explainability_{source.lower()}.md").write_text("\n".join(base_lines), encoding="utf-8")
        return

    X_eval = eval_df[feature_columns].copy()
    explainer = shap.TreeExplainer(fitted)
    shap_values = explainer.shap_values(X_eval)
    if isinstance(shap_values, list):
        shap_values = shap_values[0]
    shap_values = np.asarray(shap_values)

    global_importance = pd.DataFrame(
        {
            "source": source,
            "model_name": selected_model_name,
            "feature": feature_columns,
            "mean_abs_shap": np.abs(shap_values).mean(axis=0),
            "mean_shap": shap_values.mean(axis=0),
        }
    ).sort_values("mean_abs_shap", ascending=False)
    global_importance["rank"] = range(1, global_importance.shape[0] + 1)
    global_importance.to_csv(
        reports_dir / f"shap_global_importance_{source.lower()}.csv",
        index=False,
        encoding="utf-8",
    )

    eval_with_idx = eval_df[["product_id", "product_name", "target_qty"]].copy()
    eval_with_idx["row_id"] = np.arange(eval_with_idx.shape[0])
    top_products_df = (
        eval_with_idx.groupby(["product_id", "product_name"], as_index=False)["target_qty"]
        .sum()
        .sort_values("target_qty", ascending=False)
        .head(top_products)
    )

    top_rows = []
    for product in top_products_df.itertuples(index=False):
        mask = eval_with_idx["product_id"].eq(product.product_id)
        if not mask.any():
            continue
        product_idx = eval_with_idx.loc[mask, "row_id"].to_numpy(dtype=int)
        product_shap = shap_values[product_idx, :]
        product_df = pd.DataFrame(
            {
                "source": source,
                "model_name": selected_model_name,
                "product_id": product.product_id,
                "product_name": product.product_name,
                "target_qty_total": float(product.target_qty),
                "feature": feature_columns,
                "mean_abs_shap": np.abs(product_shap).mean(axis=0),
                "mean_shap": product_shap.mean(axis=0),
            }
        ).sort_values("mean_abs_shap", ascending=False)
        product_df = product_df.head(top_features)
        product_df["direction"] = np.where(product_df["mean_shap"].ge(0), "incrementa", "reduce")
        top_rows.append(product_df)

    top_products_report = pd.concat(top_rows, ignore_index=True) if top_rows else pd.DataFrame()
    top_products_report.to_csv(
        reports_dir / f"shap_top_products_{source.lower()}.csv",
        index=False,
        encoding="utf-8",
    )

    if plt is not None:
        top_global_plot = global_importance.head(15).copy().iloc[::-1]
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.barh(top_global_plot["feature"], top_global_plot["mean_abs_shap"], color="#2E86AB")
        ax.set_title(f"SHAP global {source} ({selected_model_name})")
        ax.set_xlabel("mean_abs_shap")
        ax.set_ylabel("feature")
        fig.tight_layout()
        fig.savefig(reports_dir / f"shap_global_importance_{source.lower()}.png", dpi=180)
        plt.close(fig)

        if not top_products_report.empty:
            top_product_ids = (
                top_products_report.groupby(["product_id", "product_name"], as_index=False)["target_qty_total"]
                .max()
                .sort_values("target_qty_total", ascending=False)
                .head(10)
            )
            selected_rows = top_products_report[top_products_report["product_id"].isin(top_product_ids["product_id"])].copy()
            selected_rows["product_label"] = selected_rows["product_name"].astype(str).str.slice(0, 28)
            pivot = selected_rows.pivot_table(
                index="product_label",
                columns="feature",
                values="mean_abs_shap",
                aggfunc="mean",
                fill_value=0.0,
            )
            if not pivot.empty:
                fig, ax = plt.subplots(figsize=(12, 7))
                im = ax.imshow(pivot.to_numpy(), aspect="auto", cmap="Blues")
                ax.set_title(f"SHAP top productos {source}")
                ax.set_xticks(range(len(pivot.columns)))
                ax.set_xticklabels(pivot.columns, rotation=45, ha="right", fontsize=8)
                ax.set_yticks(range(len(pivot.index)))
                ax.set_yticklabels(pivot.index, fontsize=8)
                fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
                fig.tight_layout()
                fig.savefig(reports_dir / f"shap_top_products_{source.lower()}.png", dpi=180)
                plt.close(fig)

    top_global = global_importance.head(10)
    base_lines += [
        "",
        "## Nota tecnica",
        "SHAP se calcula sobre el estimador interno del `TransformedTargetRegressor`.",
        "La magnitud de SHAP refleja contribucion en la escala interna del modelo (transformacion log1p).",
        "Si `matplotlib` esta disponible, tambien se generan graficos PNG en esta misma carpeta.",
        "",
        "## Top 10 features globales por impacto",
    ]
    for row in top_global.itertuples(index=False):
        base_lines.append(f"- {row.feature}: mean_abs_shap={row.mean_abs_shap:.6f}")

    (reports_dir / f"shap_explainability_{source.lower()}.md").write_text("\n".join(base_lines), encoding="utf-8")


def _compute_learning_curve(
    config: dict[str, Any],
    source: str,
    selected_model_name: str,
    hgb_tuned_params: dict[str, Any],
    train_df: pd.DataFrame,
    validation_df: pd.DataFrame,
    feature_columns: list[str],
) -> pd.DataFrame:
    cfg = dict(config["model"].get("learning_curves", {}))
    if not bool(cfg.get("enabled", True)):
        return pd.DataFrame()

    points = int(cfg.get("points", 8))
    min_frac = float(cfg.get("min_train_fraction", 0.20))
    min_rows = int(config["model"]["min_rows_to_train"])
    if points <= 1:
        points = 2

    ordered = train_df.sort_values(["periodo", "product_id"]).copy()
    periods = sorted(pd.to_datetime(ordered["periodo"].dropna()).unique())
    if len(periods) < 2 or validation_df.empty:
        return pd.DataFrame()

    start_idx = max(0, int(np.floor((len(periods) - 1) * min_frac)))
    candidate_idx = np.linspace(start_idx, len(periods) - 1, num=points, dtype=int)
    candidate_idx = sorted(set(int(i) for i in candidate_idx))

    rows = []
    for idx, period_idx in enumerate(candidate_idx, start=1):
        cutoff = pd.Timestamp(periods[period_idx])
        train_slice = ordered[ordered["periodo"].le(cutoff)].copy()
        if train_slice.shape[0] < min_rows:
            continue

        model = _make_model_by_name(config, selected_model_name, hgb_tuned_params)
        pred_train = _fit_predict(model, train_slice, train_slice, feature_columns)
        pred_val = _fit_predict(model, train_slice, validation_df, feature_columns)
        pred_train = _cap_predictions(config, train_slice, pred_train)
        pred_val = _cap_predictions(config, validation_df, pred_val)

        metrics_train = _metrics(train_slice["target_qty"].to_numpy(), pred_train)
        metrics_val = _metrics(validation_df["target_qty"].to_numpy(), pred_val)
        rows.append(
            {
                "source": source,
                "model_name": selected_model_name,
                "curve_point": idx,
                "train_until": cutoff.date().isoformat(),
                "train_rows": int(train_slice.shape[0]),
                "train_periods": int(train_slice["periodo"].nunique()),
                "validation_rows": int(validation_df.shape[0]),
                "validation_period_from": validation_df["periodo"].min().date().isoformat(),
                "validation_period_until": validation_df["periodo"].max().date().isoformat(),
                "wape_train": metrics_train["wape"],
                "wape_validation": metrics_val["wape"],
                "mae_train": metrics_train["mae"],
                "mae_validation": metrics_val["mae"],
                "rmse_train": metrics_train["rmse"],
                "rmse_validation": metrics_val["rmse"],
                "smape_train": metrics_train["smape"],
                "smape_validation": metrics_val["smape"],
                "wape_gap": metrics_val["wape"] - metrics_train["wape"],
            }
        )

    return pd.DataFrame(rows)


def _write_learning_curve_report(reports_dir: Path, source: str, curve_df: pd.DataFrame) -> None:
    if curve_df.empty:
        (reports_dir / f"learning_curve_{source.lower()}.md").write_text(
            f"# Learning Curve {source}\n\nNo se pudo generar curva de aprendizaje.",
            encoding="utf-8",
        )
        return

    ordered = curve_df.sort_values("train_rows").reset_index(drop=True)
    best_row = ordered.loc[ordered["wape_validation"].idxmin()]
    last_row = ordered.iloc[-1]
    first_row = ordered.iloc[0]

    trend = "mejora" if last_row["wape_validation"] <= first_row["wape_validation"] else "empeora"
    gap_flag = "estable" if float(last_row["wape_gap"]) <= 0.03 else "riesgo_sobreajuste"

    lines = [
        f"# Learning Curve {source}",
        "",
        f"- Puntos evaluados: {int(ordered.shape[0])}",
        f"- WAPE validacion inicial: {float(first_row['wape_validation']):.6f}",
        f"- WAPE validacion final: {float(last_row['wape_validation']):.6f}",
        f"- Tendencia global: {trend}",
        f"- Mejor punto: train_rows={int(best_row['train_rows'])}, wape_validation={float(best_row['wape_validation']):.6f}",
        f"- Gap final (val - train): {float(last_row['wape_gap']):.6f} ({gap_flag})",
    ]
    (reports_dir / f"learning_curve_{source.lower()}.md").write_text("\n".join(lines), encoding="utf-8")


def _write_learning_curve_summary(reports_dir: Path, combined_curve_df: pd.DataFrame) -> None:
    if combined_curve_df.empty:
        (reports_dir / "learning_curve_summary.md").write_text(
            "# Learning Curves\n\nNo hay datos de curva de aprendizaje.",
            encoding="utf-8",
        )
        return

    lines = ["# Learning Curves", ""]
    for source in sorted(combined_curve_df["source"].unique()):
        subset = combined_curve_df[combined_curve_df["source"].eq(source)].sort_values("train_rows")
        first = subset.iloc[0]
        last = subset.iloc[-1]
        best = subset.loc[subset["wape_validation"].idxmin()]
        lines += [
            f"## {source}",
            f"- WAPE validacion inicial: {float(first['wape_validation']):.6f}",
            f"- WAPE validacion final: {float(last['wape_validation']):.6f}",
            f"- Mejor punto: train_rows={int(best['train_rows'])}, wape_validation={float(best['wape_validation']):.6f}",
            f"- Gap final (val - train): {float(last['wape_gap']):.6f}",
            "",
        ]
    (reports_dir / "learning_curve_summary.md").write_text("\n".join(lines), encoding="utf-8")


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
        if col in EXOGENOUS_FEATURE_COLUMNS or col in MISSING_SIGNAL_COLUMNS:
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


def _temporal_cv_folds(config: dict[str, Any], base_df: pd.DataFrame) -> list[tuple[pd.DataFrame, pd.DataFrame, pd.Timestamp, pd.Timestamp]]:
    cv_cfg = dict(config["model"].get("temporal_cv", {}))
    if not bool(cv_cfg.get("enabled", True)):
        return []

    folds = int(cv_cfg.get("folds", 3))
    val_months = int(cv_cfg.get("validation_months", config["model"].get("validation_months", 3)))
    min_train_rows = int(config["model"]["min_rows_to_train"])
    if folds <= 0 or val_months <= 0:
        return []

    periods = sorted(pd.to_datetime(base_df["periodo"].dropna()).unique())
    if not periods:
        return []

    out: list[tuple[pd.DataFrame, pd.DataFrame, pd.Timestamp, pd.Timestamp]] = []
    for offset in range(folds, 0, -1):
        val_start_idx = len(periods) - (offset * val_months)
        val_end_idx = val_start_idx + val_months - 1
        if val_start_idx <= 0 or val_end_idx >= len(periods):
            continue

        val_start = pd.Timestamp(periods[val_start_idx])
        val_end = pd.Timestamp(periods[val_end_idx])
        train_fold = base_df[base_df["periodo"].lt(val_start)].copy()
        val_fold = base_df[base_df["periodo"].ge(val_start) & base_df["periodo"].le(val_end)].copy()
        if train_fold.shape[0] < min_train_rows or val_fold.empty:
            continue
        out.append((train_fold, val_fold, val_start, val_end))
    return out


def _temporal_cv_model_comparison(
    config: dict[str, Any],
    source: str,
    base_df: pd.DataFrame,
    hgb_tuned_params: dict[str, Any],
    feature_columns: list[str],
) -> pd.DataFrame:
    folds = _temporal_cv_folds(config, base_df)
    if not folds:
        return pd.DataFrame()

    truth_by_model: dict[str, list[np.ndarray]] = {}
    pred_by_model: dict[str, list[np.ndarray]] = {}

    for train_fold, val_fold, _, _ in folds:
        fold_predictions = _candidate_predictions(config, train_fold, val_fold, hgb_tuned_params, feature_columns)
        y_true = val_fold["target_qty"].to_numpy()
        for model_name, y_pred in fold_predictions.items():
            clean_pred = _cap_predictions(config, val_fold, y_pred)
            truth_by_model.setdefault(model_name, []).append(y_true)
            pred_by_model.setdefault(model_name, []).append(clean_pred)

    metric = str(config["model"].get("selection_metric", "wape"))
    rows = []
    for model_name in sorted(truth_by_model.keys()):
        y_true_all = np.concatenate(truth_by_model[model_name])
        y_pred_all = np.concatenate(pred_by_model[model_name])
        metric_values = _metrics(y_true_all, y_pred_all)
        metric_values.update(
            {
                "source": source,
                "model_name": model_name,
                "split": "temporal_cv",
                "rows": int(len(y_true_all)),
                "folds": int(len(folds)),
                "period_from": min(start for _, _, start, _ in folds).date().isoformat(),
                "period_until": max(end for _, _, _, end in folds).date().isoformat(),
                "selected_for_forecast": False,
            }
        )
        rows.append(metric_values)

    comparison = pd.DataFrame(rows).sort_values(metric).reset_index(drop=True)
    comparison["rank_wape"] = range(1, comparison.shape[0] + 1)
    return comparison


def _tune_hgb(
    config: dict[str, Any],
    train_df: pd.DataFrame,
    validation_df: pd.DataFrame,
    source: str,
    feature_columns: list[str],
    tuning_base_df: pd.DataFrame | None = None,
) -> tuple[dict[str, Any], pd.DataFrame]:
    metric = str(config["model"].get("selection_metric", "wape"))
    rows = []
    base_for_cv = tuning_base_df if tuning_base_df is not None else pd.concat([train_df, validation_df], ignore_index=True)
    cv_folds = _temporal_cv_folds(config, base_for_cv)

    for idx, params in enumerate(_hgb_tuning_candidates(config), start=1):
        if cv_folds:
            fold_truth = []
            fold_pred = []
            for train_fold, val_fold, _, _ in cv_folds:
                model = _make_hgb_model(config, params)
                pred = _fit_predict(model, train_fold, val_fold, feature_columns)
                pred = _cap_predictions(config, val_fold, pred)
                fold_truth.append(val_fold["target_qty"].to_numpy())
                fold_pred.append(pred)

            y_true_all = np.concatenate(fold_truth)
            y_pred_all = np.concatenate(fold_pred)
            metric_values = _metrics(y_true_all, y_pred_all)
            rows.append(
                {
                    "source": source,
                    "candidate": idx,
                    **params,
                    **metric_values,
                    "rows_train": int(min(train_fold.shape[0] for train_fold, _, _, _ in cv_folds)),
                    "rows_validation": int(sum(val_fold.shape[0] for _, val_fold, _, _ in cv_folds)),
                    "split": "temporal_cv",
                    "folds": int(len(cv_folds)),
                    "period_from": min(start for _, _, start, _ in cv_folds).date().isoformat(),
                    "period_until": max(end for _, _, _, end in cv_folds).date().isoformat(),
                }
            )
        else:
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
                    "split": "validation",
                    "folds": 1,
                    "period_from": validation_df["periodo"].min().date().isoformat(),
                    "period_until": validation_df["periodo"].max().date().isoformat(),
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
    temporal_cv_comparison: pd.DataFrame | None = None,
) -> str:
    del test_comparison
    configured = str(config["model"].get("forecast_model", "best_ml_temporal_cv"))
    metric = str(config["model"].get("selection_metric", "wape"))

    if configured in ML_MODEL_NAMES:
        return configured
    if configured in {"best_ml_temporal_cv", "best_temporal_cv"}:
        if temporal_cv_comparison is not None and not temporal_cv_comparison.empty:
            temporal_ml = temporal_cv_comparison[temporal_cv_comparison["model_name"].isin(ML_MODEL_NAMES)]
            return str(temporal_ml.sort_values(metric).iloc[0]["model_name"])
        validation_ml = validation_comparison[validation_comparison["model_name"].isin(ML_MODEL_NAMES)]
        return str(validation_ml.sort_values(metric).iloc[0]["model_name"])
    if configured in {"best_ml_validation", "best_validation", "best_ml_stable"}:
        validation_ml = validation_comparison[validation_comparison["model_name"].isin(ML_MODEL_NAMES)]
        return str(validation_ml.sort_values(metric).iloc[0]["model_name"])
    if configured in {"best_ml_test", "best_test"}:
        raise ValueError(
            "Estrategia best_ml_test deshabilitada para evitar leakage: "
            "la seleccion del modelo solo puede usar validacion."
        )
    raise ValueError(f"Estrategia forecast_model no soportada: {configured}")


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
    features = make_features(
        monthly,
        products,
        inactive_months=int(config["dataset"]["inactive_months"]),
        seasonal_top_3_month_share=float(config["dataset"]["seasonal_top_3_month_share"]),
        seasonal_max_active_months_per_year=int(config["dataset"]["seasonal_max_active_months_per_year"]),
    )
    if {"estado_producto", "ultima_actividad", "periodo"}.issubset(features.columns):
        features["ultima_actividad"] = pd.to_datetime(features["ultima_actividad"], errors="coerce")
        inactive_trailing_mask = (
            features["estado_producto"].eq("inactivo")
            & features["ultima_actividad"].notna()
            & features["periodo"].gt(features["ultima_actividad"])
        )
        features = features[~inactive_trailing_mask].copy()
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

    hgb_tuned_params, tuning_results = _tune_hgb(
        config,
        train_df,
        validation_df,
        source,
        feature_columns,
        tuning_base_df=pre_test_df,
    )
    validation_predictions = _candidate_predictions(config, train_df, validation_df, hgb_tuned_params, feature_columns)
    validation_comparison, _ = _evaluate_predictions(
        config,
        source,
        validation_df,
        validation_predictions,
        split_name="validation",
    )
    temporal_cv_comparison = _temporal_cv_model_comparison(
        config,
        source,
        pre_test_df,
        hgb_tuned_params,
        feature_columns,
    )
    if temporal_cv_comparison.empty:
        temporal_cv_comparison = validation_comparison.copy()
        temporal_cv_comparison["split"] = "temporal_cv_fallback_validation"
        temporal_cv_comparison["folds"] = 0
    selection_metric = str(config["model"].get("selection_metric", "wape"))

    test_predictions = _candidate_predictions(config, pre_test_df, test_df, hgb_tuned_params, feature_columns)
    comparison, backtest = _evaluate_predictions(
        config,
        source,
        test_df,
        test_predictions,
        split_name="test",
    )
    selected_model_name = _choose_model_from_comparisons(
        config,
        validation_comparison,
        comparison,
        temporal_cv_comparison=temporal_cv_comparison,
    )
    validation_comparison["selected_for_forecast"] = validation_comparison["model_name"].eq(selected_model_name)
    comparison["selected_for_forecast"] = comparison["model_name"].eq(selected_model_name)
    if not temporal_cv_comparison.empty:
        temporal_cv_comparison["selected_for_forecast"] = temporal_cv_comparison["model_name"].eq(selected_model_name)

    learning_curve = _compute_learning_curve(
        config,
        source,
        selected_model_name,
        hgb_tuned_params,
        train_df,
        validation_df,
        feature_columns,
    )

    walk_forward_backtest, walk_forward_segment_by_fold, walk_forward_segment_summary = _walk_forward_backtest(
        config,
        source,
        features,
        selected_model_name,
        hgb_tuned_params,
        feature_columns,
    )
    high_error = _high_error_products(backtest, source, selected_model_name)
    selected_pred = _cap_predictions(config, test_df, test_predictions[selected_model_name])
    metric_values = _metrics(test_df["target_qty"].to_numpy(), selected_pred)
    metric_values.update(
        {
            "source": source,
            "selected_model_name": selected_model_name,
            "selection_metric": selection_metric,
            "train_rows": int(train_df.shape[0]),
            "pre_test_rows": int(pre_test_df.shape[0]),
            "validation_rows": int(validation_df.shape[0]),
            "test_rows": int(test_df.shape[0]),
            "train_until": train_df["periodo"].max().date().isoformat(),
            "pre_test_until": pre_test_df["periodo"].max().date().isoformat(),
            "validation_from": validation_start.date().isoformat(),
            "validation_until": validation_latest.date().isoformat(),
            "test_from": test_start.date().isoformat(),
            "test_until": latest_period.date().isoformat(),
        }
    )

    final_models = _train_final_ml_models(config, features, hgb_tuned_params, feature_columns)
    _write_shap_reports(
        config,
        source,
        selected_model_name,
        final_models[selected_model_name],
        test_df,
        feature_columns,
    )

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
    temporal_cv_comparison.to_csv(
        reports_dir / f"temporal_cv_model_comparison_{source.lower()}.csv",
        index=False,
        encoding="utf-8",
    )
    learning_curve.to_csv(
        reports_dir / f"learning_curve_{source.lower()}.csv",
        index=False,
        encoding="utf-8",
    )
    _write_learning_curve_report(reports_dir, source, learning_curve)
    walk_forward_backtest.to_csv(
        reports_dir / f"walk_forward_backtest_{source.lower()}.csv",
        index=False,
        encoding="utf-8",
    )
    walk_forward_segment_by_fold.to_csv(
        reports_dir / f"walk_forward_segment_metrics_by_fold_{source.lower()}.csv",
        index=False,
        encoding="utf-8",
    )
    walk_forward_segment_summary.to_csv(
        reports_dir / f"walk_forward_segment_summary_{source.lower()}.csv",
        index=False,
        encoding="utf-8",
    )
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
    temporal_cv_comparisons = [
        pd.read_csv(reports_dir / f"temporal_cv_model_comparison_{source.lower()}.csv")
        for source in artifacts
    ]
    walk_forward_backtests = [
        pd.read_csv(reports_dir / f"walk_forward_backtest_{source.lower()}.csv")
        for source in artifacts
    ]
    walk_forward_by_fold = [
        pd.read_csv(reports_dir / f"walk_forward_segment_metrics_by_fold_{source.lower()}.csv")
        for source in artifacts
    ]
    walk_forward_summary = [
        pd.read_csv(reports_dir / f"walk_forward_segment_summary_{source.lower()}.csv")
        for source in artifacts
    ]
    learning_curves = [
        pd.read_csv(reports_dir / f"learning_curve_{source.lower()}.csv")
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
    shap_global = []
    shap_top_products = []
    for source in artifacts:
        global_path = reports_dir / f"shap_global_importance_{source.lower()}.csv"
        top_path = reports_dir / f"shap_top_products_{source.lower()}.csv"
        if global_path.exists():
            shap_global.append(pd.read_csv(global_path))
        if top_path.exists():
            shap_top_products.append(pd.read_csv(top_path))
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
    pd.concat(temporal_cv_comparisons, ignore_index=True).to_csv(
        reports_dir / "temporal_cv_model_comparison_all.csv",
        index=False,
        encoding="utf-8",
    )
    pd.concat(walk_forward_backtests, ignore_index=True).to_csv(
        reports_dir / "walk_forward_backtest_all.csv",
        index=False,
        encoding="utf-8",
    )
    pd.concat(walk_forward_by_fold, ignore_index=True).to_csv(
        reports_dir / "walk_forward_segment_metrics_by_fold_all.csv",
        index=False,
        encoding="utf-8",
    )
    pd.concat(walk_forward_summary, ignore_index=True).to_csv(
        reports_dir / "walk_forward_segment_summary_all.csv",
        index=False,
        encoding="utf-8",
    )
    combined_learning_curves = pd.concat(learning_curves, ignore_index=True)
    combined_learning_curves.to_csv(
        reports_dir / "learning_curve_all.csv",
        index=False,
        encoding="utf-8",
    )
    _write_learning_curve_summary(reports_dir, combined_learning_curves)
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
    if shap_global:
        pd.concat(shap_global, ignore_index=True).to_csv(
            reports_dir / "shap_global_importance_all.csv",
            index=False,
            encoding="utf-8",
        )
    if shap_top_products:
        pd.concat(shap_top_products, ignore_index=True).to_csv(
            reports_dir / "shap_top_products_all.csv",
            index=False,
            encoding="utf-8",
        )
    _write_operational_thresholds_report(config, reports_dir)
    return artifacts


def _future_periods(latest_period: pd.Timestamp, horizon: int) -> list[pd.Timestamp]:
    return [latest_period + pd.DateOffset(months=i) for i in range(1, horizon + 1)]


def _selected_forecast_model(config: dict[str, Any], source: str) -> str:
    configured = str(config["model"].get("forecast_model", "best_ml_temporal_cv"))
    reports_dir = config["resolved_paths"]["reports_dir"]
    if configured in ML_MODEL_NAMES:
        return configured

    validation_path = reports_dir / f"validation_model_comparison_{source.lower()}.csv"
    if not validation_path.exists():
        return "hist_gradient_boosting_tuned"

    metric = str(config["model"].get("selection_metric", "wape"))
    validation_comparison = pd.read_csv(validation_path)
    validation_ml = validation_comparison[validation_comparison["model_name"].isin(ML_MODEL_NAMES)]

    if configured in {"best_ml_test", "best_test"}:
        raise ValueError(
            "Estrategia best_ml_test deshabilitada para evitar leakage: "
            "la seleccion del modelo solo puede usar validacion."
        )
    if configured in {"best_ml_temporal_cv", "best_temporal_cv"}:
        temporal_cv_path = reports_dir / f"temporal_cv_model_comparison_{source.lower()}.csv"
        if temporal_cv_path.exists():
            temporal_cv = pd.read_csv(temporal_cv_path)
            if not temporal_cv.empty:
                temporal_ml = temporal_cv[temporal_cv["model_name"].isin(ML_MODEL_NAMES)]
                if not temporal_ml.empty:
                    return str(temporal_ml.sort_values(metric).iloc[0]["model_name"])
        return str(validation_ml.sort_values(metric).iloc[0]["model_name"])
    if configured in {"best_ml_validation", "best_validation", "best_ml_stable"}:
        return str(validation_ml.sort_values(metric).iloc[0]["model_name"])

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
    thresholds = _automation_thresholds(config)
    confidence_cfg = _confidence_thresholds(config)
    comparison = pd.read_csv(reports_dir / f"model_comparison_{source.lower()}.csv")
    selected_metric = comparison[comparison["model_name"].eq(selected_model)]
    model_wape = float(selected_metric["wape"].iloc[0]) if not selected_metric.empty else float(comparison["wape"].min())

    high_error_path = reports_dir / f"high_error_products_{source.lower()}.csv"
    if high_error_path.exists():
        high_error = pd.read_csv(high_error_path)
        high_error = _dedupe_high_error_for_merge(high_error)
        risk_cols = [
            "product_id",
            "error_absoluto_total",
            "wape_producto",
            "prioridad_revision",
        ]
        before_rows = predictions_df.shape[0]
        predictions_df = predictions_df.merge(high_error[risk_cols], on="product_id", how="left", validate="m:1")
        if predictions_df.shape[0] != before_rows:
            raise ValueError("El merge de high_error cambio la cantidad de filas de predicciones.")
    else:
        predictions_df["error_absoluto_total"] = np.nan
        predictions_df["wape_producto"] = np.nan
        predictions_df["prioridad_revision"] = "normal"

    predictions_df["wape_producto"] = predictions_df["wape_producto"].fillna(model_wape)
    predictions_df["prioridad_revision"] = predictions_df["prioridad_revision"].fillna("normal")

    predictions_df["segmento_operativo"] = np.select(
        [
            predictions_df["estado_producto"].eq("inactivo"),
            predictions_df["es_estacional"].fillna(False).astype(bool),
        ],
        ["inactivos", "activos_estacionales"],
        default="activos_no_estacionales",
    )

    segment_summary_path = reports_dir / f"walk_forward_segment_summary_{source.lower()}.csv"
    predictions_df["segmento_apto_automatizacion"] = False
    predictions_df["wape_segmento_walk_forward"] = np.nan
    predictions_df["std_wape_segmento_walk_forward"] = np.nan
    predictions_df["pct_folds_below_wape_threshold"] = np.nan
    if segment_summary_path.exists():
        summary = pd.read_csv(segment_summary_path)
        if not summary.empty:
            summary = summary.set_index("segmento")
            predictions_df["segmento_apto_automatizacion"] = (
                predictions_df["segmento_operativo"].map(summary["segmento_apto_automatizacion"]).fillna(False).astype(bool)
            )
            predictions_df["wape_segmento_walk_forward"] = predictions_df["segmento_operativo"].map(summary["mean_wape"])
            predictions_df["std_wape_segmento_walk_forward"] = predictions_df["segmento_operativo"].map(summary["std_wape"])
            predictions_df["pct_folds_below_wape_threshold"] = predictions_df["segmento_operativo"].map(
                summary["pct_folds_below_wape_threshold"]
            )

    predictions_df["wape_segmento_walk_forward"] = pd.to_numeric(
        predictions_df["wape_segmento_walk_forward"],
        errors="coerce",
    ).fillna(model_wape)
    predictions_df["std_wape_segmento_walk_forward"] = pd.to_numeric(
        predictions_df["std_wape_segmento_walk_forward"],
        errors="coerce",
    ).fillna(0.0)
    predictions_df["pct_folds_below_wape_threshold"] = pd.to_numeric(
        predictions_df["pct_folds_below_wape_threshold"],
        errors="coerce",
    ).fillna(0.0)

    predictions_df["riesgo_confianza_base"] = pd.concat(
        [
            predictions_df["wape_producto"].clip(lower=0.0, upper=2.0),
            (
                predictions_df["wape_segmento_walk_forward"]
                + predictions_df["std_wape_segmento_walk_forward"] * confidence_cfg["segment_std_weight"]
            ).clip(lower=0.0, upper=2.0),
            pd.Series(model_wape, index=predictions_df.index),
        ],
        axis=1,
    ).max(axis=1)
    predictions_df["riesgo_confianza_ajustado"] = (
        predictions_df["riesgo_confianza_base"]
        + predictions_df["prioridad_revision"].eq("alta").astype(float) * confidence_cfg["priority_penalty"]
        + predictions_df["es_estacional"].fillna(False).astype(bool).astype(float) * confidence_cfg["seasonal_penalty"]
    ).clip(lower=0.0, upper=2.0)
    predictions_df["error_relativo_estimado"] = predictions_df["riesgo_confianza_ajustado"]
    predictions_df["prediccion_min"] = (
        predictions_df["cantidad_predicha"] * (1 - predictions_df["error_relativo_estimado"])
    ).clip(lower=0.0)
    predictions_df["prediccion_max"] = predictions_df["cantidad_predicha"] * (
        1 + predictions_df["error_relativo_estimado"]
    )
    predictions_df["confianza_prediccion"] = np.select(
        [
            predictions_df["estado_producto"].eq("inactivo"),
            predictions_df["riesgo_confianza_ajustado"].le(confidence_cfg["alta_max_risk"]),
            predictions_df["riesgo_confianza_ajustado"].le(confidence_cfg["media_max_risk"]),
        ],
        ["no_aplica", "alta", "media"],
        default="baja",
    )
    predictions_df["requiere_revision"] = (
        predictions_df["confianza_prediccion"].eq("baja")
        | predictions_df["prioridad_revision"].eq("alta")
        | predictions_df["es_estacional"].fillna(False).astype(bool)
    ) & predictions_df["estado_producto"].ne("inactivo")

    confidence_rank = {"baja": 0, "media": 1, "alta": 2}
    min_conf = thresholds["min_confidence"]
    min_conf_rank = confidence_rank.get(min_conf, 1)
    pred_conf_rank = predictions_df["confianza_prediccion"].map(confidence_rank).fillna(-1)
    predictions_df["cumple_confianza_minima"] = pred_conf_rank.ge(min_conf_rank)
    predictions_df["apto_automatizacion"] = (
        predictions_df["estado_producto"].eq("activo")
        & predictions_df["cumple_confianza_minima"]
        & predictions_df["segmento_apto_automatizacion"]
        & ~predictions_df["requiere_revision"]
    )
    if not thresholds["allow_seasonal_auto"]:
        predictions_df.loc[predictions_df["es_estacional"].fillna(False).astype(bool), "apto_automatizacion"] = False

    predictions_df["cantidad_sugerida_sin_inventario"] = predictions_df["cantidad_predicha"]
    predictions_df["recomendacion_decision"] = np.select(
        [
            predictions_df["estado_producto"].eq("inactivo"),
            predictions_df["apto_automatizacion"],
            predictions_df["requiere_revision"],
        ],
        [
            "no producir por inactividad",
            "usar como cantidad sugerida",
            "revisar antes de ordenar",
        ],
        default="revision por umbral operativo",
    )

    for col in [
        "cantidad_predicha",
        "prediccion_min",
        "prediccion_max",
        "cantidad_sugerida_sin_inventario",
        "error_relativo_estimado",
        "riesgo_confianza_base",
        "riesgo_confianza_ajustado",
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
        feature_frame = make_features(
            extended,
            products,
            inactive_months=int(config["dataset"]["inactive_months"]),
            seasonal_top_3_month_share=float(config["dataset"]["seasonal_top_3_month_share"]),
            seasonal_max_active_months_per_year=int(config["dataset"]["seasonal_max_active_months_per_year"]),
        )
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
        future_output = future_features.copy()
        if "ultima_actividad" not in future_output.columns:
            future_output = future_output.merge(
                products[["product_id", "ultima_actividad"]],
                on="product_id",
                how="left",
            )
        else:
            lookup_ultima = products.set_index("product_id")["ultima_actividad"]
            future_output["ultima_actividad"] = future_output["ultima_actividad"].where(
                future_output["ultima_actividad"].notna(),
                future_output["product_id"].map(lookup_ultima),
            )
        prediction_rows.append(future_output[output_cols])

        future_history = future_features[history.columns.intersection(future_features.columns)].copy()
        future_history["target_qty"] = future_features["cantidad_predicha"].to_numpy()
        history = pd.concat([history, future_history[history.columns]], ignore_index=True, sort=False)

    predictions_df = pd.concat(prediction_rows, ignore_index=True)
    _assert_unique_prediction_keys(predictions_df, f"predicciones_{source.lower()} antes de decision")
    predictions_df["cantidad_predicha"] = predictions_df["cantidad_predicha"].round(2)
    predictions_df = _add_decision_fields(config, source, predictions_df, selected_model)
    _assert_unique_prediction_keys(predictions_df, f"predicciones_{source.lower()} despues de decision")
    predictions_df = apply_inventory_adjustments(config, source, predictions_df)
    _assert_unique_prediction_keys(predictions_df, f"predicciones_{source.lower()} final")
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
