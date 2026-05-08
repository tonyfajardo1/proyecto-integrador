# Forecasting Tesis V2 (Limpio)

Proyecto reiniciado para forecasting, paso a paso y con trazabilidad.

## Objetivo

Construir un pipeline de pronostico de produccion defendible para tesis:

1. Analisis exploratorio (EDA)
2. Data wrangling y calidad
3. Feature engineering temporal
4. Entrenamiento y comparacion de modelos
5. Evaluacion temporal y seleccion final

## Estructura

- `notebooks/01_eda.ipynb`: analisis exploratorio inicial
- `notebooks/02_wrangling.ipynb`: limpieza y calidad pre-modelado
- `notebooks/03_modeling_evaluation.ipynb`: entrenamiento y evaluacion
- `src/db.py`: utilidades de conexion y lectura SQL a DataFrame
- `src/data_source.py`: carga de datos (`dwh` o `dwh_forecasting_v1`)
- `src/eda.py`: utilidades EDA
- `src/wrangling.py`: utilidades de limpieza/wrangling
- `src/modeling.py`: features + benchmark final con controles anti-leakage
- `scripts/run_modeling.py`: ejecucion no-interactiva de modelado
- `scripts/publish_predictions_to_gold.py`: publicacion de predicciones a Gold
- `scripts/export_catalog_quality_reports.py`: reportes de calidad de catalogo/estado
- `artifacts/`: salidas de notebooks y scripts

## Regla metodologica

- ETL (Mage) aporta capa curada base.
- Este proyecto valida y prepara los datos especificamente para modelado.
- Toda transformacion que dependa de train/val/test se hace dentro del flujo de modelado para evitar leakage.

## Paso 1 (ahora)

Ejecutar `notebooks/01_eda.ipynb` y revisar:

- cobertura temporal,
- duplicados producto-periodo,
- ausentes,
- distribuciones,
- volatilidad por producto.

## Flujo recomendado

1. `notebooks/01_eda.ipynb`
2. `notebooks/02_wrangling.ipynb`
3. `notebooks/03_modeling_evaluation.ipynb`

O ejecucion por script:

```bash
python scripts/run_modeling.py
```

Para forzar la fuente legacy de produccion mensual:

```bash
python scripts/run_modeling.py --source dwh
```

Para usar la nueva base canonica por EAN/codigo en Silver:

```bash
python scripts/run_modeling.py --source dwh_forecasting_v1
```

Salidas principales:

- `artifacts/benchmark_forecasting_v2.csv`
- `artifacts/predicciones_forecasting_v2.csv`
- `artifacts/leakage_report.csv`

## Metricas y comparacion de modelos

- Metricas oficiales: `MAE`, `RMSE`, `WAPE`.
- Criterio de seleccion: menor `WAPE_val` (validacion temporal).
- Evidencia completa: `artifacts/benchmark_forecasting_v2.csv`.
- Ranking reciente (corrida actual): `LinearRegression` como ganador por `WAPE_val`.
