# Paquete `quickbooks_forecast`

Este paquete concentra la logica reutilizable del forecasting final. Es la
parte mas importante para entender como se construyen datasets, features,
entrenamiento y predicciones.

## Modulos

- `cleaning.py`: normalizacion de textos, fechas y codigos.
- `config.py`: carga de configuracion y resolucion de rutas.
- `datasets.py`: construccion de datasets PT y PP.
- `exogenous.py`: plantillas y merge de variables exogenas.
- `features.py`: feature engineering temporal y perfiles historicos.
- `modeling.py`: seleccion de modelos, CV temporal, walk-forward, SHAP y
  prediccion.
- `inventory.py`: ajustes de inventario sobre la salida del forecast.
- `decision.py`: campos de negocio y reglas de apoyo a decision.
- `operational_evaluation.py`: benchmark humano y evaluacion operativa.

## Orden logico de lectura

1. `config.py`
2. `datasets.py`
3. `features.py`
4. `modeling.py`
5. `decision.py` e `inventory.py`
6. `operational_evaluation.py`

## Idea metodologica

El paquete separa claramente tres responsabilidades:

- preparacion de datos;
- entrenamiento y validacion;
- transformacion de predicciones en recomendaciones operativas.

Esto ayuda a mantener trazabilidad y a reusar la misma logica tanto en el
standalone de modelado como en el pipeline de Mage.
