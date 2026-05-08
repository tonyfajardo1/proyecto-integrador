import pandas as pd

from .postgres_loader import load_dwh_query, load_quickbooks_query


def _from_quickbooks():
    query = """
    SELECT
        producto,
        fecha,
        qty_planificada,
        qty_fabricada
    FROM quickbooks.produccion
    WHERE producto IS NOT NULL
      AND fecha IS NOT NULL
    """
    df = load_quickbooks_query(query)
    return df


def _from_dwh():
    # Tabla curada generada en pipelines Mage de DM
    query = """
    SELECT
        producto AS producto,
        periodo AS fecha,
        qty_planificada,
        qty_fabricada,
        n_ordenes
    FROM silver.produccion_modelado_mensual
    WHERE producto IS NOT NULL
      AND periodo IS NOT NULL
    """
    return load_dwh_query(query)


def load_monthly_production_dataset(source="dwh", fallback_quickbooks=True):
    source = (source or "dwh").lower().strip()

    df = pd.DataFrame()
    errors = []

    if source == "dwh":
        try:
            df = _from_dwh()
        except Exception as e:
            errors.append(f"dwh: {e}")
            df = pd.DataFrame()

        if (len(df) == 0) and fallback_quickbooks:
            try:
                df = _from_quickbooks()
            except Exception as e:
                errors.append(f"quickbooks: {e}")
                df = pd.DataFrame()
    else:
        try:
            df = _from_quickbooks()
        except Exception as e:
            errors.append(f"quickbooks: {e}")
            df = pd.DataFrame()

    if len(df) == 0 and errors:
        raise RuntimeError("No se pudo cargar dataset de produccion. " + " | ".join(errors))

    if len(df) == 0:
        return df

    df["producto"] = df["producto"].astype(str).str.strip()
    df = df[(df["producto"] != "") & (df["producto"].str.lower() != "nan")].copy()
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    df = df[df["fecha"].notna()].copy()
    df["qty_fabricada"] = pd.to_numeric(df.get("qty_fabricada", 0), errors="coerce").fillna(0)
    df["qty_planificada"] = pd.to_numeric(df.get("qty_planificada", 0), errors="coerce").fillna(0)
    if "n_ordenes" in df.columns:
        df["n_ordenes"] = pd.to_numeric(df.get("n_ordenes", 0), errors="coerce").fillna(0)

    dedup_cols = ["producto", "fecha", "qty_planificada", "qty_fabricada"]
    if "n_ordenes" in df.columns:
        dedup_cols.append("n_ordenes")
    df = df.drop_duplicates(subset=dedup_cols).copy()
    df["anio"] = df["fecha"].dt.year
    df["mes"] = df["fecha"].dt.month

    if "n_ordenes" in df.columns:
        monthly = (
            df.groupby(["producto", "anio", "mes"], as_index=False)
            .agg(
                qty_fabricada=("qty_fabricada", "sum"),
                qty_planificada=("qty_planificada", "sum"),
                n_ordenes=("n_ordenes", "sum"),
            )
        )
    else:
        monthly = (
            df.groupby(["producto", "anio", "mes"], as_index=False)
            .agg(
                qty_fabricada=("qty_fabricada", "sum"),
                qty_planificada=("qty_planificada", "sum"),
                n_ordenes=("producto", "count"),
            )
        )
    monthly["periodo"] = pd.to_datetime(
        monthly["anio"].astype(str) + "-" + monthly["mes"].astype(str).str.zfill(2) + "-01",
        errors="coerce",
    )
    return monthly.sort_values(["producto", "periodo"]).reset_index(drop=True)
