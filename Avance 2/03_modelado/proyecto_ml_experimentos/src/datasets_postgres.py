import pandas as pd

from .postgres_loader import load_dwh_query, load_quickbooks_query


def load_forecasting_dataset():
    # Nota: se usa quickbooks.produccion porque hoy es la unica fuente con grano
    # producto-fecha para forecast t+1 por producto.
    # gold.kpis_produccion esta agregado por cliente y no conserva producto.
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
    if len(df) == 0:
        return df

    df["producto"] = df["producto"].astype(str).str.strip()
    df = df[(df["producto"] != "") & (df["producto"].str.lower() != "nan")].copy()
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    df = df[df["fecha"].notna()].copy()
    df["qty_fabricada"] = pd.to_numeric(df.get("qty_fabricada", 0), errors="coerce").fillna(0)
    df["qty_planificada"] = pd.to_numeric(df.get("qty_planificada", 0), errors="coerce").fillna(0)

    df = df.drop_duplicates(subset=["producto", "fecha", "qty_planificada", "qty_fabricada"]).copy()

    df["anio"] = df["fecha"].dt.year
    df["mes"] = df["fecha"].dt.month

    mensual = (
        df.groupby(["producto", "anio", "mes"], as_index=False)
        .agg(
            qty_fabricada=("qty_fabricada", "sum"),
            qty_planificada=("qty_planificada", "sum"),
            n_ordenes=("producto", "count"),
        )
    )
    mensual["periodo"] = pd.to_datetime(
        mensual["anio"].astype(str) + "-" + mensual["mes"].astype(str).str.zfill(2) + "-01",
        errors="coerce",
    )
    return mensual.sort_values(["producto", "periodo"]).reset_index(drop=True)


def load_association_dataset():
    query = """
    SELECT
        transaccion_id,
        producto,
        fecha
    FROM silver.apriori_transacciones
    WHERE transaccion_id IS NOT NULL
      AND producto IS NOT NULL
    """
    df = load_dwh_query(query)
    if len(df) == 0:
        return df

    df["transaccion_id"] = df["transaccion_id"].astype(str).str.strip()
    df["producto"] = df["producto"].astype(str).str.strip()
    if "fecha" in df.columns:
        df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")

    df = df[
        (df["transaccion_id"] != "")
        & (df["transaccion_id"].str.lower() != "nan")
        & (df["producto"] != "")
        & (df["producto"].str.lower() != "nan")
    ].copy()
    df = df.drop_duplicates(subset=["transaccion_id", "producto"]).copy()
    return df


def load_anomaly_dataset():
    query = """
    SELECT
        centro_costo AS agencia,
        tasa_devolucion AS ratio_devolucion,
        rentabilidad_promedio AS ratio_rentabilidad,
        (100 - rentabilidad_promedio) AS ratio_costo,
        ticket_promedio,
        total_venta AS total_ventas
    FROM gold.metricas_agencias
    """
    df = load_dwh_query(query)
    if len(df) == 0:
        return df

    df["agencia"] = df["agencia"].astype(str).str.strip().str.lower()
    df = df[(df["agencia"] != "") & (df["agencia"].str.lower() != "nan")].copy()
    for c in ["ratio_devolucion", "ratio_rentabilidad", "ratio_costo", "ticket_promedio", "total_ventas"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    if df["agencia"].duplicated().any():
        df = (
            df.groupby("agencia", as_index=False)
            .agg(
                ratio_devolucion=("ratio_devolucion", "mean"),
                ratio_rentabilidad=("ratio_rentabilidad", "mean"),
                ratio_costo=("ratio_costo", "mean"),
                ticket_promedio=("ticket_promedio", "mean"),
                total_ventas=("total_ventas", "sum"),
            )
        )
    return df
