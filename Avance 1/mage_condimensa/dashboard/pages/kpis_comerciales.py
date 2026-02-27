"""
Pagina: KPIs Comerciales
Requerimiento Empresa
"""
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from database import get_kpi_ventas
from components import render_data_table
from config import COLORS


def render():
    """Renderiza la pagina de KPIs comerciales"""
    st.title("KPIs Comerciales")
    st.markdown("**Requerimiento Empresa:** Cumplimiento de ventas, proyecciones y analisis por marca")

    try:
        df = get_kpi_ventas()

        # Filtros
        with st.expander("Filtros", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
                agencias = st.multiselect(
                    "Centro de Costo",
                    options=sorted(df['centro_costo'].unique())
                )
            with col2:
                marcas = st.multiselect(
                    "Marca",
                    options=sorted(df['marca'].unique())
                )

        df_filtrado = df.copy()
        if agencias:
            df_filtrado = df_filtrado[df_filtrado['centro_costo'].isin(agencias)]
        if marcas:
            df_filtrado = df_filtrado[df_filtrado['marca'].isin(marcas)]

        st.markdown("---")

        # KPIs principales
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            cumpl_prom = df_filtrado['cumplimiento_meta'].mean() * 100
            st.metric("Cumplimiento Promedio", f"{cumpl_prom:.1f}%")
        with col2:
            margen = df_filtrado['margen_bruto'].mean() * 100
            st.metric("Margen Bruto Promedio", f"{margen:.1f}%")
        with col3:
            tasa = df_filtrado['tasa_devolucion'].mean() * 100
            st.metric("Tasa Devolucion", f"{tasa:.1f}%")
        with col4:
            ticket = df_filtrado['ticket_promedio'].mean()
            st.metric("Ticket Promedio", f"${ticket:.2f}")

        st.markdown("---")

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Venta Real vs Meta por Agencia")
            df_ag = df_filtrado.groupby('centro_costo').agg({
                'total_venta': 'sum',
                'meta_venta': 'sum',
                'cumplimiento_meta': 'mean'
            }).reset_index()

            fig = go.Figure()
            fig.add_trace(go.Bar(
                name='Venta Real',
                x=df_ag['centro_costo'],
                y=df_ag['total_venta'],
                marker_color=COLORS['primary']
            ))
            fig.add_trace(go.Bar(
                name='Meta',
                x=df_ag['centro_costo'],
                y=df_ag['meta_venta'],
                marker_color=COLORS['danger']
            ))
            fig.update_layout(
                barmode='group',
                height=400,
                plot_bgcolor='white',
                legend=dict(orientation="h", yanchor="bottom", y=1.02)
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.subheader("Cumplimiento por Marca (Top 10)")
            df_marca = df_filtrado.groupby('marca').agg({
                'total_venta': 'sum',
                'cumplimiento_meta': 'mean'
            }).nlargest(10, 'total_venta').reset_index()

            fig = px.bar(
                df_marca,
                x='cumplimiento_meta',
                y='marca',
                orientation='h',
                color='cumplimiento_meta',
                color_continuous_scale='RdYlGn',
                text=[f"{x*100:.0f}%" for x in df_marca['cumplimiento_meta']]
            )
            fig.update_layout(
                height=400,
                yaxis={'categoryorder': 'total ascending'},
                plot_bgcolor='white',
                coloraxis_showscale=False
            )
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")

        # Analisis adicional
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Rentabilidad por Agencia")
            df_rent = df_filtrado.groupby('centro_costo').agg({
                'rentabilidad': 'sum',
                'total_venta': 'sum'
            }).reset_index()
            df_rent['margen_pct'] = (df_rent['rentabilidad'] / df_rent['total_venta'] * 100).round(2)
            df_rent = df_rent.sort_values('rentabilidad', ascending=True)

            fig = go.Figure(go.Bar(
                y=df_rent['centro_costo'],
                x=df_rent['rentabilidad'],
                orientation='h',
                marker_color=COLORS['success'],
                text=[f"${x:,.0f}" for x in df_rent['rentabilidad']],
                textposition='outside'
            ))
            fig.update_layout(height=350, plot_bgcolor='white')
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.subheader("Distribucion de Ventas por Agencia")
            df_dist = df_filtrado.groupby('centro_costo')['total_venta'].sum().reset_index()

            fig = px.pie(
                df_dist,
                values='total_venta',
                names='centro_costo',
                hole=0.4
            )
            fig.update_layout(height=350)
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")
        st.subheader("Tabla Detallada de KPIs")
        render_data_table(
            df_filtrado,
            columns=['centro_costo', 'marca', 'total_venta', 'total_neto',
                    'rentabilidad', 'tasa_devolucion', 'cumplimiento_meta']
        )

    except Exception as e:
        st.error(f"Error al cargar datos: {e}")
