"""
Generador de datos realistas para Data Mining - CONDIMENSA.

Objetivo:
- Basarse en patrones reales (si existe tabla silver.kronos_ventas).
- Poblar tablas silver/gold/dm para los modelos.
- Recalcular tablas *_resultado consumidas por el dashboard.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values


RNG = np.random.default_rng(42)


@dataclass
class DbConfig:
    host: str
    port: int
    database: str
    user: str
    password: str


def candidate_configs() -> Iterable[DbConfig]:
    env_host = os.getenv("DB_HOST")
    env_port = os.getenv("DB_PORT")
    if env_host:
        yield DbConfig(
            host=env_host,
            port=int(env_port or "5432"),
            database=os.getenv("DB_NAME", "condimensa_analytics"),
            user=os.getenv("DB_USER", "condimensa"),
            password=os.getenv("DB_PASSWORD", "change_me"),
        )
    yield DbConfig("localhost", 5433, "condimensa_analytics", "condimensa", "change_me")
    yield DbConfig("condimensa_dwh", 5432, "condimensa_analytics", "condimensa", "change_me")
    yield DbConfig("postgres_local", 5432, "condimensa_analytics", "condimensa", "change_me")


def connect_db():
    last_error = None
    for cfg in candidate_configs():
        try:
            conn = psycopg2.connect(
                host=cfg.host,
                port=cfg.port,
                database=cfg.database,
                user=cfg.user,
                password=cfg.password,
            )
            print(f"[OK] Conexion a {cfg.host}:{cfg.port}/{cfg.database}")
            return conn
        except Exception as exc:  # pragma: no cover
            last_error = exc
    raise RuntimeError(f"No se pudo conectar a la base de datos: {last_error}")


def read_sql_df(conn, query: str) -> pd.DataFrame:
    return pd.read_sql(query, conn)


def table_exists(conn, schema: str, table: str) -> bool:
    query = """
    SELECT EXISTS (
      SELECT 1
      FROM information_schema.tables
      WHERE table_schema = %s AND table_name = %s
    ) AS exists_flag
    """
    with conn.cursor() as cur:
        cur.execute(query, (schema, table))
        return bool(cur.fetchone()[0])


def cargar_base_real(conn) -> pd.DataFrame:
    fuente = None
    if table_exists(conn, "silver", "kronos_ventas"):
        fuente = "silver.kronos_ventas"
    elif table_exists(conn, "silver", "kronos_ventas_silver"):
        fuente = "silver.kronos_ventas_silver"

    if not fuente:
        raise RuntimeError(
            "No existe silver.kronos_ventas ni silver.kronos_ventas_silver para inferir patrones reales."
        )

    print(f"[INFO] Usando fuente base real: {fuente}")
    query = f"""
    SELECT
        LOWER(TRIM(centro_costo)) AS centro_costo,
        COALESCE(NULLIF(TRIM(CAST(codigo_producto AS TEXT)), ''), TRIM(CAST(codigo_alterno AS TEXT)), 'SIN_COD') AS codigo_producto,
        UPPER(TRIM(producto)) AS producto,
        CASE
            WHEN UPPER(producto) LIKE '%AJO%' THEN 'AJOS'
            WHEN UPPER(producto) LIKE '%ALINO%' OR UPPER(producto) LIKE '%ALIÑO%' THEN 'ALINOS'
            WHEN UPPER(producto) LIKE '%SAZON%' THEN 'SAZONADORES'
            WHEN UPPER(producto) LIKE '%CALDO%' THEN 'CALDOS'
            WHEN UPPER(producto) LIKE '%OREGANO%' OR UPPER(producto) LIKE '%COMINO%' OR UPPER(producto) LIKE '%PAPRIKA%' OR UPPER(producto) LIKE '%CANELA%' THEN 'ESPECIAS'
            WHEN UPPER(producto) LIKE '%MAYONESA%' OR UPPER(producto) LIKE '%SALSA%' THEN 'SALSAS'
            ELSE 'OTROS'
        END AS categoria,
        CASE
            WHEN UPPER(producto) LIKE '%PASTA%' THEN 365
            WHEN UPPER(producto) LIKE '%SALSA%' OR UPPER(producto) LIKE '%MAYONESA%' THEN 365
            WHEN UPPER(producto) LIKE '%OREGANO%' OR UPPER(producto) LIKE '%COMINO%' OR UPPER(producto) LIKE '%PAPRIKA%' OR UPPER(producto) LIKE '%CANELA%' THEN 365
            WHEN UPPER(producto) LIKE '%CHOCOLATE%' THEN 270
            ELSE 365
        END AS dias_vida_util,
        SUM(COALESCE(NULLIF(TRIM(CAST(cant_venta AS TEXT)), '')::NUMERIC, 0))::FLOAT AS cant_venta,
        SUM(COALESCE(NULLIF(TRIM(CAST(cant_devolucion AS TEXT)), '')::NUMERIC, 0))::FLOAT AS cant_devolucion,
        SUM(COALESCE(NULLIF(TRIM(CAST(total_venta AS TEXT)), '')::NUMERIC, 0))::FLOAT AS total_venta,
        SUM(COALESCE(NULLIF(TRIM(CAST(total_devolucion AS TEXT)), '')::NUMERIC, 0))::FLOAT AS total_devolucion,
        AVG(COALESCE(NULLIF(TRIM(CAST(prc_rentabilidad AS TEXT)), '')::NUMERIC, 28))::FLOAT AS prc_rentabilidad
    FROM {fuente}
    WHERE COALESCE(NULLIF(TRIM(CAST(cant_venta AS TEXT)), '')::NUMERIC, 0) > 0
      AND producto IS NOT NULL
      AND centro_costo IS NOT NULL
    GROUP BY 1, 2, 3, 4, 5
    """
    df = read_sql_df(conn, query)
    if df.empty:
        raise RuntimeError("La fuente base existe, pero no tiene datos válidos para generar DM.")
    return df


def construir_silver_realista(df_base: pd.DataFrame) -> pd.DataFrame:
    meses = [("ENERO", 1.00), ("FEBRERO", 0.95), ("MARZO", 1.08)]

    price = np.where(df_base["cant_venta"] > 0, df_base["total_venta"] / df_base["cant_venta"], 1.0)
    df_base = df_base.assign(precio_unitario=np.clip(price, 0.3, None))

    agency_rate = (
        df_base.groupby("centro_costo")[["cant_devolucion", "cant_venta"]]
        .sum()
        .assign(base_rate=lambda x: np.clip(np.where(x["cant_venta"] > 0, x["cant_devolucion"] / x["cant_venta"], 0.05), 0.02, 0.18))
    )["base_rate"]

    rows = []
    for _, r in df_base.iterrows():
        for mes, season in meses:
            vol_noise = float(np.clip(RNG.normal(1.0, 0.13), 0.7, 1.4))
            cant_venta = max(5, int(round(r["cant_venta"] * season * vol_noise)))

            base_rate = float(agency_rate.get(r["centro_costo"], 0.05))
            risk_mult = 1.35 if r["dias_vida_util"] <= 180 else 1.0
            rate_noise = float(np.clip(RNG.normal(1.0, 0.15), 0.7, 1.4))
            tasa_dev = float(np.clip(base_rate * risk_mult * rate_noise, 0.015, 0.32))
            cant_dev = max(1, int(round(cant_venta * tasa_dev)))
            cant_dev = min(cant_dev, max(1, cant_venta - 1))

            total_venta = round(float(cant_venta * r["precio_unitario"]), 2)
            total_dev = round(float(cant_dev * r["precio_unitario"]), 2)
            cant_neto = cant_venta - cant_dev
            total_neto = round(total_venta - total_dev, 2)

            margen = float(np.clip(RNG.normal(r["prc_rentabilidad"] / 100.0, 0.05), 0.18, 0.45))
            rentabilidad = round(total_neto * margen, 2)
            costo_venta = round(total_neto - rentabilidad, 2)

            motivo = None
            if cant_dev > 0:
                if r["dias_vida_util"] <= 180:
                    motivo = "CADUCADO"
                elif RNG.random() < 0.10:
                    motivo = "DANO_EMPAQUE"

            rows.append(
                {
                    "centro_costo": r["centro_costo"],
                    "codigo_producto": r["codigo_producto"],
                    "producto": r["producto"],
                    "mes": mes,
                    "anio": "2026",
                    "cant_venta": cant_venta,
                    "total_venta": total_venta,
                    "cant_nc": 0,
                    "total_nc": 0.0,
                    "cant_devolucion": cant_dev,
                    "total_devolucion": total_dev,
                    "cant_neto": cant_neto,
                    "total_neto": total_neto,
                    "costo_venta": costo_venta,
                    "rentabilidad": rentabilidad,
                    "prc_rentabilidad": round(margen * 100, 2),
                    "categoria": r["categoria"],
                    "dias_vida_util": int(r["dias_vida_util"]),
                    "motivo_devolucion": motivo,
                }
            )

    df = pd.DataFrame(rows)

    # Garantizar que toda agencia tenga al menos algo de devolucion.
    dev_by_ag = df.groupby("centro_costo")["cant_devolucion"].sum()
    for ag in dev_by_ag[dev_by_ag <= 0].index:
        idx = df[df["centro_costo"] == ag].sort_values("dias_vida_util").index[:1]
        if len(idx) > 0:
            df.loc[idx, "cant_devolucion"] = 1
            df.loc[idx, "total_devolucion"] = df.loc[idx, "total_venta"] / df.loc[idx, "cant_venta"]
            df.loc[idx, "cant_neto"] = df.loc[idx, "cant_venta"] - 1
            df.loc[idx, "total_neto"] = df.loc[idx, "total_venta"] - df.loc[idx, "total_devolucion"]
            df.loc[idx, "motivo_devolucion"] = "CADUCADO"

    return df


def generar_cestas(df_silver: pd.DataFrame, n_transacciones: int = 1800) -> pd.DataFrame:
    top = (
        df_silver.groupby(["codigo_producto", "producto", "categoria"])["cant_venta"]
        .sum()
        .sort_values(ascending=False)
        .reset_index()
        .head(18)
    )

    if len(top) < 6:
        raise RuntimeError("No hay suficientes productos para generar cestas.")

    top_codes = top["codigo_producto"].tolist()
    top_map = top.set_index("codigo_producto").to_dict("index")

    def find_code(*keywords: str):
        for _, row in top.iterrows():
            pname = str(row["producto"]).upper()
            if all(k in pname for k in keywords):
                return str(row["codigo_producto"])
        return None

    # Relaciones de negocio con confianza realista (60-70% aprox).
    reglas_semilla = []
    c_salsa = find_code("SALSA")
    c_mayo = find_code("MAYONESA")
    c_ajo = find_code("AJO")
    c_alino = find_code("ALINO")
    c_comino = find_code("COMINO")
    c_oregano = find_code("OREGANO")
    c_caldo = find_code("CALDO")
    c_sazon = find_code("SAZON")

    if c_salsa and c_mayo:
        reglas_semilla.append((c_salsa, c_mayo, 0.64))
    if c_ajo and c_alino:
        reglas_semilla.append((c_ajo, c_alino, 0.61))
    if c_comino and c_oregano:
        reglas_semilla.append((c_comino, c_oregano, 0.66))
    if c_caldo and c_sazon:
        reglas_semilla.append((c_caldo, c_sazon, 0.60))

    agencias = df_silver["centro_costo"].value_counts(normalize=True)
    agencias_list = agencias.index.tolist()
    agencias_prob = agencias.values

    records = []
    for i in range(1, n_transacciones + 1):
        trx = f"TRX{i:06d}"
        agencia = RNG.choice(agencias_list, p=agencias_prob)
        month = int(RNG.integers(1, 4))
        day = int(RNG.integers(1, 28))
        fecha = f"2026-{month:02d}-{day:02d}"

        anchor = str(RNG.choice(top_codes))
        items = {anchor}

        # Reglas semilla direccionadas (evita bidireccionalidad artificial).
        for ant, cons, prob in reglas_semilla:
            if anchor == ant and RNG.random() < prob:
                items.add(cons)

        # Extras aleatorios para evitar confianza 100%.
        n_extra = int(RNG.integers(0, 3))
        if n_extra > 0:
            extras = RNG.choice(top_codes, size=n_extra, replace=False)
            for ex in extras:
                items.add(str(ex))

        if len(items) < 2:
            items.add(str(RNG.choice(top_codes)))

        for codigo in sorted(items):
            info = top_map[codigo]
            cantidad = int(RNG.integers(1, 4))
            price = float(
                df_silver.loc[df_silver["codigo_producto"] == codigo, "total_venta"].sum()
                / max(1.0, df_silver.loc[df_silver["codigo_producto"] == codigo, "cant_venta"].sum())
            )
            price = float(np.clip(price, 0.3, None))
            records.append(
                {
                    "transaccion_id": trx,
                    "fecha": fecha,
                    "agencia": agencia,
                    "codigo_producto": codigo,
                    "producto": info["producto"],
                    "categoria": info["categoria"],
                    "cantidad": cantidad,
                    "precio_unitario": round(price, 2),
                    "total": round(price * cantidad, 2),
                }
            )

    return pd.DataFrame(records)


def _deduplicar_reglas_inversas(df_rules: pd.DataFrame) -> pd.DataFrame:
    """
    Elimina reglas espejo A->B / B->A y conserva la de mayor confianza.
    """
    if df_rules.empty:
        return df_rules

    df = df_rules.copy()
    df = df[(df["antecedents"].apply(len) == 1) & (df["consequents"].apply(len) == 1)].copy()
    if df.empty:
        return df_rules

    df["item_a"] = df["antecedents"].apply(lambda s: next(iter(s)))
    df["item_b"] = df["consequents"].apply(lambda s: next(iter(s)))
    df["pair_key"] = df.apply(lambda r: "||".join(sorted([r["item_a"], r["item_b"]])), axis=1)
    df = df.sort_values(["pair_key", "confidence", "lift"], ascending=[True, False, False])
    return df.drop_duplicates("pair_key", keep="first")


def cargar_tablas_base(conn, df_silver: pd.DataFrame, df_cestas: pd.DataFrame):
    with conn.cursor() as cur:
        cur.execute("CREATE SCHEMA IF NOT EXISTS silver;")
        cur.execute("CREATE SCHEMA IF NOT EXISTS gold;")
        cur.execute("CREATE SCHEMA IF NOT EXISTS dm;")

        cur.execute("DROP TABLE IF EXISTS silver.kronos_ventas_silver CASCADE;")
        cur.execute(
            """
            CREATE TABLE silver.kronos_ventas_silver (
                id SERIAL PRIMARY KEY,
                centro_costo VARCHAR(50),
                codigo_producto VARCHAR(30),
                producto VARCHAR(200),
                mes VARCHAR(20),
                anio VARCHAR(10),
                cant_venta NUMERIC(12,2),
                total_venta NUMERIC(15,2),
                cant_nc NUMERIC(12,2) DEFAULT 0,
                total_nc NUMERIC(15,2) DEFAULT 0,
                cant_devolucion NUMERIC(12,2),
                total_devolucion NUMERIC(15,2),
                cant_neto NUMERIC(12,2),
                total_neto NUMERIC(15,2),
                costo_venta NUMERIC(15,2),
                rentabilidad NUMERIC(15,2),
                prc_rentabilidad NUMERIC(8,2),
                categoria VARCHAR(80),
                dias_vida_util INTEGER,
                motivo_devolucion VARCHAR(50),
                fecha_carga TIMESTAMP DEFAULT NOW()
            );
            """
        )
        cols = [
            "centro_costo", "codigo_producto", "producto", "mes", "anio", "cant_venta", "total_venta",
            "cant_nc", "total_nc", "cant_devolucion", "total_devolucion", "cant_neto", "total_neto",
            "costo_venta", "rentabilidad", "prc_rentabilidad", "categoria", "dias_vida_util", "motivo_devolucion",
        ]
        execute_values(
            cur,
            f"INSERT INTO silver.kronos_ventas_silver ({', '.join(cols)}) VALUES %s",
            [tuple(r[c] for c in cols) for _, r in df_silver.iterrows()],
        )

        cur.execute("DROP TABLE IF EXISTS dm.cestas_transacciones CASCADE;")
        cur.execute(
            """
            CREATE TABLE dm.cestas_transacciones (
                id SERIAL PRIMARY KEY,
                transaccion_id VARCHAR(20),
                fecha DATE,
                agencia VARCHAR(50),
                codigo_producto VARCHAR(30),
                producto VARCHAR(200),
                categoria VARCHAR(80),
                cantidad INTEGER,
                precio_unitario NUMERIC(10,2),
                total NUMERIC(12,2)
            );
            """
        )
        ccols = ["transaccion_id", "fecha", "agencia", "codigo_producto", "producto", "categoria", "cantidad", "precio_unitario", "total"]
        execute_values(
            cur,
            f"INSERT INTO dm.cestas_transacciones ({', '.join(ccols)}) VALUES %s",
            [tuple(r[c] for c in ccols) for _, r in df_cestas.iterrows()],
        )

    conn.commit()
    print(f"[OK] silver.kronos_ventas_silver: {len(df_silver)} filas")
    print(f"[OK] dm.cestas_transacciones: {len(df_cestas)} items")


def construir_metricas_gold(conn):
    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS gold.metricas_agencias CASCADE;")
        cur.execute(
            """
            CREATE TABLE gold.metricas_agencias AS
            SELECT
                centro_costo,
                CASE
                    WHEN centro_costo IN ('guayaquil', 'portoviejo', 'santo_domingo') THEN 'COSTA'
                    WHEN centro_costo IN ('puyo') THEN 'ORIENTE'
                    ELSE 'SIERRA'
                END AS region,
                CASE
                    WHEN SUM(total_venta) > 200000 THEN 'GRANDE'
                    WHEN SUM(total_venta) > 70000 THEN 'MEDIANO'
                    ELSE 'PEQUENO'
                END AS tamano,
                SUM(cant_venta)::INT AS total_transacciones,
                SUM(total_venta)::NUMERIC(15,2) AS total_ventas,
                SUM(total_devolucion)::NUMERIC(15,2) AS total_devoluciones,
                SUM(total_neto)::NUMERIC(15,2) AS total_neto,
                ROUND((SUM(total_venta) / NULLIF(SUM(cant_venta), 0))::NUMERIC, 2) AS ticket_promedio,
                ROUND((SUM(cant_devolucion) / NULLIF(SUM(cant_venta), 0) * 100)::NUMERIC, 2) AS tasa_devolucion,
                ROUND((SUM(rentabilidad) / NULLIF(SUM(total_neto), 0) * 100)::NUMERIC, 2) AS rentabilidad_porcentual,
                COUNT(DISTINCT codigo_producto)::INT AS productos_distintos,
                CASE
                    WHEN ROUND((SUM(cant_devolucion) / NULLIF(SUM(cant_venta), 0) * 100)::NUMERIC, 2) > 10 THEN 'ALTO_RIESGO'
                    WHEN ROUND((SUM(rentabilidad) / NULLIF(SUM(total_neto), 0) * 100)::NUMERIC, 2) > 34 THEN 'SOBRESALIENTE'
                    ELSE 'ESTABLE'
                END AS comportamiento_esperado
            FROM silver.kronos_ventas_silver
            GROUP BY centro_costo;
            """
        )

        cur.execute("DROP TABLE IF EXISTS gold.metricas_productos CASCADE;")
        cur.execute(
            """
            CREATE TABLE gold.metricas_productos AS
            SELECT
                codigo_producto,
                producto,
                categoria,
                ROUND((SUM(total_venta) / NULLIF(SUM(cant_venta), 0))::NUMERIC, 2) AS precio_unitario,
                ROUND((SUM(costo_venta) / NULLIF(SUM(cant_neto), 0))::NUMERIC, 2) AS costo_unitario,
                SUM(cant_venta)::INT AS cantidad_vendida,
                SUM(cant_devolucion)::INT AS cantidad_devuelta,
                SUM(total_venta)::NUMERIC(15,2) AS total_ventas,
                SUM(total_devolucion)::NUMERIC(15,2) AS total_devoluciones,
                ROUND((SUM(cant_devolucion) / NULLIF(SUM(cant_venta), 0) * 100)::NUMERIC, 2) AS tasa_devolucion,
                ROUND((SUM(rentabilidad) / NULLIF(SUM(total_neto), 0) * 100)::NUMERIC, 2) AS rentabilidad_porcentual,
                MAX(motivo_devolucion) AS motivo_devolucion_principal,
                COUNT(DISTINCT centro_costo)::INT AS n_agencias_venta,
                ROUND((SUM(total_venta) / NULLIF(SUM(cant_venta), 0))::NUMERIC, 2) AS ticket_promedio_producto,
                CASE WHEN SUM(cant_venta) < 250 THEN TRUE ELSE FALSE END AS es_producto_nuevo,
                CASE
                    WHEN MAX(dias_vida_util) <= 120 THEN 80
                    WHEN MAX(dias_vida_util) <= 180 THEN 140
                    ELSE 240
                END AS dias_en_catalogo,
                MAX(dias_vida_util)::INT AS dias_vida_util
            FROM silver.kronos_ventas_silver
            GROUP BY codigo_producto, producto, categoria;
            """
        )
    conn.commit()
    print("[OK] Tablas gold.metricas_agencias y gold.metricas_productos actualizadas")


def construir_resultados_dashboard(conn):
    from sklearn.ensemble import IsolationForest, RandomForestClassifier
    from sklearn.preprocessing import StandardScaler
    from mlxtend.frequent_patterns import apriori, association_rules
    from mlxtend.preprocessing import TransactionEncoder

    # APRIORI -> gold.reglas_asociacion_resultado
    cestas = read_sql_df(conn, "SELECT transaccion_id, producto FROM dm.cestas_transacciones ORDER BY transaccion_id")
    tx = cestas.groupby("transaccion_id")["producto"].apply(list).tolist()
    te = TransactionEncoder()
    encoded = pd.DataFrame(te.fit(tx).transform(tx), columns=te.columns_)
    itemsets = apriori(encoded, min_support=0.03, use_colnames=True)
    rules = association_rules(itemsets, metric="confidence", min_threshold=0.40) if len(itemsets) else pd.DataFrame()

    if len(rules):
        rules = rules[(rules["antecedents"].apply(len) >= 1) & (rules["consequents"].apply(len) >= 1)].copy()
        rules = _deduplicar_reglas_inversas(rules)
        rules = rules[(rules["confidence"] >= 0.50) & (rules["confidence"] <= 0.72)].copy()
        rules = rules.sort_values(["lift", "confidence"], ascending=[False, False])
        rules["antecedente"] = rules["antecedents"].apply(lambda x: ", ".join(sorted(list(x))))
        rules["consecuente"] = rules["consequents"].apply(lambda x: ", ".join(sorted(list(x))))
        rules["fuerza_asociacion"] = rules["lift"].apply(
            lambda x: "FUERTE" if x >= 2.0 else ("MODERADA" if x >= 1.4 else "DEBIL")
        )
        rules["recomendacion"] = rules.apply(
            lambda r: f"Crear combo sugerido: {r['antecedente']} + {r['consecuente']}"
            if r["lift"] >= 1.4 else f"Ubicar juntos en percha: {r['antecedente']} y {r['consecuente']}",
            axis=1,
        )
        rules_out = rules[["antecedente", "consecuente", "support", "confidence", "lift", "fuerza_asociacion", "recomendacion"]].copy()
        rules_out.columns = ["antecedente", "consecuente", "soporte", "confianza", "lift", "fuerza_asociacion", "recomendacion"]
    else:
        rules_out = pd.DataFrame(columns=["antecedente", "consecuente", "soporte", "confianza", "lift", "fuerza_asociacion", "recomendacion"])

    # Isolation Forest -> gold.anomalias_agencias_resultado
    ag = read_sql_df(conn, "SELECT * FROM gold.metricas_agencias")
    ag["ratio_devolucion"] = pd.to_numeric(ag["tasa_devolucion"], errors="coerce").fillna(0)
    ag["ratio_rentabilidad"] = pd.to_numeric(ag["rentabilidad_porcentual"], errors="coerce").fillna(0)
    ag["ratio_costo"] = 100 - ag["ratio_rentabilidad"]
    features = ["ratio_devolucion", "ratio_rentabilidad", "ratio_costo", "ticket_promedio"]
    X = StandardScaler().fit_transform(ag[features].fillna(0))
    iso = IsolationForest(n_estimators=120, contamination=0.2, random_state=42)
    ag["es_anomalia"] = iso.fit_predict(X) == -1
    ag["anomaly_score"] = iso.decision_function(X)
    for f in features:
        std = ag[f].std()
        ag[f"z_{f}"] = (ag[f] - ag[f].mean()) / std if std > 0 else 0

    def tipo(row):
        if not row["es_anomalia"]:
            return "NORMAL", "Comportamiento dentro del rango esperado."
        if row["z_ratio_devolucion"] > 1:
            return "ALTA_DEVOLUCION", "Tasa de devolucion superior al comportamiento historico."
        if row["z_ratio_rentabilidad"] > 1:
            return "ALTA_RENTABILIDAD", "Rentabilidad superior al promedio de agencias."
        if row["z_ratio_rentabilidad"] < -1:
            return "BAJA_RENTABILIDAD", "Rentabilidad inferior y posible fuga de margen."
        return "PATRON_INUSUAL", "Patron estadistico atipico detectado por Isolation Forest."

    t = ag.apply(tipo, axis=1)
    ag["tipo_anomalia"] = [x[0] for x in t]
    ag["descripcion"] = [x[1] for x in t]
    anom_out = ag[["centro_costo", "es_anomalia", "tipo_anomalia", "tasa_devolucion", "rentabilidad_porcentual", "total_ventas", "descripcion", "anomaly_score"]]

    # Random Forest -> gold.predicciones_devolucion_resultado
    pr = read_sql_df(conn, "SELECT * FROM gold.metricas_productos")
    pr["target"] = (pd.to_numeric(pr["tasa_devolucion"], errors="coerce").fillna(0) > 10).astype(int)
    pr["cat"] = pd.factorize(pr["categoria"])[0]
    pr["log_cant"] = np.log1p(pd.to_numeric(pr["cantidad_vendida"], errors="coerce").fillna(0))
    pr["ratio_costo"] = np.where(
        pd.to_numeric(pr["precio_unitario"], errors="coerce").fillna(0) > 0,
        100 - (pd.to_numeric(pr["rentabilidad_porcentual"], errors="coerce").fillna(0)),
        100,
    )
    feats = ["cat", "log_cant", "rentabilidad_porcentual", "n_agencias_venta", "ratio_costo", "dias_en_catalogo"]
    Xp = pr[feats].fillna(0).values
    yp = pr["target"].values
    clf = RandomForestClassifier(n_estimators=120, max_depth=6, random_state=42, class_weight="balanced")
    clf.fit(Xp, yp)
    if len(clf.classes_) > 1:
        pr["probabilidad_riesgo"] = clf.predict_proba(Xp)[:, 1]
    else:
        scaled = (pr["tasa_devolucion"] / max(1.0, pr["tasa_devolucion"].max())).clip(0, 1)
        pr["probabilidad_riesgo"] = scaled
    pr["nivel_riesgo"] = pr["probabilidad_riesgo"].apply(lambda x: "ALTO" if x >= 0.62 else ("MEDIO" if x >= 0.35 else "BAJO"))
    pr["recomendacion"] = pr.apply(
        lambda r: "Priorizar rotacion, control FEFO y ajuste de pedido."
        if r["nivel_riesgo"] == "ALTO"
        else ("Monitorear tendencia y revisar reposicion semanal." if r["nivel_riesgo"] == "MEDIO" else "Mantener estrategia actual."),
        axis=1,
    )
    pred_out = pr[
        [
            "codigo_producto",
            "producto",
            "categoria",
            "tasa_devolucion",
            "dias_vida_util",
            "motivo_devolucion_principal",
            "probabilidad_riesgo",
            "nivel_riesgo",
            "recomendacion",
        ]
    ]

    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS gold.reglas_asociacion_resultado CASCADE;")
        cur.execute(
            """
            CREATE TABLE gold.reglas_asociacion_resultado (
                id SERIAL PRIMARY KEY,
                antecedente TEXT,
                consecuente TEXT,
                soporte NUMERIC(8,6),
                confianza NUMERIC(8,6),
                lift NUMERIC(10,4),
                fuerza_asociacion VARCHAR(20),
                recomendacion TEXT
            );
            """
        )
        if len(rules_out):
            execute_values(
                cur,
                """
                INSERT INTO gold.reglas_asociacion_resultado
                (antecedente, consecuente, soporte, confianza, lift, fuerza_asociacion, recomendacion)
                VALUES %s
                """,
                [tuple(x) for x in rules_out.values],
            )

        cur.execute("DROP TABLE IF EXISTS gold.anomalias_agencias_resultado CASCADE;")
        cur.execute(
            """
            CREATE TABLE gold.anomalias_agencias_resultado (
                id SERIAL PRIMARY KEY,
                centro_costo VARCHAR(50),
                es_anomalia BOOLEAN,
                tipo_anomalia VARCHAR(50),
                tasa_devolucion NUMERIC(8,2),
                rentabilidad_porcentual NUMERIC(8,2),
                total_ventas NUMERIC(15,2),
                descripcion TEXT,
                anomaly_score NUMERIC(10,6)
            );
            """
        )
        execute_values(
            cur,
            """
            INSERT INTO gold.anomalias_agencias_resultado
            (centro_costo, es_anomalia, tipo_anomalia, tasa_devolucion, rentabilidad_porcentual, total_ventas, descripcion, anomaly_score)
            VALUES %s
            """,
            [tuple(x) for x in anom_out.values],
        )

        cur.execute("DROP TABLE IF EXISTS gold.predicciones_devolucion_resultado CASCADE;")
        cur.execute(
            """
            CREATE TABLE gold.predicciones_devolucion_resultado (
                id SERIAL PRIMARY KEY,
                codigo_producto VARCHAR(30),
                producto VARCHAR(200),
                categoria VARCHAR(80),
                tasa_devolucion NUMERIC(8,2),
                dias_vida_util INTEGER,
                motivo_devolucion_principal VARCHAR(50),
                probabilidad_riesgo NUMERIC(8,6),
                nivel_riesgo VARCHAR(20),
                recomendacion TEXT
            );
            """
        )
        execute_values(
            cur,
            """
            INSERT INTO gold.predicciones_devolucion_resultado
            (codigo_producto, producto, categoria, tasa_devolucion, dias_vida_util, motivo_devolucion_principal, probabilidad_riesgo, nivel_riesgo, recomendacion)
            VALUES %s
            """,
            [tuple(x) for x in pred_out.values],
        )

    conn.commit()
    print(f"[OK] gold.reglas_asociacion_resultado: {len(rules_out)} filas")
    print(f"[OK] gold.anomalias_agencias_resultado: {len(anom_out)} filas")
    print(f"[OK] gold.predicciones_devolucion_resultado: {len(pred_out)} filas")


def main():
    print("=" * 70)
    print("GENERADOR REALISTA DE DATOS DM - CONDIMENSA")
    print("=" * 70)

    conn = connect_db()
    try:
        base = cargar_base_real(conn)
        silver = construir_silver_realista(base)
        cestas = generar_cestas(silver)
        cargar_tablas_base(conn, silver, cestas)
        construir_metricas_gold(conn)
        construir_resultados_dashboard(conn)

        resumen = read_sql_df(
            conn,
            """
            SELECT centro_costo,
                   ROUND(SUM(total_venta)::numeric, 0) AS ventas,
                   ROUND((SUM(cant_devolucion)/NULLIF(SUM(cant_venta),0)*100)::numeric, 2) AS pct_devolucion
            FROM silver.kronos_ventas_silver
            GROUP BY centro_costo
            ORDER BY ventas DESC
            """,
        )
        print("\nResumen por agencia:")
        print(resumen.to_string(index=False))
        print("\n[OK] Proceso completo. Dashboard listo con datos realistas.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
