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
notebooks/                  explicacion paso a paso del proyecto
data/input/                 templates y variables externas de entrada
data/processed/             datasets listos para modelo
models/                     modelos entrenados
reports/                    metricas, reportes y predicciones
```

## Ejecucion del proyecto

La ejecucion productiva de este flujo en el repo se hace desde Mage, no desde wrappers `scripts/`.

Pipeline operativo actual:

- `mage_condimensa2/condimensa_project/pipelines/forecasting_v3_quickbooks/`

Bloques principales del pipeline:

- `extraer_forecasting_v3_silver`
- `entrenar_forecasting_v3`
- `predecir_forecasting_v3`
- `cargar_forecasting_v3_gold`

Este directorio (`Modelado/forecasting_v3/`) conserva:

- el codigo reutilizable del modelo en `src/quickbooks_forecast/`
- los notebooks de analisis y trazabilidad metodologica en `notebooks/`
- los artefactos generados en `reports/`

## Uso standalone

No hay una carpeta `scripts/` versionada en este proyecto. Si necesitas revisar el flujo fuera de Mage, las rutas soportadas hoy son:

1. Ejecutar los notebooks en `notebooks/`
2. Importar los modulos de `src/quickbooks_forecast/` desde Python para exploracion o pruebas tecnicas

Los notebooks disponibles son:

1. `01_exploracion_datos.ipynb`
2. `02_limpieza_y_catalogo.ipynb`
3. `03_entrenamiento_modelos.ipynb`
4. `04_resultados_y_predicciones.ipynb`

## Archivos importantes generados

- `data/processed/pt_mensual_model.csv`: serie mensual PT lista para entrenar.
- `data/processed/pp_mensual_model.csv`: serie mensual PP lista para entrenar.
- `data/processed/pt_productos_model.csv`: catalogo PT usado por el modelo con estado y estacionalidad.
- `data/processed/pp_productos_model.csv`: catalogo PP usado por el modelo con estado y estacionalidad.
- `reports/pt_productos_no_catalogo.csv`: productos vendidos que no se pudieron empatar con el catalogo EAN.
- `reports/metrics_pt.csv` y `reports/metrics_pp.csv`: evaluacion de cada modelo.
- `reports/model_comparison_all.csv`: comparacion de modelos ML en test (solo auditoria).
- `reports/temporal_cv_model_comparison_all.csv`: comparacion de modelos ML en validacion cruzada temporal usada para seleccion.
- `reports/walk_forward_backtest_all.csv`: backtest walk-forward en multiples ventanas temporales.
- `reports/walk_forward_segment_summary_all.csv`: desempeno por segmento (activo/inactivo, estacional/no estacional, top volumen).
- `reports/operational_thresholds_policy.md`: umbrales operativos formales para automatizacion.
- `reports/shap_global_importance_all.csv`: importancia global de features con SHAP para PT y PP.
- `reports/shap_top_products_all.csv`: drivers SHAP por producto top de volumen (PT/PP).
- `reports/shap_global_importance_pt.csv` y `reports/shap_global_importance_pp.csv`: desglose SHAP por fuente.
- `reports/shap_top_products_pt.csv` y `reports/shap_top_products_pp.csv`: drivers SHAP por producto top de volumen.
- `reports/shap_explainability_pt.md` y `reports/shap_explainability_pp.md`: resumen textual de interpretabilidad.
- `reports/learning_curve_all.csv`: curvas de aprendizaje (train vs validacion) para PT y PP.
- `reports/learning_curve_summary.md`: resumen ejecutivo de tendencia y gap train-validacion por fuente.
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

La diferencia es que este proyecto agrega un cuarto notebook para decision empresarial.

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

Por defecto `config/config.yml` usa `forecast_model: best_ml_temporal_cv`, es decir, las predicciones finales toman el modelo ML con menor error en validacion cruzada temporal (rolling, sin mirar el futuro). Si no hay suficientes periodos para CV, cae automaticamente a `best_ml_validation`. El test historico se usa solo para auditoria de desempeno y no para seleccionar modelo, evitando leakage. Los metodos estadisticos simples no participan como candidatos.

El tuning de Gradient Boosting queda guardado en `reports/hgb_tuning_all.csv`. La comparacion de validacion queda en `reports/validation_model_comparison_all.csv`.

## Variables exogenas

El pipeline esta preparado para usar variables reales conocidas antes del mes a predecir. Si los archivos estan vacios, esas variables entran como cero y el proyecto corre igual. Para buscar una mejora fuerte, completa:

- `data/input/variables_exogenas_calendario.csv`: dias laborables, feriados, temporada alta, eventos comerciales, promociones generales y variacion de precio general.
- `data/input/variables_exogenas_producto.csv`: pedidos confirmados, preventa, promociones por producto, clientes grandes, cambio de PVP, precio planificado, riesgo de quiebre, disponibilidad de materia prima y ajustes comerciales conocidos.

Regla importante: no uses informacion que solo se conoce despues de cerrar el mes, porque eso causaria fuga de informacion y metricas artificialmente buenas.

Si se quiere evaluar un escenario asistido por planificacion humana, debe hacerse como analisis controlado y documentarse explicitamente por separado. Este repo hoy no versiona wrappers ni reportes dedicados para ese escenario; el artefacto versionado de apoyo vigente es:

- `reports/exogenous_variables_plan.md`: plan y criterios para usar exogenas sin fuga de informacion.

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
- `segmento_operativo`
- `segmento_apto_automatizacion`
- `apto_automatizacion`

El stock actual se toma de `Quickbooks/Costos.xlsx`, columna `On Hand`, usando la ultima fila disponible por item. La prediccion original no se reemplaza: el pipeline conserva `cantidad_predicha` como forecast de demanda y calcula `cantidad_a_producir_ajustada` como recomendacion operativa descontando el inventario disponible de forma secuencial en el horizonte.

## Ajustes utiles

Edita `config/config.yml` para cambiar:

- `forecast_horizon_months`: cuantos meses hacia adelante predecir.
- `inactive_months`: ventana para marcar inactividad.
- `include_unmatched_pt`: si quieres entrenar tambien con productos de ventas que no aparecen en el catalogo EAN.
- `forecast_model`: `best_ml_temporal_cv` (recomendado) para escoger automaticamente el mejor modelo ML segun validacion cruzada temporal; `best_ml_validation` para split de validacion unico; o un nombre especifico como `extra_trees`, `random_forest_conservative`, `hist_gradient_boosting_tuned`, `ridge_regression` o `sgd_gradient_regression`. `best_ml_stable` se mantiene como alias de compatibilidad y usa la regla de validacion simple. `best_ml_test` queda deshabilitado para evitar leakage.
- `temporal_cv.enabled`: activa/desactiva CV temporal para tuning y seleccion.
- `temporal_cv.folds`: cantidad de folds rolling usados antes del bloque de test.
- `temporal_cv.validation_months`: meses por fold de validacion temporal.
- `walk_forward.enabled`: activa/desactiva backtest walk-forward para estabilidad temporal.
- `walk_forward.windows`: cantidad de cortes historicos evaluados (ej. 6 a 12).
- `walk_forward.step_months`: avance entre cortes (1 = mensual).
- `walk_forward.test_months`: meses evaluados por corte walk-forward.
- `learning_curves.enabled`: activa/desactiva curva de aprendizaje por fuente.
- `learning_curves.points`: numero de puntos de entrenamiento evaluados en la curva.
- `learning_curves.min_train_fraction`: fraccion minima del historial de train para iniciar la curva.
- `decision.automation_thresholds.max_segment_wape`: WAPE maximo permitido por segmento para automatizar.
- `decision.automation_thresholds.max_segment_wape_std`: desviacion estandar maxima de WAPE por segmento.
- `decision.automation_thresholds.min_folds_below_wape_threshold`: porcentaje minimo de cortes que deben cumplir el umbral.
- `decision.automation_thresholds.min_confidence`: confianza minima (`media` o `alta`) para automatizar.
- `decision.automation_thresholds.allow_seasonal_auto`: permite o bloquea automatizacion para estacionales.
- `decision.explainability.top_products`: cantidad de productos top por volumen a explicar con SHAP.
- `decision.explainability.top_features_per_product`: cantidad de features SHAP a reportar por producto.
- `exogenous.enabled`: `true` para usar variables exogenas cuando existan, `false` para ignorarlas.
