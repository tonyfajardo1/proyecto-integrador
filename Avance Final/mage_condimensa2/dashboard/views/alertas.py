"""
Pagina: Deteccion de Anomalias
Tecnica: Isolation Forest
Pregunta 2: Que agencias tienen comportamiento atipico?
"""
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from database import get_alertas
from config import COLORS


def render():
    """Renderiza la pagina de deteccion de anomalias con Isolation Forest"""
    st.title("Deteccion de Anomalias - Isolation Forest")

    # =========================================================================
    # EXPLICACION DE LA PAGINA
    # =========================================================================
    st.info("""
    **Pregunta 2:** Cuales agencias tienen comportamiento atipico que requiere atencion?

    **Fuente de Datos:** KRONOS (Metricas agregadas por agencia)

    **Tecnica de Data Mining:** Isolation Forest (Deteccion de Anomalias No Supervisada)

    **Objetivo:** Identificar agencias con comportamiento diferente al resto para investigar causas.
    """)

    try:
        df = get_alertas()

        st.markdown("---")

        # =====================================================================
        # SECCION 1: METRICAS PRINCIPALES
        # =====================================================================
        st.subheader("1. Resumen del Analisis")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            total_ag = len(df)
            st.metric("Agencias Analizadas", total_ag)

        with col2:
            anomalias = len(df[df['es_anomalia'] == True])
            st.metric("Anomalias Detectadas", anomalias,
                     delta="Requiere atencion" if anomalias > 0 else None)

        with col3:
            normales = len(df[df['es_anomalia'] == False])
            st.metric("Comportamiento Normal", normales)

        with col4:
            ratio_dev_prom = df['ratio_devolucion'].mean()
            st.metric("Devolucion Promedio", f"{ratio_dev_prom:.1f}%")

        st.markdown("---")

        # =====================================================================
        # SECCION 2: RESULTADO PRINCIPAL
        # =====================================================================
        st.subheader("2. Agencias Anomalas Detectadas")
        st.caption("""
        **Tipos de anomalia:**
        - **ALTA_DEVOLUCION**: Agencia con tasa de devolucion muy alta (requiere accion correctiva)
        - **ALTA_RENTABILIDAD**: Agencia con rentabilidad excepcional (estudiar buenas practicas)
        - **ATIPICO**: Patron inusual que requiere investigacion
        """)

        df_anomala = df[df['es_anomalia'] == True]
        df_normal = df[df['es_anomalia'] == False]

        if len(df_anomala) > 0:
            for _, row in df_anomala.iterrows():
                tipo = row.get('tipo_anomalia', 'ATIPICO')
                descripcion = row.get('descripcion', 'Comportamiento atipico detectado')

                if tipo == 'ALTA_DEVOLUCION':
                    st.error(f"""
                    ### ANOMALIA NEGATIVA - {row['agencia'].upper()}

                    | Metrica | Valor |
                    |---------|-------|
                    | **Tipo** | {tipo} |
                    | **Tasa Devolucion** | {row['ratio_devolucion']:.1f}% |
                    | **Rentabilidad** | {row['ratio_rentabilidad']:.1f}% |
                    | **Total Ventas** | ${row['total_ventas']:,.0f} |

                    **Descripcion:** {descripcion}

                    **Accion Recomendada:** Investigar causas de alta devolucion y tomar acciones correctivas.
                    """)

                elif tipo == 'ALTA_RENTABILIDAD':
                    st.success(f"""
                    ### ANOMALIA POSITIVA - {row['agencia'].upper()}

                    | Metrica | Valor |
                    |---------|-------|
                    | **Tipo** | {tipo} |
                    | **Tasa Devolucion** | {row['ratio_devolucion']:.1f}% |
                    | **Rentabilidad** | {row['ratio_rentabilidad']:.1f}% |
                    | **Total Ventas** | ${row['total_ventas']:,.0f} |

                    **Descripcion:** {descripcion}

                    **Accion Recomendada:** Estudiar las practicas de esta agencia para replicar su exito.
                    """)

                else:
                    st.warning(f"""
                    ### ANOMALIA - {row['agencia'].upper()}

                    | Metrica | Valor |
                    |---------|-------|
                    | **Tipo** | {tipo} |
                    | **Tasa Devolucion** | {row['ratio_devolucion']:.1f}% |
                    | **Rentabilidad** | {row['ratio_rentabilidad']:.1f}% |
                    | **Total Ventas** | ${row['total_ventas']:,.0f} |

                    **Descripcion:** {descripcion}
                    """)
        else:
            st.success("No se detectaron anomalias. Todas las agencias tienen comportamiento normal.")

        st.markdown("---")

        # =====================================================================
        # SECCION 3: VISUALIZACIONES
        # =====================================================================
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("3. Tasa de Devolucion por Agencia")
            st.caption("""
            Barras ROJAS = Agencias anomalas | Barras VERDES = Agencias normales
            """)

            df_sorted = df.sort_values('ratio_devolucion', ascending=True)

            colors = [COLORS['danger'] if x else COLORS['success']
                     for x in df_sorted['es_anomalia']]

            fig = go.Figure(go.Bar(
                y=df_sorted['agencia'],
                x=df_sorted['ratio_devolucion'],
                orientation='h',
                marker_color=colors,
                text=[f"{x:.1f}%" for x in df_sorted['ratio_devolucion']],
                textposition='outside'
            ))
            fig.update_layout(
                xaxis_title="Tasa de Devolucion (%)",
                height=400,
                plot_bgcolor='white'
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.subheader("4. Mapa Devolucion vs Rentabilidad")
            st.caption("""
            El tamano del circulo representa el volumen de ventas.
            Esquina superior izquierda = Baja devolucion + Alta rentabilidad (ideal).
            """)

            fig = px.scatter(
                df,
                x='ratio_devolucion',
                y='ratio_rentabilidad',
                size='total_ventas',
                color='es_anomalia',
                text='agencia',
                color_discrete_map={True: COLORS['danger'], False: COLORS['success']},
                labels={
                    'ratio_devolucion': 'Tasa Devolucion (%)',
                    'ratio_rentabilidad': 'Rentabilidad (%)',
                    'es_anomalia': 'Es Anomalia'
                }
            )
            fig.update_traces(textposition='top center')
            fig.update_layout(
                height=400,
                plot_bgcolor='white'
            )
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")

        # =====================================================================
        # SECCION 4: METODOLOGIA
        # =====================================================================
        with st.expander("5. Metodologia - Como funciona Isolation Forest"):
            st.markdown("""
            ### Algoritmo Isolation Forest

            **Que es:** Algoritmo de Machine Learning NO supervisado especializado en detectar anomalias.
            No necesita ejemplos etiquetados de "normal" vs "anomalo".

            **Como funciona:**

            1. **Construccion de arboles:** El algoritmo construye 100 arboles de decision aleatorios
               que intentan "aislar" cada punto de datos.

            2. **Medicion de aislamiento:** Los puntos anomalos requieren MENOS divisiones para
               ser aislados, resultando en caminos mas cortos en el arbol.

            3. **Variables analizadas:**
               - `tasa_devolucion`: Porcentaje de devoluciones
               - `rentabilidad_porcentual`: Margen de rentabilidad
               - `total_ventas`: Volumen de ventas
               - `ticket_promedio`: Valor promedio por transaccion

            4. **Parametros del modelo:**
               - Contaminacion: 20% (esperamos hasta 20% de anomalias)
               - Numero de arboles: 100

            **Por que Isolation Forest?**
            - Funciona bien con datos multidimensionales
            - No asume distribucion normal de los datos
            - Eficiente computacionalmente
            - Robusto ante outliers extremos
            """)

        st.markdown("---")

        # =====================================================================
        # SECCION 5: TABLA COMPLETA
        # =====================================================================
        st.subheader("6. Detalle Completo de Agencias")

        st.dataframe(
            df[['agencia', 'es_anomalia', 'tipo_anomalia', 'ratio_devolucion',
                'ratio_rentabilidad', 'total_ventas']].sort_values('ratio_devolucion', ascending=False),
            use_container_width=True,
            height=350
        )

    except Exception as e:
        import traceback
        st.error(f"Error al cargar datos: {e}")
        st.code(traceback.format_exc())
