import numpy as np
import pandas as pd


def _pct(count, total):
    total = max(int(total), 1)
    return (float(count) / total) * 100.0


def _iqr_outlier_count(series: pd.Series, factor: float = 1.5):
    x = pd.to_numeric(series, errors="coerce").dropna()
    if len(x) < 5:
        return 0
    q1 = x.quantile(0.25)
    q3 = x.quantile(0.75)
    iqr = q3 - q1
    if not np.isfinite(iqr) or iqr <= 0:
        return 0
    lower = max(0.0, q1 - factor * iqr)
    upper = q3 + factor * iqr
    return int(((x < lower) | (x > upper)).sum())


def build_quality_report(df: pd.DataFrame, stage: str = "raw") -> pd.DataFrame:
    d = df.copy()
    total = len(d)

    # Completeness and type coercion checks
    critical_cols = [c for c in ["producto", "periodo", "qty_fabricada", "qty_planificada", "n_ordenes"] if c in d.columns]
    missing_any = int(d[critical_cols].isna().any(axis=1).sum()) if critical_cols else 0

    non_numeric_qty_fabricada = 0
    non_numeric_qty_planificada = 0
    if "qty_fabricada" in d.columns:
        s = pd.to_numeric(d["qty_fabricada"], errors="coerce")
        non_numeric_qty_fabricada = int(s.isna().sum() - d["qty_fabricada"].isna().sum())
    if "qty_planificada" in d.columns:
        s = pd.to_numeric(d["qty_planificada"], errors="coerce")
        non_numeric_qty_planificada = int(s.isna().sum() - d["qty_planificada"].isna().sum())

    # Precision checks
    dup_prod_period = 0
    if "producto" in d.columns and "periodo" in d.columns:
        dup_prod_period = int(d.duplicated(subset=["producto", "periodo"]).sum())

    neg_qty_fabricada = int((pd.to_numeric(d.get("qty_fabricada", 0), errors="coerce").fillna(0) < 0).sum())
    neg_qty_planificada = int((pd.to_numeric(d.get("qty_planificada", 0), errors="coerce").fillna(0) < 0).sum())

    outlier_fabricada = _iqr_outlier_count(d.get("qty_fabricada", pd.Series(dtype=float)))
    outlier_planificada = _iqr_outlier_count(d.get("qty_planificada", pd.Series(dtype=float)))

    # Possible scale inconsistency heuristics
    scale_ratio_issue = 0
    if "qty_fabricada" in d.columns and "qty_planificada" in d.columns:
        fab = pd.to_numeric(d["qty_fabricada"], errors="coerce").fillna(0)
        pla = pd.to_numeric(d["qty_planificada"], errors="coerce").fillna(0)
        mask = (fab > 0) & (pla > 0)
        ratio = np.where(mask, fab / np.maximum(pla, 1e-9), np.nan)
        scale_ratio_issue = int(np.isfinite(ratio).sum() and ((ratio > 5) | (ratio < 0.2)).sum())

    scale_jump_issue = 0
    if "producto" in d.columns and "periodo" in d.columns and "qty_fabricada" in d.columns:
        tmp = d[["producto", "periodo", "qty_fabricada"]].copy()
        tmp["qty_fabricada"] = pd.to_numeric(tmp["qty_fabricada"], errors="coerce").fillna(0)
        tmp = tmp.sort_values(["producto", "periodo"]) 
        prev = tmp.groupby("producto")["qty_fabricada"].shift(1)
        jump = np.where(prev > 0, tmp["qty_fabricada"] / np.maximum(prev, 1e-9), np.nan)
        scale_jump_issue = int(((jump > 8) | (jump < 0.125)).sum())

    rows = [
        ("Completitud", "ausentes_columnas_criticas", missing_any),
        ("Precision", "outliers_iqr_qty_fabricada", outlier_fabricada),
        ("Precision", "outliers_iqr_qty_planificada", outlier_planificada),
        ("Precision", "inconsistencia_escala_ratio_fab_plan", scale_ratio_issue),
        ("Precision", "inconsistencia_escala_salto_fabricada", scale_jump_issue),
        ("Precision", "duplicados_producto_periodo", dup_prod_period),
        ("Precision", "inconsistencia_tipo_qty_fabricada", non_numeric_qty_fabricada),
        ("Precision", "inconsistencia_tipo_qty_planificada", non_numeric_qty_planificada),
        ("Precision", "inconsistencia_signo_qty_fabricada_neg", neg_qty_fabricada),
        ("Precision", "inconsistencia_signo_qty_planificada_neg", neg_qty_planificada),
    ]

    report = pd.DataFrame(rows, columns=["dimension", "regla", "count"])
    report["pct_rows"] = report["count"].apply(lambda x: _pct(x, total))
    report["stage"] = stage
    report["rows_total"] = total
    report["status"] = np.where(report["count"] == 0, "OK", "REVISAR")
    return report[["stage", "dimension", "regla", "count", "pct_rows", "status", "rows_total"]]


def compare_quality_reports(raw_report: pd.DataFrame, wrangled_report: pd.DataFrame) -> pd.DataFrame:
    a = raw_report[["regla", "count"]].rename(columns={"count": "count_raw"})
    b = wrangled_report[["regla", "count"]].rename(columns={"count": "count_wrangled"})
    c = a.merge(b, on="regla", how="outer").fillna(0)
    c["delta"] = c["count_wrangled"] - c["count_raw"]
    c["mejora"] = np.where(c["delta"] < 0, "MEJORA", np.where(c["delta"] == 0, "IGUAL", "EMPEORA"))
    return c.sort_values(["mejora", "regla"]).reset_index(drop=True)
