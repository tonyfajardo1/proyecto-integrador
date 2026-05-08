# CONDIMENSA - Mage Avance 3

Proyecto limpio de orquestacion en Mage para la arquitectura medallion y los
modelos que realmente alimentan el dashboard final.

## Estructura activa

### Pipelines ETL

- `etl_bronze`
- `etl_silver`
- `etl_gold`

### Pipelines de modelos visibles en dashboard

- `dm_deteccion_anomalias`
- `dm_reglas_asociacion`
- `forecasting_v3_quickbooks`

## Fuentes operativas

### QuickBooks

Bronze trabaja con 4 fuentes reales:

- `public.raw_produccion`
- `quickbooks.sales`
- `public.raw_catalogo`
- `public.raw_ventas`

### Kronos

Bronze trabaja con 2 fuentes reales:

- `public.raw_kronos_ventas`
- `public.raw_kronos_rentabilidad`

En metadatos de ingesta la fuente se registra solo como `quickbooks` o
`kronos`.

## Dashboard activo

La app Streamlit solo expone 4 vistas:

- `Resumen Ejecutivo`
- `Cross-Selling (Apriori)`
- `Anomalias (Isolation Forest)`
- `Pronostico Produccion`

## Inicio rapido

1. Copia `.env.example` a `.env`.
2. Completa credenciales de QuickBooks y Kronos:
   - `*_HOST`: host del pooler de Supabase
   - `*_USER`: usuario del pooler, con formato `postgres.<project_ref>`
   - `*_PASSWORD`: password del proyecto
3. Levanta servicios:

```bash
docker-compose up -d
```

4. Accede a:
   - Mage: `http://localhost:6789`
   - Dashboard: `http://localhost:8501`
   - pgAdmin: `http://localhost:5050`

## Orden recomendado de ejecucion

1. `etl_bronze`
2. `etl_silver`
3. `etl_gold`
4. `dm_deteccion_anomalias`
5. `dm_reglas_asociacion`
6. `forecasting_v3_quickbooks`

## Nota de limpieza

Se removieron pipelines legacy, scripts de carga antiguos, vistas no activas del
dashboard y artefactos de ejecucion que Mage puede regenerar (`.logs`,
`.variables`, `__pycache__`, `.cache`).
