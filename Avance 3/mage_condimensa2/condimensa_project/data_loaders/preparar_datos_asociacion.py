"""
Data Loader: Preparar datos para reglas de asociacion (Cross-Selling)
Pipeline: dm_reglas_asociacion
Carga transacciones de cestas para encontrar productos que se venden juntos.
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
    Carga transacciones de cestas para analisis de cross-selling.
    Cada transaccion contiene multiples productos comprados juntos.
    """

    # Cargar transacciones de cestas (prioridad: tabla transaccional real)
    # 1) silver.apriori_transacciones (ticket-item)
    # 2) fallback a silver.kronos_ventas (agregado mensual) si no hay datos
    top_items_por_transaccion = int(kwargs.get('top_items_por_transaccion', 40))
    query_apriori = """
    SELECT
        transaccion_id,
        NULL::text AS codigo_producto,
        producto,
        categoria,
        agencia
    FROM silver.apriori_transacciones
    WHERE transaccion_id IS NOT NULL
      AND producto IS NOT NULL
    """

    query_fallback = f"""
    WITH base AS (
        SELECT
            CONCAT(centro_costo, '-', anio::text, '-', UPPER(mes)) AS transaccion_id,
            codigo_producto,
            producto,
            SPLIT_PART(producto, ':', 2) AS categoria,
            centro_costo AS agencia,
            COALESCE(total_venta, 0) AS total_venta,
            ROW_NUMBER() OVER (
                PARTITION BY CONCAT(centro_costo, '-', anio::text, '-', UPPER(mes))
                ORDER BY COALESCE(total_venta, 0) DESC
            ) AS rn
        FROM silver.kronos_ventas
        WHERE producto IS NOT NULL
          AND centro_costo IS NOT NULL
          AND anio IS NOT NULL
          AND mes IS NOT NULL
          AND COALESCE(total_venta, 0) > 0
    )
    SELECT
        transaccion_id,
        codigo_producto,
        producto,
        categoria,
        agencia
    FROM base
    WHERE rn <= {top_items_por_transaccion}
    ORDER BY transaccion_id
    """

    config_path = path.join(get_repo_path(), 'io_config.yaml')
    config_profile = 'local_dwh'

    with Postgres.with_config(ConfigFileLoader(config_path, config_profile)) as loader:
        try:
            df = loader.load(query_apriori)
        except Exception:
            df = pd.DataFrame()

        if len(df) == 0:
            df = loader.load(query_fallback)
            print("[INFO] Usando fallback agregado desde silver.kronos_ventas")
        else:
            print("[INFO] Usando fuente transaccional silver.apriori_transacciones")

    # Normalizacion minima de texto
    df['transaccion_id'] = df['transaccion_id'].astype(str).str.strip()
    df['producto'] = df['producto'].astype(str).str.strip()
    if 'categoria' in df.columns:
        df['categoria'] = df['categoria'].astype(str).str.strip().str.upper()
    if 'agencia' in df.columns:
        df['agencia'] = df['agencia'].astype(str).str.strip().str.lower()

    # Quitar nulos/invalidos basicos
    df = df[
        (df['transaccion_id'].notna())
        & (df['transaccion_id'] != '')
        & (df['transaccion_id'].str.lower() != 'nan')
        & (df['producto'].notna())
        & (df['producto'] != '')
        & (df['producto'].str.lower() != 'nan')
    ].copy()

    # Evitar duplicados dentro de la misma cesta
    before_dups = len(df)
    df = df.drop_duplicates(subset=['transaccion_id', 'producto']).copy()
    print(f"Duplicados removidos (transaccion-producto): {before_dups - len(df)}")

    # Filtrar productos extremadamente raros para reducir dimension
    min_transacciones_producto = int(kwargs.get('min_transacciones_producto', 3))
    freq = df.groupby('producto')['transaccion_id'].nunique()
    productos_validos = freq[freq >= min_transacciones_producto].index
    df = df[df['producto'].isin(productos_validos)].copy()

    print(f"\n{'='*60}")
    print(f"DATOS CARGADOS PARA REGLAS DE ASOCIACION")
    print(f"{'='*60}")
    print(f"Items totales: {len(df)}")
    print(f"Transacciones unicas: {df['transaccion_id'].nunique()}")
    if 'codigo_producto' in df.columns:
        print(f"Productos unicos (codigo): {df['codigo_producto'].nunique()}")
    print(f"Productos unicos (nombre): {df['producto'].nunique()}")
    print(f"Top items por transaccion: {top_items_por_transaccion}")
    print(f"Min transacciones por producto: {min_transacciones_producto}")
    print(f"Categorias (muestra): {df['categoria'].dropna().astype(str).unique().tolist()[:10]}")

    # Mostrar distribucion de productos por transaccion
    productos_por_trans = df.groupby('transaccion_id').size()
    print(f"\nProductos por transaccion:")
    print(f"  - Minimo: {productos_por_trans.min()}")
    print(f"  - Maximo: {productos_por_trans.max()}")
    print(f"  - Promedio: {productos_por_trans.mean():.2f}")
    print(f"{'='*60}\n")

    return df


@test
def test_output(output, *args) -> None:
    assert output is not None, 'No se cargaron datos'
    assert 'transaccion_id' in output.columns, 'Falta columna transaccion_id'
    assert 'codigo_producto' in output.columns, 'Falta columna codigo_producto'
    assert output['transaccion_id'].nunique() > 0, 'No hay transacciones'
    print(f"OK: {output['transaccion_id'].nunique()} transacciones cargadas")
