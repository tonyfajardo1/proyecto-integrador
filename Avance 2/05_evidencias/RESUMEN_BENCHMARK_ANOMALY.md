# Benchmark Anomalias

- Baseline: `IsolationForest`.
- Algoritmos comparados: `IsolationForest`, `LOF`, `OneClassSVM`, `PCA_Reconstruction`, `PCA_IsolationForest`.
- Criterio: estabilidad bootstrap de top anomalias y desviacion frente a `contamination` objetivo.

## Resultado principal

| algoritmo | n_anomalias | pct_anomalias | bootstrap_jaccard_top_anomalias | desviacion_target_contamination | score_general |
| --- | --- | --- | --- | --- | --- |
| LOF | 1 | 0.1000 | 0.7000 | 0.0000 | 0.4200 |
| IsolationForest | 1 | 0.1000 | 0.3333 | 0.0000 | 0.2000 |
| PCA_Reconstruction | 1 | 0.1000 | 0.3000 | 0.0000 | 0.1800 |
| PCA_IsolationForest | 1 | 0.1000 | 0.2667 | 0.0000 | 0.1600 |
| OneClassSVM | 2 | 0.2000 | 0.2000 | 0.1000 | 0.0800 |

## Interpretacion

- `LOF` sigue siendo el mejor en estabilidad para este dataset.
- Los candidatos con PCA agregan una familia complementaria y quedan competitivos frente a IsolationForest.
- El dataset de anomalias es pequeno (10 agencias), por lo que se recomienda lectura de resultados como soporte de decision y no como verdad definitiva.

## Checklist transversal (obligatorio)

- Antes de publicar resultados finales, completar y adjuntar evidencia de `03_modelado/CHECKLIST_ANTI_LEAKAGE_Y_EVALUACION.md`.

## Fuente

- `03_modelado/proyecto_ml_experimentos/models/benchmark_anomaly.csv`
- `03_modelado/proyecto_ml_experimentos/models/benchmark_anomaly_sensitivity.csv`
