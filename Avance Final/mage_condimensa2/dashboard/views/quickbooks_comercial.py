"""
Pagina: Indicadores Comerciales QuickBooks
Vista comercial enfocada en ventas por fecha, cliente, familia y producto.
"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import COLORS
from database import get_quickbooks_indicadores_comerciales


def _texto_limpio(valor, default='SIN_DATO'):
    txt = str(valor).strip()
    if txt == '' or txt.lower() in {'nan', 'none', 'null'}:
        return default
    return txt


def render():
    st.title("Indicadores Comerciales - QuickBooks")

    st.info("""
    **Vista comercial QuickBooks**

    Esta pestaña resume ventas comerciales desde QuickBooks para análisis por:
    - fecha
    - cliente
    - familia
    - producto

    Cuando no existe detalle transaccional para un periodo, se completa con el
    histórico mensual de ventas Econespecias. Por eso 2024 aparece como
    histórico mensual, no como venta diaria por cliente.
    """)

    try:
        df = get_quickbooks_indicadores_comerciales()

        if df.empty:
            st.warning(
                "No hay datos en `gold.quickbooks_indicadores_comerciales`. "
                "Ejecuta `etl_gold` para poblar la pestaña comercial."
            )
            st.stop()

        df = df.copy()
        df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce')
        df['anio'] = pd.to_numeric(df['anio'], errors='coerce')
        df['mes'] = pd.to_numeric(df['mes'], errors='coerce')
        df['mes_nombre'] = df['mes_nombre'].apply(lambda x: _texto_limpio(x, 'SIN_MES'))
        df['cliente'] = df['cliente'].apply(lambda x: _texto_limpio(x, 'SIN_CLIENTE'))
        df['producto'] = df['producto'].apply(lambda x: _texto_limpio(x, 'SIN_PRODUCTO'))
        df['familia'] = df['familia'].apply(lambda x: _texto_limpio(x, 'SIN_FAMILIA'))
        df['agencia'] = df['agencia'].apply(lambda x: _texto_limpio(x, 'SIN_AGENCIA'))
        if 'fuente_dato' not in df.columns:
            df['fuente_dato'] = 'Transaccional QuickBooks'
        df['fuente_dato'] = df['fuente_dato'].apply(lambda x: _texto_limpio(x, 'SIN_FUENTE'))
        df['cantidad'] = pd.to_numeric(df['cantidad'], errors='coerce').fillna(0)
        df['venta_neta'] = pd.to_numeric(df['venta_neta'], errors='coerce').fillna(0)
        df['transacciones'] = pd.to_numeric(df['transacciones'], errors='coerce').fillna(0)

        st.subheader("Filtros comerciales")
        col1, col2, col3 = st.columns(3)

        anios = sorted(df['anio'].dropna().astype(int).unique().tolist())
        with col1:
            anio_sel = st.selectbox('Año', ['Todos'] + anios, index=0)

        df_filtrado = df.copy()
        if anio_sel != 'Todos':
            df_filtrado = df_filtrado[df_filtrado['anio'] == int(anio_sel)]

        month_order = (
            df_filtrado[['mes', 'mes_nombre']]
            .dropna()
            .drop_duplicates()
            .sort_values('mes')
        )
        meses = month_order['mes_nombre'].tolist()

        with col2:
            mes_sel = st.selectbox('Mes', ['Todos'] + meses, index=0)

        with col3:
            fuentes = sorted(df_filtrado['fuente_dato'].dropna().unique().tolist())
            fuente_sel = st.selectbox('Fuente', ['Todas'] + fuentes, index=0)

        if mes_sel != 'Todos':
            df_filtrado = df_filtrado[df_filtrado['mes_nombre'] == mes_sel]
        if fuente_sel != 'Todas':
            df_filtrado = df_filtrado[df_filtrado['fuente_dato'] == fuente_sel]

        col3, col4 = st.columns(2)
        with col3:
            familias_sel = st.multiselect(
                'Familia',
                options=sorted(df_filtrado['familia'].dropna().unique().tolist()),
            )
        with col4:
            clientes_sel = st.multiselect(
                'Clientes',
                options=sorted(df_filtrado['cliente'].dropna().unique().tolist()),
            )

        col5, col6 = st.columns(2)
        with col5:
            producto_buscar = st.text_input('Buscar producto', '')
        with col6:
            cliente_buscar = st.text_input('Buscar cliente', '')

        if familias_sel:
            df_filtrado = df_filtrado[df_filtrado['familia'].isin(familias_sel)]
        if clientes_sel:
            df_filtrado = df_filtrado[df_filtrado['cliente'].isin(clientes_sel)]
        if producto_buscar.strip():
            pattern = producto_buscar.strip().lower()
            df_filtrado = df_filtrado[df_filtrado['producto'].str.lower().str.contains(pattern, na=False)]
        if cliente_buscar.strip():
            pattern = cliente_buscar.strip().lower()
            df_filtrado = df_filtrado[df_filtrado['cliente'].str.lower().str.contains(pattern, na=False)]

        st.caption(
            f"Periodo aplicado: año = {anio_sel}, mes = {mes_sel}, fuente = {fuente_sel}. "
            f"Registros visibles = {len(df_filtrado):,}."
        )
        cobertura = (
            df.groupby('anio', as_index=False)
            .agg(
                fecha_min=('fecha', 'min'),
                fecha_max=('fecha', 'max'),
                fuentes=('fuente_dato', lambda x: ', '.join(sorted(set(x.astype(str))))),
            )
            .sort_values('anio')
        )
        with st.expander("Cobertura de datos por año", expanded=False):
            st.dataframe(cobertura, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.subheader("KPIs comerciales")
        k1, k2, k3, k4 = st.columns(4)

        total_venta = float(df_filtrado['venta_neta'].sum()) if len(df_filtrado) > 0 else 0.0
        total_qty = float(df_filtrado['cantidad'].sum()) if len(df_filtrado) > 0 else 0.0
        total_clientes = int(df_filtrado['cliente'].nunique()) if len(df_filtrado) > 0 else 0
        total_productos = int(df_filtrado['producto'].nunique()) if len(df_filtrado) > 0 else 0

        with k1:
            st.metric("Venta Neta", f"${total_venta:,.0f}")
        with k2:
            st.metric("Cantidad Vendida", f"{total_qty:,.0f}")
        with k3:
            st.metric("Clientes/Fuente", total_clientes)
        with k4:
            st.metric("Productos", total_productos)

        if len(df_filtrado) == 0:
            st.warning("No hay datos con los filtros seleccionados.")
            st.stop()

        st.markdown("---")
        c1, c2 = st.columns(2)

        with c1:
            st.subheader("Ventas por cliente")
            df_clientes = (
                df_filtrado.groupby('cliente', as_index=False)
                .agg(
                    venta_neta=('venta_neta', 'sum'),
                    cantidad=('cantidad', 'sum'),
                    transacciones=('transacciones', 'sum'),
                )
                .sort_values('venta_neta', ascending=False)
            )
            total_cliente = df_clientes['venta_neta'].sum()
            df_clientes['participacion_pct'] = (
                (df_clientes['venta_neta'] / total_cliente) * 100
            ).fillna(0)
            st.dataframe(
                df_clientes.head(50).round(2),
                use_container_width=True,
                height=420,
            )

        with c2:
            st.subheader("Familias y productos")
            df_productos = (
                df_filtrado.groupby(['familia', 'producto'], as_index=False)
                .agg(
                    venta_neta=('venta_neta', 'sum'),
                    cantidad=('cantidad', 'sum'),
                    transacciones=('transacciones', 'sum'),
                )
                .sort_values('venta_neta', ascending=False)
            )
            st.dataframe(
                df_productos.head(50).round(2),
                use_container_width=True,
                height=420,
            )

        st.markdown("---")
        g1, g2 = st.columns(2)

        with g1:
            st.subheader("Top clientes por venta")
            top_clientes = df_clientes.head(15).sort_values('venta_neta', ascending=True)
            fig = go.Figure(go.Bar(
                y=top_clientes['cliente'],
                x=top_clientes['venta_neta'],
                orientation='h',
                marker_color=COLORS['primary'],
                text=[f"${x:,.0f}" for x in top_clientes['venta_neta']],
                textposition='outside',
            ))
            fig.update_layout(
                height=420,
                xaxis_title='Venta neta',
                yaxis_title='',
                plot_bgcolor='white',
            )
            st.plotly_chart(fig, use_container_width=True)

        with g2:
            st.subheader("Top productos por venta")
            top_productos = df_productos.head(15).sort_values('venta_neta', ascending=True)
            fig = go.Figure(go.Bar(
                y=top_productos['producto'],
                x=top_productos['venta_neta'],
                orientation='h',
                marker_color=COLORS['accent'],
                text=[f"${x:,.0f}" for x in top_productos['venta_neta']],
                textposition='outside',
            ))
            fig.update_layout(
                height=420,
                xaxis_title='Venta neta',
                yaxis_title='',
                plot_bgcolor='white',
            )
            st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        import traceback
        st.error(f"Error al cargar indicadores comerciales QuickBooks: {e}")
        st.code(traceback.format_exc())
