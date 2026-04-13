"""
Data Loader: Preparar datos para clustering
Pipeline: dm_clustering_segmentacion
Agrega datos por producto para segmentacion.
"""
from mage_ai.settings.repo import get_repo_path
from mage_ai.io.config import ConfigFileLoader
from mage_ai.io.postgres import Postgres
from os import path
import pandas as pd
import numpy as np

if 'data_loader' not in dir():
    from mage_ai.data_preparation.decorators import data_loader
if 'test' not in dir():
    from mage_ai.data_preparation.decorators import test


@data_loader
def preparar_datos_clustering(*args, **kwargs):
    """
    Carga datos desde Silver (ya limpios) para clustering.
    Crea perfil de cada producto basado en ventas, devoluciones, rentabilidad.
    """

    # Usar Silver layer del DWH local (datos ya limpios y transformados)
    query = """SELECT * FROM silver.kronos_ventas"""

    config_path = path.join(get_repo_path(), 'io_config.yaml')
    config_profile = 'local_dwh'

    with Postgres.with_config(ConfigFileLoader(config_path, config_profile)) as loader:
        df = loader.load(query)

    print(f"[INFO] Datos cargados desde Silver: {len(df)} registros")

    # Convertir numericos (por si acaso)
    cols_num = ['cant_venta', 'total_venta', 'cant_devolucion', 'total_devolucion',
                'cant_neto', 'total_neto', 'costo_venta', 'rentabilidad']
    for col in cols_num:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    if 'producto' in df.columns:
        df['producto'] = df['producto'].astype(str).str.strip()

    # =========================================================================
    # AGREGAR POR PRODUCTO - Perfil para clustering
    # =========================================================================

    productos = df.groupby('producto').agg({
        'total_venta': 'sum',
        'total_devolucion': 'sum',
        'rentabilidad': 'sum',
        'costo_venta': 'sum',
        'cant_venta': 'sum',
        'cant_devolucion': 'sum',
        'centro_costo': 'nunique',  # Numero de agencias que venden el producto
        'mes': 'nunique'  # Numero de meses con ventas
    }).reset_index()

    productos.columns = ['producto', 'total_ventas', 'total_devoluciones',
                         'total_rentabilidad', 'total_costo', 'cant_ventas',
                         'cant_devoluciones', 'num_agencias', 'num_meses']

    # Calcular metricas para clustering
    productos['tasa_devolucion'] = np.where(
        productos['cant_ventas'] > 0,
        (productos['cant_devoluciones'] / productos['cant_ventas']) * 100,
        0
    )

    productos['margen_rentabilidad'] = np.where(
        productos['total_ventas'] > 0,
        (productos['total_rentabilidad'] / productos['total_ventas']) * 100,
        0
    )

    productos['ticket_promedio'] = np.where(
        productos['cant_ventas'] > 0,
        productos['total_ventas'] / productos['cant_ventas'],
        0
    )

    productos['penetracion'] = productos['num_agencias'] / df['centro_costo'].nunique() * 100

    # Filtrar productos con suficientes datos
    productos = productos[productos['cant_ventas'] > 10].copy()

    print(f"\n{'='*60}")
    print(f"DATOS PREPARADOS PARA CLUSTERING")
    print(f"{'='*60}")
    print(f"Productos para segmentar: {len(productos)}")
    print(f"Features: tasa_devolucion, margen_rentabilidad, ticket_promedio, penetracion")
    print(f"{'='*60}\n")

    return productos


@test
def test_output(output, *args) -> None:
    assert output is not None, 'No se cargaron datos'
    assert len(output) > 0, 'Tabla vacia'
    print(f"OK: {len(output)} productos preparados")
