"""
Pagina: KPIs Comerciales
Requerimiento Empresa: Cumplimiento de ventas y analisis comercial
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
    st.markdown("**Requerimiento Empresa:** Analisis de ventas, rentabilidad y devoluciones por agencia y producto")

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
                productos = st.multiselect(
                    "Producto",
                    options=sorted(df['producto'].dropna().unique())
                )

        df_filtrado = df.copy()
        if agencias:
            df_filtrado = df_filtrado[df_filtrado['centro_costo'].isin(agencias)]
        if productos:
            df_filtrado = df_filtrado[df_filtrado['producto'].isin(productos)]

        st.markdown("---")

        # KPIs principales
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            total_venta = df_filtrado['total_venta'].sum()
            st.metric("Total Ventas", f"${total_venta:,.0f}")
        with col2:
            margen = df_filtrado['margen_bruto'].mean() * 100 if 'margen_bruto' in df_filtrado.columns else df_filtrado['prc_rentabilidad'].mean() * 100
            st.metric("Margen Bruto Promedio", f"{margen:.1f}%")
        with col3:
            tasa = df_filtrado['tasa_devolucion'].mean() * 100 if df_filtrado['tasa_devolucion'].mean() < 1 else df_filtrado['tasa_devolucion'].mean()
            st.metric("Tasa Devolucion", f"{tasa:.1f}%")
        with col4:
            ticket = df_filtrado['ticket_promedio'].mean() if 'ticket_promedio' in df_filtrado.columns else 0
            st.metric("Ticket Promedio", f"${ticket:.2f}")

        st.markdown("---")

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Ventas por Agencia")
            df_ag = df_filtrado.groupby('centro_costo').agg({
                'total_venta': 'sum',
                'total_neto': 'sum',
                'rentabilidad': 'sum'
            }).reset_index()
            df_ag = df_ag.sort_values('total_venta', ascending=True)

            fig = go.Figure()
            fig.add_trace(go.Bar(
                name='Venta Bruta',
                y=df_ag['centro_costo'],
                x=df_ag['total_venta'],
                orientation='h',
                marker_color=COLORS['primary']
            ))
            fig.add_trace(go.Bar(
                name='Venta Neta',
                y=df_ag['centro_costo'],
                x=df_ag['total_neto'],
                orientation='h',
                marker_color=COLORS['success']
            ))
            fig.update_layout(
                barmode='group',
                height=400,
                plot_bgcolor='white',
                legend=dict(orientation="h", yanchor="bottom", y=1.02)
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.subheader("Top 10 Productos por Venta")
            df_prod = df_filtrado.groupby('producto').agg({
                'total_venta': 'sum',
                'rentabilidad': 'sum'
            }).nlargest(10, 'total_venta').reset_index()
            df_prod = df_prod.sort_values('total_venta', ascending=True)

            fig = go.Figure(go.Bar(
                y=df_prod['producto'],
                x=df_prod['total_venta'],
                orientation='h',
                marker_color=COLORS['accent'],
                text=[f"${x:,.0f}" for x in df_prod['total_venta']],
                textposition='outside'
            ))
            fig.update_layout(
                height=400,
                plot_bgcolor='white'
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

        # Tasa de devolucion por agencia
        st.subheader("Tasa de Devolucion por Agencia")
        df_dev = df_filtrado.groupby('centro_costo').agg({
            'total_devolucion': 'sum',
            'total_venta': 'sum'
        }).reset_index()
        df_dev['tasa_dev_pct'] = (df_dev['total_devolucion'] / df_dev['total_venta'] * 100).round(2)
        df_dev = df_dev.sort_values('tasa_dev_pct', ascending=True)

        colors = [COLORS['danger'] if x > 10 else COLORS['warning'] if x > 5 else COLORS['success']
                 for x in df_dev['tasa_dev_pct']]

        fig = go.Figure(go.Bar(
            y=df_dev['centro_costo'],
            x=df_dev['tasa_dev_pct'],
            orientation='h',
            marker_color=colors,
            text=[f"{x:.1f}%" for x in df_dev['tasa_dev_pct']],
            textposition='outside'
        ))
        fig.add_vline(x=5, line_dash="dash", line_color="orange", annotation_text="Umbral 5%")
        fig.update_layout(height=350, plot_bgcolor='white', xaxis_title="Tasa de Devolucion %")
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")
        st.subheader("Tabla Detallada de KPIs")
        render_data_table(
            df_filtrado,
            columns=['centro_costo', 'producto', 'total_venta', 'total_neto',
                    'rentabilidad', 'tasa_devolucion', 'ticket_promedio']
        )

    except Exception as e:
        import traceback
        st.error(f"Error al cargar datos: {e}")
        st.code(traceback.format_exc())
