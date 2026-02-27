"""
Dashboard de Data Mining - CONDIMENSA
Version 3.1 - Estructura Modular

Autor: Proyecto Integrador
Fecha: Febrero 2026
"""
import streamlit as st
from config import APP_CONFIG, CSS_STYLES, PAGINAS
from database import test_connection
from pages import resumen, kpis_comerciales, alertas, combinaciones
from pages import plan_vs_real, tendencias, clustering


# =============================================================================
# CONFIGURACION DE LA APLICACION
# =============================================================================
st.set_page_config(
    page_title=APP_CONFIG['title'],
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded"
)

# Aplicar estilos CSS
st.markdown(CSS_STYLES, unsafe_allow_html=True)


# =============================================================================
# SIDEBAR - NAVEGACION
# =============================================================================
with st.sidebar:
    st.title("CONDIMENSA")
    st.caption(f"Data Mining Dashboard v{APP_CONFIG['version']}")
    st.markdown("---")

    st.markdown("### Navegacion")
    pagina = st.radio(
        "Seleccione una pagina",
        PAGINAS,
        label_visibility="collapsed"
    )

    st.markdown("---")

    st.markdown("### Cobertura del Proyecto")
    st.markdown("Requerimientos Empresa")
    st.markdown("Preguntas del Profesor")

    st.markdown("---")

    # Estado de conexion
    if test_connection():
        st.markdown("Base de datos: Conectada")
    else:
        st.markdown("Base de datos: Sin conexion")


# =============================================================================
# ENRUTAMIENTO DE PAGINAS
# =============================================================================
if pagina == "Resumen Ejecutivo":
    resumen.render()

elif pagina == "KPIs Comerciales":
    kpis_comerciales.render()

elif pagina == "Alertas Tempranas":
    alertas.render()

elif pagina == "Combinaciones Ineficientes":
    combinaciones.render()

elif pagina == "Plan vs Real Produccion":
    plan_vs_real.render()

elif pagina == "Tendencias y Evolucion":
    tendencias.render()

elif pagina == "Clustering y Segmentacion":
    clustering.render()


# =============================================================================
# FOOTER
# =============================================================================
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #7f8c8d; padding: 20px;">
    <p><strong>CONDIMENSA</strong> - Sistema de Data Mining</p>
    <p>Cumple requerimientos de Empresa | Responde preguntas del Profesor</p>
    <p>Dashboard v3.1 | Febrero 2026</p>
</div>
""", unsafe_allow_html=True)
