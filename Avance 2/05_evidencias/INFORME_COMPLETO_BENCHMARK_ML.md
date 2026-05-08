# Informe completo de benchmark de algoritmos

## 1) Objetivo

Comparar algoritmos por tipo de problema en Avance 2 para validar si el baseline actual es la mejor opcion operativa.

## 2) Tipos de algoritmos y enfoque

- Pronostico: aprendizaje supervisado (regresion).
- Asociacion: aprendizaje no supervisado (reglas de co-ocurrencia).
- Anomalias: no supervisado / one-class (deteccion de outliers).

## 3) Desarrollo por tipo

### 3.1 Pronostico de produccion
- Fuente: `quickbooks.produccion` (PostgreSQL).
- Baseline: `Lag-1`.
- Modelos: RandomForest, ExtraTrees, GradientBoosting.
- Protocolo: split temporal train/validation/test (60/20/20), seleccion en validation y reporte final en test.

Top resultados (incluye validation y test):

| modelo | MAE | RMSE | WAPE | config | split | mejora_vs_baseline_wape | n_train | n_val | n_test | periodos_train | periodos_val | periodos_test |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ExtraTrees | 2172.073108 | 6323.487255 | 0.327749 | ExtraTreesRegressor(min_samples_leaf=2, n_estimators=300, n_jobs=-1,
                    random_state=42) | validation | 0.041004 | 5667 | 2432 | 2217 | [Timestamp('2024-07-01 00:00:00'), Timestamp('2024-08-01 00:00:00'), Timestamp('2024-09-01 00:00:00'), Timestamp('2024-10-01 00:00:00'), Timestamp('2024-11-01 00:00:00'), Timestamp('2024-12-01 00:00:00'), Timestamp('2025-01-01 00:00:00'), Timestamp('2025-02-01 00:00:00'), Timestamp('2025-03-01 00:00:00'), Timestamp('2025-04-01 00:00:00'), Timestamp('2025-05-01 00:00:00')] | [Timestamp('2025-06-01 00:00:00'), Timestamp('2025-07-01 00:00:00'), Timestamp('2025-08-01 00:00:00'), Timestamp('2025-09-01 00:00:00')] | [Timestamp('2025-10-01 00:00:00'), Timestamp('2025-11-01 00:00:00'), Timestamp('2025-12-01 00:00:00'), Timestamp('2026-01-01 00:00:00')] |
| RandomForest | 2211.829916 | 6803.625316 | 0.333748 | RandomForestRegressor(min_samples_leaf=2, n_estimators=500, n_jobs=-1,
                      random_state=42) | validation | 0.035005 | 5667 | 2432 | 2217 | [Timestamp('2024-07-01 00:00:00'), Timestamp('2024-08-01 00:00:00'), Timestamp('2024-09-01 00:00:00'), Timestamp('2024-10-01 00:00:00'), Timestamp('2024-11-01 00:00:00'), Timestamp('2024-12-01 00:00:00'), Timestamp('2025-01-01 00:00:00'), Timestamp('2025-02-01 00:00:00'), Timestamp('2025-03-01 00:00:00'), Timestamp('2025-04-01 00:00:00'), Timestamp('2025-05-01 00:00:00')] | [Timestamp('2025-06-01 00:00:00'), Timestamp('2025-07-01 00:00:00'), Timestamp('2025-08-01 00:00:00'), Timestamp('2025-09-01 00:00:00')] | [Timestamp('2025-10-01 00:00:00'), Timestamp('2025-11-01 00:00:00'), Timestamp('2025-12-01 00:00:00'), Timestamp('2026-01-01 00:00:00')] |
| GradientBoosting | 2314.447635 | 7129.698043 | 0.349233 | GradientBoostingRegressor(random_state=42) | validation | 0.019521 | 5667 | 2432 | 2217 | [Timestamp('2024-07-01 00:00:00'), Timestamp('2024-08-01 00:00:00'), Timestamp('2024-09-01 00:00:00'), Timestamp('2024-10-01 00:00:00'), Timestamp('2024-11-01 00:00:00'), Timestamp('2024-12-01 00:00:00'), Timestamp('2025-01-01 00:00:00'), Timestamp('2025-02-01 00:00:00'), Timestamp('2025-03-01 00:00:00'), Timestamp('2025-04-01 00:00:00'), Timestamp('2025-05-01 00:00:00')] | [Timestamp('2025-06-01 00:00:00'), Timestamp('2025-07-01 00:00:00'), Timestamp('2025-08-01 00:00:00'), Timestamp('2025-09-01 00:00:00')] | [Timestamp('2025-10-01 00:00:00'), Timestamp('2025-11-01 00:00:00'), Timestamp('2025-12-01 00:00:00'), Timestamp('2026-01-01 00:00:00')] |
| Baseline_Lag1 | 2443.818199 | 8125.506472 | 0.368754 | nan | validation | 0.000000 | 5667 | 2432 | 2217 | [Timestamp('2024-07-01 00:00:00'), Timestamp('2024-08-01 00:00:00'), Timestamp('2024-09-01 00:00:00'), Timestamp('2024-10-01 00:00:00'), Timestamp('2024-11-01 00:00:00'), Timestamp('2024-12-01 00:00:00'), Timestamp('2025-01-01 00:00:00'), Timestamp('2025-02-01 00:00:00'), Timestamp('2025-03-01 00:00:00'), Timestamp('2025-04-01 00:00:00'), Timestamp('2025-05-01 00:00:00')] | [Timestamp('2025-06-01 00:00:00'), Timestamp('2025-07-01 00:00:00'), Timestamp('2025-08-01 00:00:00'), Timestamp('2025-09-01 00:00:00')] | [Timestamp('2025-10-01 00:00:00'), Timestamp('2025-11-01 00:00:00'), Timestamp('2025-12-01 00:00:00'), Timestamp('2026-01-01 00:00:00')] |
| ExtraTrees | 2790.864621 | 9280.108971 | 0.377364 | ExtraTreesRegressor(min_samples_leaf=2, n_estimators=300, n_jobs=-1,
                    random_state=42) | test | 0.067111 | 5667 | 2432 | 2217 | [Timestamp('2024-07-01 00:00:00'), Timestamp('2024-08-01 00:00:00'), Timestamp('2024-09-01 00:00:00'), Timestamp('2024-10-01 00:00:00'), Timestamp('2024-11-01 00:00:00'), Timestamp('2024-12-01 00:00:00'), Timestamp('2025-01-01 00:00:00'), Timestamp('2025-02-01 00:00:00'), Timestamp('2025-03-01 00:00:00'), Timestamp('2025-04-01 00:00:00'), Timestamp('2025-05-01 00:00:00')] | [Timestamp('2025-06-01 00:00:00'), Timestamp('2025-07-01 00:00:00'), Timestamp('2025-08-01 00:00:00'), Timestamp('2025-09-01 00:00:00')] | [Timestamp('2025-10-01 00:00:00'), Timestamp('2025-11-01 00:00:00'), Timestamp('2025-12-01 00:00:00'), Timestamp('2026-01-01 00:00:00')] |
| RandomForest | 2860.153177 | 9534.262168 | 0.386733 | RandomForestRegressor(min_samples_leaf=2, n_estimators=500, n_jobs=-1,
                      random_state=42) | test | 0.057742 | 5667 | 2432 | 2217 | [Timestamp('2024-07-01 00:00:00'), Timestamp('2024-08-01 00:00:00'), Timestamp('2024-09-01 00:00:00'), Timestamp('2024-10-01 00:00:00'), Timestamp('2024-11-01 00:00:00'), Timestamp('2024-12-01 00:00:00'), Timestamp('2025-01-01 00:00:00'), Timestamp('2025-02-01 00:00:00'), Timestamp('2025-03-01 00:00:00'), Timestamp('2025-04-01 00:00:00'), Timestamp('2025-05-01 00:00:00')] | [Timestamp('2025-06-01 00:00:00'), Timestamp('2025-07-01 00:00:00'), Timestamp('2025-08-01 00:00:00'), Timestamp('2025-09-01 00:00:00')] | [Timestamp('2025-10-01 00:00:00'), Timestamp('2025-11-01 00:00:00'), Timestamp('2025-12-01 00:00:00'), Timestamp('2026-01-01 00:00:00')] |
| GradientBoosting | 2903.999387 | 9949.913232 | 0.392662 | GradientBoostingRegressor(random_state=42) | test | 0.051814 | 5667 | 2432 | 2217 | [Timestamp('2024-07-01 00:00:00'), Timestamp('2024-08-01 00:00:00'), Timestamp('2024-09-01 00:00:00'), Timestamp('2024-10-01 00:00:00'), Timestamp('2024-11-01 00:00:00'), Timestamp('2024-12-01 00:00:00'), Timestamp('2025-01-01 00:00:00'), Timestamp('2025-02-01 00:00:00'), Timestamp('2025-03-01 00:00:00'), Timestamp('2025-04-01 00:00:00'), Timestamp('2025-05-01 00:00:00')] | [Timestamp('2025-06-01 00:00:00'), Timestamp('2025-07-01 00:00:00'), Timestamp('2025-08-01 00:00:00'), Timestamp('2025-09-01 00:00:00')] | [Timestamp('2025-10-01 00:00:00'), Timestamp('2025-11-01 00:00:00'), Timestamp('2025-12-01 00:00:00'), Timestamp('2026-01-01 00:00:00')] |
| Baseline_Lag1 | 3287.196662 | 11339.148140 | 0.444475 | nan | test | 0.000000 | 5667 | 2432 | 2217 | [Timestamp('2024-07-01 00:00:00'), Timestamp('2024-08-01 00:00:00'), Timestamp('2024-09-01 00:00:00'), Timestamp('2024-10-01 00:00:00'), Timestamp('2024-11-01 00:00:00'), Timestamp('2024-12-01 00:00:00'), Timestamp('2025-01-01 00:00:00'), Timestamp('2025-02-01 00:00:00'), Timestamp('2025-03-01 00:00:00'), Timestamp('2025-04-01 00:00:00'), Timestamp('2025-05-01 00:00:00')] | [Timestamp('2025-06-01 00:00:00'), Timestamp('2025-07-01 00:00:00'), Timestamp('2025-08-01 00:00:00'), Timestamp('2025-09-01 00:00:00')] | [Timestamp('2025-10-01 00:00:00'), Timestamp('2025-11-01 00:00:00'), Timestamp('2025-12-01 00:00:00'), Timestamp('2026-01-01 00:00:00')] |

Mejor modelo en test por WAPE: `ExtraTrees` con WAPE `0.377364`.

### 3.2 Reglas de asociacion
- Fuente: `silver.apriori_transacciones` (PostgreSQL).
- Baseline: Apriori.
- Algoritmos comparados: Apriori vs FP-Growth.
- Sensibilidad: min_support en {0.015, 0.02, 0.03}, min_confidence en {0.25, 0.30, 0.35}, top_k=50.
- Criterios: score_general, lift, confianza en holdout, estabilidad Jaccard train-vs-holdout y tiempo.

Top resultados de sensibilidad:

| algoritmo | min_support | min_confidence | reglas_train | lift_med_train | conf_val_prom | conf_test_prom | jaccard_train_val | jaccard_train_test | tiempo_seg | score_general |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Apriori | 0.020000 | 0.350000 | 10 | 12.264328 | 0.533833 | 0.533412 | 1.000000 | 0.833333 | 0.275572 | 2.821008 |
| FPGrowth | 0.020000 | 0.350000 | 10 | 12.264328 | 0.533833 | 0.533412 | 1.000000 | 0.833333 | 0.289399 | 2.816230 |
| FPGrowth | 0.015000 | 0.350000 | 20 | 10.790774 | 0.501004 | 0.520903 | 0.590909 | 0.826087 | 0.277157 | 2.551233 |
| Apriori | 0.015000 | 0.350000 | 20 | 10.790774 | 0.501004 | 0.520903 | 0.590909 | 0.826087 | 0.439171 | 2.514342 |
| FPGrowth | 0.015000 | 0.250000 | 25 | 10.011261 | 0.461697 | 0.484545 | 0.615385 | 0.884615 | 0.264329 | 2.409179 |
| FPGrowth | 0.015000 | 0.300000 | 25 | 10.011261 | 0.461697 | 0.484545 | 0.615385 | 0.884615 | 0.263262 | 2.403834 |
| Apriori | 0.015000 | 0.300000 | 25 | 10.011261 | 0.461697 | 0.484545 | 0.615385 | 0.884615 | 0.456888 | 2.361455 |
| Apriori | 0.015000 | 0.250000 | 25 | 10.011261 | 0.461697 | 0.484545 | 0.615385 | 0.884615 | 0.505644 | 2.361455 |
| FPGrowth | 0.020000 | 0.300000 | 12 | 8.622250 | 0.499109 | 0.506097 | 1.000000 | 1.000000 | 0.235167 | 2.135278 |
| FPGrowth | 0.020000 | 0.250000 | 12 | 8.622250 | 0.499109 | 0.506097 | 1.000000 | 1.000000 | 0.247173 | 2.131699 |
| Apriori | 0.020000 | 0.300000 | 12 | 8.622250 | 0.499109 | 0.506097 | 1.000000 | 1.000000 | 0.256703 | 2.126889 |
| Apriori | 0.020000 | 0.250000 | 12 | 8.622250 | 0.499109 | 0.506097 | 1.000000 | 1.000000 | 0.259663 | 2.126889 |

Mejor configuracion: algoritmo `Apriori`, support `0.020000`, confidence `0.350000`.

### 3.3 Deteccion de anomalias
- Fuente: `gold.metricas_agencias` (PostgreSQL).
- Baseline: IsolationForest.
- Algoritmos comparados: IsolationForest, LOF, OneClassSVM.
- Sensibilidad: contamination en {0.05, 0.10, 0.15}.
- Criterios: cercania a contamination objetivo, estabilidad bootstrap top-anomalias, score compuesto.

Top resultados de sensibilidad:

| algoritmo | contamination | n_anomalias | pct_anomalias | desviacion_target_contamination | bootstrap_jaccard_top_anomalias | score_general |
| --- | --- | --- | --- | --- | --- | --- |
| LOF | 0.100000 | 1 | 0.100000 | 0.000000 | 0.700000 | 0.420000 |
| LOF | 0.050000 | 1 | 0.100000 | 0.050000 | 0.700000 | 0.400000 |
| LOF | 0.150000 | 2 | 0.200000 | 0.050000 | 0.433333 | 0.240000 |
| IsolationForest | 0.100000 | 1 | 0.100000 | 0.000000 | 0.333333 | 0.200000 |
| IsolationForest | 0.050000 | 1 | 0.100000 | 0.050000 | 0.333333 | 0.180000 |
| IsolationForest | 0.150000 | 2 | 0.200000 | 0.050000 | 0.322222 | 0.173333 |
| OneClassSVM | 0.100000 | 2 | 0.200000 | 0.100000 | 0.200000 | 0.080000 |
| OneClassSVM | 0.150000 | 4 | 0.400000 | 0.250000 | 0.233333 | 0.040000 |
| OneClassSVM | 0.050000 | 1 | 0.100000 | 0.050000 | 0.066667 | 0.020000 |

Mejor configuracion: algoritmo `LOF` con contamination `0.100000`.

## 4) Validacion de sentido de negocio

- Pronostico: el mejor modelo debe superar consistentemente al baseline lag-1 en WAPE test.
- Asociacion: lift alto sin perder soporte y con estabilidad razonable en holdout.
- Anomalias: porcentaje de alertas controlado y estable, evitando sobre-alertado.

## 5) Riesgos y limitaciones

- Anomalias con n pequeno (10 agencias) pueden tener alta varianza; interpretar como soporte de decision, no verdad absoluta.
- Reglas de asociacion pueden verse influidas por estacionalidad/promociones; revisar periodos y campañas.
- Pronostico t+1 depende de calidad de historico y cobertura mensual por producto.

## 6) Recomendacion operativa

- Mantener pipeline productivo actual y usar benchmark para decision de mejora controlada.
- Adoptar el mejor modelo por caso solo si mejora en test y mantiene interpretabilidad/costo aceptables.
- Repetir benchmark por corte mensual para monitorear deriva de datos.
