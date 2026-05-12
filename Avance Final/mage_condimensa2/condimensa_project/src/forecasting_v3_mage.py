"""Helpers para ejecutar forecasting_v3 dentro de Mage.

Centraliza nombres de datasets, expectativas minimas y utilidades de
serializacion para que el pipeline de Mage se mantenga alineado con la version
de modelado validada fuera de Mage.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


CONFIG_RELATIVE_PATH = Path("config") / "forecasting_v3.yml"

TECHNICAL_COLUMNS = {"id", "fecha_carga", "pipeline_id", "batch_id", "fecha_ejecucion"}

SILVER_DATASETS = {
    "catalogo_pt_limpio": "forecasting_v3_catalogo_pt_limpio",
    "pt_catalog_match_report": "forecasting_v3_pt_catalog_match_report",
    "pt_productos_no_catalogo": "forecasting_v3_pt_productos_no_catalogo",
    "pt_mensual_model": "forecasting_v3_pt_mensual_model",
    "pt_productos_model": "forecasting_v3_pt_productos_model",
    "pp_mensual_model": "forecasting_v3_pp_mensual_model",
    "pp_productos_model": "forecasting_v3_pp_productos_model",
}

BRONZE_DATASETS = {
    "quickbooks_produccion_raw": "quickbooks_produccion_raw",
}

PROCESSED_OUTPUTS = {
    "catalogo_pt_limpio": ("processed_dir", "catalogo_pt_limpio.csv"),
    "pt_mensual_model": ("processed_dir", "pt_mensual_model.csv"),
    "pt_productos_model": ("processed_dir", "pt_productos_model.csv"),
    "pp_mensual_model": ("processed_dir", "pp_mensual_model.csv"),
    "pp_productos_model": ("processed_dir", "pp_productos_model.csv"),
    "quickbooks_produccion_raw": ("processed_dir", "production_benchmark_raw.csv"),
    "pt_catalog_match_report": ("reports_dir", "pt_catalog_match_report.csv"),
    "pt_productos_no_catalogo": ("reports_dir", "pt_productos_no_catalogo.csv"),
}

REPORT_OUTPUTS = {
    "predicciones_pt": "predicciones_pt.csv",
    "predicciones_pp": "predicciones_pp.csv",
    "metrics_pt": "metrics_pt.csv",
    "metrics_pp": "metrics_pp.csv",
    "model_comparison_all": "model_comparison_all.csv",
    "validation_model_comparison_all": "validation_model_comparison_all.csv",
    "temporal_cv_model_comparison_all": "temporal_cv_model_comparison_all.csv",
    "backtest_pt": "backtest_pt.csv",
    "backtest_pp": "backtest_pp.csv",
    "walk_forward_backtest_all": "walk_forward_backtest_all.csv",
    "walk_forward_segment_metrics_by_fold_all": "walk_forward_segment_metrics_by_fold_all.csv",
    "walk_forward_segment_summary_all": "walk_forward_segment_summary_all.csv",
    "learning_curve_all": "learning_curve_all.csv",
    "hgb_tuning_all": "hgb_tuning_all.csv",
    "high_error_products_all": "high_error_products_all.csv",
    "shap_global_importance_all": "shap_global_importance_all.csv",
    "shap_top_products_all": "shap_top_products_all.csv",
    "human_plan_benchmark": "human_plan_benchmark.csv",
    "operational_segments_error": "operational_segments_error.csv",
}

PREDICTION_KEY_COLUMNS = ["source_type", "product_id", "periodo"]
GOLD_PREDICTION_KEY_COLUMNS = ["tipo_producto", "product_id", "periodo_prediccion"]

FORECASTING_V3_DATASET_EXPECTATIONS = {
    # Referencia tomada del modelado validado en Modelado/forecasting_v3.
    "pt_mensual_model": {
        "min_rows": 25000,
        "min_products": 800,
        "min_target_sum": 75000000,
        "min_period_until": "2026-03-01",
    },
    "pt_productos_model": {
        "min_rows": 800,
        "min_products": 800,
    },
    "pp_mensual_model": {
        "min_rows": 3500,
        "min_products": 220,
        "min_target_sum": 30000000,
        "min_period_until": "2026-02-01",
    },
    "pp_productos_model": {
        "min_rows": 220,
        "min_products": 220,
    },
}

DATE_COLUMNS = {
    "periodo",
    "primera_actividad",
    "ultima_actividad",
    "periodo_referencia",
    "corte_inactividad",
    "ultimo_periodo_entrenamiento",
    "stock_fecha_referencia",
    "train_until",
    "validation_from",
    "validation_until",
    "test_from",
    "test_until",
    "period_from",
    "period_until",
}


def config_path(repo_path: str | Path) -> Path:
    return Path(repo_path) / CONFIG_RELATIVE_PATH


def ensure_dataframe(data: Any) -> pd.DataFrame:
    if isinstance(data, pd.DataFrame):
        return data.copy()
    if isinstance(data, list):
        return pd.DataFrame(data)
    if data is None:
        return pd.DataFrame()
    if isinstance(data, dict):
        return pd.DataFrame(data)
    return pd.DataFrame(data)


def strip_technical_columns(df: Any) -> pd.DataFrame:
    out = ensure_dataframe(df)
    return out.drop(columns=[col for col in TECHNICAL_COLUMNS if col in out.columns])


def normalize_dates_for_csv(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in DATE_COLUMNS.intersection(out.columns):
        out[col] = pd.to_datetime(out[col], errors="coerce").dt.strftime("%Y-%m-%d")
        out[col] = out[col].fillna("")
    return out


def duplicate_key_rows(df: pd.DataFrame, key_columns: list[str] | tuple[str, ...]) -> pd.DataFrame:
    missing = [col for col in key_columns if col not in df.columns]
    if missing:
        raise ValueError(f"Faltan columnas llave para validar duplicados: {missing}")
    duplicate_mask = df.duplicated(list(key_columns), keep=False)
    return df.loc[duplicate_mask, list(key_columns)].sort_values(list(key_columns)).copy()


def assert_unique_keys(df: pd.DataFrame, key_columns: list[str] | tuple[str, ...], context: str) -> None:
    duplicates = duplicate_key_rows(df, key_columns)
    if duplicates.empty:
        return
    sample = duplicates.head(10).to_dict("records")
    raise ValueError(
        f"{context} contiene {int(duplicates.shape[0])} filas duplicadas por "
        f"{' + '.join(key_columns)}. Ejemplos: {sample}"
    )


def summarize_forecasting_inputs(dfs: dict[str, pd.DataFrame]) -> dict[str, dict[str, Any]]:
    summary: dict[str, dict[str, Any]] = {}
    for key, df in dfs.items():
        frame = ensure_dataframe(df)
        row = {"rows": int(frame.shape[0])}
        if "product_id" in frame.columns:
            row["products"] = int(frame["product_id"].nunique(dropna=True))
        if "periodo" in frame.columns:
            periods = pd.to_datetime(frame["periodo"], errors="coerce")
            row["period_from"] = periods.min().date().isoformat() if periods.notna().any() else None
            row["period_until"] = periods.max().date().isoformat() if periods.notna().any() else None
        if "target_qty" in frame.columns:
            row["target_sum"] = float(pd.to_numeric(frame["target_qty"], errors="coerce").fillna(0.0).sum())
        summary[key] = row
    return summary


def validate_forecasting_inputs(
    dfs: dict[str, pd.DataFrame],
    expectations: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Valida que las tablas Silver cargadas por Mage se parezcan al baseline.

    No intenta garantizar calidad perfecta, pero si detecta desalineaciones
    obvias de cobertura, volumen o horizonte temporal antes de entrenar.
    """
    expectations = expectations or FORECASTING_V3_DATASET_EXPECTATIONS
    summary = summarize_forecasting_inputs(dfs)
    issues: list[str] = []

    for key, rules in expectations.items():
        stats = summary.get(key)
        if stats is None:
            issues.append(f"{key}: no fue cargado desde Silver")
            continue
        if stats["rows"] <= 0:
            issues.append(f"{key}: esta vacio")
            continue
        if "min_rows" in rules and stats["rows"] < int(rules["min_rows"]):
            issues.append(f"{key}: rows={stats['rows']} < esperado_min={int(rules['min_rows'])}")
        if "min_products" in rules:
            products = int(stats.get("products", 0))
            if products < int(rules["min_products"]):
                issues.append(f"{key}: products={products} < esperado_min={int(rules['min_products'])}")
        if "min_target_sum" in rules:
            target_sum = float(stats.get("target_sum", 0.0))
            if target_sum < float(rules["min_target_sum"]):
                issues.append(f"{key}: target_sum={target_sum:.0f} < esperado_min={float(rules['min_target_sum']):.0f}")
        if "min_period_until" in rules:
            period_until = stats.get("period_until")
            if period_until is None or pd.Timestamp(period_until) < pd.Timestamp(rules["min_period_until"]):
                issues.append(f"{key}: periodo_max={period_until} < esperado_min={rules['min_period_until']}")

    return {"summary": summary, "issues": issues}


def assert_forecasting_inputs_aligned(dfs: dict[str, pd.DataFrame]) -> dict[str, Any]:
    """Falla rapido si Mage recibio insumos incompatibles con forecasting_v3."""
    validation = validate_forecasting_inputs(dfs)
    if validation["issues"]:
        joined = "\n  - ".join(validation["issues"])
        raise RuntimeError(
            "Las tablas silver.forecasting_v3_* no estan alineadas con el modelado validado.\n"
            f"  - {joined}\n"
            "Reejecuta/actualiza el ETL Silver antes de entrenar Forecasting V3 en Mage."
        )
    return validation


def write_processed_outputs(config: dict[str, Any], dfs: dict[str, pd.DataFrame]) -> dict[str, int]:
    """Materializa en disco las tablas que el modelado standalone espera leer."""
    counts: dict[str, int] = {}
    for key, (path_key, file_name) in PROCESSED_OUTPUTS.items():
        if key not in dfs:
            continue
        target_dir = Path(config["resolved_paths"][path_key])
        target_dir.mkdir(parents=True, exist_ok=True)
        out = normalize_dates_for_csv(strip_technical_columns(dfs[key]))
        out.to_csv(target_dir / file_name, index=False, encoding="utf-8")
        counts[key] = int(out.shape[0])
    return counts


def read_report_outputs(config: dict[str, Any]) -> dict[str, pd.DataFrame]:
    """Carga reportes CSV generados por el forecasting para publicarlos en Gold."""
    reports_dir = Path(config["resolved_paths"]["reports_dir"])
    outputs: dict[str, pd.DataFrame] = {}
    for key, file_name in REPORT_OUTPUTS.items():
        report_path = reports_dir / file_name
        if report_path.exists():
            outputs[key] = pd.read_csv(report_path)
    return outputs
