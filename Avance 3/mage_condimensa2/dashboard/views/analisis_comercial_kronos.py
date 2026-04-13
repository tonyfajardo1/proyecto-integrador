"""
Pagina: Analisis Comercial Kronos
Muestra KPIs de rendimiento por agencia, productos y tendencias
Fuente: Datos comerciales de Kronos
"""
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from database import load_data
from config import COLORS


def get_kpis_agencia():
    """Obtiene KPIs por agencia"""
    query = """
    SELECT agencia, total_ventas, unidades_vendidas, rentabilidad_total,
           tasa_devolucion, margen_neto, ranking_ventas, participacion_mercado,
           productos_vendidos, ticket_promedio
    FROM gold.kpis_comercial_agencia
    ORDER BY ranking_ventas
    """
    return load_data(query)


def get_kpis_producto():
    """Obtiene KPIs por producto"""
    query = """
    SELECT producto, codigo, total_ventas, unidades, rentabilidad,
           tasa_devolucion, margen_promedio, ranking_ventas, participacion,
           es_pareto_80
    FROM gold.kpis_comercial_producto
    ORDER BY ranking_ventas
    LIMIT 100
    """
    return load_data(query)


def get_kpis_mes():
    """Obtiene KPIs mensuales"""
    query = """
    SELECT mes, anio, total_ventas, unidades, rentabilidad, devoluciones, margen
    FROM gold.kpis_comercial_mes
    ORDER BY anio, mes
    """
    return load_data(query)


def render():
    """Renderiza la pagina de analisis comercial Kronos"""
    st.title("Analisis Comercial - Kronos")

    # =========================================================================
    # EXPLICACION DE LA PAGINA
    # =========================================================================
    st.info("""
    **Fuente de Datos:** KRONOS (Sistema de la Distribuidora Comercial)

    **Tipo de Datos:** Ventas tienda-a-tienda (T-a-T) de las 10 agencias a nivel nacional

    **Contexto de Negocio:** La distribuidora es parte de CONDIMENSA y se encarga de la venta
    directa a tiendas en todo el pais. A diferencia de QuickBooks (matriz), Kronos maneja un
    volumen alto de clientes (tiendas) con ventas mas pequenas pero frecuentes.

    **Pregunta de Negocio:** Como se desempenan las agencias y productos? Cuales generan mas valor?

    **Analisis incluido:**
    - KPIs de rendimiento por agencia (ranking, participacion, rentabilidad)
    - Top productos por ventas y margen
    - Analisis de Pareto (80/20) - que productos generan el 80% de las ventas
    - Productos con alta devolucion
    - Tendencias mensuales
    """)

    try:
        # Cargar datos
        df_agencia = get_kpis_agencia()
        df_producto = get_kpis_producto()
        df_mes = get_kpis_mes()

        if df_agencia is None or len(df_agencia) == 0:
            st.warning("No hay datos disponibles. Ejecuta el pipeline dm_analisis_comercial_kronos primero.")
            return

        st.markdown("---")

        # =====================================================================
        # SECCION 1: METRICAS PRINCIPALES
        # =====================================================================
        st.subheader("1. Metricas Generales de la Distribuidora")
        st.caption("""
        **Que muestra:** Indicadores consolidados de todas las agencias de la distribuidora.
        Estos son los KPIs principales para evaluar el desempeno comercial general.
        """)

        col1, col2, col3, col4 = st.columns(4)

        total_ventas = df_agencia['total_ventas'].sum()
        total_rentabilidad = df_agencia['rentabilidad_total'].sum()
        margen_promedio = df_agencia['margen_neto'].mean()
        total_agencias = len(df_agencia)

        with col1:
            st.metric("Ventas Totales", f"${total_ventas:,.0f}",
                     help="Suma de todas las ventas brutas de la distribuidora")

        with col2:
            st.metric("Rentabilidad Total", f"${total_rentabilidad:,.0f}",
                     help="Ganancia total despues de costos")

        with col3:
            st.metric("Margen Promedio", f"{margen_promedio:.1f}%",
                     help="Porcentaje promedio de rentabilidad sobre ventas")

        with col4:
            st.metric("Agencias Activas", f"{total_agencias}",
                     help="Numero de agencias con actividad comercial")

        st.markdown("---")

        # =====================================================================
        # SECCION 2: RENDIMIENTO POR AGENCIA
        # =====================================================================
        st.subheader("2. Rendimiento por Agencia")
        st.caption("""
        **Que muestra:** Comparativa del desempeno de las 10 agencias de la distribuidora.

        **Como interpretar:**
        - Grafico de barras: Ventas totales por agencia (mayor = mejor desempeno)
        - Grafico de pastel: Participacion de cada agencia en el total de ventas

        **Uso:** Identificar agencias lideres para replicar sus practicas y agencias
        con bajo rendimiento que requieren atencion.
        """)

        col1, col2 = st.columns(2)

        with col1:
            # Grafico de barras de ventas por agencia
            fig = go.Figure(go.Bar(
                x=df_agencia['agencia'],
                y=df_agencia['total_ventas'],
                marker_color=COLORS['primary'],
                text=[f"${x:,.0f}" for x in df_agencia['total_ventas']],
                textposition='outside'
            ))
            fig.update_layout(
                title="Ventas por Agencia",
                height=400,
                plot_bgcolor='white',
                xaxis_title="Agencia",
                yaxis_title="Ventas ($)"
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            # Grafico de participacion de mercado
            fig = go.Figure(go.Pie(
                labels=df_agencia['agencia'],
                values=df_agencia['participacion_mercado'],
                hole=0.4,
                textinfo='label+percent'
            ))
            fig.update_layout(
                title="Participacion de Mercado",
                height=400,
                showlegend=False
            )
            st.plotly_chart(fig, use_container_width=True)

        # Tabla de KPIs por agencia
        st.markdown("**Tabla Detallada de KPIs por Agencia:**")
        st.caption("Metricas completas incluyendo ranking, rentabilidad, margen y tasa de devolucion.")
        df_display = df_agencia[[
            'ranking_ventas', 'agencia', 'total_ventas', 'rentabilidad_total',
            'margen_neto', 'tasa_devolucion', 'productos_vendidos'
        ]].copy()
        df_display.columns = ['Ranking', 'Agencia', 'Ventas', 'Rentabilidad', 'Margen %', 'Devolucion %', 'Productos']
        df_display['Ventas'] = df_display['Ventas'].apply(lambda x: f"${x:,.2f}")
        df_display['Rentabilidad'] = df_display['Rentabilidad'].apply(lambda x: f"${x:,.2f}")
        df_display['Margen %'] = df_display['Margen %'].apply(lambda x: f"{x:.1f}%")
        df_display['Devolucion %'] = df_display['Devolucion %'].apply(lambda x: f"{x:.1f}%")

        st.dataframe(df_display, use_container_width=True, height=300)

        st.markdown("---")

        # =====================================================================
        # SECCION 3: TOP PRODUCTOS
        # =====================================================================
        st.subheader("3. Top Productos por Ventas y Margen")
        st.caption("""
        **Que muestra:** Los productos mas importantes por volumen de ventas y por rentabilidad.

        **Como interpretar:**
        - Grafico izquierdo: Top 10 productos por ventas totales
          - Barras VERDES = Productos Pareto (generan 80% de ventas)
          - Barras AZULES = Otros productos
        - Grafico derecho: Top 10 productos por margen de rentabilidad

        **Uso:** Identificar productos estrella (alta venta + alto margen) y productos
        que requieren revision de precios o costos.
        """)

        col1, col2 = st.columns(2)

        with col1:
            # Top 10 productos
            top_10 = df_producto.head(10)
            fig = go.Figure(go.Bar(
                y=top_10['producto'].apply(lambda x: x[:30] + '...' if len(str(x)) > 30 else x),
                x=top_10['total_ventas'],
                orientation='h',
                marker_color=[COLORS['success'] if p else COLORS['primary'] for p in top_10['es_pareto_80']],
                text=[f"${x:,.0f}" for x in top_10['total_ventas']],
                textposition='outside'
            ))
            fig.update_layout(
                title="Top 10 Productos (Verde = Pareto 80%)",
                height=450,
                plot_bgcolor='white',
                yaxis=dict(autorange="reversed"),
                xaxis_title="Ventas ($)"
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            # Productos con mayor margen
            top_margen = df_producto.nlargest(10, 'margen_promedio')
            fig = go.Figure(go.Bar(
                y=top_margen['producto'].apply(lambda x: x[:30] + '...' if len(str(x)) > 30 else x),
                x=top_margen['margen_promedio'],
                orientation='h',
                marker_color=COLORS['accent'],
                text=[f"{x:.1f}%" for x in top_margen['margen_promedio']],
                textposition='outside'
            ))
            fig.update_layout(
                title="Top 10 Productos por Margen",
                height=450,
                plot_bgcolor='white',
                yaxis=dict(autorange="reversed"),
                xaxis_title="Margen (%)"
            )
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")

        # =====================================================================
        # SECCION 4: ANALISIS DE PARETO
        # =====================================================================
        st.subheader("4. Analisis de Pareto (Regla 80/20)")
        st.caption("""
        **Que muestra:** Aplicacion del Principio de Pareto al catalogo de productos.

        **Principio de Pareto:** Aproximadamente el 20% de los productos generan el 80% de las ventas.

        **Como interpretar:**
        - La curva roja muestra la participacion ACUMULADA
        - La linea horizontal en 80% marca el umbral de Pareto
        - Los productos debajo de esa linea son los mas importantes

        **Uso estrategico:**
        - Productos Pareto: Priorizar inventario, negociar mejores condiciones con proveedores
        - Resto del catalogo: Evaluar si mantener, descontinuar o promocionar
        """)

        productos_pareto = df_producto[df_producto['es_pareto_80'] == True]
        total_productos = len(df_producto)
        pct_pareto = (len(productos_pareto) / total_productos) * 100

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Productos Totales", f"{total_productos}")

        with col2:
            st.metric("Productos Pareto (80%)", f"{len(productos_pareto)}")

        with col3:
            st.metric("% del Catalogo", f"{pct_pareto:.1f}%")

        # Curva de Pareto
        df_pareto = df_producto.head(50).copy()
        df_pareto['participacion_acum'] = df_pareto['participacion'].cumsum()

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=list(range(1, len(df_pareto) + 1)),
            y=df_pareto['participacion'],
            name='Participacion Individual',
            marker_color=COLORS['primary']
        ))
        fig.add_trace(go.Scatter(
            x=list(range(1, len(df_pareto) + 1)),
            y=df_pareto['participacion_acum'],
            name='Participacion Acumulada',
            mode='lines+markers',
            line=dict(color=COLORS['danger'], width=2),
            yaxis='y2'
        ))
        fig.add_hline(y=80, line_dash="dash", line_color="red", annotation_text="80%")

        fig.update_layout(
            title="Curva de Pareto - Top 50 Productos",
            height=400,
            plot_bgcolor='white',
            xaxis_title="Ranking Producto",
            yaxis=dict(title="Participacion Individual (%)"),
            yaxis2=dict(title="Participacion Acumulada (%)", overlaying='y', side='right', range=[0, 105]),
            legend=dict(orientation="h", yanchor="bottom", y=1.02)
        )
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")

        # =====================================================================
        # SECCION 5: PRODUCTOS CON ALTA DEVOLUCION
        # =====================================================================
        st.subheader("5. Productos con Alta Devolucion (>10%)")
        st.caption("""
        **Que muestra:** Productos que superan el umbral aceptable de devoluciones (10%).

        **Como interpretar:**
        - Barras ROJAS = Tasa de devolucion del producto
        - Linea naranja = Umbral del 10% (limite aceptable)
        - Productos arriba del umbral requieren investigacion

        **Causas comunes de alta devolucion:**
        - Problemas de calidad del producto
        - Fecha de caducidad proxima
        - Danos en el transporte
        - Error en el pedido

        **Accion recomendada:** Investigar causas raiz de los productos con mayor devolucion.
        """)

        productos_devolucion = df_producto[df_producto['tasa_devolucion'] > 10].nlargest(10, 'tasa_devolucion')

        if len(productos_devolucion) > 0:
            fig = go.Figure(go.Bar(
                y=productos_devolucion['producto'].apply(lambda x: x[:30] + '...' if len(str(x)) > 30 else x),
                x=productos_devolucion['tasa_devolucion'],
                orientation='h',
                marker_color=COLORS['danger'],
                text=[f"{x:.1f}%" for x in productos_devolucion['tasa_devolucion']],
                textposition='outside'
            ))
            fig.add_vline(x=10, line_dash="dash", line_color="orange", annotation_text="Umbral 10%")
            fig.update_layout(
                height=400,
                plot_bgcolor='white',
                yaxis=dict(autorange="reversed"),
                xaxis_title="Tasa de Devolucion (%)"
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.success("No hay productos con tasa de devolucion superior al 10%")

        st.markdown("---")

        # =====================================================================
        # SECCION 6: TENDENCIA MENSUAL
        # =====================================================================
        if df_mes is not None and len(df_mes) > 0:
            st.subheader("6. Tendencia Mensual de Ventas")
            st.caption("""
            **Que muestra:** Evolucion de ventas y margen a lo largo del tiempo.

            **Como interpretar:**
            - Grafico izquierdo: Volumen de ventas por mes
            - Grafico derecho: Evolucion del margen de rentabilidad

            **Uso:** Identificar estacionalidad, tendencias de crecimiento o decrecimiento,
            y correlacion entre volumen de ventas y rentabilidad.
            """)

            col1, col2 = st.columns(2)

            with col1:
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=df_mes['mes'],
                    y=df_mes['total_ventas'],
                    name='Ventas',
                    marker_color=COLORS['primary']
                ))
                fig.update_layout(
                    title="Ventas por Mes",
                    height=300,
                    plot_bgcolor='white',
                    yaxis_title="Ventas ($)"
                )
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=df_mes['mes'],
                    y=df_mes['margen'],
                    mode='lines+markers',
                    name='Margen',
                    line=dict(color=COLORS['success'], width=3)
                ))
                fig.update_layout(
                    title="Margen por Mes",
                    height=300,
                    plot_bgcolor='white',
                    yaxis_title="Margen (%)"
                )
                st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")

        # =====================================================================
        # SECCION 7: RESUMEN EJECUTIVO
        # =====================================================================
        st.subheader("7. Resumen Ejecutivo y Conclusiones")
        st.caption("""
        **Que muestra:** Sintesis de los hallazgos principales del analisis comercial.

        **Uso:** Puntos clave para la toma de decisiones gerenciales.
        """)

        mejor_agencia = df_agencia.iloc[0]
        peor_devolucion = df_agencia.nlargest(1, 'tasa_devolucion').iloc[0]

        st.success(f"""
        **Hallazgos Principales:**

        1. **Mejor Agencia:** {mejor_agencia['agencia']} con ${mejor_agencia['total_ventas']:,.2f} en ventas
           ({mejor_agencia['participacion_mercado']:.1f}% del mercado)

        2. **Margen Promedio:** {margen_promedio:.1f}% de rentabilidad sobre ventas

        3. **Pareto:** {len(productos_pareto)} productos ({pct_pareto:.0f}% del catalogo) generan el 80% de las ventas

        4. **Atencion:** {peor_devolucion['agencia']} tiene la mayor tasa de devolucion ({peor_devolucion['tasa_devolucion']:.1f}%)
        """)

        st.markdown("---")

        # =====================================================================
        # METODOLOGIA
        # =====================================================================
        with st.expander("8. Metodologia del Analisis"):
            st.markdown("""
            ### Metodologia del Analisis Comercial

            **Fuente de Datos:**
            Los datos provienen del sistema KRONOS de la distribuidora comercial de CONDIMENSA.
            Este sistema registra las ventas tienda-a-tienda (T-a-T) realizadas por las 10 agencias
            a nivel nacional.

            **Pipeline de Datos:**
            1. **Extraccion:** Los datos crudos se cargan desde el sistema KRONOS
            2. **Transformacion:** Se calculan metricas agregadas por agencia, producto y mes
            3. **Carga:** Se almacenan en el Data Warehouse (PostgreSQL) en la capa Gold

            **Metricas Calculadas:**

            | Metrica | Formula | Descripcion |
            |---------|---------|-------------|
            | Tasa Devolucion | (Devoluciones / Ventas) * 100 | Porcentaje de productos devueltos |
            | Margen Neto | (Rentabilidad / Ventas) * 100 | Porcentaje de ganancia sobre ventas |
            | Participacion | (Ventas Agencia / Ventas Totales) * 100 | Cuota de mercado |
            | Ticket Promedio | Ventas / Unidades | Valor promedio por unidad vendida |

            **Analisis de Pareto:**
            - Se ordenan productos por ventas de mayor a menor
            - Se calcula la participacion acumulada
            - Se marcan como Pareto los productos que acumulan el 80% de las ventas

            **Actualizacion:**
            Este analisis se actualiza cada vez que se ejecuta el pipeline `dm_analisis_comercial_kronos`.
            """)

    except Exception as e:
        import traceback
        st.error(f"Error al cargar datos: {e}")
        st.code(traceback.format_exc())
