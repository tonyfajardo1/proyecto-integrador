"""
Data Loader: Cargar ventas completas desde QuickBooks (Supabase)
Pipeline: analisis_quickbooks_ventas
Carga ordenes de venta con sus lineas de detalle.
"""
from mage_ai.settings.repo import get_repo_path
from mage_ai.io.config import ConfigFileLoader
from mage_ai.io.postgres import Postgres
from os import path
import pandas as pd

if 'data_loader' not in dir():
    from mage_ai.data_preparation.decorators import data_loader
if 'test' not in dir():
    from mage_ai.data_preparation.decorators import test


@data_loader
def load_quickbooks_ventas(*args, **kwargs):
    """
    Carga ordenes de venta con lineas de detalle desde QuickBooks.
    Calcula metricas agregadas por orden.
    """

    # Query para ordenes
    query_ordenes = """
    SELECT
        s.idsales,
        s.idsale,
        s.fecha,
        s.estado,
        s.numero,
        s.cliente,
        s.idcliente,
        s.numitems,
        s.numitemsprocesados,
        s.status
    FROM quickbooks.sales s
    ORDER BY s.fecha DESC
    """

    # Query para lineas con agregacion
    query_lineas = """
    SELECT
        sl.idsales,
        COUNT(*) as num_lineas,
        SUM(sl.qty) as qty_pedida,
        SUM(sl.qtydespachada) as qty_despachada,
        COUNT(DISTINCT sl.name) as productos_unicos
    FROM quickbooks.sales_lineas sl
    GROUP BY sl.idsales
    """

    # Query para detalle de productos por orden
    query_productos = """
    SELECT
        sl.idsales,
        sl.name as producto,
        sl.fullname as categoria,
        sl.qty as qty_pedida,
        sl.qtydespachada as qty_despachada
    FROM quickbooks.sales_lineas sl
    """

    config_path = path.join(get_repo_path(), 'io_config.yaml')
    config_profile = 'quickbooks'

    with Postgres.with_config(ConfigFileLoader(config_path, config_profile)) as loader:
        df_ordenes = loader.load(query_ordenes)
        df_lineas_agg = loader.load(query_lineas)
        df_productos = loader.load(query_productos)

    # Unir ordenes con metricas de lineas
    df = df_ordenes.merge(df_lineas_agg, on='idsales', how='left')

    # Rellenar valores nulos
    df['qty_pedida'] = df['qty_pedida'].fillna(0)
    df['qty_despachada'] = df['qty_despachada'].fillna(0)
    df['num_lineas'] = df['num_lineas'].fillna(0)

    print(f"\n{'='*60}")
    print(f"CARGA DE DATOS - QUICKBOOKS VENTAS")
    print(f"{'='*60}")
    print(f"Ordenes cargadas: {len(df)}")
    print(f"Lineas de detalle: {df['num_lineas'].sum():.0f}")
    print(f"Qty total pedida: {df['qty_pedida'].sum():,.0f}")
    print(f"Qty total despachada: {df['qty_despachada'].sum():,.0f}")
    print(f"{'='*60}\n")

    # Guardar productos en kwargs para uso posterior si es necesario
    kwargs['df_productos'] = df_productos

    return df


@test
def test_output(output, *args) -> None:
    """
    Verifica que los datos se cargaron correctamente
    """
    assert output is not None, 'No se cargaron datos'
    assert len(output) > 0, 'La tabla esta vacia'
    assert 'qty_pedida' in output.columns, 'Falta columna qty_pedida'
    assert 'qty_despachada' in output.columns, 'Falta columna qty_despachada'
    print(f"OK: Cargadas {len(output)} ordenes de QuickBooks")
