import re

import numpy as np
import pandas as pd


def normalize_product_name(name: str) -> str:
    s = str(name).strip().upper()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"^\*+", "", s).strip()
    s = re.sub(r"\bEXTR\b", "EXT", s)
    s = re.sub(r"[^A-Z0-9 ]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _clip_iqr(series: pd.Series, factor: float = 1.5):
    x = pd.to_numeric(series, errors="coerce").fillna(0.0)
    q1 = x.quantile(0.25)
    q3 = x.quantile(0.75)
    iqr = q3 - q1
    if not np.isfinite(iqr) or iqr <= 0:
        return x
    lower = max(0.0, q1 - factor * iqr)
    upper = q3 + factor * iqr
    return x.clip(lower=lower, upper=upper)


def _impute_temporal(sub_df: pd.DataFrame) -> pd.DataFrame:
    m = sub_df.copy()
    m = m.sort_values("periodo")

    # Mantener NaN para imputacion temporal primero
    qf = pd.to_numeric(m["qty_fabricada"], errors="coerce")
    qp = pd.to_numeric(m["qty_planificada"], errors="coerce")
    no = pd.to_numeric(m["n_ordenes"], errors="coerce")

    qf = qf.ffill().bfill()
    qp = qp.ffill().bfill()
    no = no.ffill().bfill()

    # Fallback robusto por mediana/0
    qf = qf.fillna(qf.median() if np.isfinite(qf.median()) else 0)
    qp = qp.fillna(qp.median() if np.isfinite(qp.median()) else 0)
    no = no.fillna(no.median() if np.isfinite(no.median()) else 0)

    m["qty_fabricada"] = qf.clip(lower=0)
    m["qty_planificada"] = qp.clip(lower=0)
    m["n_ordenes"] = no.clip(lower=0)
    return m


def prepare_modeling_table(
    monthly_df: pd.DataFrame,
    min_periods_product: int = 4,
    imputation_mode: str = "zero",
):
    df = monthly_df.copy()
    if len(df) == 0:
        return df, pd.DataFrame()

    for c in ["qty_fabricada", "qty_planificada", "n_ordenes"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    df["qty_fabricada"] = df["qty_fabricada"].clip(lower=0)
    df["qty_planificada"] = df["qty_planificada"].clip(lower=0)
    df["n_ordenes"] = df["n_ordenes"].clip(lower=0)

    df["producto_raw"] = df["producto"].astype(str)
    df["producto"] = df["producto"].apply(normalize_product_name)

    grouped = (
        df.groupby(["producto", "periodo"], as_index=False)
        .agg(
            qty_fabricada=("qty_fabricada", "sum"),
            qty_planificada=("qty_planificada", "sum"),
            n_ordenes=("n_ordenes", "sum"),
        )
        .sort_values(["producto", "periodo"])
        .reset_index(drop=True)
    )

    # Completar meses faltantes por producto
    mode = str(imputation_mode).lower().strip()
    if mode not in {"zero", "temporal"}:
        mode = "zero"

    filled_parts = []
    for prod, sub in grouped.groupby("producto"):
        rng = pd.date_range(sub["periodo"].min(), sub["periodo"].max(), freq="MS")
        base = pd.DataFrame({"periodo": rng})
        m = base.merge(sub, on="periodo", how="left")
        m["producto"] = prod
        m["imputado_mes_faltante"] = m["qty_fabricada"].isna() | m["qty_planificada"].isna() | m["n_ordenes"].isna()

        if mode == "zero":
            for c in ["qty_fabricada", "qty_planificada", "n_ordenes"]:
                m[c] = pd.to_numeric(m[c], errors="coerce").fillna(0)
        else:
            m = _impute_temporal(m)

        filled_parts.append(m)
    complete = pd.concat(filled_parts, ignore_index=True)

    # Filtrar productos con poca historia
    hist = complete.groupby("producto")["periodo"].nunique().rename("n_periodos").reset_index()
    valid_products = hist[hist["n_periodos"] >= int(min_periods_product)]["producto"]
    complete = complete[complete["producto"].isin(valid_products)].copy()

    # Tratamiento de outliers por producto
    before_qty = complete["qty_fabricada"].copy()
    before_plan = complete["qty_planificada"].copy()
    complete["qty_fabricada"] = complete.groupby("producto", group_keys=False)["qty_fabricada"].apply(_clip_iqr)
    complete["qty_planificada"] = complete.groupby("producto", group_keys=False)["qty_planificada"].apply(_clip_iqr)

    changed_qty = int((np.abs(before_qty - complete["qty_fabricada"]) > 1e-9).sum())
    changed_plan = int((np.abs(before_plan - complete["qty_planificada"]) > 1e-9).sum())
    imputed_rows = int(complete["imputado_mes_faltante"].sum())

    report = pd.DataFrame(
        [
            {"metric": "rows_output", "value": len(complete)},
            {"metric": "products_output", "value": complete["producto"].nunique()},
            {"metric": "periods_output", "value": complete["periodo"].nunique()},
            {"metric": "rows_imputed_missing_month", "value": imputed_rows},
            {"metric": "rows_qty_fabricada_clipped", "value": changed_qty},
            {"metric": "rows_qty_planificada_clipped", "value": changed_plan},
            {"metric": "imputation_mode", "value": mode},
        ]
    )

    complete = complete.sort_values(["producto", "periodo"]).reset_index(drop=True)
    return complete, report
