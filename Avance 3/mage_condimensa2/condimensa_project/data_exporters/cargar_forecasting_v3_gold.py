"""
Data Exporter: Publicar Forecasting V3 en Gold para dashboard
Pipeline: forecasting_v3_quickbooks
"""
from datetime import datetime
from os import path

import pandas as pd

from mage_ai.io.config import ConfigFileLoader
from mage_ai.io.postgres import Postgres
from mage_ai.settings.repo import get_repo_path

if 'data_exporter' not in dir():
    from mage_ai.data_preparation.decorators import data_exporter
if 'test' not in dir():
    from mage_ai.data_preparation.decorators import test


DASHBOARD_TABLE = 'pronostico_produccion_unificado_v1'
DASHBOARD_COLUMNS = [
    'tipo_producto',
    'categoria_producto',
    'producto_base',
    'producto',
    'producto_dashboard',
    'periodo',
    'periodo_prediccion',
    'qty_fabricada',
    'qty_planificada',
    'pronostico_qty',
    'stock_actual',
    'qty_recomendada',
    'qty_min_recomendada',
    'qty_max_recomendada',
    'nivel_confianza',
    'rolling_std_3',
    'n_ordenes',
    'sugerencia_accion',
    'posibles_causas',
    'es_vigente_operativo',
    'razon_vigencia',
    'pipeline_id',
    'fecha_ejecucion',
    'modelo_ganador',
    'fuente_modelo',
]


def _clean_value(value):
    if pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    if hasattr(value, 'item'):
        return value.item()
    return value


def _insert_dataframe(loader, table_name, df, columns):
    if df.empty:
        return
    quoted_columns = ', '.join([f'"{col}"' for col in columns])
    placeholders = ', '.join(['%s'] * len(columns))
    sql = f'INSERT INTO gold.{table_name} ({quoted_columns}) VALUES ({placeholders})'
    rows = [
        tuple(_clean_value(value) for value in row)
        for row in df[columns].itertuples(index=False, name=None)
    ]
    with loader.conn.cursor() as cur:
        cur.executemany(sql, rows)


def _dashboard_rows(predictions: pd.DataFrame, pipeline_id: str, fecha_ejecucion: datetime) -> pd.DataFrame:
    df = predictions.copy()
    df['periodo'] = pd.to_datetime(df['periodo'], errors='coerce')
    df['ultimo_periodo_entrenamiento'] = pd.to_datetime(
        df['ultimo_periodo_entrenamiento'],
        errors='coerce',
    )

    out = pd.DataFrame()
    out['tipo_producto'] = df['source_type'].astype(str).str.upper()
    out['categoria_producto'] = out['tipo_producto']
    out['producto_base'] = df['product_name']
    out['producto'] = df['product_name']
    out['producto_dashboard'] = df['product_name']
    out['periodo'] = df['ultimo_periodo_entrenamiento']
    out['periodo_prediccion'] = df['periodo']
    out['qty_fabricada'] = 0.0
    out['qty_planificada'] = 0.0
    out['pronostico_qty'] = pd.to_numeric(df['cantidad_predicha'], errors='coerce').fillna(0.0)
    out['stock_actual'] = pd.to_numeric(df.get('stock_actual', 0.0), errors='coerce').fillna(0.0)
    out['qty_recomendada'] = pd.to_numeric(
        df.get('cantidad_a_producir_ajustada', df['cantidad_predicha']),
        errors='coerce',
    ).fillna(out['pronostico_qty'])
    min_source_col = (
        'cantidad_min_a_producir_ajustada'
        if 'cantidad_min_a_producir_ajustada' in df.columns
        else 'prediccion_min'
    )
    max_source_col = (
        'cantidad_max_a_producir_ajustada'
        if 'cantidad_max_a_producir_ajustada' in df.columns
        else 'prediccion_max'
    )
    out['qty_min_recomendada'] = pd.to_numeric(
        df[min_source_col],
        errors='coerce',
    ).fillna(out['qty_recomendada'])
    out['qty_max_recomendada'] = pd.to_numeric(
        df[max_source_col],
        errors='coerce',
    ).fillna(out['qty_recomendada'])
    out['qty_min_recomendada'] = out['qty_min_recomendada'].where(
        out['qty_min_recomendada'].le(out['qty_recomendada']),
        out['qty_recomendada'],
    )
    out['qty_max_recomendada'] = out['qty_max_recomendada'].where(
        out['qty_max_recomendada'].ge(out['qty_recomendada']),
        out['qty_recomendada'],
    )
    out['nivel_confianza'] = df.get('confianza_prediccion', 'sin_confianza')
    out['rolling_std_3'] = pd.to_numeric(df.get('error_relativo_estimado', 0.0), errors='coerce').fillna(0.0)
    out['n_ordenes'] = 0
    out['sugerencia_accion'] = df.get('recomendacion_decision', '')
    out['posibles_causas'] = (
        df.get('alerta_inventario', '').fillna('').astype(str)
        + ' | '
        + df.get('stock_match_status', '').fillna('').astype(str)
    ).str.strip(' |')
    out['es_vigente_operativo'] = ~df.get('estado_producto', '').fillna('').astype(str).str.lower().eq('inactivo')
    out['razon_vigencia'] = df.get('estado_producto', 'sin_estado')
    out['pipeline_id'] = pipeline_id
    out['fecha_ejecucion'] = fecha_ejecucion
    out['modelo_ganador'] = df.get('modelo_usado', '')
    out['fuente_modelo'] = 'FORECASTING_V3_QUICKBOOKS'

    return out[DASHBOARD_COLUMNS].copy()


@data_exporter
def cargar_forecasting_v3_gold(data, *args, **kwargs):
    config_path = path.join(get_repo_path(), 'io_config.yaml')
    config_profile = 'local_dwh'
    pipeline_id = data.get('pipeline_id', 'forecasting_v3_quickbooks')
    fecha_ejecucion = datetime.now()
    report_outputs = data.get('report_outputs', {})

    predicciones = []
    for key in ['predicciones_pt', 'predicciones_pp']:
        if key in report_outputs:
            predicciones.append(report_outputs[key].copy())

    if not predicciones:
        raise RuntimeError('No hay predicciones PT/PP para publicar en Gold.')

    dashboard_df = _dashboard_rows(
        pd.concat(predicciones, ignore_index=True, sort=False),
        pipeline_id,
        fecha_ejecucion,
    )

    print("\n" + "=" * 70)
    print("PUBLICANDO GOLD DASHBOARD - FORECASTING V3 QUICKBOOKS")
    print("=" * 70)

    with Postgres.with_config(ConfigFileLoader(config_path, config_profile)) as loader:
        loader.execute(f'TRUNCATE TABLE gold.{DASHBOARD_TABLE}')
        _insert_dataframe(loader, DASHBOARD_TABLE, dashboard_df, DASHBOARD_COLUMNS)
        loader.conn.commit()

    print(f"  gold.{DASHBOARD_TABLE}: {len(dashboard_df)} registros")
    print("  Reportes tecnicos conservados como CSV en data/forecasting_v3/reports")

    return {
        'status': 'SUCCESS',
        'loaded': {DASHBOARD_TABLE: int(dashboard_df.shape[0])},
        'csv_reports_dir': 'data/forecasting_v3/reports',
        'pipeline_id': pipeline_id,
        'batch_id': data.get('batch_id'),
    }


@test
def test_output(output, *args) -> None:
    assert output is not None, 'Carga Gold Forecasting V3 no genero salida'
    assert output.get('status') == 'SUCCESS', 'Carga Gold Forecasting V3 fallo'
    assert output.get('loaded', {}).get(DASHBOARD_TABLE, 0) > 0, 'No se cargo tabla dashboard'
