# `data_exporters`

Los bloques de esta carpeta publican los resultados de cada pipeline hacia las
tablas de destino.

## Responsabilidades

- escribir tablas Bronze, Silver y Gold;
- publicar resultados de mineria de datos;
- publicar predicciones finales del forecasting.

## Archivos clave

- `cargar_bronze.py`
- `cargar_silver.py`
- `cargar_gold.py`
- `exportar_reglas_dwh.py`
- `exportar_anomalias_dwh.py`
- `cargar_forecasting_v3_gold.py`

## Como encajan en el flujo

En Mage, estos bloques suelen ser el ultimo paso de cada pipeline: toman la
salida de los `transformers` y la convierten en tablas consumibles por dashboard
u otros procesos.
