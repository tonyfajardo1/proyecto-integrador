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


# Queries predefinidas
QUERIES = {
    'kpi_ventas': "SELECT * FROM gold.kpi_ventas_comercial",
    'alertas': "SELECT * FROM gold.alertas_tempranas ORDER BY anomaly_score DESC",
    'alertas_activas': "SELECT * FROM gold.alertas_tempranas WHERE activa = true",
    'combinaciones': "SELECT * FROM gold.combinaciones_ineficientes ORDER BY score_ineficiencia DESC",
    'plan_vs_real': "SELECT * FROM gold.analisis_plan_vs_real",
    'evolucion': "SELECT * FROM gold.evolucion_temporal",
    'clusters_productos': "SELECT * FROM dm_clusters_productos",
    'anomalias_agencias': "SELECT * FROM dm_anomalias_agencias"
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
