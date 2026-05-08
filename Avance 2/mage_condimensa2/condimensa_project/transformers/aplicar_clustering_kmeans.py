"""
Transformer: Aplicar K-Means para segmentacion de productos
Pipeline: dm_clustering_segmentacion
Segmenta productos en grupos por comportamiento.
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
def aplicar_clustering(data, *args, **kwargs):
    """
    Aplica K-Means para segmentar productos.
    """
    df = data.copy()

    # =========================================================================
    # 1. SELECCIONAR FEATURES PARA CLUSTERING
    # =========================================================================

    features = ['tasa_devolucion', 'margen_rentabilidad', 'ticket_promedio', 'penetracion']
    X = df[features].copy()

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

    print(f"\n[1] DATOS")
    print(f"    Productos a segmentar: {len(df)}")
    print(f"    Features: {features}")

    # =========================================================================
    # 3. ENCONTRAR NUMERO OPTIMO DE CLUSTERS (Elbow + Silhouette)
    # =========================================================================

    print(f"\n[2] BUSCANDO NUMERO OPTIMO DE CLUSTERS...")

    silhouette_scores = []
    inertias = []
    K_range = range(2, min(8, len(df)))

    for k in K_range:
        kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = kmeans.fit_predict(X_scaled)
        silhouette_scores.append(silhouette_score(X_scaled, labels))
        inertias.append(kmeans.inertia_)

    # Elegir K con mejor silhouette score
    best_k = K_range[np.argmax(silhouette_scores)]
    print(f"    Silhouette scores: {dict(zip(K_range, [f'{s:.3f}' for s in silhouette_scores]))}")
    print(f"    Mejor K: {best_k} (silhouette: {max(silhouette_scores):.3f})")

    # =========================================================================
    # 4. APLICAR K-MEANS CON K OPTIMO
    # =========================================================================

    print(f"\n[3] APLICANDO K-MEANS CON K={best_k}")

    kmeans_final = KMeans(n_clusters=best_k, random_state=42, n_init=10)
    df['cluster'] = kmeans_final.fit_predict(X_scaled)

    # =========================================================================
    # 5. ANALIZAR CLUSTERS
    # =========================================================================

    print(f"\n[4] PERFIL DE CADA CLUSTER")
    print(f"    " + "-"*65)

    cluster_profiles = df.groupby('cluster')[features + ['total_ventas', 'producto']].agg({
        'tasa_devolucion': 'mean',
        'margen_rentabilidad': 'mean',
        'ticket_promedio': 'mean',
        'penetracion': 'mean',
        'total_ventas': 'sum',
        'producto': 'count'
    }).round(2)

    cluster_profiles.columns = ['Tasa_Dev_%', 'Margen_%', 'Ticket_Prom', 'Penetracion_%', 'Ventas_Total', 'Num_Productos']

    # Asignar nombres descriptivos a clusters
    cluster_names = {}
    for cluster_id in range(best_k):
        profile = cluster_profiles.loc[cluster_id]

        if profile['Tasa_Dev_%'] > 15:
            name = 'PROBLEMATICOS'
        elif profile['Margen_%'] > 40 and profile['Tasa_Dev_%'] < 5:
            name = 'ESTRELLA'
        elif profile['Penetracion_%'] > 80:
            name = 'COMMODITIES'
        elif profile['Ventas_Total'] < cluster_profiles['Ventas_Total'].median():
            name = 'NICHO'
        else:
            name = 'REGULARES'

        cluster_names[cluster_id] = name

    df['cluster_nombre'] = df['cluster'].map(cluster_names)

    # Imprimir perfiles
    for cluster_id in range(best_k):
        profile = cluster_profiles.loc[cluster_id]
        name = cluster_names[cluster_id]
        print(f"\n    CLUSTER {cluster_id}: {name}")
        print(f"    Productos: {profile['Num_Productos']:.0f}")
        print(f"    Ventas totales: ${profile['Ventas_Total']:,.2f}")
        print(f"    Tasa devolucion: {profile['Tasa_Dev_%']:.2f}%")
        print(f"    Margen rentabilidad: {profile['Margen_%']:.2f}%")
        print(f"    Ticket promedio: ${profile['Ticket_Prom']:.2f}")
        print(f"    Penetracion: {profile['Penetracion_%']:.2f}%")

    # =========================================================================
    # 6. PRODUCTOS EJEMPLO POR CLUSTER
    # =========================================================================

    print(f"\n[5] EJEMPLOS DE PRODUCTOS POR CLUSTER")

    for cluster_id in range(best_k):
        name = cluster_names[cluster_id]
        productos_cluster = df[df['cluster'] == cluster_id].nlargest(3, 'total_ventas')['producto'].tolist()
        print(f"\n    {name}:")
        for prod in productos_cluster:
            print(f"      - {prod[:50]}")

    print(f"\n{'='*70}")
    print(f"INTERPRETACION DE CLUSTERS:")
    print(f"- ESTRELLA: Alta rentabilidad, baja devolucion - MANTENER")
    print(f"- COMMODITIES: Alta penetracion - OPTIMIZAR COSTOS")
    print(f"- PROBLEMATICOS: Alta devolucion - INVESTIGAR CAUSAS")
    print(f"- NICHO: Bajo volumen - EVALUAR CONTINUIDAD")
    print(f"- REGULARES: Comportamiento promedio")
    print(f"{'='*70}\n")

    return df


@test
def test_output(output, *args) -> None:
    assert output is not None, 'Transformacion fallo'
    assert 'cluster' in output.columns, 'Falta cluster'
    assert 'cluster_nombre' in output.columns, 'Falta nombre de cluster'
    print(f"OK: {output['cluster'].nunique()} clusters generados")
