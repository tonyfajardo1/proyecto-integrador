from pathlib import Path
import sys

import numpy as np
import pandas as pd
from psycopg2.extras import execute_values

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.db import connect_dwh, query_df


def _tipo_producto(name: str):
    s = str(name).upper().strip()
    if s.startswith("PP"):
        return "PP"
    if s.startswith("PT"):
        return "PT"
    return "OTRO"


def main():
    root = Path(__file__).resolve().parents[1]
    artifacts = root / "artifacts"

    pred_path = artifacts / "predicciones_forecasting_v2.csv"
    bench_path = artifacts / "benchmark_forecasting_v2.csv"
    if not pred_path.exists():
        raise FileNotFoundError(f"No existe {pred_path}")

    pred = pd.read_csv(pred_path)
    bench = pd.read_csv(bench_path) if bench_path.exists() else pd.DataFrame()
    winner = (
        str(bench.iloc[0]["modelo"]) if len(bench) > 0 and "modelo" in bench.columns else "RandomForest"
    )

    pred["periodo"] = pd.to_datetime(pred["periodo"], errors="coerce")
    pred["next_period"] = pd.to_datetime(pred["next_period"], errors="coerce")
    pred["pronostico_qty"] = pd.to_numeric(pred["pronostico_qty"], errors="coerce").fillna(0).clip(lower=0)
    pred["qty_planificada"] = pd.to_numeric(pred.get("qty_planificada", np.nan), errors="coerce")
    pred["qty_fabricada"] = pd.to_numeric(pred.get("qty_fabricada", pred.get("target_t1", 0)), errors="coerce").fillna(0)
    pred["rolling_std_3"] = pd.to_numeric(pred.get("rolling_std_3", np.nan), errors="coerce")
    pred["n_ordenes"] = pd.to_numeric(pred.get("n_ordenes", np.nan), errors="coerce")

    # Enriquecer nombre canónico de dashboard desde dimension de producto
    with connect_dwh() as conn:
        dim = query_df(
            conn,
            """
            SELECT
                COALESCE(NULLIF(TRIM(codigo_producto), ''), '') AS codigo_producto,
                COALESCE(NULLIF(TRIM(ean13), ''), '') AS ean13,
                COALESCE(NULLIF(TRIM(producto_dashboard), ''), '') AS producto_dashboard
            FROM silver.dim_producto_canonico
            """,
        )
    dim = dim[(dim["codigo_producto"] != "") | (dim["ean13"] != "")].copy()
    dim = dim[dim["producto_dashboard"] != ""].copy()
    dim_by_ean = dim[dim["ean13"] != ""].drop_duplicates(subset=["ean13"])[["ean13", "producto_dashboard"]]
    dim_by_cod = dim[dim["codigo_producto"] != ""].drop_duplicates(subset=["codigo_producto"])[
        ["codigo_producto", "producto_dashboard"]
    ]

    pred["producto_clave"] = pred["producto"].astype(str).str.strip()
    key_digits = pred["producto_clave"].str.replace(r"\D", "", regex=True)
    pred["key_ean13"] = np.where(key_digits.str.len() == 13, key_digits, "")
    pred["key_codigo"] = np.where(key_digits.str.len() != 13, key_digits.str.zfill(4), "")

    pred = pred.merge(dim_by_ean.rename(columns={"ean13": "key_ean13", "producto_dashboard": "dashboard_ean"}), on="key_ean13", how="left")
    pred = pred.merge(
        dim_by_cod.rename(columns={"codigo_producto": "key_codigo", "producto_dashboard": "dashboard_cod"}),
        on="key_codigo",
        how="left",
    )
    pred["producto_dashboard"] = pred["dashboard_ean"].fillna(pred["dashboard_cod"]).fillna(pred["producto"])

    # ---------------------------------------------------------------------
    # 1) Capa modelo: banda tecnica (min/base/max) segun incertidumbre
    # ---------------------------------------------------------------------
    base_modelo = pd.to_numeric(pred.get("qty_recomendada_modelo", pred["pronostico_qty"]), errors="coerce").fillna(0)
    base_modelo = np.ceil(np.maximum(base_modelo, 0))

    factor_unc = pd.to_numeric(pred.get("factor_incertidumbre_modelo", np.nan), errors="coerce")
    factor_unc = factor_unc.fillna(0.25).clip(lower=0.10, upper=1.00)

    min_modelo = pd.to_numeric(pred.get("qty_min_modelo", np.nan), errors="coerce")
    max_modelo = pd.to_numeric(pred.get("qty_max_modelo", np.nan), errors="coerce")
    min_modelo = min_modelo.fillna(np.floor(np.maximum(0, base_modelo * (1 - factor_unc))))
    max_modelo = max_modelo.fillna(np.ceil(np.maximum(base_modelo, base_modelo * (1 + factor_unc))))

    # ---------------------------------------------------------------------
    # 2) Capa negocio (Gold): conversion a recomendacion operativa
    #    PT: demanda pronosticada -> produccion sugerida
    #    PP: produccion sugerida directa
    # ---------------------------------------------------------------------
    pred["tipo_producto"] = pred.get("tipo_producto", pred["producto"].apply(_tipo_producto)).astype(str).str.upper().str.strip()
    lag_1 = pd.to_numeric(pred.get("lag_1", 0), errors="coerce").fillna(0).clip(lower=0)
    rolling_std = pd.to_numeric(pred.get("rolling_std_3", 0), errors="coerce").fillna(0).clip(lower=0)

    stock_seguridad = np.ceil(np.maximum(rolling_std * 0.50, base_modelo * 0.10))
    inventario_proxy = np.floor(np.maximum(0, lag_1 * 0.20))

    base_operativa = np.where(
        pred["tipo_producto"] == "PT",
        np.maximum(0, base_modelo + stock_seguridad - inventario_proxy),
        np.maximum(0, base_modelo),
    )
    min_operativa = np.where(
        pred["tipo_producto"] == "PT",
        np.maximum(0, min_modelo + np.floor(stock_seguridad * 0.70) - np.ceil(inventario_proxy * 1.10)),
        np.maximum(0, min_modelo),
    )
    max_operativa = np.where(
        pred["tipo_producto"] == "PT",
        np.maximum(base_operativa, max_modelo + np.ceil(stock_seguridad * 1.20)),
        np.maximum(base_operativa, max_modelo),
    )

    # Redondeo operativo simple a lotes de 5 unidades.
    lote = 5.0
    pred["qty_recomendada"] = np.ceil(base_operativa / lote) * lote
    pred["qty_min_recomendada"] = np.floor(np.maximum(0, min_operativa) / lote) * lote
    pred["qty_max_recomendada"] = np.ceil(np.maximum(pred["qty_recomendada"], max_operativa) / lote) * lote

    # Garantizar monotonia min <= recomendada <= max
    pred["qty_min_recomendada"] = np.minimum(pred["qty_min_recomendada"], pred["qty_recomendada"])
    pred["qty_max_recomendada"] = np.maximum(pred["qty_max_recomendada"], pred["qty_recomendada"])

    # confianza por error absoluto porcentual en horizonte evaluado
    target = pd.to_numeric(pred.get("target_t1", np.nan), errors="coerce")
    ape = np.where(target > 0, np.abs(pred["pronostico_qty"] - target) / target, np.nan)
    pred["nivel_confianza"] = np.where(
        ape <= 0.15,
        "ALTA",
        np.where(ape <= 0.35, "MEDIA", "BAJA"),
    )
    pred["nivel_confianza"] = pd.Series(pred["nivel_confianza"]).fillna("MEDIA")

    pred["sugerencia_accion"] = np.select(
        [pred["nivel_confianza"] == "ALTA", pred["nivel_confianza"] == "MEDIA"],
        [
            "Planificar con valor base y seguimiento normal.",
            "Planificar con rango y validar con operaciones.",
        ],
        default="Revisar causas y usar escenarios minimo/base/maximo.",
    )
    pred["posibles_causas"] = np.select(
        [pred["nivel_confianza"] == "ALTA", pred["nivel_confianza"] == "MEDIA"],
        [
            "Serie estable en historico reciente.",
            "Variabilidad moderada por mezcla de demanda y estacionalidad.",
        ],
        default="Alta volatilidad o cambios de demanda en historico reciente.",
    )

    if "requiere_revision_manual" in pred.columns:
        pred.loc[pred["requiere_revision_manual"].astype(str).str.upper() == "SI", "sugerencia_accion"] = (
            "REVISAR: diferencia alta entre plan y modelo; mantener plan humano hasta validacion."
        )

    if "tipo_producto" in pred.columns:
        pred["tipo_producto"] = pred["tipo_producto"].astype(str).str.upper().str.strip()
        pred.loc[~pred["tipo_producto"].isin(["PT", "PP"]), "tipo_producto"] = np.nan
        pred["tipo_producto"] = pred["tipo_producto"].fillna(pred["producto"].apply(_tipo_producto))
    else:
        pred["tipo_producto"] = pred["producto"].apply(_tipo_producto)
    if "categoria_producto" in pred.columns:
        pred["categoria_producto"] = pred["categoria_producto"].astype(str).str.strip().replace({"": "GENERAL"})
    else:
        pred["categoria_producto"] = "GENERAL"
    pred["producto_base"] = pred["producto"].astype(str).str.strip()
    pred["producto"] = pred["producto_dashboard"]
    pred["periodo_prediccion"] = pred["next_period"].dt.date
    if "es_vigente_operativo" not in pred.columns:
        pred["es_vigente_operativo"] = True
    pred["es_vigente_operativo"] = pred["es_vigente_operativo"].fillna(True).astype(bool)

    if "razon_vigencia" not in pred.columns:
        pred["razon_vigencia"] = "VIGENTE"
    pred["razon_vigencia"] = pred["razon_vigencia"].fillna("VIGENTE").astype(str)
    pred["pipeline_id"] = "forecasting_tesis_v2"
    pred["fecha_ejecucion"] = pd.Timestamp.now()

    cols = [
        "tipo_producto",
        "categoria_producto",
        "producto_base",
        "producto",
        "producto_dashboard",
        "periodo",
        "periodo_prediccion",
        "qty_fabricada",
        "qty_planificada",
        "pronostico_qty",
        "qty_recomendada",
        "qty_min_recomendada",
        "qty_max_recomendada",
        "nivel_confianza",
        "rolling_std_3",
        "n_ordenes",
        "sugerencia_accion",
        "posibles_causas",
        "es_vigente_operativo",
        "razon_vigencia",
        "pipeline_id",
        "fecha_ejecucion",
    ]
    out = pred[cols].copy()
    out["tipo_producto"] = out["tipo_producto"].astype(str).str.upper().str.strip()

    ddl = """
    CREATE SCHEMA IF NOT EXISTS gold;
    CREATE TABLE IF NOT EXISTS gold.pronostico_produccion_resultado_v2 (
        id SERIAL PRIMARY KEY,
        tipo_producto VARCHAR(20),
        categoria_producto VARCHAR(255),
        producto_base VARCHAR(255),
        producto VARCHAR(255),
        producto_dashboard VARCHAR(255),
        periodo DATE,
        periodo_prediccion DATE,
        qty_fabricada NUMERIC,
        qty_planificada NUMERIC,
        pronostico_qty NUMERIC,
        qty_recomendada NUMERIC,
        qty_min_recomendada NUMERIC,
        qty_max_recomendada NUMERIC,
        nivel_confianza VARCHAR(20),
        rolling_std_3 NUMERIC,
        n_ordenes NUMERIC,
        sugerencia_accion TEXT,
        posibles_causas TEXT,
        es_vigente_operativo BOOLEAN,
        razon_vigencia VARCHAR(50),
        pipeline_id VARCHAR(80),
        fecha_ejecucion TIMESTAMP,
        modelo_ganador VARCHAR(80)
    );
    """

    with connect_dwh() as conn:
        with conn.cursor() as cur:
            cur.execute(ddl)
            cur.execute("ALTER TABLE gold.pronostico_produccion_resultado_v2 ADD COLUMN IF NOT EXISTS producto_dashboard VARCHAR(255)")
            cur.execute("TRUNCATE TABLE gold.pronostico_produccion_resultado_v2")

            records = [tuple(row) + (winner,) for row in out.itertuples(index=False, name=None)]
            execute_values(
                cur,
                """
                INSERT INTO gold.pronostico_produccion_resultado_v2 (
                    tipo_producto,categoria_producto,producto_base,producto,producto_dashboard,periodo,periodo_prediccion,
                    qty_fabricada,qty_planificada,pronostico_qty,qty_recomendada,qty_min_recomendada,qty_max_recomendada,
                    nivel_confianza,rolling_std_3,n_ordenes,sugerencia_accion,posibles_causas,es_vigente_operativo,
                    razon_vigencia,pipeline_id,fecha_ejecucion,modelo_ganador
                ) VALUES %s
                """,
                records,
            )

            # Tabla unificada operativa: PT desde modelo nuevo, PP desde modelo legacy
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS gold.pronostico_produccion_unificado_v1 (
                    id SERIAL PRIMARY KEY,
                    tipo_producto VARCHAR(20),
                    categoria_producto VARCHAR(255),
                    producto_base VARCHAR(255),
                    producto VARCHAR(255),
                    producto_dashboard VARCHAR(255),
                    periodo DATE,
                    periodo_prediccion DATE,
                    qty_fabricada NUMERIC,
                    qty_planificada NUMERIC,
                    pronostico_qty NUMERIC,
                    qty_recomendada NUMERIC,
                    qty_min_recomendada NUMERIC,
                    qty_max_recomendada NUMERIC,
                    nivel_confianza VARCHAR(20),
                    rolling_std_3 NUMERIC,
                    n_ordenes NUMERIC,
                    sugerencia_accion TEXT,
                    posibles_causas TEXT,
                    es_vigente_operativo BOOLEAN,
                    razon_vigencia VARCHAR(50),
                    pipeline_id VARCHAR(80),
                    fecha_ejecucion TIMESTAMP,
                    modelo_ganador VARCHAR(80),
                    fuente_modelo VARCHAR(40)
                )
                """
            )
            cur.execute("TRUNCATE TABLE gold.pronostico_produccion_unificado_v1")

            # PT nuevo (tabla v2)
            cur.execute(
                """
                INSERT INTO gold.pronostico_produccion_unificado_v1 (
                    tipo_producto,categoria_producto,producto_base,producto,producto_dashboard,periodo,periodo_prediccion,
                    qty_fabricada,qty_planificada,pronostico_qty,qty_recomendada,qty_min_recomendada,qty_max_recomendada,
                    nivel_confianza,rolling_std_3,n_ordenes,sugerencia_accion,posibles_causas,es_vigente_operativo,
                    razon_vigencia,pipeline_id,fecha_ejecucion,modelo_ganador,fuente_modelo
                )
                SELECT
                    tipo_producto,categoria_producto,producto_base,producto,producto_dashboard,periodo,periodo_prediccion,
                    qty_fabricada,NULL::NUMERIC AS qty_planificada,pronostico_qty,qty_recomendada,qty_min_recomendada,qty_max_recomendada,
                    nivel_confianza,rolling_std_3,n_ordenes,sugerencia_accion,posibles_causas,es_vigente_operativo,
                    razon_vigencia,pipeline_id,fecha_ejecucion,modelo_ganador,
                    'MODELO_NUEVO_PT'::VARCHAR(40) AS fuente_modelo
                FROM (
                    SELECT
                        t.*,
                        ROW_NUMBER() OVER (
                            PARTITION BY COALESCE(NULLIF(TRIM(t.producto_dashboard), ''), NULLIF(TRIM(t.producto), ''), NULLIF(TRIM(t.producto_base), ''))
                            ORDER BY t.periodo_prediccion DESC, t.fecha_ejecucion DESC
                        ) AS rn
                    FROM gold.pronostico_produccion_resultado_v2 t
                    WHERE UPPER(COALESCE(t.tipo_producto, 'OTRO')) = 'PT'
                      AND t.periodo_prediccion = (
                          SELECT MAX(periodo_prediccion)
                          FROM gold.pronostico_produccion_resultado_v2
                          WHERE UPPER(COALESCE(tipo_producto, 'OTRO')) = 'PT'
                      )
                ) z
                WHERE z.rn = 1
                """
            )

            # PP legacy (tabla anterior)
            cur.execute(
                """
                INSERT INTO gold.pronostico_produccion_unificado_v1 (
                    tipo_producto,categoria_producto,producto_base,producto,producto_dashboard,periodo,periodo_prediccion,
                    qty_fabricada,qty_planificada,pronostico_qty,qty_recomendada,qty_min_recomendada,qty_max_recomendada,
                    nivel_confianza,rolling_std_3,n_ordenes,sugerencia_accion,posibles_causas,es_vigente_operativo,
                    razon_vigencia,pipeline_id,fecha_ejecucion,modelo_ganador,fuente_modelo
                )
                SELECT
                    UPPER(COALESCE(tipo_producto, 'OTRO')),
                    COALESCE(categoria_producto, 'GENERAL'),
                    COALESCE(producto_base, producto, 'SIN_NOMBRE'),
                    COALESCE(producto, 'SIN_NOMBRE'),
                    COALESCE(producto, 'SIN_NOMBRE'),
                    periodo,
                    periodo_prediccion,
                    qty_fabricada,
                    NULL::NUMERIC AS qty_planificada,
                    pronostico_qty,
                    qty_recomendada,
                    qty_min_recomendada,
                    qty_max_recomendada,
                    COALESCE(nivel_confianza, 'MEDIA'),
                    rolling_std_3,
                    n_ordenes,
                    COALESCE(sugerencia_accion, 'Planificar con validacion operativa.'),
                    COALESCE(posibles_causas, 'Serie historica legacy.'),
                    COALESCE(es_vigente_operativo, TRUE),
                    COALESCE(razon_vigencia, 'VIGENTE'),
                    'forecasting_legacy_pp',
                    NOW(),
                    'MODELO_LEGACY',
                    'MODELO_ANTERIOR_PP'
                FROM (
                    SELECT
                        t.*,
                        ROW_NUMBER() OVER (
                            PARTITION BY COALESCE(NULLIF(TRIM(t.producto), ''), NULLIF(TRIM(t.producto_base), ''))
                            ORDER BY t.periodo_prediccion DESC
                        ) AS rn
                    FROM gold.pronostico_produccion_resultado t
                    WHERE UPPER(COALESCE(t.tipo_producto, 'OTRO')) = 'PP'
                      AND t.periodo_prediccion = (
                          SELECT MAX(periodo_prediccion)
                          FROM gold.pronostico_produccion_resultado
                          WHERE UPPER(COALESCE(tipo_producto, 'OTRO')) = 'PP'
                      )
                ) s
                WHERE s.rn = 1
                """
            )
        conn.commit()

    print(f"Publicadas {len(out)} filas en gold.pronostico_produccion_resultado_v2 (modelo={winner})")
    print("Publicada tabla unificada gold.pronostico_produccion_unificado_v1 (PT nuevo + PP legacy)")


if __name__ == "__main__":
    main()
