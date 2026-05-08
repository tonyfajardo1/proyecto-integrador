"""
Reemplaza kronos.ventas_general_4 en Supabase con el CSV transaccional nuevo.

Uso:
  python cargar_kronos_csv_a_supabase.py
"""

from __future__ import annotations

import io
import os
from datetime import datetime
from pathlib import Path

import pandas as pd
import psycopg2


ROOT = Path(r"F:\proyecto-integrador\Avance 2")
ENV_FILE = ROOT / "mage_condimensa2" / ".env"
CSV_FILE = ROOT / "Kronos" / "Ventas_netas_2026_01.csv"


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


def clean_columns(cols):
    out = []
    for c in cols:
        name = str(c).replace("ï»¿", "").replace("\ufeff", "").strip().lower()
        name = name.replace(" ", "_").replace("/", "_")
        out.append(name)
    return out


def main():
    load_env(ENV_FILE)

    host = os.getenv("KRONOS_HOST", "your-kronos-host.supabase.com")
    port = int(os.getenv("KRONOS_PORT", "6543"))
    dbname = os.getenv("KRONOS_DB", "postgres")
    user = os.getenv("KRONOS_USER", "postgres.your-kronos-project-ref")
    password = os.getenv("KRONOS_PASSWORD", "")

    if not password:
        raise RuntimeError("KRONOS_PASSWORD no definido en .env")

    print(f"Leyendo CSV: {CSV_FILE}")
    df = pd.read_csv(CSV_FILE, sep=";", engine="python", encoding="latin1", on_bad_lines="skip")
    df.columns = clean_columns(df.columns)

    # Conversión de tipos básica
    int_cols = [
        "id_factura",
        "numero_factura",
        "id_detalle",
        "id_producto",
        "id_unidad",
        "id_promocion",
        "tipo_precio",
        "tipo_producto",
        "id_motivo",
        "id_cliente",
        "id_sucursal",
    ]
    for c in int_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
            df[c] = df[c].round().astype("Int64")

    for c in ["cantidad", "valor_unitario", "valor_total", "descuento", "costo", "titulo_gratuito"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    for c in ["fecha_ingreso", "fecha_factura", "fecha_vencimiento"]:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce")

    conn = psycopg2.connect(
        host=host,
        port=port,
        dbname=dbname,
        user=user,
        password=password,
        sslmode="require",
        connect_timeout=20,
    )
    conn.autocommit = False
    cur = conn.cursor()

    bkp_suffix = datetime.now().strftime("%Y%m%d_%H%M%S")

    try:
        cur.execute("CREATE SCHEMA IF NOT EXISTS kronos;")

        # Backup de tabla actual
        cur.execute(
            f"CREATE TABLE IF NOT EXISTS kronos.ventas_general_4_bkp_{bkp_suffix} AS TABLE kronos.ventas_general_4;"
        )

        # Reemplazo total
        cur.execute("DROP TABLE IF EXISTS kronos.ventas_general_4;")
        cur.execute(
            """
            CREATE TABLE kronos.ventas_general_4 (
                id_factura BIGINT,
                serie TEXT,
                numero_factura BIGINT,
                fecha_ingreso TIMESTAMP,
                fecha_factura TIMESTAMP,
                fecha_vencimiento TIMESTAMP,
                vendedor TEXT,
                empleado TEXT,
                titulo_gratuito NUMERIC(15,4),
                id_detalle BIGINT,
                cantidad NUMERIC(15,4),
                valor_unitario NUMERIC(15,4),
                valor_total NUMERIC(15,4),
                descuento NUMERIC(15,4),
                id_producto BIGINT,
                id_unidad BIGINT,
                costo NUMERIC(15,4),
                id_promocion BIGINT,
                tipo_precio BIGINT,
                tipo_producto BIGINT,
                id_motivo BIGINT,
                id_cliente BIGINT,
                id_sucursal BIGINT,
                vendedor_name_rutero TEXT,
                supervisor_name TEXT,
                cod_rutero TEXT,
                nombre_rutero TEXT,
                ci_empleado TEXT,
                ci_empleado_s TEXT,
                razon_social TEXT,
                nombre_comercial TEXT,
                codigo_producto TEXT,
                descripcion_producto TEXT,
                nombre_subgrupo TEXT,
                descripcion_grupo TEXT,
                nombre_marca TEXT,
                linea_name TEXT,
                tipo TEXT
            );
            """
        )

        cols = [
            "id_factura",
            "serie",
            "numero_factura",
            "fecha_ingreso",
            "fecha_factura",
            "fecha_vencimiento",
            "vendedor",
            "empleado",
            "titulo_gratuito",
            "id_detalle",
            "cantidad",
            "valor_unitario",
            "valor_total",
            "descuento",
            "id_producto",
            "id_unidad",
            "costo",
            "id_promocion",
            "tipo_precio",
            "tipo_producto",
            "id_motivo",
            "id_cliente",
            "id_sucursal",
            "vendedor_name_rutero",
            "supervisor_name",
            "cod_rutero",
            "nombre_rutero",
            "ci_empleado",
            "ci_empleado_s",
            "razon_social",
            "nombre_comercial",
            "codigo_producto",
            "descripcion_producto",
            "nombre_subgrupo",
            "descripcion_grupo",
            "nombre_marca",
            "linea_name",
            "tipo",
        ]
        for c in cols:
            if c not in df.columns:
                df[c] = None

        data = df[cols].copy()
        buf = io.StringIO()
        data.to_csv(buf, index=False, header=False, na_rep="")
        buf.seek(0)
        cur.copy_expert(
            "COPY kronos.ventas_general_4 ("
            + ", ".join(cols)
            + ") FROM STDIN WITH (FORMAT CSV)",
            buf,
        )

        conn.commit()
        print("OK: Carga completada")
        print(f"Backup: kronos.ventas_general_4_bkp_{bkp_suffix}")
        print(f"Filas cargadas: {len(data)}")
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
