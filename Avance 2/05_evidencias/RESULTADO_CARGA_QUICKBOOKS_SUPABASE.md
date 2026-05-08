# Resultado de carga QuickBooks local -> Supabase

Fecha de ejecucion: 2026-03-13

## Decision aplicada

Se ejecuto reemplazo de datos en tablas de QuickBooks con respaldo previo para mantener trazabilidad y rollback.

## Tablas respaldadas

- `quickbooks.sales_bkp_20260313_141452` (130)
- `quickbooks.sales_lineas_bkp_20260313_141452` (4872)
- `quickbooks.produccion_bkp_20260313_141452` (762)
- `quickbooks.produccion_lineas_bkp_20260313_141452` (5014)

## Tablas reemplazadas con data local

- `quickbooks.sales` => 8606
- `quickbooks.sales_lineas` => 156350
- `quickbooks.produccion` => 30645
- `quickbooks.produccion_lineas` => 30723

## Tablas no modificadas

- `quickbooks.compras` => 3410
- `quickbooks.compras_lineas` => 6953
- `quickbooks.items` => 8581

## Observacion de calidad

La nueva carga aumenta significativamente cobertura de ventas y produccion frente a la carga previa, manteniendo respaldo de la version anterior para auditoria.
