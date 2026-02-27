"""
Pagina: Tendencias y Evolucion
Requerimiento Empresa: Evolucion temporal de indicadores
"""
import streamlit as st
import plotly.graph_objects as go
from database import get_evolucion
from components import render_data_table
from config import COLORS


def render():
    """Renderiza la pagina de tendencias y evolucion"""
    st.title("Tendencias y Evolucion")
    st.markdown("**Requerimiento Empresa:** Evolucion de productos, marcas y agencias en el tiempo")

    try:
        df = get_evolucion()

        st.markdown("---")

        # Filtros
        with st.expander("Filtros", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
                tipo = st.selectbox(
                    "Tipo de Entidad",
                    options=sorted(df['entidad_tipo'].unique())
                )
            with col2:
                metrica = st.selectbox(
                    "Metrica",
                    options=sorted(df['metrica'].unique())
                )

        df_f = df[(df['entidad_tipo'] == tipo) & (df['metrica'] == metrica)]

        st.markdown("---")

        # Metricas resumen
        col1, col2, col3 = st.columns(3)
        with col1:
            total = df_f['valor'].sum()
            st.metric("Total", f"${total:,.0f}" if total > 100 else f"{total:.2f}")
        with col2:
            promedio = df_f['valor'].mean()
            st.metric("Promedio", f"${promedio:,.0f}" if promedio > 100 else f"{promedio:.2f}")
        with col3:
            var_prom = df_f['variacion_porcentual'].mean() * 100
            st.metric("Variacion Promedio", f"{var_prom:.1f}%")

        st.markdown("---")

        col1, col2 = st.columns(2)

        with col1:
            st.subheader(f"{metrica.replace('_', ' ').title()} por {tipo.title()}")
            df_sorted = df_f.sort_values('valor', ascending=True).tail(15)

            fig = go.Figure(go.Bar(
                y=df_sorted['entidad_valor'],
                x=df_sorted['valor'],
                orientation='h',
                marker=dict(color=df_sorted['valor'], colorscale='Blues'),
                text=[f"${x:,.0f}" if x > 100 else f"{x:.2f}" for x in df_sorted['valor']],
                textposition='outside'
            ))
            fig.update_layout(
                height=500,
                plot_bgcolor='white',
                yaxis={'categoryorder': 'total ascending'}
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.subheader("Variacion Porcentual")
            df_var = df_f.sort_values('variacion_porcentual', ascending=True)

            colors = [COLORS['danger'] if x < 0 else COLORS['success']
                     for x in df_var['variacion_porcentual']]

            fig = go.Figure(go.Bar(
                y=df_var['entidad_valor'],
                x=df_var['variacion_porcentual'] * 100,
                orientation='h',
                marker_color=colors,
                text=[f"{x*100:.1f}%" for x in df_var['variacion_porcentual']],
                textposition='outside'
            ))
            fig.add_vline(x=0, line_color="gray")
            fig.update_layout(
                xaxis_title="Variacion %",
                height=500,
                plot_bgcolor='white'
            )
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")

        # Analisis de tendencias
        st.subheader("Analisis de Tendencias")

        col1, col2 = st.columns(2)

        with col1:
            # Top crecimiento
            st.markdown("**Mayor Crecimiento:**")
            top_crec = df_f.nlargest(5, 'variacion_porcentual')
            for _, row in top_crec.iterrows():
                var = row['variacion_porcentual'] * 100
                st.markdown(f"- {row['entidad_valor']}: +{var:.1f}%")

        with col2:
            # Mayor caida
            st.markdown("**Mayor Decremento:**")
            top_caida = df_f.nsmallest(5, 'variacion_porcentual')
            for _, row in top_caida.iterrows():
                var = row['variacion_porcentual'] * 100
                st.markdown(f"- {row['entidad_valor']}: {var:.1f}%")

        st.markdown("---")
        st.subheader("Datos Detallados")
        render_data_table(df_f)

    except Exception as e:
        st.error(f"Error al cargar datos: {e}")
