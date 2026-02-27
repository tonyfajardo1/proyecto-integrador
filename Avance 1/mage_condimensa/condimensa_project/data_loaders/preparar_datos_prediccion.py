"""
Data Loader: Preparar datos para modelo predictivo
Pipeline: dm_prediccion_devoluciones
Prepara features y target para entrenar Random Forest.
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
    Carga datos desde Silver (ya limpios) para modelo predictivo.
    Target: devolucion_alta (tasa > 10%)
    """

    # Usar Silver layer del DWH local (datos ya limpios y transformados)
    query = """SELECT * FROM silver.kronos_ventas"""

    config_path = path.join(get_repo_path(), 'io_config.yaml')
    config_profile = 'local_dwh'

    with Postgres.with_config(ConfigFileLoader(config_path, config_profile)) as loader:
        df = loader.load(query)

    print(f"[INFO] Datos cargados desde Silver: {len(df)} registros")

    # Convertir numericos (por si acaso)
    cols_num = ['cant_venta', 'total_venta', 'cant_devolucion', 'total_devolucion',
                'cant_neto', 'total_neto', 'costo_venta', 'rentabilidad', 'prc_rentabilidad']
    for col in cols_num:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    if 'centro_costo' in df.columns:
        df['centro_costo'] = df['centro_costo'].astype(str).str.strip().str.lower()
    if 'mes' in df.columns:
        df['mes'] = df['mes'].astype(str).str.strip().str.upper()

    # =========================================================================
    # CREAR FEATURES PARA MODELO
    # =========================================================================

    # Target: devolucion alta (>10%)
    df['tasa_devolucion'] = np.where(
        df['cant_venta'] > 0,
        (df['cant_devolucion'] / df['cant_venta']) * 100,
        0
    )
    df['target_devolucion_alta'] = (df['tasa_devolucion'] > 10).astype(int)

    # Features numericos
    df['margen_rentabilidad'] = np.where(
        df['total_venta'] > 0,
        (df['rentabilidad'] / df['total_venta']) * 100,
        0
    )

    df['ratio_costo'] = np.where(
        df['total_venta'] > 0,
        (df['costo_venta'] / df['total_venta']) * 100,
        0
    )

    # Codificar agencia (label encoding simple)
    agencia_map = {ag: i for i, ag in enumerate(df['centro_costo'].unique())}
    df['agencia_encoded'] = df['centro_costo'].map(agencia_map)

    # Codificar mes
    mes_map = {'ENERO': 1, 'FEBRERO': 2, 'MARZO': 3, 'ABRIL': 4, 'MAYO': 5, 'JUNIO': 6,
               'JULIO': 7, 'AGOSTO': 8, 'SEPTIEMBRE': 9, 'OCTUBRE': 10, 'NOVIEMBRE': 11, 'DICIEMBRE': 12}
    df['mes_encoded'] = df['mes'].map(mes_map).fillna(0).astype(int)

    # Log de volumen (para normalizar)
    df['log_cant_venta'] = np.log1p(df['cant_venta'])
    df['log_total_venta'] = np.log1p(df['total_venta'])

    print(f"\n{'='*60}")
    print(f"DATOS PREPARADOS PARA MODELO PREDICTIVO")
    print(f"{'='*60}")
    print(f"Total registros: {len(df)}")
    print(f"Target (devolucion_alta): {df['target_devolucion_alta'].sum()} positivos ({df['target_devolucion_alta'].mean()*100:.1f}%)")
    print(f"Features: agencia_encoded, mes_encoded, log_cant_venta, margen_rentabilidad, ratio_costo")
    print(f"{'='*60}\n")

    return df


@test
def test_output(output, *args) -> None:
    assert output is not None, 'No se cargaron datos'
    assert 'target_devolucion_alta' in output.columns, 'Falta target'
    print(f"OK: {len(output)} registros preparados")
