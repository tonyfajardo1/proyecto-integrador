# `src`

Esta carpeta agrupa utilidades Python compartidas por los bloques de Mage.

## Archivos principales

- `forecasting_v3_mage.py`: helpers para alinear entradas y salidas del
  forecasting dentro de Mage.
- `quickbooks_forecast/`: espejo del paquete de forecasting usado tambien en el
  standalone de modelado.

## Por que existe esta carpeta

La idea es evitar duplicar logica compleja dentro de los bloques de Mage.
Cuando una transformacion necesita reglas reutilizables, se extrae aqui para que
quede mas facil de probar y mantener.
