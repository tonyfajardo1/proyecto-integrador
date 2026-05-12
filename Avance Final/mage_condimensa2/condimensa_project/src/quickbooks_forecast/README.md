# Paquete `quickbooks_forecast` dentro de Mage

Esta carpeta replica la logica central del forecasting usada en
`Modelado/forecasting_v3`, pero empaquetada dentro del proyecto Mage para que
los bloques puedan reutilizarla sin depender de notebooks.

## Modulos

- `datasets.py`
- `features.py`
- `modeling.py`
- `decision.py`
- `inventory.py`
- `operational_evaluation.py`

## Relacion con el standalone

El objetivo es que Mage y el proyecto de modelado compartan la misma logica
metodologica. Asi, la version operativa del pipeline no se separa de la version
validada academicamente.
