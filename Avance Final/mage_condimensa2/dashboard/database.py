"""
Conexion y consultas del dashboard activo.

Se dejan solo los accesos que usa la app actual:
- Resumen Ejecutivo
- Cross-Selling
- Anomalias
- Pronostico de Produccion
"""
import pandas as pd
import psycopg2
import streamlit as st

from config import APP_CONFIG, DB_CONFIG


@st.cache_resource
def get_connection():
    """Obtiene una conexion reutilizable a PostgreSQL."""
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    return conn


@st.cache_data(ttl=APP_CONFIG['cache_ttl'])
def load_data(query: str) -> pd.DataFrame:
    """Ejecuta una consulta y devuelve un DataFrame."""
    conn = get_connection()
    try:
        return pd.read_sql(query, conn)
    except Exception as exc:
        st.error(f"Error al consultar la base de datos: {exc}")
        return pd.DataFrame()


def test_connection() -> bool:
    """Verifica la conexion al DWH local."""
    try:
        conn = get_connection()
        return conn is not None
    except Exception:
        return False


QUERIES = {
    'resumen_ejecutivo_kronos': """
        SELECT
            centro_costo,
            anio,
            mes,
            cant_venta,
            total_venta,
            cant_neto,
            total_neto,
            cant_devolucion,
            total_devolucion,
            costo_venta,
            rentabilidad,
            tasa_devolucion,
            rentabilidad_promedio,
            ticket_promedio
        FROM gold.resumen_ejecutivo_kronos
    """,
    'kpi_ventas': """
        SELECT
            centro_costo,
            total_venta,
            total_neto,
            total_devolucion,
            rentabilidad,
            ticket_promedio,
            tasa_devolucion,
            rentabilidad_promedio
        FROM gold.metricas_agencias
        ORDER BY total_venta DESC
    """,
    'kpis_ventas_detalle': """
        SELECT
            centro_costo,
            producto,
            anio,
            mes,
            cant_venta,
            total_venta,
            total_neto,
            total_devolucion,
            rentabilidad
        FROM gold.kpis_ventas
    """,
    'alertas': """
        SELECT
            agencia,
            es_anomalia,
            COALESCE(razon_alerta, 'PATRON_INUSUAL') AS tipo_anomalia,
            ratio_devolucion,
            ratio_rentabilidad,
            total_ventas,
            COALESCE(razon_alerta, 'Comportamiento atipico detectado') AS descripcion,
            CASE
                WHEN ratio_rentabilidad > 30 AND ratio_devolucion < 10 THEN 'POSITIVA'
                WHEN ratio_devolucion >= 15 THEN 'NEGATIVA'
                ELSE 'MIXTA'
            END AS sentido_anomalia,
            COALESCE(razon_alerta, 'PATRON_INUSUAL') AS razon_anomalia,
            COALESCE(razon_alerta, 'Comportamiento atipico detectado') AS interpretacion,
            anomaly_score
        FROM gold.anomalias_agencias
        ORDER BY es_anomalia DESC, anomaly_score ASC
    """,
    'alertas_activas': """
        SELECT
            agencia,
            es_anomalia,
            COALESCE(razon_alerta, 'PATRON_INUSUAL') AS tipo_anomalia,
            ratio_devolucion,
            ratio_rentabilidad,
            total_ventas,
            COALESCE(razon_alerta, 'Comportamiento atipico detectado') AS descripcion,
            CASE
                WHEN ratio_rentabilidad > 30 AND ratio_devolucion < 10 THEN 'POSITIVA'
                WHEN ratio_devolucion >= 15 THEN 'NEGATIVA'
                ELSE 'MIXTA'
            END AS sentido_anomalia,
            COALESCE(razon_alerta, 'PATRON_INUSUAL') AS razon_anomalia,
            COALESCE(razon_alerta, 'Comportamiento atipico detectado') AS interpretacion,
            anomaly_score
        FROM gold.anomalias_agencias
        WHERE es_anomalia = TRUE
        ORDER BY anomaly_score ASC
    """,
    'combinaciones': """
        SELECT
            antecedente,
            consecuente,
            soporte,
            confianza,
            lift,
            COALESCE(
                interpretacion,
                CASE WHEN lift >= 2 THEN 'FUERTE' ELSE 'MODERADA' END
            ) AS fuerza_asociacion,
            COALESCE(
                accion_sugerida,
                'Aplicar cross-selling en punto de venta'
            ) AS recomendacion
        FROM gold.reglas_asociacion
        ORDER BY lift DESC
    """,
    'predicciones_v2': """
        WITH estado_v3 AS (
            SELECT
                product_name AS producto_dashboard,
                source_type AS tipo_producto,
                es_estacional,
                meses_estacionales,
                estado_producto AS estado_producto_v3
            FROM silver.forecasting_v3_pt_productos_model
            UNION ALL
            SELECT
                product_name AS producto_dashboard,
                source_type AS tipo_producto,
                es_estacional,
                meses_estacionales,
                estado_producto AS estado_producto_v3
            FROM silver.forecasting_v3_pp_productos_model
        )
        SELECT
            p.tipo_producto,
            p.categoria_producto,
            p.producto_base,
            p.producto,
            p.producto_dashboard,
            p.periodo,
            p.periodo_prediccion,
            p.qty_fabricada,
            p.qty_planificada,
            p.pronostico_qty,
            p.stock_actual,
            p.qty_recomendada,
            p.qty_min_recomendada,
            p.qty_max_recomendada,
            p.nivel_confianza,
            p.rolling_std_3,
            p.n_ordenes,
            p.sugerencia_accion,
            p.posibles_causas,
            p.es_vigente_operativo,
            p.razon_vigencia,
            p.pipeline_id,
            p.fecha_ejecucion,
            p.modelo_ganador,
            p.fuente_modelo,
            COALESCE(e.es_estacional, FALSE) AS es_estacional,
            COALESCE(e.meses_estacionales, '') AS meses_estacionales,
            COALESCE(e.estado_producto_v3, p.razon_vigencia) AS estado_producto_v3
        FROM gold.pronostico_produccion_unificado_v1 p
        LEFT JOIN estado_v3 e
            ON e.producto_dashboard = p.producto_dashboard
           AND UPPER(e.tipo_producto) = UPPER(p.tipo_producto)
        ORDER BY p.periodo_prediccion DESC, p.producto ASC
    """,
    'predicciones_legacy': """
        SELECT
            tipo_producto,
            categoria_producto,
            producto_base,
            producto,
            producto AS producto_dashboard,
            periodo,
            periodo_prediccion,
            qty_fabricada,
            qty_planificada,
            pronostico_qty,
            0::numeric AS stock_actual,
            qty_recomendada,
            qty_min_recomendada,
            qty_max_recomendada,
            nivel_confianza,
            rolling_std_3,
            n_ordenes,
            sugerencia_accion,
            posibles_causas,
            es_vigente_operativo,
            razon_vigencia,
            NULL::text AS pipeline_id,
            NULL::timestamp AS fecha_ejecucion,
            NULL::text AS modelo_ganador,
            'MODELO_ANTERIOR_PP'::text AS fuente_modelo,
            FALSE AS es_estacional,
            ''::text AS meses_estacionales,
            razon_vigencia AS estado_producto_v3
        FROM gold.pronostico_produccion_resultado
        ORDER BY periodo_prediccion DESC, producto ASC
    """,
    'productos_estacionales_forecasting': """
        SELECT
            producto_dashboard,
            tipo_producto,
            temporada_meses,
            meses_activos,
            meses_observados,
            active_share,
            total_qty_historica,
            producto_baja_rotacion,
            fecha_ejecucion
        FROM gold.forecasting_productos_estacionales_v1
        ORDER BY total_qty_historica DESC, producto_dashboard
    """,
    'quickbooks_indicadores_comerciales': """
        WITH gold_base AS (
            SELECT
                fecha,
                anio,
                mes,
                mes_nombre,
                agencia,
                cliente,
                familia,
                producto,
                cantidad,
                venta_neta,
                transacciones,
                COALESCE(fuente_dato, 'Transaccional QuickBooks')::text AS fuente_dato
            FROM gold.quickbooks_indicadores_comerciales
        ),
        gold_periods AS (
            SELECT DISTINCT anio, mes
            FROM gold_base
            WHERE anio IS NOT NULL
              AND mes IS NOT NULL
        ),
        historico_mensual AS (
            SELECT
                periodo AS fecha,
                anio,
                EXTRACT(MONTH FROM periodo)::int AS mes,
                CASE EXTRACT(MONTH FROM periodo)::int
                    WHEN 1 THEN 'enero'
                    WHEN 2 THEN 'febrero'
                    WHEN 3 THEN 'marzo'
                    WHEN 4 THEN 'abril'
                    WHEN 5 THEN 'mayo'
                    WHEN 6 THEN 'junio'
                    WHEN 7 THEN 'julio'
                    WHEN 8 THEN 'agosto'
                    WHEN 9 THEN 'septiembre'
                    WHEN 10 THEN 'octubre'
                    WHEN 11 THEN 'noviembre'
                    WHEN 12 THEN 'diciembre'
                    ELSE 'sin_mes'
                END AS mes_nombre,
                'QuickBooks mensual'::text AS agencia,
                'HISTORICO_MENSUAL'::text AS cliente,
                COALESCE(NULLIF(TRIM(familia), ''), 'SIN_FAMILIA') AS familia,
                COALESCE(NULLIF(TRIM(producto), ''), 'SIN_PRODUCTO') AS producto,
                cantidad::numeric AS cantidad,
                ventas::numeric AS venta_neta,
                COALESCE(recuento_cliente, 0)::integer AS transacciones,
                'Historico mensual ventas Econespecias'::text AS fuente_dato
            FROM silver.ventas_econespecias_mensual_clean h
            WHERE periodo IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1
                  FROM gold_periods gp
                  WHERE gp.anio = h.anio
                    AND gp.mes = EXTRACT(MONTH FROM h.periodo)::int
              )
        )
        SELECT *
        FROM gold_base
        UNION ALL
        SELECT *
        FROM historico_mensual
        ORDER BY fecha DESC, venta_neta DESC, cliente
    """,
}


def get_resumen_ejecutivo_kronos() -> pd.DataFrame:
    return load_data(QUERIES['resumen_ejecutivo_kronos'])


def get_kpi_ventas() -> pd.DataFrame:
    return load_data(QUERIES['kpi_ventas'])


def get_kpi_ventas_detalle() -> pd.DataFrame:
    return load_data(QUERIES['kpis_ventas_detalle'])


def get_alertas(solo_activas: bool = False) -> pd.DataFrame:
    query = QUERIES['alertas_activas'] if solo_activas else QUERIES['alertas']
    return load_data(query)


def get_combinaciones() -> pd.DataFrame:
    columnas = [
        'antecedente',
        'consecuente',
        'soporte',
        'confianza',
        'lift',
        'fuerza_asociacion',
        'recomendacion',
    ]
    df = load_data(QUERIES['combinaciones'])
    if df is None or len(df.columns) == 0:
        return pd.DataFrame(columns=columnas)
    for columna in columnas:
        if columna not in df.columns:
            df[columna] = None
    return df[columnas]


def get_predicciones() -> pd.DataFrame:
    df = load_data(QUERIES['predicciones_v2'])
    if df is not None and len(df) > 0:
        return df
    return load_data(QUERIES['predicciones_legacy'])


def get_productos_estacionales_forecasting() -> pd.DataFrame:
    return load_data(QUERIES['productos_estacionales_forecasting'])


def get_quickbooks_indicadores_comerciales() -> pd.DataFrame:
    return load_data(QUERIES['quickbooks_indicadores_comerciales'])
