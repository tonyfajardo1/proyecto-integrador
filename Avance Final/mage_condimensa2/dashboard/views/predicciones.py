"""
Pagina: Pronostico mensual de produccion por producto.
Tecnica: Forecasting V3 QuickBooks.
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from database import (
    get_predicciones,
    get_productos_estacionales_forecasting,
)
from config import COLORS

ESTADO_OPERATIVO_LABEL = 'Activo regular'
ESTADO_ESTACIONAL_LABEL = 'Estacional'
ESTADO_INACTIVO_LABEL = 'Inactivo'
FILTRO_OPERATIVOS_LABEL = 'Operativos'
FILTRO_TODOS_LABEL = 'Todos'

CONFIANZA_ALTA_LABEL = 'Alta'
CONFIANZA_MEDIA_LABEL = 'Media'
CONFIANZA_BAJA_LABEL = 'Baja'
CONFIANZA_NO_APLICA_LABEL = 'No aplica (inactivo)'


def _normalizar_confianza_ui(series: pd.Series) -> pd.Series:
    return (
        series.fillna('')
        .astype(str)
        .str.strip()
        .str.lower()
        .map({
            'alta': CONFIANZA_ALTA_LABEL,
            'media': CONFIANZA_MEDIA_LABEL,
            'baja': CONFIANZA_BAJA_LABEL,
            'no_aplica': CONFIANZA_NO_APLICA_LABEL,
            'sin_confianza': 'Sin confianza',
        })
        .fillna(series.fillna('').astype(str))
    )


def _filtrar_periodo_operativo(df: pd.DataFrame) -> pd.DataFrame:
    if 'periodo_prediccion' not in df.columns or len(df) == 0:
        return df

    out = df.copy()
    out['_periodo_prediccion_dt'] = pd.to_datetime(out['periodo_prediccion'], errors='coerce')
    periodos = sorted(out['_periodo_prediccion_dt'].dropna().dt.date.unique().tolist())
    if not periodos:
        return out.drop(columns=['_periodo_prediccion_dt'])

    opciones = ['Proximo mes por tipo'] + [p.isoformat() for p in periodos]
    periodo_sel = st.selectbox('Periodo pronostico', opciones, index=0)

    if periodo_sel == 'Proximo mes por tipo':
        tipo_col = 'tipo_producto' if 'tipo_producto' in out.columns else 'source_type'
        min_por_tipo = out.groupby(tipo_col)['_periodo_prediccion_dt'].transform('min')
        out = out[out['_periodo_prediccion_dt'].eq(min_por_tipo)].copy()
        resumen_periodos = (
            out[[tipo_col, '_periodo_prediccion_dt']]
            .drop_duplicates()
            .sort_values([tipo_col, '_periodo_prediccion_dt'])
        )
        texto = ', '.join(
            f"{row[tipo_col]}: {row['_periodo_prediccion_dt'].date().isoformat()}"
            for _, row in resumen_periodos.iterrows()
        )
        st.caption(f"Mostrando proximo mes disponible por tipo: {texto}")
    else:
        periodo_dt = pd.to_datetime(periodo_sel)
        out = out[out['_periodo_prediccion_dt'].eq(periodo_dt)].copy()
        st.caption(f"Mostrando periodo pronosticado: {periodo_sel}")

    return out.drop(columns=['_periodo_prediccion_dt'])


def _estado_keys(df_estado: pd.DataFrame) -> set:
    if df_estado is None or len(df_estado) == 0:
        return set()
    required = {'producto_dashboard', 'tipo_producto'}
    if not required.issubset(df_estado.columns):
        return set()

    tmp = df_estado[['producto_dashboard', 'tipo_producto']].dropna().copy()
    tmp['_producto_key'] = tmp['producto_dashboard'].astype(str).str.strip().str.upper()
    tmp['_tipo_key'] = tmp['tipo_producto'].astype(str).str.strip().str.upper()
    return set(zip(tmp['_producto_key'], tmp['_tipo_key']))


def _agregar_estado_planificacion(
    df: pd.DataFrame,
    df_estacionales: pd.DataFrame = None,
) -> pd.DataFrame:
    out = df.copy()
    out['_producto_key'] = out['producto_dashboard'].astype(str).str.strip().str.upper()
    out['_tipo_key'] = out['tipo_producto'].astype(str).str.strip().str.upper()

    estacionales = _estado_keys(df_estacionales)
    estacional_aux = pd.Series(
        [(prod, tipo) in estacionales for prod, tipo in zip(out['_producto_key'], out['_tipo_key'])],
        index=out.index,
    )
    if 'es_estacional' in out.columns:
        estacional_aux = estacional_aux | out['es_estacional'].fillna(False).astype(bool)

    razon_base = out['estado_producto_v3'] if 'estado_producto_v3' in out.columns else out['razon_vigencia']
    razon = razon_base.fillna(out['razon_vigencia']).astype(str).str.lower()
    vigente = out['es_vigente_operativo'].fillna(True).astype(bool)
    inactivo = (~vigente) | razon.str.contains('inactivo', na=False)

    out['estado_producto_plan'] = ESTADO_OPERATIVO_LABEL
    out.loc[estacional_aux & ~inactivo, 'estado_producto_plan'] = ESTADO_ESTACIONAL_LABEL
    out.loc[inactivo, 'estado_producto_plan'] = ESTADO_INACTIVO_LABEL

    accion = out['sugerencia_accion'].fillna('').astype(str)
    confianza = out['nivel_confianza'].fillna('').astype(str).str.lower()
    revisar = accion.str.contains('revisar', case=False, na=False) | confianza.isin(['media', 'baja'])
    produccion_cero = out['qty_recomendada'].fillna(0).eq(0)
    demanda_positiva = out['pronostico_qty'].fillna(0).gt(0)
    cubierto_inventario = produccion_cero & demanda_positiva & ~inactivo

    out['motivo_planificacion'] = 'Planificar produccion'
    out.loc[revisar & ~cubierto_inventario & ~inactivo, 'motivo_planificacion'] = 'Revisar antes de ordenar'
    out.loc[cubierto_inventario, 'motivo_planificacion'] = 'Inventario cubre demanda'
    out.loc[cubierto_inventario & revisar, 'motivo_planificacion'] = 'Inventario cubre demanda; revisar'
    out.loc[inactivo, 'motivo_planificacion'] = 'No producir por inactividad'

    return out.drop(columns=['_producto_key', '_tipo_key'])


def render():
    st.title("Pronostico Mensual de Produccion por Producto")

    st.info(
        """
        **Pregunta de negocio:** Cuanto se debe planificar producir por producto para el siguiente mes?

        **Fuente:** QuickBooks (historico de produccion).

        **Modelo:** Forecasting V3 QuickBooks.
        PT y PP usan el pipeline de prediccion nuevo, con Random Forest como modelo
        publicado cuando el producto esta activo y regla de cero para productos inactivos.
        La planificacion presentada es sugerida por modelo (sin plan humano en pantalla).
        """
    )
    st.caption(
        "Estados operativos: `Activo regular` = producto vigente no estacional; "
        "`Estacional` = producto vigente con patron de demanda estacional; "
        "`Inactivo` = producto sin actividad reciente, no se recomienda producir. "
        f"`{FILTRO_OPERATIVOS_LABEL}` agrupa Activo regular + Estacional. "
        "Confianza: `Alta` = error historico bajo; `Media` = error moderado; "
        "`Baja` = error alto; `No aplica (inactivo)` = la confianza no se usa porque el producto no deberia producirse."
    )

    try:
        df = get_predicciones()
        if len(df) == 0:
            st.warning("No hay pronosticos disponibles en tablas gold de forecasting")
            return

        df_est = get_productos_estacionales_forecasting()

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
            'qty_planificada', 'qty_fabricada', 'pronostico_qty', 'stock_actual', 'qty_recomendada',
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

        # Vista operativa: no mezclar todo el horizonte de prediccion.
        df = _filtrar_periodo_operativo(df)
        df = _agregar_estado_planificacion(df, df_est)
        df['nivel_confianza_ui'] = _normalizar_confianza_ui(df['nivel_confianza'])

        estados = sorted(df['estado_producto_plan'].dropna().astype(str).unique().tolist())
        estado_sel = st.selectbox('Estado operativo', [FILTRO_OPERATIVOS_LABEL, FILTRO_TODOS_LABEL] + estados, index=0)
        if estado_sel == FILTRO_OPERATIVOS_LABEL:
            df_plan = df[df['estado_producto_plan'] != ESTADO_INACTIVO_LABEL].copy()
        elif estado_sel != FILTRO_TODOS_LABEL:
            df_plan = df[df['estado_producto_plan'] == estado_sel].copy()
        else:
            df_plan = df.copy()
        st.caption(
            "Estados disponibles: Operativos = Activo regular + Estacional. "
            "Activo regular = producto vigente no estacional. "
            "Inactivo = no producir por inactividad."
        )

        if len(df_plan) == 0:
            st.warning("No hay productos para planificacion en el filtro actual")
            return

        periodos_pred = sorted(df_plan['periodo_prediccion'].dropna().astype(str).unique().tolist())
        periodo_txt = periodos_pred[0] if len(periodos_pred) == 1 else f"{periodos_pred[0]} ... {periodos_pred[-1]}"
        st.caption(f"Periodo pronostico operativo: {periodo_txt}")

        df_plan['requiere_revision_tabla'] = (
            df_plan['nivel_confianza'].fillna('').astype(str).str.lower().isin(['media', 'baja'])
            | df_plan['sugerencia_accion'].fillna('').astype(str).str.contains(
                'revisar',
                case=False,
                na=False,
            )
        )
        df_plan['produccion_cero_tabla'] = df_plan['qty_recomendada'].fillna(0).eq(0)
        tabla = df_plan[
            [
                'producto_dashboard',
                'tipo_producto',
                'estado_producto_plan',
                'periodo_prediccion',
                'meses_estacionales',
                'pronostico_qty',
                'stock_actual',
                'qty_min_recomendada',
                'qty_recomendada',
                'qty_max_recomendada',
                'nivel_confianza_ui',
                'motivo_planificacion',
            ]
        ].copy()

        tabla = tabla.rename(columns={
            'producto_dashboard': 'Producto',
            'tipo_producto': 'Tipo',
            'estado_producto_plan': 'Estado operativo',
            'periodo_prediccion': 'Mes a planificar',
            'meses_estacionales': 'Meses estacionales',
            'pronostico_qty': 'Demanda estimada',
            'stock_actual': 'Stock actual',
            'qty_min_recomendada': 'Produccion minima',
            'qty_recomendada': 'Produccion recomendada',
            'qty_max_recomendada': 'Produccion maxima',
            'nivel_confianza_ui': 'Confianza',
            'motivo_planificacion': 'Motivo planificacion',
        })

        tabla = tabla.sort_values(['Tipo', 'Estado operativo', 'Produccion recomendada'], ascending=[True, True, False])

        st.subheader("1. KPIs de planificacion")
        k1, k2, k3, k4 = st.columns(4)
        with k1:
            st.metric("Productos en vista", f"{df_plan['producto'].nunique():,}")
        with k2:
            st.metric("Demanda estimada", f"{df_plan['pronostico_qty'].sum():,.0f}")
        with k3:
            st.metric("Produccion recomendada", f"{df_plan['qty_recomendada'].sum():,.0f}")
        with k4:
            st.metric("Produccion cero", f"{df_plan['produccion_cero_tabla'].sum():,}")
        st.caption(
            f"Productos a revisar en la vista: {int(df_plan['requiere_revision_tabla'].sum()):,}"
        )

        st.markdown("---")

        st.subheader("2. Top productos (produccion recomendada)")
        top = df_plan.sort_values('qty_recomendada', ascending=False).head(20).copy()
        fig_top = go.Figure(
            go.Bar(
                x=top['qty_recomendada'],
                y=top['nombre_top'],
                orientation='h',
                marker_color=COLORS['primary'],
                text=[f"{x:,.0f}" for x in top['qty_recomendada']],
                textposition='outside',
            )
        )
        fig_top.update_layout(height=520, xaxis_title='Produccion recomendada', yaxis_title='Producto')
        st.plotly_chart(fig_top, use_container_width=True)

        st.markdown("---")

        st.subheader("3. Tabla de planificacion")
        st.caption(
            "Stock actual ayuda a explicar por que algunos productos tienen produccion recomendada baja o cero."
        )
        st.dataframe(
            tabla,
            use_container_width=True,
            height=560,
            hide_index=True,
            column_config={
                'Producto': st.column_config.TextColumn('Producto', width='large'),
                'Tipo': st.column_config.TextColumn('Tipo', width='small'),
                'Estado operativo': st.column_config.TextColumn('Estado operativo', width='small'),
                'Mes a planificar': st.column_config.DateColumn(
                    'Mes a planificar',
                    format='YYYY-MM-DD',
                    width='small',
                ),
                'Meses estacionales': st.column_config.TextColumn('Meses estacionales', width='small'),
                'Demanda estimada': st.column_config.NumberColumn(
                    'Demanda estimada',
                    format='%.0f',
                    width='medium',
                ),
                'Stock actual': st.column_config.NumberColumn(
                    'Stock actual',
                    format='%.0f',
                    width='medium',
                ),
                'Produccion minima': st.column_config.NumberColumn(
                    'Produccion minima',
                    format='%.0f',
                    width='medium',
                ),
                'Produccion recomendada': st.column_config.NumberColumn(
                    'Produccion recomendada',
                    format='%.0f',
                    width='medium',
                ),
                'Produccion maxima': st.column_config.NumberColumn(
                    'Produccion maxima',
                    format='%.0f',
                    width='medium',
                ),
                'Confianza': st.column_config.TextColumn('Confianza', width='small'),
                'Motivo planificacion': st.column_config.TextColumn('Motivo planificacion', width='medium'),
            },
        )

        st.markdown("---")

        st.subheader("4. Productos estacionales e inactivos")
        tab_est, tab_ina = st.tabs(["Estacionales", "Inactivos"])

        with tab_est:
            df_est_tab = df[df['estado_producto_plan'] == ESTADO_ESTACIONAL_LABEL].copy()
            if len(df_est_tab) == 0:
                st.info("No hay productos estacionales en el periodo operativo seleccionado.")
            else:
                est_cols = [
                    'producto_dashboard',
                    'tipo_producto',
                    'meses_estacionales',
                    'periodo_prediccion',
                    'pronostico_qty',
                    'qty_recomendada',
                    'motivo_planificacion',
                ]
                est_tabla = df_est_tab[est_cols].rename(columns={
                    'producto_dashboard': 'Producto',
                    'tipo_producto': 'Tipo',
                    'meses_estacionales': 'Meses estacionales',
                    'periodo_prediccion': 'Mes a planificar',
                    'pronostico_qty': 'Demanda estimada',
                    'qty_recomendada': 'Produccion recomendada',
                    'motivo_planificacion': 'Motivo planificacion',
                })
                st.caption(f"Productos estacionales V3: {len(est_tabla):,}")
                st.dataframe(est_tabla, use_container_width=True, height=320, hide_index=True)

        with tab_ina:
            df_ina_tab = df[df['estado_producto_plan'] == ESTADO_INACTIVO_LABEL].copy()
            if len(df_ina_tab) == 0:
                st.info("No hay productos inactivos en el periodo operativo seleccionado.")
            else:
                ina_cols = [
                    'producto_dashboard',
                    'tipo_producto',
                    'periodo_prediccion',
                    'pronostico_qty',
                    'qty_recomendada',
                    'motivo_planificacion',
                    'razon_vigencia',
                ]
                ina_tabla = df_ina_tab[ina_cols].rename(columns={
                    'producto_dashboard': 'Producto',
                    'tipo_producto': 'Tipo',
                    'periodo_prediccion': 'Mes a planificar',
                    'pronostico_qty': 'Demanda estimada',
                    'qty_recomendada': 'Produccion recomendada',
                    'motivo_planificacion': 'Motivo planificacion',
                    'razon_vigencia': 'Razon vigencia',
                })
                st.caption(f"Productos inactivos V3: {len(ina_tabla):,}")
                st.dataframe(ina_tabla, use_container_width=True, height=320, hide_index=True)

    except Exception as e:
        import traceback
        st.error(f"Error al cargar pronostico: {e}")
        st.code(traceback.format_exc())
