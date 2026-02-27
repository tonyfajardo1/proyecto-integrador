"""
Pagina: Combinaciones Ineficientes
Pregunta Profesor: Que combinaciones producto-cliente-periodo estan asociadas a ineficiencias
"""
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from database import get_combinaciones
from components import render_data_table
from config import COLORS


def render():
    """Renderiza la pagina de combinaciones ineficientes"""
    st.title("Combinaciones Ineficientes")
    st.markdown("**Pregunta Profesor:** Que combinaciones producto-cliente-periodo estan asociadas a ineficiencias?")
    st.markdown("*Analisis multidimensional de factores que generan perdidas*")

    try:
        df = get_combinaciones()

        st.markdown("---")

        # Filtros
        with st.expander("Filtros", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
                nivel = st.multiselect(
                    "Nivel de Ineficiencia",
                    options=['ALTO', 'MEDIO', 'BAJO'],
                    default=['ALTO', 'MEDIO']
                )
            with col2:
                agencias = st.multiselect(
                    "Centro de Costo",
                    options=sorted(df['centro_costo'].unique())
                )

        df_f = df[df['nivel_ineficiencia'].isin(nivel)]
        if agencias:
            df_f = df_f[df_f['centro_costo'].isin(agencias)]

        st.markdown("---")

        # Metricas
        col1, col2, col3 = st.columns(3)
        with col1:
            alto = len(df_f[df_f['nivel_ineficiencia'] == 'ALTO'])
            st.metric("Ineficiencia ALTA", alto)
        with col2:
            medio = len(df_f[df_f['nivel_ineficiencia'] == 'MEDIO'])
            st.metric("Ineficiencia MEDIA", medio)
        with col3:
            score_prom = df_f['score_ineficiencia'].mean()
            st.metric("Score Promedio", f"{score_prom:.2f}")

        st.markdown("---")

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Score de Ineficiencia por Producto (Top 15)")
            top_inef = df_f.nlargest(15, 'score_ineficiencia')

            fig = go.Figure(go.Bar(
                y=top_inef['producto'],
                x=top_inef['score_ineficiencia'],
                orientation='h',
                marker=dict(
                    color=top_inef['score_ineficiencia'],
                    colorscale='RdYlGn_r'
                ),
                text=[f"{x:.2f}" for x in top_inef['score_ineficiencia']],
                textposition='outside'
            ))
            fig.update_layout(
                yaxis={'categoryorder': 'total ascending'},
                height=500,
                plot_bgcolor='white'
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.subheader("Mapa de Ineficiencia")
            fig = px.scatter(
                df_f,
                x='tasa_devolucion',
                y='margen_real',
                color='nivel_ineficiencia',
                size='score_ineficiencia',
                hover_data=['producto', 'centro_costo'],
                color_discrete_map={
                    'ALTO': COLORS['danger'],
                    'MEDIO': COLORS['warning'],
                    'BAJO': COLORS['success']
                }
            )
            fig.update_layout(
                xaxis_title="Tasa de Devolucion",
                yaxis_title="Margen Real",
                height=500,
                plot_bgcolor='white'
            )
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")

        # Analisis por agencia
        st.subheader("Ineficiencias por Centro de Costo")
        df_ag = df_f.groupby('centro_costo').agg({
            'score_ineficiencia': 'mean',
            'producto': 'count'
        }).reset_index()
        df_ag.columns = ['centro_costo', 'score_promedio', 'cantidad']
        df_ag = df_ag.sort_values('score_promedio', ascending=True)

        fig = go.Figure(go.Bar(
            y=df_ag['centro_costo'],
            x=df_ag['score_promedio'],
            orientation='h',
            marker_color=[COLORS['danger'] if x > 0.5 else COLORS['warning']
                         for x in df_ag['score_promedio']],
            text=[f"{x:.2f}" for x in df_ag['score_promedio']],
            textposition='outside'
        ))
        fig.update_layout(
            xaxis_title="Score Promedio de Ineficiencia",
            height=350,
            plot_bgcolor='white'
        )
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")
        st.subheader("Detalle de Combinaciones Ineficientes")
        render_data_table(
            df_f,
            columns=['producto', 'centro_costo', 'tasa_devolucion', 'margen_real',
                    'desviacion_margen', 'score_ineficiencia', 'nivel_ineficiencia']
        )

    except Exception as e:
        import traceback
        st.error(f"Error al cargar datos: {e}")
        st.code(traceback.format_exc())
