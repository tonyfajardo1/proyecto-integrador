"""
Pagina: Pronostico mensual de produccion por producto.
Tecnica: modelo unificado (PT nuevo + PP legacy).
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from database import (
    get_predicciones,
    get_productos_estacionales_forecasting,
    get_productos_inactivos_forecasting,
)
from config import COLORS


def render():
    st.title("Pronostico Mensual de Produccion por Producto")

    st.info(
        """
        **Pregunta de negocio:** Cuanto se debe planificar producir por producto para el siguiente mes?

        **Fuente:** QuickBooks (historico de produccion).

        **Modelo:** estrategia unificada por tipo de producto.
        PT usa el modelo nuevo (LinearRegression ganador en validacion temporal) y
        PP usa el modelo anterior para continuidad operativa.
        La planificacion presentada es sugerida por modelo (sin plan humano en pantalla).
        """
    )

    try:
        df = get_predicciones()
        if len(df) == 0:
            st.warning("No hay pronosticos disponibles en tablas gold de forecasting")
            return

        if 'modelo_ganador' in df.columns and df['modelo_ganador'].notna().any():
            modelo = str(df['modelo_ganador'].dropna().iloc[0])
            st.caption(f"Modelo publicado: {modelo}")
        if 'fuente_modelo' in df.columns and df['fuente_modelo'].notna().any():
            fuentes = sorted(df['fuente_modelo'].dropna().astype(str).unique().tolist())
            st.caption(f"Fuentes activas: {', '.join(fuentes)}")

        for col in ['qty_min_recomendada', 'qty_max_recomendada', 'sugerencia_accion', 'posibles_causas']:
            if col not in df.columns:
                df[col] = None

        if 'es_vigente_operativo' not in df.columns:
            df['es_vigente_operativo'] = True
        if 'razon_vigencia' not in df.columns:
            df['razon_vigencia'] = 'VIGENTE'

        for col in ['tipo_producto', 'categoria_producto', 'producto_base', 'producto_dashboard']:
            if col not in df.columns:
                df[col] = 'OTRO'

        df['producto_base'] = df['producto_base'].astype(str).str.strip()
        df['producto'] = df['producto'].astype(str).str.strip()
        df['producto_dashboard'] = df['producto_dashboard'].astype(str).str.strip()
        df['nombre_top'] = df['producto_dashboard']
        df.loc[df['nombre_top'].isin(['', 'nan', 'None']), 'nombre_top'] = df['producto_base']
        df.loc[df['nombre_top'].isin(['', 'nan', 'None']), 'nombre_top'] = df['producto']

        # Normalizacion numerica robusta (evita errores con None/object)
        for col in [
            'qty_planificada', 'qty_fabricada', 'pronostico_qty', 'qty_recomendada',
            'qty_min_recomendada', 'qty_max_recomendada', 'rolling_std_3', 'n_ordenes'
        ]:
            if col not in df.columns:
                df[col] = 0
            df[col] = pd.to_numeric(df[col], errors='coerce')

        st.subheader("Filtro por tipo de producto")
        tipos = sorted([t for t in df['tipo_producto'].dropna().astype(str).unique().tolist() if t and t != 'nan'])
        tipo_sel = st.selectbox('Tipo', ['Todos'] + tipos, index=0)
        if tipo_sel != 'Todos':
            df = df[df['tipo_producto'] == tipo_sel].copy()

        if len(df) == 0:
            st.warning("No hay pronosticos para el tipo seleccionado")
            return

        # Vista operativa: trabajar con el ultimo periodo pronosticado
        if 'periodo_prediccion' in df.columns:
            periodo_max = df['periodo_prediccion'].dropna().max()
            if periodo_max is not None:
                df = df[df['periodo_prediccion'] == periodo_max].copy()
                st.caption(f"Mostrando ultimo periodo pronosticado: {periodo_max}")

        df_activos = df[df['es_vigente_operativo'] == True].copy()
        if len(df_activos) == 0:
            st.warning("No hay productos vigentes para planificacion en el filtro actual")
            return

        periodos_pred = sorted(df_activos['periodo_prediccion'].dropna().astype(str).unique().tolist())
        periodo_txt = periodos_pred[0] if len(periodos_pred) == 1 else f"{periodos_pred[0]} ... {periodos_pred[-1]}"
        st.caption(f"Periodo pronostico operativo: {periodo_txt}")

        df_activos['tipo_cantidad'] = df_activos['tipo_producto'].astype(str).str.upper().map({
            'PT': 'PRODUCIDA',
            'PP': 'PRODUCIDA',
        }).fillna('OBSERVADA')

        tabla = df_activos[
            [
                'producto_dashboard',
                'tipo_producto',
                'periodo',
                'periodo_prediccion',
                'qty_min_recomendada',
                'qty_recomendada',
                'qty_max_recomendada',
                'tipo_cantidad',
            ]
        ].copy()

        tabla = tabla.rename(columns={
            'producto_dashboard': 'Producto',
            'tipo_producto': 'Tipo',
            'periodo': 'Periodo base',
            'periodo_prediccion': 'Periodo pronostico',
            'qty_min_recomendada': 'Produccion minima',
            'qty_recomendada': 'Produccion recomendada',
            'qty_max_recomendada': 'Produccion maxima',
            'tipo_cantidad': 'Cantidad corresponde a',
        })

        tabla = tabla.sort_values(['Tipo', 'Producto'])

        st.subheader("1. KPIs de planificacion")
        k1, k2, k3, k4 = st.columns(4)
        with k1:
            st.metric("Productos vigentes", f"{df_activos['producto'].nunique():,}")
        with k2:
            st.metric("Pronostico total", f"{df_activos['pronostico_qty'].sum():,.0f}")
        with k3:
            st.metric("Promedio pronosticado", f"{df_activos['pronostico_qty'].mean():,.1f}")
        with k4:
            st.metric("Cantidad real total", f"{df_activos['qty_fabricada'].sum():,.0f}")

        st.markdown("---")

        st.subheader("2. Top productos (pronostico)")
        top = df_activos.sort_values('pronostico_qty', ascending=False).head(20).copy()
        fig_top = go.Figure(
            go.Bar(
                x=top['pronostico_qty'],
                y=top['nombre_top'],
                orientation='h',
                marker_color=COLORS['primary'],
                text=[f"{x:,.0f}" for x in top['pronostico_qty']],
                textposition='outside',
            )
        )
        fig_top.update_layout(height=520, xaxis_title='Pronostico', yaxis_title='Producto')
        st.plotly_chart(fig_top, use_container_width=True)

        st.markdown("---")

        st.subheader("3. Tabla de planificacion")
        st.dataframe(tabla, use_container_width=True, height=560)

        st.markdown("---")

        st.subheader("4. Productos estacionales e inactivos")
        tab_est, tab_ina = st.tabs(["Estacionales", "Inactivos"])

        with tab_est:
            df_est = get_productos_estacionales_forecasting()
            if df_est is None or len(df_est) == 0:
                st.info("No hay productos estacionales registrados en Gold para esta corrida.")
            else:
                for col in ["active_share", "total_qty_historica"]:
                    if col in df_est.columns:
                        df_est[col] = pd.to_numeric(df_est[col], errors='coerce')
                st.caption(f"Productos estacionales: {len(df_est):,}")
                st.dataframe(df_est, use_container_width=True, height=320)

        with tab_ina:
            df_ina = get_productos_inactivos_forecasting()
            if df_ina is None or len(df_ina) == 0:
                st.info("No hay productos inactivos registrados en Gold para esta corrida.")
            else:
                if 'months_since_last_active' in df_ina.columns:
                    df_ina['months_since_last_active'] = pd.to_numeric(
                        df_ina['months_since_last_active'], errors='coerce'
                    )
                st.caption(f"Productos inactivos: {len(df_ina):,}")
                st.dataframe(df_ina, use_container_width=True, height=320)

    except Exception as e:
        import traceback
        st.error(f"Error al cargar pronostico: {e}")
        st.code(traceback.format_exc())
