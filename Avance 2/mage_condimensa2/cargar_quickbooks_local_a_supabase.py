"""
Carga archivos locales de QuickBooks a PostgreSQL/Supabase con estrategia segura.

Modo por defecto (safe):
- crea tablas staging
- carga archivos locales
- hace upsert a tablas finales sin borrar historial completo

Requisitos de entorno:
- QUICKBOOKS_HOST
- QUICKBOOKS_PORT (default 6543)
- QUICKBOOKS_DB (default postgres)
- QUICKBOOKS_USER
- QUICKBOOKS_PASSWORD
- QUICKBOOKS_SCHEMA (default quickbooks)
"""

from __future__ import annotations

import argparse
import io
import os
from pathlib import Path

import pandas as pd
import psycopg2


def load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


def read_ventas(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, sep=";", engine="python", encoding="latin1", on_bad_lines="skip")
    df = df.loc[:, [c for c in df.columns if not str(c).startswith("Unnamed") and str(c).strip() != ""]]
    keep = ["ASESOR", "Type", "Date", "Num", "Memo", "Name", "Item", "Qty", "U/M", "Sales Price", "Amount"]
    keep = [c for c in keep if c in df.columns]
    df = df[keep].copy()
    df.columns = [
        "asesor",
        "tipo",
        "fecha",
        "numero",
        "memo",
        "cliente",
        "item",
        "qty",
        "uom",
        "precio_venta",
        "monto",
    ][: len(df.columns)]

    if "fecha" in df.columns:
        df["fecha"] = pd.to_datetime(df["fecha"], format="%d/%m/%Y", errors="coerce")
    for c in ["qty", "precio_venta", "monto"]:
        if c in df.columns:
            df[c] = (
                df[c]
                .astype(str)
                .str.replace(".", "", regex=False)
                .str.replace(",", ".", regex=False)
                .str.replace("$", "", regex=False)
                .str.strip()
            )
            df[c] = pd.to_numeric(df[c], errors="coerce")

    return df


def read_produccion(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path)
    col_map = {
        "No.": "id_registro",
        "FECHA": "fecha",
        "NUMERO": "numero",
        "LOTE": "lote",
        "PRODUCTO": "producto",
        "Q. PANIFICDA": "qty_planificada",
        "Q. LIBERADA": "qty_liberada",
        "Q. FABRICADA": "qty_fabricada",
    }
    cols = [c for c in col_map if c in df.columns]
    df = df[cols].rename(columns={c: col_map[c] for c in cols}).copy()
    if "fecha" in df.columns:
        df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    for c in ["qty_planificada", "qty_liberada", "qty_fabricada"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def read_costos(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path)
    df = df.loc[:, [c for c in df.columns if not str(c).startswith("Unnamed") and str(c).strip() != ""]]
    rename = {
        "Type": "tipo",
        "Date": "fecha",
        "Name": "cliente",
        "Num": "numero",
        "Item": "item",
        "Item Description": "item_descripcion",
        "Qty": "qty",
        "Cost": "costo",
        "On Hand": "on_hand",
        "U/M": "uom",
    }
    cols = [c for c in rename if c in df.columns]
    df = df[cols].rename(columns={c: rename[c] for c in cols}).copy()
    if "fecha" in df.columns:
        df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    for c in ["qty", "costo", "on_hand"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def copy_df(cur, schema: str, table: str, df: pd.DataFrame) -> None:
    if df.empty:
        return
    buf = io.StringIO()
    df.to_csv(buf, index=False, header=False, na_rep="")
    buf.seek(0)
    cols = ", ".join([f'"{c}"' for c in df.columns])
    sql = f'COPY "{schema}"."{table}" ({cols}) FROM STDIN WITH (FORMAT CSV)'
    cur.copy_expert(sql, buf)


def run(args) -> None:
    base = Path(args.base_path)
    load_env_file(Path(args.env_file))

    host = os.getenv("QUICKBOOKS_HOST", "")
    port = int(os.getenv("QUICKBOOKS_PORT", "6543"))
    dbname = os.getenv("QUICKBOOKS_DB", "postgres")
    user = os.getenv("QUICKBOOKS_USER", "")
    password = os.getenv("QUICKBOOKS_PASSWORD", "")
    schema = os.getenv("QUICKBOOKS_SCHEMA", "quickbooks")

    if not host or not user or not password:
        raise RuntimeError("Faltan QUICKBOOKS_HOST/USER/PASSWORD en variables de entorno.")

    ventas = read_ventas(base / "Ventas(Hoja1).csv")
    produccion = read_produccion(base / "PRODUCCION2025.xlsx")
    costos = read_costos(base / "Costos.xlsx")

    conn = psycopg2.connect(
        host=host,
        port=port,
        dbname=dbname,
        user=user,
        password=password,
        connect_timeout=15,
    )
    conn.autocommit = False

    try:
        cur = conn.cursor()

        cur.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}";')

        cur.execute(
            f'''
            CREATE TABLE IF NOT EXISTS "{schema}".sales_local_stg (
                asesor TEXT,
                tipo TEXT,
                fecha TIMESTAMP,
                numero TEXT,
                memo TEXT,
                cliente TEXT,
                item TEXT,
                qty NUMERIC,
                uom TEXT,
                precio_venta NUMERIC,
                monto NUMERIC
            );
            CREATE TABLE IF NOT EXISTS "{schema}".produccion_local_stg (
                id_registro TEXT,
                fecha TIMESTAMP,
                numero TEXT,
                lote TEXT,
                producto TEXT,
                qty_planificada NUMERIC,
                qty_liberada NUMERIC,
                qty_fabricada NUMERIC
            );
            CREATE TABLE IF NOT EXISTS "{schema}".costos_local_stg (
                tipo TEXT,
                fecha TIMESTAMP,
                cliente TEXT,
                numero TEXT,
                item TEXT,
                item_descripcion TEXT,
                qty NUMERIC,
                costo NUMERIC,
                on_hand NUMERIC,
                uom TEXT
            );
            '''
        )

        cur.execute(f'TRUNCATE TABLE "{schema}".sales_local_stg;')
        cur.execute(f'TRUNCATE TABLE "{schema}".produccion_local_stg;')
        cur.execute(f'TRUNCATE TABLE "{schema}".costos_local_stg;')

        copy_df(cur, schema, "sales_local_stg", ventas)
        copy_df(cur, schema, "produccion_local_stg", produccion)
        copy_df(cur, schema, "costos_local_stg", costos)

        if args.mode == "safe":
            cur.execute(
                f'''
                CREATE TABLE IF NOT EXISTS "{schema}".sales_local AS
                SELECT DISTINCT * FROM "{schema}".sales_local_stg WHERE 1=0;
                CREATE TABLE IF NOT EXISTS "{schema}".produccion_local AS
                SELECT DISTINCT * FROM "{schema}".produccion_local_stg WHERE 1=0;
                CREATE TABLE IF NOT EXISTS "{schema}".costos_local AS
                SELECT DISTINCT * FROM "{schema}".costos_local_stg WHERE 1=0;
                '''
            )

            cur.execute(
                f'''
                INSERT INTO "{schema}".sales_local
                SELECT DISTINCT * FROM "{schema}".sales_local_stg s
                WHERE NOT EXISTS (
                    SELECT 1 FROM "{schema}".sales_local t
                    WHERE COALESCE(t.numero, '') = COALESCE(s.numero, '')
                      AND COALESCE(t.fecha::date::text, '') = COALESCE(s.fecha::date::text, '')
                      AND COALESCE(t.tipo, '') = COALESCE(s.tipo, '')
                      AND COALESCE(t.item, '') = COALESCE(s.item, '')
                );

                INSERT INTO "{schema}".produccion_local
                SELECT DISTINCT * FROM "{schema}".produccion_local_stg s
                WHERE NOT EXISTS (
                    SELECT 1 FROM "{schema}".produccion_local t
                    WHERE COALESCE(t.numero, '') = COALESCE(s.numero, '')
                      AND COALESCE(t.fecha::date::text, '') = COALESCE(s.fecha::date::text, '')
                      AND COALESCE(t.lote, '') = COALESCE(s.lote, '')
                      AND COALESCE(t.producto, '') = COALESCE(s.producto, '')
                );

                INSERT INTO "{schema}".costos_local
                SELECT DISTINCT * FROM "{schema}".costos_local_stg s
                WHERE NOT EXISTS (
                    SELECT 1 FROM "{schema}".costos_local t
                    WHERE COALESCE(t.numero, '') = COALESCE(s.numero, '')
                      AND COALESCE(t.fecha::date::text, '') = COALESCE(s.fecha::date::text, '')
                      AND COALESCE(t.item, '') = COALESCE(s.item, '')
                );
                '''
            )

        conn.commit()
        print("Carga completada en modo:", args.mode)
        print("sales_local_stg:", len(ventas))
        print("produccion_local_stg:", len(produccion))
        print("costos_local_stg:", len(costos))
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base-path",
        default=r"F:\proyecto-integrador\Avance 2\Quickbooks",
        help="Ruta de carpeta con Ventas(Hoja1).csv, PRODUCCION2025.xlsx y Costos.xlsx",
    )
    parser.add_argument(
        "--env-file",
        default=r"F:\proyecto-integrador\Avance 2\mage_condimensa\.env",
        help="Ruta del archivo .env",
    )
    parser.add_argument("--mode", choices=["safe"], default="safe")
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
