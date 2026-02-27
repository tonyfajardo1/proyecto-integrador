"""
Data Loader: Preparar datos para reglas de asociacion
Pipeline: dm_reglas_asociacion
Prepara matriz de transacciones agencia-producto con flag de devolucion.
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
def preparar_datos_asociacion(*args, **kwargs):
    """
    Carga datos de Kronos y prepara matriz para analisis de asociacion.
    Cada fila = una transaccion (agencia-producto-mes)
    Columnas = caracteristicas binarias para Apriori
    """

    query = """SELECT * FROM kronos.ventas_general_4"""

    config_path = path.join(get_repo_path(), 'io_config.yaml')
    config_profile = 'kronos'

    with Postgres.with_config(ConfigFileLoader(config_path, config_profile)) as loader:
        df_raw = loader.load(query)

    # Limpiar datos
    df = df_raw.iloc[7:].copy()
    df.columns = ['centro_costo', 'codigo_producto', 'codigo_alterno', 'producto',
                  'cant_venta', 'total_venta', 'cant_nc', 'total_nc',
                  'cant_devolucion', 'total_devolucion', 'cant_neto', 'total_neto',
                  'costo_venta', 'rentabilidad', 'prc_rentabilidad', 'mes']

    df = df.reset_index(drop=True)
    df = df[df['centro_costo'].notna()]
    df = df[~df['centro_costo'].str.contains('CENTRO_COSTO|Total', na=False, case=False)]

    # Convertir numericos
    for col in ['cant_venta', 'total_venta', 'cant_devolucion', 'total_devolucion', 'rentabilidad']:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    df['centro_costo'] = df['centro_costo'].str.strip().str.lower()
    df['producto'] = df['producto'].str.strip()
    df['mes'] = df['mes'].str.strip().str.upper()

    # =========================================================================
    # CREAR FEATURES BINARIOS PARA APRIORI
    # =========================================================================

    # Calcular tasa de devolucion por registro
    df['tasa_devolucion'] = np.where(
        df['cant_venta'] > 0,
        (df['cant_devolucion'] / df['cant_venta']) * 100,
        0
    )

    # Crear variables binarias
    df['tiene_devolucion'] = (df['cant_devolucion'] > 0).astype(int)
    df['devolucion_alta'] = (df['tasa_devolucion'] > 10).astype(int)
    df['devolucion_critica'] = (df['tasa_devolucion'] > 20).astype(int)
    df['rentabilidad_baja'] = (df['rentabilidad'] < df['rentabilidad'].quantile(0.25)).astype(int)
    df['rentabilidad_alta'] = (df['rentabilidad'] > df['rentabilidad'].quantile(0.75)).astype(int)
    df['volumen_alto'] = (df['cant_venta'] > df['cant_venta'].quantile(0.75)).astype(int)

    # Crear ID de transaccion
    df['transaccion_id'] = range(len(df))

    # Extraer categoria de producto (primeras palabras)
    df['categoria'] = df['producto'].str.split().str[:2].str.join(' ')

    print(f"\n{'='*60}")
    print(f"DATOS PREPARADOS PARA REGLAS DE ASOCIACION")
    print(f"{'='*60}")
    print(f"Transacciones: {len(df)}")
    print(f"Agencias: {df['centro_costo'].nunique()}")
    print(f"Productos: {df['producto'].nunique()}")
    print(f"Con devolucion: {df['tiene_devolucion'].sum()}")
    print(f"Devolucion alta (>10%): {df['devolucion_alta'].sum()}")
    print(f"{'='*60}\n")

    return df


@test
def test_output(output, *args) -> None:
    assert output is not None, 'No se cargaron datos'
    assert 'tiene_devolucion' in output.columns, 'Falta columna tiene_devolucion'
    print(f"OK: {len(output)} transacciones preparadas")
