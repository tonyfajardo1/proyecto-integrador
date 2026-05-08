# Roadmap Futuro Final: Paso a Produccion de Forecasting

## Objetivo
Definir el plan futuro final para llevar el modelado de forecasting a una operacion de produccion estable, auditable y mantenible.

## Alcance funcional del flujo productivo
1) Ingesta/transformacion de datos.
2) Inferencia (prediccion).
3) Reentrenamiento (cuando toque).
4) Publicacion a Gold para dashboard.

## Arquitectura recomendada (caso actual)
- Orquestador: mantener Mage como orquestador principal.
- Capas de datos: sostener Bronze/Silver/Gold como contrato de datos.
- Modelo: artefacto versionado (`model.pkl` + `metadata.json`).
- Salida oficial de dashboard: `gold.pronostico_produccion_unificado_v1`.
- Dashboard: solo lectura de Gold (sin logica de modelo en frontend).

## Imprescindible (si o si)
- Separar entornos `dev` y `prod` (aunque sea por esquemas o DB distintos).
- Scheduler confiable para Mage (jobs diarios + reintentos + alertas).
- Gestion de secretos (sin credenciales en codigo; `.env` + vault/secret store).
- Monitoreo basico (exito/fallo, duracion, filas procesadas, ultima fecha de actualizacion).
- Backups y plan de recuperacion de PostgreSQL.

## Patron profesional de ejecucion
- Frecuencia de scoring (inferencia): diaria o al detectar data nueva.
- Frecuencia de retraining: semanal/mensual (no en cada carga).
- Publicacion: siempre idempotente y atomica (staging -> swap/replace).

## Flujo operativo objetivo
1. Correr `etl_bronze` y `etl_silver`.
2. Verificar calidad minima (conteos, nulos criticos, periodo nuevo).
3. Ejecutar inferencia con el modelo vigente.
4. Publicar a `gold.pronostico_produccion_resultado_v2` y tabla unificada.
5. Dashboard muestra automaticamente lo actualizado.
6. Monitoreo y alerta si falla algun paso.

## Mejores practicas clave
- Entornos separados: `dev` / `qa` / `prod` (DB o esquemas).
- Versionado de modelo: `model_version`, `train_period`, metricas.
- Data contracts: esquema fijo entre Silver y modelado.
- Validaciones automaticas antes y despues de publicar (row counts, tipos, fechas).
- Idempotencia: re-ejecutar no debe duplicar ni corromper.
- Observabilidad: logs, duracion, filas procesadas, razon de fallo.
- Rollback simple: conservar ultima version valida de tabla Gold.
- Seguridad: credenciales por `.env` o secret manager, nunca hardcode.
- CI/CD: pruebas y despliegue automatizado por cambios en codigo.

## Implementacion inmediata (practico)

### 1) Pipeline Mage `ml_inference_publish`
- Cargar features desde Silver.
- Cargar modelo campeon.
- Predecir y publicar en Gold unificada.
- Ejecutar checks y registrar log de ejecucion.

### 2) Pipeline Mage `ml_retrain`
- Ejecutar en frecuencia baja.
- Evaluar contra baseline.
- Promover nuevo modelo solo si mejora umbral definido.
- Guardar artefacto + metadata + version.

### 3) Tablas de control MLOps en Gold/Logs
- `logs.ml_runs`: `run_id`, `model_version`, metricas, estado, fechas.
- `gold.model_registry`: modelo campeon actual y fecha de promocion.

### 4) Trigger de actualizacion
- O por horario fijo (ejemplo: 6am diario).
- O por evento `data fresh` (cuando Silver detecte nuevo periodo).

## Criterio de exito para cierre de implementacion
- El dashboard se actualiza automaticamente tras ejecucion exitosa.
- Existe trazabilidad completa de cada corrida (datos + modelo + resultado).
- El sistema tolera reintentos y permite recuperacion por fallos.
- Las publicaciones Gold son consistentes e idempotentes.
