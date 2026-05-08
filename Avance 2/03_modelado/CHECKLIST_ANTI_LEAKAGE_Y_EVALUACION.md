# Checklist anti-leakage y evaluacion rigurosa

Usar este checklist antes de reportar cualquier metrica de modelo.

En Avance 2 es un requisito previo para publicar tablas finales de benchmark (pronostico, asociacion y anomalias).

## A. Definicion del problema y target

- [x] El target representa un evento futuro y util para negocio.
- [x] La definicion del target es estable y documentada.
- [x] El horizonte temporal de prediccion esta definido (t+1 mes).

## B. Control de data leakage

- [x] Ninguna feature contiene informacion derivada directa del target.
- [x] Ninguna feature usa datos posteriores al momento de prediccion.
- [x] Se excluyeron columnas de resultado (post-evento) del entrenamiento.
- [x] Las transformaciones (escalado/encoding/imputacion) se ajustan solo con train.
- [x] No hay agregaciones que mezclen train y test.

## C. Split de datos

- [x] Split temporal aplicado (no solo aleatorio).
- [x] Train, validation y test no se solapan.
- [x] El test representa escenario real futuro.
- [x] Se reportan periodos exactos de cada split.

**Periodos utilizados:**
- Train: Julio 2024 - Mayo 2025 (11 meses)
- Validation: Junio 2025 - Septiembre 2025 (4 meses)
- Test: Octubre 2025 - Enero 2026 (4 meses)

## D. Tamano y balance del dataset

- [x] Se reporta N total de observaciones: 10,316
- [x] Se reporta distribucion de datos por split.
- [x] Se reporta N por conjunto: Train=5,667 / Val=2,432 / Test=2,217
- [x] Se evalua baseline (Lag-1) para comparar.

## E. Metricas obligatorias segun tipo de problema

### E1. Clasificacion (si aplica)

N/A - Se uso regresion para pronostico

### E2. Regresion / pronostico

- [x] MAE: 2,790.86 (ExtraTrees test)
- [x] RMSE: 9,280.11 (ExtraTrees test)
- [x] WAPE: 0.3774 (ExtraTrees test)
- [x] Mejora vs baseline naive: +6.71% vs Lag-1

### E3. Reglas de asociacion

- [x] Lift (promedio/mediano): 8.62
- [x] Confianza realizada en validation y test: 0.5051
- [x] Estabilidad de reglas (Jaccard entre splits): 1.0000
- [x] Cobertura/soporte util de reglas: 12 reglas con support >= 0.02

### E4. Deteccion de anomalias

- [x] Porcentaje de alertas vs contamination objetivo: 10% = 10% (cumple)
- [x] Estabilidad (bootstrap/Jaccard top anomalias): 0.70 (LOF)
- [x] Revision de coherencia de negocio de alertas: 1 agencia identificada

## F. Validacion de sobreajuste

- [x] Comparacion train vs validation/test.
- [x] Si hay brecha grande, ajustar complejidad del modelo.
- [x] Se documenta ajuste de hiperparametros.

**Brechas observadas (ExtraTrees):**
- Gap Train-Val: 0.2065 (sobreajuste controlado)
- Gap Val-Test: 0.0496 (generalizacion aceptable)

## G. Trazabilidad y reproducibilidad

- [x] Version de datos usada registrada: PostgreSQL gold.kpis_ventas
- [x] Version de codigo/commit registrada: GitHub main branch
- [x] Semilla aleatoria documentada: random_state=42
- [x] Script o pipeline reproducible documentado: `03_modelado/proyecto_ml_experimentos/`

## H. Interpretacion y accion de negocio

- [x] Se identifican factores relevantes del modelo: lag_1, lag_2, tendencia_3m
- [x] Se traducen hallazgos a acciones concretas: ajustar ordenes, crear combos, auditar agencias
- [x] Se explican riesgos de falsos positivos y falsos negativos.

---

## Bitacora de validacion

**Experimento:** Benchmark completo Avance 2 (Pronostico + Asociacion + Anomalias)
**Fecha:** 26/03/2026
**Responsable:** Anthony Fajardo

**Resultado checklist:** **APROBADO**

**Observaciones:**
1. [x] Split temporal implementado correctamente
2. [x] Metricas completas reportadas
3. [x] Baseline superado en pronostico (+6.71%)
4. [x] Reglas de asociacion estables (Jaccard=1.0)
5. [x] Anomalias con estabilidad razonable (0.70) dado N pequeño
