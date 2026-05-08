import pandas as pd
import numpy as np
import random
import psycopg2
from psycopg2.extras import execute_values

DB_CONFIG = {
    'host': 'localhost',
    'port': 5433,
    'database': 'condimensa_analytics',
    'user': 'condimensa',
    'password': 'REDACTED_LOCAL_DB_PASSWORD'
}

print('=== Generando datos con vida util corregida ===')

productos = [
    {'codigo': '4716', 'nombre': 'AJO PAST DOYPACK 200', 'dias_vida_util': 300, 'precio': 2.50},
    {'codigo': '8059', 'nombre': 'SAZONADOR CERDO 1 KL', 'dias_vida_util': 365, 'precio': 8.50},
    {'codigo': '6191', 'nombre': 'MAYONESA DISPLAY X 12', 'dias_vida_util': 240, 'precio': 8.50},
    {'codigo': '0398', 'nombre': 'COMINO MOLIDO 200G', 'dias_vida_util': 365, 'precio': 4.50},
    {'codigo': 'SAL01', 'nombre': 'SALSA TOMATE 300G', 'dias_vida_util': 365, 'precio': 2.50},
    {'codigo': '7328', 'nombre': 'SAZONADOR POLLO 70G', 'dias_vida_util': 365, 'precio': 1.80},
    {'codigo': '9858', 'nombre': 'OREGANO 20G', 'dias_vida_util': 365, 'precio': 1.50},
    {'codigo': '1837', 'nombre': 'AJO PAST 400G', 'dias_vida_util': 300, 'precio': 4.20},
]
agencias = ['quito', 'guayaquil', 'cuenca', 'ambato', 'loja']

print('Generando registros...')
registros = []
for i in range(200):
    prod = random.choice(productos)
    ag = random.choice(agencias)
    cant = random.randint(10, 100)
    total = cant * prod['precio']
    
    # Productos con mas devolucion
    if prod['codigo'] in ['4716', '6191', 'SAL01', '1837']:
        dev = int(cant * random.uniform(0.05, 0.20))
    else:
        dev = int(cant * random.uniform(0, 0.03))
    
    registros.append({
        'centro_costo': ag,
        'codigo_producto': prod['codigo'],
        'producto': prod['nombre'],
        'cant_venta': cant,
        'total_venta': round(total, 2),
        'cant_devolucion': dev,
        'total_devolucion': round(dev * prod['precio'], 2),
        'dias_vida_util': prod['dias_vida_util'],
        'motivo_devolucion': 'CADUCADO' if dev > 0 else None
    })

print(f'Registros generados: {len(registros)}')

# Conectar y cargar
print('Conectando a PostgreSQL...')
conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()

# Crear tabla
print('Creando tabla...')
cur.execute('DROP TABLE IF EXISTS silver.kronos_ventas_silver CASCADE')
cur.execute('''
CREATE TABLE silver.kronos_ventas_silver (
    id SERIAL PRIMARY KEY,
    centro_costo VARCHAR(50),
    codigo_producto VARCHAR(20),
    producto VARCHAR(100),
    cant_venta NUMERIC(12,2),
    total_venta NUMERIC(15,2),
    cant_devolucion NUMERIC(12,2),
    total_devolucion NUMERIC(15,2),
    dias_vida_util INTEGER,
    motivo_devolucion VARCHAR(50)
)''')

# Insertar datos
cols = ['centro_costo', 'codigo_producto', 'producto', 'cant_venta', 'total_venta', 'cant_devolucion', 'total_devolucion', 'dias_vida_util', 'motivo_devolucion']
data = [tuple(r[c] for c in cols) for r in registros]

print('Insertando datos...')
execute_values(cur, f'INSERT INTO silver.kronos_ventas_silver ({",".join(cols)}) VALUES %s', data)
conn.commit()

print(f'OK: {len(data)} registros insertados')

# Crear tabla gold.metricas_productos
print('Creando metricas_productos...')
cur.execute('DROP TABLE IF EXISTS gold.metricas_productos CASCADE')
cur.execute('''
CREATE TABLE gold.metricas_productos (
    id SERIAL PRIMARY KEY,
    codigo_producto VARCHAR(20),
    producto VARCHAR(100),
    categoria VARCHAR(50),
    cantidad_vendida INTEGER,
    cantidad_devuelta INTEGER,
    total_ventas NUMERIC(15,2),
    total_devoluciones NUMERIC(15,2),
    tasa_devolucion NUMERIC(8,2),
    rentabilidad_porcentual NUMERIC(8,2),
    n_agencias_venta INTEGER,
    dias_vida_util INTEGER,
    motivo_devolucion_principal VARCHAR(50)
)''')

# Agregar por producto
df = pd.DataFrame(registros)
agg = df.groupby(['codigo_producto', 'producto']).agg({
    'cant_venta': 'sum',
    'cant_devolucion': 'sum',
    'total_venta': 'sum',
    'total_devolucion': 'sum',
    'dias_vida_util': 'first',
    'centro_costo': 'nunique'
}).reset_index()

agg['tasa_devolucion'] = (agg['cant_devolucion'] / agg['cant_venta'] * 100).round(2)
agg['motivo'] = agg.apply(lambda x: 'CADUCADO' if x['cant_devolucion'] > 0 else None, axis=1)

data2 = [(r['codigo_producto'], r['producto'], 'SALSAS', int(r['cant_venta']), int(r['cant_devolucion']), 
          float(r['total_venta']), float(r['total_devolucion']), float(r['tasa_devolucion']), 
          25.0, int(r['centro_costo']), int(r['dias_vida_util']), r['motivo']) for _, r in agg.iterrows()]

execute_values(cur, '''INSERT INTO gold.metricas_productos 
    (codigo_producto, producto, categoria, cantidad_vendida, cantidad_devuelta, total_ventas, 
     total_devoluciones, tasa_devolucion, rentabilidad_porcentual, n_agencias_venta, dias_vida_util, motivo_devolucion_principal) 
    VALUES %s''', data2)
conn.commit()

print(f'OK: {len(data2)} productos en metricas_productos')

cur.close()
conn.close()
print('=== DATOS CARGADOS CORRECTAMENTE ===')
