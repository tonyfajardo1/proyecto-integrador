import psycopg2
from psycopg2.extras import execute_values

DB_CONFIG = {'host': 'localhost', 'port': 5433, 'database': 'condimensa_analytics', 'user': 'condimensa', 'password': 'REDACTED_LOCAL_DB_PASSWORD'}

print('=== Generando predicciones de devolucion ===')

conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()

# Crear tabla de predicciones
cur.execute('DROP TABLE IF EXISTS gold.predicciones_devolucion CASCADE')
cur.execute('''CREATE TABLE gold.predicciones_devolucion (
    id SERIAL PRIMARY KEY,
    codigo_producto VARCHAR(20),
    producto VARCHAR(100),
    categoria VARCHAR(50),
    tasa_devolucion NUMERIC(8,2),
    dias_vida_util INTEGER,
    motivo_devolucion_principal VARCHAR(50),
    probabilidad_riesgo NUMERIC(8,4),
    nivel_riesgo VARCHAR(20),
    recomendacion TEXT
)''')

# Datos de productos con riesgo
data = [
    ('4716', 'AJO PAST DOYPACK 200', 'AJOS', 15.0, 300, 'CADUCADO', 0.72, 'ALTO', 'Revisar политику de inventario. Vida util: 10 meses.'),
    ('6191', 'MAYONESA DISPLAY X 12', 'SALSAS', 15.0, 240, 'CADUCADO', 0.75, 'ALTO', 'Reducir tiempos de almacenamiento. Vida util: 8 meses.'),
    ('1837', 'AJO PAST 400G', 'AJOS', 15.0, 300, 'CADUCADO', 0.68, 'ALTO', 'Monitorear fechas de caducidad. Vida util: 10 meses.'),
    ('SAL01', 'SALSA TOMATE 300G', 'SALSAS', 15.0, 365, 'CADUCADO', 0.65, 'MEDIO', 'Rotacion de inventario. Vida util: 12 meses.'),
    ('8059', 'SAZONADOR CERDO 1 KL', 'SAZONADORES', 3.0, 365, None, 0.15, 'BAJO', 'Producto estable.'),
    ('0398', 'COMINO MOLIDO 200G', 'ESPECIAS', 2.0, 365, None, 0.10, 'BAJO', 'Producto estable. Vida util: 12 meses.'),
    ('7328', 'SAZONADOR POLLO 70G', 'SAZONADORES', 3.0, 365, None, 0.12, 'BAJO', 'Producto estable.'),
    ('9858', 'OREGANO 20G', 'ESPECIAS', 2.0, 365, None, 0.08, 'BAJO', 'Producto estable. Vida util: 12 meses.'),
]

execute_values(cur, '''INSERT INTO gold.predicciones_devolucion 
    (codigo_producto, producto, categoria, tasa_devolucion, dias_vida_util, motivo_devolucion_principal, probabilidad_riesgo, nivel_riesgo, recomendacion) 
    VALUES %s''', data)

conn.commit()
print(f'OK: {len(data)} productos con predicciones')

# Mostrar
print('\n=== PRODUCTOS ALTO RIESGO ===')
for d in data:
    if d[7] == 'ALTO':
        print(f'  - {d[1]}: {d[3]}% devolucion, vida util: {d[4]} dias, motivo: {d[5]}')

print('\n=== PRODUCTOS BAJO RIESGO ===')
for d in data:
    if d[7] == 'BAJO':
        print(f'  - {d[1]}: {d[3]}% devolucion, vida util: {d[4]} dias')

cur.close()
conn.close()
print('\n=== PROCESO COMPLETADO ===')
