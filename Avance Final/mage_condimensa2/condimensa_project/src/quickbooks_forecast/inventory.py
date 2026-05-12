"""Cruce de stock actual y ajustes de inventario para el forecasting."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .cleaning import as_numeric, clean_string, extract_product_code, item_leaf, normalize_header, normalize_product_name


STOCK_OUTPUT_COLUMNS = [
    "product_id",
    "stock_actual",
    "stock_encontrado",
    "stock_match_status",
    "stock_item",
    "stock_item_description",
    "stock_fecha_referencia",
    "stock_avg_cost",
    "stock_asset_value",
]


def _rename_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [normalize_header(col).replace(" ", "_") for col in out.columns]
    return out


def _first_existing(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for col in candidates:
        if col in df.columns:
            return col
    return None


def _parse_excel_dates(series: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(series, errors="coerce")
    numeric = pd.to_numeric(series, errors="coerce")
    serial_mask = numeric.between(20000, 60000)
    if serial_mask.any():
        parsed.loc[serial_mask] = pd.to_datetime(
            numeric.loc[serial_mask],
            unit="D",
            origin="1899-12-30",
            errors="coerce",
        )
    return parsed


def _load_costs_stock(config: dict[str, Any]) -> pd.DataFrame:
    path = config["resolved_paths"].get("costs")
    if path is None or not path.exists():
        return pd.DataFrame()

    sheet_name = config.get("sheets", {}).get("costs", 0)
    raw = pd.read_excel(path, sheet_name=sheet_name)
    df = _rename_columns(raw)

    item_col = _first_existing(df, ["item", "producto", "product", "articulo"])
    desc_col = _first_existing(df, ["item_description", "description", "descripcion", "descripcion_item"])
    date_col = _first_existing(df, ["date", "fecha"])
    stock_col = _first_existing(df, ["on_hand", "qty_on_hand", "qty_onhand", "existencia", "stock", "stock_actual"])
    avg_cost_col = _first_existing(df, ["avg_cost", "costo_promedio", "average_cost"])
    asset_value_col = _first_existing(df, ["asset_value", "valor_activo", "valor_inventario"])

    if item_col is None or stock_col is None:
        return pd.DataFrame()

    out = pd.DataFrame(
        {
            "stock_item": df[item_col].map(clean_string),
            "stock_item_description": df[desc_col].map(clean_string) if desc_col else "",
            "stock_actual": as_numeric(df[stock_col]),
            "stock_fecha_referencia": _parse_excel_dates(df[date_col]) if date_col else pd.NaT,
            "stock_avg_cost": as_numeric(df[avg_cost_col]) if avg_cost_col else 0.0,
            "stock_asset_value": as_numeric(df[asset_value_col]) if asset_value_col else 0.0,
        }
    )
    out = out[out["stock_item"].ne("")].copy()
    out["_row_order"] = np.arange(out.shape[0])
    out["stock_item_norm"] = out["stock_item"].map(normalize_product_name)
    out["stock_item_leaf_norm"] = out["stock_item"].map(item_leaf).map(normalize_product_name)
    out["stock_description_norm"] = out["stock_item_description"].map(normalize_product_name)
    out["stock_product_code"] = out["stock_item"].map(extract_product_code)
    missing_code = out["stock_product_code"].eq("")
    out.loc[missing_code, "stock_product_code"] = out.loc[missing_code, "stock_item_description"].map(extract_product_code)

    sort_cols = ["stock_item_norm", "stock_fecha_referencia", "_row_order"]
    out = out.sort_values(sort_cols, na_position="first")
    out = out.drop_duplicates("stock_item_norm", keep="last").reset_index(drop=True)
    return out


def _product_match_keys(products: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for row in products.itertuples(index=False):
        product_id = getattr(row, "product_id")
        candidates = [
            ("code", getattr(row, "product_code", ""), 1),
            ("item_path", getattr(row, "item_path", ""), 2),
            ("item_leaf", getattr(row, "item_leaf", ""), 3),
            ("product_norm", getattr(row, "product_norm", ""), 4),
            ("product_name", getattr(row, "product_name", ""), 5),
        ]
        for key_type, value, priority in candidates:
            if key_type == "code":
                key = clean_string(value)
                match_key = f"code:{key}" if key else ""
            else:
                match_key = normalize_product_name(value)
            if match_key:
                rows.append(
                    {
                        "product_id": product_id,
                        "match_key": match_key,
                        "product_key_type": key_type,
                        "product_priority": priority,
                    }
                )
    return pd.DataFrame(rows).drop_duplicates()


def _stock_match_keys(stock: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for row in stock.itertuples(index=False):
        candidates = [
            ("code", getattr(row, "stock_product_code", ""), 1),
            ("item", getattr(row, "stock_item_norm", ""), 2),
            ("item_leaf", getattr(row, "stock_item_leaf_norm", ""), 3),
            ("description", getattr(row, "stock_description_norm", ""), 4),
        ]
        for key_type, value, priority in candidates:
            key = clean_string(value)
            match_key = f"code:{key}" if key_type == "code" and key else key
            if match_key:
                rows.append(
                    {
                        "match_key": match_key,
                        "stock_key_type": key_type,
                        "stock_priority": priority,
                        "stock_item": row.stock_item,
                        "stock_item_description": row.stock_item_description,
                        "stock_actual": row.stock_actual,
                        "stock_fecha_referencia": row.stock_fecha_referencia,
                        "stock_avg_cost": row.stock_avg_cost,
                        "stock_asset_value": row.stock_asset_value,
                    }
                )
    return pd.DataFrame(rows).drop_duplicates()


def build_current_stock(config: dict[str, Any], source: str, products: pd.DataFrame) -> pd.DataFrame:
    """Empata productos del modelo con el stock actual disponible en costos."""
    stock = _load_costs_stock(config)
    base = products[["product_id"]].drop_duplicates().copy()
    if stock.empty:
        for col in STOCK_OUTPUT_COLUMNS:
            if col not in base.columns:
                base[col] = np.nan
        base["stock_actual"] = 0.0
        base["stock_encontrado"] = False
        base["stock_match_status"] = "archivo_stock_no_disponible"
        return base[STOCK_OUTPUT_COLUMNS]

    product_keys = _product_match_keys(products)
    stock_keys = _stock_match_keys(stock)
    matches = product_keys.merge(stock_keys, on="match_key", how="inner")
    if matches.empty:
        out = base.copy()
        out["stock_actual"] = 0.0
        out["stock_encontrado"] = False
        out["stock_match_status"] = "sin_match_stock"
        out["stock_item"] = ""
        out["stock_item_description"] = ""
        out["stock_fecha_referencia"] = pd.NaT
        out["stock_avg_cost"] = 0.0
        out["stock_asset_value"] = 0.0
        return out[STOCK_OUTPUT_COLUMNS]

    matches["match_score"] = matches["product_priority"] + matches["stock_priority"]
    matches["stock_match_status"] = matches["product_key_type"] + "_vs_" + matches["stock_key_type"]
    best = (
        matches.sort_values(["product_id", "match_score", "product_priority", "stock_priority"])
        .drop_duplicates("product_id", keep="first")
        .copy()
    )

    out = base.merge(
        best[
            [
                "product_id",
                "stock_actual",
                "stock_match_status",
                "stock_item",
                "stock_item_description",
                "stock_fecha_referencia",
                "stock_avg_cost",
                "stock_asset_value",
            ]
        ],
        on="product_id",
        how="left",
    )
    out["stock_encontrado"] = out["stock_actual"].notna()
    out["stock_actual"] = out["stock_actual"].fillna(0.0)
    out["stock_match_status"] = out["stock_match_status"].fillna("sin_match_stock")
    out["stock_item"] = out["stock_item"].fillna("")
    out["stock_item_description"] = out["stock_item_description"].fillna("")
    out["stock_avg_cost"] = out["stock_avg_cost"].fillna(0.0)
    out["stock_asset_value"] = out["stock_asset_value"].fillna(0.0)
    out["source_type"] = source
    reports_dir = config["resolved_paths"]["reports_dir"]
    reports_dir.mkdir(parents=True, exist_ok=True)
    out.to_csv(reports_dir / f"stock_actual_{source.lower()}.csv", index=False, encoding="utf-8")
    return out[STOCK_OUTPUT_COLUMNS]


def _load_stock_policy(config: dict[str, Any]) -> pd.DataFrame:
    path = config["resolved_paths"]["input_dir"] / "stock_min_max_template.csv"
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame(columns=["product_id", "stock_minimo", "stock_maximo"])
    policy = pd.read_csv(path)
    if "product_id" not in policy.columns:
        return pd.DataFrame(columns=["product_id", "stock_minimo", "stock_maximo"])
    out = policy[["product_id"]].copy()
    out["stock_minimo"] = pd.to_numeric(policy.get("stock_minimo", 0.0), errors="coerce").fillna(0.0)
    out["stock_maximo"] = pd.to_numeric(policy.get("stock_maximo", np.nan), errors="coerce")
    return out.drop_duplicates("product_id", keep="last")


def _project_inventory_for_product(group: pd.DataFrame) -> pd.DataFrame:
    out = group.sort_values("periodo").copy()
    available = float(out["stock_actual"].iloc[0])
    min_stock = float(out["stock_minimo"].iloc[0])
    max_stock = out["stock_maximo"].iloc[0]
    max_stock = float(max_stock) if pd.notna(max_stock) else np.nan

    starts = []
    ends = []
    production = []
    alerts = []

    for row in out.itertuples(index=False):
        demand = float(getattr(row, "cantidad_predicha"))
        start_stock = available
        required = max(demand + min_stock - start_stock, 0.0)
        if pd.notna(max_stock):
            capacity_to_max = max(max_stock - start_stock, 0.0)
            required = min(required, capacity_to_max)
        end_stock = start_stock + required - demand

        if not bool(getattr(row, "stock_encontrado")):
            alert = "sin_stock_actual"
        elif pd.notna(max_stock) and start_stock > max_stock:
            alert = "sobrestock"
        elif end_stock < min_stock:
            alert = "riesgo_quiebre_stock"
        else:
            alert = "dentro_rango"

        starts.append(round(start_stock, 2))
        ends.append(round(end_stock, 2))
        production.append(round(required, 2))
        alerts.append(alert)
        available = end_stock

    out["stock_proyectado_inicio"] = starts
    out["stock_proyectado_fin"] = ends
    out["cantidad_a_producir_ajustada"] = production
    out["alerta_inventario"] = alerts
    return out


def apply_inventory_adjustments(config: dict[str, Any], source: str, predictions: pd.DataFrame) -> pd.DataFrame:
    """Convierte forecast de demanda en una sugerencia ajustada por inventario."""
    processed_dir = config["resolved_paths"]["processed_dir"]
    products = pd.read_csv(processed_dir / f"{source.lower()}_productos_model.csv")
    stock = build_current_stock(config, source, products)
    policy = _load_stock_policy(config)

    out = predictions.merge(stock, on="product_id", how="left")
    out = out.merge(policy, on="product_id", how="left")
    out["stock_actual"] = out["stock_actual"].fillna(0.0)
    out["stock_encontrado"] = out["stock_encontrado"].fillna(False)
    out["stock_match_status"] = out["stock_match_status"].fillna("sin_match_stock")
    out["stock_minimo"] = out["stock_minimo"].fillna(0.0)
    out["stock_item"] = out["stock_item"].fillna("")
    out["stock_item_description"] = out["stock_item_description"].fillna("")
    out["stock_avg_cost"] = out["stock_avg_cost"].fillna(0.0)
    out["stock_asset_value"] = out["stock_asset_value"].fillna(0.0)

    adjusted = pd.concat(
        [_project_inventory_for_product(group) for _, group in out.groupby("product_id", sort=False)],
        ignore_index=True,
    )
    adjusted["valor_stock_actual"] = (adjusted["stock_actual"] * adjusted["stock_avg_cost"]).round(2)
    adjusted["valor_produccion_ajustada"] = (
        adjusted["cantidad_a_producir_ajustada"] * adjusted["stock_avg_cost"]
    ).round(2)
    return adjusted
