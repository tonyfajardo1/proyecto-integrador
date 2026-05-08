"""
Data Loader: Cargar ventas desde Kronos (Supabase)
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
    Carga datos de ventas generales desde Kronos en Supabase
    Usa la tabla más completa (ventas_general_4 con 7791 registros)
    """
    query = """
    SELECT *
    FROM kronos.ventas_general_4
    """

    config_path = path.join(get_repo_path(), 'io_config.yaml')
    config_profile = 'kronos'

    with Postgres.with_config(ConfigFileLoader(config_path, config_profile)) as loader:
        return loader.load(query)


@test
def test_output(output, *args) -> None:
    assert output is not None, 'No se cargaron datos de Kronos'
    assert len(output) > 0, 'La tabla de ventas Kronos está vacía'
    print(f"✓ Cargadas {len(output)} ventas de Kronos")
