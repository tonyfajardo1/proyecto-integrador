"""
Pagina: Plan vs Real Produccion
Pregunta Profesor: Existen patrones de produccion que expliquen desviaciones plan vs real
"""
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from database import get_plan_vs_real
from components import render_data_table
from config import COLORS


def render():
    """Renderiza la pagina de analisis plan vs real"""
    st.title("Analisis Plan vs Real de Produccion")
    st.markdown("**Pregunta Profesor:** Existen patrones de produccion que expliquen desviaciones plan vs real?")
    st.markdown("*Algoritmo: K-Means para clustering de comportamiento de ordenes*")

    try:
        df = get_plan_vs_real()

        st.markdown("---")

        # Metricas
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            total_ord = len(df)
            st.metric("Ordenes Analizadas", total_ord)
        with col2:
            desv_prom = df['desviacion_porcentual'].mean() * 100
            st.metric("Desviacion Promedio", f"{desv_prom:.1f}%")
        with col3:
            cumpl_alto = len(df[df['cluster_comportamiento'] == 'Cumplimiento_Alto'])
            st.metric("Cumplimiento Alto", cumpl_alto)
        with col4:
            incumpl = len(df[df['cluster_comportamiento'] == 'Incumplimiento'])
            st.metric("Incumplimientos", incumpl)

        st.markdown("---")

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Distribucion por Cluster de Comportamiento")
            cluster_counts = df['cluster_comportamiento'].value_counts()

            fig = px.pie(
                values=cluster_counts.values,
                names=cluster_counts.index,
                color_discrete_sequence=[COLORS['success'], COLORS['warning'], COLORS['danger']],
                hole=0.4
            )
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.subheader("Plan vs Despachado")
            fig = px.scatter(
                df,
                x='cantidad_planificada',
                y='cantidad_despachada',
                color='cluster_comportamiento',
                color_discrete_map={
                    'Cumplimiento_Alto': COLORS['success'],
                    'Cumplimiento_Parcial': COLORS['warning'],
                    'Incumplimiento': COLORS['danger']
                },
                hover_data=['producto', 'orden_produccion']
            )

            # Linea de cumplimiento perfecto
            max_val = max(df['cantidad_planificada'].max(), df['cantidad_despachada'].max())
            fig.add_trace(go.Scatter(
                x=[0, max_val],
                y=[0, max_val],
                mode='lines',
                name='Cumplimiento 100%',
                line=dict(dash='dash', color='gray')
            ))
            fig.update_layout(
                height=400,
                plot_bgcolor='white',
                xaxis_title="Cantidad Planificada",
                yaxis_title="Cantidad Despachada"
            )
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")

        # Analisis por cluster
        st.subheader("Analisis Detallado por Cluster")

        for cluster in df['cluster_comportamiento'].unique():
            df_c = df[df['cluster_comportamiento'] == cluster]

            with st.expander(f"{cluster} ({len(df_c)} ordenes)"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Ordenes", len(df_c))
                with col2:
                    st.metric("Desviacion Promedio", f"{df_c['desviacion_porcentual'].mean()*100:.1f}%")
                with col3:
                    st.metric("Cantidad Promedio", f"{df_c['cantidad_planificada'].mean():.0f}")

                # Grafico de desviacion
                top_desv = df_c.nlargest(10, 'desviacion_porcentual')
                fig = go.Figure(go.Bar(
                    x=top_desv['orden_produccion'].astype(str),
                    y=top_desv['desviacion_porcentual'] * 100,
                    marker_color=COLORS['warning'],
                    text=[f"{x*100:.1f}%" for x in top_desv['desviacion_porcentual']],
                    textposition='outside'
                ))
                fig.update_layout(
                    xaxis_title="Orden de Produccion",
                    yaxis_title="Desviacion %",
                    height=250,
                    plot_bgcolor='white'
                )
                st.plotly_chart(fig, use_container_width=True)

                st.dataframe(
                    df_c[['orden_produccion', 'producto', 'cantidad_planificada',
                         'cantidad_despachada', 'desviacion_porcentual']].head(10),
                    use_container_width=True
                )

        st.markdown("---")

        # Patrones identificados
        st.subheader("Patrones Identificados")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Factores de Incumplimiento:**")
            df_incumpl = df[df['cluster_comportamiento'] == 'Incumplimiento']
            if len(df_incumpl) > 0:
                avg_plan = df_incumpl['cantidad_planificada'].mean()
                avg_desp = df_incumpl['cantidad_despachada'].mean()
                st.markdown(f"""
                - Promedio planificado: {avg_plan:.0f} unidades
                - Promedio despachado: {avg_desp:.0f} unidades
                - Deficit promedio: {avg_plan - avg_desp:.0f} unidades ({(avg_plan-avg_desp)/avg_plan*100:.1f}%)
                """)

        with col2:
            st.markdown("**Recomendaciones:**")
            st.markdown("""
            1. Revisar capacidad productiva vs demanda planificada
            2. Analizar cuellos de botella en ordenes con alto incumplimiento
            3. Ajustar planificacion basada en capacidad real historica
            """)

    except Exception as e:
        st.error(f"Error al cargar datos: {e}")
