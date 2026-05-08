# Benchmark Asociacion

- Baseline: `Apriori`.
- Algoritmos: `Apriori` vs `FPGrowth`.
- Evaluacion en holdout con: confianza realizada (val/test), estabilidad Jaccard, soporte realizado y costo computacional.

## Mejora implementada

Se agrego filtro formal de calidad de reglas antes del top final:

- `min_realized_conf_val = 0.25`
- `min_realized_conf_test = 0.25`
- `min_realized_support = 0.005`

Despues del filtro, las reglas se ordenan por consenso multicriterio (lift + confianza train + confianza test realizada + estabilidad entre splits).

## Resultado principal

| algoritmo | reglas_train | reglas_filtradas | reglas_top_consenso | conf_test_prom | support_test_prom | jaccard_train_test | tiempo_seg | score_general |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| FPGrowth | 12 | 12 | 12 | 0.5051 | 0.0276 | 1.0000 | 0.2428 | 2.1483 |
| Apriori | 12 | 12 | 12 | 0.5051 | 0.0276 | 1.0000 | 0.3071 | 2.1274 |

## Interpretacion

- Ambos algoritmos encuentran reglas equivalentes en calidad y estabilidad para este corte.
- `FPGrowth` queda levemente arriba por tiempo de ejecucion.
- El set actual cumple todos los umbrales de calidad configurados.

## Checklist transversal (obligatorio)

- Antes de publicar resultados finales, completar y adjuntar evidencia de `03_modelado/CHECKLIST_ANTI_LEAKAGE_Y_EVALUACION.md`.

## Fuente

- `03_modelado/proyecto_ml_experimentos/models/benchmark_association.csv`
- `03_modelado/proyecto_ml_experimentos/models/benchmark_association_sensitivity.csv`
