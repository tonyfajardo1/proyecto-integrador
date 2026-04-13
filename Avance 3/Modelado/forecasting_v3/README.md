# Prediccion de produccion con datos QuickBooks

Este proyecto toma los archivos de `Quickbooks/` y genera un flujo end-to-end parecido al repo de referencia: datos crudos, limpieza, datasets procesados, entrenamiento y predicciones.

El objetivo es predecir la cantidad a producir por producto en dos salidas:

- `PT`: productos terminados, entrenados con historico de ventas.
- `PP`: productos en proceso, entrenados con historico de produccion.

## Reglas principales

- Los `PT` se validan contra el catalogo `ean 13 ean 14 pvp.xlsx`.
- Los `PP` salen de `PRODUCCION2025.xlsx`, filtrando productos que empiezan con `PP`.
- Los nombres se normalizan quitando tildes, signos, espacios dobles y diferencias como `*`, puntos o parentesis.
- Los duplicados por nombre normalizado se agrupan en una sola serie mensual.
- Un producto se marca como `inactivo` si no tuvo actividad en los ultimos 12 meses disponibles de su propia fuente.
- Un producto se marca como `estacional` si concentra al menos 60% de su volumen en sus 3 meses mas fuertes o si normalmente se mueve en 4 meses o menos por año.

## Estructura

```text
Quickbooks/                 archivos originales
config/config.yml           parametros del proyecto
src/quickbooks_forecast/    codigo reutilizable
scripts/                    comandos ejecutables
notebooks/                  explicacion paso a paso del proyecto
data/processed/             datasets listos para modelo
models/                     modelos entrenados
reports/                    metricas, reportes y predicciones
```

## Ejecutar todo

```bash
python3 scripts/run_all.py
```

## Ejecutar por pasos

```bash
python3 scripts/01_build_datasets.py
python3 scripts/02_train_models.py
python3 scripts/03_predict.py
python3 scripts/04_prepare_decision_inputs.py
```

## Validar notebooks

```bash
python3 -B scripts/run_notebooks.py
```

## Archivos importantes generados

- `data/processed/pt_mensual_model.csv`: serie mensual PT lista para entrenar.
- `data/processed/pp_mensual_model.csv`: serie mensual PP lista para entrenar.
- `data/processed/pt_productos_model.csv`: catalogo PT usado por el modelo con estado y estacionalidad.
- `data/processed/pp_productos_model.csv`: catalogo PP usado por el modelo con estado y estacionalidad.
- `reports/pt_productos_no_catalogo.csv`: productos vendidos que no se pudieron empatar con el catalogo EAN.
- `reports/metrics_pt.csv` y `reports/metrics_pp.csv`: evaluacion de cada modelo.
- `reports/model_comparison_all.csv`: comparacion de modelos ML.
- `reports/high_error_products_all.csv`: productos que requieren mayor revision por error historico.
- `reports/predicciones_pt.csv`: tabla final de prediccion PT.
- `reports/predicciones_pp.csv`: tabla final de prediccion PP.
- `reports/stock_actual_pt.csv` y `reports/stock_actual_pp.csv`: stock actual cruzado desde `Quickbooks/Costos.xlsx`.
- `reports/predicciones_quickbooks.xlsx`: workbook con hojas `PT` y `PP`.
- `data/input/validacion_expertos_template.csv`: plantilla para revision de produccion/comercial.
- `data/input/stock_min_max_template.csv`: plantilla para completar stock actual, minimo y maximo.
- `data/input/variables_exogenas_calendario.csv`: entrada para variables externas mensuales por PT/PP.
- `data/input/variables_exogenas_producto.csv`: entrada para variables externas por producto y mes.
- `reports/exogenous_variables_plan.md`: guia para completar variables exogenas sin fuga de informacion.

## Notebooks

Abre la carpeta `notebooks/` en VS Code y ejecutalos en este orden:

1. `01_exploracion_datos.ipynb`
2. `02_limpieza_y_catalogo.ipynb`
3. `03_entrenamiento_modelos.ipynb`
4. `04_resultados_y_predicciones.ipynb`

Los notebooks fueron adaptados del flujo del repo de referencia:

- EDA
- preparacion de datos
- experimentos/modelado
- presentacion de resultados

La diferencia es que este proyecto agrega un cuarto notebook para decision empresarial. El analisis de referencia esta en `reports/reference_repo_analysis.md`.

## Comparacion de modelos

El notebook 03 y `reports/model_comparison_all.csv` comparan solo modelos de Machine Learning:

- `hist_gradient_boosting`: modelo principal.
- `hist_gradient_boosting_tuned`: Gradient Boosting con tuning de hiperparametros.
- `random_forest`: bosque aleatorio no lineal.
- `random_forest_conservative`: bosque aleatorio mas regularizado para reducir sobreajuste.
- `extra_trees`: ensamble de arboles extremadamente aleatorizados.
- `linear_regression`: regresion lineal.
- `ridge_regression`: regresion lineal regularizada.
- `sgd_gradient_regression`: regresion lineal ajustada con descenso por gradiente.

La metrica principal es WAPE: error absoluto total dividido para volumen real total.

Por defecto `config/config.yml` usa `forecast_model: best_ml_stable`, es decir, las predicciones finales toman el modelo ML con menor peor-error entre validacion y test historico. Los metodos estadisticos simples no participan como candidatos.

El tuning de Gradient Boosting queda guardado en `reports/hgb_tuning_all.csv`. La comparacion de validacion queda en `reports/validation_model_comparison_all.csv`.

## Variables exogenas

El pipeline esta preparado para usar variables reales conocidas antes del mes a predecir. Si los archivos estan vacios, esas variables entran como cero y el proyecto corre igual. Para buscar una mejora fuerte, completa:

- `data/input/variables_exogenas_calendario.csv`: dias laborables, feriados, temporada alta, eventos comerciales, promociones generales y variacion de precio general.
- `data/input/variables_exogenas_producto.csv`: pedidos confirmados, preventa, promociones por producto, clientes grandes, cambio de PVP, precio planificado, riesgo de quiebre, disponibilidad de materia prima y ajustes comerciales conocidos.

Regla importante: no uses informacion que solo se conoce despues de cerrar el mes, porque eso causaria fuga de informacion y metricas artificialmente buenas.

Para pruebas de sensibilidad se puede generar un escenario asistido por planificacion humana con las mismas columnas exogenas:

```bash
python3 -B scripts/06_generate_ecuador_market_exogenous.py --replacement-demo
python3 -B scripts/run_all.py
python3 -B scripts/05_operational_evaluation.py
```

Ese modo simula que pedidos, preventas y ajustes comerciales contienen una propuesta operacional previa al mes, similar a la planificacion humana. Sirve para demostrar el umbral 5%-7% de reemplazo asistido; no debe presentarse como validacion oficial hasta reemplazar esos proxies por registros reales conocidos antes de producir.

Los reportes de apoyo para presentacion quedan en:

- `reports/exogenous_replacement_results.md`: resultados del escenario asistido 5%-7% WAPE.
- `reports/replacement_readiness.md`: interpretacion del umbral 5%-7% requerido para reemplazar la planificacion humana.

## Uso para decision

Antes de usar las predicciones como decision oficial:

- revisar `reports/high_error_products_all.csv`;
- completar `data/input/validacion_expertos_template.csv`;
- completar `data/input/stock_min_max_template.csv`;
- incorporar stock actual, stock minimo y stock maximo;
- validar ajustes con produccion/comercial.

Las predicciones ya incluyen campos de decision:

- `prediccion_min`
- `prediccion_max`
- `confianza_prediccion`
- `requiere_revision`
- `cantidad_sugerida_sin_inventario`
- `stock_actual`
- `cantidad_a_producir_ajustada`
- `stock_proyectado_inicio`
- `stock_proyectado_fin`
- `alerta_inventario`
- `recomendacion_decision`

El stock actual se toma de `Quickbooks/Costos.xlsx`, columna `On Hand`, usando la ultima fila disponible por item. La prediccion original no se reemplaza: el pipeline conserva `cantidad_predicha` como forecast de demanda y calcula `cantidad_a_producir_ajustada` como recomendacion operativa descontando el inventario disponible de forma secuencial en el horizonte.

## Ajustes utiles

Edita `config/config.yml` para cambiar:

- `forecast_horizon_months`: cuantos meses hacia adelante predecir.
- `inactive_months`: ventana para marcar inactividad.
- `include_unmatched_pt`: si quieres entrenar tambien con productos de ventas que no aparecen en el catalogo EAN.
- `forecast_model`: `best_ml_stable` para escoger automaticamente el modelo ML mas estable, `best_ml_validation`, `best_ml_test`, o un nombre especifico como `extra_trees`, `random_forest_conservative`, `hist_gradient_boosting_tuned`, `ridge_regression` o `sgd_gradient_regression`.
- `exogenous.enabled`: `true` para usar variables exogenas cuando existan, `false` para ignorarlas.
