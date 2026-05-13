"""
Calcular Presupuesto basado en factores de negocio

Según la empresa, el presupuesto depende de:
1. Número de vendedores por agencia
2. Número de clientes por zona
3. Sector donde se encuentran

Como no tenemos estos datos directamente, usamos proxies:
- CANTIDAD de items vendidos -> indica tamaño de operación
- Esto correlaciona con número de vendedores y clientes

Formula propuesta:
  PRESUPUESTO = (CANTIDAD_ITEMS / FACTOR_PRODUCTIVIDAD) * PRECIO_PROMEDIO * FACTOR_ZONA

Donde:
  - FACTOR_PRODUCTIVIDAD: items que un vendedor vende por mes (estimado)
  - PRECIO_PROMEDIO: precio promedio por item
  - FACTOR_ZONA: ajuste por dificultad del mercado (costa, sierra, oriente)
"""

import psycopg2
import pandas as pd
import numpy as np

print("=" * 70)
print("CALCULO DE PRESUPUESTO BASADO EN FACTORES DE NEGOCIO")
print("=" * 70)

# Conexiones
kronos = psycopg2.connect(
    host='your-kronos-host.supabase.com',
    port=6543, dbname='postgres',
    user='postgres.your-kronos-project-ref',
    password='change_me'
)

dwh = psycopg2.connect(
    host='postgres_local', port=5432,
    dbname='condimensa_analytics',
    user='condimensa', password='change_me'
)
cur = dwh.cursor()

# Cargar datos de Kronos
df = pd.read_sql("SELECT * FROM kronos.ventas_general", kronos)
df = df.iloc[7:].reset_index(drop=True)
df.columns = ['centro_costo', 'cant', 'total', 'cant_nc', 'total_nc',
              'cant_dev', 'total_dev', 'cant_neto', 'total_neto',
              'costo_venta', 'rentabilidad', 'prc', 'mes']

for col in ['cant', 'total', 'cant_neto', 'total_neto', 'total_dev']:
    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

# Agrupar por agencia
df_agencia = df.groupby('centro_costo').agg({
    'cant': 'sum',
    'total': 'sum',
    'total_neto': 'sum',
    'total_dev': 'sum'
}).reset_index()

# Calcular precio promedio por item
df_agencia['precio_promedio'] = df_agencia['total'] / df_agencia['cant']

# Factor de zona (basado en sector geográfico y dificultad del mercado)
# Costa: más competencia, mercado más difícil -> factor más alto (presupuesto más exigente)
# Sierra: mercado estable -> factor medio
# Oriente: mercado más pequeño pero menos competencia -> factor más bajo
FACTORES_ZONA = {
    'quito': 1.05,         # Sierra - Capital, muy competitivo
    'guayaquil': 1.15,     # Costa - Puerto principal, muy competitivo
    'cuenca': 0.95,        # Sierra - Mercado establecido
    'ambato': 0.90,        # Sierra - Mercado medio
    'ibarra': 0.85,        # Sierra norte - Menos competencia
    'loja': 0.80,          # Sierra sur - Mercado pequeño
    'portoviejo': 1.00,    # Costa - Mercado medio
    'RIOBAMBA': 0.85,      # Sierra central
    'SANTO DOMINGO': 1.00, # Costa/Sierra - Zona comercial
    'PUYO': 0.75,          # Oriente - Mercado pequeño
}

# Factor de productividad esperada (ajuste para hacer presupuestos realistas)
# Este factor determina qué tan exigente es el presupuesto
FACTOR_EXIGENCIA = 0.85  # 85% de las ventas actuales como meta base

print("\n" + "=" * 70)
print("ANALISIS DE FACTORES POR AGENCIA")
print("=" * 70)
print(f"{'AGENCIA':<15} {'ITEMS':>10} {'VENTA NETA':>15} {'PRECIO PROM':>12} {'FACTOR ZONA':>12}")
print("-" * 64)

resultados = []
for _, row in df_agencia.iterrows():
    agencia = row['centro_costo']
    items = row['cant']
    venta_neta = row['total_neto']
    precio_prom = row['precio_promedio']
    factor_zona = FACTORES_ZONA.get(agencia, 1.0)

    # Calcular presupuesto
    # Presupuesto = Venta histórica * Factor de exigencia / Factor de zona
    # Si factor_zona es alto (mercado difícil), el presupuesto es menor (más realista)
    # Si factor_zona es bajo (mercado fácil), el presupuesto es mayor (más exigente)
    presupuesto = (venta_neta / FACTOR_EXIGENCIA) * factor_zona

    # Calcular cumplimiento
    cumplimiento = (venta_neta / presupuesto * 100) if presupuesto > 0 else 0

    # Simular variación (en la realidad, las ventas varían mes a mes)
    # Agregamos una variación basada en la tasa de devolución como indicador de problemas
    tasa_devolucion = (row['total_dev'] / row['total'] * 100) if row['total'] > 0 else 0

    # Ajustar presupuesto según performance histórico
    # Agencias con alta devolución tienen mercados más difíciles -> presupuesto ajustado
    if tasa_devolucion > 5:
        presupuesto = presupuesto * (1 + tasa_devolucion/100)

    cumplimiento = (venta_neta / presupuesto * 100) if presupuesto > 0 else 0

    resultados.append({
        'centro_costo': agencia,
        'items': items,
        'venta_neta': venta_neta,
        'precio_promedio': precio_prom,
        'factor_zona': factor_zona,
        'presupuesto': presupuesto,
        'cumplimiento': cumplimiento,
        'tasa_devolucion': tasa_devolucion
    })

    print(f"{agencia:<15} {items:>10,.0f} ${venta_neta:>13,.2f} ${precio_prom:>10,.2f} {factor_zona:>12.2f}")

kronos.close()

# Ordenar por cumplimiento
df_resultados = pd.DataFrame(resultados)
df_resultados = df_resultados.sort_values('cumplimiento', ascending=True)

print("\n" + "=" * 70)
print("PRESUPUESTOS CALCULADOS Y CUMPLIMIENTO")
print("=" * 70)
print(f"{'AGENCIA':<15} {'VENTA NETA':>15} {'PRESUPUESTO':>15} {'CUMPL %':>10} {'ESTADO':>12}")
print("-" * 67)

for _, row in df_resultados.iterrows():
    cumpl = row['cumplimiento']
    if cumpl >= 100:
        estado = "VERDE"
    elif cumpl >= 85:
        estado = "AMARILLO"
    else:
        estado = "ROJO"

    print(f"{row['centro_costo']:<15} ${row['venta_neta']:>13,.2f} ${row['presupuesto']:>13,.2f} {cumpl:>9.1f}% {estado:>12}")

# Actualizar base de datos
print("\n" + "=" * 70)
print("ACTUALIZANDO BASE DE DATOS...")
print("=" * 70)

for resultado in resultados:
    agencia = resultado['centro_costo']
    presupuesto = resultado['presupuesto']
    cumplimiento = resultado['cumplimiento'] / 100

    cur.execute("""
        UPDATE gold.kpi_ventas_comercial
        SET meta_venta = %s,
            cumplimiento_meta = %s
        WHERE centro_costo = %s
    """, (presupuesto, cumplimiento, agencia))

dwh.commit()

# Resumen
print("\nRESUMEN:")
total_venta = df_resultados['venta_neta'].sum()
total_presup = df_resultados['presupuesto'].sum()
cumpl_global = total_venta / total_presup * 100

verdes = len(df_resultados[df_resultados['cumplimiento'] >= 100])
amarillos = len(df_resultados[(df_resultados['cumplimiento'] >= 85) & (df_resultados['cumplimiento'] < 100)])
rojos = len(df_resultados[df_resultados['cumplimiento'] < 85])

print(f"  Cumplimiento Global: {cumpl_global:.1f}%")
print(f"  Agencias VERDE (>=100%):   {verdes}")
print(f"  Agencias AMARILLO (85-99%): {amarillos}")
print(f"  Agencias ROJO (<85%):       {rojos}")

dwh.close()

print("\n" + "=" * 70)
print("COMPLETADO - Presupuestos calculados con formula de negocio")
print("=" * 70)
