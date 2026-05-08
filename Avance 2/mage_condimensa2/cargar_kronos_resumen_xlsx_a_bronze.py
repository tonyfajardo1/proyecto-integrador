import os
import re
from pathlib import Path

import numpy as np
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values


def parse_numeric(series: pd.Series) -> pd.Series:
    def _parse(value):
        if pd.isna(value):
            return np.nan
        if isinstance(value, (int, float, np.number)):
            return float(value)

        s = str(value).strip()
        if not s:
            return np.nan

        s = s.upper()
        if s in {"NULL", "NONE", "NAN"}:
            return np.nan

        s = s.replace(" ", "").replace(",", ".")

        try:
            if "E" in s:
                return float(s)

            if s.count(".") > 1:
                parts = s.split(".")
                s = "".join(parts[:-1]) + "." + parts[-1]

            return float(s)
        except Exception:
            return np.nan

    return series.apply(_parse)


def extraer_anio(file_path: Path) -> int:
    raw = pd.read_excel(file_path, header=None, nrows=12)
    patron = re.compile(r"Desde:\s*(\d{1,2})/(\d{1,2})/(\d{4})", re.IGNORECASE)

    for _, row in raw.iterrows():
        for val in row.tolist():
            txt = str(val) if pd.notna(val) else ""
            m = patron.search(txt)
            if m:
                return int(m.group(3))

    return 2026


def cargar_resumen_kronos(file_path: Path):
    anio = extraer_anio(file_path)

    df = pd.read_excel(file_path, header=7)
    df.columns = [str(c).strip().upper() for c in df.columns]

    mapeo = {
        "CENTRO_COSTO": "centro_costo",
        "CODIGO_PRODUCTO": "codigo_producto",
        "ALTERNO": "codigo_alterno",
        "PRODUCTO": "producto",
        "CANT": "cant_venta",
        "TOTAL": "total_venta",
        "CANT NC": "cant_nc",
        "TOTAL NC": "total_nc",
        "CANT NC DV": "cant_devolucion",
        "TOTAL NC DV": "total_devolucion",
        "CANT. NETO": "cant_neto",
        "TOTAL NETO": "total_neto",
        "COSTO VENTA": "costo_venta",
        "VALOR RENTAB": "rentabilidad",
        "PRC": "prc_rentabilidad",
        "MES": "mes",
    }

    faltantes = [c for c in mapeo.keys() if c not in df.columns]
    if faltantes:
        raise ValueError(f"Columnas faltantes en archivo: {faltantes}")

    df = df[list(mapeo.keys())].rename(columns=mapeo)
    df = df[df["mes"].notna()].copy()
    df = df[~df["centro_costo"].astype(str).str.contains("TOTAL|SUBTOTAL", case=False, na=False)].copy()

    for col in [
        "cant_venta",
        "total_venta",
        "cant_nc",
        "total_nc",
        "cant_devolucion",
        "total_devolucion",
        "cant_neto",
        "total_neto",
        "costo_venta",
        "rentabilidad",
        "prc_rentabilidad",
    ]:
        df[col] = parse_numeric(df[col]).fillna(0)

    df["anio"] = anio
    df["centro_costo"] = df["centro_costo"].astype(str).str.strip().str.lower()
    df["codigo_producto"] = df["codigo_producto"].astype(str).str.strip().str.upper()
    df["codigo_alterno"] = df["codigo_alterno"].astype(str).str.strip()
    df["producto"] = df["producto"].astype(str).str.strip()
    df["mes"] = df["mes"].astype(str).str.strip().str.upper()

    df = df[df["producto"] != ""].copy()
    df = df.groupby(
        ["centro_costo", "codigo_producto", "codigo_alterno", "producto", "mes", "anio"], as_index=False
    ).sum(numeric_only=True)

    df["fuente"] = "kronos"
    df["nombre_tabla_origen"] = file_path.name
    df["fecha_ingesta"] = pd.Timestamp.now()
    df["pipeline_id"] = "carga_manual_kronos_resumen"
    df["batch_id"] = pd.Timestamp.now().strftime("%Y%m%d%H%M%S")

    conn = psycopg2.connect(
        host="localhost",
        port=5433,
        dbname="condimensa_analytics",
        user="condimensa",
        password=os.getenv("DB_PASSWORD", "REDACTED_LOCAL_DB_PASSWORD"),
    )
    conn.autocommit = True

    ddl = """
    CREATE TABLE IF NOT EXISTS bronze.kronos_ventas_resumen_raw (
        id SERIAL PRIMARY KEY,
        centro_costo VARCHAR(100),
        codigo_producto VARCHAR(50),
        codigo_alterno VARCHAR(50),
        producto VARCHAR(255),
        mes VARCHAR(20),
        anio INTEGER,
        cant_venta NUMERIC(15,4),
        total_venta NUMERIC(15,4),
        cant_nc NUMERIC(15,4),
        total_nc NUMERIC(15,4),
        cant_devolucion NUMERIC(15,4),
        total_devolucion NUMERIC(15,4),
        cant_neto NUMERIC(15,4),
        total_neto NUMERIC(15,4),
        costo_venta NUMERIC(15,4),
        rentabilidad NUMERIC(15,4),
        prc_rentabilidad NUMERIC(15,6),
        fuente VARCHAR(50),
        nombre_tabla_origen VARCHAR(100),
        fecha_ingesta TIMESTAMP,
        pipeline_id VARCHAR(50),
        batch_id VARCHAR(50)
    )
    """

    cols = [
        "centro_costo",
        "codigo_producto",
        "codigo_alterno",
        "producto",
        "mes",
        "anio",
        "cant_venta",
        "total_venta",
        "cant_nc",
        "total_nc",
        "cant_devolucion",
        "total_devolucion",
        "cant_neto",
        "total_neto",
        "costo_venta",
        "rentabilidad",
        "prc_rentabilidad",
        "fuente",
        "nombre_tabla_origen",
        "fecha_ingesta",
        "pipeline_id",
        "batch_id",
    ]

    values = [tuple(None if pd.isna(v) else v for v in row) for row in df[cols].itertuples(index=False, name=None)]

    with conn.cursor() as cur:
        cur.execute("CREATE SCHEMA IF NOT EXISTS bronze")
        cur.execute(ddl)
        cur.execute("TRUNCATE TABLE bronze.kronos_ventas_resumen_raw")
        execute_values(
            cur,
            """
            INSERT INTO bronze.kronos_ventas_resumen_raw (
                centro_costo, codigo_producto, codigo_alterno, producto, mes, anio,
                cant_venta, total_venta, cant_nc, total_nc,
                cant_devolucion, total_devolucion, cant_neto, total_neto,
                costo_venta, rentabilidad, prc_rentabilidad,
                fuente, nombre_tabla_origen, fecha_ingesta, pipeline_id, batch_id
            ) VALUES %s
            """,
            values,
            page_size=1000,
        )

    conn.close()

    print(f"Archivo: {file_path}")
    print(f"Registros cargados: {len(df)}")
    print(f"TOTAL venta: {df['total_venta'].sum():,.2f}")
    print(f"TOTAL neto: {df['total_neto'].sum():,.2f}")
    print(f"TOTAL rentabilidad: {df['rentabilidad'].sum():,.2f}")


if __name__ == "__main__":
    default_file = Path(__file__).resolve().parents[1] / "Kronos" / "Ventas_general (4).xlsx"
    kronos_file = Path(os.getenv("KRONOS_RESUMEN_FILE", str(default_file)))

    if not kronos_file.exists():
        raise FileNotFoundError(f"No existe archivo: {kronos_file}")

    cargar_resumen_kronos(kronos_file)
