"""
Componentes reutilizables del dashboard
"""
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from config import COLORS


def render_metric_card(label: str, value: str, delta: str = None):
    """Renderiza una metrica con estilo"""
    st.metric(label=label, value=value, delta=delta)


def render_alert_card(tipo: str, entidad: str, indicador: str,
                      score: float, nivel: str, tendencia: str = None):
    """Renderiza una tarjeta de alerta"""
    color = COLORS['danger'] if nivel == 'CRITICO' else COLORS['warning']

    html = f"""
    <div style="background-color: {color}; color: white; padding: 15px;
                border-radius: 8px; margin: 10px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
        <h4 style="margin:0; color:white; font-size: 1.1em;">{tipo}</h4>
        <p style="margin:5px 0;"><strong>Entidad:</strong> {entidad}</p>
        <p style="margin:5px 0;"><strong>Indicador:</strong> {indicador}</p>
        <p style="margin:5px 0;"><strong>Score:</strong> {score:.2f}</p>
        {f'<p style="margin:5px 0;"><strong>Tendencia:</strong> {tendencia}</p>' if tendencia else ''}
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def create_bar_chart_horizontal(df, x_col: str, y_col: str,
                                 color_col: str = None, title: str = None,
                                 height: int = 400):
    """Crea grafico de barras horizontal"""
    if color_col:
        colors = df[color_col].tolist()
    else:
        colors = COLORS['primary']

    fig = go.Figure(go.Bar(
        y=df[y_col],
        x=df[x_col],
        orientation='h',
        marker_color=colors,
        text=[f"{x:.1f}" if isinstance(x, float) else str(x) for x in df[x_col]],
        textposition='outside'
    ))

    fig.update_layout(
        title=title,
        height=height,
        yaxis={'categoryorder': 'total ascending'},
        plot_bgcolor='white',
        paper_bgcolor='white',
        font=dict(family="Arial, sans-serif", size=12),
        margin=dict(l=20, r=20, t=40, b=20)
    )

    return fig


def create_bar_chart_grouped(df, x_col: str, y_cols: list,
                             names: list, colors: list = None,
                             title: str = None, height: int = 400):
    """Crea grafico de barras agrupadas"""
    if colors is None:
        colors = [COLORS['primary'], COLORS['danger']]

    fig = go.Figure()

    for i, (y_col, name) in enumerate(zip(y_cols, names)):
        fig.add_trace(go.Bar(
            name=name,
            x=df[x_col],
            y=df[y_col],
            marker_color=colors[i % len(colors)]
        ))

    fig.update_layout(
        title=title,
        barmode='group',
        height=height,
        plot_bgcolor='white',
        paper_bgcolor='white',
        font=dict(family="Arial, sans-serif", size=12),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )

    return fig


def create_scatter_chart(df, x_col: str, y_col: str,
                         color_col: str = None, size_col: str = None,
                         hover_data: list = None, title: str = None,
                         color_map: dict = None, height: int = 400):
    """Crea grafico de dispersion"""
    fig = px.scatter(
        df, x=x_col, y=y_col,
        color=color_col, size=size_col,
        hover_data=hover_data,
        color_discrete_map=color_map,
        color_continuous_scale='RdYlGn_r' if color_map is None and color_col else None
    )

    fig.update_layout(
        title=title,
        height=height,
        plot_bgcolor='white',
        paper_bgcolor='white',
        font=dict(family="Arial, sans-serif", size=12)
    )

    return fig


def create_pie_chart(values, names, title: str = None,
                     hole: float = 0.4, height: int = 400):
    """Crea grafico de pie/donut"""
    fig = px.pie(
        values=values,
        names=names,
        hole=hole,
        color_discrete_sequence=[COLORS['success'], COLORS['warning'], COLORS['danger']]
    )

    fig.update_layout(
        title=title,
        height=height,
        font=dict(family="Arial, sans-serif", size=12)
    )

    return fig


def render_data_table(df, columns: list = None, height: int = 400):
    """Renderiza tabla de datos"""
    if columns:
        df_display = df[columns]
    else:
        df_display = df

    st.dataframe(
        df_display.round(4),
        use_container_width=True,
        height=height
    )


def render_filter_section(df, column_configs: dict):
    """
    Renderiza seccion de filtros
    column_configs: dict con {nombre_col: label}
    """
    filters = {}
    cols = st.columns(len(column_configs))

    for i, (col_name, label) in enumerate(column_configs.items()):
        with cols[i]:
            values = df[col_name].unique()
            selected = st.multiselect(label, values)
            filters[col_name] = selected

    return filters


def apply_filters(df, filters: dict):
    """Aplica filtros al DataFrame"""
    df_filtered = df.copy()
    for col_name, values in filters.items():
        if values:
            df_filtered = df_filtered[df_filtered[col_name].isin(values)]
    return df_filtered
