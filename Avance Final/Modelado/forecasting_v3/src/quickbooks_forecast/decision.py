from __future__ import annotations

from typing import Any

import pandas as pd

from .inventory import build_current_stock


def _load_predictions(config: dict[str, Any]) -> pd.DataFrame:
    reports_dir = config["resolved_paths"]["reports_dir"]
    pt = pd.read_csv(reports_dir / "predicciones_pt.csv", parse_dates=["periodo"])
    pp = pd.read_csv(reports_dir / "predicciones_pp.csv", parse_dates=["periodo"])
    return pd.concat([pt, pp], ignore_index=True)


def _load_products(config: dict[str, Any]) -> pd.DataFrame:
    processed_dir = config["resolved_paths"]["processed_dir"]
    pt = pd.read_csv(processed_dir / "pt_productos_model.csv")
    pp = pd.read_csv(processed_dir / "pp_productos_model.csv")
    cols = [
        "source_type",
        "product_id",
        "product_name",
        "estado_producto",
        "es_estacional",
        "meses_estacionales",
        "ultima_actividad",
    ]
    return pd.concat([pt[cols], pp[cols]], ignore_index=True)


def build_stock_policy_template(config: dict[str, Any]) -> pd.DataFrame:
    processed_dir = config["resolved_paths"]["processed_dir"]
    pt_products = pd.read_csv(processed_dir / "pt_productos_model.csv")
    pp_products = pd.read_csv(processed_dir / "pp_productos_model.csv")
    products = _load_products(config)
    stock = pd.concat(
        [
            build_current_stock(config, "PT", pt_products),
            build_current_stock(config, "PP", pp_products),
        ],
        ignore_index=True,
    )
    template = products.merge(
        stock[["product_id", "stock_actual", "stock_encontrado", "stock_match_status"]],
        on="product_id",
        how="left",
    )
    template["stock_minimo"] = ""
    template["stock_maximo"] = ""
    template["lead_time_dias"] = ""
    template["lote_minimo_produccion"] = ""
    template["observacion"] = ""
    template = template.sort_values(["source_type", "product_name"]).reset_index(drop=True)

    input_dir = config["resolved_paths"]["project_root"] / "data" / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    template.to_csv(input_dir / "stock_min_max_template.csv", index=False, encoding="utf-8")
    return template


def build_expert_validation_template(config: dict[str, Any], top_n: int = 120) -> pd.DataFrame:
    reports_dir = config["resolved_paths"]["reports_dir"]
    predictions = _load_predictions(config)
    high_error = pd.read_csv(reports_dir / "high_error_products_all.csv")

    next_month = predictions["periodo"].min()
    next_predictions = predictions[predictions["periodo"].eq(next_month)].copy()
    next_predictions = next_predictions.sort_values("cantidad_predicha", ascending=False)

    if {"error_absoluto_total", "wape_producto", "prioridad_revision"}.issubset(next_predictions.columns):
        review = next_predictions.copy()
    else:
        review = next_predictions.merge(
            high_error[
                [
                    "source_type",
                    "product_id",
                    "error_absoluto_total",
                    "wape_producto",
                    "prioridad_revision",
                ]
            ],
            on=["source_type", "product_id"],
            how="left",
        )
    review["prioridad_revision"] = review["prioridad_revision"].fillna("normal")
    review["criterio_experto"] = ""
    review["cantidad_ajustada_experto"] = ""
    review["motivo_ajuste"] = ""
    review["responsable_revision"] = ""

    cols = [
        "source_type",
        "product_id",
        "product_name",
        "periodo",
        "cantidad_predicha",
        "prediccion_min",
        "prediccion_max",
        "confianza_prediccion",
        "requiere_revision",
        "recomendacion_decision",
        "estado_producto",
        "es_estacional",
        "meses_estacionales",
        "error_absoluto_total",
        "wape_producto",
        "prioridad_revision",
        "criterio_experto",
        "cantidad_ajustada_experto",
        "motivo_ajuste",
        "responsable_revision",
    ]
    review = review[cols].head(top_n)

    input_dir = config["resolved_paths"]["project_root"] / "data" / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    review.to_csv(input_dir / "validacion_expertos_template.csv", index=False, encoding="utf-8")
    return review


def build_decision_report(config: dict[str, Any]) -> str:
    reports_dir = config["resolved_paths"]["reports_dir"]
    comparison = pd.read_csv(reports_dir / "model_comparison_all.csv")
    pt_best = comparison[comparison["source"].eq("PT")].sort_values("wape").iloc[0]
    pp_best = comparison[comparison["source"].eq("PP")].sort_values("wape").iloc[0]

    text = f"""# Guia de uso para toma de decisiones


## Recomendacion

Usar las predicciones como decision operativa solo cuando `confianza_prediccion` sea media/alta y `requiere_revision` sea falso. Primero revisar productos con error alto en `reports/high_error_products_all.csv`.
"""
    path = reports_dir / "decision_support_plan.md"
    path.write_text(text, encoding="utf-8")
    return text


def build_decision_templates(config: dict[str, Any]) -> dict[str, pd.DataFrame | str]:
    stock = build_stock_policy_template(config)
    validation = build_expert_validation_template(config)
    report = build_decision_report(config)
    return {"stock": stock, "validation": validation, "report": report}
