"""
Transformer: Clustering K-Means para productos
Pipeline: dm_clustering_productos
Segmenta productos en grupos por comportamiento.
Guarda resultados en gold.clusters_productos.
"""
import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score

if 'transformer' not in dir():
    from mage_ai.data_preparation.decorators import transformer
if 'test' not in dir():
    from mage_ai.data_preparation.decorators import test


@transformer
def clustering_productos(data, *args, **kwargs):
    """
    Aplica K-Means para segmentar productos.
    Usa gold.metricas_productos como entrada.
    """
    df = data.copy()
    pipeline_id = kwargs.get('pipeline_id', 'dm_clustering_productos')

    # =========================================================================
    # 1. SELECCIONAR FEATURES PARA CLUSTERING
    # =========================================================================

    features = ['tasa_devolucion', 'margen_rentabilidad', 'ticket_promedio', 'penetracion']
    
    # Mapear nombres de columnas
    col_mapping = {
        'rentabilidad_promedio': 'margen_rentabilidad'
    }
    for old, new in col_mapping.items():
        if old in df.columns and new not in df.columns:
            df[new] = df[old]
    
    # Usar columnas disponibles
    available_features = [c for c in features if c in df.columns]
    if not available_features:
        available_features = ['tasa_devolucion', 'rentabilidad_promedio', 'ticket_promedio', 'penetracion']
        available_features = [c for c in available_features if c in df.columns]
    
    X = df[available_features].copy()
    
    # Manejar infinitos y NaN
    X = X.replace([np.inf, -np.inf], np.nan).fillna(0)

    # =========================================================================
    # 2. ESCALAR DATOS
    # =========================================================================

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    print(f"\n{'='*70}")
    print(f"CLUSTERING DE PRODUCTOS - K-MEANS")
    print(f"{'='*70}")
    print(f"Productos a segmentar: {len(df)}")
    print(f"Features: {available_features}")

    # =========================================================================
    # 3. ENCONTRAR NUMERO OPTIMO DE CLUSTERS
    # =========================================================================

    silhouette_scores = []
    K_range = range(2, min(8, len(df)))

    for k in K_range:
        kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = kmeans.fit_predict(X_scaled)
        silhouette_scores.append(silhouette_score(X_scaled, labels))

    best_k = K_range[np.argmax(silhouette_scores)]
    print(f"Mejor K: {best_k} (silhouette: {max(silhouette_scores):.3f})")

    # =========================================================================
    # 4. APLICAR K-MEANS CON K OPTIMO
    # =========================================================================

    kmeans_final = KMeans(n_clusters=best_k, random_state=42, n_init=10)
    df['cluster'] = kmeans_final.fit_predict(X_scaled)
    df['silhouette_score'] = max(silhouette_scores)

    # =========================================================================
    # 5. ANALIZAR Y NOMBRAR CLUSTERS
    # =========================================================================

    cluster_profiles = df.groupby('cluster')[available_features + ['total_ventas']].agg({
        **{f: 'mean' for f in available_features},
        'total_ventas': 'sum'
    }).round(2)

    # Asignar nombres descriptivos
    cluster_names = {}
    for cluster_id in range(best_k):
        profile = cluster_profiles.loc[cluster_id]
        
        tasa_dev = profile.get('tasa_devolucion', 0)
        margen = profile.get('margen_rentabilidad', profile.get('margen_rentabilidad', 0))
        penetracion = profile.get('penetracion', 0)
        ventas = profile.get('total_ventas', 0)
        
        if tasa_dev > 15:
            name = 'PROBLEMATICOS'
        elif margen > 40 and tasa_dev < 5:
            name = 'ESTRELLA'
        elif penetracion > 80:
            name = 'COMMODITIES'
        elif ventas < cluster_profiles['total_ventas'].median():
            name = 'NICHO'
        else:
            name = 'REGULARES'
        
        cluster_names[cluster_id] = name

    df['cluster_nombre'] = df['cluster'].map(cluster_names)

    # =========================================================================
    # 6. PREPARAR OUTPUT
    # =========================================================================

    df['pipeline_id'] = pipeline_id
    df['n_clusters'] = best_k

    # =========================================================================
    # 7. IMPRIMIR RESULTADOS
    # =========================================================================

    print(f"\n[RESULTADOS]")
    for cluster_id in range(best_k):
        name = cluster_names[cluster_id]
        profile = cluster_profiles.loc[cluster_id]
        count = (df['cluster'] == cluster_id).sum()
        
        print(f"\n    CLUSTER {cluster_id}: {name}")
        print(f"    Productos: {count}")
        print(f"    Tasa devolucion: {profile.get('tasa_devolucion', 'N/A'):.2f}%")
        print(f"    Margen rentabilidad: {profile.get('margen_rentabilidad', 'N/A'):.2f}%")

    print(f"\n{'='*70}")

    return df


@test
def test_output(output, *args) -> None:
    assert output is not None, 'Transformacion fallo'
    assert 'cluster' in output.columns, 'Falta cluster'
    assert 'cluster_nombre' in output.columns, 'Falta nombre de cluster'
    print(f"OK: {output['cluster'].nunique()} clusters generados")
