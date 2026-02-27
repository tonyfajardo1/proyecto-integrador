"""
Data Loader: Cargar órdenes de producción desde QuickBooks (Supabase)
"""
from mage_ai.settings.repo import get_repo_path
from mage_ai.io.config import ConfigFileLoader
from mage_ai.io.postgres import Postgres
from os import path

if 'data_loader' not in dir():
    from mage_ai.data_preparation.decorators import data_loader
if 'test' not in dir():
    from mage_ai.data_preparation.decorators import test


@data_loader
def load_data_from_postgres(*args, **kwargs):
    """
    Carga órdenes de producción desde QuickBooks en Supabase
    """
    query = """
    SELECT
        p.*
    FROM quickbooks.produccion p
    ORDER BY p.fecha DESC
    """

    config_path = path.join(get_repo_path(), 'io_config.yaml')
    config_profile = 'quickbooks'

    with Postgres.with_config(ConfigFileLoader(config_path, config_profile)) as loader:
        return loader.load(query)


@test
def test_output(output, *args) -> None:
    assert output is not None, 'No se cargaron datos de producción'
    assert len(output) > 0, 'La tabla de producción está vacía'
    print(f"✓ Cargadas {len(output)} órdenes de producción")
