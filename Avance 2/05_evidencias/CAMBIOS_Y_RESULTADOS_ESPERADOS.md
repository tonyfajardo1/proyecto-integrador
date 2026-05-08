# Cambios aplicados y resultados esperados (Avance 2)

Fecha: 2026-03-13

## 1) Cambios principales aplicados

### Arquitectura y configuracion
- Se aislo `Avance 2` de `Avance 1` en Docker con puertos y nombres propios:
  - Mage: `6790`
  - Dashboard: `8502`
  - Postgres local: `5434`
  - pgAdmin: `5051`
- Se parametrizo conexion en `io_config.yaml` para QuickBooks y Kronos via variables de entorno.

### Data Mining y pipelines
- Se reemplazo el pipeline de "desviaciones" por **pronostico mensual de produccion por producto**:
  - Loader: `data_loaders/dm/preparar_datos_desviaciones.py`
  - Transformer: `transformers/dm/analizar_causas_desviaciones.py`
  - Exporter: `data_exporters/dm/exportar_causas_desviaciones.py`
- Se ajusto reglas de asociacion para consumir `silver.kronos_ventas` (sin dependencia a `dm.cestas_transacciones`).
- Se ajusto loader de anomalias a columnas reales de `gold.metricas_agencias`.

### Idempotencia y calidad
- Exportadores DM de reglas y anomalias pasaron de `replace` a `delete + append` por `pipeline_id`.
- Se agrego depuracion basica de nulos en loaders clave.

### Dashboard
- Se actualizo navegacion a 3 vistas objetivo:
  1. `Pronostico Produccion`
  2. `Cross-Selling (Apriori)`
  3. `Anomalias (Isolation Forest)`
- Se actualizaron queries en `dashboard/database.py` para consumir tablas gold actuales.

## 2) Tablas gold esperadas para las vistas

### Vista 1 - Pronostico mensual
- `gold.pronostico_produccion_resultado`
- `gold.metricas_pronostico_produccion`
- `gold.importancia_features_pronostico`

### Vista 2 - Reglas de asociacion
- `gold.reglas_asociacion`

### Vista 3 - Anomalias
- `gold.anomalias_agencias`

## 3) Que deberia mostrar cada vista (ejemplo)

### Vista 1: Pronostico mensual de produccion por producto
- **KPIs**
  - Productos con pronostico: `120`
  - Cantidad recomendada total: `45,800`
  - Promedio pronosticado: `381.7`
  - Confianza alta: `62.5%`
- **Grafico principal**: Top productos por `qty_recomendada`.
- **Grafico secundario**: `qty_planificada` vs `pronostico_qty` por nivel de confianza.
- **Tabla detalle**: producto, periodo, periodo_prediccion, qty_fabricada, qty_planificada, pronostico_qty, qty_recomendada, nivel_confianza.

### Vista 2: Cross-Selling (Apriori)
- **KPIs**
  - Total reglas: `35`
  - Lift maximo: `3.10`
  - Confianza promedio: `58%`
- **Contenido**
  - Top reglas por lift
  - Grafico lift por regla
  - Scatter confianza vs lift
  - Recomendaciones de combos

### Vista 3: Anomalias (Isolation Forest)
- **KPIs**
  - Agencias analizadas: `24`
  - Anomalias detectadas: `3`
  - Devolucion promedio: `8.7%`
- **Contenido**
  - Ranking de agencias anomalas
  - Barras de tasa de devolucion por agencia
  - Mapa devolucion vs rentabilidad
  - Interpretacion y accion sugerida

## 4) Estado de Mage (diagnostico)

Validacion tecnica local:
- `GET http://localhost:6790` -> `200 OK` (HTML de Mage)
- `GET http://localhost:6790/api/status` -> `200 OK`

Esto confirma que el backend de Mage esta arriba.

## 5) Si la pantalla de Mage sigue en negro

1. Abrir en incognito: `http://127.0.0.1:6790`
2. Limpiar cache duro (`Ctrl+F5`) y cerrar pestañas previas de Mage.
3. Reiniciar solo el contenedor de Mage:
   - `docker restart mage_condimensa_a2`
4. Ver logs en vivo:
   - `docker logs -f mage_condimensa_a2`
5. Si persiste, resetear metadata local de Mage (solo UI/estado, no codigo):
   - detener contenedor,
   - respaldar y eliminar `condimensa_project/mage-ai.db`,
   - volver a levantar.

Nota: el warning de triggers antiguos (`trigger_type`) aparece en logs, pero no impide que el servidor responda.
