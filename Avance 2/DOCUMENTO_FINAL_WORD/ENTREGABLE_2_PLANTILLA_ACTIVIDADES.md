# ENTREGABLE 2 - PROYECTO INTEGRADOR

## Informacion General

| Campo | Valor |
|-------|-------|
| **Estudiante** | Anthony Fajardo |
| **Codigo** | [Completar codigo estudiante] |
| **Carrera** | Ingenieria en Ciencias de la Computacion |
| **Tutor** | Jose Vega |
| **Periodo** | 2025-2026 |
| **Fecha de entrega** | 29 de marzo de 2026 |

---

## 1. Titulo del Proyecto

**Aplicacion de tecnicas de Data Mining para analisis de devoluciones, desviaciones plan vs real y deteccion de anomalias en CONDIMENSA**

---

## 2. Resumen de Actividades Realizadas (Periodo Avance 2)

### 2.1 Actividades Completadas

| # | Actividad | Descripcion | Evidencia |
|---|-----------|-------------|-----------|
| 1 | Correccion metodologica de modelos ML | Implementacion de split temporal para evitar data leakage. Cambio de clasificacion a regresion para pronostico. | `03_modelado/CHECKLIST_ANTI_LEAKAGE_Y_EVALUACION.md` |
| 2 | Benchmark de algoritmos | Comparacion de ExtraTrees, RandomForest, GradientBoosting vs baseline Lag-1. Mejor modelo: ExtraTrees (WAPE 0.3774). | `05_evidencias/RESUMEN_BENCHMARK_FORECASTING.md` |
| 3 | Estado del arte con trabajos relacionados | Incorporacion de 5 papers relevantes (Gu 2024, Zhang 2024, Baur 2025, Santos 2025, Jadhav 2023). | Seccion 2.2 del documento final |
| 4 | Justificacion OLTP vs OLAP | Documentacion de por que se separa capa transaccional de analitica y justificacion de arquitectura Medallion. | Seccion 3 del documento final |
| 5 | Integracion de arquitectura en documento | Arquitectura movida de anexos al cuerpo principal del documento (Seccion 5). | Seccion 5.1 con diagrama |
| 6 | Metricas completas de evaluacion | Reporte de MAE, RMSE, WAPE, Lift, Confianza, Jaccard segun tipo de experimento. | `03_modelado/MATRIZ_METRICAS_EXPERIMENTOS.md` |
| 7 | Dashboard funcional Streamlit | Visualizacion de KPIs, pronosticos, reglas de asociacion y anomalias. | `dashboard/` y capturas en evidencias |
| 8 | Actualizacion de repositorio GitHub | Commit de Avance 2 con estructura organizada. | https://github.com/tonyfajardo1/proyecto-integrador |

### 2.2 Correcciones Aplicadas segun Retroalimentacion del Entregable 1

| Observacion del Profesor | Accion Tomada | Estado |
|--------------------------|---------------|--------|
| Estado del arte sin trabajos relacionados | Agregada tabla con 5 papers y analisis critico | COMPLETADO |
| AUC-ROC = 0.9993 sospechoso (posible leakage) | Implementado split temporal, target t+1, metricas WAPE | COMPLETADO |
| Arquitectura en anexos | Movida a Seccion 5 del documento principal | COMPLETADO |
| No explica OLTP vs OLAP | Agregada Seccion 3 con justificacion tecnica | COMPLETADO |
| Falta distribucion de clases | Reportado N=10,316 con split Train/Val/Test | COMPLETADO |
| Metricas incompletas | Agregadas MAE, RMSE, WAPE, Lift, Confianza, Jaccard | COMPLETADO |
| Crear repositorio GitHub | Repositorio activo con commits del proyecto | COMPLETADO |

---

## 3. Avance vs Cronograma

| Actividad Planificada | Fecha Planificada | Fecha Real | Estado |
|-----------------------|-------------------|------------|--------|
| Documento de planificacion | Semana 1-2 | Completado | OK |
| Estado del arte + KPIs | Semana 1-3 | Completado | OK |
| Diseño Data Mart PostgreSQL | Semana 2-3 | Completado | OK |
| Pipeline 1 (Produccion) | Semana 3-4 | Completado | OK |
| Pipeline 2 (Comercial Kronos) | Semana 3-4 | Completado | OK |
| Pipeline 3 (Integracion + DM) | Semana 4-5 | Completado | OK |
| Dashboard Streamlit | Semana 4-5 | Completado | OK |
| Experimentos y documentacion | Semana 5 | Completado | OK |

**Porcentaje de avance:** 100% de actividades planificadas para Avance 2

---

## 4. Resultados Principales del Periodo

### 4.1 Resultados Cuantitativos

| Metrica | Valor | Interpretacion |
|---------|-------|----------------|
| WAPE modelo pronostico | 0.3774 | 6.71% mejor que baseline |
| Reglas de asociacion | 9 estables | Lift promedio 15.57 |
| Anomalias detectadas | 1 agencia | QUITO requiere investigacion |
| Productos pronosticados | 724 | Cobertura completa |
| Registros procesados | 10,316 | Dataset completo |

### 4.2 Entregables Generados

1. Documento tecnico final (formato biblioteca USFQ)
2. Presentacion de 5 minutos con guion
3. Repositorio GitHub actualizado
4. Dashboard funcional en Streamlit
5. Evidencias de ejecucion (capturas)

---

## 5. Siguientes Pasos (Avance 3)

1. Validacion con usuarios de CONDIMENSA
2. Refinamiento de modelos segun feedback operativo
3. Despliegue productivo del dashboard
4. Documentacion final y manual de usuario

---

## 6. Firma del Tutor

| | |
|---|---|
| **Nombre del Tutor:** | Jose Vega |
| **Firma:** | _________________________ |
| **Fecha:** | ____/____/2026 |

---

**Nota:** Este documento debe estar firmado por el tutor para ser valido. Entregables sin firma obtendran calificacion de cero.
