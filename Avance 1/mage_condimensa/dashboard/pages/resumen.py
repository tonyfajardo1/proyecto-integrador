"""
Pagina: Resumen Ejecutivo
"""
import streamlit as st
import plotly.graph_objects as go
from database import get_kpi_ventas, get_alertas, get_combinaciones, get_plan_vs_real
from components import render_alert_card, create_bar_chart_horizontal
from config import COLORS


def render():
    """Renderiza la pagina de resumen ejecutivo"""
    st.title("Resumen Ejecutivo")
    st.markdown("**Vista consolidada de indicadores clave y alertas del sistema**")

    try:
        df_kpi = get_kpi_ventas()
        df_alertas = get_alertas(solo_activas=True)
        df_inef = get_combinaciones()
        df_prod = get_plan_vs_real()

        st.markdown("---")

        # KPIs principales
        col1, col2, col3, col4, col5 = st.columns(5)

        with col1:
            total_ventas = df_kpi['total_venta'].sum()
            st.metric("Total Ventas", f"${total_ventas:,.0f}")

        with col2:
            total_neto = df_kpi['total_neto'].sum()
            st.metric("Venta Neta", f"${total_neto:,.0f}")

        with col3:
            rentabilidad = df_kpi['rentabilidad'].sum()
            st.metric("Rentabilidad", f"${rentabilidad:,.0f}")

        with col4:
            if df_kpi['total_venta'].sum() > 0:
                tasa_dev = df_kpi['total_devolucion'].sum() / df_kpi['total_venta'].sum() * 100
            else:
                tasa_dev = 0
            st.metric("Tasa Devolucion", f"{tasa_dev:.1f}%")

        with col5:
            alertas_criticas = len(df_alertas[df_alertas['nivel_alerta'] == 'CRITICO'])
            st.metric("Alertas Criticas", alertas_criticas)

        st.markdown("---")

        # Graficos
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Cumplimiento de Meta por Agencia")
            df_cumpl = df_kpi.groupby('centro_costo').agg({
                'total_venta': 'sum',
                'meta_venta': 'sum'
            }).reset_index()
            df_cumpl['cumplimiento'] = df_cumpl['total_venta'] / df_cumpl['meta_venta'] * 100
            df_cumpl = df_cumpl.sort_values('cumplimiento', ascending=True)

            colors = [COLORS['danger'] if x < 80 else COLORS['warning'] if x < 100 else COLORS['success']
                     for x in df_cumpl['cumplimiento']]

            fig = go.Figure(go.Bar(
                y=df_cumpl['centro_costo'],
                x=df_cumpl['cumplimiento'],
                orientation='h',
                marker_color=colors,
                text=[f"{x:.0f}%" for x in df_cumpl['cumplimiento']],
                textposition='outside'
            ))
            fig.add_vline(x=100, line_dash="dash", line_color="green",
                         annotation_text="Meta 100%")
            fig.update_layout(
                xaxis_title="% Cumplimiento",
                yaxis_title="",
                height=400,
                plot_bgcolor='white'
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.subheader("Alertas Activas")
            if len(df_alertas) > 0:
                for _, alerta in df_alertas.iterrows():
                    render_alert_card(
                        tipo=alerta['tipo_alerta'],
                        entidad=alerta['valor_entidad'],
                        indicador=alerta['indicador'],
                        score=alerta['anomaly_score'],
                        nivel=alerta['nivel_alerta'],
                        tendencia=alerta.get('tendencia')
                    )
            else:
                st.success("No hay alertas activas en el sistema")

        st.markdown("---")

        # Resumen de analisis
        col1, col2, col3 = st.columns(3)

        with col1:
            st.subheader("Ineficiencias Detectadas")
            alto = len(df_inef[df_inef['nivel_ineficiencia'] == 'ALTO'])
            medio = len(df_inef[df_inef['nivel_ineficiencia'] == 'MEDIO'])
            st.metric("Nivel ALTO", alto)
            st.metric("Nivel MEDIO", medio)

        with col2:
            st.subheader("Produccion")
            if len(df_prod) > 0:
                cumplidos = len(df_prod[df_prod['cluster_comportamiento'] == 'Cumplimiento_Alto'])
                total_ord = len(df_prod)
                st.metric("Ordenes Analizadas", total_ord)
                st.metric("Cumplimiento Alto", f"{cumplidos} ({cumplidos/total_ord*100:.0f}%)")

        with col3:
            st.subheader("Top Marcas")
            top_marcas = df_kpi.groupby('marca')['total_venta'].sum().nlargest(3)
            for marca, valor in top_marcas.items():
                st.write(f"**{marca}**: ${valor:,.0f}")

    except Exception as e:
        st.error(f"Error al cargar datos: {e}")
