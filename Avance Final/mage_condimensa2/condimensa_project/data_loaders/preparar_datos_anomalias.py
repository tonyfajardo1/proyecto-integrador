"""
Data Loader: Preparar datos para deteccion de anomalias
Pipeline: dm_deteccion_anomalias
Carga metricas de agencias para detectar comportamientos atipicos.
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
def preparar_datos_anomalias(*args, **kwargs):
    """
    Carga metricas agregadas por agencia para deteccion de anomalias.
    Responde: ¿Que agencias tienen comportamiento anomalo?
    """

    # Cargar metricas de agencias
    query = """
    SELECT
        centro_costo,
        total_venta,
        total_devolucion,
        total_neto,
        ticket_promedio,
        tasa_devolucion,
        rentabilidad_promedio,
        cant_venta
    FROM gold.metricas_agencias
    """

    config_path = path.join(get_repo_path(), 'io_config.yaml')
    config_profile = 'local_dwh'

    with Postgres.with_config(ConfigFileLoader(config_path, config_profile)) as loader:
        df = loader.load(query)

    print(f"[INFO] Datos cargados desde gold.metricas_agencias: {len(df)} registros")

    # Renombrar columnas para compatibilidad con el transformer
    df = df.rename(columns={
        'centro_costo': 'agencia',
        'tasa_devolucion': 'ratio_devolucion',
        'rentabilidad_promedio': 'ratio_rentabilidad',
        'total_venta': 'total_ventas',
    })

    # Normalizacion de entidad
    if 'agencia' in df.columns:
        df['agencia'] = df['agencia'].astype(str).str.strip().str.lower()
        df = df[(df['agencia'] != '') & (df['agencia'].str.lower() != 'nan')].copy()

    # Calcular ratio de costo (si no existe)
    if 'ratio_costo' not in df.columns:
        df['ratio_costo'] = 100 - df['ratio_rentabilidad']

    # Depuracion minima de nulos para modelo
    for col in ['ratio_devolucion', 'ratio_rentabilidad', 'ratio_costo', 'ticket_promedio', 'total_ventas']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # Consolidar posibles duplicados por agencia (si existieran por multiples corridas)
    if 'agencia' in df.columns and df['agencia'].duplicated().any():
        agg_cols = {
            'ratio_devolucion': 'mean',
            'ratio_rentabilidad': 'mean',
            'ratio_costo': 'mean',
            'ticket_promedio': 'mean',
            'total_ventas': 'sum',
            'cant_venta': 'sum',
        }
        agg_cols = {k: v for k, v in agg_cols.items() if k in df.columns}
        before = len(df)
        df = df.groupby('agencia', as_index=False).agg(agg_cols)
        print(f"[INFO] Duplicados por agencia consolidados: {before - len(df)}")

    print(f"\n{'='*60}")
    print(f"DATOS PREPARADOS PARA DETECCION DE ANOMALIAS")
    print(f"{'='*60}")
    print(f"Agencias analizadas: {len(df)}")
    print(f"\nAgencias unicas: {df['agencia'].nunique()}")
    if 'cant_venta' in df.columns:
        print(f"Transacciones totales aproximadas: {pd.to_numeric(df['cant_venta'], errors='coerce').fillna(0).sum():.0f}")
    print(f"\nFeatures para deteccion:")
    print(f"  - ratio_devolucion: {df['ratio_devolucion'].min():.2f}% - {df['ratio_devolucion'].max():.2f}%")
    print(f"  - ratio_rentabilidad: {df['ratio_rentabilidad'].min():.2f}% - {df['ratio_rentabilidad'].max():.2f}%")
    print(f"  - ticket_promedio: ${df['ticket_promedio'].min():.2f} - ${df['ticket_promedio'].max():.2f}")
    print(f"{'='*60}\n")

    return df


@test
def test_output(output, *args) -> None:
    assert output is not None, 'No se cargaron datos'
    assert len(output) > 0, 'Tabla vacia'
    assert 'ratio_devolucion' in output.columns, 'Falta ratio_devolucion'
    assert 'ratio_rentabilidad' in output.columns, 'Falta ratio_rentabilidad'
    print(f"OK: {len(output)} agencias preparadas para analisis")
