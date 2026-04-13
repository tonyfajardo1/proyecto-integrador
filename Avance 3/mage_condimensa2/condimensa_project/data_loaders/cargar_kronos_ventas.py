"""
Data Loader: Cargar ventas desde Kronos (Supabase)
Pipeline: analisis_kronos_ventas
Limpia los datos que vienen de Excel y los estructura correctamente.
"""
from mage_ai.settings.repo import get_repo_path
from mage_ai.io.config import ConfigFileLoader
from mage_ai.io.postgres import Postgres
from os import path
import pandas as pd

if 'data_loader' not in dir():
    from mage_ai.data_preparation.decorators import data_loader
if 'test' not in dir():
    from mage_ai.data_preparation.decorators import test


@data_loader
def load_kronos_ventas(*args, **kwargs):
    """
    Carga datos de ventas desde Kronos en Supabase.
    Los datos vienen de un Excel, por lo que necesitan limpieza.
    """

    # Query para cargar todos los datos
    query = """
    SELECT
        distribuidora_la_cosecha_sas as col_0,
        "unnamed:_1" as col_1,
        "unnamed:_2" as col_2,
        "unnamed:_3" as col_3,
        "unnamed:_4" as col_4,
        "unnamed:_5" as col_5,
        "unnamed:_6" as col_6,
        "unnamed:_7" as col_7,
        "unnamed:_8" as col_8,
        "unnamed:_9" as col_9,
        "unnamed:_10" as col_10,
        "unnamed:_11" as col_11,
        "unnamed:_12" as col_12,
        "unnamed:_13" as col_13,
        "unnamed:_14" as col_14,
        "unnamed:_15" as col_15
    FROM kronos.ventas_general_4
    """

    config_path = path.join(get_repo_path(), 'io_config.yaml')
    config_profile = 'kronos'

    with Postgres.with_config(ConfigFileLoader(config_path, config_profile)) as loader:
        df_raw = loader.load(query)

    # =========================================================================
    # LIMPIEZA DE DATOS
    # =========================================================================

    # Encontrar la fila con los encabezados reales
    header_row = None
    for idx, row in df_raw.iterrows():
        if row['col_0'] == 'CENTRO_COSTO' or str(row['col_1']).upper() == 'CODIGO_PRODUCTO':
            header_row = idx
            break

    if header_row is None:
        # Buscar por contenido tipico
        for idx, row in df_raw.iterrows():
            if 'CENTRO' in str(row['col_0']).upper():
                header_row = idx
                break

    # Si encontramos los encabezados, usamos las filas siguientes como datos
    if header_row is not None:
        df_data = df_raw.iloc[header_row + 1:].copy()
    else:
        # Si no, saltamos las primeras 7 filas (tipico de este Excel)
        df_data = df_raw.iloc[7:].copy()

    # Renombrar columnas con nombres significativos
    df_data.columns = [
        'centro_costo',      # Agencia/Ciudad
        'codigo_producto',
        'codigo_alterno',    # Codigo de barras
        'producto',
        'cant_venta',        # Cantidad vendida
        'total_venta',       # Total venta $
        'cant_nc',           # Cantidad notas credito
        'total_nc',          # Total notas credito $
        'cant_devolucion',   # Cantidad devoluciones
        'total_devolucion',  # Total devoluciones $
        'cant_neto',         # Cantidad neta
        'total_neto',        # Total neto $
        'costo_venta',       # Costo de venta
        'rentabilidad',      # Valor rentabilidad $
        'prc_rentabilidad',  # Porcentaje rentabilidad
        'mes'                # Mes
    ]

    # Resetear indice
    df_data = df_data.reset_index(drop=True)

    # Filtrar filas vacias o que no sean datos reales
    df_data = df_data[df_data['centro_costo'].notna()]
    df_data = df_data[~df_data['centro_costo'].str.contains('CENTRO_COSTO|Total|^$', na=False, case=False)]

    # Convertir columnas numericas
    columnas_numericas = [
        'cant_venta', 'total_venta', 'cant_nc', 'total_nc',
        'cant_devolucion', 'total_devolucion', 'cant_neto', 'total_neto',
        'costo_venta', 'rentabilidad', 'prc_rentabilidad'
    ]

    for col in columnas_numericas:
        df_data[col] = pd.to_numeric(df_data[col], errors='coerce').fillna(0)

    # Limpiar texto
    df_data['centro_costo'] = df_data['centro_costo'].str.strip().str.lower()
    df_data['producto'] = df_data['producto'].str.strip()
    df_data['mes'] = df_data['mes'].str.strip().str.upper()

    print(f"\n{'='*60}")
    print(f"CARGA DE DATOS - KRONOS VENTAS")
    print(f"{'='*60}")
    print(f"Registros cargados: {len(df_data)}")
    print(f"Agencias encontradas: {df_data['centro_costo'].nunique()}")
    print(f"Productos unicos: {df_data['producto'].nunique()}")
    print(f"Meses: {df_data['mes'].unique().tolist()}")
    print(f"{'='*60}\n")

    return df_data


@test
def test_output(output, *args) -> None:
    """
    Verifica que los datos se cargaron correctamente
    """
    assert output is not None, 'No se cargaron datos'
    assert len(output) > 0, 'La tabla esta vacia'
    assert 'centro_costo' in output.columns, 'Falta columna centro_costo'
    assert 'cant_devolucion' in output.columns, 'Falta columna cant_devolucion'
    print(f"OK: Cargados {len(output)} registros de Kronos")
