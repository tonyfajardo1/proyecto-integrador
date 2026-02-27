"""
Data Loader: Preparar datos para deteccion de anomalias
Pipeline: dm_deteccion_anomalias
Agrega datos de Kronos por agencia para detectar comportamientos atipicos.
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
def preparar_datos_anomalias(*args, **kwargs):
    """
    Carga datos desde Silver (ya limpios) por agencia.
    Calcula metricas que seran usadas para detectar anomalias.
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

    if 'centro_costo' in df.columns:
        df['centro_costo'] = df['centro_costo'].astype(str).str.strip().str.lower()

    # =========================================================================
    # AGREGAR POR AGENCIA - Metricas para deteccion de anomalias
    # =========================================================================

    agencias = df.groupby('centro_costo').agg({
        'total_venta': 'sum',
        'total_devolucion': 'sum',
        'rentabilidad': 'sum',
        'costo_venta': 'sum',
        'cant_venta': 'sum',
        'cant_devolucion': 'sum',
        'producto': 'count'
    }).reset_index()

    agencias.columns = ['agencia', 'total_ventas', 'total_devoluciones',
                        'total_rentabilidad', 'total_costo', 'cant_ventas',
                        'cant_devoluciones', 'num_productos']

    # Calcular ratios (features para deteccion de anomalias)
    agencias['ratio_devolucion'] = np.where(
        agencias['total_ventas'] > 0,
        (agencias['total_devoluciones'] / agencias['total_ventas']) * 100,
        0
    )

    agencias['ratio_rentabilidad'] = np.where(
        agencias['total_ventas'] > 0,
        (agencias['total_rentabilidad'] / agencias['total_ventas']) * 100,
        0
    )

    agencias['ratio_costo'] = np.where(
        agencias['total_ventas'] > 0,
        (agencias['total_costo'] / agencias['total_ventas']) * 100,
        0
    )

    agencias['ticket_promedio'] = np.where(
        agencias['num_productos'] > 0,
        agencias['total_ventas'] / agencias['num_productos'],
        0
    )

    print(f"\n{'='*60}")
    print(f"DATOS PREPARADOS PARA DETECCION DE ANOMALIAS")
    print(f"{'='*60}")
    print(f"Agencias analizadas: {len(agencias)}")
    print(f"Features calculados: ratio_devolucion, ratio_rentabilidad, ratio_costo, ticket_promedio")
    print(f"{'='*60}\n")

    return agencias


@test
def test_output(output, *args) -> None:
    assert output is not None, 'No se cargaron datos'
    assert len(output) > 0, 'Tabla vacia'
    assert 'ratio_devolucion' in output.columns, 'Falta ratio_devolucion'
    print(f"OK: {len(output)} agencias preparadas para analisis")
