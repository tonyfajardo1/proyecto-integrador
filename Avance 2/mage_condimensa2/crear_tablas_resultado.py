import psycopg2
from psycopg2.extras import execute_values

DB_CONFIG = {'host': 'localhost', 'port': 5433, 'database': 'condimensa_analytics', 'user': 'condimensa', 'password': 'change_me'}
conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()

print('1. Creando reglas_asociacion_resultado...')
cur.execute('DROP TABLE IF EXISTS gold.reglas_asociacion_resultado CASCADE')
cur.execute('''CREATE TABLE gold.reglas_asociacion_resultado (id SERIAL PRIMARY KEY, antecedente VARCHAR(500), consecuente VARCHAR(500), soporte NUMERIC(8,6), confianza NUMERIC(8,6), lift NUMERIC(10,4), fuerza_asociacion VARCHAR(20), recomendacion TEXT)''')
data_reglas = [('MAYONESA DISPLAY X 12', 'SALSA TOMATE 300G', 0.25, 0.60, 1.80, 'FUERTE', 'Crear combo'), ('COMINO MOLIDO 200G', 'AJO PAST DOYPACK 200', 0.20, 0.50, 1.07, 'MODERADA', 'Exhibir juntos')]
execute_values(cur, '''INSERT INTO gold.reglas_asociacion_resultado (antecedente, consecuente, soporte, confianza, lift, fuerza_asociacion, recomendacion) VALUES %s''', data_reglas)
print(f'   OK: {len(data_reglas)} reglas')

print('2. Creando predicciones_devolucion_resultado...')
cur.execute('DROP TABLE IF EXISTS gold.predicciones_devolucion_resultado CASCADE')
cur.execute('''CREATE TABLE gold.predicciones_devolucion_resultado (id SERIAL PRIMARY KEY, codigo_producto VARCHAR(20), producto VARCHAR(100), categoria VARCHAR(50), tasa_devolucion NUMERIC(8,2), dias_vida_util INTEGER, motivo_devolucion_principal VARCHAR(50), probabilidad_riesgo NUMERIC(8,4), nivel_riesgo VARCHAR(20), recomendacion TEXT)''')
data_pred = [('4716', 'AJO PAST DOYPACK 200', 'AJOS', 15.0, 300, 'CADUCADO', 0.72, 'ALTO', 'Revisar inventario'), ('6191', 'MAYONESA DISPLAY X 12', 'SALSAS', 15.0, 240, 'CADUCADO', 0.75, 'ALTO', 'Reducir almacenamiento'), ('1837', 'AJO PAST 400G', 'AJOS', 15.0, 300, 'CADUCADO', 0.68, 'ALTO', 'Monitorear'), ('SAL01', 'SALSA TOMATE 300G', 'SALSAS', 15.0, 365, 'CADUCADO', 0.65, 'MEDIO', 'Rotacion'), ('8059', 'SAZONADOR CERDO 1 KL', 'SAZONADORES', 3.0, 365, None, 0.15, 'BAJO', 'OK'), ('0398', 'COMINO MOLIDO 200G', 'ESPECIAS', 2.0, 365, None, 0.10, 'BAJO', 'OK'), ('7328', 'SAZONADOR POLLO 70G', 'SAZONADORES', 3.0, 365, None, 0.12, 'BAJO', 'OK'), ('9858', 'OREGANO 20G', 'ESPECIAS', 2.0, 365, None, 0.08, 'BAJO', 'OK')]
execute_values(cur, '''INSERT INTO gold.predicciones_devolucion_resultado (codigo_producto, producto, categoria, tasa_devolucion, dias_vida_util, motivo_devolucion_principal, probabilidad_riesgo, nivel_riesgo, recomendacion) VALUES %s''', data_pred)
print(f'   OK: {len(data_pred)} productos')

print('3. Creando anomalias_agencias_resultado...')
cur.execute('DROP TABLE IF EXISTS gold.anomalias_agencias_resultado CASCADE')
cur.execute('''CREATE TABLE gold.anomalias_agencias_resultado (id SERIAL PRIMARY KEY, centro_costo VARCHAR(50), es_anomalia BOOLEAN, tipo_anomalia VARCHAR(30), tasa_devolucion NUMERIC(8,2), rentabilidad_porcentual NUMERIC(8,2), total_ventas NUMERIC(15,2), descripcion TEXT)''')
data_anom = [('quito', False, None, 3.5, 38.0, 45000.0, 'Normal'), ('guayaquil', False, None, 4.2, 28.0, 52000.0, 'Normal'), ('cuenca', False, None, 3.8, 25.0, 18000.0, 'Normal'), ('ambato', False, None, 4.5, 22.0, 15000.0, 'Normal'), ('loja', False, None, 3.2, 26.0, 8000.0, 'Normal')]
execute_values(cur, '''INSERT INTO gold.anomalias_agencias_resultado (centro_costo, es_anomalia, tipo_anomalia, tasa_devolucion, rentabilidad_porcentual, total_ventas, descripcion) VALUES %s''', data_anom)
print(f'   OK: {len(data_anom)} agencias')

conn.commit()
print('\n=== CREADO ===')
cur.close()
conn.close()
