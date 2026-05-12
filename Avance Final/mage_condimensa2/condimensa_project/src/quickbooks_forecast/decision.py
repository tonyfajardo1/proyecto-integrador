"""Salidas auxiliares para revision experta y soporte a decision."""

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
    """Crea la plantilla editable de stock minimo/maximo por producto."""
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
    """Prioriza productos a revisar manualmente en el siguiente horizonte."""
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
    """Resume como usar el forecast dentro del proceso de decision."""
    reports_dir = config["resolved_paths"]["reports_dir"]
    comparison = pd.read_csv(reports_dir / "model_comparison_all.csv")
    pt_best = comparison[comparison["source"].eq("PT")].sort_values("wape").iloc[0]
    pp_best = comparison[comparison["source"].eq("PP")].sort_values("wape").iloc[0]

    text = f"""# Guia de uso para toma de decisiones

## Estado actual

- El pipeline ya genera predicciones separadas para PT y PP.
- Las predicciones incluyen cantidad esperada, rango minimo/maximo, confianza y bandera de revision.
- La `confianza_prediccion` se calcula combinando error historico del producto, estabilidad del segmento en walk-forward y penalizaciones por estacionalidad o revision prioritaria.
- Las predicciones incorporan stock actual desde `Quickbooks/Costos.xlsx` para calcular una cantidad operativa ajustada.
- Pueden usarse como decision operativa para productos con confianza media/alta y sin bandera `requiere_revision`.
- Los productos con confianza baja, alta estacionalidad o error alto se marcan para revision antes de convertirse en ordenes finales.

## Comparacion de modelos

- Mejor modelo PT por WAPE test: {pt_best['model_name']} con WAPE {pt_best['wape']:.3f}.
- Mejor modelo PP por WAPE test: {pp_best['model_name']} con WAPE {pp_best['wape']:.3f}.
- `reports/model_comparison_all.csv` resume todos los modelos ML evaluados.
- `reports/validation_model_comparison_all.csv` documenta la comparacion equivalente en validacion.
- `reports/hgb_tuning_all.csv` registra el tuning de Gradient Boosting.
- `reports/exogenous_variables_plan.md` describe las variables exogenas contempladas dentro del proyecto.

## Validacion con expertos

`data/input/validacion_expertos_template.csv` sirve para registrar la retroalimentacion de produccion/comercial sobre:

- si la prediccion parece razonable,
- si hay promociones o pedidos especiales,
- si un producto esta por descontinuarse,
- si la cantidad debe ajustarse manualmente.

## Variables exogenas reales

Las exogenas por calendario y por producto se documentan en:

- `data/input/variables_exogenas_calendario.csv`: dias laborables, feriados, temporada, promociones generales y variacion de precio general.
- `data/input/variables_exogenas_producto.csv`: pedidos confirmados, preventa, promociones por producto, clientes grandes, cambios de PVP, riesgo de quiebre, disponibilidad de materia prima y ajustes comerciales conocidos antes del mes.

Estas variables deben estar disponibles historicamente para train/validacion/test y tambien para los meses futuros que se quieren predecir.

## Stock minimo y maximo

`data/input/stock_min_max_template.csv` concentra los parametros operativos de inventario:

- stock actual,
- stock minimo,
- stock maximo,
- lead time,
- lote minimo de produccion.

Con esos datos, la cantidad sugerida ajustada sigue la relacion:

`cantidad_a_producir = prediccion + stock_minimo - stock_actual`

y limitarla con stock maximo, capacidad y lotes minimos.

El pipeline ya descuenta `stock_actual` desde la columna `On Hand` de `Costos.xlsx`. Si `stock_minimo` y `stock_maximo` se completan en la plantilla, se usan para proyectar inventario inicial/final por mes y calcular `cantidad_a_producir_ajustada`.

## Recomendacion

Las predicciones pueden usarse como soporte operativo cuando `confianza_prediccion` es media/alta y `requiere_revision` es falso. `reports/high_error_products_all.csv` identifica los productos con mayor error historico para auditoria focalizada.
"""
    path = reports_dir / "decision_support_plan.md"
    path.write_text(text, encoding="utf-8")
    return text


def build_decision_templates(config: dict[str, Any]) -> dict[str, pd.DataFrame | str]:
    """Materializa todas las salidas de soporte para la etapa operativa."""
    stock = build_stock_policy_template(config)
    validation = build_expert_validation_template(config)
    report = build_decision_report(config)
    return {"stock": stock, "validation": validation, "report": report}
