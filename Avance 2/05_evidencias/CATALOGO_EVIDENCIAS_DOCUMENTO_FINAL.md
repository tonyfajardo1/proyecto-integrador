# Catalogo de Evidencias para Documento Final - Avance 2

Este catalogo describe cada imagen/evidencia y donde debe insertarse en el documento Word final.

---

## Instrucciones de uso

1. Abrir el documento Word (plantilla de biblioteca)
2. Insertar cada imagen en la seccion indicada
3. Agregar pie de figura con el texto proporcionado
4. Mantener el formato de la plantilla oficial

---

## SECCION 5: Arquitectura e Implementacion

### Figura 1: Arquitectura del Sistema
- **Archivo:** `Planificacion/arquitectura_horizontal.png`
- **Insertar en:** Seccion 5.1 Arquitectura general
- **Pie de figura:** "Figura 1. Arquitectura del Sistema - App Web Analitica CONDIMENSA. Muestra el flujo desde fuentes operacionales (MySQL/QuickBooks y Kronos) a traves de Mage AI con arquitectura Medallion (Bronze/Silver/Gold) hacia PostgreSQL y Dashboard Streamlit."
- **Tamaño sugerido:** Ancho completo de pagina

### Figura 2: Lista de Pipelines en Mage AI
- **Archivo:** `Avance 1/Evidencias/Pipeline List.png`
- **Insertar en:** Seccion 5.2 Fuentes y pipelines
- **Pie de figura:** "Figura 2. Pipelines implementados en Mage AI: 4 pipelines de Data Mining (clustering, anomalias, prediccion, asociacion) y 3 pipelines ETL (bronze, silver, gold)."
- **Tamaño sugerido:** Ancho completo de pagina

### Figura 3: Ejecucion Pipeline ETL Bronze
- **Archivo:** `Avance 2/05_evidencias/Imagenes/mage_etl_bronze.png`
- **Insertar en:** Seccion 5.2 despues de Figura 2
- **Pie de figura:** "Figura 3. Ejecucion exitosa del pipeline ETL Bronze (26 marzo 2026). Bloques: cargar_bronze, extraer_datos_bronze, crear_tablas_bronze - todos completados."
- **Tamaño sugerido:** Ancho completo de pagina

### Figura 4: Validacion SQL - Conteos Gold
- **Archivo:** `Avance 2/05_evidencias/Imagenes/sql_gold_conteos.png`
- **Insertar en:** Seccion 5.3 Reglas de calidad
- **Pie de figura:** "Figura 4. Validacion de datos en capa Gold: 2,683 filas totales, 2,656 activas, 27 inactivas en tabla gold.pronostico_produccion_resultado_v2."
- **Tamaño sugerido:** 70% ancho de pagina

---

## SECCION 6: Experimentos y Resultados

### Figura 5: Dashboard KPIs Principales
- **Archivo:** `Avance 2/05_evidencias/Imagenes/Resumen ejecutivo 1.png`
- **Insertar en:** Inicio de Seccion 6 (antes de 6.1)
- **Pie de figura:** "Figura 5. Dashboard de KPIs principales: Total Ventas $1,373,944, Rentabilidad $439,613, Tasa Devolucion 5.8%, 10 Agencias. Incluye respuestas a las 3 preguntas analiticas."
- **Tamaño sugerido:** Ancho completo de pagina

### Figura 6: Ventas por Agencia
- **Archivo:** `Avance 2/05_evidencias/Imagenes/Resumen ejecutivo 2.png`
- **Insertar en:** Seccion 6 despues de Figura 5
- **Pie de figura:** "Figura 6. Distribucion de ventas por agencia. Quito lidera con $512,415 (33% rentabilidad), seguido de Ibarra $160,679 y Riobamba $123,168."
- **Tamaño sugerido:** Ancho completo de pagina

### Figura 7: Benchmark de Modelos de Pronostico
- **Archivo:** `Avance 2/05_evidencias/Imagenes/benchmark_modelos .png`
- **Insertar en:** Seccion 6.1.5 Metricas reportadas
- **Pie de figura:** "Figura 7. Benchmark de modelos de pronostico. ExtraTrees logra mejor WAPE_test (0.3774) superando a RandomForest, GradientBoosting y baseline Lag-1."
- **Tamaño sugerido:** Ancho completo de pagina

### Figura 8: Dashboard de Pronosticos
- **Archivo:** `Avance 2/05_evidencias/Imagenes/dashboard_predicciones_kpis1.png`
- **Insertar en:** Seccion 6.1.7 Hallazgos accionables
- **Pie de figura:** "Figura 8. Dashboard de pronosticos: 724 productos vigentes, cantidad recomendada total 19,657,115 unidades. Top productos: Aliño Completo, Achiote Pasta, Cebolla Paitea."
- **Tamaño sugerido:** Ancho completo de pagina

### Figura 9: Reglas de Asociacion (Cross-Selling)
- **Archivo:** `Avance 2/05_evidencias/Imagenes/apriori1.png`
- **Insertar en:** Seccion 6.2.4 Metricas reportadas
- **Pie de figura:** "Figura 9. Dashboard Cross-Selling con Apriori: 9 reglas descubiertas, Lift maximo 15.57, Confianza promedio 52%. Top 3 reglas mostradas con productos FDA Popular y Faba Tostado."
- **Tamaño sugerido:** Ancho completo de pagina

### Figura 10: Deteccion de Anomalias
- **Archivo:** `Avance 2/05_evidencias/Imagenes/anomalias1.png`
- **Insertar en:** Seccion 6.3.3 Metricas reportadas
- **Pie de figura:** "Figura 10. Dashboard de anomalias: 10 agencias analizadas, 1 anomalia detectada (QUITO) con tipo ALTA_RENTABILIDAD, BAJO_COSTO, ALTO_TICKET. Tasa devolucion 5.6%, Rentabilidad 35.2%."
- **Tamaño sugerido:** Ancho completo de pagina

---

## EVIDENCIAS ADICIONALES (Anexos)

### Anexo B-1: Estructura del Proyecto ML
- **Archivo:** `Avance 2/05_evidencias/Imagenes/estructura_proyecto .png`
- **Descripcion:** Estructura de carpetas del proyecto de forecasting (notebooks, artifacts, mlruns, scripts, src)

### Anexo B-2: Pipeline ETL Silver
- **Archivo:** `Avance 2/05_evidencias/Imagenes/mage_etl_silver.png`
- **Descripcion:** Diagrama del pipeline ETL Silver en Mage AI

### Anexo B-3: Pipeline ETL Gold
- **Archivo:** `Avance 2/05_evidencias/Imagenes/mage_etl_gold.png`
- **Descripcion:** Diagrama del pipeline ETL Gold en Mage AI

### Anexo B-4: Wrangling Report
- **Archivo:** `Avance 2/05_evidencias/Imagenes/wrangling_report.png`
- **Descripcion:** Reporte de calidad de datos generado automaticamente

### Anexo B-5: Apriori Detalle
- **Archivo:** `Avance 2/05_evidencias/Imagenes/apriori2.png`
- **Descripcion:** Detalle adicional de reglas de asociacion

### Anexo B-6: Anomalias Detalle
- **Archivo:** `Avance 2/05_evidencias/Imagenes/anomalias2.png`
- **Descripcion:** Detalle adicional de agencias anomalas

---

## Resumen de KPIs extraidos de evidencias

| KPI | Valor | Fuente |
|-----|-------|--------|
| Total Ventas | $1,373,944 | Resumen ejecutivo 1.png |
| Rentabilidad | $439,613 | Resumen ejecutivo 1.png |
| Tasa Devolucion | 5.8% | Resumen ejecutivo 1.png |
| Agencias | 10 | Resumen ejecutivo 1.png |
| Reglas Cross-Selling | 9 | apriori1.png |
| Lift Maximo | 15.57 | apriori1.png |
| Confianza Promedio | 52% | apriori1.png |
| Anomalias Detectadas | 1 (QUITO) | anomalias1.png |
| Productos Pronosticados | 724 | dashboard_predicciones_kpis1.png |
| WAPE Mejor Modelo | 0.3774 | benchmark_modelos.png |
| Registros Gold | 2,683 | sql_gold_conteos.png |

---

## Comando para copiar imagenes a carpeta de documento

```powershell
# Crear carpeta de imagenes para documento Word
mkdir "F:\proyecto-integrador\Avance 2\DOCUMENTO_FINAL_WORD\imagenes"

# Copiar imagenes principales
copy "F:\proyecto-integrador\Planificacion\arquitectura_horizontal.png" "F:\proyecto-integrador\Avance 2\DOCUMENTO_FINAL_WORD\imagenes\fig01_arquitectura.png"
copy "F:\proyecto-integrador\Avance 1\Evidencias\Pipeline List.png" "F:\proyecto-integrador\Avance 2\DOCUMENTO_FINAL_WORD\imagenes\fig02_pipelines.png"
copy "F:\proyecto-integrador\Avance 2\05_evidencias\Imagenes\mage_etl_bronze.png" "F:\proyecto-integrador\Avance 2\DOCUMENTO_FINAL_WORD\imagenes\fig03_etl_bronze.png"
copy "F:\proyecto-integrador\Avance 2\05_evidencias\Imagenes\sql_gold_conteos.png" "F:\proyecto-integrador\Avance 2\DOCUMENTO_FINAL_WORD\imagenes\fig04_sql_gold.png"
copy "F:\proyecto-integrador\Avance 2\05_evidencias\Imagenes\Resumen ejecutivo 1.png" "F:\proyecto-integrador\Avance 2\DOCUMENTO_FINAL_WORD\imagenes\fig05_kpis.png"
copy "F:\proyecto-integrador\Avance 2\05_evidencias\Imagenes\Resumen ejecutivo 2.png" "F:\proyecto-integrador\Avance 2\DOCUMENTO_FINAL_WORD\imagenes\fig06_agencias.png"
copy "F:\proyecto-integrador\Avance 2\05_evidencias\Imagenes\benchmark_modelos .png" "F:\proyecto-integrador\Avance 2\DOCUMENTO_FINAL_WORD\imagenes\fig07_benchmark.png"
copy "F:\proyecto-integrador\Avance 2\05_evidencias\Imagenes\dashboard_predicciones_kpis1.png" "F:\proyecto-integrador\Avance 2\DOCUMENTO_FINAL_WORD\imagenes\fig08_pronosticos.png"
copy "F:\proyecto-integrador\Avance 2\05_evidencias\Imagenes\apriori1.png" "F:\proyecto-integrador\Avance 2\DOCUMENTO_FINAL_WORD\imagenes\fig09_apriori.png"
copy "F:\proyecto-integrador\Avance 2\05_evidencias\Imagenes\anomalias1.png" "F:\proyecto-integrador\Avance 2\DOCUMENTO_FINAL_WORD\imagenes\fig10_anomalias.png"
```
