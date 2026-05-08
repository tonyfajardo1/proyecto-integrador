# Tesis Forecasting (QuickBooks)

Pipeline especializado de pronostico de produccion para defensa de tesis.

## Objetivo

Predecir `qty_fabricada` a horizonte t+1 por producto usando solo informacion historica (sin leakage), con evaluacion temporal, sensibilidad y trazabilidad de experimentos.

## Enfoque metodologico

- Fuente por defecto: `silver.produccion_modelado_mensual` (DWH local)
- Fallback opcional: `quickbooks.produccion` (si DWH no esta disponible)
- Serie de tiempo por producto (grano mensual)
- Features historicas:
  - `lag_1`, `lag_2`, `lag_3`
  - `rolling_mean_3`
  - `rolling_std_3`
  - `delta_1`
  - `qty_planificada_lag_1`, `n_ordenes_lag_1`
  - `mes_num`, `anio_num`
- Variables de negocio:
  - `alpha` (nivel de servicio)
  - `stock_respaldo = z(alpha) * rolling_std_3 * sqrt(lead_time)`
  - `qty_recomendada = pronostico + stock_respaldo`

## Modelos candidatos

- `LinearRegression`
- `RandomForestRegressor`
- `ExtraTreesRegressor`
- `Prophet` (si esta instalado)
- `Ensemble_RF_ET_LR` (promedio ponderado)
- `Baseline_Lag1`

## Evaluacion

- Split temporal train/val/test
- Metricas: `WAPE`, `MAE`, `RMSE`
- Brechas: `gap_wape_train_val`, `gap_wape_val_test`
- Drift:
  - PSI por feature
  - Log de drift en `artifacts/drift_log.csv`

## MLflow

El pipeline soporta MLflow de forma opcional:

- Si `mlflow` esta instalado y `use_mlflow=True`, registra params, metricas y artefactos.
- Si no esta instalado, continua en modo local sin bloquear ejecucion.

## Estructura

- `src/postgres_loader.py`: conexion y queries PostgreSQL
- `src/dataset.py`: carga y agregacion mensual QuickBooks
- `src/wrangling.py`: limpieza y preparacion avanzada para modelado
- `src/quality.py`: checklist de calidad (precision y completitud) pre/post wrangling
- `src/features.py`: ingenieria temporal y stock de respaldo
- `src/evaluation.py`: metricas y split temporal
- `src/models.py`: modelos, Prophet y ensamblador
- `src/pipeline.py`: orquestacion completa
- `scripts/run_forecasting_thesis.py`: ejecucion principal
- `notebooks/exploration_forecasting_tesis.ipynb`: EDA de forecasting
- `notebooks/data_wrangling_forecasting_tesis.ipynb`: wrangling reproducible
- `artifacts/`: salidas (`benchmark`, `predicciones`, `drift_log`)

### Artefactos de calidad (notebook wrangling)

- `artifacts/quality_report_raw.csv`
- `artifacts/quality_report_wrangled.csv`
- `artifacts/quality_report_comparison.csv`

## Ejecucion

Desde `03_modelado/tesis_forecasting`:

```bash
python scripts/run_forecasting_thesis.py
```

La funcion principal acepta `source='dwh'` (recomendado) o `source='quickbooks'`.

## Prueba A/B de imputacion

Comparacion entre:

- A: `wrangling_mode=zero` + `model_imputer_strategy=zero`
- B: `wrangling_mode=temporal` + `model_imputer_strategy=median` (SimpleImputer sklearn)

Ejecucion:

```bash
python scripts/run_imputation_ab_test.py
```

Salida principal:

- `artifacts/imputation_ab_summary.csv`
