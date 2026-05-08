"""
Reemplaza datos QuickBooks en Supabase con archivos locales.

Acciones:
1) Respaldar tablas actuales quickbooks.sales, sales_lineas, produccion, produccion_lineas
2) Truncar esas tablas
3) Cargar datos transformados desde carpeta local Quickbooks

Uso:
  python reemplazar_quickbooks_con_local.py
"""

from __future__ import annotations

import io
import os
from datetime import datetime
from pathlib import Path

import pandas as pd
import psycopg2


ROOT = Path(r"F:\proyecto-integrador")
QB_DIR = ROOT / "Avance 2" / "Quickbooks"
ENV_FILE = ROOT / "Avance 2" / "mage_condimensa" / ".env"


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


def normalize_number(series: pd.Series) -> pd.Series:
    s = series.astype(str)
    s = s.str.replace("$", "", regex=False).str.replace(" ", "", regex=False)
    s = s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    return pd.to_numeric(s, errors="coerce")


def build_sales_frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    ventas = pd.read_csv(
        QB_DIR / "Ventas(Hoja1).csv",
        sep=";",
        engine="python",
        encoding="latin1",
        on_bad_lines="skip",
    )
    ventas = ventas.loc[:, [c for c in ventas.columns if not str(c).startswith("Unnamed") and str(c).strip() != ""]]

    cols = ["ASESOR", "Type", "Date", "Num", "Name", "Item", "Qty", "Sales Price"]
    cols = [c for c in cols if c in ventas.columns]
    ventas = ventas[cols].copy()

    ventas["fecha_dt"] = pd.to_datetime(ventas["Date"], format="%d/%m/%Y", errors="coerce")
    ventas = ventas[ventas["Num"].notna() & ventas["fecha_dt"].notna()].copy()

    ventas["qty_n"] = normalize_number(ventas["Qty"]).fillna(0)
    ventas["rate_n"] = normalize_number(ventas["Sales Price"]).fillna(0)
    ventas["tipo"] = ventas["Type"].fillna("").astype(str)
    ventas["estado"] = ventas["tipo"].map({"Invoice": "PROCESADA", "Credit Memo": "DEVOLUCION"}).fillna("PROCESADA")

    ventas["idsale"] = (
        ventas["Num"].astype(str).str.strip()
        + "-"
        + ventas["fecha_dt"].dt.strftime("%Y%m%d")
        + "-"
        + ventas["tipo"].str.replace(" ", "", regex=False).str.upper().str.slice(0, 3)
    )

    headers = (
        ventas.groupby(["idsale", "Num", "fecha_dt", "estado", "ASESOR", "Name"], dropna=False)
        .agg(numitems=("Item", "count"))
        .reset_index()
    )
    headers = headers.sort_values(["fecha_dt", "Num", "idsale"]).reset_index(drop=True)
    headers["idsales"] = range(1, len(headers) + 1)

    sales = pd.DataFrame(
        {
            "idsales": headers["idsales"],
            "idsale": headers["idsale"],
            "nick": headers["ASESOR"].astype(str),
            "fecha": headers["fecha_dt"].dt.strftime("%Y-%m-%d"),
            "estado": headers["estado"].astype(str),
            "numero": headers["Num"].astype(str),
            "cliente": headers["Name"].astype(str),
            "idcliente": None,
            "numitems": headers["numitems"].fillna(0).astype("int64"),
            "qb": None,
            "numitemsprocesados": headers["numitems"].fillna(0).astype("int64"),
            "status": headers["estado"].astype(str),
            "numitemsopen": 0,
            "idinvoice": headers["Num"].astype(str),
        }
    )

    ventas_l = ventas.merge(headers[["idsale", "idsales"]], on="idsale", how="left")
    ventas_l = ventas_l.sort_values(["idsales", "idsale", "Item"]).reset_index(drop=True)
    ventas_l["idlinea"] = ventas_l.groupby("idsale").cumcount() + 1

    lines = pd.DataFrame(
        {
            "idsales_lineas": range(1, len(ventas_l) + 1),
            "idsale": ventas_l["idsale"],
            "idlinea": ventas_l["idlinea"].astype(str),
            "fullname": ventas_l["Item"].astype(str),
            "iditem": None,
            "name": ventas_l["Item"].astype(str),
            "qty": ventas_l["qty_n"].round().fillna(0).astype("int64"),
            "ean13": None,
            "ue": None,
            "ubicacion": None,
            "qtydespachada": ventas_l["qty_n"].round().fillna(0).astype("int64"),
            "novedades": None,
            "hora": None,
            "nick": ventas_l["ASESOR"].astype(str),
            "ean14": None,
            "okescaneo": None,
            "stock": None,
            "idsales": ventas_l["idsales"].astype("int64"),
            "rate": ventas_l["rate_n"].astype(float),
        }
    )

    return sales, lines


def build_produccion_frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    prod = pd.read_excel(QB_DIR / "PRODUCCION2025.xlsx")
    rename = {
        "No.": "id_registro",
        "FECHA": "fecha",
        "NUMERO": "numero",
        "LOTE": "lote",
        "PRODUCTO": "producto",
        "Q. PANIFICDA": "qty_planificada",
        "Q. LIBERADA": "qty_liberada",
        "Q. FABRICADA": "qty_fabricada",
    }
    prod = prod[[c for c in rename if c in prod.columns]].rename(columns={c: rename[c] for c in rename if c in prod.columns})
    prod["fecha_dt"] = pd.to_datetime(prod["fecha"], errors="coerce")
    prod = prod[prod["numero"].notna() & prod["fecha_dt"].notna()].copy()
    for c in ["qty_planificada", "qty_liberada", "qty_fabricada"]:
        if c in prod.columns:
            prod[c] = pd.to_numeric(prod[c], errors="coerce").fillna(0)
        else:
            prod[c] = 0

    prod["idsale"] = prod["numero"].astype(str).str.strip() + "-" + prod["fecha_dt"].dt.strftime("%Y%m%d")

    headers = (
        prod.groupby(["idsale", "numero", "fecha_dt"], dropna=False)
        .agg(numitems=("producto", "count"), numitemsprocesados=("qty_fabricada", lambda s: int((s > 0).sum())))
        .reset_index()
    )
    headers = headers.sort_values(["fecha_dt", "numero"]).reset_index(drop=True)
    headers["idsales"] = range(1, len(headers) + 1)
    headers["numitemsopen"] = (headers["numitems"] - headers["numitemsprocesados"]).clip(lower=0)

    produccion = pd.DataFrame(
        {
            "idsales": headers["idsales"],
            "idsale": headers["idsale"],
            "nick": "LOCAL_FILE",
            "fecha": headers["fecha_dt"].dt.strftime("%Y-%m-%d"),
            "estado": "PROCESADA",
            "numero": headers["numero"].astype(str),
            "cliente": None,
            "idcliente": None,
            "numitems": headers["numitems"].astype("int64"),
            "qb": None,
            "numitemsprocesados": headers["numitemsprocesados"].astype("int64"),
            "status": "PROCESADA",
            "numitemsopen": headers["numitemsopen"].astype("int64"),
            "idinvoice": headers["numero"].astype(str),
        }
    )

    prod_l = prod.merge(headers[["idsale", "idsales"]], on="idsale", how="left")
    prod_l = prod_l.sort_values(["idsales", "idsale", "id_registro"]).reset_index(drop=True)
    prod_l["idlinea"] = prod_l.groupby("idsale").cumcount() + 1

    prod_lines = pd.DataFrame(
        {
            "idsales_lineas": range(1, len(prod_l) + 1),
            "idsale": prod_l["idsale"],
            "idlinea": prod_l["idlinea"].astype(str),
            "fullname": prod_l["producto"].astype(str),
            "iditem": None,
            "name": prod_l["producto"].astype(str),
            "qty": prod_l["qty_planificada"].astype(float),
            "ean13": None,
            "ue": None,
            "ubicacion": prod_l.get("lote", None),
            "qtydespachada": prod_l["qty_fabricada"].round().fillna(0).astype("int64"),
            "novedades": None,
            "hora": None,
            "nick": "LOCAL_FILE",
            "ean14": None,
            "okescaneo": None,
            "stock": None,
            "idsales": prod_l["idsales"].astype("int64"),
        }
    )

    return produccion, prod_lines


def copy_df(cur, table: str, df: pd.DataFrame) -> None:
    if df.empty:
        return
    buf = io.StringIO()
    df.to_csv(buf, index=False, header=False, na_rep="")
    buf.seek(0)
    cols = ", ".join([f'"{c}"' for c in df.columns])
    cur.copy_expert(f'COPY quickbooks."{table}" ({cols}) FROM STDIN WITH (FORMAT CSV)', buf)


def main() -> None:
    load_env(ENV_FILE)

    conn = psycopg2.connect(
        host="your-quickbooks-host.supabase.com",
        port=6543,
        dbname="postgres",
        user="postgres.your-quickbooks-project-ref",
        password=os.getenv("QUICKBOOKS_PASSWORD", ""),
        sslmode="require",
        connect_timeout=20,
    )
    conn.autocommit = False

    sales, sales_lines = build_sales_frames()
    produccion, produccion_lines = build_produccion_frames()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    try:
        cur = conn.cursor()

        # Backups
        cur.execute(f'CREATE TABLE quickbooks.sales_bkp_{ts} AS TABLE quickbooks.sales;')
        cur.execute(f'CREATE TABLE quickbooks.sales_lineas_bkp_{ts} AS TABLE quickbooks.sales_lineas;')
        cur.execute(f'CREATE TABLE quickbooks.produccion_bkp_{ts} AS TABLE quickbooks.produccion;')
        cur.execute(f'CREATE TABLE quickbooks.produccion_lineas_bkp_{ts} AS TABLE quickbooks.produccion_lineas;')

        # Full refresh requested
        cur.execute('TRUNCATE TABLE quickbooks.sales, quickbooks.sales_lineas, quickbooks.produccion, quickbooks.produccion_lineas;')

        # Load
        copy_df(cur, "sales", sales)
        copy_df(cur, "sales_lineas", sales_lines)
        copy_df(cur, "produccion", produccion)
        copy_df(cur, "produccion_lineas", produccion_lines)

        conn.commit()

        print("OK: Carga completada")
        print(f"Backups: sales_bkp_{ts}, sales_lineas_bkp_{ts}, produccion_bkp_{ts}, produccion_lineas_bkp_{ts}")
        print(f"sales={len(sales)} sales_lineas={len(sales_lines)}")
        print(f"produccion={len(produccion)} produccion_lineas={len(produccion_lines)}")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
