"""
Data Loader: Cargar ordenes de produccion con sus lineas desde QuickBooks
Pipeline: analisis_produccion_desviaciones
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
def load_produccion_completa(*args, **kwargs):
    """
    Carga ordenes de produccion (cabecera + lineas) desde QuickBooks en Supabase.
    Une ambas tablas para tener la vista completa de cada orden.
    """

    # Query para obtener produccion con metricas agregadas por orden
    query_ordenes = """
    SELECT
        p.idsales,
        p.idsale,
        p.fecha,
        p.estado,
        p.numero,
        p.cliente,
        p.numitems as items_planificados,
        p.numitemsprocesados as items_procesados,
        p.numitemsopen as items_pendientes,
        p.status
    FROM quickbooks.produccion p
    ORDER BY p.fecha DESC
    """

    # Query para obtener detalle de lineas con cantidades
    query_lineas = """
    SELECT
        pl.idsales,
        pl.idsale,
        pl.name as producto,
        pl.fullname as producto_fullname,
        pl.qty as cantidad_planificada,
        pl.qtydespachada as cantidad_despachada,
        pl.novedades,
        pl.hora as fecha_actualizacion
    FROM quickbooks.produccion_lineas pl
    """

    config_path = path.join(get_repo_path(), 'io_config.yaml')
    config_profile = 'quickbooks'

    with Postgres.with_config(ConfigFileLoader(config_path, config_profile)) as loader:
        df_ordenes = loader.load(query_ordenes)
        df_lineas = loader.load(query_lineas)

    # Agregar metricas de lineas por orden
    lineas_agg = df_lineas.groupby('idsales').agg({
        'cantidad_planificada': 'sum',
        'cantidad_despachada': 'sum',
        'producto': 'count'
    }).reset_index()

    lineas_agg.columns = ['idsales', 'qty_total_planificada', 'qty_total_despachada', 'num_lineas']

    # Unir con ordenes
    df_completo = df_ordenes.merge(lineas_agg, on='idsales', how='left')

    # Calcular desviacion basica
    df_completo['qty_total_planificada'] = df_completo['qty_total_planificada'].fillna(0)
    df_completo['qty_total_despachada'] = df_completo['qty_total_despachada'].fillna(0)

    print(f"\n{'='*60}")
    print(f"CARGA DE DATOS DE PRODUCCION")
    print(f"{'='*60}")
    print(f"Ordenes cargadas: {len(df_ordenes)}")
    print(f"Lineas cargadas: {len(df_lineas)}")
    print(f"Rango de fechas: {df_completo['fecha'].min()} a {df_completo['fecha'].max()}")
    print(f"{'='*60}\n")

    return df_completo


@test
def test_output(output, *args) -> None:
    """
    Verifica que los datos se cargaron correctamente
    """
    assert output is not None, 'No se cargaron datos'
    assert len(output) > 0, 'La tabla esta vacia'
    assert 'qty_total_planificada' in output.columns, 'Falta columna qty_total_planificada'
    assert 'qty_total_despachada' in output.columns, 'Falta columna qty_total_despachada'
    print(f"OK: Cargadas {len(output)} ordenes de produccion")
