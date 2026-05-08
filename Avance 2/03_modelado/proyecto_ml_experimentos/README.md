# Proyecto de experimentacion ML (Avance 2)

Este proyecto organiza notebooks y scripts para comparar algoritmos en los 3 casos del dashboard:

1. Pronostico de produccion.
2. Reglas de asociacion.
3. Deteccion de anomalias.

Se inspiro en la estructura de `C:\Users\Tony\Documents\Data mining\proyecto-ml-end-to-end` y la adapta a tu flujo actual.

## Estructura

```text
proyecto_ml_experimentos/
  data/
    README.md
  models/
    README.md
  notebooks/
    exploration.ipynb
    experiments_forecasting.ipynb
    experiments_association.ipynb
    experiments_anomaly.ipynb
  scripts/
    run_benchmark_forecasting.py
    run_benchmark_association.py
    run_benchmark_anomaly.py
  src/
    __init__.py
    data_loaders.py
    evaluation.py
    forecasting.py
    association.py
    anomaly.py
```

## Baselines definidos

- Pronostico: baseline naive lag-1.
- Asociacion: baseline Apriori actual.
- Anomalias: baseline Isolation Forest actual.

## Protocolo profesional de comparacion

### Pronostico
- Split temporal estricto: `train` (60%) -> `validation` (20%) -> `test` (20%) por periodos.
- Seleccion de hiperparametros por `validation`.
- Evaluacion final en `test` con reentrenamiento `train+validation`.
- Metricas: `MAE`, `RMSE`, `WAPE`, y mejora vs baseline lag-1.

### Asociacion
- Split de transacciones `train/validation/test` (temporal por fecha cuando existe).
- Reglas descubiertas en `train`.
- Evaluacion en holdout:
  - confianza realizada en `validation` y `test`,
  - estabilidad de reglas (Jaccard train-vs-val y train-vs-test),
  - lift mediano y costo computacional.

### Anomalias
- Comparacion de modelos no supervisados:
  - `IsolationForest`, `LOF`, `OneClassSVM`.
- Criterios:
  - desviacion vs contamination objetivo,
  - estabilidad por bootstrap (Jaccard top anomalias),
  - score compuesto para ranking.

## Fuente de datos

Los notebooks y scripts estan configurados para extraer desde PostgreSQL:

- Pronostico: `quickbooks.produccion`.
- Asociacion: `silver.apriori_transacciones`.
- Anomalias: `gold.metricas_agencias`.

## Variables de conexion

Para DWH local (asociacion/anomalias):

- `DWH_HOST` (default: `localhost`)
- `DWH_PORT` (default: `5433`)
- `DWH_DB` (default: `condimensa_analytics`)
- `DWH_USER` (default: `condimensa`)
- `DWH_PASSWORD` (default: `REDACTED_LOCAL_DB_PASSWORD`)

Para QuickBooks (pronostico):

- `QUICKBOOKS_HOST`
- `QUICKBOOKS_PORT` (default: `6543`)
- `QUICKBOOKS_DB` (default: `postgres`)
- `QUICKBOOKS_USER`
- `QUICKBOOKS_PASSWORD`
- `QUICKBOOKS_SSLMODE` (default: `require`)

## Uso rapido

1. Configura variables de entorno.
2. Abre notebooks en `notebooks/` y ejecuta.
3. Cada notebook guarda dataset en `data/` y resultados en `models/`.
