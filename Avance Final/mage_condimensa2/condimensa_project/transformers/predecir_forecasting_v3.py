"""
Transformer: Generar predicciones Forecasting V3 QuickBooks
Pipeline: forecasting_v3_quickbooks
"""
from os import path
import sys
from datetime import datetime

from mage_ai.settings.repo import get_repo_path

if 'transformer' not in dir():
    from mage_ai.data_preparation.decorators import transformer
if 'test' not in dir():
    from mage_ai.data_preparation.decorators import test

repo_src = path.join(get_repo_path(), 'src')
if repo_src not in sys.path:
    sys.path.insert(0, repo_src)

from forecasting_v3_mage import PREDICTION_KEY_COLUMNS, assert_unique_keys, config_path, read_report_outputs
from quickbooks_forecast.config import load_config
from quickbooks_forecast.decision import build_decision_templates
from quickbooks_forecast.modeling import predict_all
from quickbooks_forecast.operational_evaluation import build_operational_evaluation


@transformer
def predecir_forecasting_v3(data, *args, **kwargs):
    repo_path = get_repo_path()
    cfg = load_config(config_path(repo_path))

    print("\n" + "=" * 70)
    print("PREDICCION - FORECASTING V3 QUICKBOOKS")
    print("=" * 70)

    predictions = predict_all(cfg)
    for source, df in predictions.items():
        assert_unique_keys(df, PREDICTION_KEY_COLUMNS, f'predicciones_{source.lower()}')
        modelos = ', '.join(df['modelo_usado'].value_counts().index.astype(str))
        print(f"  {source}: {df.shape[0]} predicciones ({modelos})")

    decision_outputs = build_decision_templates(cfg)
    operational_outputs = build_operational_evaluation(cfg)
    print("  Plantillas de decision y evaluacion operativa actualizadas")

    outputs = read_report_outputs(cfg)
    counts = {key: int(df.shape[0]) for key, df in outputs.items()}
    for key, rows in counts.items():
        print(f"  Reporte {key}: {rows} registros")

    return {
        **data,
        'status': 'SUCCESS',
        'fecha_fin': datetime.now().isoformat(),
        'report_outputs': outputs,
        'report_counts': counts,
        'decision_outputs': decision_outputs,
        'operational_outputs': operational_outputs,
    }


@test
def test_output(output, *args) -> None:
    assert output is not None, 'Prediccion no genero salida'
    assert output.get('status') == 'SUCCESS', 'Prediccion fallo'
    reports = output.get('report_outputs', {})
    assert 'predicciones_pt' in reports, 'Faltan predicciones PT'
    assert 'predicciones_pp' in reports, 'Faltan predicciones PP'
    assert_unique_keys(reports['predicciones_pt'], PREDICTION_KEY_COLUMNS, 'report_outputs.predicciones_pt')
    assert_unique_keys(reports['predicciones_pp'], PREDICTION_KEY_COLUMNS, 'report_outputs.predicciones_pp')
