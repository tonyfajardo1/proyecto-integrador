import json
from pathlib import Path


def md_cell(text):
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": [line + "\n" for line in text.strip("\n").split("\n")],
    }


def code_cell(code):
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [line + "\n" for line in code.strip("\n").split("\n")],
    }


def notebook_dict(cells):
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {
                "name": "python",
                "version": "3.11",
            },
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def build_forecasting_notebook():
    cells = [
        md_cell(
            """
# Benchmark de pronostico (PostgreSQL)

Este notebook ejecuta el benchmark completo de pronostico con comparaciones, sensibilidad e interpretacion automatica.
"""
        ),
        code_cell(
            """
from pathlib import Path
import sys
import warnings

import matplotlib.pyplot as plt
import pandas as pd
from IPython.display import Markdown, display

warnings.filterwarnings("ignore")

CWD = Path.cwd().resolve()
candidates = [
    CWD,
    CWD.parent,
    CWD / "03_modelado" / "proyecto_ml_experimentos",
]
ROOT = next((p for p in candidates if (p / "src" / "forecasting.py").exists()), None)
if ROOT is None:
    raise RuntimeError("No se encontro la raiz de proyecto_ml_experimentos (src/forecasting.py).")

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

for m in ["src", "src.datasets_postgres", "src.forecasting"]:
    if m in sys.modules:
        del sys.modules[m]

from src.datasets_postgres import load_forecasting_dataset
from src.forecasting import benchmark_forecasting, benchmark_forecasting_sensitivity
"""
        ),
        code_cell(
            """
df = load_forecasting_dataset()
display(df.head())

display(
    Markdown(
        f'''
### Calidad del dataset
- Filas: **{len(df):,}**
- Productos: **{df['producto'].nunique():,}**
- Periodos: **{df['periodo'].nunique():,}**
- Nulos en `periodo`: **{int(df['periodo'].isna().sum()):,}**
'''
    )
)
"""
        ),
        code_cell(
            """
res = benchmark_forecasting(df)
sens = benchmark_forecasting_sensitivity(df)

models_dir = ROOT / "models"
models_dir.mkdir(exist_ok=True)
charts_dir = ROOT.parents[1] / "05_evidencias" / "graficas"
charts_dir.mkdir(parents=True, exist_ok=True)
res.to_csv(models_dir / "benchmark_forecasting.csv", index=False)
sens.to_csv(models_dir / "benchmark_forecasting_sensitivity.csv", index=False)

display(res)
display(sens.head(12))
"""
        ),
        code_cell(
            """
test_table = res[res["split"] == "test"].sort_values("WAPE").reset_index(drop=True)
plot_df = test_table[["modelo", "WAPE"]].copy()

plt.figure(figsize=(10, 4))
plt.bar(plot_df["modelo"], plot_df["WAPE"])
plt.title("WAPE en test por modelo")
plt.ylabel("WAPE")
plt.xticks(rotation=30, ha="right")
plt.tight_layout()
plt.savefig(charts_dir / "forecasting_wape_test_por_modelo.png", dpi=150)
plt.show()

top_sens = sens.sort_values("WAPE_val").head(6).copy()
melt = top_sens[["modelo", "WAPE_train", "WAPE_val", "WAPE_test"]].melt(
    id_vars=["modelo"],
    var_name="split",
    value_name="WAPE",
)

plt.figure(figsize=(10, 4))
for model_name, sub in melt.groupby("modelo"):
    plt.plot(sub["split"], sub["WAPE"], marker="o", label=model_name)
plt.title("Brechas train/validation/test (top sensibilidad)")
plt.ylabel("WAPE")
plt.legend(bbox_to_anchor=(1.02, 1), loc="upper left")
plt.tight_layout()
plt.savefig(charts_dir / "forecasting_brechas_train_val_test.png", dpi=150)
plt.show()

display(Markdown(f"Graficas guardadas en: `{charts_dir}`"))
"""
        ),
        code_cell(
            """
best_test = test_table.iloc[0]
baseline_test = test_table[test_table["modelo"] == "Baseline_Lag1"].iloc[0]
improvement = float(baseline_test["WAPE"] - best_test["WAPE"])

best_sens = sens.sort_values(["WAPE_val", "WAPE_test"]).iloc[0]
gap_val_test = float(best_sens["gap_wape_val_test"])

if improvement >= 0.05 and gap_val_test <= 0.06:
    semaforo = "VERDE"
    estado = "modelo robusto y mejora clara frente al baseline"
elif improvement > 0 and gap_val_test <= 0.10:
    semaforo = "AMARILLO"
    estado = "mejora valida, pero requiere monitoreo de brecha"
else:
    semaforo = "ROJO"
    estado = "sin mejora consistente o con riesgo alto de sobreajuste"

display(
    Markdown(
        f'''
## Interpretacion
- Mejor modelo en test: **{best_test['modelo']}**.
- `WAPE` test del mejor: **{best_test['WAPE']:.4f}**.
- `WAPE` baseline lag-1: **{baseline_test['WAPE']:.4f}**.
- Mejora absoluta vs baseline: **{improvement:.4f}**.
- Mejor configuracion de sensibilidad (por validacion): **{best_sens['modelo']}**.
- Brecha `WAPE train -> val` en la mejor configuracion: **{best_sens['gap_wape_train_val']:.4f}**.

Lectura recomendada:
1. Si la brecha train-val sube demasiado, ajustar complejidad.
2. Mantener decision final por metrica de **test**.
3. Reportar siempre comparacion contra baseline lag-1.

## Conclusion ejecutiva
- Semaforo: **{semaforo}**.
- Estado: **{estado}**.
'''
    )
)
"""
        ),
    ]
    return notebook_dict(cells)


def build_association_notebook():
    cells = [
        md_cell(
            """
# Benchmark de asociacion (PostgreSQL)

Este notebook ejecuta benchmark y sensibilidad de reglas de asociacion con filtros de calidad y consenso multicriterio.
"""
        ),
        code_cell(
            """
from pathlib import Path
import sys
import warnings

import matplotlib.pyplot as plt
import pandas as pd
from IPython.display import Markdown, display

warnings.filterwarnings("ignore")

CWD = Path.cwd().resolve()
candidates = [
    CWD,
    CWD.parent,
    CWD / "03_modelado" / "proyecto_ml_experimentos",
]
ROOT = next((p for p in candidates if (p / "src" / "association.py").exists()), None)
if ROOT is None:
    raise RuntimeError("No se encontro la raiz de proyecto_ml_experimentos (src/association.py).")

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

for m in ["src", "src.datasets_postgres", "src.association"]:
    if m in sys.modules:
        del sys.modules[m]

from src.datasets_postgres import load_association_dataset
from src.association import benchmark_association, benchmark_association_sensitivity
"""
        ),
        code_cell(
            """
df = load_association_dataset()
display(df.head())

tx_size = df.groupby("transaccion_id")["producto"].nunique()

display(
    Markdown(
        f'''
### Calidad del dataset
- Filas: **{len(df):,}**
- Transacciones: **{df['transaccion_id'].nunique():,}**
- Productos unicos: **{df['producto'].nunique():,}**
- Transacciones con >=2 productos: **{int((tx_size >= 2).sum()):,}**
'''
    )
)
"""
        ),
        code_cell(
            """
res = benchmark_association(
    df,
    min_support=0.02,
    min_confidence=0.25,
    top_k=20,
    min_realized_conf_val=0.25,
    min_realized_conf_test=0.25,
    min_realized_support=0.005,
)

sens = benchmark_association_sensitivity(
    df,
    support_grid=(0.015, 0.02, 0.03),
    confidence_grid=(0.25, 0.30, 0.35),
    top_k=50,
    min_realized_conf_val=0.25,
    min_realized_conf_test=0.25,
    min_realized_support=0.005,
)

models_dir = ROOT / "models"
models_dir.mkdir(exist_ok=True)
charts_dir = ROOT.parents[1] / "05_evidencias" / "graficas"
charts_dir.mkdir(parents=True, exist_ok=True)
res.to_csv(models_dir / "benchmark_association.csv", index=False)
sens.to_csv(models_dir / "benchmark_association_sensitivity.csv", index=False)

display(res)
display(sens.head(15))
"""
        ),
        code_cell(
            """
plt.figure(figsize=(8, 4))
plt.bar(res["algoritmo"], res["score_general"])
plt.title("Score general por algoritmo")
plt.ylabel("score_general")
plt.tight_layout()
plt.savefig(charts_dir / "association_score_por_algoritmo.png", dpi=150)
plt.show()

for algo, sub in sens.groupby("algoritmo"):
    tmp = sub.sort_values(["min_support", "min_confidence"])
    plt.figure(figsize=(8, 4))
    plt.plot(tmp["min_support"].astype(str) + "|" + tmp["min_confidence"].astype(str), tmp["score_general"], marker="o")
    plt.title(f"Sensibilidad de score_general - {algo}")
    plt.ylabel("score_general")
    plt.xlabel("support|confidence")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(charts_dir / f"association_sensibilidad_{algo.lower()}.png", dpi=150)
    plt.show()

display(Markdown(f"Graficas guardadas en: `{charts_dir}`"))
"""
        ),
        code_cell(
            """
best = res.sort_values("score_general", ascending=False).iloc[0]
best_sens = sens.sort_values("score_general", ascending=False).iloc[0]

if float(best["conf_test_prom"]) >= 0.45 and float(best["jaccard_train_test"]) >= 0.8:
    semaforo = "VERDE"
    estado = "reglas estables y confiables para uso operativo"
elif float(best["conf_test_prom"]) >= 0.30 and float(best["jaccard_train_test"]) >= 0.5:
    semaforo = "AMARILLO"
    estado = "resultado util con necesidad de revisar reglas manualmente"
else:
    semaforo = "ROJO"
    estado = "calidad insuficiente para usar reglas sin ajustes"

display(
    Markdown(
        f'''
## Interpretacion
- Mejor algoritmo en este corte: **{best['algoritmo']}**.
- `score_general`: **{best['score_general']:.4f}**.
- Reglas train: **{int(best['reglas_train'])}**.
- Reglas que pasan filtro de calidad: **{int(best['reglas_filtradas_calidad'])}**.
- Top consenso usado para evaluacion: **{int(best['reglas_top_consenso'])}**.
- Configuracion de sensibilidad ganadora: support **{best_sens['min_support']:.3f}**, confidence **{best_sens['min_confidence']:.2f}**.

Lectura recomendada:
1. Mantener solo reglas que pasen umbrales de calidad para reducir ruido.
2. Priorizar estabilidad (Jaccard) y confianza en test sobre cantidad total de reglas.
3. Si Apriori y FPGrowth empatan en calidad, elegir por tiempo de ejecucion.

## Conclusion ejecutiva
- Semaforo: **{semaforo}**.
- Estado: **{estado}**.
'''
    )
)
"""
        ),
    ]
    return notebook_dict(cells)


def build_anomaly_notebook():
    cells = [
        md_cell(
            """
# Benchmark de anomalias (PostgreSQL)

Este notebook ejecuta benchmark y sensibilidad de detectores de anomalias, incluyendo candidatos basados en PCA.
"""
        ),
        code_cell(
            """
from pathlib import Path
import sys
import warnings

import matplotlib.pyplot as plt
import pandas as pd
from IPython.display import Markdown, display

warnings.filterwarnings("ignore")

CWD = Path.cwd().resolve()
candidates = [
    CWD,
    CWD.parent,
    CWD / "03_modelado" / "proyecto_ml_experimentos",
]
ROOT = next((p for p in candidates if (p / "src" / "anomaly.py").exists()), None)
if ROOT is None:
    raise RuntimeError("No se encontro la raiz de proyecto_ml_experimentos (src/anomaly.py).")

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

for m in ["src", "src.datasets_postgres", "src.anomaly"]:
    if m in sys.modules:
        del sys.modules[m]

from src.datasets_postgres import load_anomaly_dataset
from src.anomaly import benchmark_anomaly, benchmark_anomaly_sensitivity
"""
        ),
        code_cell(
            """
df = load_anomaly_dataset()
display(df.head())

display(
    Markdown(
        f'''
### Calidad del dataset
- Filas (agencias): **{len(df):,}**
- Agencias unicas: **{df['agencia'].nunique():,}**
- Features usadas: `ratio_devolucion`, `ratio_rentabilidad`, `ratio_costo`, `ticket_promedio`
'''
    )
)
"""
        ),
        code_cell(
            """
res = benchmark_anomaly(df, contamination=0.10)
sens = benchmark_anomaly_sensitivity(df, contamination_grid=(0.05, 0.10, 0.15))

models_dir = ROOT / "models"
models_dir.mkdir(exist_ok=True)
charts_dir = ROOT.parents[1] / "05_evidencias" / "graficas"
charts_dir.mkdir(parents=True, exist_ok=True)
res.to_csv(models_dir / "benchmark_anomaly.csv", index=False)
sens.to_csv(models_dir / "benchmark_anomaly_sensitivity.csv", index=False)

display(res)
display(sens.head(15))
"""
        ),
        code_cell(
            """
plt.figure(figsize=(9, 4))
plt.bar(res["algoritmo"], res["score_general"])
plt.title("Score general por algoritmo")
plt.ylabel("score_general")
plt.xticks(rotation=25, ha="right")
plt.tight_layout()
plt.savefig(charts_dir / "anomaly_score_por_algoritmo.png", dpi=150)
plt.show()

for algo, sub in sens.groupby("algoritmo"):
    tmp = sub.sort_values("contamination")
    plt.plot(tmp["contamination"], tmp["score_general"], marker="o", label=algo)
plt.title("Sensibilidad: contamination vs score_general")
plt.xlabel("contamination")
plt.ylabel("score_general")
plt.legend(bbox_to_anchor=(1.02, 1), loc="upper left")
plt.tight_layout()
plt.savefig(charts_dir / "anomaly_sensibilidad_contamination.png", dpi=150)
plt.show()

display(Markdown(f"Graficas guardadas en: `{charts_dir}`"))
"""
        ),
        code_cell(
            """
best = res.sort_values("score_general", ascending=False).iloc[0]

if float(best["bootstrap_jaccard_top_anomalias"]) >= 0.6 and float(best["desviacion_target_contamination"]) <= 0.02:
    semaforo = "VERDE"
    estado = "detector estable y alineado al nivel de alertas objetivo"
elif float(best["bootstrap_jaccard_top_anomalias"]) >= 0.35 and float(best["desviacion_target_contamination"]) <= 0.05:
    semaforo = "AMARILLO"
    estado = "detector util, pero requiere validacion manual recurrente"
else:
    semaforo = "ROJO"
    estado = "detector inestable o con volumen de alertas no controlado"

display(
    Markdown(
        f'''
## Interpretacion
- Mejor algoritmo en este corte: **{best['algoritmo']}**.
- `score_general`: **{best['score_general']:.4f}**.
- `% anomalias detectadas`: **{best['pct_anomalias']:.4f}**.
- Estabilidad bootstrap (Jaccard top anomalias): **{best['bootstrap_jaccard_top_anomalias']:.4f}**.

Lectura recomendada:
1. Validar manualmente las anomalias top en negocio antes de accionar.
2. Comparar estabilidad mensual para detectar deriva.
3. Recordar que con pocas agencias la varianza del ranking puede subir.

## Conclusion ejecutiva
- Semaforo: **{semaforo}**.
- Estado: **{estado}**.
'''
    )
)
"""
        ),
    ]
    return notebook_dict(cells)


def main():
    root = Path(__file__).resolve().parents[1]
    notebooks_dir = root / "notebooks"
    notebooks_dir.mkdir(exist_ok=True)

    targets = {
        notebooks_dir / "experiments_forecasting.ipynb": build_forecasting_notebook(),
        notebooks_dir / "experiments_association.ipynb": build_association_notebook(),
        notebooks_dir / "experiments_anomaly.ipynb": build_anomaly_notebook(),
    }

    for path, nb in targets.items():
        path.write_text(json.dumps(nb, ensure_ascii=True, indent=1), encoding="utf-8")
        print(f"Notebook actualizado: {path}")


if __name__ == "__main__":
    main()
