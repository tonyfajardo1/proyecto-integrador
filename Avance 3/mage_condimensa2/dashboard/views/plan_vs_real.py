"""
Pagina: Plan vs Real Produccion
Analisis de cumplimiento de produccion por cliente
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
    st.markdown("**Requerimiento:** Analizar cumplimiento de produccion planificada vs despachada")
    st.markdown("*Datos de QuickBooks - Produccion*")

    try:
        df = get_plan_vs_real()

        st.markdown("---")

        # Metricas
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            total_clientes = len(df)
            st.metric("Clientes Analizados", total_clientes)
        with col2:
            cumpl_prom = df['tasa_cumplimiento'].mean() * 100
            st.metric("Cumplimiento Promedio", f"{cumpl_prom:.1f}%")
        with col3:
            total_plan = df['qty_total_planificada'].sum()
            st.metric("Total Planificado", f"{total_plan:,.0f}")
        with col4:
            total_desp = df['qty_total_despachada'].sum()
            st.metric("Total Despachado", f"{total_desp:,.0f}")

        st.markdown("---")

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Tasa de Cumplimiento por Cliente")
            df_sorted = df.sort_values('tasa_cumplimiento', ascending=True)

            colors = [COLORS['danger'] if x < 0.8 else COLORS['warning'] if x < 1.0 else COLORS['success']
                     for x in df_sorted['tasa_cumplimiento']]

            fig = go.Figure(go.Bar(
                y=df_sorted['cliente'],
                x=df_sorted['tasa_cumplimiento'] * 100,
                orientation='h',
                marker_color=colors,
                text=[f"{x*100:.1f}%" for x in df_sorted['tasa_cumplimiento']],
                textposition='outside'
            ))
            fig.add_vline(x=100, line_dash="dash", line_color="green",
                         annotation_text="Meta 100%")
            fig.update_layout(
                xaxis_title="Tasa de Cumplimiento %",
                height=400,
                plot_bgcolor='white'
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.subheader("Plan vs Despachado")
            fig = px.scatter(
                df,
                x='qty_total_planificada',
                y='qty_total_despachada',
                size='num_ordenes',
                color='tasa_cumplimiento',
                hover_data=['cliente'],
                color_continuous_scale='RdYlGn'
            )

            # Linea de cumplimiento perfecto
            max_val = max(df['qty_total_planificada'].max(), df['qty_total_despachada'].max())
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

        # Analisis de desviacion
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Desviacion Total por Cliente")
            df_desv = df.sort_values('desviacion_total', ascending=True)

            colors = [COLORS['danger'] if x < 0 else COLORS['success']
                     for x in df_desv['desviacion_total']]

            fig = go.Figure(go.Bar(
                y=df_desv['cliente'],
                x=df_desv['desviacion_total'],
                orientation='h',
                marker_color=colors,
                text=[f"{x:,.0f}" for x in df_desv['desviacion_total']],
                textposition='outside'
            ))
            fig.add_vline(x=0, line_color="gray")
            fig.update_layout(
                xaxis_title="Desviacion (Despachado - Planificado)",
                height=400,
                plot_bgcolor='white'
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.subheader("Numero de Ordenes por Cliente")
            df_ord = df.sort_values('num_ordenes', ascending=True)

            fig = go.Figure(go.Bar(
                y=df_ord['cliente'],
                x=df_ord['num_ordenes'],
                orientation='h',
                marker_color=COLORS['accent'],
                text=[f"{x}" for x in df_ord['num_ordenes']],
                textposition='outside'
            ))
            fig.update_layout(
                xaxis_title="Numero de Ordenes",
                height=400,
                plot_bgcolor='white'
            )
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")

        # Resumen y recomendaciones
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Resumen de Produccion")

            # Clasificar clientes por cumplimiento
            alto_cumpl = len(df[df['tasa_cumplimiento'] >= 1.0])
            medio_cumpl = len(df[(df['tasa_cumplimiento'] >= 0.8) & (df['tasa_cumplimiento'] < 1.0)])
            bajo_cumpl = len(df[df['tasa_cumplimiento'] < 0.8])

            st.markdown(f"""
            **Clasificacion de Clientes:**
            - Cumplimiento >= 100%: **{alto_cumpl}** clientes
            - Cumplimiento 80-99%: **{medio_cumpl}** clientes
            - Cumplimiento < 80%: **{bajo_cumpl}** clientes

            **Totales:**
            - Total planificado: {df['qty_total_planificada'].sum():,.0f} unidades
            - Total despachado: {df['qty_total_despachada'].sum():,.0f} unidades
            - Diferencia: {df['desviacion_total'].sum():,.0f} unidades
            """)

        with col2:
            st.subheader("Recomendaciones")
            st.markdown("""
            **Acciones sugeridas:**

            1. **Clientes con bajo cumplimiento:**
               - Revisar capacidad de produccion
               - Analizar causas de incumplimiento
               - Ajustar planificacion

            2. **Clientes con sobre-cumplimiento:**
               - Validar precision de planificacion
               - Revisar procesos de estimacion

            3. **Mejora continua:**
               - Monitorear tendencias mensuales
               - Establecer alertas de desviacion
            """)

        st.markdown("---")
        st.subheader("Detalle de Produccion")
        render_data_table(df)

    except Exception as e:
        import traceback
        st.error(f"Error al cargar datos: {e}")
        st.code(traceback.format_exc())
