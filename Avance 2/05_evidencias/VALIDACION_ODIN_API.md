# Validacion tecnica ODIN API (QuickBooks)

## Objetivo

Verificar que QuickBooks pueda extraerse desde ODIN API (sin depender de Supabase para QuickBooks).

## Referencia revisada

- Documento: `Avance 1/ODIN_WS_V2_1.pdf`
- Regla de token: `SHA1(publicKey + fecha_utc_minuto + function_name + privateKey)`

## Verificacion de configuracion local

- Archivo `.env` presente en `Avance 2/mage_condimensa`.
- Variables requeridas detectadas:
  - `ODIN_BASE_URL`
  - `ODIN_PUBLIC_KEY`
  - `ODIN_PRIVATE_KEY`
  - `ODIN_ESTADO`

## Pruebas ejecutadas

1. **Endpoint `sales`**
   - Request: `sales?estado=PENDIENTE&from=0&skip=2`
   - Resultado: `status=OK`, total reportado `650`.

2. **Endpoint `produccion`**
   - Request: `produccion?estado=PENDIENTE&from=0&skip=2`
   - Resultado: `status=OK`, total reportado `1534`.

3. **Validez de token para lineas**
   - `lines` con `function_name=SaleLines`: aceptado (`status=OK`).
   - `lines` con `function_name=SalesLines`: rechazado (`Token no valido`).

## Conclusion

La extraccion de QuickBooks desde ODIN API **si es viable** y ya responde correctamente para cabeceras de `sales` y `produccion`.

## Nota operativa importante

En pruebas de lineas (`lines`, `produccionlines`) se obtuvo `message=0` para muestras consultadas. Esto no invalida la API de cabecera, pero requiere validar con negocio:

- estado correcto de documentos a consultar,
- filtros (`date`, `nick`, `estado`),
- o disponibilidad real de lineas en ODIN para esos `idsale`.

## Estado de migracion QuickBooks

- En `Avance 2`, el loader `extraer_datos_bronze.py` ya consume QuickBooks por ODIN API:
  - `load_quickbooks_sales_from_odin`
  - `load_quickbooks_produccion_from_odin`
