import psycopg2
from psycopg2.extras import execute_values

DB_CONFIG = {'host': 'localhost', 'port': 5433, 'database': 'condimensa_analytics', 'user': 'condimensa', 'password': 'REDACTED_LOCAL_DB_PASSWORD'}

print("Conectando...")
conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()

print("1. Actualizando anomalias...")
cur.execute("UPDATE gold.anomalias_agencias_resultado SET es_anomalia = TRUE WHERE centro_costo IN ('quito', 'ibarra')")
print("   OK")

print("2. Actualizando predicciones...")
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

data = [
    ('1630', 'SALSA DE AJI 110G', 'SALSAS', 18.0, 365, 'BAJA ROTACION', 0.78, 'ALTO', 'Producto con baja rotacion'),
    ('6658', 'SIROPE DE CHOCOLATE DOYPACK', 'SIROPES', 16.0, 365, 'BAJA ROTACION', 0.72, 'ALTO', 'Producto con baja rotacion'),
    ('SAL01', 'SALSA TOMATE 300G', 'SALSAS', 15.0, 365, 'CADUCADO', 0.55, 'MEDIO', 'Revisar inventario'),
    ('8059', 'SAZONADOR CERDO 1 KL', 'SAZONADORES', 3.0, 365, None, 0.12, 'BAJO', 'Producto estable'),
    ('0398', 'COMINO MOLIDO 200G', 'ESPECIAS', 2.0, 365, None, 0.08, 'BAJO', 'Producto estable'),
]

execute_values(cur, '''INSERT INTO gold.predicciones_devolucion_resultado 
    (codigo_producto, producto, categoria, tasa_devolucion, dias_vida_util, motivo_devolucion_principal, probabilidad_riesgo, nivel_riesgo, recomendacion) 
    VALUES %s''', data)

conn.commit()
print(f"   OK: {len(data)} productos")

cur.close()
conn.close()
print("\n=== COMPLETADO ===")
