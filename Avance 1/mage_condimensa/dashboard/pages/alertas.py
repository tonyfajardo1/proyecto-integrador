"""
Pagina: Alertas Tempranas
Pregunta Profesor: Detectar comportamientos atipicos antes del impacto financiero
"""
import streamlit as st
import plotly.graph_objects as go
from database import get_alertas
from components import render_alert_card, render_data_table
from config import COLORS


def render():
    """Renderiza la pagina de alertas tempranas"""
    st.title("Sistema de Alertas Tempranas")
    st.markdown("**Pregunta Profesor:** Detectar comportamientos atipicos ANTES de impactar indicadores financieros")
    st.markdown("*Algoritmo: Isolation Forest + Z-Score para deteccion de anomalias*")

    try:
        df = get_alertas()

        st.markdown("---")

        # Metricas
        col1, col2, col3 = st.columns(3)
        with col1:
            criticas = len(df[df['nivel_alerta'] == 'CRITICO'])
            st.metric("Alertas CRITICAS", criticas)
        with col2:
            altas = len(df[df['nivel_alerta'] == 'ALTO'])
            st.metric("Alertas ALTAS", altas)
        with col3:
            activas = len(df[df['activa'] == True])
            st.metric("Alertas Activas", activas)

        st.markdown("---")

        col1, col2 = st.columns([2, 1])

        with col1:
            st.subheader("Anomaly Score por Entidad")

            colors = [COLORS['danger'] if x == 'CRITICO' else COLORS['warning']
                     for x in df['nivel_alerta']]

            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=df['valor_entidad'],
                y=df['anomaly_score'],
                marker_color=colors,
                text=[f"{x:.2f}" for x in df['anomaly_score']],
                textposition='outside'
            ))
            fig.add_hline(
                y=0.3,
                line_dash="dash",
                line_color="red",
                annotation_text="Umbral Critico"
            )
            fig.update_layout(
                xaxis_title="Entidad",
                yaxis_title="Anomaly Score",
                height=400,
                plot_bgcolor='white'
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.subheader("Alertas Activas")
            df_activas = df[df['activa'] == True]

            if len(df_activas) > 0:
                for _, row in df_activas.iterrows():
                    render_alert_card(
                        tipo=row['tipo_alerta'],
                        entidad=row['valor_entidad'],
                        indicador=row['indicador'],
                        score=row['anomaly_score'],
                        nivel=row['nivel_alerta'],
                        tendencia=row.get('tendencia')
                    )
            else:
                st.info("No hay alertas activas actualmente")

        st.markdown("---")

        # Analisis por tipo de alerta
        st.subheader("Distribucion por Tipo de Alerta")
        col1, col2 = st.columns(2)

        with col1:
            tipo_counts = df['tipo_alerta'].value_counts()
            fig = go.Figure(go.Pie(
                labels=tipo_counts.index,
                values=tipo_counts.values,
                hole=0.4,
                marker_colors=[COLORS['danger'], COLORS['warning'], COLORS['primary']]
            ))
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.markdown("**Interpretacion de Alertas:**")
            st.markdown("""
            - **DEVOLUCION_ALTA**: Tasa de devolucion significativamente superior al promedio
            - **RENTABILIDAD_BAJA**: Margen por debajo del umbral esperado
            - **COMPORTAMIENTO_ATIPICO**: Patron detectado por Isolation Forest
            """)

            st.markdown("**Acciones Recomendadas:**")
            st.markdown("""
            1. Revisar operaciones de las entidades alertadas
            2. Analizar causas raiz de las desviaciones
            3. Implementar medidas correctivas inmediatas
            """)

        st.markdown("---")
        st.subheader("Detalle de Todas las Alertas")
        render_data_table(df)

    except Exception as e:
        import traceback
        st.error(f"Error al cargar datos: {e}")
        st.code(traceback.format_exc())
