from __future__ import annotations

import math

import pandas as pd

from .cleaning import MONTH_NAMES_ES


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

MISSING_SIGNAL_COLUMNS = [
    "monthly_observed_flag",
    "missing_cantidad_flag",
    "missing_ventas_flag",
    "missing_recuento_cliente_flag",
    "missing_q_planificada_flag",
    "missing_q_liberada_flag",
    "missing_q_fabricada_flag",
    "target_qty_missing_source_flag",
    "target_qty_proxy_flag",
]

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

FEATURE_COLUMNS = BASE_FEATURE_COLUMNS + EXOGENOUS_FEATURE_COLUMNS + MISSING_SIGNAL_COLUMNS

PROFILE_COLUMNS = [
    "estado_producto",
    "es_estacional",
    "share_top_3_meses",
    "meses_estacionales_num",
    "meses_estacionales",
    "ultima_actividad",
]


def _seasonal_flag(month: int, months: str) -> int:
    if not isinstance(months, str) or not months:
        return 0
    allowed = {int(part) for part in months.split(",") if part.strip().isdigit()}
    return int(month in allowed)


def _historical_profile_by_product(
    df: pd.DataFrame,
    inactive_months: int,
    seasonal_top_3_month_share: float,
    seasonal_max_active_months_per_year: int,
) -> pd.DataFrame:
    profile_frames = []

    for _, group in df.groupby("product_id", sort=False):
        product_df = group.sort_values("periodo").copy()
        last_active_period = pd.NaT
        month_qty = {month: 0.0 for month in range(1, 13)}
        active_months_by_year: dict[int, set[int]] = {}

        estado = []
        es_estacional = []
        share_top_3 = []
        meses_estacionales_num = []
        meses_estacionales = []
        ultima_actividad = []

        for row in product_df.itertuples(index=False):
            current_period = pd.Timestamp(row.periodo)
            cutoff = current_period - pd.DateOffset(months=inactive_months)
            is_active = pd.notna(last_active_period) and last_active_period >= cutoff

            nonzero_months = [(month, qty) for month, qty in month_qty.items() if qty > 0]
            nonzero_months.sort(key=lambda item: (-item[1], item[0]))
            top_months = [month for month, _ in nonzero_months[:3]]
            total_history_qty = float(sum(month_qty.values()))
            top3_qty = float(sum(month_qty[month] for month in top_months))
            top3_share = top3_qty / total_history_qty if total_history_qty > 0 else 0.0

            active_counts = [len(months) for months in active_months_by_year.values()]
            median_active_months = float(pd.Series(active_counts).median()) if active_counts else 0.0
            active_years = len(active_counts)
            seasonal = active_years >= 2 and (
                top3_share >= seasonal_top_3_month_share
                or median_active_months <= seasonal_max_active_months_per_year
            )

            estado.append("activo" if is_active else "inactivo")
            es_estacional.append(bool(seasonal))
            share_top_3.append(round(top3_share, 4))
            meses_estacionales_num.append(",".join(str(month) for month in top_months))
            meses_estacionales.append(", ".join(MONTH_NAMES_ES[month] for month in top_months))
            ultima_actividad.append(last_active_period)

            target_qty = pd.to_numeric(pd.Series([row.target_qty]), errors="coerce").iloc[0]
            target_qty = float(target_qty) if pd.notna(target_qty) else 0.0
            if target_qty > 0:
                last_active_period = current_period
                month_qty[current_period.month] += target_qty
                active_months_by_year.setdefault(current_period.year, set()).add(current_period.month)

        product_df["estado_producto"] = estado
        product_df["es_estacional"] = es_estacional
        product_df["share_top_3_meses"] = share_top_3
        product_df["meses_estacionales_num"] = meses_estacionales_num
        product_df["meses_estacionales"] = meses_estacionales
        product_df["ultima_actividad"] = ultima_actividad
        profile_frames.append(product_df)

    if not profile_frames:
        return df.copy()
    return pd.concat(profile_frames, ignore_index=True)


def make_features(
    monthly: pd.DataFrame,
    products: pd.DataFrame,
    *,
    inactive_months: int = 12,
    seasonal_top_3_month_share: float = 0.60,
    seasonal_max_active_months_per_year: int = 4,
) -> pd.DataFrame:
    del products
    df = monthly.copy()
    df["periodo"] = pd.to_datetime(df["periodo"])
    df = df.sort_values(["product_id", "periodo"]).reset_index(drop=True)

    duplicate_profile_cols = [col for col in PROFILE_COLUMNS if col in df.columns]
    if duplicate_profile_cols:
        df = df.drop(columns=duplicate_profile_cols)
    df = _historical_profile_by_product(
        df,
        inactive_months=inactive_months,
        seasonal_top_3_month_share=seasonal_top_3_month_share,
        seasonal_max_active_months_per_year=seasonal_max_active_months_per_year,
    )

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

    for col in MISSING_SIGNAL_COLUMNS:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    df[FEATURE_COLUMNS] = df[FEATURE_COLUMNS].fillna(0.0)
    return df
