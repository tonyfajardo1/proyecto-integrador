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

PROCESSED_OUTPUTS = {
    "catalogo_pt_limpio": ("processed_dir", "catalogo_pt_limpio.csv"),
    "pt_mensual_model": ("processed_dir", "pt_mensual_model.csv"),
    "pt_productos_model": ("processed_dir", "pt_productos_model.csv"),
    "pp_mensual_model": ("processed_dir", "pp_mensual_model.csv"),
    "pp_productos_model": ("processed_dir", "pp_productos_model.csv"),
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
    "backtest_pt": "backtest_pt.csv",
    "backtest_pp": "backtest_pp.csv",
    "hgb_tuning_all": "hgb_tuning_all.csv",
    "high_error_products_all": "high_error_products_all.csv",
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


def strip_technical_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    return out.drop(columns=[col for col in TECHNICAL_COLUMNS if col in out.columns])


def normalize_dates_for_csv(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in DATE_COLUMNS.intersection(out.columns):
        out[col] = pd.to_datetime(out[col], errors="coerce").dt.strftime("%Y-%m-%d")
        out[col] = out[col].fillna("")
    return out


def write_processed_outputs(config: dict[str, Any], dfs: dict[str, pd.DataFrame]) -> dict[str, int]:
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
    reports_dir = Path(config["resolved_paths"]["reports_dir"])
    outputs: dict[str, pd.DataFrame] = {}
    for key, file_name in REPORT_OUTPUTS.items():
        report_path = reports_dir / file_name
        if report_path.exists():
            outputs[key] = pd.read_csv(report_path)
    return outputs
