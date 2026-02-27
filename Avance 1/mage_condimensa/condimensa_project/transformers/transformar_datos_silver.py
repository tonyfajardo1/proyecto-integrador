"""
Transformer: Limpiar y transformar datos de Bronze a Silver
Pipeline: etl_silver
"""
import pandas as pd
import numpy as np
from datetime import datetime

if 'transformer' not in dir():
    from mage_ai.data_preparation.decorators import transformer
if 'test' not in dir():
    from mage_ai.data_preparation.decorators import test


@transformer
def transformar_kronos_silver(data, *args, **kwargs):
    """
    Transforma datos crudos de Bronze a Silver.
    Los datos de Kronos vienen de un Excel con formato especial.
    """

    dfs = data.get('dfs', {})
    batch_id = data.get('batch_id')
    pipeline_id = data.get('pipeline_id')

    print(f"\n{'='*70}")
    print(f"TRANSFORMACION - BRONZE A SILVER")
    print(f"{'='*70}\n")

    resultados = {}

    # Buscar la tabla de ventas
    key_ventas = None
    for key in dfs.keys():
        if 'ventas' in key.lower() or 'kronos' in key.lower():
            key_ventas = key
            break

    if key_ventas:
        print(f"[1] Transformando {key_ventas}...")

        dato = dfs[key_ventas]

        # Convertir a DataFrame
        if isinstance(dato, list):
            df_raw = pd.DataFrame(dato)
        elif isinstance(dato, pd.DataFrame):
            df_raw = dato.copy()
        else:
            df_raw = pd.DataFrame()

        print(f"    Filas iniciales: {len(df_raw)}")
        print(f"    Columnas: {df_raw.columns.tolist()}")

        # =========================================================================
        # 1. BUSCAR FILA DE ENCABEZADOS REALES
        # El archivo Excel de Kronos tiene:
        # - Filas 0-6: Titulos del reporte
        # - Fila 7: Encabezados reales (CENTRO_COSTO, CODIGO_PRODUCTO, etc.)
        # - Fila 8+: Datos
        # =========================================================================

        header_row = None
        col_busqueda = df_raw.columns[0] if len(df_raw.columns) > 0 else None

        if col_busqueda:
            for idx in range(min(50, len(df_raw))):
                try:
                    val = str(df_raw.iloc[idx][col_busqueda]).upper().strip() if pd.notna(df_raw.iloc[idx][col_busqueda]) else ''
                    # Buscar EXACTAMENTE "CENTRO_COSTO" (no solo "CENTRO")
                    if val == 'CENTRO_COSTO':
                        header_row = idx
                        print(f"    Encabezado encontrado en fila {idx}: '{val}'")
                        break
                except:
                    continue

        # Si no encontramos CENTRO_COSTO exacto, buscar por patron de columnas
        if header_row is None:
            print(f"    [INFO] Buscando encabezados por patron...")
            for idx in range(min(50, len(df_raw))):
                try:
                    # Verificar si esta fila tiene aspecto de encabezados
                    row_values = [str(df_raw.iloc[idx][c]).upper().strip() for c in df_raw.columns[:4]]
                    # Los encabezados reales tienen valores cortos y especificos
                    if any('CENTRO' in v and len(v) < 20 for v in row_values):
                        if any('CODIGO' in v or 'PRODUCTO' in v for v in row_values):
                            header_row = idx
                            print(f"    Encabezado encontrado por patron en fila {idx}")
                            break
                except:
                    continue

        # =========================================================================
        # 2. CREAR DATAFRAME CON DATOS LIMPIOS
        # =========================================================================

        if header_row is not None:
            # Obtener encabezados
            encabezados = []
            for c in df_raw.columns:
                val = df_raw.iloc[header_row][c]
                enc = str(val).strip().upper() if pd.notna(val) else f'COL_{c}'
                encabezados.append(enc)

            print(f"    Encabezados detectados: {encabezados[:8]}")

            # Crear nuevo DataFrame con datos (filas despues del encabezado)
            df = df_raw.iloc[header_row + 1:].copy()
            df.columns = encabezados

            # Limpiar filas vacias y totales
            df = df.replace('', np.nan)
            df = df.dropna(how='all')

            # Filtrar filas que son totales o subtotales
            first_col = df.columns[0]
            df = df[~df[first_col].astype(str).str.contains('Total|TOTAL|Subtotal', na=False, case=False)]
            df = df[df[first_col].notna()]

            print(f"    Filas de datos: {len(df)}")
        else:
            print(f"    [WARN] No se encontraron encabezados, usando estructura por defecto")
            df = df_raw.iloc[7:].copy()  # Saltar las 7 primeras filas tipicas
            df.columns = ['CENTRO_COSTO', 'CODIGO_PRODUCTO', 'ALTERNO', 'PRODUCTO',
                         'CANT_VENTA', 'TOTAL_VENTA', 'CANT_NC', 'TOTAL_NC',
                         'CANT_DEVOLUCION', 'TOTAL_DEVOLUCION', 'CANT_NETO', 'TOTAL_NETO',
                         'COSTO_VENTA', 'RENTABILIDAD', 'PRC_RENTABILIDAD', 'MES'][:len(df.columns)]

        # =========================================================================
        # 3. MAPEAR COLUMNAS A NOMBRES ESTANDAR
        # El archivo Kronos tiene columnas en orden especifico.
        # Usamos mapeo EXACTO para evitar duplicados.
        # =========================================================================

        # Mapeo EXACTO (sin coincidencias parciales)
        mapeo_exacto = {
            'CENTRO_COSTO': 'centro_costo',
            'CENTRO COSTO': 'centro_costo',
            'CODIGO_PRODUCTO': 'codigo_producto',
            'CODIGO PRODUCTO': 'codigo_producto',
            'ALTERNO': 'codigo_alterno',
            'CODIGO_ALTERNO': 'codigo_alterno',
            'CODIGO ALTERNO': 'codigo_alterno',
            'PRODUCTO': 'producto',
            'NOMBRE': 'producto',
            'NOMBRE_PRODUCTO': 'producto',
            # Columnas de cantidad - EXACTAS
            'CANT': 'cant_venta',
            'CANT_VENTA': 'cant_venta',
            'CANT VENTA': 'cant_venta',
            'CANTIDAD': 'cant_venta',
            'CANT NC': 'cant_nc',
            'CANT_NC': 'cant_nc',
            'CANT DV': 'cant_devolucion',
            'CANT_DV': 'cant_devolucion',
            'CANT DEVOLUCION': 'cant_devolucion',
            'CANT_DEVOLUCION': 'cant_devolucion',
            'CANT NC DV': 'cant_devolucion',
            'CANT_NC_DV': 'cant_devolucion',
            'CANT NETO': 'cant_neto',
            'CANT_NETO': 'cant_neto',
            # Columnas de totales - EXACTAS
            'TOTAL': 'total_venta',
            'TOTAL_VENTA': 'total_venta',
            'TOTAL VENTA': 'total_venta',
            'VENTA': 'total_venta',
            'TOTAL NC': 'total_nc',
            'TOTAL_NC': 'total_nc',
            'TOTAL DV': 'total_devolucion',
            'TOTAL_DV': 'total_devolucion',
            'TOTAL DEVOLUCION': 'total_devolucion',
            'TOTAL_DEVOLUCION': 'total_devolucion',
            'TOTAL NC DV': 'total_devolucion',
            'TOTAL_NC_DV': 'total_devolucion',
            'TOTAL NETO': 'total_neto',
            'TOTAL_NETO': 'total_neto',
            'NETO': 'total_neto',
            # Otras columnas
            'COSTO': 'costo_venta',
            'COSTO_VENTA': 'costo_venta',
            'COSTO VENTA': 'costo_venta',
            'RENTABILIDAD': 'rentabilidad',
            'RENT': 'rentabilidad',
            'PRC_RENTABILIDAD': 'prc_rentabilidad',
            'PRC RENTABILIDAD': 'prc_rentabilidad',
            '% RENT': 'prc_rentabilidad',
            '%RENT': 'prc_rentabilidad',
            'MARGEN': 'prc_rentabilidad',
            'MES': 'mes'
        }

        # Mapear solo con coincidencias EXACTAS
        rename_dict = {}
        columnas_ya_mapeadas = set()

        for col in df.columns:
            col_upper = str(col).upper().strip()
            if col_upper in mapeo_exacto:
                destino = mapeo_exacto[col_upper]
                # Evitar duplicados - si ya mapeamos a este destino, agregar sufijo
                if destino in columnas_ya_mapeadas:
                    print(f"    [WARN] Columna duplicada ignorada: {col} -> {destino}")
                    continue
                rename_dict[col] = destino
                columnas_ya_mapeadas.add(destino)

        df = df.rename(columns=rename_dict)

        print(f"    Columnas mapeadas: {list(rename_dict.values())}")

        print(f"    Columnas finales: {df.columns.tolist()[:10]}")

        # =========================================================================
        # 4. CONVERTIR COLUMNAS NUMERICAS
        # =========================================================================

        columnas_numericas = ['cant_venta', 'total_venta', 'cant_nc', 'total_nc',
                             'cant_devolucion', 'total_devolucion', 'cant_neto', 'total_neto',
                             'costo_venta', 'rentabilidad', 'prc_rentabilidad']

        for col in columnas_numericas:
            if col in df.columns:
                try:
                    df[col] = df[col].astype(str)
                    df[col] = df[col].str.replace(',', '').str.replace('$', '').str.replace('%', '').str.strip()
                    df[col] = df[col].replace(['nan', 'None', '', 'NaN'], '0')
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                except Exception as e:
                    print(f"    [WARN] Error convirtiendo {col}: {e}")
                    df[col] = 0.0
            else:
                df[col] = 0.0

        # =========================================================================
        # 5. CALCULOS ADICIONALES
        # =========================================================================

        # Si no hay cant_neto, calcularlo
        if df['cant_neto'].sum() == 0 and df['cant_venta'].sum() > 0:
            df['cant_neto'] = df['cant_venta'] - df['cant_devolucion']

        if df['total_neto'].sum() == 0 and df['total_venta'].sum() > 0:
            df['total_neto'] = df['total_venta'] - df['total_devolucion']

        # Calcular rentabilidad si no existe
        if df['rentabilidad'].sum() == 0:
            df['rentabilidad'] = df['total_neto'] - df['costo_venta']

        # Calcular porcentaje de rentabilidad
        df['prc_rentabilidad'] = np.where(
            df['total_neto'] > 0,
            (df['rentabilidad'] / df['total_neto']) * 100,
            0
        )

        # =========================================================================
        # 6. AGREGAR METADATOS
        # =========================================================================

        df['es_dato_calidado'] = True
        df['flag_outlier'] = False
        df['flag_valor_nulo'] = df.isnull().any(axis=1)
        df['fecha_carga'] = datetime.now()

        # Columnas finales para Silver
        columnas_finales = [
            'centro_costo', 'codigo_producto', 'codigo_alterno', 'producto', 'mes',
            'cant_venta', 'total_venta', 'cant_nc', 'total_nc',
            'cant_devolucion', 'total_devolucion', 'cant_neto', 'total_neto',
            'costo_venta', 'rentabilidad', 'prc_rentabilidad',
            'es_dato_calidado', 'flag_outlier', 'flag_valor_nulo', 'fecha_carga'
        ]

        # Asegurar que todas las columnas existen
        for col in columnas_finales:
            if col not in df.columns:
                df[col] = None

        df_export = df[columnas_finales].copy()
        df_export['pipeline_id'] = pipeline_id
        df_export['batch_id'] = batch_id

        # Estadisticas
        print(f"\n    === RESUMEN ===")
        print(f"    Registros finales: {len(df_export)}")
        print(f"    Centros de costo unicos: {df_export['centro_costo'].nunique()}")
        print(f"    Productos unicos: {df_export['producto'].nunique()}")
        print(f"    Total ventas: ${df_export['total_venta'].sum():,.2f}")

        resultados['kronos_ventas'] = df_export
    else:
        print("[WARN] No se encontro tabla de ventas Kronos en los datos")

    # =========================================================================
    # TRANSFORMAR: QuickBooks Produccion
    # =========================================================================

    if 'quickbooks_produccion_raw' in dfs:
        print(f"\n[2] Transformando quickbooks_produccion_raw...")

        df_prod = dfs['quickbooks_produccion_raw']
        if isinstance(df_prod, list):
            df_prod = pd.DataFrame(df_prod)
        elif isinstance(df_prod, pd.DataFrame):
            df_prod = df_prod.copy()
        else:
            df_prod = pd.DataFrame()

        if len(df_prod) > 0:
            print(f"    Filas iniciales: {len(df_prod)}")

            # Convertir columnas numericas
            for col in ['numitems', 'numitemsprocesados', 'num_lineas', 'qty_planificada', 'qty_despachada']:
                if col in df_prod.columns:
                    df_prod[col] = pd.to_numeric(df_prod[col], errors='coerce').fillna(0)

            # Calcular desviacion
            df_prod['desviacion_absoluta'] = df_prod['qty_planificada'] - df_prod['qty_despachada']
            df_prod['desviacion_porcentual'] = np.where(
                df_prod['qty_planificada'] > 0,
                (df_prod['desviacion_absoluta'] / df_prod['qty_planificada']) * 100,
                0
            )
            df_prod['tasa_cumplimiento'] = np.where(
                df_prod['qty_planificada'] > 0,
                (df_prod['qty_despachada'] / df_prod['qty_planificada']) * 100,
                0
            )

            # Clasificar cumplimiento
            def clasificar_cumplimiento(tasa):
                if tasa >= 95:
                    return 'OPTIMO'
                elif tasa >= 80:
                    return 'ACEPTABLE'
                elif tasa >= 50:
                    return 'DEFICIENTE'
                else:
                    return 'CRITICO'

            df_prod['clasificacion_cumplimiento'] = df_prod['tasa_cumplimiento'].apply(clasificar_cumplimiento)

            # Metadatos
            df_prod['es_dato_calidado'] = True
            df_prod['fecha_carga'] = datetime.now()
            df_prod['pipeline_id'] = pipeline_id
            df_prod['batch_id'] = batch_id

            resultados['quickbooks_produccion'] = df_prod
            print(f"    Registros finales: {len(df_prod)}")
            print(f"    Tasa cumplimiento promedio: {df_prod['tasa_cumplimiento'].mean():.2f}%")

    # =========================================================================
    # TRANSFORMAR: QuickBooks Ventas
    # =========================================================================

    if 'quickbooks_ventas_raw' in dfs:
        print(f"\n[3] Transformando quickbooks_ventas_raw...")

        df_ventas = dfs['quickbooks_ventas_raw']
        if isinstance(df_ventas, list):
            df_ventas = pd.DataFrame(df_ventas)
        elif isinstance(df_ventas, pd.DataFrame):
            df_ventas = df_ventas.copy()
        else:
            df_ventas = pd.DataFrame()

        if len(df_ventas) > 0:
            print(f"    Filas iniciales: {len(df_ventas)}")

            # Convertir columnas numericas
            for col in ['numitems', 'numitemsprocesados', 'num_lineas', 'productos_unicos', 'qty_pedida', 'qty_despachada']:
                if col in df_ventas.columns:
                    df_ventas[col] = pd.to_numeric(df_ventas[col], errors='coerce').fillna(0)

            # Calcular metricas
            df_ventas['qty_pendiente'] = df_ventas['qty_pedida'] - df_ventas['qty_despachada']
            df_ventas['tasa_cumplimiento'] = np.where(
                df_ventas['qty_pedida'] > 0,
                (df_ventas['qty_despachada'] / df_ventas['qty_pedida']) * 100,
                0
            )

            # Metadatos
            df_ventas['es_dato_calidado'] = True
            df_ventas['fecha_carga'] = datetime.now()
            df_ventas['pipeline_id'] = pipeline_id
            df_ventas['batch_id'] = batch_id

            resultados['quickbooks_ventas'] = df_ventas
            print(f"    Registros finales: {len(df_ventas)}")
            print(f"    Qty total pedida: {df_ventas['qty_pedida'].sum():,.0f}")
            print(f"    Qty total despachada: {df_ventas['qty_despachada'].sum():,.0f}")

    # =========================================================================
    # RESUMEN FINAL
    # =========================================================================

    print(f"\n{'='*70}")
    print(f"RESUMEN TRANSFORMACION SILVER")
    print(f"{'='*70}")
    for tabla, df in resultados.items():
        print(f"  {tabla}: {len(df)} registros")
    print(f"{'='*70}\n")

    return {
        'dfs': resultados,
        'pipeline_id': pipeline_id,
        'batch_id': batch_id,
        'metadata': data.get('metadata', {})
    }


@test
def test_output(output, *args) -> None:
    assert output is not None, 'Output es None'
    assert 'dfs' in output, 'Falta dfs en output'
    if len(output['dfs']) > 0:
        print(f"OK: Transformacion completada con {len(output['dfs'])} tablas")
    else:
        print("WARN: No se transformaron datos")
