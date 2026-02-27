"""
Pagina: Clustering y Segmentacion
Segmentacion de productos y agencias mediante algoritmos de ML
"""
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from database import get_clusters_productos, get_anomalias_agencias
from components import render_data_table
from config import COLORS


def render():
    """Renderiza la pagina de clustering y segmentacion"""
    st.title("Clustering y Segmentacion")
    st.markdown("**Segmentacion de productos y agencias mediante K-Means e Isolation Forest**")

    try:
        df_clusters = get_clusters_productos()
        df_anomalias = get_anomalias_agencias()

        st.markdown("---")

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Clusters de Productos")

            fig = px.scatter(
                df_clusters,
                x='total_ventas',
                y='tasa_devolucion',
                color='cluster_nombre',
                hover_data=['producto'],
                color_discrete_sequence=px.colors.qualitative.Set2
            )
            fig.update_layout(
                height=450,
                plot_bgcolor='white',
                xaxis_title="Total Ventas",
                yaxis_title="Tasa de Devolucion"
            )
            st.plotly_chart(fig, use_container_width=True)

            # Resumen de clusters
            st.markdown("**Resumen por Cluster:**")
            resumen = df_clusters.groupby('cluster_nombre').agg({
                'producto': 'count',
                'total_ventas': 'mean',
                'tasa_devolucion': 'mean'
            }).round(2)
            resumen.columns = ['Productos', 'Ventas Prom.', 'Tasa Dev. Prom.']
            st.dataframe(resumen, use_container_width=True)

        with col2:
            st.subheader("Anomalias por Agencia")

            colors = [COLORS['danger'] if x else COLORS['success']
                     for x in df_anomalias['es_anomalia']]

            fig = go.Figure(go.Bar(
                x=df_anomalias['agencia'],
                y=df_anomalias['ratio_devolucion'],
                marker_color=colors,
                text=[f"{x:.1f}%" for x in df_anomalias['ratio_devolucion']],
                textposition='outside'
            ))
            fig.update_layout(
                xaxis_title="Agencia",
                yaxis_title="Tasa Devolucion %",
                height=450,
                plot_bgcolor='white'
            )
            st.plotly_chart(fig, use_container_width=True)

            # Lista de anomalias
            anomalas = df_anomalias[df_anomalias['es_anomalia'] == True]
            if len(anomalas) > 0:
                st.warning(f"{len(anomalas)} agencias con comportamiento anomalo:")
                for _, row in anomalas.iterrows():
                    st.markdown(f"- **{row['agencia']}**: {row['ratio_devolucion']:.1f}% devolucion")
            else:
                st.success("Ninguna agencia presenta comportamiento anomalo")

        st.markdown("---")

        # Interpretacion de clusters
        st.subheader("Interpretacion de Clusters")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("""
            **Segmentos de Productos:**

            | Cluster | Caracteristica | Accion |
            |---------|----------------|--------|
            | Alto Vol - Baja Dev | Productos estrella | Maximizar disponibilidad |
            | Alto Vol - Alta Dev | Populares con problemas | Investigar calidad |
            | Bajo Vol - Baja Dev | Productos estables | Stock minimo |
            | Bajo Vol - Alta Dev | Productos problematicos | Evaluar discontinuacion |
            """)

        with col2:
            st.markdown("""
            **Metodologia:**

            - **K-Means**: Agrupa productos por similitud en ventas y devoluciones
            - **Isolation Forest**: Detecta agencias con comportamiento atipico
            - **Z-Score**: Identifica valores extremos en indicadores

            Los clusters permiten priorizar acciones y asignar recursos de forma eficiente.
            """)

        st.markdown("---")

        # Datos detallados
        tab1, tab2 = st.tabs(["Productos por Cluster", "Agencias Analizadas"])

        with tab1:
            cluster_sel = st.selectbox(
                "Filtrar por Cluster",
                options=['Todos'] + list(df_clusters['cluster_nombre'].unique())
            )

            if cluster_sel != 'Todos':
                df_show = df_clusters[df_clusters['cluster_nombre'] == cluster_sel]
            else:
                df_show = df_clusters

            render_data_table(df_show)

        with tab2:
            render_data_table(df_anomalias)

    except Exception as e:
        import traceback
        st.error(f"Error al cargar datos: {e}")
        st.code(traceback.format_exc())
