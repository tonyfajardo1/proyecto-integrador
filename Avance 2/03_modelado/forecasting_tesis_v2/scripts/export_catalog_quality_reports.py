from pathlib import Path
import sys
from datetime import datetime

import pandas as pd
from psycopg2.extras import execute_values

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.db import connect_dwh, query_df


def main():
    root = Path(__file__).resolve().parents[1]
    artifacts = root / "artifacts"
    artifacts.mkdir(exist_ok=True, parents=True)

    with connect_dwh() as conn:
        conflictos = query_df(
            conn,
            """
            SELECT
                ean13,
                COUNT(DISTINCT producto_dashboard) AS n_nombres,
                STRING_AGG(DISTINCT producto_dashboard, ' | ' ORDER BY producto_dashboard) AS nombres_dashboard,
                COUNT(DISTINCT codigo_producto) AS n_codigos
            FROM silver.dim_producto_canonico
            WHERE COALESCE(flag_conflicto_ean13, FALSE) = TRUE
              AND ean13 IS NOT NULL
              AND TRIM(ean13) <> ''
            GROUP BY ean13
            ORDER BY n_nombres DESC, ean13
            """,
        )

        estado = query_df(
            conn,
            """
            SELECT
                estado_producto,
                COUNT(*) AS n_rows,
                COUNT(DISTINCT COALESCE(NULLIF(TRIM(ean13), ''), NULLIF(TRIM(codigo_producto), ''))) AS n_productos
            FROM silver.forecasting_base_mensual_v1
            GROUP BY estado_producto
            ORDER BY n_rows DESC
            """,
        )

        ts = datetime.now()
        conflictos["fecha_ejecucion"] = ts
        estado["fecha_ejecucion"] = ts

        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE SCHEMA IF NOT EXISTS gold;
                CREATE TABLE IF NOT EXISTS gold.catalogo_conflictos_ean13_v1 (
                    id SERIAL PRIMARY KEY,
                    ean13 VARCHAR(20),
                    n_nombres INTEGER,
                    nombres_dashboard TEXT,
                    n_codigos INTEGER,
                    fecha_ejecucion TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS gold.forecasting_estado_producto_resumen_v1 (
                    id SERIAL PRIMARY KEY,
                    estado_producto VARCHAR(20),
                    n_rows INTEGER,
                    n_productos INTEGER,
                    fecha_ejecucion TIMESTAMP
                );
                """
            )
            cur.execute("TRUNCATE TABLE gold.catalogo_conflictos_ean13_v1")
            cur.execute("TRUNCATE TABLE gold.forecasting_estado_producto_resumen_v1")

            if len(conflictos) > 0:
                records_conf = [tuple(row) for row in conflictos[["ean13", "n_nombres", "nombres_dashboard", "n_codigos", "fecha_ejecucion"]].itertuples(index=False, name=None)]
                execute_values(
                    cur,
                    """
                    INSERT INTO gold.catalogo_conflictos_ean13_v1
                    (ean13, n_nombres, nombres_dashboard, n_codigos, fecha_ejecucion)
                    VALUES %s
                    """,
                    records_conf,
                )

            if len(estado) > 0:
                records_estado = [tuple(row) for row in estado[["estado_producto", "n_rows", "n_productos", "fecha_ejecucion"]].itertuples(index=False, name=None)]
                execute_values(
                    cur,
                    """
                    INSERT INTO gold.forecasting_estado_producto_resumen_v1
                    (estado_producto, n_rows, n_productos, fecha_ejecucion)
                    VALUES %s
                    """,
                    records_estado,
                )
            conn.commit()

    conflictos_path = artifacts / "catalogo_conflictos_ean13.csv"
    estado_path = artifacts / "forecasting_estado_producto_resumen.csv"
    conflictos.to_csv(conflictos_path, index=False)
    estado.to_csv(estado_path, index=False)

    print(f"Conflictos EAN13 exportados: {len(conflictos)} -> {conflictos_path}")
    print(f"Resumen estado producto exportado: {len(estado)} -> {estado_path}")
    print(f"Publicados en Gold: conflictos={len(conflictos)}, estado={len(estado)}")


if __name__ == "__main__":
    main()
