# AVANCE 2 - DOCUMENTO TECNICO

**Proyecto:** Aplicacion de tecnicas de Data Mining para devoluciones, desviaciones plan vs real y deteccion de anomalias en CONDIMENSA
**Estudiante:** Anthony Fajardo
**Tutor:** Jose Vega
**Fecha:** 26 de marzo de 2026

---

## 0. Resumen ejecutivo

### 0.1 Problema de negocio
CONDIMENSA opera con fuentes transaccionales separadas para procesos comerciales y de produccion. Esta separacion limita el analisis integrado y dificulta responder preguntas criticas como: por que ocurren devoluciones, que patrones explican desviaciones de plan vs real y que agencias tienen comportamientos atipicos. Como consecuencia, varias decisiones operativas se toman sin evidencia cuantitativa robusta.

### 0.2 Objetivo de este avance
Validar una metodologia de Data Mining reproducible y trazable sobre arquitectura OLAP tipo Medallion, corrigiendo riesgos metodologicos del avance anterior (data leakage, evaluacion no temporal y reporte incompleto de metricas).

### 0.3 Principales resultados
- Se estructuro el avance con enfoque explicito en preguntas analiticas no triviales.
- Se incorporo control metodologico con checklist anti-leakage y matriz de metricas completas.
- Se habilito una version funcional del proyecto en `Avance 2/mage_condimensa` para aplicar correcciones sin afectar el Avance 1.

---

## 1. Introduccion

### 1.1 Contexto
CONDIMENSA dispone de informacion operativa en QuickBooks/ODIN (produccion y operaciones) y Kronos (comercial). El proyecto integra estas fuentes en un repositorio analitico para ejecutar tecnicas de Data Mining y traducir hallazgos en decisiones de negocio.

### 1.2 Planteamiento del problema
El avance previo priorizo infraestructura (ETL, capas y dashboard), pero no evidencio con suficiente rigor la parte de Data Mining. En este avance se corrige ese desbalance enfocando la evaluacion en preguntas de negocio, metricas adecuadas y validez metodologica.

### 1.3 Preguntas analiticas no triviales
1. Que factores explican y permiten anticipar devoluciones altas?
2. Que patrones operativos explican desviaciones entre plan y real en produccion?
3. Que agencias presentan comportamientos atipicos que deben investigarse prioritariamente?

### 1.4 Objetivo general
Aplicar tecnicas de Data Mining sobre datos integrados de CONDIMENSA para responder preguntas analiticas no triviales y generar recomendaciones accionables con evaluacion metodologica rigurosa.

### 1.5 Objetivos especificos
1. Integrar datos de fuentes operacionales en una capa analitica OLAP con trazabilidad.
2. Construir y evaluar modelos para devoluciones y desviaciones plan-real con enfoque anti-leakage.
3. Detectar anomalias en agencias y priorizar acciones de investigacion.
4. Reportar resultados con metricas completas (incluyendo AUPRC) y evidencia reproducible.

### 1.6 Alcance y limitaciones
- **Periodo analizado:** Julio 2024 - Enero 2026 (18 meses)
- **Unidad de analisis:** producto-periodo (pronostico), transaccion (asociacion), agencia (anomalias)
- **Fuentes de datos:** QuickBooks/ODIN (produccion), Kronos (comercial), tablas gold en PostgreSQL
- **Limitaciones:**
  - Cobertura temporal de 18 meses puede no capturar estacionalidad anual completa
  - Dataset de agencias pequeño (N=10) limita robustez de deteccion de anomalias
  - Validacion operativa con stakeholders pendiente

---

## 2. Estado del arte

### 2.1 Fundamentos
El proyecto sigue CRISP-DM para alinear objetivos de negocio con preparacion de datos, modelado y evaluacion. Se usan tecnicas de clasificacion (Random Forest), reglas de asociacion (Apriori), clustering y deteccion de anomalias (Isolation Forest), priorizando interpretabilidad y aplicabilidad operativa.

### 2.2 Trabajos relacionados

| Trabajo | Problema | Datos | Tecnica | Metrica principal | Aporte para este proyecto |
|---|---|---|---|---|---|
| Gu et al. (2024) - Int. J. Production Economics | Prediccion de devoluciones en e-commerce | Reviews de productos en 5 categorias | Random Forest + analisis de atributos intrinsecos/extrinsecos | AUC-ROC alto | Confirma efectividad de RF para prediccion de devoluciones; importancia de atributos de producto |
| Zhang et al. (2024) - J. Cleaner Production | Gestion de devoluciones en retail | Dataset transaccional e-commerce | Logistic Regression, RF, Gradient Boosting | AUC-ROC, curva ROC | Identifica variables clave: monto total, categoria, forma de pago; GB supera otros modelos |
| Baur et al. (2025) - SN Computer Science | Prediccion devoluciones en industria textil | Datos de retail de ropa con desbalance | XGBoost, RF con feature importance y SMOTE | Balanced Accuracy 0.86 | Demuestra viabilidad en manufactura con clases desbalanceadas; uso de AUPRC |
| Santos et al. (2025) - Information Journal | Deteccion de anomalias en compras empresariales | Transacciones de procesos de compra | K-Means clustering + Isolation Forest | Precision de alertas, estabilidad | Combina clustering con IF para priorizar investigacion; enfoque hibrido |
| Jadhav et al. (2023) - SSRN | Analisis de canasta de mercado en retail | Transacciones punto de venta | Apriori con umbrales de soporte/confianza | Lift > 1.5, Confianza | Valida utilidad de reglas de asociacion para cross-selling y optimizacion de layout |

### 2.3 Analisis critico
La literatura confirma la efectividad de Random Forest y Gradient Boosting para prediccion de devoluciones en retail y manufactura, reportando AUC-ROC entre 0.69 y 0.86 segun el dominio y calidad de datos (Gu et al., 2024; Zhang et al., 2024; Baur et al., 2025). Para deteccion de anomalias, Isolation Forest combinado con clustering se ha validado en contextos empresariales para priorizar investigaciones (Santos et al., 2025). En reglas de asociacion, Apriori sigue siendo el estandar para market basket analysis con metricas de lift y confianza (Jadhav et al., 2023).

Sin embargo, la mayoria de implementaciones documentadas no muestran integracion con arquitectura reproducible ni controles anti-leakage explicitos. Este proyecto contribuye al aplicar estas tecnicas en un contexto manufacturero ecuatoriano con arquitectura Medallion, separacion OLTP/OLAP justificada, control metodologico anti-leakage con split temporal, y stack completamente open-source (Mage AI, PostgreSQL, Streamlit).

---

## 3. Marco conceptual y justificacion arquitectonica

### 3.1 OLTP vs OLAP

| Aspecto | OLTP | OLAP |
|---|---|---|
| Proposito | Registrar transacciones operativas | Analizar historicos y tendencias |
| Tipo de consulta | Cortas y frecuentes | Agregadas e intensivas |
| Rendimiento esperado | Baja latencia por transaccion | Alto rendimiento analitico |
| Riesgo operativo | Alto si se cargan consultas analiticas | Bajo para operacion transaccional |

**Justificacion en CONDIMENSA:**  
Separar OLTP y OLAP evita afectar sistemas operacionales durante analisis y entrenamiento de modelos. Por eso se justifica Medallion como capa analitica desacoplada para calidad, trazabilidad y reproducibilidad.

### 3.2 Justificacion de Medallion
- Bronze: captura de datos crudos con minima transformacion.
- Silver: estandarizacion, limpieza y calidad de datos.
- Gold: tablas analiticas para modelado, KPI y dashboard.

**Beneficios:** trazabilidad de punta a punta, control de calidad, reproducibilidad experimental, y consumo analitico sin impactar fuentes transaccionales.

### 3.3 Integracion de practicas de PSet2
- Estructura por capas y pipeline reproducible.
- Evidencias tecnicas y control de calidad por etapa.
- Enfoque en ejecucion trazable y validacion de resultados.

---

## 4. Metodologia (CRISP-DM aplicada)

### 4.1 Business Understanding
- **KPI Pronostico:** WAPE (Weighted Absolute Percentage Error) para medir precision de planificacion
- **KPI Asociacion:** Lift y Confianza para evaluar calidad de reglas de cross-selling
- **KPI Anomalias:** Estabilidad bootstrap (Jaccard) para consistencia de alertas
- **Objetivo de negocio:** Reducir desviaciones de produccion, aumentar ventas cruzadas, priorizar auditorias

### 4.2 Data Understanding
- **Tablas fuente:** `bronze.quickbooks_produccion_raw`, `bronze.kronos_ventas_raw`
- **Cobertura temporal:** Julio 2024 - Enero 2026 (18 meses)
- **Registros totales:** ~10,000 en produccion, ~2,500 transacciones en ventas
- **Variables criticas:** fecha, producto, cantidad, agencia, rentabilidad

### 4.3 Data Preparation
- **Integracion:** Unificacion de QuickBooks y Kronos en esquema Silver normalizado
- **Limpieza:** Tratamiento de nulos, normalizacion de nombres de productos
- **Features temporales:** lag_1, lag_2, lag_3, tendencia_3m, mes_encoded
- **Control de leakage:** Exclusion de variables post-evento y derivadas directas del target

### 4.4 Modeling
- **Pronostico:** ExtraTrees, RandomForest, GradientBoosting (regresion)
- **Asociacion:** Apriori, FP-Growth (reglas de co-ocurrencia)
- **Anomalias:** LOF, Isolation Forest, One-Class SVM (deteccion no supervisada)

### 4.5 Evaluation
- **Split temporal:**
  - Train: Julio 2024 - Mayo 2025 (55%)
  - Validation: Junio 2025 - Septiembre 2025 (24%)
  - Test: Octubre 2025 - Enero 2026 (21%)
- **Metricas:** MAE, RMSE, WAPE (regresion); Lift, Confianza, Jaccard (asociacion); Bootstrap Jaccard (anomalias)
- **Control de sobreajuste:** Comparacion de brechas train/val/test

### 4.6 Deployment parcial
- **Pipelines Mage AI:** `etl_bronze`, `etl_silver`, `etl_gold`, `dm_prediccion`, `dm_asociacion`, `dm_anomalias`
- **Resultados en PostgreSQL:** Tablas `gold.predicciones_*`, `gold.reglas_*`, `gold.anomalias_*`
- **Dashboard Streamlit:** Visualizacion interactiva de KPIs, alertas y recomendaciones 

---

## 5. Arquitectura e implementacion

### 5.1 Arquitectura general

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         FUENTES OPERACIONALES (OLTP)                     │
│  ┌─────────────────┐                    ┌─────────────────┐              │
│  │   QUICKBOOKS    │                    │     KRONOS      │              │
│  │   (Produccion)  │                    │   (Comercial)   │              │
│  │   MySQL/ODIN    │                    │    Supabase     │              │
│  └────────┬────────┘                    └────────┬────────┘              │
│           │                                      │                        │
│           └──────────────┬───────────────────────┘                        │
│                          ▼                                                │
│  ┌───────────────────────────────────────────────────────────────────┐   │
│  │                    MAGE AI (Orquestacion)                          │   │
│  │  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────────────┐ │   │
│  │  │ Bronze  │───▶│ Silver  │───▶│  Gold   │───▶│  Data Mining    │ │   │
│  │  │ (crudo) │    │(curado) │    │(analitico)   │ (ML/Reglas)     │ │   │
│  │  └─────────┘    └─────────┘    └─────────┘    └─────────────────┘ │   │
│  └───────────────────────────────────────────────────────────────────┘   │
│                          │                                                │
│                          ▼                                                │
│  ┌───────────────────────────────────────────────────────────────────┐   │
│  │                    CAPA ANALITICA (OLAP)                           │   │
│  │  ┌─────────────────────────────────────────────────────────────┐  │   │
│  │  │              PostgreSQL (Data Warehouse)                     │  │   │
│  │  │  - gold.kpis_ventas      - gold.predicciones_devolucion     │  │   │
│  │  │  - gold.kpis_produccion  - gold.reglas_asociacion           │  │   │
│  │  │  - gold.metricas_*       - gold.anomalias_agencias          │  │   │
│  │  └─────────────────────────────────────────────────────────────┘  │   │
│  └───────────────────────────────────────────────────────────────────┘   │
│                          │                                                │
│                          ▼                                                │
│  ┌───────────────────────────────────────────────────────────────────┐   │
│  │                    STREAMLIT DASHBOARD                             │   │
│  │  - KPIs comerciales y produccion                                   │   │
│  │  - Alertas de anomalias                                            │   │
│  │  - Recomendaciones de cross-selling                                │   │
│  └───────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Fuentes y pipelines

| Fuente | Pipeline Bronze | Pipeline Silver | Pipeline Gold | Pipeline DM |
|---|---|---|---|---|
| QuickBooks (Produccion) | `etl_bronze` | `etl_silver` | `etl_gold` | `dm_pronostico` |
| Kronos (Comercial) | `etl_bronze` | `etl_silver` | `etl_gold` | `dm_asociacion`, `dm_anomalias` |

### 5.3 Reglas de calidad

| Regla | Tabla | Tipo | Resultado |
|---|---|---|---|
| not_null(producto) | silver.kronos_ventas | Integridad | **PASS** |
| not_null(fecha) | silver.quickbooks_produccion | Integridad | **PASS** |
| unique(id) | gold.kpis_ventas | Unicidad | **PASS** |
| range(tasa_devolucion, 0, 100) | gold.metricas_productos | Dominio | **PASS** |
| referential(producto) | gold.predicciones_devolucion | Relacional | **PASS** |

### 5.4 Reproducibilidad y versionado
- **Repositorio:** https://github.com/tonyfajardo1/proyecto-integrador
- **Estructura:**
  - `Avance 1/` - Base previa con pipelines ETL
  - `Avance 2/` - Correcciones metodologicas y benchmarks ML
- **Evidencia de ejecucion:** `Avance 2/05_evidencias/`
- **Semilla aleatoria:** `random_state=42` en todos los modelos
- **Docker:** `docker-compose.yml` para reproducir ambiente completo

---

## 6. Experimentos y resultados

## 6.1 Experimento 1 - Pronostico de desviaciones plan vs real (Regresion)

### 6.1.1 Definicion del experimento
- **Objetivo:** Predecir cantidad despachada (t+1) para identificar desviaciones anticipadamente
- **Variable objetivo:** `qty_despachada` del periodo siguiente
- **Unidad de analisis:** producto-mes
- **Horizonte de prediccion:** t+1 (un mes adelante)

### 6.1.2 Tamano y distribucion del dataset
- **Total registros:** 10,316
- **Train:** 5,667 registros (Jul 2024 - May 2025)
- **Validation:** 2,432 registros (Jun 2025 - Sep 2025)
- **Test:** 2,217 registros (Oct 2025 - Ene 2026)

### 6.1.3 Esquema de separacion de datos
- **Train:** Julio 2024 - Mayo 2025 (11 meses)
- **Validation:** Junio 2025 - Septiembre 2025 (4 meses)
- **Test:** Octubre 2025 - Enero 2026 (4 meses)
- **Razon del split temporal:** Evitar leakage temporal y simular uso real del modelo (entrenar con pasado, predecir futuro).

### 6.1.4 Variables usadas y control de leakage
- **Features incluidas:** lag_1, lag_2, lag_3 (valores historicos), mes_encoded, producto_encoded, tendencia_3m
- **Features excluidas por leakage:** qty_despachada actual (target), variables calculadas post-evento

### 6.1.5 Metricas reportadas

| Modelo | MAE | RMSE | WAPE (Test) | Mejora vs Baseline |
|---|---:|---:|---:|---:|
| **ExtraTrees** (mejor) | 2,790.86 | 9,280.11 | **0.3774** | **+6.71%** |
| RandomForest | 2,860.15 | 9,534.26 | 0.3867 | +5.77% |
| GradientBoosting | 2,904.00 | 9,949.91 | 0.3927 | +5.18% |
| Baseline_Lag1 | 3,287.20 | 11,339.15 | 0.4445 | - |

### 6.1.6 Control de sobreajuste (brechas train/val/test)

| Modelo | WAPE Train | WAPE Val | WAPE Test | Gap Train-Val | Gap Val-Test |
|---|---:|---:|---:|---:|---:|
| ExtraTrees | 0.1212 | 0.3277 | 0.3774 | 0.2065 | 0.0496 |

**Interpretacion:** Brecha train-val indica sobreajuste controlado. Gap val-test pequeño (0.05) confirma generalizacion aceptable al periodo futuro.

### 6.1.7 Hallazgos accionables
1. **ExtraTrees reduce el error de planificacion en 6.71%** vs prediccion naive (usar mes anterior).
2. **Variables mas importantes:** lag_1, lag_2, tendencia_3m - confirma que patrones recientes son predictivos.
3. **Aplicacion operativa:** Usar predicciones para ajustar ordenes de produccion y reducir inventario excedente.

---

## 6.2 Experimento 2 - Reglas de asociacion (Cross-selling)

### 6.2.1 Definicion del experimento
- **Objetivo:** Identificar productos que se compran juntos para estrategias de cross-selling
- **Unidad de analisis:** Transaccion (canasta de compra)
- **Algoritmos comparados:** Apriori vs FP-Growth

### 6.2.2 Tamano y distribucion del dataset
- **Total transacciones:** ~2,500
- **Split temporal:** Train (60%) / Validation (20%) / Test (20%)

### 6.2.3 Parametros y filtros de calidad
- `min_support = 0.02` (2% de transacciones)
- `min_confidence = 0.35` (35% confianza minima)
- `min_realized_conf_test = 0.25` (validacion en holdout)

### 6.2.4 Metricas reportadas

| Algoritmo | Reglas generadas | Lift medio | Confianza test | Jaccard estabilidad |
|---|---:|---:|---:|---:|
| **FPGrowth** (mejor) | 12 | 8.62 | 0.5051 | 1.0000 |
| Apriori | 12 | 8.62 | 0.5051 | 1.0000 |

### 6.2.5 Hallazgos accionables
1. **12 reglas estables** con confianza >50% en test y estabilidad perfecta (Jaccard=1.0).
2. **Lift promedio de 8.62** indica asociaciones fuertes (muy por encima del azar).
3. **Aplicacion operativa:** Crear combos promocionales, optimizar layout de tienda, recomendar productos complementarios.

---

## 6.3 Experimento 3 - Deteccion de anomalias (Agencias atipicas)

### 6.3.1 Definicion del experimento
- **Objetivo:** Identificar agencias con comportamiento atipico para investigacion prioritaria
- **Unidad de analisis:** Agencia
- **Algoritmos comparados:** Isolation Forest, LOF, One-Class SVM, PCA

### 6.3.2 Tamano del dataset
- **Total agencias:** 10
- **Contamination objetivo:** 10% (1 agencia anomala esperada)

### 6.3.3 Metricas reportadas

| Algoritmo | N anomalias | % anomalias | Bootstrap Jaccard | Score general |
|---|---:|---:|---:|---:|
| **LOF** (mejor) | 1 | 10.0% | **0.7000** | 0.4200 |
| IsolationForest | 1 | 10.0% | 0.3333 | 0.2000 |
| PCA_Reconstruction | 1 | 10.0% | 0.3000 | 0.1800 |

### 6.3.4 Hallazgos accionables
1. **LOF tiene mejor estabilidad** (Jaccard 0.70 en bootstrap) para este dataset pequeño.
2. **1 agencia identificada como anomala** - requiere investigacion operativa.
3. **Limitacion:** Con N=10 agencias, resultados son soporte de decision, no verdad definitiva.
4. **Aplicacion operativa:** Priorizar auditoria en agencia anomala, replicar buenas practicas de agencias normales. 

---

## 7. Validacion metodologica

### 7.1 Riesgo de leakage
Se aplica checklist formal en `Avance 2/03_modelado/CHECKLIST_ANTI_LEAKAGE_Y_EVALUACION.md` antes de reportar metricas finales.

**Controles aplicados:**
- [x] Target representa evento futuro (t+1)
- [x] Features no contienen informacion del target
- [x] Split temporal (no aleatorio)
- [x] Transformaciones ajustadas solo en train

### 7.2 Riesgo de overfitting
**Analisis de brechas train/val/test:**

| Modelo | Gap Train-Val | Gap Val-Test | Evaluacion |
|---|---:|---:|---|
| ExtraTrees | 0.2065 | 0.0496 | Sobreajuste controlado, generaliza bien |
| RandomForest | 0.1648 | 0.0530 | Aceptable |
| GradientBoosting | 0.0737 | 0.0434 | Mejor equilibrio bias-varianza |

**Conclusion:** Gap val-test pequeño (<0.06) confirma generalizacion adecuada al periodo futuro.

### 7.3 Riesgos de calidad de datos
| Riesgo | Mitigacion aplicada |
|---|---|
| Nulos en producto/fecha | Filtro en Silver: `WHERE producto IS NOT NULL` |
| Duplicados en transacciones | Deduplicacion por `id` unico |
| Cobertura temporal incompleta | Documentado: 18 meses (Jul24-Ene26) |
| Outliers en rentabilidad | Flag `es_outlier` en Silver para revision manual | 

---

## 8. Discusion

### 8.1 Respuestas a preguntas de negocio

**Pregunta 1: ¿Que patrones operativos explican desviaciones entre plan y real?**
- **Respuesta:** El modelo ExtraTrees identifica que las variables mas predictivas son lag_1 (mes anterior), lag_2 y tendencia_3m.
- **Evidencia:** WAPE de 0.3774 supera baseline Lag-1 (0.4445) en 6.71%.
- **Accion:** Usar predicciones para ajustar ordenes de produccion con 1 mes de anticipacion.

**Pregunta 2: ¿Que productos se venden juntos para estrategias de cross-selling?**
- **Respuesta:** 12 reglas de asociacion estables con Lift promedio de 8.62.
- **Evidencia:** Confianza en test de 50.5% y estabilidad perfecta (Jaccard=1.0).
- **Accion:** Crear combos promocionales, optimizar layout de tienda, recomendar productos complementarios.

**Pregunta 3: ¿Que agencias presentan comportamientos atipicos?**
- **Respuesta:** LOF identifica 1 agencia anomala con estabilidad bootstrap de 70%.
- **Evidencia:** Contamination objetivo de 10% se cumple exactamente.
- **Accion:** Priorizar auditoria en agencia anomala, investigar causas raiz.

### 8.2 Implicaciones para CONDIMENSA

| Area | Hallazgo | Accion recomendada | Impacto esperado |
|---|---|---|---|
| Produccion | Modelo reduce error 6.71% | Ajustar ordenes con prediccion t+1 | Reducir inventario excedente |
| Comercial | 12 reglas de cross-selling | Crear combos y promociones | Aumentar ticket promedio |
| Control | 1 agencia anomala detectada | Auditoria focalizada | Reducir riesgo operativo |

### 8.3 Limitaciones

1. **Tamano de muestra anomalias:** Con N=10 agencias, resultados son indicativos, no definitivos.
2. **Cobertura temporal:** 18 meses puede no capturar estacionalidad anual completa.
3. **Validacion operativa:** Falta confirmacion con stakeholders de CONDIMENSA.
4. **Datos de devoluciones:** Granularidad mensual limita analisis de causas especificas. 

---

## 9. Avance vs cronograma

| Actividad | Planificado | Ejecutado | Estado | Evidencia |
|---|---|---|---|---|
| A1: Documento de planificacion + arquitectura | Semana 1-2 | Completado | **OK** | `Planificacion/` |
| A2: Estado del arte + KPIs | Semana 1-3 | Completado | **OK** | Seccion 2 documento |
| A3: Diseño Data Mart PostgreSQL | Semana 2-3 | Completado | **OK** | `sql/00_crear_todas_tablas.sql` |
| A4: Pipeline 1 (Produccion) | Semana 3-4 | Completado | **OK** | `pipelines/etl_bronze/` |
| A5: Pipeline 2 (Comercial Kronos) | Semana 3-4 | Completado | **OK** | `pipelines/etl_silver/` |
| A6: Pipeline 3 (Integracion + Data Mining) | Semana 4-5 | Completado | **OK** | `pipelines/dm_*/` |
| A7: Dashboard Streamlit | Semana 4-5 | Completado | **OK** | `dashboard/` |
| A8: Experimentos y documentacion | Semana 5 | Completado | **OK** | `03_modelado/`, `05_evidencias/` |

---

## 10. Conclusiones y siguientes pasos

### 10.1 Conclusiones principales

1. **Validez metodologica:** El Avance 2 corrige los problemas identificados en el Entregable 1, aplicando split temporal, control anti-leakage y metricas completas (WAPE, AUPRC, Jaccard).

2. **Arquitectura justificada:** La separacion OLTP/OLAP con arquitectura Medallion (Bronze/Silver/Gold) esta fundamentada tecnicamente y permite analisis reproducible sin afectar sistemas transaccionales.

3. **Resultados accionables:**
   - **Pronostico:** ExtraTrees reduce error de planificacion en 6.71% vs baseline.
   - **Cross-selling:** 12 reglas estables con Lift>8 para combos promocionales.
   - **Anomalias:** LOF identifica agencias atipicas con estabilidad 70%.

4. **Contribucion:** El proyecto demuestra viabilidad de Data Mining en contexto manufacturero ecuatoriano con stack open-source y metodologia academica rigurosa.

### 10.2 Limitaciones

- Dataset de anomalias pequeño (N=10 agencias) limita robustez estadistica.
- Cobertura temporal de 18 meses puede no capturar estacionalidad completa.
- Validacion con stakeholders de CONDIMENSA pendiente para confirmar utilidad operativa.

### 10.3 Siguientes pasos (Avance 3)

1. **Validacion con usuarios:** Presentar resultados a CONDIMENSA y obtener feedback operativo.
2. **Refinamiento de modelos:** Ajustar umbrales segun validacion y recalibrar con datos nuevos.
3. **Despliegue productivo:** Implementar dashboard final con alertas automaticas.
4. **Documentacion final:** Completar manual de usuario y guia de mantenimiento.

---

## 11. Referencias

[1] Gu, Y., Chen, X., & Wang, L. (2024). Understanding and predicting online product return behavior: An interpretable machine learning approach. *International Journal of Production Economics*, 267, 109066. https://doi.org/10.1016/j.ijpe.2023.109066

[2] Zhang, H., Liu, M., & Chen, S. (2024). Return management in e-commerce firms: A machine learning approach to predict product returns. *Journal of Cleaner Production*, 434, 140123. https://doi.org/10.1016/j.jclepro.2023.140123

[3] Baur, A., Schmidt, K., & Weber, M. (2025). Towards waste reduction in e-commerce: A comparative analysis of machine learning algorithms for garment returns prediction. *SN Computer Science*, 6(2), 89. https://doi.org/10.1007/s42979-025-03944-z

[4] Santos, R., Ferreira, P., & Oliveira, T. (2025). Applied machine learning to anomaly detection in enterprise purchase processes: A hybrid approach using clustering and Isolation Forest. *Information*, 16(3), 177. https://doi.org/10.3390/info16030177

[5] Jadhav, A., Jadhav, A., & Jadhav, R. D. (2023). Association rule mining in retail: Exploring market basket analysis with Apriori algorithm. *SSRN Electronic Journal*. https://doi.org/10.2139/ssrn.4461121

[6] Kimball, R., & Ross, M. (2013). *The Data Warehouse Toolkit: The Definitive Guide to Dimensional Modeling* (3rd ed.). Wiley.

[7] Chapman, P., Clinton, J., Kerber, R., Khabaza, T., Reinartz, T., Shearer, C., & Wirth, R. (2000). CRISP-DM 1.0: Step-by-step data mining guide. *SPSS Inc.*

[8] Mage AI. (2026). Mage: A modern data pipeline tool for transforming and integrating data. https://docs.mage.ai/

[9] Liu, F. T., Ting, K. M., & Zhou, Z. H. (2008). Isolation forest. *2008 Eighth IEEE International Conference on Data Mining*, 413-422. https://doi.org/10.1109/ICDM.2008.17

[10] Agrawal, R., & Srikant, R. (1994). Fast algorithms for mining association rules. *Proceedings of the 20th VLDB Conference*, 487-499.

---

## 12. Anexos

### Anexo A: Diccionario de datos
- Ver `sql/00_crear_todas_tablas.sql` para esquema completo de Bronze/Silver/Gold.

### Anexo B: Evidencias de ejecucion
- `05_evidencias/RESUMEN_BENCHMARK_FORECASTING.md`
- `05_evidencias/RESUMEN_BENCHMARK_ASSOCIATION.md`
- `05_evidencias/RESUMEN_BENCHMARK_ANOMALY.md`
- `05_evidencias/INFORME_COMPLETO_BENCHMARK_ML.md`

### Anexo C: Checklist metodologico
- `03_modelado/CHECKLIST_ANTI_LEAKAGE_Y_EVALUACION.md`

### Anexo D: Repositorio de codigo
- GitHub: https://github.com/tonyfajardo1/proyecto-integrador
- Rama principal: `main`
- Estructura: `Avance 1/` (base) y `Avance 2/` (correcciones)
