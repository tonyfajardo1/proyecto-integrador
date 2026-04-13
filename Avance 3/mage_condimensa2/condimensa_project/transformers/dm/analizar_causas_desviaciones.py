"""
Transformer: Pronostico mensual de cantidad de produccion por producto.
Pipeline: dm_analisis_desviaciones
Modelo: RandomForestRegressor + baseline naive.
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

if 'transformer' not in dir():
    from mage_ai.data_preparation.decorators import transformer
if 'test' not in dir():
    from mage_ai.data_preparation.decorators import test


def _wape(y_true, y_pred):
    den = np.abs(np.asarray(y_true)).sum()
    if den == 0:
        return np.nan
    return np.abs(np.asarray(y_true) - np.asarray(y_pred)).sum() / den


@transformer
def analizar_causas_desviaciones(data, *args, **kwargs):
    """
    Entrena un modelo de pronostico t+1 a nivel producto-mes.
    """
    df = data.copy()
    if 'tipo_producto' not in df.columns:
        df['tipo_producto'] = 'OTRO'
    if 'categoria_producto' not in df.columns:
        df['categoria_producto'] = 'GENERAL'
    if 'producto_base' not in df.columns:
        df['producto_base'] = df.get('producto', 'SIN_PRODUCTO')

    df['producto'] = df['producto'].astype(str).str.strip()
    df['tipo_producto'] = df['tipo_producto'].astype(str).str.upper().str.strip()
    df['producto_key'] = df['tipo_producto'] + '|' + df['producto']
    df = df.sort_values(['producto_key', 'periodo']).reset_index(drop=True)

    if len(df) == 0:
        return {
            'predicciones': pd.DataFrame(),
            'metricas_modelo': pd.DataFrame(),
            'importancia_features': pd.DataFrame(),
            'serie_modelado': pd.DataFrame(),
        }

    # Features temporales por producto
    grp = df.groupby('producto_key')
    df['lag_1'] = grp['qty_fabricada'].shift(1)
    df['lag_2'] = grp['qty_fabricada'].shift(2)
    df['lag_3'] = grp['qty_fabricada'].shift(3)
    df['rolling_3'] = grp['qty_fabricada'].shift(1).rolling(3, min_periods=1).mean()
    df['rolling_std_3'] = grp['qty_fabricada'].shift(1).rolling(3, min_periods=1).std().fillna(0)
    df['plan_lag_1'] = grp['qty_planificada'].shift(1)

    # Target futuro t+1
    df['target_t1'] = grp['qty_fabricada'].shift(-1)

    # Eliminar filas sin historial o sin target
    model_df = df.dropna(subset=['lag_1', 'target_t1']).copy()
    if len(model_df) < 30:
        # fallback de emergencia
        model_df = df.dropna(subset=['target_t1']).copy()
        for c in ['lag_1', 'lag_2', 'lag_3', 'rolling_3', 'rolling_std_3', 'plan_lag_1']:
            if c not in model_df.columns:
                model_df[c] = 0
            model_df[c] = model_df[c].fillna(0)

    model_df['mes_num'] = model_df['periodo'].dt.month
    model_df['anio_num'] = model_df['periodo'].dt.year
    model_df['producto_id'] = pd.factorize(model_df['producto_key'])[0]

    features = [
        'producto_id', 'anio_num', 'mes_num',
        'lag_1', 'lag_2', 'lag_3', 'rolling_3', 'rolling_std_3',
        'plan_lag_1', 'n_ordenes',
    ]

    X = model_df[features].replace([np.inf, -np.inf], np.nan).fillna(0)
    y = model_df['target_t1'].astype(float)

    # Split temporal global
    cutoff = model_df['periodo'].quantile(0.8)
    train_mask = model_df['periodo'] <= cutoff
    test_mask = model_df['periodo'] > cutoff

    if test_mask.sum() == 0:
        # fallback para poca historia
        train_mask = np.arange(len(model_df)) < int(len(model_df) * 0.8)
        test_mask = ~train_mask

    X_train, X_test = X[train_mask], X[test_mask]
    y_train, y_test = y[train_mask], y[test_mask]

    model = RandomForestRegressor(
        n_estimators=300,
        random_state=42,
        n_jobs=-1,
        min_samples_leaf=2,
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    y_pred = np.maximum(y_pred, 0)

    # Baseline naive: valor anterior
    naive_pred = model_df.loc[test_mask, 'lag_1'].fillna(0).values

    mae = mean_absolute_error(y_test, y_pred) if len(y_test) > 0 else np.nan
    rmse = np.sqrt(mean_squared_error(y_test, y_pred)) if len(y_test) > 0 else np.nan
    wape = _wape(y_test, y_pred) if len(y_test) > 0 else np.nan

    mae_baseline = mean_absolute_error(y_test, naive_pred) if len(y_test) > 0 else np.nan
    rmse_baseline = np.sqrt(mean_squared_error(y_test, naive_pred)) if len(y_test) > 0 else np.nan
    wape_baseline = _wape(y_test, naive_pred) if len(y_test) > 0 else np.nan

    # Predicciones del siguiente mes por producto
    ult = df.sort_values(['producto_key', 'periodo']).groupby('producto_key', as_index=False).tail(1).copy()
    ult['lag_1'] = ult['qty_fabricada']
    ult['lag_2'] = grp['qty_fabricada'].shift(1).groupby(df['producto_key']).tail(1).values
    ult['lag_3'] = grp['qty_fabricada'].shift(2).groupby(df['producto_key']).tail(1).values
    ult['rolling_3'] = grp['qty_fabricada'].rolling(3, min_periods=1).mean().reset_index(level=0, drop=True).groupby(df['producto_key']).tail(1).values
    ult['rolling_std_3'] = grp['qty_fabricada'].rolling(3, min_periods=1).std().fillna(0).reset_index(level=0, drop=True).groupby(df['producto_key']).tail(1).values
    ult['qty_fabricada_3m'] = grp['qty_fabricada'].rolling(3, min_periods=1).sum().reset_index(level=0, drop=True).groupby(df['producto_key']).tail(1).values
    ult['qty_planificada_3m'] = grp['qty_planificada'].rolling(3, min_periods=1).sum().reset_index(level=0, drop=True).groupby(df['producto_key']).tail(1).values
    ult['plan_lag_1'] = ult['qty_planificada']
    ult['mes_num'] = ult['periodo'].dt.month
    ult['anio_num'] = ult['periodo'].dt.year
    prod_map = {p: i for i, p in enumerate(model_df['producto_key'].dropna().unique())}
    ult['producto_id'] = ult['producto_key'].map(prod_map).fillna(0)

    X_next = ult[features].replace([np.inf, -np.inf], np.nan).fillna(0)
    next_pred = np.maximum(model.predict(X_next), 0)

    max_periodo_global = df['periodo'].max()
    periodo_prediccion_global = (max_periodo_global + pd.offsets.MonthBegin(1)).date()
    ult['periodo_prediccion'] = periodo_prediccion_global
    ult['pronostico_qty'] = next_pred
    ult['qty_recomendada'] = np.ceil(next_pred)
    ult['error_historico_abs'] = np.abs(ult['qty_fabricada'] - ult['lag_1'])
    ult['nivel_confianza'] = np.where(
        ult['rolling_std_3'] <= ult['rolling_3'] * 0.15,
        'ALTA',
        np.where(ult['rolling_std_3'] <= ult['rolling_3'] * 0.35, 'MEDIA', 'BAJA'),
    )

    # Recomendacion en rango (no solo punto), segun nivel de confianza
    factor_rango = np.select(
        [ult['nivel_confianza'] == 'ALTA', ult['nivel_confianza'] == 'MEDIA'],
        [1.0, 1.5],
        default=2.0,
    )
    amplitud = factor_rango * ult['rolling_std_3'].fillna(0)
    piso_minimo = np.maximum(0, ult['pronostico_qty'] * 0.30)
    ult['qty_min_recomendada'] = np.floor(np.maximum(piso_minimo, ult['pronostico_qty'] - amplitud))
    ult['qty_max_recomendada'] = np.ceil(np.maximum(0, ult['pronostico_qty'] + amplitud))

    # Guardrail de actividad: si no hubo fabricacion ni planificacion reciente, no recomendar produccion
    mask_sin_actividad = (ult['qty_fabricada_3m'].fillna(0) <= 0) & (ult['qty_planificada_3m'].fillna(0) <= 0)
    mask_no_reciente = ult['periodo'] < (max_periodo_global - pd.DateOffset(months=2))
    mask_recomendacion_cero = mask_sin_actividad | mask_no_reciente
    ult.loc[mask_recomendacion_cero, 'pronostico_qty'] = 0
    ult.loc[mask_recomendacion_cero, 'qty_recomendada'] = 0
    ult.loc[mask_recomendacion_cero, 'qty_min_recomendada'] = 0
    ult.loc[mask_recomendacion_cero, 'qty_max_recomendada'] = 0
    ult.loc[mask_recomendacion_cero, 'nivel_confianza'] = 'BAJA'

    ult['sugerencia_accion'] = np.select(
        [ult['nivel_confianza'] == 'ALTA', ult['nivel_confianza'] == 'MEDIA'],
        [
            'Planificar con el valor base; seguimiento operativo normal.',
            'Planificar con rango y validar con comercial y operaciones.',
        ],
        default='Revisar causas antes de cerrar plan y usar escenarios minimo/base/maximo.',
    )

    ult['posibles_causas'] = np.select(
        [ult['nivel_confianza'] == 'ALTA', ult['nivel_confianza'] == 'MEDIA'],
        [
            'Demanda estable; baja variabilidad historica reciente.',
            'Variacion moderada por mix de clientes, promociones o estacionalidad.',
        ],
        default='Alta volatilidad reciente; posibles promociones agresivas, quiebres de stock, cambios de precio o eventos atipicos.',
    )

    ult.loc[mask_sin_actividad, 'sugerencia_accion'] = 'Sin actividad en los ultimos 3 meses; validar si el producto sigue vigente antes de planificar.'
    ult.loc[mask_sin_actividad, 'posibles_causas'] = 'Producto inactivo o descontinuado temporalmente; no hay fabricacion ni planificacion reciente.'
    ult.loc[mask_no_reciente, 'sugerencia_accion'] = 'Ultimo movimiento fuera de ventana operativa; excluir de plan actual y revisar vigencia del SKU.'
    ult.loc[mask_no_reciente, 'posibles_causas'] = 'Producto historico o de baja rotacion; no tiene datos recientes para planificacion del siguiente ciclo.'

    ult['es_vigente_operativo'] = ~(mask_recomendacion_cero)
    ult['razon_vigencia'] = np.where(
        mask_no_reciente,
        'FUERA_VENTANA',
        np.where(mask_sin_actividad, 'SIN_ACTIVIDAD_3M', 'VIGENTE')
    )

    # Consistencia final de rango
    ult['qty_min_recomendada'] = np.minimum(ult['qty_min_recomendada'], ult['qty_recomendada'])
    ult['qty_max_recomendada'] = np.maximum(ult['qty_max_recomendada'], ult['qty_recomendada'])

    pred_cols = [
        'tipo_producto', 'categoria_producto', 'producto_base',
        'producto', 'periodo', 'periodo_prediccion',
        'qty_fabricada', 'qty_planificada', 'pronostico_qty', 'qty_recomendada',
        'qty_min_recomendada', 'qty_max_recomendada',
        'nivel_confianza', 'rolling_std_3', 'n_ordenes',
        'sugerencia_accion', 'posibles_causas',
        'es_vigente_operativo', 'razon_vigencia',
    ]
    predicciones = ult[pred_cols].copy()
    predicciones['pipeline_id'] = kwargs.get('pipeline_id', 'dm_analisis_desviaciones')

    serie_modelado = df[
        [
            'tipo_producto', 'categoria_producto', 'producto_base', 'producto',
            'periodo', 'qty_fabricada', 'qty_planificada', 'n_ordenes',
        ]
    ].drop_duplicates().copy()
    serie_modelado['pipeline_id'] = kwargs.get('pipeline_id', 'dm_analisis_desviaciones')

    metricas = pd.DataFrame(
        [
            {'metrica': 'MAE', 'valor_modelo': mae, 'valor_baseline': mae_baseline},
            {'metrica': 'RMSE', 'valor_modelo': rmse, 'valor_baseline': rmse_baseline},
            {'metrica': 'WAPE', 'valor_modelo': wape, 'valor_baseline': wape_baseline},
        ]
    )
    metricas['mejora_vs_baseline'] = metricas['valor_baseline'] - metricas['valor_modelo']
    metricas['pipeline_id'] = kwargs.get('pipeline_id', 'dm_analisis_desviaciones')

    importancia = pd.DataFrame(
        {'feature': features, 'importancia': model.feature_importances_}
    ).sort_values('importancia', ascending=False)
    importancia['pipeline_id'] = kwargs.get('pipeline_id', 'dm_analisis_desviaciones')

    print(f"\n{'='*70}")
    print("PRONOSTICO DE PRODUCCION - RESULTADOS")
    print(f"{'='*70}")
    print(f"Registros train: {len(X_train)} | test: {len(X_test)}")
    print(f"MAE modelo: {mae:.2f} | baseline: {mae_baseline:.2f}")
    print(f"RMSE modelo: {rmse:.2f} | baseline: {rmse_baseline:.2f}")
    print(f"WAPE modelo: {wape:.4f} | baseline: {wape_baseline:.4f}")
    print(f"Predicciones siguiente periodo: {len(predicciones)}")
    print(f"{'='*70}\n")

    return {
        'predicciones': predicciones,
        'metricas_modelo': metricas,
        'importancia_features': importancia,
        'serie_modelado': serie_modelado,
    }


@test
def test_output(output, *args) -> None:
    assert output is not None, 'Transformacion fallo'
    assert 'predicciones' in output, 'Falta salida de predicciones'
    assert 'metricas_modelo' in output, 'Faltan metricas'
    print('OK: Pronostico de produccion generado')
