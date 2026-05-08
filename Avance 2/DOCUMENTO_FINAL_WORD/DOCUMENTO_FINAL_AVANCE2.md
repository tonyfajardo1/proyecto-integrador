# APLICACION DE TECNICAS DE DATA MINING PARA ANALISIS DE DEVOLUCIONES, DESVIACIONES PLAN VS REAL Y DETECCION DE ANOMALIAS EN CONDIMENSA

**Proyecto Integrador - Avance 2**

---

**Estudiante:** Anthony Fajardo

**Tutor:** Jose Vega

**Carrera:** Ingenieria en Ciencias de la Computacion

**Universidad:** Universidad San Francisco de Quito

**Fecha:** 26 de marzo de 2026

---

## RESUMEN

Este proyecto aplica tecnicas de Data Mining sobre datos integrados de la empresa CONDIMENSA para responder tres preguntas analiticas: (1) que factores permiten pronosticar desviaciones entre plan y produccion real, (2) que productos se venden juntos para estrategias de cross-selling, y (3) que agencias presentan comportamientos atipicos. Se implemento una arquitectura Medallion (Bronze/Silver/Gold) sobre PostgreSQL, orquestada con Mage AI y visualizada en Streamlit. Los resultados muestran que ExtraTrees reduce el error de pronostico en 6.71% vs baseline, se identificaron 9 reglas de asociacion con Lift promedio de 15.57, y se detecto 1 agencia anomala (QUITO) con estabilidad bootstrap de 70%. El proyecto contribuye con una metodologia reproducible, control anti-leakage explicito y stack open-source.

**Palabras clave:** Data Mining, CRISP-DM, Arquitectura Medallion, Pronostico, Reglas de Asociacion, Deteccion de Anomalias, CONDIMENSA

---

## TABLA DE CONTENIDOS

1. Introduccion
2. Estado del Arte
3. Marco Conceptual y Justificacion Arquitectonica
4. Metodologia (CRISP-DM)
5. Arquitectura e Implementacion
6. Experimentos y Resultados
7. Validacion Metodologica
8. Discusion
9. Avance vs Cronograma
10. Conclusiones y Siguientes Pasos
11. Referencias
12. Anexos

---

## 1. INTRODUCCION

### 1.1 Contexto

CONDIMENSA es una empresa ecuatoriana dedicada a la produccion y comercializacion de condimentos y productos alimenticios. La empresa opera con dos sistemas transaccionales principales: QuickBooks/ODIN para produccion y operaciones, y Kronos para gestion comercial. Esta separacion dificulta el analisis integrado de informacion para la toma de decisiones.

### 1.2 Planteamiento del Problema

El avance previo priorizo la infraestructura (ETL, capas y dashboard), pero no evidencio con suficiente rigor la parte de Data Mining. En este avance se corrige ese desbalance, enfocando la evaluacion en preguntas de negocio, metricas adecuadas y validez metodologica. Especificamente, se abordan las observaciones del Entregable 1: estado del arte incompleto, posible data leakage en modelos, arquitectura en anexos, y metricas insuficientes.

### 1.3 Preguntas Analiticas No Triviales

1. **Pronostico de produccion:** ¿Que factores permiten anticipar desviaciones entre cantidad planificada y cantidad real despachada?
2. **Cross-selling:** ¿Que productos tienden a venderse juntos y pueden aprovecharse para promociones combinadas?
3. **Anomalias:** ¿Que agencias presentan comportamientos atipicos que requieren investigacion prioritaria?

### 1.4 Objetivo General

Aplicar tecnicas de Data Mining sobre datos integrados de CONDIMENSA para responder preguntas analiticas no triviales y generar recomendaciones accionables con evaluacion metodologica rigurosa.

### 1.5 Objetivos Especificos

1. Integrar datos de fuentes operacionales en una capa analitica OLAP con trazabilidad.
2. Construir y evaluar modelos para pronostico y analisis de patrones con enfoque anti-leakage.
3. Detectar anomalias en agencias y priorizar acciones de investigacion.
4. Reportar resultados con metricas completas y evidencia reproducible.

### 1.6 Alcance y Limitaciones

- **Periodo analizado:** Julio 2024 - Enero 2026 (18 meses)
- **Unidad de analisis:** producto-periodo (pronostico), transaccion (asociacion), agencia (anomalias)
- **Fuentes de datos:** QuickBooks/ODIN (produccion), Kronos (comercial), PostgreSQL (Gold)
- **Limitaciones:**
  - Cobertura temporal de 18 meses puede no capturar estacionalidad anual completa
  - Dataset de agencias pequeno (N=10) limita robustez estadistica
  - Validacion operativa con stakeholders pendiente

---

## 2. ESTADO DEL ARTE

### 2.1 Fundamentos

El proyecto sigue CRISP-DM (Cross-Industry Standard Process for Data Mining) para alinear objetivos de negocio con preparacion de datos, modelado y evaluacion (Chapman et al., 2000). Se utilizan tecnicas de regresion (Random Forest, ExtraTrees), reglas de asociacion (Apriori, FP-Growth) y deteccion de anomalias (Isolation Forest, LOF).

### 2.2 Trabajos Relacionados

| Trabajo | Problema | Datos | Tecnica | Metrica | Aporte |
|---------|----------|-------|---------|---------|--------|
| Gu et al. (2024) | Prediccion devoluciones e-commerce | Reviews 5 categorias | Random Forest | AUC-ROC | Confirma RF para PRB |
| Zhang et al. (2024) | Gestion devoluciones retail | Transaccional | LR, RF, GB | AUC-ROC | Variables clave identificadas |
| Baur et al. (2025) | Devoluciones textiles | Retail con desbalance | XGBoost, RF | Balanced Acc 0.86 | Viabilidad en manufactura |
| Santos et al. (2025) | Anomalias en compras | Transacciones empresariales | K-Means + IF | Precision alertas | Enfoque hibrido |
| Jadhav et al. (2023) | Market basket analysis | POS retail | Apriori | Lift, Confianza | Cross-selling validado |

### 2.3 Analisis Critico

La literatura confirma la efectividad de Random Forest y Gradient Boosting para prediccion en retail y manufactura, con AUC-ROC entre 0.69 y 0.86. Para anomalias, Isolation Forest combinado con clustering se valida en contextos empresariales. Apriori sigue siendo estandar para market basket analysis.

Sin embargo, la mayoria de implementaciones no muestran integracion con arquitectura reproducible ni controles anti-leakage explicitos. Este proyecto contribuye al aplicar estas tecnicas en contexto manufacturero ecuatoriano con arquitectura Medallion, control metodologico riguroso y stack open-source.

---

## 3. MARCO CONCEPTUAL Y JUSTIFICACION ARQUITECTONICA

### 3.1 OLTP vs OLAP

| Aspecto | OLTP | OLAP |
|---------|------|------|
| Proposito | Registrar transacciones | Analizar historicos |
| Consultas | Cortas y frecuentes | Agregadas e intensivas |
| Rendimiento | Baja latencia | Alto throughput analitico |
| Riesgo | Alto si se sobrecargan | Bajo para operacion |

**Justificacion:** Separar OLTP y OLAP evita afectar sistemas operacionales durante analisis y entrenamiento de modelos.

### 3.2 Arquitectura Medallion

- **Bronze:** Datos crudos con minima transformacion
- **Silver:** Datos estandarizados y limpios
- **Gold:** Tablas analiticas para modelado y dashboard

**Beneficios:** Trazabilidad, control de calidad, reproducibilidad, consumo analitico sin impactar fuentes.

---

## 4. METODOLOGIA (CRISP-DM)

### 4.1 Business Understanding

- **KPI Pronostico:** WAPE (Weighted Absolute Percentage Error)
- **KPI Asociacion:** Lift y Confianza
- **KPI Anomalias:** Estabilidad bootstrap (Jaccard)

### 4.2 Data Understanding

- **Tablas fuente:** bronze.quickbooks_produccion_raw, bronze.kronos_ventas_raw
- **Cobertura:** 18 meses (Jul 2024 - Ene 2026)
- **Registros:** ~10,000 produccion, ~2,500 transacciones

### 4.3 Data Preparation

- Integracion QuickBooks + Kronos en Silver
- Features temporales: lag_1, lag_2, lag_3, tendencia_3m
- Control de leakage: exclusion de variables post-evento

### 4.4 Modeling

- **Pronostico:** ExtraTrees, RandomForest, GradientBoosting
- **Asociacion:** Apriori, FP-Growth
- **Anomalias:** LOF, Isolation Forest, One-Class SVM

### 4.5 Evaluation

- **Split temporal:** Train (Jul24-May25) / Val (Jun25-Sep25) / Test (Oct25-Ene26)
- **Metricas:** MAE, RMSE, WAPE, Lift, Confianza, Jaccard

### 4.6 Deployment

- Pipelines Mage AI: etl_bronze, etl_silver, etl_gold, dm_*
- Resultados en PostgreSQL Gold
- Dashboard Streamlit

---

## 5. ARQUITECTURA E IMPLEMENTACION

### 5.1 Arquitectura General

[INSERTAR FIGURA 1: imagenes/fig01_arquitectura.png]

**Figura 1.** Arquitectura del Sistema - App Web Analitica CONDIMENSA. Flujo desde fuentes operacionales (MySQL/QuickBooks y Kronos) a traves de Mage AI con Medallion hacia PostgreSQL y Streamlit.

### 5.2 Pipelines Implementados

[INSERTAR FIGURA 2: imagenes/fig02_pipelines.png]

**Figura 2.** Pipelines en Mage AI: 4 de Data Mining y 3 ETL.

| Fuente | Bronze | Silver | Gold | Data Mining |
|--------|--------|--------|------|-------------|
| QuickBooks | etl_bronze | etl_silver | etl_gold | dm_pronostico |
| Kronos | etl_bronze | etl_silver | etl_gold | dm_asociacion, dm_anomalias |

[INSERTAR FIGURA 3: imagenes/fig03_etl_bronze.png]

**Figura 3.** Ejecucion exitosa del pipeline ETL Bronze (26 marzo 2026).

[INSERTAR FIGURA 11: imagenes/fig11_etl_silver.png]

**Figura 11.** Ejecucion pipeline ETL Silver: transformacion y limpieza.

[INSERTAR FIGURA 12: imagenes/fig12_etl_gold.png]

**Figura 12.** Ejecucion pipeline ETL Gold: cargar_gold, calcular_kpis_gold, extraer_desde_silver, crear_tablas_gold.

### 5.3 Reglas de Calidad

[INSERTAR FIGURA 4: imagenes/fig04_sql_gold.png]

**Figura 4.** Validacion SQL: 2,683 registros en Gold (2,656 activos, 27 inactivos).

[INSERTAR FIGURA 16: imagenes/fig16_sql_silver.png]

**Figura 16.** Query Silver: tipo_producto, producto, periodo, qty_planificada, qty_fabricada, n_ordenes.

[INSERTAR FIGURA 19: imagenes/fig19_wrangling.png]

**Figura 19.** Wrangling Report: 14,670 rows, 904 productos, 21 periodos, 2,434 imputados, 108 outliers.

| Regla | Tabla | Tipo | Resultado |
|-------|-------|------|-----------|
| not_null(producto) | silver.kronos_ventas | Integridad | PASS |
| unique(id) | gold.kpis_ventas | Unicidad | PASS |
| range(tasa_devolucion) | gold.metricas | Dominio | PASS |
| rows_output | wrangling_report | Completitud | 14,670 |
| outliers_detectados | wrangling_report | Anomalias | 108 |

### 5.4 Repositorio

- **GitHub:** https://github.com/tonyfajardo1/proyecto-integrador
- **Estructura:** Avance 1/ (base) y Avance 2/ (correcciones)
- **Semilla:** random_state=42

---

## 6. EXPERIMENTOS Y RESULTADOS

[INSERTAR FIGURA 5: imagenes/fig05_kpis.png]

**Figura 5.** Dashboard KPIs: Total Ventas $1,373,944, Rentabilidad $439,613, Tasa Devolucion 5.8%, 10 Agencias.

[INSERTAR FIGURA 6: imagenes/fig06_agencias.png]

**Figura 6.** Ventas por agencia: Quito lidera con $512,415 (33% rentabilidad).

### 6.1 Experimento 1: Pronostico de Produccion

**Objetivo:** Predecir cantidad despachada (t+1)

**Dataset:** 10,316 registros
- Train: 5,667 (Jul24-May25)
- Validation: 2,432 (Jun25-Sep25)
- Test: 2,217 (Oct25-Ene26)

[INSERTAR FIGURA 7: imagenes/fig07_benchmark.png]

**Figura 7.** Benchmark de modelos. ExtraTrees logra WAPE 0.3774, superando baseline.

| Modelo | MAE | RMSE | WAPE | Mejora vs Baseline |
|--------|-----|------|------|-------------------|
| **ExtraTrees** | 2,790.86 | 9,280.11 | **0.3774** | **+6.71%** |
| RandomForest | 2,860.15 | 9,534.26 | 0.3867 | +5.77% |
| GradientBoosting | 2,904.00 | 9,949.91 | 0.3927 | +5.18% |
| Baseline_Lag1 | 3,287.20 | 11,339.15 | 0.4445 | - |

[INSERTAR FIGURA 8: imagenes/fig08_pronosticos.png]

**Figura 8.** Dashboard pronosticos: 724 productos, 19.6M unidades recomendadas.

[INSERTAR FIGURA 13: imagenes/fig13_scatter.png]

**Figura 13.** Scatter Pronostico vs Plan historico con niveles de confianza (Baja/Media/Alta) y tabla de detalle.

[INSERTAR FIGURA 20: imagenes/fig20_inactivos.png]

**Figura 20.** Productos excluidos por vigencia con razon de exclusion y sugerencia.

**Hallazgos:**
1. ExtraTrees reduce error de planificacion en 6.71%
2. Variables importantes: lag_1, lag_2, tendencia_3m
3. Aplicacion: ajustar ordenes de produccion

### 6.2 Experimento 2: Reglas de Asociacion

**Objetivo:** Identificar productos que se venden juntos

**Dataset:** ~2,500 transacciones
- min_support = 0.02
- min_confidence = 0.35

[INSERTAR FIGURA 9: imagenes/fig09_apriori.png]

**Figura 9.** Cross-Selling: 9 reglas, Lift maximo 15.57, Confianza 52%.

[INSERTAR FIGURA 15: imagenes/fig15_apriori_detalle.png]

**Figura 15.** Interpretacion de metricas (Soporte, Confianza, Lift), grafico Lift por regla, scatter Confianza vs Lift, y recomendaciones de negocio.

| Algoritmo | Reglas | Lift | Confianza test | Jaccard |
|-----------|--------|------|----------------|---------|
| **FPGrowth** | 9 | 15.57 | 0.52 | 1.00 |
| Apriori | 9 | 15.57 | 0.52 | 1.00 |

**Recomendacion principal:** Cuando un cliente compra FDA POPULAR 5 NEGRO LLANA, hay 70% probabilidad de que compre FDA POPULAR 2 NEGRO LLANA (Lift 15.6x mas fuerte que azar).

**Hallazgos:**
1. 9 reglas estables con confianza >50%
2. Lift 15.57 indica asociaciones muy fuertes
3. Aplicacion: crear combos promocionales, colocar productos cerca en punto de venta

### 6.3 Experimento 3: Deteccion de Anomalias

**Objetivo:** Identificar agencias atipicas

**Dataset:** 10 agencias
- Contamination: 10%

[INSERTAR FIGURA 10: imagenes/fig10_anomalias.png]

**Figura 10.** Anomalias: QUITO detectada (Alta rentabilidad, bajo costo, alto ticket).

[INSERTAR FIGURA 14: imagenes/fig14_anomalias_detalle.png]

**Figura 14.** Detalle completo: Tasa devolucion por agencia (barras), Mapa Devolucion vs Rentabilidad (scatter con QUITO en rojo), Tabla de 10 agencias con metricas.

| Algoritmo | Anomalias | Bootstrap Jaccard | Score |
|-----------|-----------|-------------------|-------|
| **LOF** | 1 | **0.70** | 0.42 |
| IsolationForest | 1 | 0.33 | 0.20 |
| PCA | 1 | 0.30 | 0.18 |

**Detalle de QUITO (anomalia):**
- Tasa Devolucion: 5.6%
- Rentabilidad: 35.2%
- Total Ventas: $512,415
- Tipo: ALTA_RENTABILIDAD, BAJO_COSTO, ALTO_TICKET

**Hallazgos:**
1. LOF tiene mejor estabilidad (Jaccard 0.70)
2. QUITO identificada como anomala por combinacion atipica de metricas
3. Aplicacion: priorizar auditoria, investigar practicas para replicar en otras agencias

---

## 7. VALIDACION METODOLOGICA

### 7.1 Control de Leakage

- [x] Target representa evento futuro (t+1)
- [x] Features no contienen informacion del target
- [x] Split temporal aplicado
- [x] Transformaciones solo en train

### 7.2 Control de Overfitting

| Modelo | Gap Train-Val | Gap Val-Test | Evaluacion |
|--------|---------------|--------------|------------|
| ExtraTrees | 0.2065 | 0.0496 | Generaliza bien |

Gap val-test pequeño (<0.06) confirma generalizacion adecuada.

---

## 8. DISCUSION

### 8.1 Respuestas a Preguntas de Negocio

**P1 (Pronostico):** ExtraTrees con WAPE 0.3774 supera baseline en 6.71%.
**P2 (Cross-selling):** 9 reglas estables con Lift 15.57.
**P3 (Anomalias):** QUITO detectada con estabilidad 70%.

### 8.2 Implicaciones para CONDIMENSA

| Area | Hallazgo | Accion | Impacto |
|------|----------|--------|---------|
| Produccion | -6.71% error | Ajustar ordenes | Reducir inventario |
| Comercial | 9 reglas | Crear combos | Aumentar ticket |
| Control | 1 anomalia | Auditoria | Reducir riesgo |

### 8.3 Limitaciones

1. N=10 agencias limita robustez de anomalias
2. 18 meses puede no capturar estacionalidad completa
3. Validacion operativa pendiente

---

## 9. AVANCE VS CRONOGRAMA

| Actividad | Planificado | Estado |
|-----------|-------------|--------|
| Documento planificacion | Semana 1-2 | OK |
| Estado del arte | Semana 1-3 | OK |
| Data Mart PostgreSQL | Semana 2-3 | OK |
| Pipelines ETL | Semana 3-4 | OK |
| Pipelines DM | Semana 4-5 | OK |
| Dashboard | Semana 4-5 | OK |
| Experimentacion | Semana 5 | OK |

**Avance:** 100% completado

---

## 10. CONCLUSIONES Y SIGUIENTES PASOS

### 10.1 Conclusiones

1. **Validez metodologica:** Split temporal, control anti-leakage, metricas completas.
2. **Arquitectura justificada:** OLTP/OLAP con Medallion fundamentada tecnicamente.
3. **Resultados accionables:** Pronostico -6.71% error, 9 reglas cross-selling, 1 anomalia.
4. **Contribucion:** Data Mining en contexto manufacturero ecuatoriano con stack open-source.

### 10.2 Siguientes Pasos

1. Validacion con usuarios CONDIMENSA
2. Refinamiento de modelos
3. Despliegue productivo
4. Documentacion final

---

## 11. REFERENCIAS

[1] Gu, Y., Chen, X., & Wang, L. (2024). Understanding and predicting online product return behavior. *Int. J. Production Economics*, 267, 109066.

[2] Zhang, H., Liu, M., & Chen, S. (2024). Return management in e-commerce firms. *J. Cleaner Production*, 434, 140123.

[3] Baur, A., Schmidt, K., & Weber, M. (2025). Machine learning for garment returns prediction. *SN Computer Science*, 6(2), 89.

[4] Santos, R., Ferreira, P., & Oliveira, T. (2025). Anomaly detection in enterprise purchase processes. *Information*, 16(3), 177.

[5] Jadhav, A., Jadhav, A., & Jadhav, R. D. (2023). Association rule mining in retail. *SSRN*.

[6] Kimball, R., & Ross, M. (2013). *The Data Warehouse Toolkit* (3rd ed.). Wiley.

[7] Chapman, P. et al. (2000). CRISP-DM 1.0. *SPSS Inc.*

[8] Liu, F. T., Ting, K. M., & Zhou, Z. H. (2008). Isolation forest. *IEEE ICDM*, 413-422.

[9] Agrawal, R., & Srikant, R. (1994). Fast algorithms for mining association rules. *VLDB*, 487-499.

---

## 12. ANEXOS

### Anexo A: Diccionario de Datos
Ver `sql/00_crear_todas_tablas.sql`

### Anexo B: Evidencias de Ejecucion
Ver `05_evidencias/`

### Anexo C: Checklist Metodologico
Ver `03_modelado/CHECKLIST_ANTI_LEAKAGE_Y_EVALUACION.md`

### Anexo D: Repositorio
https://github.com/tonyfajardo1/proyecto-integrador
