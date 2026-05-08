import pandas as pd
from .db import connect_dwh, connect_quickbooks, query_df


def load_monthly_dataset(source="dwh", fallback_quickbooks=True) -> pd.DataFrame:
    source = str(source).lower().strip()
    errs = []
    df = pd.DataFrame()

    if source == "dwh":
        try:
            with connect_dwh() as conn:
                df = query_df(
                    conn,
                    """
                    SELECT
                        COALESCE(NULLIF(TRIM(tipo_producto), ''), 'OTRO') AS tipo_producto,
                        producto,
                        periodo AS fecha,
                        qty_planificada,
                        qty_fabricada,
                        n_ordenes
                    FROM silver.produccion_modelado_mensual
                    WHERE producto IS NOT NULL AND periodo IS NOT NULL
                    """,
                )
        except Exception as e:
            errs.append(f"dwh: {e}")
            df = pd.DataFrame()

        if len(df) == 0 and fallback_quickbooks:
            try:
                with connect_quickbooks() as conn:
                    raw = query_df(
                        conn,
                        """
                        SELECT producto, fecha, qty_planificada, qty_fabricada
                        FROM quickbooks.produccion
                        WHERE producto IS NOT NULL AND fecha IS NOT NULL
                        """
                    )
                raw["fecha"] = pd.to_datetime(raw["fecha"], errors="coerce")
                raw = raw[raw["fecha"].notna()].copy()
                raw["producto"] = raw["producto"].astype(str).str.strip()
                raw["tipo_producto"] = raw["producto"].astype(str).str.upper().str.strip().str[:2]
                raw.loc[~raw["tipo_producto"].isin(["PT", "PP"]), "tipo_producto"] = "OTRO"
                raw["qty_fabricada"] = pd.to_numeric(raw.get("qty_fabricada", 0), errors="coerce").fillna(0)
                raw["qty_planificada"] = pd.to_numeric(raw.get("qty_planificada", 0), errors="coerce").fillna(0)
                raw["anio"] = raw["fecha"].dt.year
                raw["mes"] = raw["fecha"].dt.month
                df = (
                    raw.groupby(["tipo_producto", "producto", "anio", "mes"], as_index=False)
                    .agg(
                        qty_fabricada=("qty_fabricada", "sum"),
                        qty_planificada=("qty_planificada", "sum"),
                        n_ordenes=("producto", "count"),
                    )
                )
                df["fecha"] = pd.to_datetime(
                    df["anio"].astype(str) + "-" + df["mes"].astype(str).str.zfill(2) + "-01"
                )
                df = df[["tipo_producto", "producto", "fecha", "qty_planificada", "qty_fabricada", "n_ordenes"]]
            except Exception as e:
                errs.append(f"quickbooks: {e}")
                df = pd.DataFrame()
    else:
        if source == "dwh_forecasting_v1":
            try:
                with connect_dwh() as conn:
                    df = query_df(
                        conn,
                        """
                        SELECT
                            COALESCE(NULLIF(TRIM(b.tipo_producto), ''), 'OTRO') AS tipo_producto,
                            COALESCE(
                                NULLIF(TRIM(b.producto_dashboard), ''),
                                NULLIF(TRIM(b.producto_item), ''),
                                NULLIF(TRIM(b.codigo_producto), ''),
                                NULLIF(TRIM(b.ean13), '')
                            ) AS producto,
                            b.periodo AS fecha,
                            0::numeric AS qty_planificada,
                            COALESCE(b.qty_vendida, 0)::numeric AS qty_fabricada,
                            COALESCE(b.clientes, 0)::numeric AS n_ordenes
                        FROM silver.forecasting_base_mensual_v1 b
                        WHERE b.periodo IS NOT NULL
                        """,
                    )
            except Exception as e:
                errs.append(f"dwh_forecasting_v1: {e}")
                df = pd.DataFrame()
        else:
            raise ValueError("source debe ser 'dwh' o 'dwh_forecasting_v1'")

    if len(df) == 0 and errs:
        raise RuntimeError("No se pudo cargar dataset: " + " | ".join(errs))

    if len(df) == 0:
        return df

    df["producto"] = df["producto"].astype(str).str.strip()
    if "tipo_producto" not in df.columns:
        df["tipo_producto"] = "OTRO"
    df["tipo_producto"] = df["tipo_producto"].astype(str).str.upper().str.strip()
    df.loc[~df["tipo_producto"].isin(["PT", "PP"]), "tipo_producto"] = "OTRO"
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    df = df[(df["producto"] != "") & df["fecha"].notna()].copy()
    for c in ["qty_planificada", "qty_fabricada", "n_ordenes"]:
        if c not in df.columns:
            df[c] = 0
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

    df = df.drop_duplicates(
        subset=["tipo_producto", "producto", "fecha", "qty_planificada", "qty_fabricada", "n_ordenes"]
    ).copy()
    df = df.rename(columns={"fecha": "periodo"}).sort_values(["producto", "periodo"]).reset_index(drop=True)
    return df
