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
    return psycopg2.connect(**DB_CONFIG)


@st.cache_data(ttl=APP_CONFIG['cache_ttl'])
def load_data(query: str) -> pd.DataFrame:
    """Ejecuta query y retorna DataFrame"""
    conn = get_connection()
    return pd.read_sql(query, conn)


def test_connection() -> bool:
    """Verifica conexion a la base de datos"""
    try:
        conn = get_connection()
        return conn is not None
    except Exception:
        return False


# Queries predefinidas - CONSULTAS A CAPA GOLD
# gold.kpis_ventas columns: centro_costo, producto, mes, cant_venta, total_venta, 
# cant_neto, total_neto, cant_devolucion, total_devolucion, tasa_devolucion_cant, 
# tasa_devolucion_valor, rentabilidad, prc_rentabilidad, margen_bruto
QUERIES = {
    'kpi_ventas': """
        SELECT 
            centro_costo,
            producto,
            mes,
            cant_venta,
            total_venta,
            cant_neto,
            total_neto,
            cant_devolucion,
            total_devolucion,
            tasa_devolucion_cant as tasa_devolucion,
            tasa_devolucion_valor,
            rentabilidad,
            prc_rentabilidad,
            margen_bruto,
            nivel_devolucion,
            nivel_rentabilidad
        FROM gold.kpis_ventas
        ORDER BY total_venta DESC
    """,
    'alertas': "SELECT * FROM gold.anomalias_agencias ORDER BY anomaly_score ASC",
    'alertas_activas': "SELECT * FROM gold.anomalias_agencias WHERE es_anomalia = true ORDER BY anomaly_score ASC",
    'combinaciones': "SELECT * FROM gold.reglas_asociacion ORDER BY lift DESC LIMIT 50",
    'plan_vs_real': "SELECT * FROM gold.kpis_produccion",
    'evolucion': "SELECT * FROM silver.kronos_ventas ORDER BY fecha_carga DESC",
    'clusters_productos': "SELECT * FROM gold.clusters_productos ORDER BY cluster, total_ventas DESC",
    'anomalias_agencias': "SELECT * FROM gold.anomalias_agencias ORDER BY anomaly_score ASC",
    'metricas_agencias': "SELECT * FROM gold.metricas_agencias ORDER BY total_venta DESC",
    'metricas_productos': "SELECT * FROM gold.metricas_productos ORDER BY total_venta DESC"
}


def get_kpi_ventas() -> pd.DataFrame:
    return load_data(QUERIES['kpi_ventas'])


def get_alertas(solo_activas: bool = False) -> pd.DataFrame:
    query = QUERIES['alertas_activas'] if solo_activas else QUERIES['alertas']
    return load_data(query)


def get_combinaciones() -> pd.DataFrame:
    return load_data(QUERIES['combinaciones'])


def get_plan_vs_real() -> pd.DataFrame:
    return load_data(QUERIES['plan_vs_real'])


def get_evolucion() -> pd.DataFrame:
    return load_data(QUERIES['evolucion'])


def get_clusters_productos() -> pd.DataFrame:
    return load_data(QUERIES['clusters_productos'])


def get_anomalias_agencias() -> pd.DataFrame:
    return load_data(QUERIES['anomalias_agencias'])


def get_metricas_agencias() -> pd.DataFrame:
    return load_data(QUERIES['metricas_agencias'])


def get_metricas_productos() -> pd.DataFrame:
    return load_data(QUERIES['metricas_productos'])
