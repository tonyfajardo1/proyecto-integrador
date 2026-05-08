"""
Pagina: Causas de Desviaciones en Produccion
Tecnica: Random Forest + Decision Tree
Pregunta: Que patrones de produccion explican las desviaciones plan vs real?
"""
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from database import load_data
from config import COLORS


def get_factores_desviacion():
    """Obtiene los factores que causan desviaciones"""
    query = """
    SELECT ranking, factor, importancia, interpretacion
    FROM gold.factores_desviacion
    ORDER BY ranking
    """
    return load_data(query)


def get_predicciones_desviacion():
    """Obtiene las predicciones de desviacion por orden"""
    query = """
    SELECT
        idsales, fecha, cliente, tipo_producto, linea_producto,
        items_planificados, qty_planificada, qty_despachada,
        desviacion_porcentual, tasa_cumplimiento, tipo_desviacion,
        prob_desviacion, nivel_riesgo, dia_semana, mes
    FROM gold.predicciones_desviacion
    ORDER BY prob_desviacion DESC
    """
    return load_data(query)


def get_metricas_modelo():
    """Obtiene las metricas del modelo"""
    query = """
    SELECT metrica, valor, tipo
    FROM gold.metricas_modelo_desviacion
    """
    return load_data(query)


def render():
    """Renderiza la pagina de causas de desviaciones"""
    st.title("Causas de Desviaciones en Produccion")

    # =========================================================================
    # EXPLICACION DE LA PAGINA
    # =========================================================================
    st.info("""
    **Fuente de Datos:** QuickBooks (Sistema de produccion de la Matriz CONDIMENSA)

    **Tipo de Datos:** Ordenes de produccion con cantidades planificadas vs despachadas

    **Tecnica de Data Mining:** Random Forest (Clasificacion + Regresion) + Decision Tree

    **Pregunta de Negocio:** Que patrones de produccion explican las desviaciones plan vs real?

    **Objetivo:** Identificar los FACTORES que causan que la produccion real difiera de la planificada.
    """)

    try:
        # Cargar datos
        df_factores = get_factores_desviacion()
        df_predicciones = get_predicciones_desviacion()
        df_metricas = get_metricas_modelo()

        if df_factores is None or len(df_factores) == 0:
            st.warning("No hay datos de factores. Ejecuta el pipeline dm_analisis_desviaciones primero.")
            return

        st.markdown("---")

        # =====================================================================
        # SECCION 1: METRICAS PRINCIPALES
        # =====================================================================
        st.subheader("1. Resumen del Analisis")
        st.caption("""
        **Que muestra:** Estadisticas generales del analisis de desviaciones en produccion.
        El modelo evalua cada orden de produccion para predecir su riesgo de desviacion.
        """)

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            total_ordenes = len(df_predicciones) if df_predicciones is not None else 0
            st.metric("Ordenes Analizadas", f"{total_ordenes:,}")

        with col2:
            if df_predicciones is not None:
                alto_riesgo = len(df_predicciones[df_predicciones['nivel_riesgo'] == 'ALTO'])
                st.metric("Riesgo ALTO", f"{alto_riesgo:,}",
                         delta=f"{alto_riesgo/total_ordenes*100:.1f}%" if total_ordenes > 0 else "0%")
            else:
                st.metric("Riesgo ALTO", "0")

        with col3:
            if df_metricas is not None:
                accuracy = df_metricas[df_metricas['metrica'] == 'accuracy']['valor'].values
                if len(accuracy) > 0:
                    st.metric("Accuracy Modelo", f"{accuracy[0]*100:.1f}%")
                else:
                    st.metric("Accuracy Modelo", "N/A")
            else:
                st.metric("Accuracy Modelo", "N/A")

        with col4:
            if df_predicciones is not None:
                desv_promedio = df_predicciones['desviacion_porcentual'].mean()
                st.metric("Desviacion Promedio", f"{desv_promedio:.1f}%")
            else:
                st.metric("Desviacion Promedio", "N/A")

        st.markdown("---")

        # =====================================================================
        # SECCION 2: FACTORES QUE CAUSAN DESVIACIONES
        # =====================================================================
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("2. Factores que Causan Desviaciones")
            st.caption("""
            **Que muestra:** Variables que el modelo identifica como mas importantes para predecir desviaciones.

            **Como interpretar:** La barra mas larga indica el factor con mayor influencia en las desviaciones.
            El Random Forest calcula esto midiendo cuanto reduce el error cada variable.

            **Feature Importance:** Porcentaje de importancia relativa de cada variable.
            """)

            # Grafico de barras de importancia
            fig = go.Figure(go.Bar(
                y=df_factores['factor'],
                x=df_factores['importancia'],
                orientation='h',
                marker_color=COLORS['primary'],
                text=[f"{x:.3f}" for x in df_factores['importancia']],
                textposition='outside'
            ))
            fig.update_layout(
                height=400,
                plot_bgcolor='white',
                xaxis_title="Importancia",
                yaxis_title="Factor",
                yaxis=dict(autorange="reversed")
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.subheader("3. Interpretacion de Factores")
            st.caption("""
            **Que muestra:** Explicacion en lenguaje de negocio de cada factor identificado.

            **Como usar esta informacion:** Priorizar acciones correctivas en los factores de mayor importancia.
            """)

            for _, row in df_factores.head(5).iterrows():
                importancia_pct = row['importancia'] * 100
                color = "red" if importancia_pct > 15 else "orange" if importancia_pct > 10 else "green"

                st.markdown(f"""
                **{row['ranking']}. {row['factor']}** ({importancia_pct:.1f}%)

                {row['interpretacion']}

                ---
                """)

        st.markdown("---")

        # =====================================================================
        # SECCION 4: DISTRIBUCION DE RIESGO
        # =====================================================================
        if df_predicciones is not None and len(df_predicciones) > 0:
            col1, col2 = st.columns(2)

            with col1:
                st.subheader("4. Distribucion por Nivel de Riesgo")
                st.caption("""
                **Que muestra:** Proporcion de ordenes segun su probabilidad de desviacion.

                **Clasificacion:**
                - ALTO: Probabilidad > 70% de tener desviacion significativa
                - MEDIO: Probabilidad 30-70%
                - BAJO: Probabilidad < 30%
                """)

                riesgo_counts = df_predicciones['nivel_riesgo'].value_counts()

                fig = go.Figure(go.Pie(
                    labels=riesgo_counts.index,
                    values=riesgo_counts.values,
                    hole=0.5,
                    marker_colors=[COLORS['danger'], COLORS['warning'], COLORS['success']],
                    textinfo='label+percent+value'
                ))
                fig.update_layout(height=350, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                st.subheader("5. Desviacion por Tipo de Producto")
                st.caption("""
                **Que muestra:** Desviacion promedio agrupada por tipo de producto.

                **Como interpretar:** Tipos de producto con barras mas altas tienen mayor
                tendencia a desviaciones. Esto puede indicar problemas en la planificacion
                o ejecucion especificos de ese tipo.
                """)

                df_tipo = df_predicciones.groupby('tipo_producto').agg({
                    'desviacion_porcentual': 'mean',
                    'idsales': 'count'
                }).reset_index()
                df_tipo.columns = ['Tipo', 'Desviacion Promedio', 'Ordenes']

                fig = go.Figure(go.Bar(
                    x=df_tipo['Tipo'],
                    y=df_tipo['Desviacion Promedio'],
                    marker_color=[COLORS['primary'], COLORS['accent'], COLORS['secondary']],
                    text=[f"{x:.1f}%" for x in df_tipo['Desviacion Promedio']],
                    textposition='outside'
                ))
                fig.update_layout(
                    height=350,
                    plot_bgcolor='white',
                    yaxis_title="Desviacion Promedio (%)"
                )
                st.plotly_chart(fig, use_container_width=True)

            st.markdown("---")

            # Desviacion por dia de semana
            st.subheader("Desviacion por Dia de la Semana")

            dias = ['Lunes', 'Martes', 'Miercoles', 'Jueves', 'Viernes', 'Sabado', 'Domingo']
            df_dia = df_predicciones.groupby('dia_semana')['desviacion_porcentual'].mean().reset_index()
            df_dia['dia_nombre'] = df_dia['dia_semana'].apply(lambda x: dias[int(x)] if x < 7 else f'Dia {x}')

            fig = go.Figure(go.Bar(
                x=df_dia['dia_nombre'],
                y=df_dia['desviacion_porcentual'],
                marker_color=[COLORS['danger'] if x > 15 else COLORS['warning'] if x > 10 else COLORS['success']
                             for x in df_dia['desviacion_porcentual']],
                text=[f"{x:.1f}%" for x in df_dia['desviacion_porcentual']],
                textposition='outside'
            ))
            fig.add_hline(y=10, line_dash="dash", line_color="orange", annotation_text="Umbral 10%")
            fig.update_layout(
                height=300,
                plot_bgcolor='white',
                yaxis_title="Desviacion Promedio (%)",
                xaxis_title="Dia de la Semana"
            )
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")

        # =====================================================================
        # METRICAS DEL MODELO
        # =====================================================================
        st.subheader("Rendimiento del Modelo")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("""
            ### Metricas de Clasificacion

            El modelo predice si una orden tendra desviacion significativa (>10%).

            | Metrica | Descripcion |
            |---------|-------------|
            | **Accuracy** | Porcentaje de predicciones correctas |
            | **Precision** | De las predichas con desviacion, cuantas realmente tienen |
            | **Recall** | De las que tienen desviacion, cuantas detectamos |
            | **F1-Score** | Balance entre precision y recall |
            """)

        with col2:
            if df_metricas is not None and len(df_metricas) > 0:
                # Filtrar metricas de clasificacion
                metricas_clf = df_metricas[df_metricas['tipo'] == 'clasificacion']

                if len(metricas_clf) > 0:
                    fig = go.Figure(go.Bar(
                        x=metricas_clf['metrica'],
                        y=metricas_clf['valor'] * 100,
                        marker_color=COLORS['success'],
                        text=[f"{v*100:.1f}%" for v in metricas_clf['valor']],
                        textposition='outside'
                    ))
                    fig.update_layout(
                        height=300,
                        plot_bgcolor='white',
                        yaxis_title="Porcentaje (%)",
                        yaxis_range=[0, 110]
                    )
                    st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")

        # =====================================================================
        # TABLA DE ORDENES DE ALTO RIESGO
        # =====================================================================
        st.subheader("Ordenes con Mayor Riesgo de Desviacion")

        if df_predicciones is not None and len(df_predicciones) > 0:
            # Filtrar alto riesgo
            df_alto_riesgo = df_predicciones[df_predicciones['nivel_riesgo'] == 'ALTO'].head(20)

            if len(df_alto_riesgo) > 0:
                st.dataframe(
                    df_alto_riesgo[[
                        'fecha', 'tipo_producto', 'linea_producto',
                        'items_planificados', 'prob_desviacion', 'nivel_riesgo'
                    ]].sort_values('prob_desviacion', ascending=False),
                    use_container_width=True,
                    height=400
                )
            else:
                st.success("No hay ordenes de alto riesgo actualmente.")

        st.markdown("---")

        # =====================================================================
        # CONCLUSION
        # =====================================================================
        st.subheader("Conclusion y Recomendaciones")

        if df_factores is not None and len(df_factores) > 0:
            top_3 = df_factores.head(3)

            st.success(f"""
            **Respuesta a la pregunta del profesor:**

            SI, existen patrones de produccion que explican las desviaciones. Los principales factores son:

            1. **{top_3.iloc[0]['factor']}**: {top_3.iloc[0]['interpretacion']}
            2. **{top_3.iloc[1]['factor']}**: {top_3.iloc[1]['interpretacion']}
            3. **{top_3.iloc[2]['factor']}**: {top_3.iloc[2]['interpretacion']}

            **Recomendaciones:**
            - Priorizar revision de ordenes con los factores identificados
            - Implementar controles adicionales para ordenes de alto riesgo
            - Monitorear dias/periodos con mayor desviacion historica
            """)

    except Exception as e:
        import traceback
        st.error(f"Error al cargar datos: {e}")
        st.code(traceback.format_exc())
