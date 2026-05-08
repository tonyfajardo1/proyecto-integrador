"""
Data Loader: Cargar ventas completas desde QuickBooks (ODIN API)
Pipeline: analisis_quickbooks_ventas
Carga ordenes de venta con sus lineas de detalle.
"""
import os
import sys

import pandas as pd

from mage_ai.settings.repo import get_repo_path

try:
    from custom.odin_api_client import load_quickbooks_sales_from_odin
except ModuleNotFoundError:
    repo_path = get_repo_path()
    if repo_path not in sys.path:
        sys.path.append(repo_path)
    from custom.odin_api_client import load_quickbooks_sales_from_odin

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
    estado = kwargs.get('estado') or os.getenv('ODIN_ESTADO', 'PENDIENTE')
    date = kwargs.get('date')
    nick = kwargs.get('nick')

    df_ordenes, df_lineas = load_quickbooks_sales_from_odin(
        estado=estado,
        date=date,
        nick=nick,
    )

    if df_ordenes.empty:
        return df_ordenes

    if df_lineas.empty:
        df = df_ordenes.copy()
        df['num_lineas'] = 0
        df['qty_pedida'] = 0
        df['qty_despachada'] = 0
        df['productos_unicos'] = 0
        return df

    if 'idsale' in df_lineas.columns:
        df_lineas['idsale'] = df_lineas['idsale'].astype(str)
    if 'idsale' in df_ordenes.columns:
        df_ordenes['idsale'] = df_ordenes['idsale'].astype(str)

    df_lineas['qty'] = pd.to_numeric(df_lineas.get('qty'), errors='coerce').fillna(0)
    df_lineas['qtydespachada'] = pd.to_numeric(df_lineas.get('qtydespachada'), errors='coerce').fillna(0)

    if 'idlinea' not in df_lineas.columns:
        df_lineas['idlinea'] = df_lineas['idsale']
    if 'name' not in df_lineas.columns:
        df_lineas['name'] = None

    df_lineas_agg = (
        df_lineas.groupby('idsale', dropna=False)
        .agg(
            num_lineas=('idlinea', 'count'),
            qty_pedida=('qty', 'sum'),
            qty_despachada=('qtydespachada', 'sum'),
            productos_unicos=('name', 'nunique'),
        )
        .reset_index()
    )

    df_productos = pd.DataFrame(
        {
            'idsale': df_lineas.get('idsale'),
            'producto': df_lineas.get('name'),
            'categoria': df_lineas.get('fullname'),
            'qty_pedida': pd.to_numeric(df_lineas.get('qty'), errors='coerce').fillna(0),
            'qty_despachada': pd.to_numeric(df_lineas.get('qtydespachada'), errors='coerce').fillna(0),
        }
    )

    # Unir ordenes con metricas de lineas
    df = df_ordenes.merge(df_lineas_agg, on='idsale', how='left')

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
