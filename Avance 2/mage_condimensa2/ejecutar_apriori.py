import psycopg2
import pandas as pd
from mlxtend.frequent_patterns import apriori, association_rules
from mlxtend.preprocessing import TransactionEncoder
from psycopg2.extras import execute_values

DB_CONFIG = {'host': 'localhost', 'port': 5433, 'database': 'condimensa_analytics', 'user': 'condimensa', 'password': 'change_me'}

print('=== Generando reglas de asociacion (Apriori) ===')

# Crear datos de transacciones de ejemplo
transacciones = [
    ['AJO PAST DOYPACK 200', 'SAZONADOR POLLO 70G', 'OREGANO 20G'],
    ['AJO PAST DOYPACK 200', 'COMINO MOLIDO 200G'],
    ['MAYONESA DISPLAY X 12', 'SALSA TOMATE 300G', 'AJO PAST 400G'],
    ['SAZONADOR CERDO 1 KL', 'AJO PAST DOYPACK 200', 'COMINO MOLIDO 200G'],
    ['MAYONESA DISPLAY X 12', 'SALSA TOMATE 300G'],
    ['AJO PAST DOYPACK 200', 'OREGANO 20G', 'COMINO MOLIDO 200G'],
    ['SAZONADOR POLLO 70G', 'AJO PAST 400G'],
    ['MAYONESA DISPLAY X 12', 'AJO PAST DOYPACK 200'],
    ['SALSA TOMATE 300G', 'AJO PAST 400G', 'COMINO MOLIDO 200G'],
    ['SAZONADOR CERDO 1 KL', 'COMINO MOLIDO 200G'],
    ['AJO PAST DOYPACK 200', 'SALSA TOMATE 300G', 'MAYONESA DISPLAY X 12'],
    ['COMINO MOLIDO 200G', 'OREGANO 20G', 'SALSA TOMATE 300G'],
    ['AJO PAST 400G', 'MAYONESA DISPLAY X 12'],
    ['SAZONADOR POLLO 70G', 'OREGANO 20G'],
    ['AJO PAST DOYPACK 200', 'SAZONADOR CERDO 1 KL'],
]

# Codificar
te = TransactionEncoder()
te_array = te.fit_transform(transacciones)
df_encoded = pd.DataFrame(te_array, columns=te.columns_)

print(f'Transacciones: {len(transacciones)}, Productos: {len(te.columns_)}')

# Encontrar itemsets frecuentes
frequent_itemsets = apriori(df_encoded, min_support=0.15, use_colnames=True)
print(f'Itemsets frecuentes: {len(frequent_itemsets)}')

if len(frequent_itemsets) > 0:
    # Generar reglas
    rules = association_rules(frequent_itemsets, metric="confidence", min_threshold=0.3)
    rules = rules[rules['antecedents'].apply(len) >= 1]
    rules = rules[rules['consequents'].apply(len) >= 1]
    
    # Eliminar duplicados viceversa
    def get_rule_key(antecedents, consequents):
        ant = frozenset(antecedents)
        cons = frozenset(consequents)
        return tuple(sorted([tuple(ant), tuple(cons)]))
    
    rules['rule_key'] = rules.apply(lambda r: get_rule_key(r['antecedents'], r['consequents']), axis=1)
    rules = rules.drop_duplicates(subset='rule_key', keep='first')
    rules = rules.sort_values('lift', ascending=False)
    
    print(f'Reglas unicas: {len(rules)}')
    
    # Guardar en base de datos
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    cur.execute('DROP TABLE IF EXISTS gold.reglas_asociacion CASCADE')
    cur.execute('''CREATE TABLE gold.reglas_asociacion (
        id SERIAL PRIMARY KEY,
        antecedente VARCHAR(500),
        consecuente VARCHAR(500),
        soporte NUMERIC(8,6),
        confianza NUMERIC(8,6),
        lift NUMERIC(10,4),
        interpretacion VARCHAR(20),
        fecha_calculo TIMESTAMP DEFAULT NOW()
    )''')
    
    data = []
    for _, r in rules.iterrows():
        ant = ', '.join(list(r['antecedents']))
        cons = ', '.join(list(r['consequents']))
        interp = 'FUERTE' if r['lift'] > 2 else 'MODERADA' if r['lift'] > 1.5 else 'DEBIL'
        data.append((ant, cons, float(r['support']), float(r['confidence']), float(r['lift']), interp))
    
    execute_values(cur, '''INSERT INTO gold.reglas_asociacion (antecedente, consecuente, soporte, confianza, lift, interpretacion) VALUES %s''', data)
    conn.commit()
    
    print(f'OK: {len(data)} reglas guardadas')
    
    # Mostrar reglas
    print('\n=== REGLAS DE ASOCIACION ===')
    for i, r in enumerate(data[:6], 1):
        print(f'{i}. {r[0]} -> {r[1]} (Lift: {r[4]:.2f}, Conf: {r[3]*100:.0f}%)')
    
    cur.close()
    conn.close()

print('=== PROCESO COMPLETADO ===')
