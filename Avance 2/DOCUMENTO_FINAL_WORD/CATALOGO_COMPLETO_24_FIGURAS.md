# Catálogo Completo de 24 Figuras para Documento Final

## Resumen de Evidencias

| Total Figuras | 24 |
|---------------|-----|
| Arquitectura | 4 figuras |
| Pipelines ETL | 3 figuras |
| SQL/Datos | 6 figuras |
| Dashboard KPIs | 3 figuras |
| Experimentos ML | 8 figuras |

---

## SECCIÓN 5: Arquitectura e Implementación

### Figura 1: Arquitectura del Sistema
- **Archivo:** `fig01_arquitectura.png`
- **Pie:** "Arquitectura del Sistema CONDIMENSA: Fuentes (MySQL, Kronos) → Mage AI (Medallion) → PostgreSQL → Streamlit"

### Figura 2: Lista de Pipelines
- **Archivo:** `fig02_pipelines.png`
- **Pie:** "7 pipelines en Mage AI: 4 Data Mining + 3 ETL (Bronze, Silver, Gold)"

### Figura 3: Pipeline ETL Bronze
- **Archivo:** `fig03_etl_bronze.png`
- **Pie:** "Ejecución ETL Bronze (26/03/2026): cargar_bronze, extraer_datos, crear_tablas - completado"

### Figura 11: Pipeline ETL Silver
- **Archivo:** `fig11_etl_silver.png`
- **Pie:** "Ejecución ETL Silver: transformación y limpieza de datos"

### Figura 12: Pipeline ETL Gold
- **Archivo:** `fig12_etl_gold.png`
- **Pie:** "Ejecución ETL Gold: cargar_gold, calcular_kpis_gold, extraer_desde_silver, crear_tablas_gold"

### Figura 21: Estructura del Proyecto ML
- **Archivo:** `fig21_estructura.png`
- **Pie:** "Estructura del proyecto de forecasting: notebooks, artifacts, mlruns, scripts, src"

### Figura 22: Artefactos Generados
- **Archivo:** `fig22_artefactos.png`
- **Pie:** "Artefactos de MLflow generados durante experimentación"

### Figura 23: Documentación E2E
- **Archivo:** `fig23_documentacion.png`
- **Pie:** "Documentación end-to-end del proceso de forecasting"

---

## SECCIÓN 5.3: Calidad de Datos

### Figura 4: Validación SQL Gold - Conteos
- **Archivo:** `fig04_sql_gold.png`
- **Pie:** "Validación Gold: 2,683 filas totales, 2,656 activas, 27 inactivas"

### Figura 16: Muestra SQL Silver
- **Archivo:** `fig16_sql_silver.png`
- **Pie:** "Query silver.produccion_modelado_mensual: tipo_producto, producto, periodo, qty_planificada, qty_fabricada"

### Figura 17: Conteos SQL Silver
- **Archivo:** `fig17_sql_silver_conteos.png`
- **Pie:** "Conteos de registros en capa Silver"

### Figura 18: Muestra SQL Gold
- **Archivo:** `fig18_sql_gold_muestra.png`
- **Pie:** "Muestra de datos en capa Gold con KPIs calculados"

### Figura 19: Wrangling Report
- **Archivo:** `fig19_wrangling.png`
- **Pie:** "Reporte de calidad: 14,670 rows, 904 productos, 21 periodos, 2,434 imputados, 108 outliers extremos"

### Figura 24: Qty Planificada
- **Archivo:** `fig24_qty_planificada.png`
- **Pie:** "Análisis de cantidad planificada vs fabricada"

---

## SECCIÓN 6: Experimentos y Resultados

### Figura 5: Dashboard KPIs Principales
- **Archivo:** `fig05_kpis.png`
- **Pie:** "KPIs: Total Ventas $1,373,944, Rentabilidad $439,613, Tasa Devolución 5.8%, 10 Agencias"

### Figura 6: Ventas por Agencia
- **Archivo:** `fig06_agencias.png`
- **Pie:** "Distribución ventas: Quito $512,415 (33%), Ibarra $160,679, Riobamba $123,168"

---

## SECCIÓN 6.1: Experimento 1 - Pronóstico

### Figura 7: Benchmark de Modelos
- **Archivo:** `fig07_benchmark.png`
- **Pie:** "Benchmark: ExtraTrees (WAPE 0.3774) supera RandomForest, GradientBoosting y baseline Lag-1"

### Figura 8: Dashboard Pronósticos
- **Archivo:** `fig08_pronosticos.png`
- **Pie:** "724 productos vigentes, 19.6M unidades recomendadas, top: Aliño Completo, Achiote, Cebolla"

### Figura 13: Scatter Pronóstico vs Plan
- **Archivo:** `fig13_scatter.png`
- **Pie:** "Pronóstico vs Plan histórico: puntos por nivel de confianza (Baja/Media/Alta) + tabla detalle"

### Figura 20: Productos Inactivos
- **Archivo:** `fig20_inactivos.png`
- **Pie:** "Productos excluidos por vigencia: razón de exclusión y sugerencia de acción"

---

## SECCIÓN 6.2: Experimento 2 - Cross-Selling

### Figura 9: Dashboard Apriori
- **Archivo:** `fig09_apriori.png`
- **Pie:** "Cross-Selling: 9 reglas, Lift máximo 15.57, Confianza promedio 52%, top 3 reglas"

### Figura 15: Apriori Detalle
- **Archivo:** `fig15_apriori_detalle.png`
- **Pie:** "Interpretación métricas (Soporte, Confianza, Lift) + Gráfico Lift por regla + Recomendaciones de negocio"

---

## SECCIÓN 6.3: Experimento 3 - Anomalías

### Figura 10: Dashboard Anomalías
- **Archivo:** `fig10_anomalias.png`
- **Pie:** "10 agencias analizadas, 1 anomalía (QUITO): Alta rentabilidad, bajo costo, alto ticket"

### Figura 14: Anomalías Detalle
- **Archivo:** `fig14_anomalias_detalle.png`
- **Pie:** "Tasa devolución por agencia + Mapa Devolución vs Rentabilidad + Tabla completa 10 agencias"

---

## Datos Clave Extraídos de Evidencias

| KPI | Valor | Fuente |
|-----|-------|--------|
| Total Ventas | $1,373,944 | fig05_kpis |
| Rentabilidad | $439,613 | fig05_kpis |
| Tasa Devolución | 5.8% | fig05_kpis |
| Agencias | 10 | fig05_kpis |
| Productos Output | 904 | fig19_wrangling |
| Periodos | 21 | fig19_wrangling |
| Rows Procesadas | 14,670 | fig19_wrangling |
| Rows Imputadas | 2,434 | fig19_wrangling |
| Outliers Extremos | 108 | fig19_wrangling |
| WAPE Mejor Modelo | 0.3774 | fig07_benchmark |
| Mejora vs Baseline | +6.71% | fig07_benchmark |
| Reglas Cross-Selling | 9 | fig09_apriori |
| Lift Máximo | 15.57 | fig09_apriori |
| Confianza Promedio | 52% | fig09_apriori |
| Anomalías Detectadas | 1 (QUITO) | fig10_anomalias |
| Registros Gold | 2,683 | fig04_sql_gold |
| Productos Pronóstico | 724 | fig08_pronosticos |

---

## Instrucciones de Inserción en Word

Para cada figura marcada `[INSERTAR FIGURA X]` en el documento:

1. **Insertar → Imagen → Desde archivo**
2. Seleccionar de carpeta `imagenes/figXX_nombre.png`
3. **Ajustar tamaño:** Ancho de página para arquitectura/dashboards, 70% para SQL
4. **Agregar pie de figura:** Insertar → Leyenda → "Figura X. [texto del pie]"
5. **Estilo:** Centrado, con borde si lo requiere la plantilla

---

## Figuras Recomendadas por Sección

### Documento Principal (mínimo 10)
- fig01, fig02, fig05, fig07, fig08, fig09, fig10, fig13, fig14, fig15

### Anexos (opcionales, 14 adicionales)
- fig03, fig04, fig06, fig11, fig12, fig16-24
