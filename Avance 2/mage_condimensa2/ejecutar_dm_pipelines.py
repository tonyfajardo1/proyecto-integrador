"""
Script para ejecutar los pipelines de Data Mining manualmente
y guardar los resultados en PostgreSQL.
"""

import pandas as pd
import numpy as np
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime

# Configuracion de conexion
DB_CONFIG = {
    'host': 'localhost',
    'port': 5433,
    'database': 'condimensa_analytics',
    'user': 'condimensa',
    'password': 'REDACTED_LOCAL_DB_PASSWORD'
}


def ejecutar_apriori():
    """
    Ejecuta el pipeline de reglas de asociacion (Cross-Selling).
    """
    print("\n" + "="*70)
    print("PIPELINE: REGLAS DE ASOCIACION (APRIORI)")
    print("Pregunta: ¿Que productos se venden juntos?")
    print("="*70)

    try:
        from mlxtend.frequent_patterns import apriori, association_rules
        from mlxtend.preprocessing import TransactionEncoder
    except ImportError:
        import subprocess
        subprocess.check_call(['pip', 'install', 'mlxtend', '-q'])
        from mlxtend.frequent_patterns import apriori, association_rules
        from mlxtend.preprocessing import TransactionEncoder

    # Cargar datos
    conn = psycopg2.connect(**DB_CONFIG)
    df = pd.read_sql("SELECT transaccion_id, producto FROM dm.cestas_transacciones", conn)

    print(f"\n[1] Datos cargados: {len(df)} items, {df['transaccion_id'].nunique()} transacciones")

    # Crear lista de transacciones
    transacciones = df.groupby('transaccion_id')['producto'].apply(list).tolist()
    print(f"    Ejemplo de cesta: {transacciones[0][:3]}...")

    # Codificar transacciones
    te = TransactionEncoder()
    te_array = te.fit_transform(transacciones)
    df_encoded = pd.DataFrame(te_array, columns=te.columns_)

    print(f"\n[2] Matriz codificada: {df_encoded.shape[0]} x {df_encoded.shape[1]}")

    # Encontrar itemsets frecuentes
    frequent_itemsets = apriori(df_encoded, min_support=0.05, use_colnames=True)
    print(f"\n[3] Itemsets frecuentes encontrados: {len(frequent_itemsets)}")

    if len(frequent_itemsets) == 0:
        frequent_itemsets = apriori(df_encoded, min_support=0.02, use_colnames=True)
        print(f"    Con min_support=0.02: {len(frequent_itemsets)}")

    # Generar reglas
    if len(frequent_itemsets) > 0:
        rules = association_rules(frequent_itemsets, metric="confidence", min_threshold=0.3)
        rules = rules[rules['antecedents'].apply(len) >= 1]
        rules = rules[rules['consequents'].apply(len) >= 1]

        print(f"\n[4] Reglas de asociacion generadas: {len(rules)}")

        # =========================================================================
        # ELIMINAR REGLAS DUPLICADAS (VICEVERSA)
        # =========================================================================
        def get_rule_key(antecedents, consequents):
            ant = frozenset(antecedents)
            cons = frozenset(consequents)
            return tuple(sorted([tuple(ant), tuple(cons)]))

        rules['rule_key'] = rules.apply(lambda r: get_rule_key(r['antecedents'], r['consequents']), axis=1)
        rules = rules.drop_duplicates(subset='rule_key', keep='first')
        rules = rules.sort_values('lift', ascending=False)
        
        print(f"    Reglas unicas (sin duplicados viceversa): {len(rules)}")

        # Mostrar top 10
        print(f"\n[5] TOP 10 REGLAS DE CROSS-SELLING (por Lift):")
        top_rules = rules.nlargest(10, 'lift')
        for idx, (_, rule) in enumerate(top_rules.iterrows(), 1):
            antecedent = ', '.join(list(rule['antecedents']))
            consequent = ', '.join(list(rule['consequents']))
            interpretacion = "FUERTE" if rule['lift'] > 2 else "MODERADA" if rule['lift'] > 1.5 else "DEBIL"
            print(f"\n    [{idx}] SI compra: {antecedent}")
            print(f"        ENTONCES compra: {consequent}")
            print(f"        Confianza: {rule['confidence']*100:.1f}% | Lift: {rule['lift']:.2f} ({interpretacion})")

        # Preparar para guardar
        rules['antecedente'] = rules['antecedents'].apply(lambda x: ', '.join(list(x)))
        rules['consecuente'] = rules['consequents'].apply(lambda x: ', '.join(list(x)))
        rules['interpretacion'] = rules['lift'].apply(
            lambda x: 'FUERTE' if x > 2 else ('MODERADA' if x > 1.5 else 'DEBIL')
        )

        df_rules = rules[['antecedente', 'consecuente', 'support', 'confidence', 'lift', 'interpretacion']].copy()
        df_rules.columns = ['antecedente', 'consecuente', 'soporte', 'confianza', 'lift', 'interpretacion']

        # Guardar en PostgreSQL
        cur = conn.cursor()
        cur.execute("DROP TABLE IF EXISTS gold.reglas_asociacion CASCADE;")
        cur.execute("""
            CREATE TABLE gold.reglas_asociacion (
                id SERIAL PRIMARY KEY,
                antecedente VARCHAR(500),
                consecuente VARCHAR(500),
                soporte NUMERIC(8,6),
                confianza NUMERIC(8,6),
                lift NUMERIC(10,4),
                interpretacion VARCHAR(20),
                fecha_calculo TIMESTAMP DEFAULT NOW()
            );
        """)

        data = [tuple(x) + (datetime.now(),) for x in df_rules.values]
        execute_values(cur, """
            INSERT INTO gold.reglas_asociacion
            (antecedente, consecuente, soporte, confianza, lift, interpretacion, fecha_calculo)
            VALUES %s
        """, data)

        conn.commit()
        print(f"\n[OK] {len(df_rules)} reglas guardadas en gold.reglas_asociacion")

    conn.close()
    return len(rules) if 'rules' in dir() else 0


def ejecutar_isolation_forest():
    """
    Ejecuta el pipeline de deteccion de anomalias.
    """
    print("\n" + "="*70)
    print("PIPELINE: DETECCION DE ANOMALIAS (ISOLATION FOREST)")
    print("Pregunta: ¿Que agencias tienen comportamiento anomalo?")
    print("="*70)

    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler

    # Cargar datos
    conn = psycopg2.connect(**DB_CONFIG)
    df = pd.read_sql("SELECT * FROM gold.metricas_agencias", conn)

    print(f"\n[1] Datos cargados: {len(df)} agencias")

    # Preparar features
    df = df.rename(columns={
        'centro_costo': 'agencia',
        'tasa_devolucion': 'ratio_devolucion',
        'rentabilidad_porcentual': 'ratio_rentabilidad'
    })
    df['ratio_costo'] = 100 - df['ratio_rentabilidad']

    features = ['ratio_devolucion', 'ratio_rentabilidad', 'ratio_costo', 'ticket_promedio']
    X = df[features].copy()

    # Escalar
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Aplicar Isolation Forest
    iso_forest = IsolationForest(n_estimators=100, contamination=0.2, random_state=42)
    df['anomaly_label'] = iso_forest.fit_predict(X_scaled)
    df['anomaly_score'] = iso_forest.decision_function(X_scaled)
    df['es_anomalia'] = df['anomaly_label'] == -1

    # Calcular z-scores
    for feat in features:
        mean_val = df[feat].mean()
        std_val = df[feat].std()
        df[f'zscore_{feat}'] = (df[feat] - mean_val) / std_val if std_val > 0 else 0

    # Clasificar tipo de anomalia
    def clasificar_anomalia(row):
        if not row['es_anomalia']:
            return 'NORMAL', 'Comportamiento dentro de parametros esperados'

        razones = []
        if row['zscore_ratio_devolucion'] > 1.0:
            razones.append('ALTA_DEVOLUCION')
        elif row['zscore_ratio_devolucion'] < -1.0:
            razones.append('BAJA_DEVOLUCION')

        if row['zscore_ratio_rentabilidad'] > 1.0:
            razones.append('ALTA_RENTABILIDAD')
        elif row['zscore_ratio_rentabilidad'] < -1.0:
            razones.append('BAJA_RENTABILIDAD')

        razon = ', '.join(razones) if razones else 'PATRON_INUSUAL'
        return razon, 'Requiere investigacion'

    resultados = df.apply(clasificar_anomalia, axis=1)
    df['razon_anomalia'] = [r[0] for r in resultados]
    df['interpretacion'] = [r[1] for r in resultados]

    print(f"\n[2] Resultados:")
    print(f"    Total agencias: {len(df)}")
    print(f"    Anomalias detectadas: {df['es_anomalia'].sum()}")

    print(f"\n[3] DETALLE DE ANOMALIAS:")
    anomalias = df[df['es_anomalia']].sort_values('anomaly_score')
    for _, row in anomalias.iterrows():
        print(f"\n    AGENCIA: {row['agencia'].upper()}")
        print(f"    Razon: {row['razon_anomalia']}")
        print(f"    Score: {row['anomaly_score']:.4f}")
        print(f"    - Tasa Devolucion: {row['ratio_devolucion']:.2f}%")
        print(f"    - Rentabilidad: {row['ratio_rentabilidad']:.2f}%")

    # Guardar en PostgreSQL
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS gold.anomalias_agencias CASCADE;")
    cur.execute("""
        CREATE TABLE gold.anomalias_agencias (
            id SERIAL PRIMARY KEY,
            agencia VARCHAR(50),
            es_anomalia BOOLEAN,
            anomaly_score NUMERIC(10,6),
            razon_anomalia VARCHAR(100),
            interpretacion VARCHAR(200),
            ratio_devolucion NUMERIC(8,2),
            ratio_rentabilidad NUMERIC(8,2),
            ticket_promedio NUMERIC(12,2),
            fecha_calculo TIMESTAMP DEFAULT NOW()
        );
    """)

    cols = ['agencia', 'es_anomalia', 'anomaly_score', 'razon_anomalia', 'interpretacion',
            'ratio_devolucion', 'ratio_rentabilidad', 'ticket_promedio']
    data = [tuple(x) + (datetime.now(),) for x in df[cols].values]
    execute_values(cur, f"""
        INSERT INTO gold.anomalias_agencias
        ({', '.join(cols)}, fecha_calculo)
        VALUES %s
    """, data)

    conn.commit()
    conn.close()

    print(f"\n[OK] Resultados guardados en gold.anomalias_agencias")
    return df['es_anomalia'].sum()


def ejecutar_random_forest():
    """
    Ejecuta el pipeline de prediccion de devoluciones.
    """
    print("\n" + "="*70)
    print("PIPELINE: PREDICCION DE DEVOLUCIONES (RANDOM FOREST)")
    print("Pregunta: ¿Que productos tienen alto riesgo de devolucion?")
    print("="*70)

    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import classification_report, roc_auc_score

    # Cargar datos
    conn = psycopg2.connect(**DB_CONFIG)
    df = pd.read_sql("SELECT * FROM gold.metricas_productos", conn)

    print(f"\n[1] Datos cargados: {len(df)} productos")

    # Preparar features
    df['target_devolucion_alta'] = (df['tasa_devolucion'] > 10).astype(int)

    categoria_map = {cat: i for i, cat in enumerate(df['categoria'].unique())}
    df['categoria_encoded'] = df['categoria'].map(categoria_map)

    df['log_cantidad_vendida'] = np.log1p(df['cantidad_vendida'])
    df['log_total_ventas'] = np.log1p(df['total_ventas'])
    df['margen_producto'] = np.where(
        df['costo_unitario'] > 0,
        ((df['precio_unitario'] - df['costo_unitario']) / df['precio_unitario']) * 100,
        0
    )

    features = ['categoria_encoded', 'log_cantidad_vendida', 'log_total_ventas',
                'rentabilidad_porcentual', 'n_agencias_venta', 'es_producto_nuevo']

    X = df[features].fillna(0)
    y = df['target_devolucion_alta']

    print(f"\n[2] Features: {features}")
    print(f"    Target positivo: {y.sum()} ({y.mean()*100:.1f}%)")

    # Entrenar modelo
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42)

    model = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42, class_weight='balanced')
    model.fit(X_train, y_train)

    # Evaluar
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1] if len(model.classes_) > 1 else np.zeros(len(y_test))

    print(f"\n[3] Evaluacion del modelo:")
    print(classification_report(y_test, y_pred, target_names=['Normal', 'Alto Riesgo']))

    if len(np.unique(y_test)) > 1 and len(model.classes_) > 1:
        auc = roc_auc_score(y_test, y_prob)
        print(f"    AUC-ROC: {auc:.4f}")

    # Predecir para todos los productos
    df['prob_devolucion_alta'] = model.predict_proba(X)[:, 1] if len(model.classes_) > 1 else 0
    df['prediccion_devolucion'] = model.predict(X)
    df['nivel_riesgo'] = df['prob_devolucion_alta'].apply(
        lambda x: 'ALTO' if x >= 0.6 else ('MEDIO' if x >= 0.3 else 'BAJO')
    )

    print(f"\n[4] PRODUCTOS DE ALTO RIESGO:")
    alto_riesgo = df[df['nivel_riesgo'] == 'ALTO'].sort_values('prob_devolucion_alta', ascending=False)
    for _, row in alto_riesgo.iterrows():
        print(f"    - {row['producto']}: {row['prob_devolucion_alta']*100:.1f}% probabilidad")
        print(f"      Tasa actual: {row['tasa_devolucion']:.1f}% | Motivo: {row['motivo_devolucion_principal']}")

    # Guardar en PostgreSQL
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS gold.predicciones_devolucion CASCADE;")
    cur.execute("""
        CREATE TABLE gold.predicciones_devolucion (
            id SERIAL PRIMARY KEY,
            codigo_producto VARCHAR(20),
            producto VARCHAR(100),
            categoria VARCHAR(50),
            tasa_devolucion_actual NUMERIC(8,2),
            prob_devolucion_alta NUMERIC(8,4),
            nivel_riesgo VARCHAR(20),
            motivo_principal VARCHAR(50),
            recomendacion VARCHAR(200),
            fecha_calculo TIMESTAMP DEFAULT NOW()
        );
    """)

    # Agregar recomendaciones
    def generar_recomendacion(row):
        if row['nivel_riesgo'] == 'ALTO':
            return f"URGENTE: Revisar calidad y proceso de {row['categoria']}"
        elif row['nivel_riesgo'] == 'MEDIO':
            return f"Monitorear: Posible problema de {row['motivo_devolucion_principal']}"
        else:
            return "Sin accion requerida"

    df['recomendacion'] = df.apply(generar_recomendacion, axis=1)

    cols = ['codigo_producto', 'producto', 'categoria', 'tasa_devolucion',
            'prob_devolucion_alta', 'nivel_riesgo', 'motivo_devolucion_principal', 'recomendacion']
    data = [tuple(x) + (datetime.now(),) for x in df[cols].values]

    execute_values(cur, f"""
        INSERT INTO gold.predicciones_devolucion
        (codigo_producto, producto, categoria, tasa_devolucion_actual,
         prob_devolucion_alta, nivel_riesgo, motivo_principal, recomendacion, fecha_calculo)
        VALUES %s
    """, data)

    conn.commit()
    conn.close()

    print(f"\n[OK] Predicciones guardadas en gold.predicciones_devolucion")
    return len(alto_riesgo)


def main():
    print("="*70)
    print("EJECUTANDO PIPELINES DE DATA MINING - CONDIMENSA")
    print("="*70)

    # Ejecutar cada pipeline
    n_reglas = ejecutar_apriori()
    n_anomalias = ejecutar_isolation_forest()
    n_alto_riesgo = ejecutar_random_forest()

    # Resumen final
    print("\n" + "="*70)
    print("RESUMEN DE EJECUCION")
    print("="*70)

    print(f"""
PREGUNTA 1: ¿Que productos se venden juntos?
  Algoritmo: Apriori (Reglas de Asociacion)
  Resultado: {n_reglas} reglas de cross-selling
  Tabla: gold.reglas_asociacion
  Accion: Crear combos y promociones con productos asociados

PREGUNTA 2: ¿Que agencias tienen comportamiento anomalo?
  Algoritmo: Isolation Forest
  Resultado: {n_anomalias} agencias anomalas detectadas
  Tabla: gold.anomalias_agencias
  Accion: Investigar agencias con desviaciones significativas

PREGUNTA 3: ¿Que productos tienen alto riesgo de devolucion?
  Algoritmo: Random Forest
  Resultado: {n_alto_riesgo} productos de alto riesgo
  Tabla: gold.predicciones_devolucion
  Accion: Revisar calidad y procesos de productos criticos
""")

    print("="*70)
    print("EJECUCION COMPLETADA")
    print("="*70)


if __name__ == "__main__":
    main()
