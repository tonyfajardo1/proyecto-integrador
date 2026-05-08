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


def build_quickbooks_notebook():
    cells = [
        md_cell(
            """
# Exploracion - QuickBooks

Analisis exploratorio para preparar modelado de pronostico: calidad, semantica de producto, vigencia y estabilidad temporal.
"""
        ),
        code_cell(
            '''
from pathlib import Path
import re
import sys
import warnings

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from IPython.display import Markdown, display

warnings.filterwarnings("ignore")
sns.set_theme(style="whitegrid")

CWD = Path.cwd().resolve()
candidates = [CWD, CWD.parent, CWD / "03_modelado" / "proyecto_ml_experimentos"]
ROOT = next((p for p in candidates if (p / "src" / "datasets_postgres.py").exists()), None)
if ROOT is None:
    raise RuntimeError("No se encontro la raiz de proyecto_ml_experimentos.")

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

for m in ["src", "src.datasets_postgres", "src.postgres_loader"]:
    if m in sys.modules:
        del sys.modules[m]

from src.datasets_postgres import load_forecasting_dataset
from src.postgres_loader import load_dwh_query, load_quickbooks_query

charts_dir = ROOT.parents[1] / "05_evidencias" / "graficas"
charts_dir.mkdir(parents=True, exist_ok=True)
'''
        ),
        code_cell(
            '''
df_monthly = load_forecasting_dataset()

df_raw = load_quickbooks_query(
    """
    SELECT producto, fecha, qty_planificada, qty_fabricada
    FROM quickbooks.produccion
    WHERE producto IS NOT NULL AND fecha IS NOT NULL
    """
)

df_raw["producto"] = df_raw["producto"].astype(str).str.strip()
df_raw["fecha"] = pd.to_datetime(df_raw["fecha"], errors="coerce")
for c in ["qty_planificada", "qty_fabricada"]:
    df_raw[c] = pd.to_numeric(df_raw[c], errors="coerce").fillna(0)

df_raw = df_raw[(df_raw["producto"] != "") & df_raw["fecha"].notna()].copy()

display(df_monthly.head())
display(df_raw.head())
'''
        ),
        code_cell(
            '''
def tipo_producto(name):
    s = str(name).upper().strip()
    if s.startswith("PP"):
        return "PP"
    if s.startswith("PT"):
        return "PT"
    return "OTRO"


def producto_norm(name):
    s = str(name).upper()
    s = re.sub(r"\\s+", " ", s).strip()
    s = re.sub(r"^\\*+", "", s).strip()
    s = re.sub(r"\\bEXTR\\b", "EXT", s)
    s = re.sub(r"[^A-Z0-9 ]", "", s)
    s = re.sub(r"\\s+", " ", s).strip()
    return s


df_raw["tipo_producto"] = df_raw["producto"].apply(tipo_producto)
df_raw["producto_base_norm"] = df_raw["producto"].apply(producto_norm)

raw_rows = len(df_raw)
raw_prod = df_raw["producto"].nunique()
raw_prod_norm = df_raw["producto_base_norm"].nunique()
dup_exact = int(df_raw.duplicated(subset=["producto", "fecha", "qty_planificada", "qty_fabricada"]).sum())
gap_sem = int(raw_prod - raw_prod_norm)

display(
    Markdown(
        f"""
## Calidad base QuickBooks
- Filas crudas: **{raw_rows:,}**
- Productos crudos: **{raw_prod:,}**
- Productos normalizados: **{raw_prod_norm:,}**
- Brecha semantica (crudo-normalizado): **{gap_sem:,}**
- Duplicados exactos (`producto,fecha,qty_planificada,qty_fabricada`): **{dup_exact:,}**

## Dataset mensual de modelado
- Filas: **{len(df_monthly):,}**
- Productos: **{df_monthly['producto'].nunique():,}**
- Periodos: **{df_monthly['periodo'].nunique():,}**
- Rango: **{df_monthly['periodo'].min().date()}** a **{df_monthly['periodo'].max().date()}**
"""
    )
)

display(df_raw["tipo_producto"].value_counts(dropna=False).rename_axis("tipo").to_frame("conteo"))
'''
        ),
        code_cell(
            '''
max_period = df_monthly["periodo"].max()
last_prod = df_monthly.groupby("producto", as_index=False)["periodo"].max().rename(columns={"periodo": "ultimo_periodo"})
last_prod["meses_desfase"] = (
    max_period.to_period("M") - last_prod["ultimo_periodo"].dt.to_period("M")
).apply(lambda x: x.n)
last_prod["es_vigente_3m"] = last_prod["meses_desfase"] <= 2

display(
    Markdown(
        f"""
## Vigencia operativa
- Periodo global mas reciente: **{max_period.date()}**
- Productos vigentes (<=2 meses): **{int(last_prod['es_vigente_3m'].sum()):,}**
- Productos fuera de ventana: **{int((~last_prod['es_vigente_3m']).sum()):,}**
"""
    )
)

display(last_prod.sort_values("meses_desfase", ascending=False).head(15))
'''
        ),
        code_cell(
            '''
fig, axes = plt.subplots(1, 2, figsize=(12, 4))
sns.histplot(df_monthly["qty_fabricada"], bins=40, ax=axes[0], color="#1f77b4")
axes[0].set_title("Distribucion qty_fabricada")
sns.histplot(df_monthly["qty_planificada"], bins=40, ax=axes[1], color="#ff7f0e")
axes[1].set_title("Distribucion qty_planificada")
plt.tight_layout()
plt.savefig(charts_dir / "eda_quickbooks_distribuciones_qty.png", dpi=150)
plt.show()

monthly = (
    df_monthly.groupby("periodo", as_index=False)[["qty_fabricada", "qty_planificada"]]
    .sum()
    .sort_values("periodo")
)
plt.figure(figsize=(12, 4))
plt.plot(monthly["periodo"], monthly["qty_fabricada"], marker="o", label="Fabricada")
plt.plot(monthly["periodo"], monthly["qty_planificada"], marker="o", label="Planificada")
plt.title("Tendencia mensual total QuickBooks")
plt.legend()
plt.tight_layout()
plt.savefig(charts_dir / "eda_quickbooks_tendencia_mensual.png", dpi=150)
plt.show()
'''
        ),
        code_cell(
            '''
stats_prod = (
    df_monthly.groupby("producto", as_index=False)
    .agg(
        media_fabricada=("qty_fabricada", "mean"),
        std_fabricada=("qty_fabricada", "std"),
        media_planificada=("qty_planificada", "mean"),
        periodos=("periodo", "nunique"),
    )
)
stats_prod["std_fabricada"] = stats_prod["std_fabricada"].fillna(0)
stats_prod["cv_fabricada"] = np.where(
    stats_prod["media_fabricada"] > 0,
    stats_prod["std_fabricada"] / stats_prod["media_fabricada"],
    np.nan,
)

display(Markdown("## Top productos por volumen"))
display(stats_prod.sort_values("media_fabricada", ascending=False).head(15))

display(Markdown("## Top productos por volatilidad (CV)"))
display(stats_prod.dropna(subset=["cv_fabricada"]).sort_values("cv_fabricada", ascending=False).head(15))
'''
        ),
        code_cell(
            '''
gold_prod = load_dwh_query(
    """
    SELECT cliente, qty_total_planificada, qty_total_despachada, tasa_cumplimiento, num_ordenes
    FROM gold.kpis_produccion
    """
)
for c in ["qty_total_planificada", "qty_total_despachada", "tasa_cumplimiento", "num_ordenes"]:
    gold_prod[c] = pd.to_numeric(gold_prod[c], errors="coerce").fillna(0)

display(
    Markdown(
        f"""
## Contraste con Gold
- Filas `gold.kpis_produccion`: **{len(gold_prod):,}**
- Cumplimiento promedio: **{gold_prod['tasa_cumplimiento'].mean():.2f}**
- Cumplimiento max: **{gold_prod['tasa_cumplimiento'].max():.2f}**
"""
    )
)

display(gold_prod.describe(include="all").T)
'''
        ),
        code_cell(
            '''
no_vigentes = int((~last_prod["es_vigente_3m"]).sum())
riesgo_sem = "ALTO" if gap_sem > 0 else "BAJO"
riesgo_vig = "ALTO" if no_vigentes > 0 else "BAJO"

display(
    Markdown(
        f"""
## Conclusiones para modelado QuickBooks
1. Usar `load_forecasting_dataset` como base principal para entrenamiento de pronostico.
2. Riesgo semantico de productos: **{riesgo_sem}**.
3. Riesgo de vigencia operativa: **{riesgo_vig}** (fuera de ventana: **{no_vigentes:,}**).
4. Regla sugerida: excluir o separar SKU fuera de ventana (>2 meses) en plan operativo.
5. Gold sirve para contraste ejecutivo, no para reemplazar la granularidad de entrenamiento.

Graficas guardadas en: `{charts_dir}`
"""
    )
)
'''
        ),
    ]
    return notebook_dict(cells)


def build_kronos_notebook():
    cells = [
        md_cell(
            """
# Exploracion - Kronos

Analisis exploratorio para preparar modelado de asociacion y anomalias con foco en calidad de ventas/devoluciones.
"""
        ),
        code_cell(
            '''
from pathlib import Path
import sys
import warnings

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from IPython.display import Markdown, display

warnings.filterwarnings("ignore")
sns.set_theme(style="whitegrid")

CWD = Path.cwd().resolve()
candidates = [CWD, CWD.parent, CWD / "03_modelado" / "proyecto_ml_experimentos"]
ROOT = next((p for p in candidates if (p / "src" / "postgres_loader.py").exists()), None)
if ROOT is None:
    raise RuntimeError("No se encontro la raiz de proyecto_ml_experimentos.")

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

for m in ["src", "src.postgres_loader"]:
    if m in sys.modules:
        del sys.modules[m]

from src.postgres_loader import load_dwh_query

charts_dir = ROOT.parents[1] / "05_evidencias" / "graficas"
charts_dir.mkdir(parents=True, exist_ok=True)
'''
        ),
        code_cell(
            '''
kronos = load_dwh_query(
    """
    SELECT centro_costo, codigo_producto, codigo_alterno, producto, mes, anio,
           cant_venta, total_venta, cant_devolucion, total_devolucion,
           cant_neto, total_neto, flag_outlier
    FROM silver.kronos_ventas
    """
)

apriori_tx = load_dwh_query(
    """
    SELECT transaccion_id, producto, fecha
    FROM silver.apriori_transacciones
    """
)

gold_kpis = load_dwh_query(
    """
    SELECT centro_costo, producto, anio, mes, cant_venta, total_venta,
           cant_neto, total_neto, cant_devolucion, total_devolucion,
           tasa_devolucion_cant, tasa_devolucion_valor
    FROM gold.kpis_ventas
    """
)

gold_agencias = load_dwh_query(
    """
    SELECT centro_costo, total_venta, total_neto, total_devolucion,
           rentabilidad, ticket_promedio, tasa_devolucion, rentabilidad_promedio
    FROM gold.metricas_agencias
    """
)

for c in ["cant_venta", "total_venta", "cant_devolucion", "total_devolucion", "cant_neto", "total_neto"]:
    kronos[c] = pd.to_numeric(kronos[c], errors="coerce").fillna(0)

for c in ["cant_venta", "total_venta", "cant_devolucion", "total_devolucion", "cant_neto", "total_neto", "tasa_devolucion_cant", "tasa_devolucion_valor"]:
    gold_kpis[c] = pd.to_numeric(gold_kpis[c], errors="coerce").fillna(0)

for c in ["total_venta", "total_neto", "total_devolucion", "rentabilidad", "ticket_promedio", "tasa_devolucion", "rentabilidad_promedio"]:
    gold_agencias[c] = pd.to_numeric(gold_agencias[c], errors="coerce").fillna(0)

display(kronos.head())
display(apriori_tx.head())
display(gold_agencias.head())
'''
        ),
        code_cell(
            '''
null_key = int(((kronos["centro_costo"].astype(str).str.strip() == "") | (kronos["producto"].astype(str).str.strip() == "")).sum())
dup_key = int(kronos.duplicated(subset=["centro_costo", "codigo_producto", "mes", "anio"], keep=False).sum())
neg_net = int(((kronos["cant_neto"] < 0) | (kronos["total_neto"] < 0)).sum())
dev_gt_sale = int(((kronos["cant_devolucion"] > kronos["cant_venta"]) | (kronos["total_devolucion"] > kronos["total_venta"])).sum())
outliers = int(kronos.get("flag_outlier", pd.Series([False] * len(kronos))).fillna(False).astype(bool).sum())

display(
    Markdown(
        f"""
## Calidad Silver Kronos
- Filas: **{len(kronos):,}**
- Agencias: **{kronos['centro_costo'].nunique():,}**
- Productos: **{kronos['producto'].nunique():,}**
- Nulos/vacios en claves: **{null_key:,}**
- Duplicados por (`centro_costo,codigo_producto,mes,anio`): **{dup_key:,}**
- Netos negativos: **{neg_net:,}**
- Devolucion > venta (cantidad o valor): **{dev_gt_sale:,}**
- Filas con `flag_outlier`: **{outliers:,}**
"""
    )
)

tx_uniq = apriori_tx.drop_duplicates(subset=["transaccion_id", "producto"]).shape[0]
display(
    Markdown(
        f"""
## Calidad Silver Apriori
- Filas: **{len(apriori_tx):,}**
- Transacciones: **{apriori_tx['transaccion_id'].nunique():,}**
- Productos: **{apriori_tx['producto'].nunique():,}**
- Duplicados exactos (`transaccion_id`,`producto`): **{len(apriori_tx) - tx_uniq:,}**
"""
    )
)
'''
        ),
        code_cell(
            '''
month_map = {
    "ENERO": 1, "FEBRERO": 2, "MARZO": 3, "ABRIL": 4, "MAYO": 5, "JUNIO": 6,
    "JULIO": 7, "AGOSTO": 8, "SEPTIEMBRE": 9, "SETIEMBRE": 9, "OCTUBRE": 10,
    "NOVIEMBRE": 11, "DICIEMBRE": 12,
}

tmp = kronos.copy()
tmp["mes_num"] = tmp["mes"].astype(str).str.upper().map(month_map)
tmp["periodo"] = pd.to_datetime(
    tmp["anio"].astype("Int64").astype(str) + "-" + tmp["mes_num"].astype("Int64").astype(str).str.zfill(2) + "-01",
    errors="coerce",
)

monthly = (
    tmp.dropna(subset=["periodo"]).groupby("periodo", as_index=False)[["total_venta", "total_devolucion", "total_neto"]].sum().sort_values("periodo")
)

plt.figure(figsize=(12, 4))
plt.plot(monthly["periodo"], monthly["total_venta"], marker="o", label="Venta")
plt.plot(monthly["periodo"], monthly["total_devolucion"], marker="o", label="Devolucion")
plt.plot(monthly["periodo"], monthly["total_neto"], marker="o", label="Neto")
plt.title("Tendencia mensual Silver Kronos")
plt.legend()
plt.tight_layout()
plt.savefig(charts_dir / "eda_kronos_tendencia_mensual.png", dpi=150)
plt.show()

plt.figure(figsize=(8, 4))
sns.histplot(kronos["total_venta"], bins=40, color="#2ca02c")
plt.title("Distribucion total_venta")
plt.tight_layout()
plt.savefig(charts_dir / "eda_kronos_distribucion_total_venta.png", dpi=150)
plt.show()
'''
        ),
        code_cell(
            '''
ag = (
    kronos.groupby("centro_costo", as_index=False)
    .agg(total_venta=("total_venta", "sum"), total_devolucion=("total_devolucion", "sum"), total_neto=("total_neto", "sum"))
)
ag["tasa_dev"] = np.where(ag["total_venta"] > 0, ag["total_devolucion"] / ag["total_venta"], np.nan)

display(Markdown("## Top agencias por venta"))
display(ag.sort_values("total_venta", ascending=False).head(10))

display(Markdown("## Top agencias por tasa de devolucion"))
display(ag.sort_values("tasa_dev", ascending=False).head(10))

cmp = pd.DataFrame(
    [{
        "silver_total_venta": float(kronos["total_venta"].sum()),
        "gold_total_venta": float(gold_kpis["total_venta"].sum()),
        "silver_total_devolucion": float(kronos["total_devolucion"].sum()),
        "gold_total_devolucion": float(gold_kpis["total_devolucion"].sum()),
    }]
)
display(Markdown("## Contraste Silver vs Gold"))
display(cmp)
'''
        ),
        code_cell(
            '''
tx_size = apriori_tx.groupby("transaccion_id")["producto"].nunique()

plt.figure(figsize=(8, 4))
sns.histplot(tx_size, bins=30, color="#9467bd")
plt.title("Productos por transaccion (apriori)")
plt.tight_layout()
plt.savefig(charts_dir / "eda_kronos_apriori_productos_por_transaccion.png", dpi=150)
plt.show()

display(
    Markdown(
        f"""
## Lectura para asociacion
- Transacciones con >=2 productos: **{int((tx_size >= 2).sum()):,}**
- Promedio productos por transaccion: **{tx_size.mean():.2f}**
- P95 productos por transaccion: **{tx_size.quantile(0.95):.2f}**
"""
    )
)
'''
        ),
        code_cell(
            '''
riesgo = "ALTO" if (dup_key > 0 or dev_gt_sale > 0) else "BAJO"
apto_asoc = "SI" if int((tx_size >= 2).sum()) > 100 else "NO"

display(
    Markdown(
        f"""
## Conclusiones para modelado Kronos
1. Asociacion: usar `silver.apriori_transacciones` como fuente base.
2. Anomalias: usar `gold.metricas_agencias` para monitoreo y `silver.kronos_ventas` para explicabilidad.
3. Riesgo de calidad Silver: **{riesgo}**.
4. Dataset apto para asociacion multi-producto: **{apto_asoc}**.
5. Gold se usa para cierre ejecutivo y validacion de consistencia.

Graficas guardadas en: `{charts_dir}`
"""
    )
)
'''
        ),
    ]
    return notebook_dict(cells)


def main():
    root = Path(__file__).resolve().parents[1]
    notebooks_dir = root / "notebooks"
    notebooks_dir.mkdir(exist_ok=True)

    targets = {
        notebooks_dir / "exploration_quickbooks.ipynb": build_quickbooks_notebook(),
        notebooks_dir / "exploration_kronos.ipynb": build_kronos_notebook(),
    }

    for path, nb in targets.items():
        path.write_text(json.dumps(nb, ensure_ascii=True, indent=1), encoding="utf-8")
        print(f"Notebook generado: {path}")


if __name__ == "__main__":
    main()
