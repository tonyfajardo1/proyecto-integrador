"""
Dashboard de Data Mining - CONDIMENSA
Version 4.2 - 4 Pestanas (3 Preguntas Analiticas)

Autor: Proyecto Integrador
Fecha: Marzo 2026
"""
import streamlit as st
from config import APP_CONFIG, CSS_STYLES, PAGINAS
from database import test_connection
from views import resumen, combinaciones, alertas, predicciones


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

    st.markdown("### 3 Preguntas Analiticas")
    st.markdown("""
    1. Cross-Selling (Apriori)
    2. Anomalias (Isolation Forest)
    3. Pronostico Produccion (Random Forest Regressor)
    """)

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

elif pagina == "Cross-Selling (Apriori)":
    combinaciones.render()

elif pagina == "Anomalias (Isolation Forest)":
    alertas.render()

elif pagina == "Pronostico Produccion":
    predicciones.render()


# =============================================================================
# FOOTER
# =============================================================================
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #7f8c8d; padding: 20px;">
    <p><strong>CONDIMENSA</strong> - Sistema de Data Mining</p>
    <p>3 Preguntas Analiticas | Apriori - Isolation Forest - Pronostico Produccion</p>
    <p>Dashboard v4.2 | Marzo 2026</p>
</div>
""", unsafe_allow_html=True)
