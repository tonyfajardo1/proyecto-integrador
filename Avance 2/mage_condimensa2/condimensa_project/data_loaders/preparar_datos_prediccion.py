"""
Data Loader: Preparar datos para modelo predictivo de devoluciones.
Pipeline: dm_prediccion_devoluciones

En Avance 2 se prioriza control metodologico:
- unidad de analisis producto-periodo
- target futuro (t+1)
- evitamos leakage temporal al separar periodos
"""
from mage_ai.settings.repo import get_repo_path
from mage_ai.io.config import ConfigFileLoader
from mage_ai.io.postgres import Postgres
from os import path
import pandas as pd
import numpy as np

if 'data_loader' not in dir():
    from mage_ai.data_preparation.decorators import data_loader
if 'test' not in dir():
    from mage_ai.data_preparation.decorators import test


@data_loader
def preparar_datos_prediccion(*args, **kwargs):
    """
    Carga metricas de productos para modelo predictivo.
    Responde: ¿Que productos tienen alto riesgo de devolucion?
    """

    # Fuente principal: series por periodo desde kpis_ventas
    query_kpis = """
    SELECT
        producto,
        anio,
        mes,
        cant_venta,
        total_venta,
        cant_devolucion,
        total_devolucion,
        rentabilidad,
        prc_rentabilidad,
        fecha_calculo
    FROM gold.kpis_ventas
    WHERE producto IS NOT NULL
      AND anio IS NOT NULL
      AND mes IS NOT NULL
    """

    # Fallback: tabla agregada por producto (sin temporalidad suficiente)
    query_metricas = """
    SELECT
        producto,
        total_venta,
        total_devolucion,
        cant_venta,
        rentabilidad,
        tasa_devolucion,
        rentabilidad_promedio,
        fecha_calculo
    FROM gold.metricas_productos
    """

    config_path = path.join(get_repo_path(), 'io_config.yaml')
    config_profile = 'local_dwh'

    with Postgres.with_config(ConfigFileLoader(config_path, config_profile)) as loader:
        try:
            df = loader.load(query_kpis)
            origen = 'gold.kpis_ventas'
        except Exception:
            df = pd.DataFrame()
            origen = 'none'

        if len(df) == 0:
            df = loader.load(query_metricas)
            origen = 'gold.metricas_productos'

    print(f"[INFO] Datos cargados desde {origen}: {len(df)} registros")

    # =========================================================================
    # CREAR FEATURES PARA MODELO PREDICTIVO
    # =========================================================================

    if origen == 'gold.kpis_ventas':
        # Normalizar mes
        mes_map = {
            'ENERO': 1, 'FEBRERO': 2, 'MARZO': 3, 'ABRIL': 4,
            'MAYO': 5, 'JUNIO': 6, 'JULIO': 7, 'AGOSTO': 8,
            'SEPTIEMBRE': 9, 'SETIEMBRE': 9, 'OCTUBRE': 10,
            'NOVIEMBRE': 11, 'DICIEMBRE': 12
        }
        df['mes_num'] = df['mes'].astype(str).str.upper().map(mes_map)
        df['mes_num'] = pd.to_numeric(df['mes_num'], errors='coerce').fillna(1).astype(int)
        df['anio'] = pd.to_numeric(df['anio'], errors='coerce').fillna(0).astype(int)
        df['periodo_id'] = df['anio'] * 100 + df['mes_num']

        # Agregar por producto-periodo para evitar granularidad mezclada
        df = df.groupby(['producto', 'anio', 'mes_num', 'periodo_id'], as_index=False).agg({
            'cant_venta': 'sum',
            'total_venta': 'sum',
            'cant_devolucion': 'sum',
            'total_devolucion': 'sum',
            'rentabilidad': 'sum',
        })

        df['tasa_devolucion'] = np.where(
            df['total_venta'] > 0,
            (df['total_devolucion'] / df['total_venta']) * 100,
            0,
        )
        df['margen_rentabilidad'] = np.where(
            df['total_venta'] > 0,
            (df['rentabilidad'] / df['total_venta']) * 100,
            0,
        )

        # Target futuro (t+1) por producto
        df = df.sort_values(['producto', 'periodo_id']).reset_index(drop=True)
        df['tasa_devolucion_t1'] = df.groupby('producto')['tasa_devolucion'].shift(-1)
        df = df[df['tasa_devolucion_t1'].notna()].copy()
        df['target_devolucion_alta'] = (df['tasa_devolucion_t1'] > 10).astype(int)

        # Features disponibles al final de t
        df['log_cant_venta'] = np.log1p(df['cant_venta'])
        df['log_total_venta'] = np.log1p(df['total_venta'])
        df['ratio_costo'] = 100 - df['margen_rentabilidad']
        df['mes_encoded'] = df['mes_num']

        product_map = {p: i for i, p in enumerate(df['producto'].dropna().unique())}
        df['agencia_encoded'] = df['producto'].map(product_map).fillna(-1).astype(int)

        # Campos de salida compatibles
        df['centro_costo'] = df['producto']
        df['mes'] = df['mes_num']

    else:
        # Fallback conservador cuando no hay historia temporal
        df['tasa_devolucion'] = pd.to_numeric(df.get('tasa_devolucion', 0), errors='coerce').fillna(0)
        df['cant_venta'] = pd.to_numeric(df.get('cant_venta', 0), errors='coerce').fillna(0)
        df['total_venta'] = pd.to_numeric(df.get('total_venta', 0), errors='coerce').fillna(0)
        df['margen_rentabilidad'] = pd.to_numeric(df.get('rentabilidad_promedio', 0), errors='coerce').fillna(0)

        df['target_devolucion_alta'] = (df['tasa_devolucion'] > 10).astype(int)
        df['log_cant_venta'] = np.log1p(df['cant_venta'])
        df['log_total_venta'] = np.log1p(df['total_venta'])
        df['ratio_costo'] = 100 - df['margen_rentabilidad']
        df['mes_encoded'] = 0
        df['agencia_encoded'] = pd.factorize(df['producto'])[0]
        df['centro_costo'] = df['producto']
        df['periodo_id'] = 0
        df['mes'] = 0

    print(f"\n{'='*60}")
    print(f"DATOS PREPARADOS PARA MODELO PREDICTIVO")
    print(f"{'='*60}")
    print(f"Total productos: {len(df)}")
    print(f"Target (devolucion_alta): {df['target_devolucion_alta'].sum()} positivos ({df['target_devolucion_alta'].mean()*100:.1f}%)")
    if 'periodo_id' in df.columns:
        print(f"Periodos disponibles: {df['periodo_id'].nunique()}")
    print(f"\nFeatures:")
    print(f"  - agencia_encoded: {df['agencia_encoded'].nunique()} entidades")
    print(f"  - log_cant_venta: {df['log_cant_venta'].min():.2f} - {df['log_cant_venta'].max():.2f}")
    print(f"  - margen_rentabilidad: {df['margen_rentabilidad'].min():.2f}% - {df['margen_rentabilidad'].max():.2f}%")
    print(f"{'='*60}\n")

    return df


@test
def test_output(output, *args) -> None:
    assert output is not None, 'No se cargaron datos'
    assert 'target_devolucion_alta' in output.columns, 'Falta target'
    assert len(output) > 0, 'Tabla vacia'
    print(f"OK: {len(output)} productos preparados")
