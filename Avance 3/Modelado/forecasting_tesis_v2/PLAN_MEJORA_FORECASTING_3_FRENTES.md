# Plan de Mejora Forecasting (3 frentes)

## Objetivo general
Reducir el error del modelo en produccion, pasando de un `WAPE_test` cercano a 0.35 hacia un objetivo de 0.30 (o mejor), sin afectar la estabilidad operativa del pipeline.

## Metricas de seguimiento
- Metrica primaria de seleccion: `WAPE_val`.
- Metricas secundarias: `WAPE_test`, `MAE_test`, `RMSE_test`, `gap_wape_val_test`.
- Regla de aceptacion: mejorar baseline y mantener generalizacion estable entre validacion y test.

## Frente 1: Segmentacion + campeon por segmento (mayor impacto)

### Duracion estimada
1 semana.

### Implementacion
- Segmentar entrenamiento/evaluacion por `tipo_producto` (`PT`, `PP`, `OTRO`) y categorias relevantes.
- Evaluar candidatos por segmento con el mismo split temporal.
- Definir campeon por segmento con regla fija:
  - menor `WAPE_val`,
  - minimo de filas por segmento para evitar sobreajuste.
- Generar prediccion final combinando campeones por segmento.

### Entregables
- `artifacts/champion_segment_report.csv` (usado en produccion).
- `artifacts/segment_error_report.csv` actualizado.

### Criterio de aceptacion
- Mejora de `WAPE_val` global frente al modelo unico.
- Al menos 60%-70% de segmentos con mejora o empate tecnico.

## Frente 2: Tuning de hiperparametros por segmento (RF/XGB/LGBM)

### Duracion estimada
1 semana.

### Implementacion
- Ejecutar busqueda aleatoria (Random Search) con presupuesto controlado.
- Espacios recomendados:
  - RandomForest: `n_estimators`, `max_depth`, `min_samples_leaf`.
  - XGBoost/LightGBM: `n_estimators`, `learning_rate`, `max_depth`, `subsample`.
- Guardar mejores parametros por segmento para reutilizarlos en corridas futuras.

### Entregables
- `artifacts/tuning_results_<fecha>.csv`.
- Archivo de parametros campeones por segmento (`json` o `csv`).

### Criterio de aceptacion
- Mejora adicional de `WAPE_val` y/o `WAPE_test` respecto al Frente 1.
- No deteriorar fuertemente `gap_wape_val_test`.

## Frente 3: Variables exogenas de calendario (feriados)

### Duracion estimada
3 a 5 dias.

### Nota de alcance
No hay problema en usar solo feriados en esta etapa.

### Implementacion
- Integrar tabla/calendario de feriados al pipeline de features.
- Crear features:
  - `is_holiday_month` (mes con feriado: 0/1),
  - `holiday_count_month` (cantidad de feriados en el mes),
  - `is_pre_holiday_month` (mes previo a meses con alta carga de feriados).
- Opcional: `month_sin` y `month_cos` para estacionalidad suave.
- Correr prueba A/B: modelo base vs modelo con feriados.

### Entregables
- Feature set actualizado con calendario.
- Reporte comparativo A/B por metrica y por segmento.

### Criterio de aceptacion
- Si mejora global o en segmentos criticos, se activa en produccion.
- Si no mejora, se documenta y se deja desactivado (decision trazable).

## Cronograma sugerido
- Semana 1: Frente 1 (segmentacion y campeon por segmento).
- Semana 2: Frente 2 (tuning por segmento).
- Semana 3 (corta): Frente 3 (feriados + validacion A/B).

## Resultado esperado
- Pipeline de modelado mas robusto y defendible.
- Mejora gradual de precision sin perder estabilidad operativa.
- Trazabilidad completa de decisiones de seleccion y despliegue.
