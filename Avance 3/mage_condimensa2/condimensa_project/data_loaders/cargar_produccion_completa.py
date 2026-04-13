"""
Data Loader: Cargar ordenes de produccion con sus lineas desde QuickBooks
Pipeline: analisis_produccion_desviaciones
"""
import os
import sys

import pandas as pd

from mage_ai.settings.repo import get_repo_path

try:
    from custom.odin_api_client import load_quickbooks_produccion_from_odin
except ModuleNotFoundError:
    repo_path = get_repo_path()
    if repo_path not in sys.path:
        sys.path.append(repo_path)
    from custom.odin_api_client import load_quickbooks_produccion_from_odin

if 'data_loader' not in dir():
    from mage_ai.data_preparation.decorators import data_loader
if 'test' not in dir():
    from mage_ai.data_preparation.decorators import test


@data_loader
def load_produccion_completa(*args, **kwargs):
    """
    Carga ordenes de produccion (cabecera + lineas) desde QuickBooks via ODIN API.
    Une ambas tablas para tener la vista completa de cada orden.
    """
    estado = kwargs.get('estado') or os.getenv('ODIN_ESTADO', 'PENDIENTE')
    date = kwargs.get('date')
    nick = kwargs.get('nick')

    df_ordenes, df_lineas = load_quickbooks_produccion_from_odin(
        estado=estado,
        date=date,
        nick=nick,
    )

    if df_ordenes.empty:
        return df_ordenes

    rename_map = {
        'numitems': 'items_planificados',
        'numitemsprocesados': 'items_procesados',
        'numitemsopen': 'items_pendientes',
    }
    df_ordenes = df_ordenes.rename(columns=rename_map)

    if df_lineas.empty:
        df_completo = df_ordenes.copy()
        df_completo['qty_total_planificada'] = 0
        df_completo['qty_total_despachada'] = 0
        df_completo['num_lineas'] = 0
        return df_completo

    if 'idsale' in df_lineas.columns:
        df_lineas['idsale'] = df_lineas['idsale'].astype(str)
    if 'idsale' in df_ordenes.columns:
        df_ordenes['idsale'] = df_ordenes['idsale'].astype(str)

    df_lineas['cantidad_planificada'] = pd.to_numeric(df_lineas.get('qty'), errors='coerce').fillna(0)
    df_lineas['cantidad_despachada'] = pd.to_numeric(df_lineas.get('qtydespachada'), errors='coerce').fillna(0)
    df_lineas['producto'] = df_lineas.get('name')

    # Agregar metricas de lineas por orden
    lineas_agg = df_lineas.groupby('idsale').agg({
        'cantidad_planificada': 'sum',
        'cantidad_despachada': 'sum',
        'producto': 'count'
    }).reset_index()

    lineas_agg.columns = ['idsale', 'qty_total_planificada', 'qty_total_despachada', 'num_lineas']

    # Unir con ordenes
    df_completo = df_ordenes.merge(lineas_agg, on='idsale', how='left')

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
