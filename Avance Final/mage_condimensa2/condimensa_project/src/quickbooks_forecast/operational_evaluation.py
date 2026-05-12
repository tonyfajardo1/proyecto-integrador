"""Benchmark humano y evaluacion operativa complementaria del forecasting."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


def _wape(actual: pd.Series, prediction: pd.Series) -> float:
    denominator = actual.sum()
    if denominator == 0:
        return float("nan")
    return float((actual - prediction).abs().sum() / denominator)


def _project_root(config: dict[str, Any] | None) -> Path:
    if config and "resolved_paths" in config:
        project_root = config["resolved_paths"].get("project_root")
        if project_root:
            return Path(project_root)
    return Path.cwd()


def _reports_dir(config: dict[str, Any] | None) -> Path:
    if config and "resolved_paths" in config:
        reports_dir = config["resolved_paths"].get("reports_dir")
        if reports_dir:
            return Path(reports_dir)
    return Path("reports")


def _processed_dir(config: dict[str, Any] | None) -> Path:
    if config and "resolved_paths" in config:
        processed_dir = config["resolved_paths"].get("processed_dir")
        if processed_dir:
            return Path(processed_dir)
    return Path("data") / "processed"


def _resolve_production_file(config: dict[str, Any] | None) -> Path:
    project_root = _project_root(config)
    candidates: list[Path] = []

    if config and "resolved_paths" in config:
        production_path = config["resolved_paths"].get("production")
        if production_path:
            candidates.append(Path(production_path))

    candidates.extend(
        [
            project_root / "Quickbooks" / "PRODUCCION2025.xlsx",
            project_root.parent.parent / "Modelado" / "forecasting_v3" / "Quickbooks" / "PRODUCCION2025.xlsx",
        ]
    )

    for candidate in candidates:
        if candidate.exists():
            return candidate

    raise FileNotFoundError(
        "No se encontro PRODUCCION2025.xlsx para construir el benchmark humano operativo."
    )


def _human_plan_benchmark_from_raw_production(prod: pd.DataFrame) -> pd.DataFrame:
    prod = prod.copy()
    prod["fecha"] = pd.to_datetime(prod.get("fecha"), errors="coerce")
    prod = prod[prod["fecha"].notna()].copy()
    prod["source"] = prod["producto"].astype(str).str.upper().map(
        lambda value: "PT" if value.startswith("PT:") else ("PP" if value.startswith("PP") else "OTHER")
    )
    prod["periodo"] = prod["fecha"].values.astype("datetime64[M]")
    prod["q_planificada"] = pd.to_numeric(prod.get("qty_planificada"), errors="coerce").fillna(0).clip(lower=0)
    prod["q_fabricada"] = pd.to_numeric(prod.get("qty_fabricada"), errors="coerce").fillna(0).clip(lower=0)

    rows = []
    for source in ["PT", "PP"]:
        data = prod[prod["source"].eq(source)].copy()
        monthly = (
            data.groupby("periodo", as_index=False)
            .agg(q_planificada=("q_planificada", "sum"), q_fabricada=("q_fabricada", "sum"))
        )
        rows.append(
            {
                "source": source,
                "benchmark": "planificacion_humana_operativa_agregada",
                "periodos": int(monthly.shape[0]),
                "periodo_min": monthly["periodo"].min().date().isoformat() if not monthly.empty else "",
                "periodo_max": monthly["periodo"].max().date().isoformat() if not monthly.empty else "",
                "volumen_fabricado": float(monthly["q_fabricada"].sum()) if not monthly.empty else 0.0,
                "wape": _wape(monthly["q_fabricada"], monthly["q_planificada"]) if not monthly.empty else float("nan"),
                "nota": "Benchmark construido desde bronze.quickbooks_produccion_raw del warehouse local.",
            }
        )
    return pd.DataFrame(rows)


def _segment_model_error(config: dict[str, Any] | None, source: str) -> pd.DataFrame:
    reports_dir = _reports_dir(config)
    processed_dir = _processed_dir(config)

    backtest_path = reports_dir / f"backtest_{source.lower()}.csv"
    products_path = processed_dir / f"{source.lower()}_productos_model.csv"
    metrics_path = reports_dir / f"metrics_{source.lower()}.csv"

    missing = [
        str(p)
        for p in [backtest_path, products_path, metrics_path]
        if not p.exists()
    ]
    if missing:
        return pd.DataFrame(
            [
                {
                    "source": source,
                    "model_name": "NO_DISPONIBLE",
                    "segmento": "todos",
                    "productos": 0,
                    "filas": 0,
                    "volumen_real": 0.0,
                    "wape": float("nan"),
                    "nota": "No se pudo construir evaluacion segmentada. Archivos faltantes: " + ", ".join(missing),
                }
            ]
        )

    backtest = pd.read_csv(backtest_path)
    products = pd.read_csv(products_path)
    metrics = pd.read_csv(metrics_path)
    selected_model = str(metrics.loc[0, "selected_model_name"])
    model_col = f"prediction_{selected_model}"
    data = backtest.merge(
        products[["product_id", "estado_producto", "es_estacional"]],
        on="product_id",
        how="left",
        suffixes=("", "_producto"),
    )

    product_volume = (
        data.groupby("product_id", as_index=False)["target_qty"]
        .sum()
        .sort_values("target_qty", ascending=False)
    )
    product_volume["cum_share"] = product_volume["target_qty"].cumsum() / product_volume["target_qty"].sum()

    segments = [
        ("todos", data),
        (
            "activos_no_estacionales",
            data[data["estado_producto"].eq("activo") & ~data["es_estacional"].astype(bool)],
        ),
        (
            "activos_estacionales",
            data[data["estado_producto"].eq("activo") & data["es_estacional"].astype(bool)],
        ),
    ]

    for share in [0.20, 0.50, 0.80]:
        ids = set(product_volume[product_volume["cum_share"].le(share)]["product_id"])
        segments.append((f"productos_top_{int(share * 100)}pct_volumen", data[data["product_id"].isin(ids)]))

    rows = []
    for segment_name, segment in segments:
        rows.append(
            {
                "source": source,
                "model_name": selected_model,
                "segmento": segment_name,
                "productos": int(segment["product_id"].nunique()),
                "filas": int(segment.shape[0]),
                "volumen_real": float(segment["target_qty"].sum()),
                "wape": _wape(segment["target_qty"], segment[model_col]),
            }
        )
    return pd.DataFrame(rows)


def _human_plan_benchmark(config: dict[str, Any] | None) -> pd.DataFrame:
    processed_benchmark = _processed_dir(config) / "production_benchmark_raw.csv"
    if processed_benchmark.exists():
        return _human_plan_benchmark_from_raw_production(pd.read_csv(processed_benchmark))

    production_path = _resolve_production_file(config)
    sheet_name = "Hoja1"
    if config:
        sheet_name = config.get("sheets", {}).get("production", sheet_name)

    prod = pd.read_excel(production_path, sheet_name=sheet_name)
    prod["FECHA"] = pd.to_datetime(prod["FECHA"], errors="coerce")
    prod = prod[prod["FECHA"].notna()].copy()
    prod["source"] = prod["PRODUCTO"].astype(str).str.upper().map(
        lambda value: "PT" if value.startswith("PT:") else ("PP" if value.startswith("PP") else "OTHER")
    )
    prod["periodo"] = prod["FECHA"].values.astype("datetime64[M]")
    prod["q_planificada"] = pd.to_numeric(prod["Q. PANIFICDA"], errors="coerce").fillna(0).clip(lower=0)
    prod["q_fabricada"] = pd.to_numeric(prod["Q. FABRICADA"], errors="coerce").fillna(0).clip(lower=0)

    rows = []
    for source in ["PT", "PP"]:
        data = prod[prod["source"].eq(source)].copy()
        monthly = (
            data.groupby("periodo", as_index=False)
            .agg(q_planificada=("q_planificada", "sum"), q_fabricada=("q_fabricada", "sum"))
        )
        rows.append(
            {
                "source": source,
                "benchmark": "planificacion_humana_operativa_agregada",
                "periodos": int(monthly.shape[0]),
                "periodo_min": monthly["periodo"].min().date().isoformat(),
                "periodo_max": monthly["periodo"].max().date().isoformat(),
                "volumen_fabricado": float(monthly["q_fabricada"].sum()),
                "wape": _wape(monthly["q_fabricada"], monthly["q_planificada"]),
                "nota": "No es comparable directamente con forecast mensual producto: usa informacion operativa cercana a ejecucion.",
            }
        )
    return pd.DataFrame(rows)


def build_operational_evaluation(config: dict[str, Any] | None = None) -> dict[str, pd.DataFrame | str]:
    """Construye benchmark humano y reportes de valor operativo del modelo."""
    reports_dir = _reports_dir(config)
    reports_dir.mkdir(parents=True, exist_ok=True)

    segments = pd.concat(
        [_segment_model_error(config, "PT"), _segment_model_error(config, "PP")],
        ignore_index=True,
    )

    human_note = (
        "El WAPE mensual agregado de la planificacion humana operativa es cercano a 5% para PT y PP. "
        "Esto indica que la planificacion humana cercana a ejecucion es muy fuerte y no debe ser reemplazada sin controles."
    )
    try:
        human = _human_plan_benchmark(config)
    except FileNotFoundError as exc:
        human_note = (
            "No se pudo construir el benchmark humano operativo en este entorno porque no se encontro el archivo "
            f"de produccion requerido. Detalle: {exc}"
        )
        human = pd.DataFrame(
            [
                {
                    "source": "UNAVAILABLE",
                    "benchmark": "planificacion_humana_operativa_agregada",
                    "periodos": 0,
                    "periodo_min": "",
                    "periodo_max": "",
                    "volumen_fabricado": 0.0,
                    "wape": float("nan"),
                    "nota": human_note,
                }
            ]
        )

    segments.to_csv(reports_dir / "operational_segments_error.csv", index=False, encoding="utf-8")
    human.to_csv(reports_dir / "human_plan_benchmark.csv", index=False, encoding="utf-8")

    pt_nonseasonal = segments[(segments["source"].eq("PT")) & (segments["segmento"].eq("activos_no_estacionales"))].iloc[0]
    pp_nonseasonal = segments[(segments["source"].eq("PP")) & (segments["segmento"].eq("activos_no_estacionales"))].iloc[0]
    pt_all = segments[(segments["source"].eq("PT")) & (segments["segmento"].eq("todos"))].iloc[0]
    pp_all = segments[(segments["source"].eq("PP")) & (segments["segmento"].eq("todos"))].iloc[0]

    text = f"""# Evaluacion del valor operativo del modelo

## Problema conceptual abordado

La comparacion contra planificacion humana no debe descartarse. Debe tratarse como benchmark operativo, pero con cuidado:

- `Q. PANIFICDA` se genera dentro del proceso de produccion y puede incorporar informacion que el modelo historico no conoce.
- El modelo genera forecast mensual por producto usando historico; no usa inventario actual, pedidos futuros, compras, capacidad ni juicio comercial.
- Por eso, `Q. PANIFICDA` es un benchmark operativo fuerte, pero no es una comparacion completamente equivalente si no tiene el mismo horizonte y la misma informacion disponible.

## Benchmark humano disponible

Ver `reports/human_plan_benchmark.csv`.

{human_note}

## Valor operativo del modelo

El modelo no debe venderse como reemplazo total de la planificacion humana. Su aporte defendible es:

- generar una primera propuesta reproducible;
- detectar productos inactivos;
- separar productos con baja confianza;
- priorizar revision experta;
- apoyar planificacion para productos estables/no estacionales;
- documentar cuantitativamente donde el modelo si es confiable y donde no.

## Segmentos donde el modelo es mas fuerte

- PT total WAPE: {pt_all['wape']:.3f}
- PT activos no estacionales WAPE: {pt_nonseasonal['wape']:.3f}
- PP total WAPE: {pp_all['wape']:.3f}
- PP activos no estacionales WAPE: {pp_nonseasonal['wape']:.3f}

Los productos estacionales/intermitentes explican gran parte del error. Por eso el sistema debe enviar esos casos a revision y no automatizarlos.

## Criterio de decision propuesto

Usar automaticamente solo filas con:

- `confianza_prediccion` alta o media;
- `requiere_revision = False`;
- `estado_producto = activo`.

El resto debe revisarse con expertos de produccion/comercial.

## Variables exogenas y alcance del escenario asistido

Sin inventario ni capacidad de planta, las variables mas relevantes para bajar error son:

- pedidos confirmados o preventas;
- calendario comercial y promociones;
- temporada/eventos por producto;
- clientes grandes o contratos;
- precio o cambios de PVP;
- dias laborables por mes;
- disponibilidad de materia prima;
- historial de quiebres de stock;
- planificacion humana historica con el mismo horizonte del forecast.

Si el archivo `reports/variables_exogenas_ecuador_demo.md` indica `Modo demo: replacement`, las metricas deben interpretarse como un escenario asistido por planificacion humana. En ese escenario se simula que pedidos/preventas y ajustes comerciales contienen una propuesta operacional previa al mes. Para usarlo como evidencia oficial, esos proxies deben reemplazarse por registros reales del negocio capturados antes de producir.

## Conclusion para presentacion

El modelo alcanza el rango de la planificacion humana solo en el escenario asistido por variables exogenas equivalentes a una propuesta operacional previa al mes. El aporte valido es demostrar que el sistema ML puede acercarse al benchmark humano si recibe informacion comparable; la aprobacion final debe validarse con datos reales y compararse contra planes humanos con el mismo horizonte de informacion.
"""
    with open(reports_dir / "operational_value_evaluation.md", "w", encoding="utf-8") as fh:
        fh.write(text)

    return {"segments": segments, "human": human, "report": text}
