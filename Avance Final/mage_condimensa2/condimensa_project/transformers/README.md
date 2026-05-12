# `transformers`

Aqui vive la logica principal del proyecto Mage. Cada archivo corresponde a un
bloque que transforma datos ya cargados por los `data_loaders`.

## Responsabilidades

- crear tablas destino en Bronze, Silver y Gold;
- transformar datos curados;
- entrenar y predecir forecasting;
- ejecutar algoritmos de mineria de datos;
- calcular KPIs para consumo del dashboard.

## Archivos clave

- `crear_tablas_bronze.py`
- `crear_tablas_silver.py`
- `crear_tablas_gold.py`
- `transformar_datos_silver.py`
- `calcular_kpis_gold.py`
- `generar_reglas_apriori.py`
- `detectar_anomalias_isolation_forest.py`
- `entrenar_forecasting_v3.py`
- `predecir_forecasting_v3.py`
- `crear_tablas_forecasting_v3_gold.py`

## Punto de lectura recomendado

Si el objetivo es entender el aporte analitico del proyecto, los tres bloques
mas importantes son:

1. `transformar_datos_silver.py`
2. `entrenar_forecasting_v3.py`
3. `predecir_forecasting_v3.py`
