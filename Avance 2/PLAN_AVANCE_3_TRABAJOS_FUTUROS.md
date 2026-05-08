# Plan Avance 3 - Trabajos Futuros para Cierre 100%

## Objetivo
Completar los componentes tecnicos, operativos y documentales faltantes para dejar el proyecto totalmente listo para entrega final y sustentacion.

## Estado actual (base alcanzada)
- Flujo E2E de forecasting operativo: datos -> modelado -> publicacion Gold -> dashboard.
- Pipelines ETL depurados y ejecutando.
- Modelo benchmark con seleccion por validacion temporal.
- Dashboard con salida operativa (minimo, recomendado, maximo) y estado de productos.

## Trabajos futuros pendientes (Avance 3)

### 1) Consolidacion de datos comerciales de Kronos desde Power BI
- Definir acceso tecnico a workspace/dataset/dataflow de la empresa.
- Documentar linaje de datos (origen real de cada tabla depurada).
- Integrar extraccion reproducible al flujo analitico.
- Validar calidad de datos: cobertura, duplicados, nulos, consistencia temporal.
- Entregable:
  - Documento de linaje + script/proceso de extraccion validado.

### 2) Mejora del modelo de forecasting (prioridad alta)
- Implementar segmentacion por tipo/categoria con campeon por segmento.
- Ejecutar tuning de hiperparametros (RF/XGB/LGBM) por segmento.
- Incorporar exogenas de calendario (feriados) y evaluar impacto.
- Comparar A/B contra baseline actual.
- Entregables:
  - `benchmark` actualizado,
  - reporte de mejora por segmento,
  - decision de modelo final para produccion.

### 3) Integracion de recetas (BOM) para planificacion operativa
- Incorporar recetas de productos terminados (PT).
- Convertir pronostico de PT en requerimientos de produccion/componentes.
- Generar salida operativa por receta para abastecimiento y produccion.
- Entregables:
  - tabla Gold de requerimientos por receta,
  - validacion tecnica con casos de negocio.

### 4) Automatizacion productiva en Mage (MLOps basico)
- Definir pipeline de inferencia y publicacion automatica.
- Definir pipeline de reentrenamiento periodico (semanal/mensual).
- Programar scheduler, reintentos y alertas de fallo.
- Entregables:
  - pipelines documentados y calendarizados.

### 5) Gobierno de modelo y trazabilidad
- Crear registro de corridas (`logs.ml_runs`) con metricas, version y estado.
- Crear `model_registry` en Gold con modelo campeon vigente.
- Documentar criterio oficial de promocion de modelo.
- Entregables:
  - tablas de control + politica de promocion.

### 6) Endurecimiento de infraestructura (minimo profesional)
- Separar entorno dev/prod (DB o esquema).
- Gestionar secretos (variables de entorno / vault).
- Definir backup y recuperacion para PostgreSQL.
- Entregables:
  - checklist de infraestructura validado.

### 7) Dashboard final para defensa
- Consolidar vista ejecutiva enfocada en forecasting.
- Mostrar claramente:
  - produccion minima/recomendada/maxima,
  - productos estacionales,
  - productos inactivos,
  - fecha y version de corrida.
- Entregable:
  - version final de dashboard lista para demo.

### 8) Validacion funcional final (QA de extremo a extremo)
- Correr prueba completa:
  - ETL -> modelado -> publicacion -> dashboard.
- Verificar consistencia de conteos, periodos y metricas.
- Documentar incidencias y correcciones finales.
- Entregable:
  - acta de validacion E2E.

### 9) Cierre documental y presentacion final
- Alinear documento final con estado real del sistema.
- Actualizar metricas finales, figuras y tablas.
- Preparar presentacion de 5 minutos + banco de preguntas.
- Entregables:
  - tesis final corregida,
  - presentacion final cerrada.

## Criterios de "100% listo para entrega"
- Pipeline E2E automatizado y estable.
- Modelo final seleccionado con evidencia cuantitativa.
- Dashboard operativo coherente con Gold.
- Trazabilidad de datos y modelo documentada.
- Documento final y presentacion consistentes con la implementacion real.

## Cronograma sugerido Avance 3 (resumen)
- Semana 1: Power BI/Kronos + linaje + recetas (diseno).
- Semana 2: mejora de modelo (segmentacion + tuning + feriados).
- Semana 3: automatizacion Mage + tablas de control MLOps.
- Semana 4: QA E2E + cierre dashboard + cierre documental/presentacion.

## Riesgos y mitigacion
- Riesgo: acceso incompleto a fuente Power BI.
  - Mitigacion: plan alterno con export controlado + validacion de linaje.
- Riesgo: no mejora de metricas con exogenas.
  - Mitigacion: mantener modelo campeon actual y documentar A/B.
- Riesgo: cambios tardios en alcance.
  - Mitigacion: congelar alcance en forecasting para entrega final.
