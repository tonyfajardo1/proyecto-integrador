# CONDIMENSA - ETL, pipelines y dashboard

Esta carpeta contiene la implementacion aplicada del proyecto final en Mage AI
y Streamlit. Aqui se conecta el modelado con la parte operativa del sistema.

## Que contiene

- `condimensa_project/`: proyecto Mage con pipelines ETL y de analitica.
- `dashboard/`: aplicacion Streamlit para visualizacion y apoyo a decision.
- `docker-compose.yml`: servicios locales para levantar Mage, dashboard y
  herramientas auxiliares.
- `.env.example`: variables de entorno necesarias para configuracion local.

## Pipelines principales

### ETL

- `etl_bronze`
- `etl_silver`
- `etl_gold`

### Analitica

- `forecasting_v3_quickbooks`
- `dm_reglas_asociacion`
- `dm_deteccion_anomalias`

## Dashboard publicado en el proyecto

La app Streamlit expone las vistas que consumen la salida de los pipelines:

- `Resumen Ejecutivo`
- `Indicadores Comerciales QuickBooks`
- `Cross-Selling (Apriori)`
- `Anomalias (Isolation Forest)`
- `Pronostico Produccion`

## Estructura recomendada para navegar

1. Lee [condimensa_project/README.md](condimensa_project/README.md) para
   entender como Mage organiza bloques y pipelines.
2. Lee [dashboard/README.md](dashboard/README.md) para ver como se presenta la
   informacion al usuario final.
3. Si te interesa forecasting, sigue la ruta del pipeline
   `forecasting_v3_quickbooks`.

## Inicio rapido local

1. Copia `.env.example` a `.env`.
2. Completa credenciales y endpoints requeridos.
3. Levanta el entorno:

```bash
docker-compose up -d
```

4. Accede a:
   - Mage: `http://localhost:6789`
   - Dashboard: `http://localhost:8501`
   - pgAdmin: `http://localhost:5050`

## Nota

Esta carpeta fue limpiada para publicacion. Por eso no versiona artefactos
temporales, caches ni configuraciones privadas del entorno local.
