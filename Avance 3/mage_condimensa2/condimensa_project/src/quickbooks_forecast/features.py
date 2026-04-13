from __future__ import annotations

import math

import pandas as pd


LAG_FEATURES = [1, 2, 3, 6, 12]
ROLLING_WINDOWS = [3, 6, 12]

CALENDAR_EXOGENOUS_FEATURES = [
    "dias_laborables",
    "feriados_mes",
    "promocion_general",
    "temporada_alta_general",
    "evento_comercial",
    "variacion_precio_general_pct",
]

PRODUCT_EXOGENOUS_FEATURES = [
    "pedidos_confirmados",
    "preventa_confirmada",
    "promocion_producto",
    "cliente_grande_confirmado",
    "cambio_pvp_pct",
    "precio_planificado",
    "riesgo_quiebre_stock",
    "disponibilidad_materia_prima",
    "ajuste_comercial_manual",
]

EXOGENOUS_FEATURE_COLUMNS = CALENDAR_EXOGENOUS_FEATURES + PRODUCT_EXOGENOUS_FEATURES

BASE_FEATURE_COLUMNS = [
    "month",
    "quarter",
    "year_index",
    "month_sin",
    "month_cos",
    "months_since_first",
    "is_seasonal",
    "seasonal_month_flag",
    "share_top_3_meses",
    "lag_1",
    "lag_2",
    "lag_3",
    "lag_6",
    "lag_12",
    "rolling_mean_3",
    "rolling_mean_6",
    "rolling_mean_12",
    "rolling_max_12",
    "rolling_nonzero_6",
    "rolling_nonzero_12",
    "expanding_mean",
    "expanding_max",
]

FEATURE_COLUMNS = BASE_FEATURE_COLUMNS + EXOGENOUS_FEATURE_COLUMNS


def _seasonal_flag(month: int, months: str) -> int:
    if not isinstance(months, str) or not months:
        return 0
    allowed = {int(part) for part in months.split(",") if part.strip().isdigit()}
    return int(month in allowed)


def make_features(monthly: pd.DataFrame, products: pd.DataFrame) -> pd.DataFrame:
    df = monthly.copy()
    df["periodo"] = pd.to_datetime(df["periodo"])
    df = df.sort_values(["product_id", "periodo"]).reset_index(drop=True)

    product_cols = [
        "product_id",
        "estado_producto",
        "es_estacional",
        "share_top_3_meses",
        "meses_estacionales_num",
        "meses_estacionales",
    ]
    product_cols = [col for col in product_cols if col in products.columns]
    meta = products[product_cols].drop_duplicates("product_id")

    duplicate_cols = [col for col in meta.columns if col != "product_id" and col in df.columns]
    if duplicate_cols:
        df = df.drop(columns=duplicate_cols)
    df = df.merge(meta, on="product_id", how="left")

    df["month"] = df["periodo"].dt.month
    df["quarter"] = df["periodo"].dt.quarter
    df["year_index"] = df["periodo"].dt.year - df["periodo"].dt.year.min()
    df["month_sin"] = df["month"].map(lambda m: math.sin(2 * math.pi * m / 12))
    df["month_cos"] = df["month"].map(lambda m: math.cos(2 * math.pi * m / 12))
    df["months_since_first"] = df.groupby("product_id").cumcount()
    df["is_seasonal"] = df.get("es_estacional", False).fillna(False).astype(int)
    df["share_top_3_meses"] = df.get("share_top_3_meses", 0.0).fillna(0.0)
    df["meses_estacionales_num"] = df.get("meses_estacionales_num", "").fillna("")
    df["seasonal_month_flag"] = [
        _seasonal_flag(month, months)
        for month, months in zip(df["month"], df["meses_estacionales_num"], strict=False)
    ]

    grouped = df.groupby("product_id")["target_qty"]
    for lag in LAG_FEATURES:
        df[f"lag_{lag}"] = grouped.shift(lag)

    for window in ROLLING_WINDOWS:
        df[f"rolling_mean_{window}"] = grouped.transform(
            lambda series: series.shift(1).rolling(window, min_periods=1).mean()
        )

    df["rolling_max_12"] = grouped.transform(lambda series: series.shift(1).rolling(12, min_periods=1).max())
    df["rolling_nonzero_6"] = grouped.transform(
        lambda series: series.shift(1).gt(0).rolling(6, min_periods=1).sum()
    )
    df["rolling_nonzero_12"] = grouped.transform(
        lambda series: series.shift(1).gt(0).rolling(12, min_periods=1).sum()
    )
    df["expanding_mean"] = grouped.transform(lambda series: series.shift(1).expanding().mean())
    df["expanding_max"] = grouped.transform(lambda series: series.shift(1).expanding().max())

    for col in EXOGENOUS_FEATURE_COLUMNS:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    df[FEATURE_COLUMNS] = df[FEATURE_COLUMNS].fillna(0.0)
    return df
