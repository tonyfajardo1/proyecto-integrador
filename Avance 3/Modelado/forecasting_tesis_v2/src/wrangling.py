import re

import numpy as np
import pandas as pd


def normalize_product_name(name: str) -> str:
    s = str(name).upper().strip()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"^\*+", "", s).strip()
    s = re.sub(r"\bEXTR\b", "EXT", s)
    s = re.sub(r"[^A-Z0-9 ]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def extract_category_name(name: str) -> str:
    s = str(name).upper().strip()
    if s == "" or s == "NAN":
        return "GENERAL"
    if ">" in s:
        parts = [p.strip() for p in s.split(">") if p.strip()]
        if len(parts) >= 2:
            return normalize_product_name(parts[1]) or "GENERAL"
        if len(parts) == 1:
            return normalize_product_name(parts[0]) or "GENERAL"
    if ":" in s:
        parts = [p.strip() for p in s.split(":") if p.strip()]
        if len(parts) >= 3:
            return normalize_product_name(parts[2]) or "GENERAL"
        if len(parts) >= 2:
            return normalize_product_name(parts[1]) or "GENERAL"
    return "GENERAL"


def _robust_upper_bound(series: pd.Series, iqr_mult: float = 3.0, q_fallback: float = 0.995) -> float:
    s = pd.to_numeric(series, errors="coerce").dropna()
    if len(s) == 0:
        return 0.0
    q1 = float(s.quantile(0.25))
    q3 = float(s.quantile(0.75))
    iqr = q3 - q1
    ub_iqr = q3 + float(iqr_mult) * iqr if np.isfinite(iqr) else np.nan
    ub_q = float(s.quantile(q_fallback))
    if not np.isfinite(ub_iqr):
        ub_iqr = ub_q
    return float(max(ub_iqr, ub_q, 0.0))


def prepare_for_modeling(
    df: pd.DataFrame,
    min_periods_product=4,
    seasonality_max_active_months=3,
    seasonality_max_active_share=0.45,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    d = df.copy()
    if "tipo_producto" not in d.columns:
        d["tipo_producto"] = "OTRO"
    d["tipo_producto"] = d["tipo_producto"].astype(str).str.upper().str.strip()
    d.loc[~d["tipo_producto"].isin(["PT", "PP"]), "tipo_producto"] = "OTRO"
    d["categoria_producto"] = d["producto"].apply(extract_category_name)
    d["producto"] = d["producto"].apply(normalize_product_name)
    for c in ["qty_fabricada", "qty_planificada", "n_ordenes"]:
        d[c] = pd.to_numeric(d[c], errors="coerce").fillna(0).clip(lower=0)

    tipo_ref = (
        d.groupby("producto", as_index=False)["tipo_producto"]
        .agg(lambda s: s.value_counts().index[0] if len(s) > 0 else "OTRO")
    )
    categoria_ref = (
        d.groupby("producto", as_index=False)["categoria_producto"]
        .agg(lambda s: s.value_counts().index[0] if len(s) > 0 else "GENERAL")
    )

    d = (
        d.groupby(["producto", "periodo"], as_index=False)
        .agg(
            qty_fabricada=("qty_fabricada", "sum"),
            qty_planificada=("qty_planificada", "sum"),
            n_ordenes=("n_ordenes", "sum"),
        )
        .merge(tipo_ref, on="producto", how="left")
        .merge(categoria_ref, on="producto", how="left")
        .sort_values(["producto", "periodo"])
        .reset_index(drop=True)
    )

    parts = []
    outlier_summary = []
    for prod, sub in d.groupby("producto"):
        rng = pd.date_range(sub["periodo"].min(), sub["periodo"].max(), freq="MS")
        base = pd.DataFrame({"periodo": rng})
        m = base.merge(sub, on="periodo", how="left")
        m["producto"] = prod
        if "tipo_producto" not in m.columns:
            m["tipo_producto"] = "OTRO"
        if "categoria_producto" not in m.columns:
            m["categoria_producto"] = "GENERAL"

        cols = ["qty_fabricada", "qty_planificada", "n_ordenes"]
        missing_mask = m[cols].isna().any(axis=1)
        m["imputado_mes_faltante"] = missing_mask
        m["tipo_imputacion"] = "observado"

        m["mes"] = m["periodo"].dt.month

        active_rows = sub[(sub["qty_fabricada"] > 0) | (sub["qty_planificada"] > 0) | (sub["n_ordenes"] > 0)]
        active_months = sorted(active_rows["periodo"].dt.month.unique().tolist())
        n_active = len(active_months)
        n_total = max(len(m), 1)
        active_share = n_active / n_total
        is_seasonal = (
            n_active > 0
            and n_active <= int(seasonality_max_active_months)
            and active_share <= float(seasonality_max_active_share)
        )

        m["producto_estacional"] = bool(is_seasonal)
        m["temporada_meses"] = ",".join([str(x) for x in active_months]) if active_months else ""

        for c in ["qty_fabricada", "qty_planificada", "n_ordenes"]:
            m[c] = pd.to_numeric(m[c], errors="coerce")

        # 1) Cero estructural para productos estacionales fuera de temporada
        structural_mask = missing_mask & bool(is_seasonal) & (~m["mes"].isin(active_months))
        m.loc[structural_mask, cols] = 0
        m.loc[structural_mask, "tipo_imputacion"] = "cero_estructural"

        # 2) Imputacion temporal (ffill/bfill) para faltantes restantes
        rem_before = m[cols].isna().any(axis=1)
        temp_imp = m[cols].ffill().bfill()
        m[cols] = temp_imp
        rem_after_temp = m[cols].isna().any(axis=1)
        temporal_mask = rem_before & (~rem_after_temp)
        m.loc[temporal_mask, "tipo_imputacion"] = "temporal"

        # 3) Fallback mediana por producto para remanentes
        median_needed = rem_after_temp.copy()
        for c in cols:
            med = m[c].median(skipna=True)
            if not np.isfinite(med):
                med = 0
            m[c] = m[c].fillna(med)
        m.loc[median_needed, "tipo_imputacion"] = "mediana"

        # Asegurar no negativos
        for c in cols:
            m[c] = pd.to_numeric(m[c], errors="coerce").fillna(0).clip(lower=0)

        # Control inteligente de outliers (solo para extremos no creibles)
        # 1) pico real: extremo pero acompaniado por senales operativas
        # 2) sospechoso: extremo sin senales (plan casi cero y pocas ordenes)
        m["qty_fabricada_raw"] = m["qty_fabricada"]
        m["qty_planificada_raw"] = m["qty_planificada"]

        ub_fab = _robust_upper_bound(m["qty_fabricada_raw"], iqr_mult=3.0, q_fallback=0.995)
        ub_plan = _robust_upper_bound(m["qty_planificada_raw"], iqr_mult=3.0, q_fallback=0.995)

        extreme_fab = m["qty_fabricada_raw"] > ub_fab
        extreme_plan = m["qty_planificada_raw"] > ub_plan

        operational_signal = (m["qty_planificada_raw"] > 0) | (m["n_ordenes"] >= 2)
        suspicious_fab = extreme_fab & (~operational_signal)
        suspicious_plan = extreme_plan & (m["n_ordenes"] <= 1)

        m["outlier_flag_extremo_fabricada"] = extreme_fab
        m["outlier_flag_extremo_planificada"] = extreme_plan
        m["outlier_flag_sospechoso_fabricada"] = suspicious_fab
        m["outlier_flag_sospechoso_planificada"] = suspicious_plan

        m.loc[suspicious_fab, "qty_fabricada"] = ub_fab
        m.loc[suspicious_plan, "qty_planificada"] = ub_plan

        m["outlier_treatment"] = "none"
        m.loc[suspicious_fab & (~suspicious_plan), "outlier_treatment"] = "cap_qty_fabricada"
        m.loc[(~suspicious_fab) & suspicious_plan, "outlier_treatment"] = "cap_qty_planificada"
        m.loc[suspicious_fab & suspicious_plan, "outlier_treatment"] = "cap_ambas"

        outlier_summary.append(
            {
                "producto": prod,
                "upper_bound_qty_fabricada": float(ub_fab),
                "upper_bound_qty_planificada": float(ub_plan),
                "extremos_fabricada": int(extreme_fab.sum()),
                "extremos_planificada": int(extreme_plan.sum()),
                "sospechosos_fabricada": int(suspicious_fab.sum()),
                "sospechosos_planificada": int(suspicious_plan.sum()),
                "caps_aplicados": int((m["outlier_treatment"] != "none").sum()),
            }
        )

        m = m.drop(columns=["mes"])
        parts.append(m)

    out = pd.concat(parts, ignore_index=True)
    out["tipo_producto"] = out["tipo_producto"].fillna("OTRO").astype(str).str.upper().str.strip()
    out.loc[~out["tipo_producto"].isin(["PT", "PP"]), "tipo_producto"] = "OTRO"
    out["categoria_producto"] = out["categoria_producto"].fillna("GENERAL").astype(str).str.upper().str.strip()
    out.loc[out["categoria_producto"].isin(["", "NAN", "NONE", "NULL"]), "categoria_producto"] = "GENERAL"

    outlier_detail = pd.DataFrame(outlier_summary)

    hist = out.groupby("producto")["periodo"].nunique().reset_index(name="n_periodos")
    valid = hist[hist["n_periodos"] >= int(min_periods_product)]["producto"]
    out = out[out["producto"].isin(valid)].copy().sort_values(["producto", "periodo"]).reset_index(drop=True)

    report = pd.DataFrame(
        [
            {"metric": "rows_output", "value": len(out)},
            {"metric": "products_output", "value": out["producto"].nunique()},
            {"metric": "periods_output", "value": out["periodo"].nunique()},
            {"metric": "rows_imputed_missing_month", "value": int(out["imputado_mes_faltante"].sum())},
            {"metric": "products_seasonal_detected", "value": int(out.groupby("producto")["producto_estacional"].max().sum())},
            {"metric": "rows_imputed_structural_zero", "value": int((out["tipo_imputacion"] == "cero_estructural").sum())},
            {"metric": "rows_imputed_temporal", "value": int((out["tipo_imputacion"] == "temporal").sum())},
            {"metric": "rows_imputed_median", "value": int((out["tipo_imputacion"] == "mediana").sum())},
            {"metric": "rows_outlier_extremo_fabricada", "value": int(out["outlier_flag_extremo_fabricada"].sum())},
            {"metric": "rows_outlier_extremo_planificada", "value": int(out["outlier_flag_extremo_planificada"].sum())},
            {"metric": "rows_outlier_sospechoso_fabricada", "value": int(out["outlier_flag_sospechoso_fabricada"].sum())},
            {"metric": "rows_outlier_sospechoso_planificada", "value": int(out["outlier_flag_sospechoso_planificada"].sum())},
            {"metric": "rows_outlier_caps_aplicados", "value": int((out["outlier_treatment"] != "none").sum())},
            {"metric": "products_with_caps", "value": int((outlier_detail["caps_aplicados"] > 0).sum())},
        ]
    )
    return out, report
