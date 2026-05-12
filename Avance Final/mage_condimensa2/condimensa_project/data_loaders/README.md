# `data_loaders`

Los bloques de esta carpeta se encargan de leer datos de entrada para los
pipelines de Mage.

## Roles principales

- extraer tablas crudas desde Bronze;
- leer tablas curadas desde Silver;
- preparar datasets de entrada para Apriori, anomalias o forecasting.

## Archivos clave

- `extraer_datos_bronze.py`: entrada base del pipeline `etl_bronze`.
- `extraer_desde_bronze.py`: lectura de tablas Bronze para transformaciones
  posteriores.
- `extraer_desde_silver.py`: lectura de tablas Silver para `etl_gold`.
- `extraer_forecasting_v3_silver.py`: carga datasets Silver requeridos por el
  forecasting final.
- `preparar_datos_anomalias.py`: construye el dataset de entrada para
  Isolation Forest.
- `preparar_datos_asociacion.py`: construye las transacciones usadas por
  Apriori.

## Lectura recomendada

Primero identifica el pipeline en `pipelines/`, luego entra aqui para ver que
dataset recibe cada bloque transformador.
