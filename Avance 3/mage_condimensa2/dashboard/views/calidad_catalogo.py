"""
Pagina: Calidad de catalogo EAN para forecasting.
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

import database as db
from config import COLORS


def render():
    st.title("Calidad Catalogo EAN")
    st.info(
        """
        Monitoreo de conflictos de catalogo y estado de productos usados en forecasting.
        Fuente: tablas Gold derivadas de silver.dim_producto_canonico y silver.forecasting_base_mensual_v1.
        """
    )

    if hasattr(db, "get_catalogo_conflictos_ean"):
        df_conf = db.get_catalogo_conflictos_ean()
    else:
        query_conf = db.QUERIES.get("catalogo_conflictos_ean", "SELECT * FROM gold.catalogo_conflictos_ean13_v1")
        df_conf = db.load_data(query_conf)

    if hasattr(db, "get_estado_producto_forecasting"):
        df_estado = db.get_estado_producto_forecasting()
    else:
        query_estado = db.QUERIES.get(
            "estado_producto_forecasting",
            "SELECT * FROM gold.forecasting_estado_producto_resumen_v1",
        )
        df_estado = db.load_data(query_estado)

    if len(df_conf) == 0 and len(df_estado) == 0:
        st.warning("No hay datos de calidad de catalogo publicados en Gold.")
        return

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("EAN en conflicto", f"{len(df_conf):,}")
    with c2:
        n_prod_conf = int(df_conf["n_codigos"].sum()) if len(df_conf) > 0 and "n_codigos" in df_conf.columns else 0
        st.metric("Codigos involucrados", f"{n_prod_conf:,}")
    with c3:
        n_prod_estado = int(df_estado["n_productos"].sum()) if len(df_estado) > 0 and "n_productos" in df_estado.columns else 0
        st.metric("Productos en base", f"{n_prod_estado:,}")

    st.markdown("---")

    if len(df_estado) > 0:
        st.subheader("Estado de producto en forecasting")
        plot_df = df_estado.copy()
        plot_df["estado_producto"] = plot_df["estado_producto"].astype(str)
        plot_df["n_rows"] = pd.to_numeric(plot_df["n_rows"], errors="coerce").fillna(0)
        fig = go.Figure(
            go.Bar(
                x=plot_df["estado_producto"],
                y=plot_df["n_rows"],
                marker_color=[COLORS["success"], COLORS["warning"], COLORS["danger"]][: len(plot_df)],
                text=[f"{int(v):,}" for v in plot_df["n_rows"]],
                textposition="outside",
            )
        )
        fig.update_layout(height=360, xaxis_title="Estado", yaxis_title="Filas")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df_estado, use_container_width=True, height=180)

    st.markdown("---")

    st.subheader("Conflictos EAN13")
    if len(df_conf) == 0:
        st.success("No hay EAN13 en conflicto en la publicacion actual.")
    else:
        view = df_conf.rename(
            columns={
                "ean13": "EAN13",
                "n_nombres": "Nombres distintos",
                "n_codigos": "Codigos distintos",
                "nombres_dashboard": "Productos dashboard",
                "fecha_ejecucion": "Fecha ejecucion",
            }
        )
        st.dataframe(view, use_container_width=True, height=280)
