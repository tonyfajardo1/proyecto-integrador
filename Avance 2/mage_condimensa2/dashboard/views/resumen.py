"""
Pagina: Resumen Ejecutivo
Vista consolidada de las 3 preguntas analiticas
"""
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from database import get_kpi_ventas, get_kpi_ventas_detalle, get_alertas, get_combinaciones, get_predicciones
from config import COLORS


def _texto_limpio(valor, default='SIN_NOMBRE'):
    txt = str(valor).strip()
    if txt == '' or txt.lower() in {'nan', 'none', 'null'}:
        return default
    return txt


def render():
    """Renderiza la pagina de resumen ejecutivo"""
    st.title("Resumen Ejecutivo - Data Mining CONDIMENSA")

    # =========================================================================
    # EXPLICACION DE LA PAGINA
    # =========================================================================
    st.info("""
    **Dashboard de Data Mining - CONDIMENSA**

    Este dashboard responde a 3 preguntas analiticas utilizando tecnicas de Data Mining:

    1. **Cross-Selling (Apriori)**: Que productos se venden juntos?
    2. **Anomalias (Isolation Forest)**: Que agencias tienen comportamiento atipico?
    3. **Pronostico de produccion (Random Forest Regressor)**: Disponible en la vista de Predicciones.

    **Fuentes de datos:** Kronos (comercial) y QuickBooks (produccion).
    """)

    try:
        df_kpi_detalle = get_kpi_ventas_detalle()
        df_kpi = pd.DataFrame()

        if len(df_kpi_detalle) > 0:
            for col in ['total_venta', 'total_neto', 'total_devolucion', 'rentabilidad', 'cant_venta']:
                if col in df_kpi_detalle.columns:
                    df_kpi_detalle[col] = pd.to_numeric(df_kpi_detalle[col], errors='coerce').fillna(0)

            df_kpi_detalle['anio'] = pd.to_numeric(df_kpi_detalle.get('anio'), errors='coerce')
            df_kpi_detalle['mes'] = df_kpi_detalle.get('mes', '').astype(str).str.upper()

            st.subheader("Filtros de periodo")
            colf1, colf2 = st.columns(2)

            anios = sorted(df_kpi_detalle['anio'].dropna().astype(int).unique().tolist())
            with colf1:
                anio_sel = st.selectbox('Anio', ['Todos'] + anios, index=0)

            df_filtrado = df_kpi_detalle.copy()
            if anio_sel != 'Todos':
                df_filtrado = df_filtrado[df_filtrado['anio'] == int(anio_sel)]

            meses = sorted([m for m in df_filtrado['mes'].dropna().unique().tolist() if m and m != 'NAN'])
            with colf2:
                mes_sel = st.selectbox('Mes', ['Todos'] + meses, index=0)

            if mes_sel != 'Todos':
                df_filtrado = df_filtrado[df_filtrado['mes'] == mes_sel]

            if len(df_filtrado) > 0:
                df_kpi = (
                    df_filtrado.groupby('centro_costo', as_index=False)
                    .agg({
                        'total_venta': 'sum',
                        'total_neto': 'sum',
                        'total_devolucion': 'sum',
                        'rentabilidad': 'sum',
                    })
                )
                df_kpi['ticket_promedio'] = 0
                df_kpi['tasa_devolucion'] = (df_kpi['total_devolucion'] / df_kpi['total_venta'].replace(0, pd.NA) * 100).fillna(0)
                df_kpi['rentabilidad_promedio'] = (df_kpi['rentabilidad'] / df_kpi['total_neto'].replace(0, pd.NA) * 100).fillna(0)

                st.caption(f"Periodo aplicado: anio = {anio_sel}, mes = {mes_sel}.")

        if len(df_kpi) == 0:
            df_kpi = get_kpi_ventas()

        df_alertas = get_alertas()
        df_reglas = get_combinaciones()
        df_pred = get_predicciones()

        if len(df_pred) > 0:
            if 'producto_base' not in df_pred.columns:
                df_pred['producto_base'] = df_pred.get('producto', 'SIN_NOMBRE')
            if 'producto_dashboard' not in df_pred.columns:
                df_pred['producto_dashboard'] = df_pred.get('producto_base', df_pred.get('producto', 'SIN_NOMBRE'))
            if 'tipo_producto' not in df_pred.columns:
                df_pred['tipo_producto'] = 'OTRO'
            df_pred['producto'] = df_pred.get('producto', '').apply(_texto_limpio)
            df_pred['producto_base'] = df_pred.apply(
                lambda r: _texto_limpio(r.get('producto_base'), _texto_limpio(r.get('producto'))),
                axis=1,
            )
            df_pred['producto_dashboard'] = df_pred.apply(
                lambda r: _texto_limpio(r.get('producto_dashboard'), _texto_limpio(r.get('producto_base'), _texto_limpio(r.get('producto')))),
                axis=1,
            )
            df_pred['tipo_producto'] = df_pred.get('tipo_producto', 'OTRO').apply(lambda x: _texto_limpio(x, 'OTRO'))

        st.markdown("---")

        # =====================================================================
        # SECCION 1: KPIs PRINCIPALES
        # =====================================================================
        st.subheader("KPIs Principales")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            total_ventas = df_kpi['total_venta'].sum()
            st.metric("Total Ventas", f"${total_ventas:,.0f}")

        with col2:
            rentabilidad = df_kpi['rentabilidad'].sum()
            st.metric("Rentabilidad", f"${rentabilidad:,.0f}")

        with col3:
            if df_kpi['total_venta'].sum() > 0:
                tasa_dev = df_kpi['total_devolucion'].sum() / df_kpi['total_venta'].sum() * 100
            else:
                tasa_dev = 0
            st.metric("Tasa Devolucion", f"{tasa_dev:.1f}%")

        with col4:
            n_agencias = df_kpi['centro_costo'].nunique()
            st.metric("Agencias", n_agencias)

        st.markdown("---")

        # =====================================================================
        # SECCION 2: LAS 3 PREGUNTAS
        # =====================================================================
        st.subheader("Respuestas a las 3 Preguntas Analiticas")

        col1, col2, col3 = st.columns(3)

        # PREGUNTA 1: CROSS-SELLING
        with col1:
            st.markdown("### 1. Cross-Selling")
            st.caption("Tecnica: Apriori")

            if len(df_reglas) > 0:
                st.metric("Reglas Encontradas", len(df_reglas))
                st.metric("Lift Maximo", f"{df_reglas['lift'].max():.2f}")

                st.markdown("**Top 3 Asociaciones:**")
                for i, (_, row) in enumerate(df_reglas.head(3).iterrows(), 1):
                    st.markdown(f"""
                    {i}. **{row['antecedente']}** + **{row['consecuente']}**
                    - Lift: {row['lift']:.2f}
                    """)
            else:
                st.warning("Sin datos de asociaciones")

        # PREGUNTA 2: ANOMALIAS
        with col2:
            st.markdown("### 2. Anomalias")
            st.caption("Tecnica: Isolation Forest")

            if len(df_alertas) > 0:
                anomalias = df_alertas[df_alertas['es_anomalia'] == True]
                st.metric("Total Agencias", len(df_alertas))
                st.metric("Anomalias Detectadas", len(anomalias))

                if len(anomalias) > 0:
                    st.markdown("**Agencias Anomalas:**")
                    for _, row in anomalias.iterrows():
                        tipo = row.get('tipo_anomalia', 'ATIPICO')
                        if tipo == 'ALTA_DEVOLUCION':
                            st.error(f"**{row['agencia'].upper()}**: {row['ratio_devolucion']:.1f}% devoluciones")
                        elif tipo == 'ALTA_RENTABILIDAD':
                            st.success(f"**{row['agencia'].upper()}**: {row['ratio_rentabilidad']:.1f}% rentabilidad")
                        else:
                            st.warning(f"**{row['agencia'].upper()}**: Comportamiento atipico")
            else:
                st.warning("Sin datos de anomalias")

        # PREGUNTA 3: PRONOSTICO PRODUCCION
        with col3:
            st.markdown("### 3. Pronostico Produccion")
            st.caption("Tecnica: Random Forest Regressor")

            if len(df_pred) > 0:
                st.metric("Productos con pronostico", df_pred['producto'].nunique())
                st.metric("Qty recomendada total", f"{df_pred['qty_recomendada'].sum():,.0f}")

                top = df_pred.sort_values('qty_recomendada', ascending=False).head(3)
                st.markdown("**Top productos recomendados:**")
                for _, row in top.iterrows():
                    tipo = _texto_limpio(row.get('tipo_producto', 'OTRO'), 'OTRO')
                    nombre = _texto_limpio(row.get('producto_dashboard'), _texto_limpio(row.get('producto_base'), _texto_limpio(row.get('producto'))))
                    st.success(f"**[{tipo}] {nombre}** -> {row['qty_recomendada']:.0f} unidades ({row['nivel_confianza']})")
            else:
                st.warning("Sin datos de predicciones")

        st.caption("Detalle operativo de planificacion disponible en la pagina 'Predicciones'.")

        st.markdown("---")

        # =====================================================================
        # SECCION 3: GRAFICO DE VENTAS
        # =====================================================================
        st.subheader("Ventas por Agencia")

        df_ag = df_kpi.groupby('centro_costo').agg({
            'total_venta': 'sum',
            'rentabilidad': 'sum'
        }).reset_index()
        df_ag['margen_pct'] = (df_ag['rentabilidad'] / df_ag['total_venta'] * 100).round(1)
        df_ag = df_ag.sort_values('total_venta', ascending=True)

        colors = [COLORS['success'] if x > 35 else COLORS['warning'] if x > 25 else COLORS['danger']
                 for x in df_ag['margen_pct']]

        fig = go.Figure(go.Bar(
            y=df_ag['centro_costo'],
            x=df_ag['total_venta'],
            orientation='h',
            marker_color=colors,
            text=[f"${x:,.0f} ({m:.0f}%)" for x, m in zip(df_ag['total_venta'], df_ag['margen_pct'])],
            textposition='outside'
        ))
        fig.update_layout(
            xaxis_title="Total Ventas $",
            yaxis_title="",
            height=400,
            plot_bgcolor='white'
        )
        st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        import traceback
        st.error(f"Error al cargar datos: {e}")
        st.code(traceback.format_exc())
