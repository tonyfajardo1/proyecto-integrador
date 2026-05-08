from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from src.datasets_postgres import (
    load_forecasting_dataset,
    load_association_dataset,
    load_anomaly_dataset,
)
from src.forecasting import benchmark_forecasting, benchmark_forecasting_sensitivity
from src.association import benchmark_association_sensitivity
from src.anomaly import benchmark_anomaly_sensitivity


def _fmt(v):
    if isinstance(v, float):
        return f"{v:.6f}"
    return str(v)


def _table_md(df, max_rows=12):
    if len(df) == 0:
        return "Sin resultados.\n"
    cols = list(df.columns)
    lines = []
    lines.append("| " + " | ".join(cols) + " |")
    lines.append("| " + " | ".join(["---"] * len(cols)) + " |")
    for _, row in df.head(max_rows).iterrows():
        vals = [_fmt(row[c]) for c in cols]
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines) + "\n"


def main():
    models_dir = ROOT / "models"
    evid_dir = ROOT.parents[1] / "05_evidencias"
    models_dir.mkdir(exist_ok=True)
    evid_dir.mkdir(exist_ok=True)

    df_f = load_forecasting_dataset()
    df_a = load_association_dataset()
    df_n = load_anomaly_dataset()

    res_f = benchmark_forecasting(df_f)
    res_f.to_csv(models_dir / "benchmark_forecasting.csv", index=False)

    res_f_sens = benchmark_forecasting_sensitivity(df_f)
    res_f_sens.to_csv(models_dir / "benchmark_forecasting_sensitivity.csv", index=False)

    res_a = benchmark_association_sensitivity(
        df_a,
        support_grid=(0.015, 0.02, 0.03),
        confidence_grid=(0.25, 0.30, 0.35),
        top_k=50,
    )
    res_a.to_csv(models_dir / "benchmark_association_sensitivity.csv", index=False)

    res_n = benchmark_anomaly_sensitivity(df_n, contamination_grid=(0.05, 0.10, 0.15))
    res_n.to_csv(models_dir / "benchmark_anomaly_sensitivity.csv", index=False)

    f_test = res_f[res_f.get("split") == "test"].copy() if "split" in res_f.columns else res_f.copy()
    f_best = f_test.sort_values("WAPE").iloc[0].to_dict() if len(f_test) > 0 else {}
    f_sens_best = res_f_sens.sort_values(["WAPE_val", "WAPE_test"]).iloc[0].to_dict() if len(res_f_sens) > 0 else {}
    a_best = res_a.iloc[0].to_dict() if len(res_a) > 0 else {}
    n_best = res_n.iloc[0].to_dict() if len(res_n) > 0 else {}

    md = []
    md.append("# Informe completo de benchmark de algoritmos")
    md.append("")
    md.append("## 1) Objetivo")
    md.append("")
    md.append("Comparar algoritmos por tipo de problema en Avance 2 para validar si el baseline actual es la mejor opcion operativa.")
    md.append("")
    md.append("## 2) Tipos de algoritmos y enfoque")
    md.append("")
    md.append("- Pronostico: aprendizaje supervisado (regresion).")
    md.append("- Asociacion: aprendizaje no supervisado (reglas de co-ocurrencia).")
    md.append("- Anomalias: no supervisado / one-class (deteccion de outliers).")
    md.append("")
    md.append("## 3) Desarrollo por tipo")
    md.append("")
    md.append("### 3.1 Pronostico de produccion")
    md.append("- Fuente: `quickbooks.produccion` (PostgreSQL).")
    md.append("- Baseline: `Lag-1`.")
    md.append("- Modelos: RandomForest, ExtraTrees, GradientBoosting, LinearRegression, Ridge y ElasticNet (pipeline con escalado).")
    md.append("- Protocolo: split temporal train/validation/test (60/20/20), seleccion en validation y reporte final en test.")
    md.append("- Sensibilidad: cuadricula de hiperparametros para modelos lineales regularizados y arboles con brechas train/validation/test.")
    md.append("")
    md.append("Top resultados (incluye validation y test):")
    md.append("")
    md.append(_table_md(res_f, max_rows=10))
    md.append(
        f"Mejor modelo en test por WAPE: `{_fmt(f_best.get('modelo', 'N/A'))}` "
        f"con WAPE `{_fmt(f_best.get('WAPE', float('nan')))}`."
    )
    md.append("")
    md.append("Top sensibilidad forecasting (por WAPE validation):")
    md.append("")
    md.append(_table_md(res_f_sens, max_rows=12))
    md.append(
        f"Mejor configuracion sensibilidad: `{_fmt(f_sens_best.get('modelo', 'N/A'))}` con "
        f"WAPE train `{_fmt(f_sens_best.get('WAPE_train', float('nan')))}`, "
        f"WAPE val `{_fmt(f_sens_best.get('WAPE_val', float('nan')))}` y "
        f"WAPE test `{_fmt(f_sens_best.get('WAPE_test', float('nan')))}`."
    )
    md.append("")
    md.append("### 3.2 Reglas de asociacion")
    md.append("- Fuente: `silver.apriori_transacciones` (PostgreSQL).")
    md.append("- Baseline: Apriori.")
    md.append("- Algoritmos comparados: Apriori vs FP-Growth.")
    md.append("- Sensibilidad: min_support en {0.015, 0.02, 0.03}, min_confidence en {0.25, 0.30, 0.35}, top_k=50.")
    md.append("- Criterios: score_general, lift, confianza en holdout, estabilidad Jaccard train-vs-holdout y tiempo.")
    md.append("- Filtro formal de reglas: umbrales minimos de confianza realizada (validation/test) y soporte realizado antes del top por consenso.")
    md.append("")
    md.append("Top resultados de sensibilidad:")
    md.append("")
    md.append(_table_md(res_a, max_rows=12))
    md.append(
        f"Mejor configuracion: algoritmo `{_fmt(a_best.get('algoritmo', 'N/A'))}`, "
        f"support `{_fmt(a_best.get('min_support', float('nan')))}`, "
        f"confidence `{_fmt(a_best.get('min_confidence', float('nan')))}`."
    )
    md.append("")
    md.append("### 3.3 Deteccion de anomalias")
    md.append("- Fuente: `gold.metricas_agencias` (PostgreSQL).")
    md.append("- Baseline: IsolationForest.")
    md.append("- Algoritmos comparados: IsolationForest, LOF, OneClassSVM, PCA_Reconstruction y PCA_IsolationForest.")
    md.append("- Sensibilidad: contamination en {0.05, 0.10, 0.15}.")
    md.append("- Criterios: cercania a contamination objetivo, estabilidad bootstrap top-anomalias, score compuesto.")
    md.append("")
    md.append("Top resultados de sensibilidad:")
    md.append("")
    md.append(_table_md(res_n, max_rows=12))
    md.append(
        f"Mejor configuracion: algoritmo `{_fmt(n_best.get('algoritmo', 'N/A'))}` "
        f"con contamination `{_fmt(n_best.get('contamination', float('nan')))}`."
    )
    md.append("")
    md.append("## 4) Validacion de sentido de negocio")
    md.append("")
    md.append("- Pronostico: el mejor modelo debe superar consistentemente al baseline lag-1 en WAPE test.")
    md.append("- Asociacion: lift alto sin perder soporte y con estabilidad razonable en holdout.")
    md.append("- Anomalias: porcentaje de alertas controlado y estable, evitando sobre-alertado.")
    md.append("")
    md.append("## 5) Riesgos y limitaciones")
    md.append("")
    md.append("- Anomalias con n pequeno (10 agencias) pueden tener alta varianza; interpretar como soporte de decision, no verdad absoluta.")
    md.append("- Reglas de asociacion pueden verse influidas por estacionalidad/promociones; revisar periodos y campañas.")
    md.append("- Pronostico t+1 depende de calidad de historico y cobertura mensual por producto.")
    md.append("")
    md.append("## 6) Recomendacion operativa")
    md.append("")
    md.append("- Mantener pipeline productivo actual y usar benchmark para decision de mejora controlada.")
    md.append("- Adoptar el mejor modelo por caso solo si mejora en test y mantiene interpretabilidad/costo aceptables.")
    md.append("- Repetir benchmark por corte mensual para monitorear deriva de datos.")
    md.append("")

    out_md = evid_dir / "INFORME_COMPLETO_BENCHMARK_ML.md"
    out_md.write_text("\n".join(md), encoding="utf-8")

    print("Generados:")
    print(models_dir / "benchmark_forecasting.csv")
    print(models_dir / "benchmark_forecasting_sensitivity.csv")
    print(models_dir / "benchmark_association_sensitivity.csv")
    print(models_dir / "benchmark_anomaly_sensitivity.csv")
    print(out_md)


if __name__ == "__main__":
    main()
