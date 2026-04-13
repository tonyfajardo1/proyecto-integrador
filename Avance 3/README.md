# Avance 3 - Proyecto Integrador CONDIMENSA

Repositorio del Avance 3 para el proyecto analitico de CONDIMENSA. Incluye pipelines ETL/ELT en Mage, dashboard Streamlit, modelado de forecasting V3 para QuickBooks y evidencias/presentacion del avance.

## Estructura principal

- `mage_condimensa2/`: entorno Mage, dashboard Streamlit y pipelines medallion.
- `Modelado/forecasting_v3/`: experimentacion local del modelo de forecasting QuickBooks.
- `Modelado/forecasting_tesis_v2/`: version previa de modelado usada como referencia.
- `Evidencias/`: capturas y materiales de soporte.
- `Presentacion/`: material de exposicion.

## Configuracion local

Los archivos con credenciales reales no se versionan. Para configurar el proyecto localmente, usar los ejemplos:

- `mage_condimensa2/.env.example`
- `mage_condimensa2/condimensa_project/io_config.example.yaml`
- `mage_condimensa2/pgadmin_servers.example.json`

Crear las copias locales correspondientes (`.env`, `io_config.yaml`, `pgadmin_servers.json`) y completar las claves en el equipo de ejecucion.

## Archivos no versionados

Por seguridad y tamano, quedan fuera del repositorio:

- Credenciales y configuraciones reales.
- Bases locales de Mage.
- Logs, cache y variables de ejecucion de Mage.
- Datos crudos/generados de QuickBooks.
- Modelos entrenados y artefactos binarios.

Los modelos, reportes y datasets procesados se regeneran ejecutando los notebooks o pipelines correspondientes.
