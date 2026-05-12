# Forecasting v3

`forecasting_v3` es la version final del pipeline de pronostico defendida en la
tesis. Su objetivo es estimar demanda y necesidades de produccion para dos
grupos:

- `PT`: productos terminados, entrenados desde historico de ventas.
- `PP`: productos/proceso, entrenados desde historico de produccion.

## Que resuelve esta version

Frente a iteraciones anteriores, esta version se centra en:

- reducir riesgo de leakage;
- seleccionar modelos con validacion temporal;
- separar claramente PT y PP;
- medir estabilidad con walk-forward;
- llevar el forecast a una recomendacion operativa consumible.

## Estructura

```text
forecasting_v3/
|- config/
|- data/
|  |- input/
|  |- processed/
|- models/
|- notebooks/
|- reports/
|- src/quickbooks_forecast/
|- README.md
```

## Subcarpetas importantes

- `src/quickbooks_forecast/`: paquete principal del forecasting.
- `notebooks/`: trazabilidad metodologica paso a paso.
- `reports/`: metricas, comparaciones, SHAP, walk-forward y predicciones.
- `config/config.yml`: parametros del pipeline.

## Flujo metodologico

1. construir datasets PT y PP;
2. generar features temporales y exogenas previas;
3. reservar holdout final;
4. seleccionar el modelo con CV temporal;
5. evaluar estabilidad con walk-forward;
6. entrenar artefacto final;
7. generar predicciones y reglas de decision.

## Resultados finales

- `PT`: `WAPE = 0.0580`
- `PP`: `WAPE = 0.0601`
- modelo ganador:
  - `RandomForest`

## Reportes que conviene revisar

- `reports/metrics_pt.csv`
- `reports/metrics_pp.csv`
- `reports/temporal_cv_model_comparison_all.csv`
- `reports/walk_forward_segment_summary_all.csv`
- `reports/shap_global_importance_pt.csv`
- `reports/shap_global_importance_pp.csv`
- `reports/predicciones_pt.csv`
- `reports/predicciones_pp.csv`

## Como ejecutar y entender el proyecto

### Ruta academica

Lee los notebooks en este orden:

1. `notebooks/01_exploracion_datos.ipynb`
2. `notebooks/02_limpieza_y_catalogo.ipynb`
3. `notebooks/03_entrenamiento_modelos.ipynb`
4. `notebooks/04_resultados_y_predicciones.ipynb`

### Ruta operativa

En el proyecto final, la ejecucion productiva no se hace desde scripts
standalone, sino desde Mage mediante el pipeline
`forecasting_v3_quickbooks`.

## Navegacion recomendada

- revisa [notebooks/README.md](notebooks/README.md) si quieres seguir el flujo
  explicativo;
- revisa [src/quickbooks_forecast/README.md](src/quickbooks_forecast/README.md)
  si quieres entender el paquete Python;
- revisa `reports/` si solo quieres resultados y evidencia.
