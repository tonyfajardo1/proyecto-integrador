from __future__ import annotations

from difflib import get_close_matches
from pathlib import Path
from typing import Any

import pandas as pd

from .cleaning import (
    MONTH_NAMES_ES,
    as_numeric,
    clean_string,
    extract_product_code,
    infer_product_type,
    item_leaf,
    make_product_id,
    mode_or_blank,
    normalize_header,
    normalize_product_name,
    remove_product_prefix,
    to_month_start,
)
from .config import ensure_output_dirs
from .exogenous import add_exogenous_features, build_exogenous_templates, write_exogenous_report


def _rename_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [normalize_header(c) for c in out.columns]
    return out


def _safe_write(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8")
    parquet_path = path.with_suffix(".parquet")
    df.to_parquet(parquet_path, index=False)


def _has_child(item: str, all_items: set[str]) -> bool:
    prefix = f"{item}:"
    return any(other.startswith(prefix) for other in all_items if other != item)


def build_pt_catalog(config: dict[str, Any]) -> pd.DataFrame:
    path = config["resolved_paths"]["catalog"]
    sheet = config["sheets"]["catalog"]
    df = pd.read_excel(path, sheet_name=sheet)

    df = df.rename(
        columns={
            "Item": "item_path",
            "Description": "description",
            "U/M": "unit",
            "Price": "price",
            "EAN13": "ean13",
            "EAN14": "ean14",
        }
    )
    for col in ["item_path", "description", "unit", "ean13", "ean14"]:
        df[col] = df.get(col, "").map(clean_string)
    df["price"] = as_numeric(df.get("price", pd.Series(dtype=float)))

    df = df[df["item_path"].ne("")].copy()
    df["product_type"] = df["item_path"].map(infer_product_type)
    pt = df[df["product_type"].eq("PT")].copy()

    item_set = set(pt["item_path"])
    pt["is_leaf"] = ~pt["item_path"].map(lambda item: _has_child(item, item_set))
    pt["item_leaf"] = pt["item_path"].map(item_leaf)
    pt["product_name"] = pt["description"].where(pt["description"].ne(""), pt["item_leaf"])
    pt["product_norm"] = pt["product_name"].map(normalize_product_name)
    pt["item_leaf_norm"] = pt["item_leaf"].map(normalize_product_name)
    pt["product_code"] = pt["product_name"].map(extract_product_code)
    missing_code = pt["product_code"].eq("")
    pt.loc[missing_code, "product_code"] = pt.loc[missing_code, "item_leaf"].map(extract_product_code)
    pt["product_id"] = [
        make_product_id("PT", code, norm)
        for code, norm in zip(pt["product_code"], pt["product_norm"], strict=False)
    ]

    products = pt[pt["is_leaf"] & pt["product_norm"].ne("")].copy()
    products["quality_score"] = (
        products["ean13"].ne("").astype(int) * 4
        + products["ean14"].ne("").astype(int) * 4
        + products["unit"].ne("").astype(int) * 2
        + products["price"].gt(0).astype(int)
        + products["item_path"].str.len().fillna(0) / 10000
    )
    products = (
        products.sort_values(["product_id", "quality_score"], ascending=[True, False])
        .drop_duplicates("product_id", keep="first")
        .drop(columns=["quality_score"])
        .reset_index(drop=True)
    )

    return products[
        [
            "product_id",
            "product_code",
            "product_name",
            "product_norm",
            "item_leaf",
            "item_leaf_norm",
            "item_path",
            "description",
            "unit",
            "price",
            "ean13",
            "ean14",
            "is_leaf",
        ]
    ]


def _unique_map(df: pd.DataFrame, key_col: str) -> dict[str, dict[str, Any]]:
    tmp = df[df[key_col].ne("")].copy()
    counts = tmp.groupby(key_col)["product_id"].nunique()
    unique_keys = set(counts[counts.eq(1)].index)
    out: dict[str, dict[str, Any]] = {}
    for key, row in tmp[tmp[key_col].isin(unique_keys)].drop_duplicates(key_col).set_index(key_col).iterrows():
        out[key] = row.to_dict()
    return out


def _catalog_lookup(catalog: pd.DataFrame) -> dict[str, Any]:
    norm_map = _unique_map(catalog, "product_norm")
    leaf_map = _unique_map(catalog, "item_leaf_norm")
    code_map = _unique_map(catalog, "product_code")
    fuzzy_choices = sorted(set(catalog["product_norm"].dropna()) | set(catalog["item_leaf_norm"].dropna()))
    fuzzy_to_row = {**norm_map, **leaf_map}
    return {
        "norm": norm_map,
        "leaf": leaf_map,
        "code": code_map,
        "fuzzy_choices": fuzzy_choices,
        "fuzzy_to_row": fuzzy_to_row,
    }


def _match_pt_product(row: pd.Series, lookup: dict[str, Any]) -> dict[str, Any]:
    norm = row["product_norm"]
    code = row["product_code"]

    if norm in lookup["norm"]:
        match = lookup["norm"][norm].copy()
        match["catalog_match_status"] = "exact_description"
        return match
    if norm in lookup["leaf"]:
        match = lookup["leaf"][norm].copy()
        match["catalog_match_status"] = "exact_item_leaf"
        return match
    if code and code in lookup["code"]:
        match = lookup["code"][code].copy()
        match["catalog_match_status"] = "product_code"
        return match

    close = get_close_matches(norm, lookup["fuzzy_choices"], n=1, cutoff=0.88)
    if close:
        match = lookup["fuzzy_to_row"][close[0]].copy()
        match["catalog_match_status"] = "fuzzy_name"
        return match

    product_id = make_product_id("PT_UNMATCHED", code, norm)
    return {
        "product_id": product_id,
        "product_code": code,
        "product_name": row["producto_raw"],
        "product_norm": norm,
        "item_leaf": "",
        "item_leaf_norm": "",
        "item_path": "",
        "description": "",
        "unit": "",
        "price": 0.0,
        "ean13": "",
        "ean14": "",
        "is_leaf": False,
        "catalog_match_status": "no_catalog_match",
    }


def _complete_monthly_grid(
    monthly: pd.DataFrame,
    products: pd.DataFrame,
    value_columns: list[str],
    latest_period: pd.Timestamp | None = None,
) -> pd.DataFrame:
    if latest_period is None:
        latest_period = monthly["periodo"].max()

    activity = (
        monthly[monthly["target_qty"].gt(0)]
        .groupby("product_id")["periodo"]
        .min()
        .rename("first_period")
        .reset_index()
    )
    products_with_start = products.merge(activity, on="product_id", how="inner")

    grids = []
    for row in products_with_start.itertuples(index=False):
        periods = pd.date_range(row.first_period, latest_period, freq="MS")
        grids.append(pd.DataFrame({"product_id": row.product_id, "periodo": periods}))

    if not grids:
        return monthly.iloc[0:0].copy()

    grid = pd.concat(grids, ignore_index=True)
    out = grid.merge(monthly, on=["product_id", "periodo"], how="left")
    for col in value_columns:
        out[col] = out[col].fillna(0.0)
    return out.merge(products, on="product_id", how="left")


def summarize_products(
    monthly: pd.DataFrame,
    inactive_months: int,
    seasonal_top_3_month_share: float,
    seasonal_max_active_months_per_year: int,
) -> pd.DataFrame:
    data = monthly.copy()
    data["periodo"] = pd.to_datetime(data["periodo"])
    latest_period = data["periodo"].max()
    cutoff = latest_period - pd.DateOffset(months=inactive_months - 1)

    active_rows = data[data["target_qty"].gt(0)].copy()
    base = (
        data.groupby("product_id", as_index=False)
        .agg(
            producto=("product_name", "first"),
            total_qty=("target_qty", "sum"),
            meses_en_serie=("periodo", "nunique"),
        )
    )
    activity = (
        active_rows.groupby("product_id", as_index=False)
        .agg(
            primera_actividad=("periodo", "min"),
            ultima_actividad=("periodo", "max"),
            meses_con_actividad=("periodo", "nunique"),
        )
    )
    summary = base.merge(activity, on="product_id", how="left")
    summary["periodo_referencia"] = latest_period
    summary["corte_inactividad"] = cutoff
    summary["estado_producto"] = summary["ultima_actividad"].apply(
        lambda value: "activo" if pd.notna(value) and value >= cutoff else "inactivo"
    )

    data["month_num"] = data["periodo"].dt.month
    by_month = active_rows.assign(month_num=active_rows["periodo"].dt.month)
    month_qty = by_month.groupby(["product_id", "month_num"], as_index=False)["target_qty"].sum()

    seasonal_rows = []
    for product_id, group in month_qty.groupby("product_id"):
        total = group["target_qty"].sum()
        sorted_months = group.sort_values("target_qty", ascending=False)
        top3_share = 0.0 if total <= 0 else sorted_months.head(3)["target_qty"].sum() / total
        top_months = sorted_months.head(3)["month_num"].astype(int).tolist()
        product_history = data[data["product_id"].eq(product_id)].copy()
        active_per_year = (
            product_history[product_history["target_qty"].gt(0)]
            .assign(year=product_history["periodo"].dt.year)
            .groupby("year")["month_num"]
            .nunique()
        )
        median_active_months = float(active_per_year.median()) if len(active_per_year) else 0.0
        active_years = int(active_per_year.shape[0])
        is_seasonal = active_years >= 2 and (
            top3_share >= seasonal_top_3_month_share
            or median_active_months <= seasonal_max_active_months_per_year
        )
        seasonal_rows.append(
            {
                "product_id": product_id,
                "es_estacional": bool(is_seasonal),
                "share_top_3_meses": round(float(top3_share), 4),
                "mediana_meses_activos_por_anio": round(median_active_months, 2),
                "meses_estacionales_num": ",".join(str(m) for m in top_months),
                "meses_estacionales": ", ".join(MONTH_NAMES_ES[m] for m in top_months),
            }
        )

    seasonal = pd.DataFrame(seasonal_rows)
    summary = summary.merge(seasonal, on="product_id", how="left")
    summary["es_estacional"] = summary["es_estacional"].fillna(False)
    summary["share_top_3_meses"] = summary["share_top_3_meses"].fillna(0.0)
    summary["mediana_meses_activos_por_anio"] = summary["mediana_meses_activos_por_anio"].fillna(0.0)
    summary["meses_estacionales_num"] = summary["meses_estacionales_num"].fillna("")
    summary["meses_estacionales"] = summary["meses_estacionales"].fillna("")
    return summary


def build_pt_dataset(config: dict[str, Any], catalog: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    path = config["resolved_paths"]["sales"]
    sheet = config["sheets"]["sales"]
    df = pd.read_excel(path, sheet_name=sheet)
    df = _rename_columns(df).rename(
        columns={
            "marca": "marca",
            "familia": "familia",
            "producto": "producto_raw",
            "recuento de cliente": "recuento_cliente",
            "cantidad": "cantidad",
            "ventas": "ventas",
            "ano": "anio",
            "mes": "mes",
        }
    )

    df["producto_raw"] = df["producto_raw"].map(clean_string)
    df = df[df["producto_raw"].ne("")].copy()
    df["cantidad"] = as_numeric(df["cantidad"])
    df["ventas"] = as_numeric(df["ventas"])
    df["recuento_cliente"] = as_numeric(df["recuento_cliente"])
    df["periodo"] = to_month_start(df["anio"], df["mes"])
    df = df[df["periodo"].notna()].copy()
    df["product_norm"] = df["producto_raw"].map(normalize_product_name)
    df["product_code"] = df["producto_raw"].map(extract_product_code)

    lookup = _catalog_lookup(catalog)
    unique_products = (
        df.groupby("product_norm", as_index=False)
        .agg(
            producto_raw=("producto_raw", mode_or_blank),
            product_code=("product_code", mode_or_blank),
            cantidad_total=("cantidad", "sum"),
            ventas_total=("ventas", "sum"),
            marca=("marca", mode_or_blank),
            familia=("familia", mode_or_blank),
        )
        .sort_values("cantidad_total", ascending=False)
    )
    matches = pd.DataFrame([_match_pt_product(row, lookup) for _, row in unique_products.iterrows()])
    matches = matches.rename(
        columns={
            "product_code": "catalog_product_code",
            "product_norm": "catalog_product_norm",
        }
    )
    match_table = pd.concat([unique_products.reset_index(drop=True), matches.reset_index(drop=True)], axis=1)

    df = df.merge(
        match_table[["product_norm", "product_id", "product_name", "catalog_match_status"]],
        on="product_norm",
        how="left",
    )
    monthly = (
        df.groupby(["product_id", "periodo"], as_index=False)
        .agg(
            target_qty=("cantidad", "sum"),
            ventas=("ventas", "sum"),
            recuento_cliente=("recuento_cliente", "sum"),
            productos_raw_distintos=("producto_raw", "nunique"),
        )
    )
    monthly["target_qty_raw"] = monthly["target_qty"]
    monthly["target_qty"] = monthly["target_qty"].clip(lower=0.0)

    product_meta = (
        match_table.groupby("product_id", as_index=False)
        .agg(
            product_code=("catalog_product_code", mode_or_blank),
            product_name=("product_name", "first"),
            product_norm=("product_norm", "first"),
            catalog_match_status=("catalog_match_status", "first"),
            item_path=("item_path", "first"),
            unit=("unit", "first"),
            price=("price", "first"),
            ean13=("ean13", "first"),
            ean14=("ean14", "first"),
            marca=("marca", mode_or_blank),
            familia=("familia", mode_or_blank),
            cantidad_total_raw=("cantidad_total", "sum"),
            ventas_total_raw=("ventas_total", "sum"),
        )
    )
    product_meta["source_type"] = "PT"

    grid = _complete_monthly_grid(
        monthly,
        product_meta,
        ["target_qty", "target_qty_raw", "ventas", "recuento_cliente", "productos_raw_distintos"],
    )
    product_meta = product_meta[product_meta["product_id"].isin(grid["product_id"].unique())].copy()
    summary = summarize_products(
        grid,
        inactive_months=config["dataset"]["inactive_months"],
        seasonal_top_3_month_share=config["dataset"]["seasonal_top_3_month_share"],
        seasonal_max_active_months_per_year=config["dataset"]["seasonal_max_active_months_per_year"],
    )
    products = product_meta.merge(summary.drop(columns=["producto"]), on="product_id", how="left")
    grid = grid.merge(
        products[
            [
                "product_id",
                "estado_producto",
                "es_estacional",
                "share_top_3_meses",
                "meses_estacionales_num",
                "meses_estacionales",
                "ultima_actividad",
            ]
        ],
        on="product_id",
        how="left",
    )

    reports_dir = config["resolved_paths"]["reports_dir"]
    unmatched = (
        match_table[match_table["catalog_match_status"].eq("no_catalog_match")]
        .sort_values("cantidad_total", ascending=False)
        .copy()
    )
    _safe_write(match_table, reports_dir / "pt_catalog_match_report.csv")
    _safe_write(unmatched, reports_dir / "pt_productos_no_catalogo.csv")

    return grid, products


def _load_pp_categories(config: dict[str, Any]) -> dict[str, str]:
    try:
        df = pd.read_excel(
            config["resolved_paths"]["production"],
            sheet_name=config["sheets"]["pp_categories"],
        )
    except ValueError:
        return {}

    df = _rename_columns(df).rename(columns={"familia": "familia", "categorias pp": "categoria_pp"})
    if "familia" not in df or "categoria_pp" not in df:
        return {}
    df["familia_norm"] = df["familia"].map(normalize_product_name)
    return {
        row.familia_norm: clean_string(row.categoria_pp)
        for row in df.itertuples(index=False)
        if row.familia_norm and clean_string(row.categoria_pp)
    }


def build_pp_dataset(config: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    path = config["resolved_paths"]["production"]
    sheet = config["sheets"]["production"]
    df = pd.read_excel(path, sheet_name=sheet)
    df = _rename_columns(df).rename(
        columns={
            "fecha": "fecha",
            "numero": "numero",
            "lote": "lote",
            "producto": "producto_raw",
            "q panificda": "q_planificada",
            "q liberada": "q_liberada",
            "q fabricada": "q_fabricada",
        }
    )
    df["producto_raw"] = df["producto_raw"].map(clean_string)
    df["product_type"] = df["producto_raw"].map(infer_product_type)
    df = df[df["product_type"].eq("PP")].copy()
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    df = df[df["fecha"].notna()].copy()
    df["periodo"] = df["fecha"].values.astype("datetime64[M]")

    for col in ["q_planificada", "q_liberada", "q_fabricada"]:
        df[col] = as_numeric(df[col])
    df["target_qty"] = df["q_fabricada"].where(df["q_fabricada"].gt(0), df["q_liberada"])
    df["target_qty"] = df["target_qty"].where(df["target_qty"].gt(0), df["q_planificada"]).fillna(0.0)
    df["product_name"] = df["producto_raw"].map(remove_product_prefix)
    df["product_norm"] = df["producto_raw"].map(normalize_product_name)
    df["product_id"] = [make_product_id("PP", "", norm) for norm in df["product_norm"]]
    df["product_code"] = ""

    categories = _load_pp_categories(config)
    df["product_leaf_norm"] = df["product_name"].map(normalize_product_name)
    df["categoria_pp"] = df["product_leaf_norm"].map(categories).fillna("")

    monthly = (
        df.groupby(["product_id", "periodo"], as_index=False)
        .agg(
            target_qty=("target_qty", "sum"),
            q_planificada=("q_planificada", "sum"),
            q_liberada=("q_liberada", "sum"),
            q_fabricada=("q_fabricada", "sum"),
            lotes=("lote", "nunique"),
            ordenes=("numero", "nunique"),
        )
    )
    monthly["target_qty_raw"] = monthly["target_qty"]
    monthly["target_qty"] = monthly["target_qty"].clip(lower=0.0)
    product_meta = (
        df.groupby("product_id", as_index=False)
        .agg(
            product_code=("product_code", "first"),
            product_name=("product_name", mode_or_blank),
            product_norm=("product_norm", "first"),
            categoria_pp=("categoria_pp", mode_or_blank),
        )
    )
    product_meta["source_type"] = "PP"
    product_meta["catalog_match_status"] = "production_pp"

    grid = _complete_monthly_grid(
        monthly,
        product_meta,
        ["target_qty", "target_qty_raw", "q_planificada", "q_liberada", "q_fabricada", "lotes", "ordenes"],
    )
    product_meta = product_meta[product_meta["product_id"].isin(grid["product_id"].unique())].copy()
    summary = summarize_products(
        grid,
        inactive_months=config["dataset"]["inactive_months"],
        seasonal_top_3_month_share=config["dataset"]["seasonal_top_3_month_share"],
        seasonal_max_active_months_per_year=config["dataset"]["seasonal_max_active_months_per_year"],
    )
    products = product_meta.merge(summary.drop(columns=["producto"]), on="product_id", how="left")
    grid = grid.merge(
        products[
            [
                "product_id",
                "estado_producto",
                "es_estacional",
                "share_top_3_meses",
                "meses_estacionales_num",
                "meses_estacionales",
                "ultima_actividad",
            ]
        ],
        on="product_id",
        how="left",
    )
    return grid, products


def write_dataset_summary(
    config: dict[str, Any],
    pt_monthly: pd.DataFrame,
    pt_products: pd.DataFrame,
    pp_monthly: pd.DataFrame,
    pp_products: pd.DataFrame,
) -> None:
    reports_dir = config["resolved_paths"]["reports_dir"]
    unmatched_path = reports_dir / "pt_productos_no_catalogo.csv"
    unmatched_count = 0
    if unmatched_path.exists():
        unmatched_count = pd.read_csv(unmatched_path).shape[0]

    lines = [
        "# Resumen de datasets QuickBooks",
        "",
        "## PT ventas",
        f"- Productos en serie mensual total: {pt_products.shape[0]}",
        f"- Productos activos: {int(pt_products['estado_producto'].eq('activo').sum())}",
        f"- Productos inactivos: {int(pt_products['estado_producto'].eq('inactivo').sum())}",
        f"- Productos estacionales: {int(pt_products['es_estacional'].sum())}",
        f"- Productos de ventas sin match de catalogo: {unmatched_count}",
        f"- Periodo minimo: {pt_monthly['periodo'].min().date()}",
        f"- Periodo maximo: {pt_monthly['periodo'].max().date()}",
        "",
        "## PP produccion",
        f"- Productos en serie mensual total: {pp_products.shape[0]}",
        f"- Productos activos: {int(pp_products['estado_producto'].eq('activo').sum())}",
        f"- Productos inactivos: {int(pp_products['estado_producto'].eq('inactivo').sum())}",
        f"- Productos estacionales: {int(pp_products['es_estacional'].sum())}",
        f"- Periodo minimo: {pp_monthly['periodo'].min().date()}",
        f"- Periodo maximo: {pp_monthly['periodo'].max().date()}",
        "",
    ]
    (reports_dir / "data_quality_summary.md").write_text("\n".join(lines), encoding="utf-8")


def build_all_datasets(config: dict[str, Any]) -> dict[str, pd.DataFrame]:
    ensure_output_dirs(config)
    processed_dir = config["resolved_paths"]["processed_dir"]

    catalog = build_pt_catalog(config)
    _safe_write(catalog, processed_dir / "catalogo_pt_limpio.csv")

    pt_monthly, pt_products = build_pt_dataset(config, catalog)
    pp_monthly, pp_products = build_pp_dataset(config)

    include_unmatched = bool(config["dataset"].get("include_unmatched_pt", False))
    if include_unmatched:
        pt_monthly_model = pt_monthly.copy()
        pt_products_model = pt_products.copy()
    else:
        matched_ids = set(pt_products[~pt_products["catalog_match_status"].eq("no_catalog_match")]["product_id"])
        pt_monthly_model = pt_monthly[pt_monthly["product_id"].isin(matched_ids)].copy()
        pt_products_model = pt_products[pt_products["product_id"].isin(matched_ids)].copy()

    build_exogenous_templates(config, pt_monthly_model, pt_products_model, pp_monthly, pp_products)
    pt_monthly_model = add_exogenous_features(config, pt_monthly_model, "PT")
    pp_monthly = add_exogenous_features(config, pp_monthly, "PP")

    _safe_write(pt_monthly, processed_dir / "pt_mensual.csv")
    _safe_write(pt_products, processed_dir / "pt_productos.csv")
    _safe_write(pt_monthly_model, processed_dir / "pt_mensual_model.csv")
    _safe_write(pt_products_model, processed_dir / "pt_productos_model.csv")
    _safe_write(pp_monthly, processed_dir / "pp_mensual.csv")
    _safe_write(pp_products, processed_dir / "pp_productos.csv")
    _safe_write(pp_monthly, processed_dir / "pp_mensual_model.csv")
    _safe_write(pp_products, processed_dir / "pp_productos_model.csv")

    write_dataset_summary(config, pt_monthly_model, pt_products_model, pp_monthly, pp_products)
    write_exogenous_report(config)

    return {
        "catalog": catalog,
        "pt_monthly": pt_monthly_model,
        "pt_products": pt_products_model,
        "pp_monthly": pp_monthly,
        "pp_products": pp_products,
    }
