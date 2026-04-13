# Forecasting E2E (Mage -> Modelado -> Gold -> Dashboard)

## 1) Objetivo del proyecto

Este documento resume, de forma tecnica y trazable, la implementacion completa del flujo de forecasting de produccion para CONDIMENSA, desde la ingesta de datos (Mage) hasta la visualizacion operativa en Streamlit.

El enfoque se concentro en una pregunta de negocio unica:

**Cuanto se debe planificar producir por producto para el siguiente mes, con control de calidad de datos, validacion temporal y salida util para planificacion operativa?**


## 2) Alcance funcional y tecnico

Se implemento un flujo end-to-end con las siguientes capas:

1. **Ingesta y estandarizacion (Mage / DWH)**
2. **Dataset de modelado mensual (Silver)**
3. **EDA + Wrangling orientado a series temporales**
4. **Entrenamiento y benchmark de modelos con anti-leakage**
5. **Publicacion de pronosticos a Gold v2**
6. **Consumo y visualizacion en dashboard Streamlit**


## 3) Arquitectura del flujo

### 3.1 ETL en Mage

- Pipeline Bronze: `mage_condimensa2/condimensa_project/pipelines/etl_bronze/metadata.yaml`
  - `crear_tablas_bronze` -> `extraer_datos_bronze` -> `cargar_bronze`
- Pipeline Silver: `mage_condimensa2/condimensa_project/pipelines/etl_silver/metadata.yaml`
  - `crear_tablas_silver` -> `extraer_desde_bronze` -> `transformar_datos_silver` -> `cargar_silver`
- Pipeline Gold: `mage_condimensa2/condimensa_project/pipelines/etl_gold/metadata.yaml`
  - `crear_tablas_gold` -> `extraer_desde_silver` -> `calcular_kpis_gold` -> `cargar_gold` -> `publicar_estado_forecasting_gold`

### 3.2 Fuentes de datos de produccion

- Carga de produccion QuickBooks via ODIN API:
  - `mage_condimensa2/condimensa_project/data_loaders/load_quickbooks_produccion.py`
  - `mage_condimensa2/condimensa_project/data_loaders/cargar_produccion_completa.py`
- Transformaciones Silver (limpieza, consolidaciones, calculos):
  - `mage_condimensa2/condimensa_project/transformers/transformar_datos_silver.py`

### 3.3 Capa de modelado (proyecto limpio)

Proyecto: `03_modelado/forecasting_tesis_v2`

- Fuente de datos modelado: `src/data_source.py`
- Wrangling temporal: `src/wrangling.py`
- Entrenamiento/evaluacion: `src/modeling.py`
- Ejecucion batch: `scripts/run_modeling.py`
- Publicacion Gold v2: `scripts/publish_predictions_to_gold.py`
- Artefactos: carpeta `artifacts/`


## 4) Dataset de entrada para forecasting

La carga principal se realiza desde dos fuentes segun modo de ejecucion:

- `source="dwh"`: `silver.produccion_modelado_mensual`
- `source="dwh_forecasting_v1"`: `silver.forecasting_base_mensual_v1`

Columnas esperadas:

- `producto`
- `periodo`
- `qty_planificada`
- `qty_fabricada`
- `n_ordenes`

Fallback implementado en `src/data_source.py` (para `source="dwh"`):

- Si la consulta DWH falla o retorna vacio, se intenta reconstruir mensual desde `quickbooks.produccion`.


## 5) EDA y calidad de datos

En las ejecuciones de validacion se observaron (antes de wrangling final):

- Filas: 12,381
- Productos: 1,002
- Periodos: 21
- Duplicados por `producto-periodo`: 0
- Nulos en `qty`: 0 (segun chequeos de EDA aplicados)

El objetivo del EDA fue confirmar:

1. granularidad mensual correcta,
2. cobertura temporal por SKU,
3. comportamiento de faltantes,
4. necesidad de tratamiento estacional.


## 6) Wrangling implementado para modelado

Archivo: `03_modelado/forecasting_tesis_v2/src/wrangling.py`

### 6.1 Reglas aplicadas

1. **Normalizacion semantica de producto** (`normalize_product_name`)
2. **Agregacion a nivel producto-periodo**
3. **Completitud temporal por SKU** (relleno del calendario mensual entre min y max fecha por producto)
4. **Imputacion jerarquica de faltantes**
   - Paso 1: `cero_estructural` para estacionales fuera de temporada
   - Paso 2: `temporal` por `ffill/bfill` para faltantes restantes
   - Paso 3: `mediana` por producto como fallback final
5. **No negatividad** en `qty_fabricada`, `qty_planificada`, `n_ordenes`
6. **Filtro de historia minima por producto** (`min_periods_product=4`)

### 6.2 Variables de trazabilidad generadas

- `imputado_mes_faltante`
- `tipo_imputacion`
- `producto_estacional`
- `temporada_meses`

### 6.3 Resultado de wrangling (artefacto oficial)

Archivo: `03_modelado/forecasting_tesis_v2/artifacts/wrangling_report.csv`

- `rows_output`: 14,670
- `products_output`: 904
- `periods_output`: 21
- `rows_imputed_missing_month`: 2,434
- `products_seasonal_detected`: 37
- `rows_imputed_structural_zero`: 267
- `rows_imputed_temporal`: 2,167
- `rows_imputed_median`: 0


## 7) Modelado y evaluacion temporal

Archivo: `03_modelado/forecasting_tesis_v2/src/modeling.py`

### 7.1 Configuracion usada

Desde `scripts/run_modeling.py`:

- `source="dwh"`
- `min_periods_product=4`
- `train_frac=0.6`
- `val_frac=0.2`
- `seasonal_active_months=3`
- `seasonal_active_share=0.45`
- `cap_quantile=0.995`

### 7.2 Feature engineering principal

- Lags: `lag_1`, `lag_2`, `lag_3`
- Rolling: `rolling_mean_3`, `rolling_std_3`
- Diferencia: `delta_1`
- Variables operativas lag: `qty_planificada_lag_1`, `n_ordenes_lag_1`
- Calendario: `mes_num`, `anio_num`
- Target: `target_t1` (shift -1 por producto)

### 7.3 Modelos comparados

- `Baseline_Lag1`
- `Baseline_Lag12_Seasonal`
- `Baseline_Hibrido_L1_L12`
- `LinearRegression`
- `RandomForest`
- `RandomForest_ByTipo`
- `RandomForest_ByCategoria`
- `RandomForest_Hierarquico`
- `ExtraTrees`
- `LightGBM`
- `XGBoost`
- `Prophet` (opcional, si esta disponible)
- `Ensemble_RF_ET_LR`

### 7.4 Metricas

- `MAE`
- `RMSE`
- `WAPE` (principal para comparacion)
- Gaps de generalizacion:
  - `gap_wape_train_val`
  - `gap_wape_val_test`
- Mejora vs baseline:
  - `mejora_vs_baseline_val_wape`
  - `mejora_vs_baseline_test_wape`

Nota metodologica:

- La seleccion de modelo se hace unicamente por metricas del modelo (sin comparacion formal contra `qty_planificada`).


## 8) Controles anti-leakage

Se implementaron controles explicitos para evitar leakage temporal y de codificacion:

1. `target_t1` construido con `shift(-1)` por producto.
2. Split temporal estricto por periodos (train, val, test).
3. Encoding de `producto_id` entrenado solo con train (`desconocidos=-1` fuera de train).
4. Reglas de estacionalidad inferidas con `train+val` (sin usar test).
5. Cap por producto usando historico `train+val` con percentil `q=0.995`.

Reporte exportado:

- `03_modelado/forecasting_tesis_v2/artifacts/leakage_report.csv`


## 9) Resultados finales del benchmark

Archivo oficial: `03_modelado/forecasting_tesis_v2/artifacts/benchmark_forecasting_v2.csv`

Ranking por validacion (WAPE_val):

1. **LinearRegression**
   - `WAPE_val = 0.2428`
   - `WAPE_test = 0.3494`
2. Ensemble RF/ET/LR
   - `WAPE_val = 0.2455`
   - `WAPE_test = 0.3423`
3. RandomForest_ByTipo
   - `WAPE_val = 0.2511`
   - `WAPE_test = 0.3569`
4. RandomForest_Hierarquico
   - `WAPE_val = 0.2511`
   - `WAPE_test = 0.3571`
5. RandomForest
   - `WAPE_val = 0.2565`
   - `WAPE_test = 0.3468`

Lectura tecnica:

- El modelo seleccionado por criterio de validacion fue **LinearRegression**.
- Frente al baseline Lag1, la mejora en validacion fue de ~**0.0300 WAPE**.
- En test, `Ensemble_RF_ET_LR` queda ligeramente mejor en WAPE, pero la seleccion oficial se mantiene por criterio de validacion.


## 10) Publicacion a Gold v2

Script: `03_modelado/forecasting_tesis_v2/scripts/publish_predictions_to_gold.py`

### 10.1 Tabla de salida

- `gold.pronostico_produccion_resultado_v2`

### 10.2 Campos principales publicados

- Identidad y clasificacion:
  - `tipo_producto`, `categoria_producto`, `producto_base`, `producto`
- Eje temporal:
  - `periodo`, `periodo_prediccion`
- Operacion y forecast:
  - `qty_fabricada`, `qty_planificada`, `pronostico_qty`
  - `qty_recomendada`, `qty_min_recomendada`, `qty_max_recomendada`
- Riesgo operativo:
  - `nivel_confianza`, `sugerencia_accion`, `posibles_causas`
- Vigencia:
  - `es_vigente_operativo`, `razon_vigencia`
- Trazabilidad:
  - `pipeline_id`, `fecha_ejecucion`, `modelo_ganador`

### 10.3 Resultado de publicacion

- Filas publicadas en corrida actual: **4,996**
- Activos: **4,996**
- Inactivos: **0**


## 11) Ajustes funcionales recientes

- Se elimino del pipeline de modelado la comparacion formal contra `qty_planificada`.
- Se removieron salidas `plan_vs_model_*` y `plan_data_quality` para evitar interpretaciones mixtas.
- La evaluacion oficial queda centrada en benchmark temporal (MAE/RMSE/WAPE) y controles anti-leakage.


## 12) Integracion dashboard

### 12.1 Data access con fallback v2 -> legacy

Archivo: `mage_condimensa2/dashboard/database.py`

Implementado:

- Query primaria: `gold.pronostico_produccion_resultado_v2`
- Fallback automatico: `gold.pronostico_produccion_resultado`
- Salida homologada con columnas nuevas (`pipeline_id`, `fecha_ejecucion`, `modelo_ganador`).

### 12.2 Vista de predicciones

Archivo: `mage_condimensa2/dashboard/views/predicciones.py`

Estado actual:

- Muestra modelo publicado (`modelo_ganador`) cuando esta disponible.
- Mantiene KPIs, top productos y tabla operativa de planificacion.
- Muestra rango de planificacion (`minima`, `recomendada`, `maxima`) para produccion.
- Incluye seccion de estado de forecasting con tabs de `Estacionales` e `Inactivos`.


## 13) Reproducibilidad paso a paso

Desde `F:\proyecto-integrador\Avance 2\03_modelado\forecasting_tesis_v2`:

1. Ejecutar modelado completo:

```bash
python scripts/run_modeling.py
```

2. Publicar resultados a Gold v2:

```bash
python scripts/publish_predictions_to_gold.py
```

3. Levantar dashboard (desde carpeta `mage_condimensa2/dashboard` segun entorno local):

```bash
streamlit run app.py
```


## 14) Evidencia y archivos clave

### 14.1 Artefactos de modelado

- `03_modelado/forecasting_tesis_v2/artifacts/benchmark_forecasting_v2.csv`
- `03_modelado/forecasting_tesis_v2/artifacts/predicciones_forecasting_v2.csv`
- `03_modelado/forecasting_tesis_v2/artifacts/wrangling_report.csv`
- `03_modelado/forecasting_tesis_v2/artifacts/leakage_report.csv`

### 14.2 Codigo principal

- `03_modelado/forecasting_tesis_v2/src/data_source.py`
- `03_modelado/forecasting_tesis_v2/src/wrangling.py`
- `03_modelado/forecasting_tesis_v2/src/modeling.py`
- `03_modelado/forecasting_tesis_v2/scripts/run_modeling.py`
- `03_modelado/forecasting_tesis_v2/scripts/publish_predictions_to_gold.py`

### 14.3 Dashboard

- `mage_condimensa2/dashboard/database.py`
- `mage_condimensa2/dashboard/views/predicciones.py`
- `mage_condimensa2/dashboard/views/resumen.py`


## 15) Guia de capturas (para informe/presentacion)

Esta seccion define exactamente que capturar para que tu evidencia quede completa y defendible.

### Captura 1 - Arquitectura ETL en Mage

- Pantalla: pipelines `etl_bronze`, `etl_silver`, `etl_gold` con sus bloques.
- Debe verse: secuencia de bloques y estado de ejecucion.
- Objetivo: demostrar trazabilidad de capas Bronze/Silver/Gold.

### Captura 2 - Dataset de modelado en Silver

- Pantalla: consulta SQL a `silver.forecasting_base_mensual_v1` (muestra de filas y conteos).
- Debe verse: columnas `producto`, `periodo`, `qty_planificada`, `qty_fabricada`, `n_ordenes`.
- Objetivo: validar fuente de entrenamiento.

### Captura 3 - Wrangling report

- Pantalla: `wrangling_report.csv` o notebook/celda con su tabla.
- Debe verse: imputaciones (`cero_estructural`, `temporal`) y productos estacionales detectados.
- Objetivo: justificar tratamiento de faltantes/estacionalidad.

### Captura 4 - Benchmark de modelos

- Pantalla: `benchmark_forecasting_v2.csv` ordenado por `WAPE_val`.
- Debe verse: LinearRegression ganador y comparacion vs baseline.
- Objetivo: sustentar seleccion del modelo.

### Captura 5 - Leakage report

- Pantalla: `leakage_report.csv`.
- Debe verse: checks en estado `OK`.
- Objetivo: demostrar rigor metodologico temporal.

### Captura 6 - Publicacion Gold v2

- Pantalla: query a `gold.pronostico_produccion_resultado_v2` con conteos.
- Debe verse: total filas, activos e inactivos.
- Objetivo: evidenciar despliegue operativo.

### Captura 7 - Dashboard: Resumen Ejecutivo

- Pantalla: pagina `Resumen Ejecutivo`.
- Debe verse: KPI principal y bloque de Pregunta 3 (Pronostico Produccion).
- Objetivo: mostrar consumo de resultados a nivel ejecutivo.

### Captura 8 - Dashboard: Pronostico Produccion (vista principal)

- Pantalla: KPIs + top productos + tabla de planificacion.
- Debe verse: `qty_min_recomendada`, `qty_recomendada`, `qty_max_recomendada`, periodo de pronostico.
- Objetivo: evidencia funcional de planificacion.

### Captura 9 - Dashboard: Estado Forecasting (Estacionales/Inactivos)

- Pantalla: seccion 4 de `Predicciones`.
- Debe verse: tabs `Estacionales` e `Inactivos` con sus tablas Gold.
- Objetivo: mostrar control operativo de ciclo de vida del producto.

### Captura 10 - Rango de recomendacion operativa

- Pantalla: tabla de planificacion en dashboard.
- Debe verse: `Produccion minima`, `Produccion recomendada`, `Produccion maxima`.
- Objetivo: evidenciar salida operativa de rango min/base/max.


## 16) Riesgos, limitaciones y siguientes mejoras

1. **Campo activo/inactivo oficial no confiable en origen**:
   se usa vigencia operativa derivada por actividad reciente.
2. **Prophet costo-tiempo**:
   util como referencia, pero no ganador en esta corrida.
3. **Mejora futura recomendada**:
   incorporar exogenas (promociones, calendario comercial, eventos) para productos volatil.
4. **Monitoreo de drift**:
   agregar comparacion mensual automatica de WAPE por segmento de producto.


## 17) Conclusion

Se completo la implementacion E2E de forecasting de produccion con:

- pipeline de datos trazable (Mage -> Silver),
- wrangling robusto para estacionalidad/faltantes,
- benchmark temporal y controles anti-leakage,
- publicacion operativa en Gold v2,
- consumo en dashboard Streamlit con soporte de vigencia operativa e inactivos.

Con esto, el proceso queda en condiciones de sustentacion tecnica y uso operativo para planificacion mensual de produccion.
