# `pipelines`

Cada subcarpeta de este directorio representa un pipeline de Mage AI con su
metadata de bloques y orden de ejecucion.

## Pipelines incluidos

### ETL

- `etl_bronze`: carga inicial hacia la capa Bronze.
- `etl_silver`: limpieza y homologacion hacia Silver.
- `etl_gold`: KPIs y tablas finales de consumo.

### Analitica

- `dm_reglas_asociacion`: cross-selling con Apriori.
- `dm_deteccion_anomalias`: deteccion de comportamiento atipico con Isolation
  Forest.
- `forecasting_v3_quickbooks`: entrenamiento, prediccion y publicacion del
  forecasting final.

## Como leerlos

Si eres nuevo en Mage, abre primero `metadata.yaml` dentro del pipeline que te
interesa. Desde ahi puedes seguir la secuencia:

1. `data_loader`
2. `transformer`
3. `data_exporter`

Ese orden refleja bastante bien la arquitectura operativa del proyecto.
