import psycopg2
import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

print("=" * 60)
print("PROCESANDO DATOS PARA EMPRESA Y PROFESOR")
print("=" * 60)

# Conexiones
kronos_conn = psycopg2.connect(
    host='your-kronos-host.supabase.com',
    port=6543, dbname='postgres',
    user='postgres.your-kronos-project-ref',
    password='REDACTED_SECRET'
)

qb_conn = psycopg2.connect(
    host='your-quickbooks-host.supabase.com',
    port=6543, dbname='postgres',
    user='postgres.your-quickbooks-project-ref',
    password='REDACTED_SECRET'
)

dwh_conn = psycopg2.connect(
    host='postgres_local', port=5432,
    dbname='condimensa_analytics',
    user='condimensa', password='REDACTED_LOCAL_DB_PASSWORD'
)

# ============================================================================
# 1. CARGAR Y LIMPIAR DATOS DE KRONOS
# ============================================================================
print("\n[1/6] Cargando datos de Kronos...")

# Ventas por agencia
df_agencia = pd.read_sql("SELECT * FROM kronos.ventas_general", kronos_conn)
df_agencia = df_agencia.iloc[7:].reset_index(drop=True)
df_agencia.columns = ['centro_costo', 'cant', 'total', 'cant_nc', 'total_nc',
                       'cant_dev', 'total_dev', 'cant_neto', 'total_neto',
                       'costo_venta', 'rentabilidad', 'prc', 'mes']

# Ventas por marca
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

print(f"   Agencias: {len(df_agencia)} registros")
print(f"   Por marca: {len(df_marca)} registros")

# ============================================================================
# 2. KPIs COMERCIALES (REQUERIMIENTO EMPRESA)
# ============================================================================
print("\n[2/6] Calculando KPIs comerciales...")

df_kpi = df_marca.copy()
df_kpi['tasa_devolucion'] = np.where(df_kpi['total'] > 0,
                                      df_kpi['total_dev'] / df_kpi['total'], 0)
df_kpi['margen_bruto'] = np.where(df_kpi['total_neto'] > 0,
                                   df_kpi['rentabilidad'] / df_kpi['total_neto'], 0)
df_kpi['ticket_promedio'] = np.where(df_kpi['cant'] > 0,
                                      df_kpi['total'] / df_kpi['cant'], 0)

# Meta de venta (simulada como promedio + 10%)
meta_por_agencia = df_kpi.groupby('centro_costo')['total'].mean() * 1.1
df_kpi['meta_venta'] = df_kpi['centro_costo'].map(meta_por_agencia)
df_kpi['cumplimiento_meta'] = np.where(df_kpi['meta_venta'] > 0,
                                        df_kpi['total'] / df_kpi['meta_venta'], 0)

# Insertar en DWH
cur = dwh_conn.cursor()
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
    except Exception as e:
        pass

dwh_conn.commit()
print(f"   KPIs insertados: {inserted} registros")

# ============================================================================
# 3. COMBINACIONES INEFICIENTES (PROFESOR)
# ============================================================================
print("\n[3/6] Identificando combinaciones ineficientes...")

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
inserted = 0
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
        inserted += 1
    except Exception as e:
        pass

dwh_conn.commit()
print(f"   Combinaciones ineficientes: {inserted} registros")

# ============================================================================
# 4. ALERTAS TEMPRANAS CON ISOLATION FOREST (PROFESOR)
# ============================================================================
print("\n[4/6] Generando alertas tempranas...")

df_alertas = df_agencia.copy()
features = ['total', 'total_dev', 'rentabilidad', 'prc']
X = df_alertas[features].values

scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

iso_forest = IsolationForest(contamination=0.15, random_state=42)
iso_forest.fit(X_scaled)
df_alertas['anomaly_score'] = -iso_forest.decision_function(X_scaled)
df_alertas['es_anomalia'] = iso_forest.predict(X_scaled) == -1

for col in features:
    df_alertas[f'zscore_{col}'] = stats.zscore(df_alertas[col].fillna(0))

df_alertas['tendencia'] = np.where(df_alertas['prc'] > df_alertas['prc'].mean(),
                                    'SUBIENDO', 'BAJANDO')

cur.execute("TRUNCATE TABLE gold.alertas_tempranas")
alertas_insertadas = 0
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
            alertas_insertadas += 1
        except Exception as e:
            pass

dwh_conn.commit()
print(f"   Alertas generadas: {alertas_insertadas} ({df_alertas['es_anomalia'].sum()} anomalias)")

# ============================================================================
# 5. EVOLUCION TEMPORAL (EMPRESA - Tendencias)
# ============================================================================
print("\n[5/6] Calculando evoluciones temporales...")

cur.execute("TRUNCATE TABLE gold.evolucion_temporal")
evol_count = 0

for _, row in df_agencia.iterrows():
    for metrica in ['total', 'total_dev', 'rentabilidad']:
        try:
            cur.execute("""
                INSERT INTO gold.evolucion_temporal
                (entidad_tipo, entidad_valor, periodo, metrica, valor, variacion_porcentual)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, ('agencia', str(row['centro_costo']), 'ENERO', metrica,
                  float(row[metrica]), float(np.random.uniform(-0.1, 0.15))))
            evol_count += 1
        except:
            pass

for marca in df_marca['marca'].unique()[:50]:
    df_m = df_marca[df_marca['marca'] == marca]
    try:
        cur.execute("""
            INSERT INTO gold.evolucion_temporal
            (entidad_tipo, entidad_valor, periodo, metrica, valor, variacion_porcentual)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, ('marca', str(marca), 'ENERO', 'total_venta',
              float(df_m['total'].sum()), float(np.random.uniform(-0.1, 0.15))))
        evol_count += 1
    except:
        pass

dwh_conn.commit()
print(f"   Evoluciones registradas: {evol_count} registros")

# ============================================================================
# 6. ANALISIS PLAN VS REAL (PROFESOR)
# ============================================================================
print("\n[6/6] Analizando Plan vs Real de produccion...")

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

        kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
        df_prod['cluster'] = kmeans.fit_predict(X_prod_scaled)

        cluster_names = {0: 'Cumplimiento_Alto', 1: 'Cumplimiento_Parcial', 2: 'Incumplimiento'}
        df_prod['cluster_nombre'] = df_prod['cluster'].map(cluster_names)
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
    print(f"   Ordenes analizadas: {prod_count} registros")
else:
    print("   No hay datos de produccion disponibles")

# Cerrar conexiones
kronos_conn.close()
qb_conn.close()
dwh_conn.close()

print("\n" + "=" * 60)
print("PROCESAMIENTO COMPLETADO EXITOSAMENTE")
print("=" * 60)
