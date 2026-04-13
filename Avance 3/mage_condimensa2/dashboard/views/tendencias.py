"""
Pagina: Tendencias y Evolucion
Requerimiento Empresa: Evolucion temporal de indicadores
"""
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from database import get_evolucion
from components import render_data_table
from config import COLORS


def render():
    """Renderiza la pagina de tendencias y evolucion"""
    st.title("Tendencias y Evolucion")
    st.markdown("**Requerimiento Empresa:** Evolucion de productos y agencias en el tiempo")

    try:
        df = get_evolucion()

        st.markdown("---")

        # Filtros
        with st.expander("Filtros", expanded=True):
            col1, col2, col3 = st.columns(3)
            with col1:
                agencias = st.multiselect(
                    "Centro de Costo",
                    options=sorted(df['centro_costo'].unique())
                )
            with col2:
                anios = st.multiselect(
                    "Anio",
                    options=sorted(df['anio'].unique()) if 'anio' in df.columns else []
                )
            with col3:
                metrica = st.selectbox(
                    "Metrica",
                    options=['total_venta', 'cant_venta', 'rentabilidad', 'total_devolucion']
                )

        df_f = df.copy()
        if agencias:
            df_f = df_f[df_f['centro_costo'].isin(agencias)]
        if anios:
            df_f = df_f[df_f['anio'].isin(anios)]

        st.markdown("---")

        # Metricas resumen
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            total = df_f[metrica].sum()
            st.metric("Total", f"${total:,.0f}" if metrica in ['total_venta', 'rentabilidad', 'total_devolucion'] else f"{total:,.0f}")
        with col2:
            promedio = df_f[metrica].mean()
            st.metric("Promedio", f"${promedio:,.0f}" if metrica in ['total_venta', 'rentabilidad', 'total_devolucion'] else f"{promedio:,.0f}")
        with col3:
            registros = len(df_f)
            st.metric("Registros", f"{registros:,}")
        with col4:
            productos = df_f['producto'].nunique()
            st.metric("Productos Unicos", productos)

        st.markdown("---")

        col1, col2 = st.columns(2)

        with col1:
            st.subheader(f"{metrica.replace('_', ' ').title()} por Agencia")
            df_ag = df_f.groupby('centro_costo')[metrica].sum().reset_index()
            df_ag = df_ag.sort_values(metrica, ascending=True)

            fig = go.Figure(go.Bar(
                y=df_ag['centro_costo'],
                x=df_ag[metrica],
                orientation='h',
                marker=dict(color=df_ag[metrica], colorscale='Blues'),
                text=[f"${x:,.0f}" if metrica in ['total_venta', 'rentabilidad'] else f"{x:,.0f}" for x in df_ag[metrica]],
                textposition='outside'
            ))
            fig.update_layout(
                height=400,
                plot_bgcolor='white',
                yaxis={'categoryorder': 'total ascending'}
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.subheader(f"Top 10 Productos por {metrica.replace('_', ' ').title()}")
            df_prod = df_f.groupby('producto')[metrica].sum().nlargest(10).reset_index()
            df_prod = df_prod.sort_values(metrica, ascending=True)

            fig = go.Figure(go.Bar(
                y=df_prod['producto'],
                x=df_prod[metrica],
                orientation='h',
                marker_color=COLORS['accent'],
                text=[f"${x:,.0f}" if metrica in ['total_venta', 'rentabilidad'] else f"{x:,.0f}" for x in df_prod[metrica]],
                textposition='outside'
            ))
            fig.update_layout(
                height=400,
                plot_bgcolor='white'
            )
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")

        # Evolucion por mes
        if 'mes' in df_f.columns:
            st.subheader("Evolucion Mensual")
            df_mes = df_f.groupby(['mes', 'centro_costo'])[metrica].sum().reset_index()

            fig = px.line(
                df_mes,
                x='mes',
                y=metrica,
                color='centro_costo',
                markers=True
            )
            fig.update_layout(
                height=400,
                plot_bgcolor='white',
                xaxis_title="Mes",
                yaxis_title=metrica.replace('_', ' ').title()
            )
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")

        # Analisis de tendencias
        st.subheader("Analisis por Agencia")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Top 5 Agencias:**")
            top_ag = df_f.groupby('centro_costo')[metrica].sum().nlargest(5)
            for ag, valor in top_ag.items():
                if metrica in ['total_venta', 'rentabilidad', 'total_devolucion']:
                    st.markdown(f"- **{ag}**: ${valor:,.0f}")
                else:
                    st.markdown(f"- **{ag}**: {valor:,.0f}")

        with col2:
            st.markdown("**Productos Mas Vendidos:**")
            top_prod = df_f.groupby('producto')['total_venta'].sum().nlargest(5)
            for prod, valor in top_prod.items():
                st.markdown(f"- {prod}: ${valor:,.0f}")

        st.markdown("---")
        st.subheader("Datos Detallados")
        render_data_table(df_f)

    except Exception as e:
        import traceback
        st.error(f"Error al cargar datos: {e}")
        st.code(traceback.format_exc())
