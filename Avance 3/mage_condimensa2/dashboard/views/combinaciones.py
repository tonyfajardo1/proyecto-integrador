"""
Pagina: Reglas de Asociacion (Cross-Selling)
Tecnica: Apriori
Pregunta 1: Que productos se venden juntos?
"""
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from database import get_combinaciones
from config import COLORS


def render():
    """Renderiza la pagina de reglas de asociacion con Apriori"""
    st.title("Cross-Selling - Reglas de Asociacion (Apriori)")

    # =========================================================================
    # EXPLICACION DE LA PAGINA
    # =========================================================================
    st.info("""
    **Pregunta 1:** Que productos tienden a venderse juntos?

    **Fuente de Datos:** Silver transaccional (`silver.apriori_transacciones`) construido desde QuickBooks.

    **Tecnica de Data Mining:** Apriori (Reglas de Asociacion)

    **Objetivo:** Identificar patrones de compra para estrategias de cross-selling y promociones combinadas.
    """)

    try:
        df = get_combinaciones()

        if df.empty:
            st.warning(
                "No hay reglas en `gold.reglas_asociacion`. Ejecuta primero `etl_gold` y luego `dm_reglas_asociacion`."
            )
            st.stop()

        st.markdown("---")

        # =====================================================================
        # SECCION 1: METRICAS PRINCIPALES
        # =====================================================================
        st.subheader("1. Resumen de Reglas Descubiertas")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            total_reglas = len(df)
            st.metric("Total Reglas", total_reglas)

        with col2:
            lift_max = float(df['lift'].max()) if 'lift' in df.columns and len(df) > 0 else 0
            st.metric("Lift Maximo", f"{lift_max:.2f}")

        with col3:
            conf_prom = (float(df['confianza'].mean()) * 100) if 'confianza' in df.columns and len(df) > 0 else 0
            st.metric("Confianza Promedio", f"{conf_prom:.0f}%")

        with col4:
            alto_lift = len(df[df['lift'] > 2]) if 'lift' in df.columns else 0
            st.metric("Reglas Fuertes (Lift>2)", alto_lift)

        st.markdown("---")

        # =====================================================================
        # SECCION 2: TOP REGLAS
        # =====================================================================
        st.subheader("2. Principales Reglas de Asociacion")
        st.caption("""
        **Como leer:** "Si el cliente compra X, probablemente comprara Y"

        **Lift > 2** indica asociacion fuerte y accionable para cross-selling.
        """)

        for i, (_, row) in enumerate(df.head(6).iterrows(), 1):
            lift_color = COLORS['success'] if row['lift'] > 3 else COLORS['warning'] if row['lift'] > 2 else COLORS['primary']

            st.markdown(f"""
            <div style="background-color: #f8f9fa; padding: 15px; border-radius: 8px; margin: 10px 0; border-left: 4px solid {lift_color};">
                <strong>Regla #{i} - {row['fuerza_asociacion']}</strong><br>
                <strong>SI</strong> compra: <code>{row['antecedente']}</code><br>
                <strong>ENTONCES</strong> probablemente compra: <code>{row['consecuente']}</code><br>
                <small>
                    Lift: <strong>{row['lift']:.2f}</strong> |
                    Confianza: {row['confianza']*100:.0f}% |
                    Soporte: {row['soporte']*100:.1f}%
                </small>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("---")

        # =====================================================================
        # SECCION 3: EXPLICACION DE METRICAS
        # =====================================================================
        st.subheader("3. Como Interpretar las Metricas")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown("""
            **SOPORTE**

            Frecuencia de la combinacion en los datos.

            *Ejemplo:* Soporte 15% = Esta combinacion aparece en el 15% de todas las ventas.
            """)

        with col2:
            st.markdown("""
            **CONFIANZA**

            Probabilidad de comprar B cuando ya se compro A.

            *Ejemplo:* Confianza 80% = De 100 clientes que compran A, 80 tambien compran B.
            """)

        with col3:
            st.markdown("""
            **LIFT**

            Fuerza de la asociacion comparada con el azar.

            - Lift = 1: No hay asociacion
            - Lift > 2: Asociacion FUERTE
            - Lift = 4: 4 veces mas probable que por azar
            """)

        st.markdown("---")

        # =====================================================================
        # SECCION 4: VISUALIZACIONES
        # =====================================================================
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("4. Lift por Regla")
            st.caption("La linea roja marca Lift = 2 (umbral de asociacion fuerte)")

            df_sorted = df.sort_values('lift', ascending=True)
            df_sorted['regla'] = df_sorted['antecedente'] + ' -> ' + df_sorted['consecuente']

            colors = [COLORS['success'] if x > 3 else COLORS['warning'] if x > 2 else COLORS['primary']
                     for x in df_sorted['lift']]

            fig = go.Figure(go.Bar(
                y=df_sorted['regla'],
                x=df_sorted['lift'],
                orientation='h',
                marker_color=colors,
                text=[f"{x:.2f}" for x in df_sorted['lift']],
                textposition='outside'
            ))
            fig.add_vline(x=2, line_dash="dash", line_color="red",
                         annotation_text="Lift = 2")
            fig.update_layout(
                xaxis_title="Lift",
                height=350,
                plot_bgcolor='white'
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.subheader("5. Confianza vs Lift")
            st.caption("El tamano del punto representa el soporte. Las mejores reglas estan arriba a la derecha.")

            fig = px.scatter(
                df,
                x='confianza',
                y='lift',
                size='soporte',
                hover_data=['antecedente', 'consecuente'],
                color='lift',
                color_continuous_scale='Viridis'
            )
            fig.update_layout(
                xaxis_title="Confianza",
                yaxis_title="Lift",
                height=350,
                plot_bgcolor='white'
            )
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")

        # =====================================================================
        # SECCION 5: RECOMENDACIONES
        # =====================================================================
        st.subheader("6. Recomendaciones de Negocio")

        if len(df) > 0:
            mejor_regla = df.iloc[0]
            st.success(f"""
            **Oportunidad Principal de Cross-Selling:**

            Cuando un cliente compra **{mejor_regla['antecedente']}**,
            hay un **{mejor_regla['confianza']*100:.0f}%** de probabilidad de que tambien compre
            **{mejor_regla['consecuente']}**.

            Esta asociacion es **{mejor_regla['lift']:.1f}x** mas fuerte que el azar.

            **Acciones sugeridas:**
            - Colocar estos productos cerca en el punto de venta
            - Crear promociones tipo "combo"
            - Sugerir el producto complementario en el momento de la venta
            """)

        st.markdown("---")

        # =====================================================================
        # SECCION 6: METODOLOGIA
        # =====================================================================
        with st.expander("7. Metodologia - Como funciona Apriori"):
            st.markdown("""
            ### Algoritmo Apriori

            **Que es:** Algoritmo clasico de Data Mining para descubrir asociaciones
            frecuentes en conjuntos de transacciones.

            **Como funciona:**

            1. **Itemsets frecuentes:** Identifica productos que aparecen frecuentemente juntos
            2. **Generacion de reglas:** Crea reglas "Si A entonces B"
            3. **Filtrado:** Selecciona reglas con alta confianza y lift

            **Parametros utilizados:**
            - Soporte minimo: 5%
            - Confianza minima: 30%
            - Lift minimo: 1.0

            **Por que Apriori?**
            - Algoritmo probado y confiable
            - Resultados interpretables
            - Aplicacion directa en estrategias comerciales
            """)

        st.markdown("---")

        # =====================================================================
        # SECCION 7: TABLA COMPLETA
        # =====================================================================
        st.subheader("8. Todas las Reglas de Asociacion")

        st.dataframe(
            df[['antecedente', 'consecuente', 'soporte', 'confianza', 'lift', 'fuerza_asociacion']].sort_values('lift', ascending=False),
            use_container_width=True,
            height=300
        )

    except Exception as e:
        import traceback
        st.error(f"Error al cargar datos: {e}")
        st.code(traceback.format_exc())
