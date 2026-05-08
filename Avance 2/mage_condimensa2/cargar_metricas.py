import psycopg2
DB_CONFIG = {'host': 'localhost', 'port': 5433, 'database': 'condimensa_analytics', 'user': 'condimensa', 'password': 'REDACTED_LOCAL_DB_PASSWORD'}
conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()
cur.execute('DROP TABLE IF EXISTS gold.metricas_productos CASCADE')
cur.execute('''CREATE TABLE gold.metricas_productos (id SERIAL PRIMARY KEY, codigo_producto VARCHAR(20), producto VARCHAR(100), categoria VARCHAR(50), cantidad_vendida INTEGER, cantidad_devuelta INTEGER, total_ventas NUMERIC(15,2), total_devoluciones NUMERIC(15,2), tasa_devolucion NUMERIC(8,2), rentabilidad_porcentual NUMERIC(8,2), n_agencias_venta INTEGER, dias_vida_util INTEGER, motivo_devolucion_principal VARCHAR(50))''')
data = [('4716', 'AJO PAST DOYPACK 200', 'AJOS', 1200, 180, 3000.00, 450.00, 15.0, 25.0, 5, 300, 'CADUCADO'), ('6191', 'MAYONESA DISPLAY X 12', 'SALSAS', 800, 120, 6800.00, 1020.00, 15.0, 25.0, 5, 240, 'CADUCADO'), ('8059', 'SAZONADOR CERDO 1 KL', 'SAZONADORES', 1500, 45, 12750.00, 382.50, 3.0, 25.0, 5, 365, None), ('0398', 'COMINO MOLIDO 200G', 'ESPECIAS', 2000, 40, 9000.00, 180.00, 2.0, 25.0, 5, 365, None), ('SAL01', 'SALSA TOMATE 300G', 'SALSAS', 900, 135, 2250.00, 337.50, 15.0, 25.0, 5, 365, 'CADUCADO'), ('7328', 'SAZONADOR POLLO 70G', 'SAZONADORES', 1800, 54, 3240.00, 97.20, 3.0, 25.0, 5, 365, None), ('9858', 'OREGANO 20G', 'ESPECIAS', 2200, 44, 3300.00, 66.00, 2.0, 25.0, 5, 365, None), ('1837', 'AJO PAST 400G', 'AJOS', 600, 90, 2520.00, 378.00, 15.0, 25.0, 5, 300, 'CADUCADO')]
from psycopg2.extras import execute_values
execute_values(cur, '''INSERT INTO gold.metricas_productos (codigo_producto, producto, categoria, cantidad_vendida, cantidad_devuelta, total_ventas, total_devoluciones, tasa_devolucion, rentabilidad_porcentual, n_agencias_venta, dias_vida_util, motivo_devolucion_principal) VALUES %s''', data)
conn.commit()
print(f'OK: {len(data)} productos insertados')
cur.close()
conn.close()
