# Plan recomendado de carga a Supabase (calidad de datos)

## Recomendacion

No borrar tablas productivas existentes de QuickBooks de forma directa.

Para maximizar calidad y trazabilidad:

1. Cargar primero a tablas `*_local_stg`.
2. Validar conteos, fechas y nulos.
3. Insertar incremental a tablas `*_local` con deduplicacion por claves naturales.
4. Mantener ODIN y Local en tablas separadas para comparacion de cobertura.

## Por que esta estrategia es mejor

- Evita perdida de informacion historica.
- Permite auditoria y rollback.
- Se puede demostrar calidad y cobertura al profesor.
- Facilita reconciliacion ODIN vs export local.

## Script listo

`Avance 2/mage_condimensa/cargar_quickbooks_local_a_supabase.py`

## Variables necesarias para ejecutar

- `QUICKBOOKS_HOST`
- `QUICKBOOKS_PORT`
- `QUICKBOOKS_DB`
- `QUICKBOOKS_USER`
- `QUICKBOOKS_PASSWORD`
- `QUICKBOOKS_SCHEMA`

## Comando de ejecucion

```bash
python "Avance 2/mage_condimensa/cargar_quickbooks_local_a_supabase.py" --mode safe
```

## Bloqueo actual detectado

Las credenciales/host actuales del pooler en `io_config.yaml` no permiten conexion (error `Tenant or user not found`).
Se requiere actualizar host/usuario de Supabase para ejecutar la carga.
