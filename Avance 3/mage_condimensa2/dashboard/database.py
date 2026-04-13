"""
Conexion y consultas a base de datos
"""
import streamlit as st
import pandas as pd
import psycopg2
from config import DB_CONFIG, APP_CONFIG


@st.cache_resource
def get_connection():
    """Obtiene conexion a la base de datos"""
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    return conn


@st.cache_data(ttl=APP_CONFIG['cache_ttl'])
def load_data(query: str) -> pd.DataFrame:
    """Ejecuta query y retorna DataFrame"""
    conn = get_connection()
    try:
        return pd.read_sql(query, conn)
    except Exception as exc:
        st.error(f"Error al consultar la base de datos: {exc}")
        return pd.DataFrame()


def test_connection() -> bool:
    """Verifica conexion a la base de datos"""
    try:
        conn = get_connection()
        return conn is not None
    except Exception:
        return False


def table_exists(schema: str, table: str) -> bool:
    """Verifica si una tabla existe sin romper vistas opcionales."""
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass(%s)", (f"{schema}.{table}",))
            return cur.fetchone()[0] is not None
    except Exception:
        return False


# Queries predefinidas - CONSULTAS A CAPAS SILVER Y GOLD
QUERIES = {
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
            CASE WHEN ratio_rentabilidad > 30 AND ratio_devolucion < 10 THEN 'POSITIVA'
                 WHEN ratio_devolucion >= 15 THEN 'NEGATIVA'
                 ELSE 'MIXTA' END as sentido_anomalia,
            COALESCE(razon_alerta, 'PATRON_INUSUAL') as razon_anomalia,
            COALESCE(razon_alerta, 'Comportamiento atipico detectado') as interpretacion,
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
            CASE WHEN ratio_rentabilidad > 30 AND ratio_devolucion < 10 THEN 'POSITIVA'
                 WHEN ratio_devolucion >= 15 THEN 'NEGATIVA'
                 ELSE 'MIXTA' END as sentido_anomalia,
            COALESCE(razon_alerta, 'PATRON_INUSUAL') as razon_anomalia,
            COALESCE(razon_alerta, 'Comportamiento atipico detectado') as interpretacion,
            anomaly_score
        FROM gold.anomalias_agencias
        WHERE es_anomalia = true
        ORDER BY anomaly_score ASC
    """,
    'combinaciones': """
        SELECT
            antecedente,
            consecuente,
            soporte,
            confianza,
            lift,
            COALESCE(interpretacion, CASE WHEN lift >= 2 THEN 'FUERTE' ELSE 'MODERADA' END) AS fuerza_asociacion,
            COALESCE(accion_sugerida, 'Aplicar cross-selling en punto de venta') AS recomendacion
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
            COALESCE(e.es_estacional, false) AS es_estacional,
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
            false AS es_estacional,
            ''::text AS meses_estacionales,
            razon_vigencia AS estado_producto_v3
        FROM gold.pronostico_produccion_resultado
        ORDER BY periodo_prediccion DESC, producto ASC
    """,
    'metricas_agencias': """
        SELECT * FROM gold.metricas_agencias
        ORDER BY total_venta DESC
    """,
    'metricas_productos': """
        SELECT * FROM gold.metricas_productos
        ORDER BY total_venta DESC
    """,
    'plan_vs_real': """
        SELECT
            cliente,
            SUM(qty_total_planificada) AS qty_total_planificada,
            SUM(qty_total_despachada) AS qty_total_despachada,
            SUM(desviacion_total) AS desviacion_total,
            SUM(num_ordenes) AS num_ordenes,
            CASE
                WHEN SUM(qty_total_planificada) > 0
                THEN SUM(qty_total_despachada) / SUM(qty_total_planificada)
                ELSE 0
            END AS tasa_cumplimiento
        FROM gold.kpis_produccion
        GROUP BY cliente
        ORDER BY qty_total_planificada DESC
    """,
    'evolucion': """
        SELECT
            centro_costo,
            producto,
            anio,
            mes,
            cant_venta,
            total_venta,
            total_devolucion,
            rentabilidad
        FROM gold.kpis_ventas
        ORDER BY anio, mes, centro_costo, producto
    """,
    'clusters_productos': """
        SELECT
            producto,
            tasa_devolucion,
            margen_rentabilidad,
            ticket_promedio,
            penetracion,
            total_ventas,
            cluster,
            cluster_nombre
        FROM gold.clusters_productos
        ORDER BY total_ventas DESC
    """,
    'catalogo_planificacion': """
        SELECT
            tipo_producto,
            categoria_producto,
            producto_base,
            producto,
            pipeline_id,
            fecha_ejecucion
        FROM gold.catalogo_productos_planificacion
        ORDER BY tipo_producto, categoria_producto, producto_base
    """,
    'catalogo_conflictos_ean': """
        SELECT
            ean13,
            n_nombres,
            nombres_dashboard,
            n_codigos,
            fecha_ejecucion
        FROM gold.catalogo_conflictos_ean13_v1
        ORDER BY n_nombres DESC, ean13
    """,
    'estado_producto_forecasting': """
        SELECT
            estado_producto,
            n_rows,
            n_productos,
            fecha_ejecucion
        FROM gold.forecasting_estado_producto_resumen_v1
        ORDER BY n_rows DESC
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
    'productos_inactivos_forecasting': """
        SELECT
            producto_dashboard,
            tipo_producto,
            last_active_period,
            months_since_last_active,
            razon_vigencia,
            fecha_ejecucion
        FROM gold.forecasting_productos_inactivos_v1
        ORDER BY months_since_last_active DESC, producto_dashboard
    """
}


def get_kpi_ventas() -> pd.DataFrame:
    return load_data(QUERIES['kpi_ventas'])


def get_kpi_ventas_detalle() -> pd.DataFrame:
    return load_data(QUERIES['kpis_ventas_detalle'])


def get_alertas(solo_activas: bool = False) -> pd.DataFrame:
    query = QUERIES['alertas_activas'] if solo_activas else QUERIES['alertas']
    return load_data(query)


def get_combinaciones() -> pd.DataFrame:
    df = load_data(QUERIES['combinaciones'])
    columnas = [
        'antecedente',
        'consecuente',
        'soporte',
        'confianza',
        'lift',
        'fuerza_asociacion',
        'recomendacion',
    ]
    if df is None or len(df.columns) == 0:
        return pd.DataFrame(columns=columnas)
    for c in columnas:
        if c not in df.columns:
            df[c] = None
    return df[columnas]


def get_metricas_agencias() -> pd.DataFrame:
    return load_data(QUERIES['metricas_agencias'])


def get_metricas_productos() -> pd.DataFrame:
    return load_data(QUERIES['metricas_productos'])


def get_plan_vs_real() -> pd.DataFrame:
    return load_data(QUERIES['plan_vs_real'])


def get_evolucion() -> pd.DataFrame:
    return load_data(QUERIES['evolucion'])


def get_clusters_productos() -> pd.DataFrame:
    columnas = [
        'producto',
        'tasa_devolucion',
        'margen_rentabilidad',
        'ticket_promedio',
        'penetracion',
        'total_ventas',
        'cluster',
        'cluster_nombre',
    ]
    if not table_exists('gold', 'clusters_productos'):
        return pd.DataFrame(columns=columnas)
    df = load_data(QUERIES['clusters_productos'])
    for col in columnas:
        if col not in df.columns:
            df[col] = None
    return df[columnas]


def get_predicciones() -> pd.DataFrame:
    df = load_data(QUERIES['predicciones_v2'])
    if df is not None and len(df) > 0:
        return df
    return load_data(QUERIES['predicciones_legacy'])


def get_catalogo_planificacion() -> pd.DataFrame:
    return load_data(QUERIES['catalogo_planificacion'])


def get_catalogo_conflictos_ean() -> pd.DataFrame:
    return load_data(QUERIES['catalogo_conflictos_ean'])


def get_estado_producto_forecasting() -> pd.DataFrame:
    return load_data(QUERIES['estado_producto_forecasting'])


def get_productos_estacionales_forecasting() -> pd.DataFrame:
    return load_data(QUERIES['productos_estacionales_forecasting'])


def get_productos_inactivos_forecasting() -> pd.DataFrame:
    return load_data(QUERIES['productos_inactivos_forecasting'])
