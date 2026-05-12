"""Lectura, plantillas y merge de variables exogenas controladas."""

from __future__ import annotations

from typing import Any

import pandas as pd

from .cleaning import normalize_header
from .features import CALENDAR_EXOGENOUS_FEATURES, EXOGENOUS_FEATURE_COLUMNS, PRODUCT_EXOGENOUS_FEATURES


CALENDAR_TEMPLATE_COLUMNS = [
    "source_type",
    "periodo",
    *CALENDAR_EXOGENOUS_FEATURES,
    "observacion",
]
PRODUCT_TEMPLATE_COLUMNS = [
    "source_type",
    "product_id",
    "product_name",
    "periodo",
    *PRODUCT_EXOGENOUS_FEATURES,
    "observacion",
]


def _input_dir(config: dict[str, Any]):
    path = config.get("resolved_paths", {}).get("input_dir")
    if path is not None:
        return path
    return config["resolved_paths"]["project_root"] / "data" / "input"


def _exogenous_path(config: dict[str, Any], key: str, default_name: str):
    file_name = config.get("exogenous", {}).get(key, default_name)
    return _input_dir(config) / file_name


def _read_optional_csv(path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _standardize_period(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [normalize_header(col).replace(" ", "_") for col in out.columns]
    if "periodo" not in out.columns:
        return pd.DataFrame()
    out["periodo"] = pd.to_datetime(out["periodo"], errors="coerce")
    out = out[out["periodo"].notna()].copy()
    out["periodo"] = out["periodo"].values.astype("datetime64[M]")
    if "source_type" in out.columns:
        out["source_type"] = out["source_type"].astype(str).str.strip().str.upper()
    return out


def _numeric_features(df: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    out = df.copy()
    for col in features:
        if col not in out.columns:
            out[col] = 0.0
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0.0)
    return out


def _calendar_features(config: dict[str, Any], source: str) -> pd.DataFrame:
    path = _exogenous_path(config, "calendar_file", "variables_exogenas_calendario.csv")
    df = _standardize_period(_read_optional_csv(path))
    if df.empty:
        return pd.DataFrame(columns=["source_type", "periodo", *CALENDAR_EXOGENOUS_FEATURES])
    if "source_type" not in df.columns:
        df["source_type"] = source
    df = df[df["source_type"].isin([source, "ALL", ""])].copy()
    df.loc[df["source_type"].isin(["ALL", ""]), "source_type"] = source
    df = _numeric_features(df, CALENDAR_EXOGENOUS_FEATURES)
    return (
        df[["source_type", "periodo", *CALENDAR_EXOGENOUS_FEATURES]]
        .groupby(["source_type", "periodo"], as_index=False)
        .mean(numeric_only=True)
    )


def _product_features(config: dict[str, Any], source: str) -> pd.DataFrame:
    path = _exogenous_path(config, "product_file", "variables_exogenas_producto.csv")
    df = _standardize_period(_read_optional_csv(path))
    if df.empty or "product_id" not in df.columns:
        return pd.DataFrame(columns=["source_type", "product_id", "periodo", *PRODUCT_EXOGENOUS_FEATURES])
    if "source_type" not in df.columns:
        df["source_type"] = source
    df["source_type"] = df["source_type"].astype(str).str.strip().str.upper()
    df["product_id"] = df["product_id"].astype(str).str.strip()
    df = df[df["source_type"].isin([source, "ALL", ""])].copy()
    df.loc[df["source_type"].isin(["ALL", ""]), "source_type"] = source
    df = df[df["product_id"].ne("")].copy()
    df = _numeric_features(df, PRODUCT_EXOGENOUS_FEATURES)
    return (
        df[["source_type", "product_id", "periodo", *PRODUCT_EXOGENOUS_FEATURES]]
        .groupby(["source_type", "product_id", "periodo"], as_index=False)
        .mean(numeric_only=True)
    )


def add_exogenous_features(config: dict[str, Any], monthly: pd.DataFrame, source: str) -> pd.DataFrame:
    """Anexa exogenas calendario/producto respetando `source_type` y periodo."""
    if not bool(config.get("exogenous", {}).get("enabled", True)):
        out = monthly.copy()
        for col in EXOGENOUS_FEATURE_COLUMNS:
            if col not in out.columns:
                out[col] = 0.0
        return out

    out = monthly.copy()
    out["periodo"] = pd.to_datetime(out["periodo"]).values.astype("datetime64[M]")
    if "source_type" not in out.columns:
        out["source_type"] = source
    out["source_type"] = out["source_type"].astype(str).str.strip().str.upper()
    out = out.drop(columns=[col for col in EXOGENOUS_FEATURE_COLUMNS if col in out.columns])

    calendar = _calendar_features(config, source)
    if not calendar.empty:
        out = out.merge(calendar, on=["source_type", "periodo"], how="left")

    product = _product_features(config, source)
    if not product.empty:
        out = out.merge(product, on=["source_type", "product_id", "periodo"], how="left")

    for col in EXOGENOUS_FEATURE_COLUMNS:
        if col not in out.columns:
            out[col] = 0.0
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0.0)
    return out


def _period_range_with_horizon(monthly: pd.DataFrame, horizon: int) -> pd.DatetimeIndex:
    periods = pd.to_datetime(monthly["periodo"])
    start = periods.min()
    end = periods.max() + pd.DateOffset(months=horizon)
    return pd.date_range(start, end, freq="MS")


def _blank_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    out = df.copy()
    for col in columns:
        if col not in out.columns:
            out[col] = ""
    return out[columns]


def build_exogenous_templates(
    config: dict[str, Any],
    pt_monthly: pd.DataFrame,
    pt_products: pd.DataFrame,
    pp_monthly: pd.DataFrame,
    pp_products: pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    """Genera plantillas base para capturar exogenas historicas y futuras."""
    input_dir = _input_dir(config)
    input_dir.mkdir(parents=True, exist_ok=True)
    horizon = int(config["dataset"].get("forecast_horizon_months", 6))

    calendar_rows = []
    for source, monthly in [("PT", pt_monthly), ("PP", pp_monthly)]:
        for periodo in _period_range_with_horizon(monthly, horizon):
            calendar_rows.append({"source_type": source, "periodo": periodo.date().isoformat()})
    calendar_template = _blank_columns(pd.DataFrame(calendar_rows), CALENDAR_TEMPLATE_COLUMNS)

    product_rows = []
    for source, monthly, products in [
        ("PT", pt_monthly, pt_products),
        ("PP", pp_monthly, pp_products),
    ]:
        periods = _period_range_with_horizon(monthly, horizon)
        product_ref = products[["product_id", "product_name"]].drop_duplicates("product_id")
        for product in product_ref.itertuples(index=False):
            for periodo in periods:
                product_rows.append(
                    {
                        "source_type": source,
                        "product_id": product.product_id,
                        "product_name": product.product_name,
                        "periodo": periodo.date().isoformat(),
                    }
                )
    product_template = _blank_columns(pd.DataFrame(product_rows), PRODUCT_TEMPLATE_COLUMNS)

    calendar_template.to_csv(input_dir / "variables_exogenas_calendario_template.csv", index=False, encoding="utf-8")
    product_template.to_csv(input_dir / "variables_exogenas_producto_template.csv", index=False, encoding="utf-8")

    calendar_actual = _exogenous_path(config, "calendar_file", "variables_exogenas_calendario.csv")
    product_actual = _exogenous_path(config, "product_file", "variables_exogenas_producto.csv")
    if not calendar_actual.exists():
        calendar_template.to_csv(calendar_actual, index=False, encoding="utf-8")
    if not product_actual.exists():
        product_template.to_csv(product_actual, index=False, encoding="utf-8")

    return {"calendar": calendar_template, "product": product_template}


def write_exogenous_report(config: dict[str, Any]) -> str:
    """Escribe una guia operativa para completar exogenas sin leakage."""
    reports_dir = config["resolved_paths"]["reports_dir"]
    calendar_path = _exogenous_path(config, "calendar_file", "variables_exogenas_calendario.csv")
    product_path = _exogenous_path(config, "product_file", "variables_exogenas_producto.csv")
    calendar = _numeric_features(_standardize_period(_read_optional_csv(calendar_path)), CALENDAR_EXOGENOUS_FEATURES)
    product = _numeric_features(_standardize_period(_read_optional_csv(product_path)), PRODUCT_EXOGENOUS_FEATURES)

    calendar_nonzero = int(calendar[CALENDAR_EXOGENOUS_FEATURES].abs().sum(axis=1).gt(0).sum()) if not calendar.empty else 0
    product_nonzero = int(product[PRODUCT_EXOGENOUS_FEATURES].abs().sum(axis=1).gt(0).sum()) if not product.empty else 0

    text = f"""# Plan de variables exogenas

## Archivos de entrada

- `data/input/variables_exogenas_calendario.csv`: variables conocidas por mes y tipo PT/PP.
- `data/input/variables_exogenas_producto.csv`: variables conocidas por producto y mes.
- Las plantillas equivalentes terminan en `_template.csv`.

## Regla contra fuga de informacion

Cada valor debe ser conocido antes de iniciar el mes que se quiere predecir. No uses cantidades reales vendidas, fabricadas o informacion calculada despues del cierre del mes como variable exogena de ese mismo mes.

## Variables generales por mes

{", ".join(CALENDAR_EXOGENOUS_FEATURES)}

## Variables por producto y mes

{", ".join(PRODUCT_EXOGENOUS_FEATURES)}

