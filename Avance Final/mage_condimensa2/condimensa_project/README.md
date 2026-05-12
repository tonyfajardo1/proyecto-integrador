# Proyecto Mage `condimensa_project`

Esta es la implementacion del proyecto dentro de Mage AI. Organiza la carga,
transformacion y publicacion de datos en bloques reutilizables.

## Estructura

- `data_loaders/`: extraen datos desde Bronze, Silver u otras fuentes.
- `transformers/`: aplican la logica principal de transformacion o modelado.
- `data_exporters/`: escriben resultados a Bronze, Silver o Gold.
- `pipelines/`: definen el orden de ejecucion de los bloques.
- `src/`: utilidades Python compartidas por varios bloques.
- `tests/`: pruebas tecnicas del proyecto Mage.

## Pipelines versionados

- `etl_bronze`
- `etl_silver`
- `etl_gold`
- `dm_reglas_asociacion`
- `dm_deteccion_anomalias`
- `forecasting_v3_quickbooks`

## Como leer esta carpeta

1. entra a [pipelines/README.md](pipelines/README.md) para ubicar el flujo;
2. revisa `data_loaders`, `transformers` y `data_exporters` para entender cada
   etapa;
3. revisa `src/forecasting_v3_mage.py` si te interesa la alineacion entre Mage
   y el modelado standalone.

## Nota

En la version publica se excluyen caches, bases locales, credenciales y
artefactos temporales que Mage puede regenerar.
