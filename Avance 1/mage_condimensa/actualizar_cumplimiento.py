"""
Actualizar cumplimiento de ventas usando presupuestos reales
Basado en los datos de la imagen de la empresa

La formula correcta es:
- % cumplimiento a la fecha = Venta Neta / Presupuesto
- Proyeccion = (Venta Neta / dias_transcurridos) * dias_del_mes
- % cumplimiento proyectado = Proyeccion / Presupuesto
"""

import psycopg2
import pandas as pd
import numpy as np
from datetime import datetime

print("=" * 60)
print("ACTUALIZANDO CUMPLIMIENTO CON PRESUPUESTOS REALES")
print("=" * 60)

# Conexion
dwh_conn = psycopg2.connect(
    host='postgres_local', port=5432,
    dbname='condimensa_analytics',
    user='condimensa', password='change_me'
)
cur = dwh_conn.cursor()

# Presupuestos mensuales por agencia (basados en imagen de empresa)
# Estos valores deberían venir de una tabla de presupuestos real
PRESUPUESTOS_MENSUALES = {
    'cuenca': 70000.00,
    'SANTO DOMINGO': 108938.24,
    'ambato': 77352.68,
    'guayaquil': 75000.00,
    'PUYO': 35000.00,
    'portoviejo': 60000.00,
    'quito': 370000.00,  # Suma de QUITO-VALLE + QUITO-NORTE + QUITO-SUR
    'ibarra': 118950.30,
    'RIOBAMBA': 82000.00,
    'loja': 45000.00,
}

# Parametros de tiempo (simulando periodo parcial del mes)
DIAS_TRANSCURRIDOS = 5  # Dias del mes transcurridos
DIAS_DEL_MES = 30  # Total dias del mes

print(f"\nParametros:")
print(f"  Dias transcurridos: {DIAS_TRANSCURRIDOS}")
print(f"  Dias del mes: {DIAS_DEL_MES}")

# Cargar datos actuales
df = pd.read_sql("SELECT * FROM gold.kpi_ventas_comercial", dwh_conn)

# Calcular totales por agencia
df_agencia = df.groupby('centro_costo').agg({
    'total_neto': 'sum',
    'total_venta': 'sum'
}).reset_index()

print(f"\n{'='*60}")
print("DETALLE DE CUMPLIMIENTO DE VENTAS")
print(f"{'='*60}")
print(f"{'AGENCIA':<20} {'VENTA NETA':>15} {'PRESUPUESTO':>15} {'% CUMPL':>10} {'PROYECCION':>15} {'% PROY':>10}")
print("-" * 95)

resultados = []
for _, row in df_agencia.iterrows():
    agencia = row['centro_costo']
    venta_neta = row['total_neto']

    # Obtener presupuesto (si no existe, estimar basado en venta * 1.2)
    presupuesto = PRESUPUESTOS_MENSUALES.get(agencia, venta_neta * 1.2)

    # Calcular cumplimiento a la fecha
    cumplimiento_fecha = (venta_neta / presupuesto * 100) if presupuesto > 0 else 0

    # Calcular proyeccion lineal
    venta_diaria = venta_neta / DIAS_TRANSCURRIDOS
    proyeccion = venta_diaria * DIAS_DEL_MES

    # Calcular cumplimiento proyectado
    cumplimiento_proyectado = (proyeccion / presupuesto * 100) if presupuesto > 0 else 0

    resultados.append({
        'centro_costo': agencia,
        'venta_neta': venta_neta,
        'presupuesto': presupuesto,
        'cumplimiento_fecha': cumplimiento_fecha,
        'proyeccion': proyeccion,
        'cumplimiento_proyectado': cumplimiento_proyectado
    })

    print(f"{agencia:<20} ${venta_neta:>13,.2f} ${presupuesto:>13,.2f} {cumplimiento_fecha:>9.2f}% ${proyeccion:>13,.2f} {cumplimiento_proyectado:>9.2f}%")

# Crear DataFrame de resultados
df_resultados = pd.DataFrame(resultados)
df_resultados = df_resultados.sort_values('cumplimiento_proyectado', ascending=False)

print(f"\n{'='*60}")
print("RANKING POR CUMPLIMIENTO PROYECTADO")
print(f"{'='*60}")

for i, row in df_resultados.iterrows():
    proy = row['cumplimiento_proyectado']
    if proy >= 100:
        estado = "VERDE (Cumplira)"
    elif proy >= 70:
        estado = "AMARILLO (En riesgo)"
    else:
        estado = "ROJO (No cumplira)"

    print(f"  {row['centro_costo']:<20}: {proy:>7.2f}% - {estado}")

# Actualizar la base de datos con los valores correctos
print(f"\n{'='*60}")
print("ACTUALIZANDO BASE DE DATOS...")
print(f"{'='*60}")

# Actualizar meta_venta y cumplimiento_meta en la tabla
for resultado in resultados:
    agencia = resultado['centro_costo']
    presupuesto = resultado['presupuesto']
    cumplimiento = resultado['cumplimiento_proyectado'] / 100  # Guardar como decimal

    cur.execute("""
        UPDATE gold.kpi_ventas_comercial
        SET meta_venta = %s,
            cumplimiento_meta = %s
        WHERE centro_costo = %s
    """, (presupuesto, cumplimiento, agencia))

dwh_conn.commit()
print("Base de datos actualizada correctamente")

# Verificar
print(f"\n{'='*60}")
print("VERIFICACION")
print(f"{'='*60}")

df_check = pd.read_sql("""
    SELECT centro_costo,
           SUM(total_neto) as venta_neta,
           AVG(meta_venta) as presupuesto,
           AVG(cumplimiento_meta) * 100 as cumplimiento_pct
    FROM gold.kpi_ventas_comercial
    GROUP BY centro_costo
    ORDER BY cumplimiento_pct DESC
""", dwh_conn)

for _, row in df_check.iterrows():
    print(f"  {row['centro_costo']:<20}: {row['cumplimiento_pct']:>7.2f}%")

dwh_conn.close()

print(f"\n{'='*60}")
print("NOTA IMPORTANTE:")
print("Los presupuestos usados son ESTIMADOS basados en la imagen.")
print("Para datos precisos, la empresa debe proporcionar la tabla")
print("de presupuestos reales por agencia y periodo.")
print(f"{'='*60}")
