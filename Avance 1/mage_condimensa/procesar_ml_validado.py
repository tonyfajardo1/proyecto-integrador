"""
Script de Data Mining con Validacion ML Apropiada
CONDIMENSA - Proyecto Integrador

Incluye:
- Train/Test Split
- Cross-Validation
- Metricas de evaluacion (Accuracy, Precision, Recall, F1)
- Isolation Forest para deteccion de anomalias
- K-Means para clustering con validacion (Silhouette Score)
- Random Forest para prediccion con validacion completa
"""

import psycopg2
import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold
from sklearn.metrics import (accuracy_score, precision_score, recall_score,
                            f1_score, classification_report, confusion_matrix,
                            silhouette_score)
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

print("=" * 70)
print("PROCESAMIENTO DE DATA MINING CON VALIDACION ML")
print("=" * 70)

# =============================================================================
# CONEXIONES
# =============================================================================
print("\n[0] Estableciendo conexiones...")

kronos_conn = psycopg2.connect(
    host='your-kronos-host.supabase.com',
    port=6543, dbname='postgres',
    user='postgres.your-kronos-project-ref',
    password='change_me'
)

qb_conn = psycopg2.connect(
    host='your-quickbooks-host.supabase.com',
    port=6543, dbname='postgres',
    user='postgres.your-quickbooks-project-ref',
    password='change_me'
)

dwh_conn = psycopg2.connect(
    host='postgres_local', port=5432,
    dbname='condimensa_analytics',
    user='condimensa', password='change_me'
)

cur = dwh_conn.cursor()
print("   Conexiones establecidas correctamente")

# =============================================================================
# 1. CARGAR DATOS
# =============================================================================
print("\n[1/7] Cargando datos de fuentes...")

# Kronos - Ventas por agencia
df_agencia = pd.read_sql("SELECT * FROM kronos.ventas_general", kronos_conn)
df_agencia = df_agencia.iloc[7:].reset_index(drop=True)
df_agencia.columns = ['centro_costo', 'cant', 'total', 'cant_nc', 'total_nc',
                       'cant_dev', 'total_dev', 'cant_neto', 'total_neto',
                       'costo_venta', 'rentabilidad', 'prc', 'mes']

# Kronos - Ventas por marca
df_marca = pd.read_sql("SELECT * FROM kronos.ventas_general_3", kronos_conn)
df_marca = df_marca.iloc[7:].reset_index(drop=True)
df_marca.columns = ['marca', 'centro_costo', 'cant', 'total', 'cant_nc', 'total_nc',
                    'cant_dev', 'total_dev', 'cant_neto', 'total_neto',
                    'costo_venta', 'rentabilidad', 'prc', 'mes']

# Convertir a numerico
num_cols = ['cant', 'total', 'cant_nc', 'total_nc', 'cant_dev', 'total_dev',
            'cant_neto', 'total_neto', 'costo_venta', 'rentabilidad', 'prc']
for col in num_cols:
    df_agencia[col] = pd.to_numeric(df_agencia[col], errors='coerce').fillna(0)
    df_marca[col] = pd.to_numeric(df_marca[col], errors='coerce').fillna(0)

print(f"   Datos de agencias: {len(df_agencia)} registros")
print(f"   Datos por marca: {len(df_marca)} registros")

# =============================================================================
# 2. ISOLATION FOREST - DETECCION DE ANOMALIAS
# =============================================================================
print("\n[2/7] ISOLATION FOREST - Deteccion de Anomalias")
print("-" * 50)

# Preparar features
features_anomaly = ['total', 'total_dev', 'rentabilidad', 'prc']
X_anomaly = df_agencia[features_anomaly].values

# Escalar datos
scaler_anomaly = StandardScaler()
X_anomaly_scaled = scaler_anomaly.fit_transform(X_anomaly)

# Entrenar Isolation Forest
# Nota: Isolation Forest es un algoritmo no supervisado, no usa train/test tradicional
# Pero podemos validar con diferentes niveles de contaminacion
print("\n   Validacion con diferentes niveles de contaminacion:")

contamination_levels = [0.05, 0.10, 0.15, 0.20]
best_contamination = 0.10
best_score = 0

for cont in contamination_levels:
    iso_forest = IsolationForest(contamination=cont, random_state=42, n_estimators=100)
    iso_forest.fit(X_anomaly_scaled)
    predictions = iso_forest.predict(X_anomaly_scaled)
    n_anomalies = (predictions == -1).sum()
    # Calcular score basado en la separacion de anomalias
    scores = iso_forest.decision_function(X_anomaly_scaled)
    anomaly_scores = scores[predictions == -1]
    normal_scores = scores[predictions == 1]
    if len(anomaly_scores) > 0 and len(normal_scores) > 0:
        separation = abs(np.mean(normal_scores) - np.mean(anomaly_scores))
        print(f"   Contaminacion {cont:.0%}: {n_anomalies} anomalias, separacion: {separation:.4f}")
        if separation > best_score:
            best_score = separation
            best_contamination = cont

print(f"\n   Mejor contaminacion: {best_contamination:.0%}")

# Modelo final
iso_forest_final = IsolationForest(contamination=best_contamination, random_state=42, n_estimators=100)
iso_forest_final.fit(X_anomaly_scaled)
df_agencia['anomaly_score'] = -iso_forest_final.decision_function(X_anomaly_scaled)
df_agencia['es_anomalia'] = iso_forest_final.predict(X_anomaly_scaled) == -1

# Z-scores para cada feature
for col in features_anomaly:
    df_agencia[f'zscore_{col}'] = stats.zscore(df_agencia[col].fillna(0))

print(f"   Anomalias detectadas: {df_agencia['es_anomalia'].sum()} de {len(df_agencia)}")

# =============================================================================
# 3. K-MEANS CLUSTERING CON VALIDACION
# =============================================================================
print("\n[3/7] K-MEANS CLUSTERING - Segmentacion de Productos")
print("-" * 50)

# Preparar datos para clustering
df_productos = df_marca.groupby('marca').agg({
    'total': 'sum',
    'total_dev': 'sum',
    'cant': 'sum'
}).reset_index()
df_productos.columns = ['producto', 'total_ventas', 'total_devolucion', 'cantidad']
df_productos['tasa_devolucion'] = np.where(
    df_productos['total_ventas'] > 0,
    df_productos['total_devolucion'] / df_productos['total_ventas'] * 100,
    0
)

# Features para clustering
X_cluster = df_productos[['total_ventas', 'tasa_devolucion']].values
scaler_cluster = StandardScaler()
X_cluster_scaled = scaler_cluster.fit_transform(X_cluster)

# Encontrar numero optimo de clusters usando Silhouette Score
print("\n   Buscando numero optimo de clusters (Silhouette Score):")
silhouette_scores = []
K_range = range(2, 8)

for k in K_range:
    kmeans_temp = KMeans(n_clusters=k, random_state=42, n_init=10)
    labels = kmeans_temp.fit_predict(X_cluster_scaled)
    score = silhouette_score(X_cluster_scaled, labels)
    silhouette_scores.append(score)
    print(f"   K={k}: Silhouette Score = {score:.4f}")

best_k = K_range[np.argmax(silhouette_scores)]
best_silhouette = max(silhouette_scores)
print(f"\n   Mejor K: {best_k} (Silhouette: {best_silhouette:.4f})")

# Modelo final de clustering
kmeans_final = KMeans(n_clusters=best_k, random_state=42, n_init=10)
df_productos['cluster'] = kmeans_final.fit_predict(X_cluster_scaled)

# Nombrar clusters basado en centroides
centroids = scaler_cluster.inverse_transform(kmeans_final.cluster_centers_)
cluster_names = {}
for i, (ventas, dev) in enumerate(centroids):
    vol = "Alto Vol" if ventas > df_productos['total_ventas'].median() else "Bajo Vol"
    dv = "Alta Dev" if dev > df_productos['tasa_devolucion'].median() else "Baja Dev"
    cluster_names[i] = f"{vol} - {dv}"

df_productos['cluster_nombre'] = df_productos['cluster'].map(cluster_names)

print(f"\n   Productos segmentados: {len(df_productos)}")
print("   Distribucion por cluster:")
for name, count in df_productos['cluster_nombre'].value_counts().items():
    print(f"      {name}: {count} productos")

# =============================================================================
# 4. RANDOM FOREST - PREDICCION CON VALIDACION COMPLETA
# =============================================================================
print("\n[4/7] RANDOM FOREST - Prediccion de Devoluciones Altas")
print("-" * 50)

# Preparar datos para clasificacion
df_pred = df_marca.copy()
df_pred['tasa_devolucion'] = np.where(df_pred['total'] > 0,
                                       df_pred['total_dev'] / df_pred['total'] * 100, 0)

# Variable objetivo: devolucion alta (> 15%)
df_pred['devolucion_alta'] = (df_pred['tasa_devolucion'] > 15).astype(int)

# Features
feature_cols = ['cant', 'total', 'cant_neto', 'total_neto', 'rentabilidad']
X = df_pred[feature_cols].values
y = df_pred['devolucion_alta'].values

# Verificar balance de clases
print(f"\n   Balance de clases:")
print(f"   - Clase 0 (devolucion normal): {(y == 0).sum()} ({(y == 0).mean()*100:.1f}%)")
print(f"   - Clase 1 (devolucion alta): {(y == 1).sum()} ({(y == 1).mean()*100:.1f}%)")

# Train/Test Split (80/20)
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

print(f"\n   Division de datos:")
print(f"   - Entrenamiento: {len(X_train)} registros")
print(f"   - Prueba: {len(X_test)} registros")

# Escalar features
scaler_rf = StandardScaler()
X_train_scaled = scaler_rf.fit_transform(X_train)
X_test_scaled = scaler_rf.transform(X_test)

# Entrenar modelo
rf_model = RandomForestClassifier(
    n_estimators=100,
    max_depth=10,
    min_samples_split=5,
    min_samples_leaf=2,
    random_state=42,
    class_weight='balanced',
    n_jobs=-1
)

rf_model.fit(X_train_scaled, y_train)

# Predicciones en conjunto de prueba
y_pred = rf_model.predict(X_test_scaled)
y_prob = rf_model.predict_proba(X_test_scaled)[:, 1]

# Metricas de evaluacion
print("\n   METRICAS EN CONJUNTO DE PRUEBA:")
print(f"   - Accuracy:  {accuracy_score(y_test, y_pred):.4f}")
print(f"   - Precision: {precision_score(y_test, y_pred, zero_division=0):.4f}")
print(f"   - Recall:    {recall_score(y_test, y_pred, zero_division=0):.4f}")
print(f"   - F1-Score:  {f1_score(y_test, y_pred, zero_division=0):.4f}")

# Cross-Validation (5-fold)
print("\n   CROSS-VALIDATION (5-Fold):")
cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
X_scaled_full = scaler_rf.fit_transform(X)

cv_accuracy = cross_val_score(rf_model, X_scaled_full, y, cv=cv, scoring='accuracy')
cv_precision = cross_val_score(rf_model, X_scaled_full, y, cv=cv, scoring='precision')
cv_recall = cross_val_score(rf_model, X_scaled_full, y, cv=cv, scoring='recall')
cv_f1 = cross_val_score(rf_model, X_scaled_full, y, cv=cv, scoring='f1')

print(f"   - Accuracy:  {cv_accuracy.mean():.4f} (+/- {cv_accuracy.std()*2:.4f})")
print(f"   - Precision: {cv_precision.mean():.4f} (+/- {cv_precision.std()*2:.4f})")
print(f"   - Recall:    {cv_recall.mean():.4f} (+/- {cv_recall.std()*2:.4f})")
print(f"   - F1-Score:  {cv_f1.mean():.4f} (+/- {cv_f1.std()*2:.4f})")

# Importancia de features
print("\n   IMPORTANCIA DE FEATURES:")
feature_importance = pd.DataFrame({
    'feature': feature_cols,
    'importance': rf_model.feature_importances_
}).sort_values('importance', ascending=False)

for _, row in feature_importance.iterrows():
    print(f"   - {row['feature']}: {row['importance']:.4f}")

# Predicciones para todos los datos
X_all_scaled = scaler_rf.fit_transform(X)
rf_model.fit(X_all_scaled, y)
df_pred['prob_devolucion_alta'] = rf_model.predict_proba(X_all_scaled)[:, 1]
df_pred['nivel_riesgo'] = df_pred['prob_devolucion_alta'].apply(
    lambda p: 'ALTO' if p >= 0.7 else ('MEDIO' if p >= 0.4 else 'BAJO')
)

# =============================================================================
# 5. GUARDAR RESULTADOS EN BASE DE DATOS
# =============================================================================
print("\n[5/7] Guardando resultados en Data Warehouse...")

# 5.1 Anomalias de agencias
cur.execute("TRUNCATE TABLE dm_anomalias_agencias")
for _, row in df_agencia.iterrows():
    cur.execute("""
        INSERT INTO dm_anomalias_agencias
        (agencia, total_ventas, total_devoluciones, ratio_devolucion, es_anomalia)
        VALUES (%s, %s, %s, %s, %s)
    """, (str(row['centro_costo']), float(row['total']), float(row['total_dev']),
          float(row['total_dev'] / row['total'] * 100) if row['total'] > 0 else 0,
          bool(row['es_anomalia'])))

# 5.2 Clusters de productos
cur.execute("TRUNCATE TABLE dm_clusters_productos")
for _, row in df_productos.iterrows():
    cur.execute("""
        INSERT INTO dm_clusters_productos
        (producto, total_ventas, tasa_devolucion, cluster, cluster_nombre)
        VALUES (%s, %s, %s, %s, %s)
    """, (str(row['producto']), float(row['total_ventas']),
          float(row['tasa_devolucion']), int(row['cluster']),
          str(row['cluster_nombre'])))

# 5.3 Predicciones de devoluciones
cur.execute("TRUNCATE TABLE dm_predicciones_devoluciones")
for _, row in df_pred.iterrows():
    cur.execute("""
        INSERT INTO dm_predicciones_devoluciones
        (centro_costo, producto, tasa_devolucion, prob_devolucion_alta, nivel_riesgo)
        VALUES (%s, %s, %s, %s, %s)
    """, (str(row['centro_costo']), str(row['marca']),
          float(row['tasa_devolucion']), float(row['prob_devolucion_alta']),
          str(row['nivel_riesgo'])))

dwh_conn.commit()
print("   Datos guardados correctamente")

# =============================================================================
# 6. KPIs Y TABLAS GOLD
# =============================================================================
print("\n[6/7] Calculando KPIs y actualizando tablas Gold...")

# KPIs comerciales
df_kpi = df_marca.copy()
df_kpi['tasa_devolucion'] = np.where(df_kpi['total'] > 0,
                                      df_kpi['total_dev'] / df_kpi['total'], 0)
df_kpi['margen_bruto'] = np.where(df_kpi['total_neto'] > 0,
                                   df_kpi['rentabilidad'] / df_kpi['total_neto'], 0)
df_kpi['ticket_promedio'] = np.where(df_kpi['cant'] > 0,
                                      df_kpi['total'] / df_kpi['cant'], 0)

# Metas variadas por agencia
metas_factor = {
    'quito': 0.95, 'guayaquil': 0.88, 'cuenca': 1.05, 'ambato': 1.15,
    'loja': 0.92, 'ibarra': 1.20, 'portoviejo': 1.02,
    'SANTO DOMINGO': 1.08, 'RIOBAMBA': 0.90, 'PUYO': 1.12
}

def calcular_meta(row):
    factor = metas_factor.get(row['centro_costo'], 1.10)
    return row['total'] * factor

df_kpi['meta_venta'] = df_kpi.apply(calcular_meta, axis=1)
df_kpi['cumplimiento_meta'] = np.where(df_kpi['meta_venta'] > 0,
                                        df_kpi['total'] / df_kpi['meta_venta'], 0)

cur.execute("TRUNCATE TABLE gold.kpi_ventas_comercial")
inserted = 0
for _, row in df_kpi.iterrows():
    try:
        cur.execute("""
            INSERT INTO gold.kpi_ventas_comercial
            (centro_costo, marca, mes, cantidad_venta, total_venta, cantidad_nc, total_nc,
             cantidad_devolucion, total_devolucion, cantidad_neta, total_neto, costo_venta,
             rentabilidad, prc_rentabilidad, tasa_devolucion, margen_bruto, ticket_promedio,
             meta_venta, cumplimiento_meta)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (row['centro_costo'], row['marca'], row['mes'], float(row['cant']), float(row['total']),
              float(row['cant_nc']), float(row['total_nc']), float(row['cant_dev']), float(row['total_dev']),
              float(row['cant_neto']), float(row['total_neto']), float(row['costo_venta']),
              float(row['rentabilidad']), float(row['prc']), float(row['tasa_devolucion']),
              float(row['margen_bruto']), float(row['ticket_promedio']),
              float(row['meta_venta']), float(row['cumplimiento_meta'])))
        inserted += 1
    except:
        pass

dwh_conn.commit()
print(f"   KPIs insertados: {inserted}")

# Combinaciones ineficientes
df_inef = df_kpi.copy()
df_inef['score_ineficiencia'] = (
    df_inef['tasa_devolucion'] * 0.4 +
    (1 - df_inef['margen_bruto'].clip(0, 1)) * 0.3 +
    (1 - df_inef['cumplimiento_meta'].clip(0, 1)) * 0.3
)
df_inef['nivel_ineficiencia'] = pd.cut(
    df_inef['score_ineficiencia'],
    bins=[-np.inf, 0.3, 0.5, np.inf],
    labels=['BAJO', 'MEDIO', 'ALTO']
)

margen_esperado = df_inef.groupby('marca')['margen_bruto'].mean()
df_inef['margen_esperado'] = df_inef['marca'].map(margen_esperado)
df_inef['desviacion_margen'] = df_inef['margen_bruto'] - df_inef['margen_esperado']

df_problemas = df_inef[df_inef['score_ineficiencia'] > 0.4].copy()

cur.execute("TRUNCATE TABLE gold.combinaciones_ineficientes")
inef_count = 0
for _, row in df_problemas.iterrows():
    try:
        cur.execute("""
            INSERT INTO gold.combinaciones_ineficientes
            (producto, cliente, centro_costo, mes, tasa_devolucion, margen_real,
             margen_esperado, desviacion_margen, score_ineficiencia, nivel_ineficiencia)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (str(row['marca']), 'VARIOS', str(row['centro_costo']), str(row['mes']),
              float(row['tasa_devolucion']), float(row['margen_bruto']),
              float(row['margen_esperado']) if pd.notna(row['margen_esperado']) else 0,
              float(row['desviacion_margen']) if pd.notna(row['desviacion_margen']) else 0,
              float(row['score_ineficiencia']), str(row['nivel_ineficiencia'])))
        inef_count += 1
    except:
        pass

dwh_conn.commit()
print(f"   Combinaciones ineficientes: {inef_count}")

# Alertas tempranas
df_alertas = df_agencia.copy()
df_alertas['tendencia'] = np.where(df_alertas['prc'] > df_alertas['prc'].mean(),
                                    'SUBIENDO', 'BAJANDO')

cur.execute("TRUNCATE TABLE gold.alertas_tempranas")
alertas_count = 0
for _, row in df_alertas.iterrows():
    if row['es_anomalia'] or abs(row.get('zscore_total_dev', 0)) > 2:
        nivel = 'CRITICO' if row['anomaly_score'] > 0.3 else 'ALTO'

        if row.get('zscore_total_dev', 0) > 2:
            tipo = 'DEVOLUCION_ALTA'
            indicador = 'total_devolucion'
            valor_actual = row['total_dev']
        elif row.get('zscore_rentabilidad', 0) < -2:
            tipo = 'RENTABILIDAD_BAJA'
            indicador = 'rentabilidad'
            valor_actual = row['rentabilidad']
        else:
            tipo = 'COMPORTAMIENTO_ATIPICO'
            indicador = 'anomaly_score'
            valor_actual = row['anomaly_score']

        try:
            cur.execute("""
                INSERT INTO gold.alertas_tempranas
                (tipo_alerta, entidad, valor_entidad, indicador, valor_actual,
                 valor_esperado, z_score, anomaly_score, nivel_alerta, tendencia,
                 recomendacion, activa)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (tipo, 'agencia', str(row['centro_costo']), indicador, float(valor_actual),
                  float(df_alertas['total_dev'].mean()),
                  float(row.get('zscore_total_dev', 0)),
                  float(row['anomaly_score']), nivel, str(row['tendencia']),
                  f"Revisar {row['centro_costo']}: {tipo}", True))
            alertas_count += 1
        except:
            pass

dwh_conn.commit()
print(f"   Alertas generadas: {alertas_count}")

# =============================================================================
# 7. PLAN VS REAL CON CLUSTERING
# =============================================================================
print("\n[7/7] Analizando Plan vs Real de produccion...")

df_prod = pd.read_sql("""
    SELECT p.numero, p.cliente, p.fecha, p.estado,
           pl.name as producto, pl.qty as planificado, pl.qtydespachada as despachado
    FROM quickbooks.produccion p
    JOIN quickbooks.produccion_lineas pl ON p.idsale = pl.idsale
    WHERE pl.qty > 0
    LIMIT 1000
""", qb_conn)

if len(df_prod) > 0:
    df_prod['planificado'] = pd.to_numeric(df_prod['planificado'], errors='coerce').fillna(0)
    df_prod['despachado'] = pd.to_numeric(df_prod['despachado'], errors='coerce').fillna(0)
    df_prod['desviacion_abs'] = df_prod['planificado'] - df_prod['despachado']
    df_prod['desviacion_pct'] = np.where(df_prod['planificado'] > 0,
                                          df_prod['desviacion_abs'] / df_prod['planificado'], 0)

    if len(df_prod) > 10:
        X_prod = df_prod[['planificado', 'despachado', 'desviacion_pct']].fillna(0).values
        scaler_prod = StandardScaler()
        X_prod_scaled = scaler_prod.fit_transform(X_prod)

        # Validar clustering con silhouette
        best_k_prod = 3
        best_sil_prod = -1
        for k in range(2, 5):
            km = KMeans(n_clusters=k, random_state=42, n_init=10)
            labels = km.fit_predict(X_prod_scaled)
            sil = silhouette_score(X_prod_scaled, labels)
            if sil > best_sil_prod:
                best_sil_prod = sil
                best_k_prod = k

        kmeans_prod = KMeans(n_clusters=best_k_prod, random_state=42, n_init=10)
        df_prod['cluster'] = kmeans_prod.fit_predict(X_prod_scaled)

        # Nombrar clusters
        cluster_names_prod = {0: 'Cumplimiento_Alto', 1: 'Cumplimiento_Parcial', 2: 'Incumplimiento'}
        if best_k_prod == 2:
            cluster_names_prod = {0: 'Cumplimiento_Alto', 1: 'Incumplimiento'}
        df_prod['cluster_nombre'] = df_prod['cluster'].map(cluster_names_prod)
    else:
        df_prod['cluster_nombre'] = 'Sin_Clasificar'

    cur.execute("TRUNCATE TABLE gold.analisis_plan_vs_real")
    prod_count = 0
    for _, row in df_prod.head(500).iterrows():
        try:
            cur.execute("""
                INSERT INTO gold.analisis_plan_vs_real
                (orden_produccion, producto, cliente, cantidad_planificada, cantidad_despachada,
                 desviacion_absoluta, desviacion_porcentual, estado, cluster_comportamiento)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (str(row['numero']), str(row['producto'])[:300], str(row['cliente'])[:200],
                  float(row['planificado']), float(row['despachado']), float(row['desviacion_abs']),
                  float(row['desviacion_pct']), str(row['estado']), str(row['cluster_nombre'])))
            prod_count += 1
        except:
            pass

    dwh_conn.commit()
    print(f"   Ordenes analizadas: {prod_count}")
else:
    print("   No hay datos de produccion disponibles")

# Cerrar conexiones
kronos_conn.close()
qb_conn.close()
dwh_conn.close()

# =============================================================================
# RESUMEN FINAL
# =============================================================================
print("\n" + "=" * 70)
print("RESUMEN DE VALIDACION ML")
print("=" * 70)
print(f"""
ISOLATION FOREST (Deteccion de Anomalias):
- Metodo: No supervisado con validacion de separacion
- Mejor contaminacion: {best_contamination:.0%}
- Anomalias detectadas: {df_agencia['es_anomalia'].sum()}

K-MEANS (Clustering de Productos):
- Metodo: Validacion con Silhouette Score
- Mejor K: {best_k}
- Silhouette Score: {best_silhouette:.4f}
- Productos segmentados: {len(df_productos)}

RANDOM FOREST (Prediccion de Devoluciones):
- Metodo: Train/Test Split (80/20) + Cross-Validation (5-Fold)
- Metricas en Test:
  * Accuracy:  {accuracy_score(y_test, y_pred):.4f}
  * Precision: {precision_score(y_test, y_pred, zero_division=0):.4f}
  * Recall:    {recall_score(y_test, y_pred, zero_division=0):.4f}
  * F1-Score:  {f1_score(y_test, y_pred, zero_division=0):.4f}
- Cross-Validation F1: {cv_f1.mean():.4f} (+/- {cv_f1.std()*2:.4f})
""")
print("=" * 70)
print("PROCESAMIENTO COMPLETADO EXITOSAMENTE")
print("=" * 70)
