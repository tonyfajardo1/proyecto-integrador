"""
Data Loader: Cargar órdenes de producción desde QuickBooks (ODIN API)
"""
import os
import sys

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
def load_data_from_postgres(*args, **kwargs):
    """
    Carga órdenes de producción desde QuickBooks usando ODIN API.
    """
    estado = kwargs.get('estado') or os.getenv('ODIN_ESTADO', 'PENDIENTE')
    date = kwargs.get('date')
    nick = kwargs.get('nick')

    df_orders, _ = load_quickbooks_produccion_from_odin(
        estado=estado,
        date=date,
        nick=nick,
    )

    if df_orders.empty:
        return df_orders

    return df_orders.sort_values(by='fecha', ascending=False)


@test
def test_output(output, *args) -> None:
    assert output is not None, 'No se cargaron datos de producción'
    assert len(output) > 0, 'La tabla de producción está vacía'
    print(f"✓ Cargadas {len(output)} órdenes de producción")
