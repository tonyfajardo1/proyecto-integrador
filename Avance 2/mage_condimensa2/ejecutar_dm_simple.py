"""
Script simple para ejecutar Data Mining - version rapida
"""
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime
import numpy as np

DB = {'host': 'localhost', 'port': 5433, 'database': 'condimensa_analytics',
      'user': 'condimensa', 'password': 'change_me'}

def main():
    print("="*70)
    print("DATA MINING - CONDIMENSA")
    print("="*70)

    conn = psycopg2.connect(**DB)
    cur = conn.cursor()

    # ===== 1. ISOLATION FOREST =====
    print("\n[1] ISOLATION FOREST - Anomalias")
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler

    cur.execute("SELECT * FROM gold.metricas_agencias")
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    df2 = pd.DataFrame(rows, columns=cols)
    print(f"    Agencias: {len(df2)}")

    df2['ratio_costo'] = 100 - df2['rentabilidad_porcentual'].astype(float)
    features = ['tasa_devolucion', 'rentabilidad_porcentual', 'ratio_costo', 'ticket_promedio']

    for f in features:
        df2[f] = pd.to_numeric(df2[f], errors='coerce').fillna(0)

    X = df2[features].values
    X_scaled = StandardScaler().fit_transform(X)

    iso = IsolationForest(n_estimators=100, contamination=0.2, random_state=42)
    df2['es_anomalia'] = iso.fit_predict(X_scaled) == -1
    df2['anomaly_score'] = iso.decision_function(X_scaled)

    for f in features:
        m, s = df2[f].mean(), df2[f].std()
        df2[f'z_{f}'] = (df2[f] - m) / s if s > 0 else 0

    def razon(row):
        if not row['es_anomalia']: return 'NORMAL'
        r = []
        if row['z_tasa_devolucion'] > 1: r.append('ALTA_DEVOLUCION')
        elif row['z_tasa_devolucion'] < -1: r.append('BAJA_DEVOLUCION')
        if row['z_rentabilidad_porcentual'] > 1: r.append('ALTA_RENTABILIDAD')
        elif row['z_rentabilidad_porcentual'] < -1: r.append('BAJA_RENTABILIDAD')
        return ', '.join(r) if r else 'PATRON_INUSUAL'

    df2['razon'] = df2.apply(razon, axis=1)

    print("    Anomalias detectadas:")
    for _, r in df2[df2['es_anomalia']].iterrows():
        print(f"      - {r['centro_costo'].upper()}: {r['razon']}")

    cur.execute('DROP TABLE IF EXISTS gold.anomalias_agencias CASCADE;')
    cur.execute('''CREATE TABLE gold.anomalias_agencias (
        id SERIAL PRIMARY KEY, agencia VARCHAR(50), es_anomalia BOOLEAN,
        anomaly_score NUMERIC(10,6), razon_anomalia VARCHAR(100),
        tasa_devolucion NUMERIC(8,2), rentabilidad_porcentual NUMERIC(8,2));''')

    data = [(r['centro_costo'], bool(r['es_anomalia']), float(r['anomaly_score']),
             r['razon'], float(r['tasa_devolucion']), float(r['rentabilidad_porcentual']))
            for _, r in df2.iterrows()]
    execute_values(cur, '''INSERT INTO gold.anomalias_agencias
        (agencia, es_anomalia, anomaly_score, razon_anomalia, tasa_devolucion, rentabilidad_porcentual)
        VALUES %s''', data)
    conn.commit()
    print("    OK: gold.anomalias_agencias")

    # ===== 2. RANDOM FOREST =====
    print("\n[2] RANDOM FOREST - Predicciones")
    from sklearn.ensemble import RandomForestClassifier

    cur.execute("SELECT * FROM gold.metricas_productos")
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    df3 = pd.DataFrame(rows, columns=cols)
    print(f"    Productos: {len(df3)}")

    for c in ['tasa_devolucion', 'cantidad_vendida', 'rentabilidad_porcentual', 'n_agencias_venta', 'es_producto_nuevo']:
        df3[c] = pd.to_numeric(df3[c], errors='coerce').fillna(0)

    df3['target'] = (df3['tasa_devolucion'] > 10).astype(int)
    df3['cat_enc'] = pd.factorize(df3['categoria'])[0]
    df3['log_qty'] = np.log1p(df3['cantidad_vendida'])

    feats = ['cat_enc', 'log_qty', 'rentabilidad_porcentual', 'n_agencias_venta', 'es_producto_nuevo']
    X = df3[feats].values
    y = df3['target'].values

    model = RandomForestClassifier(n_estimators=50, max_depth=5, random_state=42, class_weight='balanced')
    model.fit(X, y)

    if len(model.classes_) > 1:
        df3['prob'] = model.predict_proba(X)[:, 1]
    else:
        df3['prob'] = 0.5

    df3['riesgo'] = df3['prob'].apply(lambda x: 'ALTO' if x >= 0.6 else 'MEDIO' if x >= 0.3 else 'BAJO')

    print("    Productos alto riesgo:")
    for _, r in df3[df3['riesgo'] == 'ALTO'].iterrows():
        print(f"      - {r['producto']}: {r['prob']*100:.0f}% prob")

    cur.execute('DROP TABLE IF EXISTS gold.predicciones_devolucion CASCADE;')
    cur.execute('''CREATE TABLE gold.predicciones_devolucion (
        id SERIAL PRIMARY KEY, codigo_producto VARCHAR(20), producto VARCHAR(100),
        categoria VARCHAR(50), tasa_devolucion_actual NUMERIC(8,2),
        prob_devolucion_alta NUMERIC(8,4), nivel_riesgo VARCHAR(20));''')

    data = [(r['codigo_producto'], r['producto'], r['categoria'],
             float(r['tasa_devolucion']), float(r['prob']), r['riesgo'])
            for _, r in df3.iterrows()]
    execute_values(cur, '''INSERT INTO gold.predicciones_devolucion
        (codigo_producto, producto, categoria, tasa_devolucion_actual, prob_devolucion_alta, nivel_riesgo)
        VALUES %s''', data)
    conn.commit()
    print("    OK: gold.predicciones_devolucion")

    # ===== 3. APRIORI (Simplificado) =====
    print("\n[3] APRIORI - Cross-Selling (muestra)")

    # Usar solo 500 transacciones para velocidad
    cur.execute("SELECT transaccion_id, producto FROM dm.cestas_transacciones WHERE transaccion_id IN (SELECT DISTINCT transaccion_id FROM dm.cestas_transacciones ORDER BY transaccion_id LIMIT 500)")
    rows = cur.fetchall()
    df = pd.DataFrame(rows, columns=['transaccion_id', 'producto'])
    print(f"    Transacciones: {df['transaccion_id'].nunique()}")

    from mlxtend.frequent_patterns import apriori, association_rules
    from mlxtend.preprocessing import TransactionEncoder

    transacciones = df.groupby('transaccion_id')['producto'].apply(list).tolist()
    te = TransactionEncoder()
    te_array = te.fit_transform(transacciones)
    df_encoded = pd.DataFrame(te_array, columns=te.columns_)

    itemsets = apriori(df_encoded, min_support=0.05, use_colnames=True)
    print(f"    Itemsets: {len(itemsets)}")

    if len(itemsets) > 0:
        rules = association_rules(itemsets, metric='confidence', min_threshold=0.3)
        rules = rules[rules['antecedents'].apply(len) >= 1]
        print(f"    Reglas: {len(rules)}")

        print("    Top 5 reglas:")
        for i, (_, r) in enumerate(rules.nlargest(5, 'lift').iterrows(), 1):
            ant = ', '.join(list(r['antecedents']))
            con = ', '.join(list(r['consequents']))
            print(f"      {i}. {ant} -> {con} (lift={r['lift']:.2f})")

        rules['antecedente'] = rules['antecedents'].apply(lambda x: ', '.join(list(x)))
        rules['consecuente'] = rules['consequents'].apply(lambda x: ', '.join(list(x)))
        rules['interpretacion'] = rules['lift'].apply(lambda x: 'FUERTE' if x > 2 else 'MODERADA' if x > 1.5 else 'DEBIL')

        cur.execute('DROP TABLE IF EXISTS gold.reglas_asociacion CASCADE;')
        cur.execute('''CREATE TABLE gold.reglas_asociacion (
            id SERIAL PRIMARY KEY, antecedente VARCHAR(500), consecuente VARCHAR(500),
            soporte NUMERIC(8,6), confianza NUMERIC(8,6), lift NUMERIC(10,4),
            interpretacion VARCHAR(20));''')

        data = [(r['antecedente'], r['consecuente'], float(r['support']),
                 float(r['confidence']), float(r['lift']), r['interpretacion'])
                for _, r in rules.iterrows()]
        execute_values(cur, '''INSERT INTO gold.reglas_asociacion
            (antecedente, consecuente, soporte, confianza, lift, interpretacion)
            VALUES %s''', data)
        conn.commit()
        print(f"    OK: {len(rules)} reglas en gold.reglas_asociacion")

    conn.close()
    print("\n" + "="*70)
    print("COMPLETADO")
    print("="*70)

if __name__ == "__main__":
    main()
