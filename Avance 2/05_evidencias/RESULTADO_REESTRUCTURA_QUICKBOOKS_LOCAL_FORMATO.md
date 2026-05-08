# Resultado: reestructura QuickBooks al formato local

Se reemplazo el modelo de tablas `quickbooks` para que refleje el formato real de los archivos locales (sin columnas heredadas de ODIN).

## Tablas eliminadas/reemplazadas

- `quickbooks.sales`
- `quickbooks.sales_lineas`
- `quickbooks.produccion`
- `quickbooks.produccion_lineas`
- `quickbooks.costos` (recreada)

## Backups previos conservados

- `quickbooks.sales_compat_backup`
- `quickbooks.sales_lineas_compat_backup`
- `quickbooks.produccion_compat_backup`
- `quickbooks.produccion_lineas_compat_backup`

## Estructura final cargada

### `quickbooks.sales`
- id, asesor, tipo_documento, fecha, numero, memo, cliente, item, qty, uom, sales_price, amount
- Registros: **156350**

### `quickbooks.produccion`
- id, id_registro, fecha, numero, lote, producto, qty_planificada, qty_liberada, qty_fabricada
- Registros: **30724**

### `quickbooks.costos`
- id, tipo_documento, fecha, cliente, numero, item, item_descripcion, qty, cost, on_hand, uom
- Registros: **281814**

## Nota tecnica

Esta reestructura mejora fidelidad de datos con la fuente local, pero cambia contratos de columnas respecto al modelo ODIN anterior.
