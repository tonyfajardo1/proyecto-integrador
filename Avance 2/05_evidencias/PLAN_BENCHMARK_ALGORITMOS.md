# Plan de benchmark de algoritmos (post-Avance 2)

## Objetivo
Comparar los algoritmos actuales del proyecto contra alternativas para validar si las elecciones actuales son las mejores para:

1. Pronostico de produccion.
2. Reglas de asociacion (cross-selling).
3. Deteccion de anomalias.

---

## Baseline actual del proyecto

### 1) Pronostico de produccion
- **Modelo actual:** `RandomForestRegressor`.
- **Baseline explicito:** **naive lag-1** (usar el valor anterior como prediccion).
- **Donde esta definido:** `Avance 2/mage_condimensa2/condimensa_project/transformers/dm/analizar_causas_desviaciones.py`.
  - `naive_pred = lag_1`.
  - Se comparan `MAE`, `RMSE`, `WAPE` contra ese baseline.

### 2) Reglas de asociacion
- **Algoritmo actual:** `Apriori` + `association_rules`.
- **Baseline practico para benchmark:** el propio Apriori actual con parametros productivos:
  - `min_support=0.02`, `min_confidence=0.25`, `max_len=2`, `max_productos=120`.
- **Donde esta definido:** `Avance 2/mage_condimensa2/condimensa_project/transformers/generar_reglas_apriori.py`.

### 3) Deteccion de anomalias
- **Algoritmo actual:** `IsolationForest`.
- **Baseline practico para benchmark:** IsolationForest actual (`n_estimators=100`, `contamination=0.1`).
- **Donde esta definido:** `Avance 2/mage_condimensa2/condimensa_project/transformers/detectar_anomalias_isolation_forest.py`.

> Nota: en anomalias y asociacion no hay baseline "naive" explicito como en pronostico; el baseline de comparacion sera el modelo actual en produccion.

---

## Algoritmos candidatos a comparar

### A) Pronostico
- `RandomForestRegressor` (baseline actual).
- `XGBoost` o `LightGBM`.
- `CatBoost`.
- `SARIMAX` o `Prophet` (como enfoque de series temporales).

### B) Asociacion
- `Apriori` (baseline actual).
- `FP-Growth`.
- `Eclat` (si se implementa o via libreria compatible).

### C) Anomalias
- `IsolationForest` (baseline actual).
- `LocalOutlierFactor (LOF)`.
- `One-Class SVM`.
- `EllipticEnvelope` (solo si la distribucion ayuda).

---

## Protocolo de evaluacion

### 1) Fijar datos y ventana
- Mantener el mismo dataset y periodo para todos los modelos de cada problema.
- No mezclar cortes de tiempo distintos entre modelos.

### 2) Split y validacion
- **Pronostico:** split temporal (train pasado, test futuro).
- **Asociacion:** mismo universo de transacciones y mismo preprocesamiento.
- **Anomalias:** mismo set de agencias/features.

### 3) Metricas
- **Pronostico:** `WAPE` (principal), `MAE`, `RMSE`.
- **Asociacion:** numero de reglas utiles, soporte medio, confianza media, lift medio/mediano, cobertura de transacciones, tiempo de ejecucion.
- **Anomalias:** estabilidad temporal, porcentaje de alertas razonable, coherencia de negocio por revision manual.

### 4) Criterio de seleccion final
- Mejor metrica principal sin disparar complejidad/tiempo.
- Mantener interpretabilidad para el dashboard y defensa academica.

---

## Entregables sugeridos

1. Tabla comparativa por problema (baseline vs candidatos).
2. Recomendacion final por problema (modelo elegido + justificacion).
3. Evidencia de corrida (metricas y tiempos).
4. Decision final para version productiva del dashboard.

---

## Estado actual (referencia)
- Flujo operativo actual:
  - KPIs de ventas/rentabilidad: `kronos.ventas_resumen` (Supabase).
  - Asociacion: `kronos.ventas_detalle` (Supabase).
  - Pronostico: `quickbooks.produccion` (Supabase).
- Dashboard ya consume tablas gold pobladas desde este flujo.
