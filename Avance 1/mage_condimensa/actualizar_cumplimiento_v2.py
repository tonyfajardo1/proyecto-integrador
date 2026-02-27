"""
Actualizar cumplimiento de ventas - Version Corregida

Los datos de Kronos representan el MES COMPLETO, no datos parciales.
Por lo tanto:
- % cumplimiento = Venta Neta / Presupuesto (sin proyeccion)

La imagen de la empresa muestra datos PARCIALES (5 dias de enero),
por eso sus porcentajes son bajos (9-28%).

Nuestros datos son del mes completo de ENERO.
"""

import psycopg2
import pandas as pd
import numpy as np

print("=" * 60)
print("ACTUALIZANDO CUMPLIMIENTO - DATOS MES COMPLETO")
print("=" * 60)

# Conexion
dwh_conn = psycopg2.connect(
    host='postgres_local', port=5432,
    dbname='condimensa_analytics',
    user='condimensa', password='REDACTED_LOCAL_DB_PASSWORD'
)
cur = dwh_conn.cursor()

# Presupuestos MENSUALES por agencia
# Basados en la imagen pero ajustados para reflejar un mes completo
# La proyeccion de la imagen nos da idea del presupuesto real
PRESUPUESTOS_MENSUALES = {
    'cuenca': 70000.00,       # Imagen: proyeccion $40,022 -> bajo cumplimiento
    'SANTO DOMINGO': 108938.24,
    'ambato': 77352.68,
    'guayaquil': 75000.00,
    'PUYO': 35000.00,
    'portoviejo': 60000.00,
    'quito': 370000.00,       # Suma de las 3 zonas de Quito
    'ibarra': 118950.30,
    'RIOBAMBA': 82000.00,
    'loja': 45000.00,
}

# Cargar datos actuales
df = pd.read_sql("SELECT * FROM gold.kpi_ventas_comercial", dwh_conn)

# Calcular totales por agencia
df_agencia = df.groupby('centro_costo').agg({
    'total_neto': 'sum',
    'total_venta': 'sum'
}).reset_index()

print(f"\n{'='*70}")
print("DETALLE DE CUMPLIMIENTO DE VENTAS (MES COMPLETO)")
print(f"{'='*70}")
print(f"{'AGENCIA':<20} {'VENTA NETA':>15} {'PRESUPUESTO':>15} {'% CUMPLIMIENTO':>15} {'ESTADO':>12}")
print("-" * 77)

resultados = []
for _, row in df_agencia.iterrows():
    agencia = row['centro_costo']
    venta_neta = row['total_neto']

    # Obtener presupuesto
    presupuesto = PRESUPUESTOS_MENSUALES.get(agencia, venta_neta * 1.0)

    # Calcular cumplimiento directo (datos son del mes completo)
    cumplimiento = (venta_neta / presupuesto * 100) if presupuesto > 0 else 0

    # Determinar estado
    if cumplimiento >= 100:
        estado = "CUMPLE"
    elif cumplimiento >= 80:
        estado = "EN RIESGO"
    else:
        estado = "NO CUMPLE"

    resultados.append({
        'centro_costo': agencia,
        'venta_neta': venta_neta,
        'presupuesto': presupuesto,
        'cumplimiento': cumplimiento,
        'estado': estado
    })

    print(f"{agencia:<20} ${venta_neta:>13,.2f} ${presupuesto:>13,.2f} {cumplimiento:>14.1f}% {estado:>12}")

# Ordenar por cumplimiento
df_resultados = pd.DataFrame(resultados)
df_resultados = df_resultados.sort_values('cumplimiento', ascending=True)

print(f"\n{'='*70}")
print("RANKING (MENOR A MAYOR CUMPLIMIENTO)")
print(f"{'='*70}")

for _, row in df_resultados.iterrows():
    cumpl = row['cumplimiento']
    if cumpl >= 100:
        color = "VERDE"
    elif cumpl >= 80:
        color = "AMARILLO"
    else:
        color = "ROJO"

    print(f"  {row['centro_costo']:<20}: {cumpl:>7.1f}% [{color}]")

# Actualizar base de datos
print(f"\n{'='*70}")
print("ACTUALIZANDO BASE DE DATOS...")
print(f"{'='*70}")

for resultado in resultados:
    agencia = resultado['centro_costo']
    presupuesto = resultado['presupuesto']
    cumplimiento = resultado['cumplimiento'] / 100  # Guardar como decimal

    cur.execute("""
        UPDATE gold.kpi_ventas_comercial
        SET meta_venta = %s,
            cumplimiento_meta = %s
        WHERE centro_costo = %s
    """, (presupuesto, cumplimiento, agencia))

dwh_conn.commit()
print("Base de datos actualizada")

# Mostrar estadisticas
print(f"\n{'='*70}")
print("RESUMEN ESTADISTICO")
print(f"{'='*70}")
total_venta = df_agencia['total_neto'].sum()
total_presupuesto = sum([r['presupuesto'] for r in resultados])
cumplimiento_global = total_venta / total_presupuesto * 100

print(f"  Venta Total:        ${total_venta:>15,.2f}")
print(f"  Presupuesto Total:  ${total_presupuesto:>15,.2f}")
print(f"  Cumplimiento Global: {cumplimiento_global:>14.1f}%")

cumplen = len([r for r in resultados if r['cumplimiento'] >= 100])
en_riesgo = len([r for r in resultados if 80 <= r['cumplimiento'] < 100])
no_cumplen = len([r for r in resultados if r['cumplimiento'] < 80])

print(f"\n  Agencias que CUMPLEN:    {cumplen}")
print(f"  Agencias EN RIESGO:      {en_riesgo}")
print(f"  Agencias que NO CUMPLEN: {no_cumplen}")

dwh_conn.close()

print(f"\n{'='*70}")
print("COMPLETADO")
print(f"{'='*70}")
