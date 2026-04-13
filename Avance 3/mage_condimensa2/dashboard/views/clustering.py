"""
Pagina: Clustering y Segmentacion de Productos
Tecnica: K-Means
Fuente: KRONOS (Distribuidora comercial)
"""
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from database import get_clusters_productos
from config import COLORS


def render():
    """Renderiza la pagina de clustering K-Means"""
    st.title("Segmentacion de Productos con K-Means")

    # =========================================================================
    # EXPLICACION DE LA PAGINA
    # =========================================================================
    st.info("""
    **Fuente de Datos:** KRONOS (Sistema comercial de la Distribuidora)

    **Tipo de Datos:** Caracteristicas de productos (ventas, devoluciones, rentabilidad)

    **Tecnica de Data Mining:** K-Means Clustering (Segmentacion No Supervisada)

    **Pregunta de Negocio:** Como podemos agrupar los productos para gestionar mejor el catalogo?

    **Aplicacion:** Estrategias diferenciadas por segmento, optimizacion de inventario
    """)

    try:
        df = get_clusters_productos()
        if df.empty:
            st.warning("No hay datos de clustering publicados en Gold.")
            return

        st.markdown("---")

        # =====================================================================
        # SECCION 1: METRICAS PRINCIPALES
        # =====================================================================
        st.subheader("1. Resumen de Segmentacion")
        st.caption("""
        **Que muestra:** Cantidad de productos analizados y como fueron agrupados.
        El algoritmo agrupa automaticamente productos con caracteristicas similares.
        """)

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            total_productos = len(df)
            st.metric("Total Productos", total_productos,
                     help="Productos analizados del catalogo")

        with col2:
            n_clusters = df['cluster_nombre'].nunique()
            st.metric("Segmentos Identificados", n_clusters,
                     help="Grupos homogeneos encontrados")

        with col3:
            commodities = len(df[df['cluster_nombre'] == 'COMMODITIES'])
            st.metric("COMMODITIES", commodities,
                     help="Productos con comportamiento estable")

        with col4:
            problematicos = len(df[df['cluster_nombre'] == 'PROBLEMATICOS'])
            st.metric("PROBLEMATICOS", problematicos,
                     help="Productos que requieren atencion")

        st.markdown("---")

        # =====================================================================
        # SECCION 2: VISUALIZACION PRINCIPAL
        # =====================================================================
        col1, col2 = st.columns([2, 1])

        with col1:
            st.subheader("2. Mapa de Productos por Cluster")
            st.caption("""
            **Que muestra:** Cada punto es un producto, posicionado segun sus ventas y tasa de devolucion.

            **Como interpretar:**
            - Eje X: Total de ventas del producto
            - Eje Y: Tasa de devolucion
            - Color VERDE = Cluster COMMODITIES (productos estables)
            - Color ROJO = Cluster PROBLEMATICOS (requieren atencion)
            - Tamano del punto = Ticket promedio
            """)

            fig = px.scatter(
                df,
                x='total_ventas',
                y='tasa_devolucion',
                color='cluster_nombre',
                size='ticket_promedio',
                hover_data=['producto', 'margen_rentabilidad'],
                color_discrete_map={
                    'COMMODITIES': COLORS['success'],
                    'PROBLEMATICOS': COLORS['danger']
                },
                labels={
                    'total_ventas': 'Total Ventas ($)',
                    'tasa_devolucion': 'Tasa de Devolucion (%)',
                    'cluster_nombre': 'Cluster'
                }
            )
            fig.update_layout(
                height=500,
                plot_bgcolor='white',
                legend=dict(orientation="h", yanchor="bottom", y=1.02)
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.subheader("3. Composicion")
            st.caption("Proporcion de productos en cada segmento.")

            cluster_counts = df['cluster_nombre'].value_counts()

            fig = go.Figure(go.Pie(
                labels=cluster_counts.index,
                values=cluster_counts.values,
                hole=0.5,
                marker_colors=[COLORS['success'], COLORS['danger']],
                textinfo='label+percent+value'
            ))
            fig.update_layout(height=300, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

            # Estadisticas por cluster
            st.markdown("**Estadisticas por Segmento:**")
            for cluster in df['cluster_nombre'].unique():
                df_c = df[df['cluster_nombre'] == cluster]
                with st.expander(f"{cluster} ({len(df_c)} productos)"):
                    st.write(f"- Ventas promedio: ${df_c['total_ventas'].mean():,.0f}")
                    st.write(f"- Tasa devolucion: {df_c['tasa_devolucion'].mean():.2f}%")
                    st.write(f"- Margen rentab.: {df_c['margen_rentabilidad'].mean():.2f}%")

        st.markdown("---")

        # =====================================================================
        # SECCION 3: INTERPRETACION
        # =====================================================================
        st.subheader("4. Interpretacion de Segmentos")
        st.caption("Descripcion detallada de cada cluster y acciones recomendadas.")

        col1, col2 = st.columns(2)

        with col1:
            commodities_pct = (commodities / total_productos) * 100
            st.success(f"""
            **COMMODITIES** ({commodities} productos - {commodities_pct:.1f}%)

            **Caracteristicas:**
            - Comportamiento de ventas estable
            - Tasa de devolucion dentro de lo normal
            - Buena rentabilidad

            **Acciones recomendadas:**
            - Mantener disponibilidad de inventario
            - Monitorear tendencias de ventas
            - Usar como base para cross-selling
            """)

        with col2:
            problematicos_pct = (problematicos / total_productos) * 100
            st.error(f"""
            **PROBLEMATICOS** ({problematicos} productos - {problematicos_pct:.1f}%)

            **Caracteristicas:**
            - Alta tasa de devolucion
            - Comportamiento atipico
            - Pueden afectar la rentabilidad

            **Acciones recomendadas:**
            - Investigar causas de devolucion
            - Evaluar calidad del producto
            - Considerar descontinuar si no mejora
            """)

        st.markdown("---")

        # =====================================================================
        # SECCION 4: METODOLOGIA
        # =====================================================================
        with st.expander("5. Metodologia Tecnica - Como funciona K-Means"):
            st.markdown("""
            ### Algoritmo K-Means Clustering

            **Que es:** Es un algoritmo de Machine Learning NO supervisado que agrupa datos
            en K clusters basandose en la similitud de sus caracteristicas.

            **Como funciona:**

            1. **Seleccion de K:** Se evaluo el numero optimo de clusters usando:
               - Metodo del codo (Elbow Method)
               - Silhouette Score
               - K=2 mostro la mejor separacion

            2. **Variables de entrada:**
               - `tasa_devolucion`: Porcentaje de productos devueltos
               - `margen_rentabilidad`: Porcentaje de rentabilidad
               - `ticket_promedio`: Valor promedio por venta
               - `penetracion`: Presencia en diferentes agencias

            3. **Normalizacion:** Las variables fueron estandarizadas con StandardScaler
               para evitar que variables con escalas grandes dominen el clustering.

            4. **Proceso iterativo:**
               - Se asigna cada producto al cluster mas cercano
               - Se recalculan los centroides
               - Se repite hasta convergencia

            5. **Resultado:** 2 clusters bien diferenciados

            **Por que K-Means?**
            - Algoritmo simple y eficiente
            - Facil de interpretar
            - Resultados accionables
            - Escalable a grandes conjuntos de datos
            """)

        st.markdown("---")

        # =====================================================================
        # SECCION 5: TABLA DETALLADA
        # =====================================================================
        st.subheader("6. Detalle de Productos por Segmento")
        st.caption("Lista completa de productos con su clasificacion y metricas.")

        cluster_sel = st.selectbox(
            "Filtrar por Segmento",
            options=['Todos'] + list(df['cluster_nombre'].unique())
        )

        if cluster_sel != 'Todos':
            df_show = df[df['cluster_nombre'] == cluster_sel]
        else:
            df_show = df

        st.write(f"Mostrando {len(df_show)} productos")

        st.dataframe(
            df_show[['producto', 'cluster_nombre', 'total_ventas', 'tasa_devolucion',
                    'margen_rentabilidad', 'ticket_promedio', 'penetracion']].sort_values('total_ventas', ascending=False),
            use_container_width=True,
            height=400
        )

    except Exception as e:
        import traceback
        st.error(f"Error al cargar datos: {e}")
        st.code(traceback.format_exc())
