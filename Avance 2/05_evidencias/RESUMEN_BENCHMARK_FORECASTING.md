# Benchmark Pronostico

- Baseline: `Baseline_Lag1`.
- Modelos evaluados: `RandomForest`, `ExtraTrees`, `GradientBoosting`, `LinearRegression`, `Ridge`, `ElasticNet` (con pipeline y escalado para lineales).
- Seleccion por `WAPE` en validacion y reporte final en test con reentrenamiento train+validation.

## Resultado principal

- Mejor modelo en test: `ExtraTrees`.
- `WAPE test`: `0.3774` vs baseline `0.4445` (mejora absoluta `+0.0671`).

## Sensibilidad y brechas train/val/test

Archivo de sensibilidad: `03_modelado/proyecto_ml_experimentos/models/benchmark_forecasting_sensitivity.csv`

| modelo | WAPE_train | WAPE_val | WAPE_test | gap_train_val | gap_val_test |
| --- | --- | --- | --- | --- | --- |
| ExtraTrees (min_leaf=2, n_estimators=300) | 0.1212 | 0.3277 | 0.3774 | 0.2065 | 0.0496 |
| RandomForest (min_leaf=2, n_estimators=500) | 0.1689 | 0.3338 | 0.3867 | 0.1648 | 0.0530 |
| GradientBoosting (default) | 0.2756 | 0.3492 | 0.3927 | 0.0737 | 0.0434 |
| Mejor ElasticNet (alpha=1.0, l1=0.8) | 0.4140 | 0.3758 | 0.4083 | -0.0381 | 0.0325 |
| Baseline_Lag1 | 0.4348 | 0.3688 | 0.4445 | -0.0661 | 0.0757 |

## Interpretacion

- Los modelos de arbol siguen dominando en `WAPE` test.
- Los lineales regularizados quedan por encima del baseline en test, pero no superan a ExtraTrees/RandomForest.
- Se observa brecha train-val relevante en arboles (sobreajuste controlado), por eso se mantiene seleccion por validacion y confirmacion en test.

## Checklist transversal (obligatorio)

- Antes de publicar resultados finales, completar y adjuntar evidencia de `03_modelado/CHECKLIST_ANTI_LEAKAGE_Y_EVALUACION.md`.

## Fuente

- `03_modelado/proyecto_ml_experimentos/models/benchmark_forecasting.csv`
- `03_modelado/proyecto_ml_experimentos/models/benchmark_forecasting_sensitivity.csv`
