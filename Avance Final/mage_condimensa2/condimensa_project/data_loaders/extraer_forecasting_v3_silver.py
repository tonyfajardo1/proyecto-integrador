"""
Data Loader: Extraer datasets Forecasting V3 desde Silver
Pipeline: forecasting_v3_quickbooks
"""
from os import path
import sys

from mage_ai.io.config import ConfigFileLoader
from mage_ai.io.postgres import Postgres
from mage_ai.settings.repo import get_repo_path

if 'data_loader' not in dir():
    from mage_ai.data_preparation.decorators import data_loader
if 'test' not in dir():
    from mage_ai.data_preparation.decorators import test

repo_src = path.join(get_repo_path(), 'src')
if repo_src not in sys.path:
    sys.path.insert(0, repo_src)

from forecasting_v3_mage import BRONZE_DATASETS, SILVER_DATASETS, validate_forecasting_inputs


@data_loader
def extraer_forecasting_v3_silver(*args, **kwargs):
    config_path = path.join(get_repo_path(), 'io_config.yaml')
    config_profile = 'local_dwh'

    print("\n" + "=" * 70)
    print("EXTRACCION SILVER - FORECASTING V3 QUICKBOOKS")
    print("=" * 70)

    dfs = {}
    counts = {}

    with Postgres.with_config(ConfigFileLoader(config_path, config_profile)) as loader:
        for key, table_name in SILVER_DATASETS.items():
            sql = f"SELECT * FROM silver.{table_name} ORDER BY id"
            df = loader.load(sql)
            dfs[key] = df
            counts[key] = int(df.shape[0])
            print(f"  silver.{table_name}: {df.shape[0]} registros")

        for key, table_name in BRONZE_DATASETS.items():
            sql = f"SELECT * FROM bronze.{table_name} ORDER BY id"
            df = loader.load(sql)
            dfs[key] = df
            counts[key] = int(df.shape[0])
            print(f"  bronze.{table_name}: {df.shape[0]} registros")

    quality = validate_forecasting_inputs(dfs)
    if quality['issues']:
        print("  [WARN] Silver no esta alineado con el modelado validado:")
        for issue in quality['issues']:
            print(f"    - {issue}")
        print("  El pipeline continua para diagnostico/demo; actualiza ETL Silver para metricas comparables.")
    else:
        print("  Validacion Silver vs modelado validado: OK")

    return {
        'dfs': dfs,
        'counts': counts,
        'quality_summary': quality['summary'],
        'quality_issues': quality['issues'],
        'data_quality_status': 'WARNING' if quality['issues'] else 'OK',
        'pipeline_id': kwargs.get('pipeline_uuid', 'forecasting_v3_quickbooks'),
        'batch_id': kwargs.get('execution_date'),
    }


@test
def test_output(output, *args) -> None:
    assert output is not None, 'No se extrajeron datos'
    expected = {**SILVER_DATASETS, **BRONZE_DATASETS}
    missing = [key for key in expected if key not in output.get('dfs', {})]
    assert not missing, f'Faltan datasets Forecasting V3: {missing}'
    empty = [key for key, df in output['dfs'].items() if df.empty]
    assert not empty, f'Datasets Forecasting V3 vacios: {empty}'
    assert output.get('data_quality_status') in {'OK', 'WARNING'}, 'Estado de calidad invalido'
