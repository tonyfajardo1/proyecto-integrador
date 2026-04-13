"""
Transformer: Entrenar modelos Forecasting V3 QuickBooks
Pipeline: forecasting_v3_quickbooks
"""
from os import path
import sys
from datetime import datetime

import pandas as pd

from mage_ai.settings.repo import get_repo_path

if 'transformer' not in dir():
    from mage_ai.data_preparation.decorators import transformer
if 'test' not in dir():
    from mage_ai.data_preparation.decorators import test

repo_src = path.join(get_repo_path(), 'src')
if repo_src not in sys.path:
    sys.path.insert(0, repo_src)

from forecasting_v3_mage import config_path, strip_technical_columns, write_processed_outputs
from quickbooks_forecast.config import ensure_output_dirs, load_config
from quickbooks_forecast.exogenous import add_exogenous_features
from quickbooks_forecast.modeling import train_all


def _prepare_monthly_with_exogenous(config, df: pd.DataFrame, source: str) -> pd.DataFrame:
    clean_df = strip_technical_columns(df)
    clean_df['periodo'] = pd.to_datetime(clean_df['periodo'], errors='coerce')
    return add_exogenous_features(config, clean_df, source)


@transformer
def entrenar_forecasting_v3(data, *args, **kwargs):
    repo_path = get_repo_path()
    cfg = load_config(config_path(repo_path))
    ensure_output_dirs(cfg)

    dfs = {key: value.copy() for key, value in data.get('dfs', {}).items()}
    pipeline_id = data.get('pipeline_id', 'forecasting_v3_quickbooks')
    batch_id = data.get('batch_id')
    fecha_inicio = datetime.now()

    print("\n" + "=" * 70)
    print("ENTRENAMIENTO - FORECASTING V3 QUICKBOOKS")
    print("=" * 70)

    dfs['pt_mensual_model'] = _prepare_monthly_with_exogenous(cfg, dfs['pt_mensual_model'], 'PT')
    dfs['pp_mensual_model'] = _prepare_monthly_with_exogenous(cfg, dfs['pp_mensual_model'], 'PP')

    staged_counts = write_processed_outputs(cfg, dfs)
    for key, rows in staged_counts.items():
        print(f"  Staging {key}: {rows} registros")

    artifacts = train_all(cfg)
    metrics = []
    for source, artifact in artifacts.items():
        row = artifact['metric_values'].copy()
        row['source'] = source
        metrics.append(row)
        print(
            f"  {source}: modelo={row['selected_model_name']} "
            f"WAPE={float(row['wape']):.4f} train={int(row['train_rows'])}"
        )

    return {
        'status': 'SUCCESS',
        'config_path': str(config_path(repo_path)),
        'pipeline_id': pipeline_id,
        'batch_id': batch_id,
        'fecha_inicio': fecha_inicio.isoformat(),
        'staged_counts': staged_counts,
        'metrics': metrics,
    }


@test
def test_output(output, *args) -> None:
    assert output is not None, 'Entrenamiento no genero salida'
    assert output.get('status') == 'SUCCESS', 'Entrenamiento fallo'
    assert len(output.get('metrics', [])) == 2, 'No se entrenaron PT y PP'
