"""
Data Loader: Cargar datos comerciales de Kronos para analisis
Pipeline: dm_analisis_comercial_kronos
Pregunta: Cual es el rendimiento comercial por agencia y producto?
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
def cargar_datos_comercial(*args, **kwargs):
    """
    Carga datos de ventas comerciales desde silver.kronos_ventas
    para analisis de rendimiento por agencia y producto.
    """

    query = """
    SELECT
        centro_costo,
        codigo_producto,
        producto,
        mes,
        anio,
        CAST(NULLIF(cant_venta, '') AS NUMERIC) as cant_venta,
        CAST(NULLIF(total_venta, '') AS NUMERIC) as total_venta,
        CAST(NULLIF(cant_devolucion, '') AS NUMERIC) as cant_devolucion,
        CAST(NULLIF(total_devolucion, '') AS NUMERIC) as total_devolucion,
        cant_neto,
        total_neto,
        CAST(NULLIF(costo_venta, '') AS NUMERIC) as costo_venta,
        rentabilidad,
        prc_rentabilidad
    FROM silver.kronos_ventas
    WHERE es_dato_calidado = true
    """

    config_path = path.join(get_repo_path(), 'io_config.yaml')
    config_profile = 'local_dwh'

    with Postgres.with_config(ConfigFileLoader(config_path, config_profile)) as loader:
        df = loader.load(query)

    print(f"\n{'='*70}")
    print(f"CARGA DE DATOS COMERCIALES - KRONOS")
    print(f"{'='*70}")
    print(f"Registros cargados: {len(df)}")

    # Convertir a numerico y limpiar
    cols_num = ['cant_venta', 'total_venta', 'cant_devolucion', 'total_devolucion',
                'cant_neto', 'total_neto', 'costo_venta', 'rentabilidad', 'prc_rentabilidad']

    for col in cols_num:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # Limpiar texto
    df['centro_costo'] = df['centro_costo'].astype(str).str.strip().str.upper()
    df['mes'] = df['mes'].astype(str).str.strip().str.upper()
    df['producto'] = df['producto'].astype(str).str.strip()

    # =========================================================================
    # CALCULAR METRICAS COMERCIALES
    # =========================================================================

    # Tasa de devolucion
    df['tasa_devolucion'] = np.where(
        df['cant_venta'] > 0,
        (df['cant_devolucion'] / df['cant_venta']) * 100,
        0
    )

    # Margen de rentabilidad sobre venta
    df['margen_rentabilidad'] = np.where(
        df['total_venta'] > 0,
        (df['rentabilidad'] / df['total_venta']) * 100,
        0
    )

    # Ticket promedio por unidad
    df['precio_unitario'] = np.where(
        df['cant_venta'] > 0,
        df['total_venta'] / df['cant_venta'],
        0
    )

    # Costo unitario
    df['costo_unitario'] = np.where(
        df['cant_venta'] > 0,
        df['costo_venta'] / df['cant_venta'],
        0
    )

    # Clasificar rendimiento
    def clasificar_rendimiento(row):
        if row['prc_rentabilidad'] >= 40:
            return 'EXCELENTE'
        elif row['prc_rentabilidad'] >= 30:
            return 'BUENO'
        elif row['prc_rentabilidad'] >= 20:
            return 'REGULAR'
        else:
            return 'BAJO'

    df['categoria_rendimiento'] = df.apply(clasificar_rendimiento, axis=1)

    # Clasificar tasa devolucion
    df['nivel_devolucion'] = pd.cut(
        df['tasa_devolucion'],
        bins=[-np.inf, 5, 10, 20, np.inf],
        labels=['BAJO', 'MODERADO', 'ALTO', 'CRITICO']
    )

    # Extraer categoria de producto (primera palabra antes del parentesis)
    df['categoria_producto'] = df['producto'].apply(
        lambda x: x.split('(')[0].strip()[:30] if '(' in str(x) else str(x)[:30]
    )

    # =========================================================================
    # ESTADISTICAS
    # =========================================================================

    print(f"\n[METRICAS CALCULADAS]")
    print(f"  - Agencias: {df['centro_costo'].nunique()}")
    print(f"  - Productos: {df['producto'].nunique()}")
    print(f"  - Total ventas: ${df['total_venta'].sum():,.2f}")
    print(f"  - Total rentabilidad: ${df['rentabilidad'].sum():,.2f}")
    print(f"  - Margen promedio: {df['prc_rentabilidad'].mean():.2f}%")

    print(f"\n[DISTRIBUCION POR RENDIMIENTO]")
    print(df['categoria_rendimiento'].value_counts().to_string())

    print(f"\n[VENTAS POR AGENCIA]")
    ventas_agencia = df.groupby('centro_costo')['total_venta'].sum().sort_values(ascending=False)
    print(ventas_agencia.head(5).to_string())

    print(f"\n{'='*70}\n")

    return df


@test
def test_output(output, *args) -> None:
    assert output is not None, 'No se cargaron datos'
    assert len(output) > 0, 'DataFrame vacio'
    assert 'centro_costo' in output.columns, 'Falta columna centro_costo'
    print(f"OK: {len(output)} registros comerciales cargados")
