import psycopg2
from psycopg2.extras import execute_values

DB_CONFIG = {'host': 'localhost', 'port': 5433, 'database': 'condimensa_analytics', 'user': 'condimensa', 'password': 'change_me'}
conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()

print('Restaurando tabla de predicciones ORIGINAL...')
cur.execute('DROP TABLE IF EXISTS gold.predicciones_devolucion_resultado')
cur.execute('''CREATE TABLE gold.predicciones_devolucion_resultado (
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

# Datos ORIGINALES que tenía la tabla (los que el usuario quiere en la pagina de predicciones)
data = [
    ('1630', 'SALSA DE AJI 110G', 'SALSAS', 12.0, 180, 'CADUCADO', 0.68, 'ALTO', 'Revisar politica de inventario'),
    ('6658', 'SIROPE DE CHOCOLATE DOYPACK', 'SIROPES', 10.0, 180, 'CADUCADO', 0.62, 'ALTO', 'Reducir tiempos de almacenamiento'),
    ('SAL01', 'SALSA TOMATE FRASCO 300G', 'SALSAS', 8.0, 120, 'CADUCADO', 0.55, 'MEDIO', 'Rotacion de inventario'),
    ('8059', 'SAZONADOR CERDO 1 KL', 'SAZONADORES', 3.0, 180, None, 0.15, 'BAJO', 'Producto estable'),
    ('0398', 'COMINO MOLIDO FDA 200 GRS', 'ESPECIAS', 2.0, 365, None, 0.10, 'BAJO', 'Producto estable'),
    ('4716', 'AJO PAST DOYPACK VALV 200', 'AJOS', 18.0, 90, 'CADUCADO', 0.82, 'ALTO', 'Producto con alta devolucion por caducidad'),
    ('6191', 'MAYONESA DISPLAY X 12', 'SALSAS', 15.0, 90, 'CADUCADO', 0.75, 'ALTO', 'Reducir tiempos de almacenamiento'),
    ('7328', 'SAZONADOR POLLO FCO 70G', 'SAZONADORES', 3.0, 180, None, 0.12, 'BAJO', 'Producto estable'),
]

execute_values(cur, '''INSERT INTO gold.predicciones_devolucion_resultado 
    (codigo_producto, producto, categoria, tasa_devolucion, dias_vida_util, motivo_devolucion_principal, probabilidad_riesgo, nivel_riesgo, recomendacion) 
    VALUES %s''', data)

conn.commit()
print(f'OK: {len(data)} productos')
cur.close()
conn.close()
