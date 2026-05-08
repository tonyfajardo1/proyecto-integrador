"""
Transformer: Limpiar y transformar datos de Bronze a Silver
Pipeline: etl_silver
"""
import pandas as pd
import numpy as np
import re
from datetime import datetime

if 'transformer' not in dir():
    from mage_ai.data_preparation.decorators import transformer
if 'test' not in dir():
    from mage_ai.data_preparation.decorators import test


@transformer
def transformar_kronos_silver(data, *args, **kwargs):
    """
    Transforma datos crudos de Bronze a Silver.

    Guia de exposicion por bloques:
    [0] Kronos resumen normalizado (prioridad para KPI comercial)
    [1] Kronos detalle (fallback de parsing cuando no hay resumen)
    [2] QuickBooks produccion (cumplimiento de ordenes)
    [3] QuickBooks ventas (consolidacion por venta)
    [4] Transacciones para Apriori (canasta de compra)
    [5] Catalogo EAN limpio (homologacion)
    [6] Ventas mensuales limpias (serie temporal)
    [7] Dimension canonica + base de forecasting

    Cada bloque estandariza esquema, corrige tipos y agrega metadatos para
    trazabilidad (`pipeline_id`, `batch_id`, `fecha_carga`).
    """

    dfs = data.get('dfs', {})
    batch_id = data.get('batch_id')
    pipeline_id = data.get('pipeline_id')

    print(f"\n{'='*70}")
    print(f"TRANSFORMACION - BRONZE A SILVER")
    print(f"{'='*70}\n")

    resultados = {}

    def parse_numeric_robusto(series):
        """Convierte texto numerico mixto (., ,, miles, cientifica) a float."""
        if series is None:
            return pd.Series(dtype='float64')

        def _parse_one(value):
            if pd.isna(value):
                return np.nan
            if isinstance(value, (int, float, np.number)):
                return float(value)

            s = str(value).strip()
            if not s:
                return np.nan

            s_up = s.upper()
            if s_up in {'NULL', 'NONE', 'NAN'}:
                return np.nan

            s_norm = s.replace(' ', '').replace(',', '.')

            try:
                if 'E' in s_norm.upper():
                    return float(s_norm)

                if s_norm.count('.') > 1:
                    parts = s_norm.split('.')
                    s_norm = ''.join(parts[:-1]) + '.' + parts[-1]

                return float(s_norm)
            except Exception:
                return np.nan

        return series.apply(_parse_one)

    # =========================================================================
    # 0. FUENTE PRIORITARIA: KRONOS RESUMEN NORMALIZADO (EXCEL)
    # =========================================================================
    if 'kronos_ventas_resumen_raw' in dfs:
        print("[0] Transformando kronos_ventas_resumen_raw (prioridad para KPIs)...")

        df_res = dfs['kronos_ventas_resumen_raw']
        if isinstance(df_res, list):
            df_res = pd.DataFrame(df_res)
        elif isinstance(df_res, pd.DataFrame):
            df_res = df_res.copy()
        else:
            df_res = pd.DataFrame()

        if len(df_res) > 0:
            mapeo = {
                'centro_costo': 'centro_costo',
                'codigo_producto': 'codigo_producto',
                'codigo_alterno': 'codigo_alterno',
                'producto': 'producto',
                'mes': 'mes',
                'anio': 'anio',
                'cant_venta': 'cant_venta',
                'total_venta': 'total_venta',
                'cant_nc': 'cant_nc',
                'total_nc': 'total_nc',
                'cant_devolucion': 'cant_devolucion',
                'total_devolucion': 'total_devolucion',
                'cant_neto': 'cant_neto',
                'total_neto': 'total_neto',
                'costo_venta': 'costo_venta',
                'rentabilidad': 'rentabilidad',
                'prc_rentabilidad': 'prc_rentabilidad',
            }

            for col in mapeo.keys():
                if col not in df_res.columns:
                    df_res[col] = None

            df_k = df_res[list(mapeo.keys())].copy()

            for col in [
                'cant_venta', 'total_venta', 'cant_nc', 'total_nc',
                'cant_devolucion', 'total_devolucion', 'cant_neto', 'total_neto',
                'costo_venta', 'rentabilidad', 'prc_rentabilidad',
            ]:
                df_k[col] = parse_numeric_robusto(df_k[col]).fillna(0)

            df_k['anio'] = pd.to_numeric(df_k['anio'], errors='coerce').fillna(2026).astype(int)
            df_k['mes'] = df_k['mes'].astype(str).str.upper().str.strip()
            df_k['centro_costo'] = df_k['centro_costo'].astype(str).str.strip()
            df_k['codigo_producto'] = df_k['codigo_producto'].astype(str).str.strip()
            df_k['codigo_alterno'] = df_k['codigo_alterno'].astype(str).str.strip()
            df_k['producto'] = df_k['producto'].astype(str).str.strip()

            df_k = df_k[df_k['mes'].notna() & (df_k['mes'] != '') & (df_k['mes'] != 'NAN')].copy()
            df_k = df_k[df_k['producto'].notna() & (df_k['producto'] != '') & (df_k['producto'] != 'NAN')].copy()

            df_k = (
                df_k.groupby(
                    ['centro_costo', 'codigo_producto', 'codigo_alterno', 'producto', 'mes', 'anio'],
                    as_index=False,
                )
                .sum(numeric_only=True)
            )

            devolucion_excede_venta = (
                (df_k['cant_devolucion'] > df_k['cant_venta'])
                | (df_k['total_devolucion'] > df_k['total_venta'])
            )
            neto_negativo = (df_k['cant_neto'] < 0) | (df_k['total_neto'] < 0)

            df_k['es_dato_calidado'] = True
            df_k['flag_outlier'] = devolucion_excede_venta | neto_negativo
            df_k['flag_valor_nulo'] = False
            df_k['fecha_carga'] = datetime.now()
            df_k['pipeline_id'] = pipeline_id
            df_k['batch_id'] = batch_id

            resultados['kronos_ventas'] = df_k
            print(f"    kronos_ventas desde resumen normalizado: {len(df_k)}")

    # =========================================================================
    # 0. NUEVA FUENTE KRONOS TRANSACCIONAL (detalle factura-item)
    # =========================================================================
    if 'kronos_ventas_detalle_raw' in dfs and 'kronos_ventas' not in resultados:
        print("[0] Transformando kronos_ventas_detalle_raw (transaccional)...")

        df_det = dfs['kronos_ventas_detalle_raw']
        if isinstance(df_det, list):
            df_det = pd.DataFrame(df_det)
        elif isinstance(df_det, pd.DataFrame):
            df_det = df_det.copy()
        else:
            df_det = pd.DataFrame()

        if len(df_det) > 0:
            # Normalizar tipos
            for col in ['cantidad', 'valor_unitario', 'valor_total', 'costo', 'descuento']:
                if col in df_det.columns:
                    df_det[col] = parse_numeric_robusto(df_det[col]).fillna(0)
                else:
                    df_det[col] = 0

            if 'fecha_factura' in df_det.columns:
                df_det['fecha_factura'] = pd.to_datetime(df_det['fecha_factura'], errors='coerce')
            else:
                df_det['fecha_factura'] = pd.NaT

            # Filtrar filas utiles
            df_det = df_det[df_det['fecha_factura'].notna()].copy()
            df_det['tipo'] = df_det.get('tipo', '').astype(str).str.upper().str.strip()

            # Campos base
            df_det['centro_costo'] = df_det.get('id_sucursal', '').astype(str)
            df_det['codigo_producto'] = df_det.get('codigo_producto', '').astype(str)
            df_det['codigo_alterno'] = df_det.get('id_producto', '').astype(str)
            df_det['producto'] = df_det.get('descripcion_producto', '').astype(str)
            df_det['mes'] = df_det['fecha_factura'].dt.month.map({
                1: 'ENERO', 2: 'FEBRERO', 3: 'MARZO', 4: 'ABRIL', 5: 'MAYO', 6: 'JUNIO',
                7: 'JULIO', 8: 'AGOSTO', 9: 'SEPTIEMBRE', 10: 'OCTUBRE', 11: 'NOVIEMBRE', 12: 'DICIEMBRE'
            })
            df_det['anio'] = df_det['fecha_factura'].dt.year

            # Separar por tipo de documento
            is_factura = df_det['tipo'].str.contains('FACTURA', na=False)
            is_nc = df_det['tipo'].str.contains('NC', na=False)

            # En esta fuente, cantidad suele venir escalada x100 (100=1 unidad).
            mask_qty_x100 = (np.abs(df_det['cantidad']) >= 100) & ((np.abs(df_det['cantidad']) % 100) < 1e-9)
            df_det['cantidad_norm'] = np.where(mask_qty_x100, df_det['cantidad'] / 100, df_det['cantidad'])

            # Normalizar precio unitario cuando viene escalado x100.
            # Regla: si valor_unitario ~= 100 * (valor_total / cantidad), dividir por 100.
            precio_implicito = np.where(
                df_det['cantidad_norm'] > 0,
                df_det['valor_total'] / df_det['cantidad_norm'],
                np.nan,
            )
            ratio_precio = np.where(
                np.isfinite(precio_implicito) & (precio_implicito > 0),
                df_det['valor_unitario'] / precio_implicito,
                np.nan,
            )

            mask_precio_x100 = (
                np.isfinite(ratio_precio)
                & (ratio_precio >= 80)
                & (ratio_precio <= 120)
            )

            df_det['valor_unitario_norm'] = np.where(
                mask_precio_x100,
                df_det['valor_unitario'] / 100,
                df_det['valor_unitario'],
            )

            # Normalizar valor_total cuando viene escalado x100 respecto a unitario*cantidad.
            denom_total = df_det['valor_unitario_norm'] * df_det['cantidad_norm']
            ratio_total = np.where(
                (denom_total > 0) & np.isfinite(denom_total),
                df_det['valor_total'] / denom_total,
                np.nan,
            )
            mask_total_x100 = (
                np.isfinite(ratio_total)
                & (ratio_total >= 0.8)
                & (ratio_total <= 1.2)
            )

            mask_reconstruir_total = (df_det['valor_total'] <= 0)
            df_det['valor_total_norm'] = np.where(
                mask_total_x100,
                df_det['valor_total'] / 100,
                df_det['valor_total'],
            )

            df_det['cant_venta'] = np.where(is_factura, df_det['cantidad_norm'].clip(lower=0), 0)
            df_det['total_venta'] = np.where(is_factura, df_det['valor_total_norm'].clip(lower=0), 0)

            df_det['cant_nc'] = np.where(is_nc, np.abs(df_det['cantidad_norm']), 0)
            df_det['total_nc'] = np.where(is_nc, np.abs(df_det['valor_total_norm']), 0)

            # Devolucion aproximada via NC DEV
            is_nc_dev = df_det['tipo'].str.contains('NC DEV', na=False)
            df_det['cant_devolucion'] = np.where(is_nc_dev, np.abs(df_det['cantidad_norm']), 0)
            df_det['total_devolucion'] = np.where(is_nc_dev, np.abs(df_det['valor_total_norm']), 0)

            df_det['cant_neto'] = df_det['cant_venta'] - df_det['cant_nc']
            df_det['total_neto'] = df_det['total_venta'] - df_det['total_nc']
            # En la fuente Kronos, `costo` viene a nivel de linea (no unitario).
            # Multiplicar por cantidad infla costos y distorsiona rentabilidad.
            df_det['costo_venta'] = np.where(is_factura, np.abs(df_det['costo']), 0)
            df_det['rentabilidad'] = df_det['total_neto'] - df_det['costo_venta']
            df_det['prc_rentabilidad'] = np.where(
                df_det['total_neto'] > 0,
                (df_det['rentabilidad'] / df_det['total_neto']) * 100,
                0,
            )

            agg_cols = [
                'centro_costo', 'codigo_producto', 'codigo_alterno', 'producto', 'mes', 'anio',
                'cant_venta', 'total_venta', 'cant_nc', 'total_nc',
                'cant_devolucion', 'total_devolucion', 'cant_neto', 'total_neto',
                'costo_venta', 'rentabilidad', 'prc_rentabilidad',
            ]
            df_k = df_det[agg_cols].groupby(
                ['centro_costo', 'codigo_producto', 'codigo_alterno', 'producto', 'mes', 'anio'],
                as_index=False,
            ).sum(numeric_only=True)

            devolucion_excede_venta = (
                (df_k['cant_devolucion'] > df_k['cant_venta'])
                | (df_k['total_devolucion'] > df_k['total_venta'])
            )
            neto_negativo = (df_k['cant_neto'] < 0) | (df_k['total_neto'] < 0)

            df_k['es_dato_calidado'] = True
            df_k['flag_outlier'] = devolucion_excede_venta | neto_negativo
            df_k['flag_valor_nulo'] = False
            df_k['fecha_carga'] = datetime.now()
            df_k['pipeline_id'] = pipeline_id
            df_k['batch_id'] = batch_id

            resultados['kronos_ventas'] = df_k
            print(f"    kronos_ventas desde detalle: {len(df_k)}")
            print(f"    precios unitarios normalizados x100: {int(mask_precio_x100.sum())}")
            print(f"    totales normalizados x100: {int(mask_total_x100.sum())}")
            print(f"    cantidades normalizadas x100: {int(mask_qty_x100.sum())}")
            print(f"    lineas sin total util (no se imputan): {int(mask_reconstruir_total.sum())}")

    # Buscar la tabla de ventas
    key_ventas = None
    for key in dfs.keys():
        if 'ventas' in key.lower() or 'kronos' in key.lower():
            key_ventas = key
            break

    if key_ventas and 'kronos_ventas' not in resultados:
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
        mes_extraido = None  # Para extraer el mes del encabezado del reporte
        col_busqueda = df_raw.columns[0] if len(df_raw.columns) > 0 else None

        # Extraer AÑO del encabezado del reporte (no MES, porque cada fila tiene su MES)
        # El formato es: "Agrupado por: ... Desde: DD/MM/YYYY Hasta: DD/MM/YYYY"
        import re
        anio_extraido = None

        if col_busqueda:
            for idx in range(min(10, len(df_raw))):
                try:
                    val = str(df_raw.iloc[idx][col_busqueda]) if pd.notna(df_raw.iloc[idx][col_busqueda]) else ''
                    # Buscar patrón "Desde: DD/MM/YYYY" para extraer el AÑO
                    match = re.search(r'Desde:\s*(\d{1,2})/(\d{1,2})/(\d{4})', val)
                    if match:
                        anio_extraido = match.group(3)  # Extraer el año (2026)
                        print(f"    Año extraído del encabezado: {anio_extraido}")
                        break
                except:
                    continue

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

        devolucion_excede_venta = (
            (df['cant_devolucion'] > df['cant_venta'])
            | (df['total_devolucion'] > df['total_venta'])
        )
        neto_negativo = (df['cant_neto'] < 0) | (df['total_neto'] < 0)

        df['es_dato_calidado'] = True
        df['flag_outlier'] = devolucion_excede_venta | neto_negativo
        df['flag_valor_nulo'] = df.isnull().any(axis=1)
        df['fecha_carga'] = datetime.now()

        # Verificar y limpiar columna MES (cada fila tiene su propio MES de la columna 16)
        if 'mes' in df.columns:
            # Limpiar valores de MES
            df['mes'] = df['mes'].astype(str).str.strip().str.upper()
            # Filtrar valores inválidos (headers, None, etc.)
            df['mes'] = df['mes'].replace(['MES', 'NONE', 'NAN', ''], np.nan)
            # Contar valores válidos
            mes_validos = df['mes'].dropna().value_counts()
            if len(mes_validos) > 0:
                print(f"    Distribución de MES: {dict(mes_validos)}")
            else:
                print(f"    [WARN] No se encontraron valores de MES válidos")
                df['mes'] = 'ENERO'  # Valor por defecto
        else:
            print(f"    [WARN] Columna MES no encontrada, asignando valor por defecto")
            df['mes'] = 'ENERO'

        # Asignar AÑO extraído del encabezado del reporte
        if anio_extraido:
            df['anio'] = anio_extraido
            print(f"    Año asignado a todos los registros: {anio_extraido}")
        else:
            df['anio'] = '2026'  # Valor por defecto basado en los datos
            print(f"    [WARN] Año no encontrado, asignando valor por defecto: 2026")

        # Columnas finales para Silver
        columnas_finales = [
            'centro_costo', 'codigo_producto', 'codigo_alterno', 'producto', 'mes', 'anio',
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

        # =========================================================================
        # 7. NORMALIZAR TEXTOS (IMPORTANTE: evita inconsistencias)
        # =========================================================================
        if 'centro_costo' in df_export.columns:
            df_export['centro_costo'] = df_export['centro_costo'].astype(str).str.strip().str.lower()

        df_export['pipeline_id'] = pipeline_id
        df_export['batch_id'] = batch_id

        # Estadisticas
        print(f"\n    === RESUMEN ===")
        print(f"    Registros finales: {len(df_export)}")
        print(f"    Centros de costo unicos: {df_export['centro_costo'].nunique()}")
        print(f"    Productos unicos: {df_export['producto'].nunique()}")
        print(f"    Total ventas: ${df_export['total_venta'].sum():,.2f}")
        print(f"    Meses: {df_export['mes'].value_counts().to_dict()}")
        print(f"    Año: {df_export['anio'].unique()}")

        resultados['kronos_ventas'] = df_export
    elif 'kronos_ventas' not in resultados:
        print("[WARN] No se encontro tabla de ventas Kronos en los datos")

    # =========================================================================
    # [2] TRANSFORMAR: QuickBooks Produccion
    # Convierte lineas operativas en un dataset consolidado por orden.
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

            # Estandarizar nombres esperados (compatibilidad de fuentes)
            if 'qty_planificada' not in df_prod.columns and 'qty_pedida' in df_prod.columns:
                df_prod['qty_planificada'] = df_prod['qty_pedida']
            if 'qty_despachada' not in df_prod.columns:
                if 'qty_fabricada' in df_prod.columns:
                    df_prod['qty_despachada'] = df_prod['qty_fabricada']
                elif 'qty_liberada' in df_prod.columns:
                    df_prod['qty_despachada'] = df_prod['qty_liberada']
                else:
                    df_prod['qty_despachada'] = 0
            if 'numero_orden' not in df_prod.columns and 'numero' in df_prod.columns:
                df_prod['numero_orden'] = df_prod['numero']

            # Normalizacion minima de texto/identificadores
            for col in ['idsale', 'idsales', 'numero_orden', 'estado', 'cliente']:
                if col in df_prod.columns:
                    df_prod[col] = df_prod[col].astype(str).str.strip()

            # Eliminar filas sin identificador o fecha valida
            if 'fecha' in df_prod.columns:
                df_prod['fecha'] = pd.to_datetime(df_prod['fecha'], errors='coerce')
            if 'fecha_creacion' in df_prod.columns:
                df_prod['fecha_creacion'] = pd.to_datetime(df_prod['fecha_creacion'], errors='coerce')

            id_col = None
            for cand in ['idsale', 'idsales', 'numero_orden', 'numero', 'id_registro']:
                if cand in df_prod.columns:
                    id_col = cand
                    break
            if id_col is not None:
                df_prod = df_prod[
                    df_prod[id_col].notna()
                    & (df_prod[id_col] != '')
                    & (df_prod[id_col].str.lower() != 'nan')
                    & (df_prod[id_col].str.lower() != 'none')
                ].copy()
            if 'fecha' in df_prod.columns:
                df_prod = df_prod[df_prod['fecha'].notna()].copy()

            # Convertir columnas numericas
            for col in ['numitems', 'numitemsprocesados', 'num_lineas', 'qty_planificada', 'qty_despachada']:
                if col in df_prod.columns:
                    df_prod[col] = pd.to_numeric(df_prod[col], errors='coerce').fillna(0)

            # Consolidar duplicados por orden (si existen por reingestas)
            before_dups = len(df_prod)
            if id_col is not None:
                agg_num = {
                    'numitems': 'max',
                    'numitemsprocesados': 'max',
                    'num_lineas': 'max',
                    'qty_planificada': 'sum',
                    'qty_despachada': 'sum',
                    'fecha': 'max',
                    'fecha_creacion': 'max',
                    'numero_orden': 'first',
                    'estado': 'first',
                    'cliente': 'first',
                }
                agg_num = {k: v for k, v in agg_num.items() if k in df_prod.columns}
                df_prod = df_prod.groupby(id_col, as_index=False).agg(agg_num)
            print(f"    Duplicados consolidados quickbooks_produccion: {before_dups - len(df_prod)}")

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

            # Limitar rangos para ajustarse al tipo NUMERIC(8,4) en Silver
            df_prod['desviacion_porcentual'] = pd.to_numeric(df_prod['desviacion_porcentual'], errors='coerce').fillna(0).clip(-9999, 9999)
            df_prod['tasa_cumplimiento'] = pd.to_numeric(df_prod['tasa_cumplimiento'], errors='coerce').fillna(0).clip(0, 100)

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

            # Estandarizar nombres al esquema silver.quickbooks_produccion
            rename_cols = {
                'numero': 'numero_orden',
                'status': 'status_orden',
                'numitems': 'items_planificados',
                'numitemsprocesados': 'items_procesados',
                'qty_planificada': 'qty_total_planificada',
                'qty_despachada': 'qty_total_despachada',
            }
            rename_cols = {k: v for k, v in rename_cols.items() if k in df_prod.columns}
            df_prod = df_prod.rename(columns=rename_cols)

            if 'items_pendientes' not in df_prod.columns:
                if 'items_planificados' in df_prod.columns and 'items_procesados' in df_prod.columns:
                    df_prod['items_pendientes'] = (df_prod['items_planificados'] - df_prod['items_procesados']).clip(lower=0)
                else:
                    df_prod['items_pendientes'] = 0

            if 'qty_pendiente' not in df_prod.columns:
                if 'qty_total_planificada' in df_prod.columns and 'qty_total_despachada' in df_prod.columns:
                    df_prod['qty_pendiente'] = (df_prod['qty_total_planificada'] - df_prod['qty_total_despachada']).clip(lower=0)
                else:
                    df_prod['qty_pendiente'] = 0

            if 'flag_orden_atrasada' not in df_prod.columns:
                df_prod['flag_orden_atrasada'] = False

            # Metadatos
            df_prod['es_dato_calidado'] = True
            df_prod['fecha_carga'] = datetime.now()
            df_prod['pipeline_id'] = pipeline_id
            df_prod['batch_id'] = batch_id

            silver_cols = [
                'idsales', 'idsale', 'numero_orden',
                'fecha', 'fecha_creacion', 'estado', 'cliente',
                'idcliente', 'status_orden', 'items_planificados',
                'items_procesados', 'items_pendientes', 'num_lineas',
                'qty_total_planificada', 'qty_total_despachada',
                'qty_pendiente', 'desviacion_absoluta',
                'desviacion_porcentual', 'tasa_cumplimiento',
                'es_dato_calidado', 'flag_orden_atrasada',
                'fecha_carga', 'pipeline_id', 'batch_id',
            ]
            for c in silver_cols:
                if c not in df_prod.columns:
                    df_prod[c] = None
            df_prod = df_prod[silver_cols].copy()

            resultados['quickbooks_produccion'] = df_prod
            print(f"    Registros finales: {len(df_prod)}")
            print(f"    Tasa cumplimiento promedio: {df_prod['tasa_cumplimiento'].mean():.2f}%")

    # =========================================================================
    # [3] TRANSFORMAR: QuickBooks Ventas
    # Consolida detalle por identificador robusto y calcula cumplimiento.
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

            # Normalizacion de texto/identificadores para evitar falsos
            # duplicados por espacios/capitalizacion del origen.
            for col in ['idsale', 'idsales', 'numero', 'estado', 'cliente', 'status', '_status']:
                if col in df_ventas.columns:
                    df_ventas[col] = df_ventas[col].astype(str).str.strip()
            if 'fecha' in df_ventas.columns:
                df_ventas['fecha'] = pd.to_datetime(df_ventas['fecha'], errors='coerce')

            # Canonizar estado: legado `_status` se estandariza en `status`.
            if 'status' in df_ventas.columns and '_status' in df_ventas.columns:
                status_clean = df_ventas['status'].replace({'nan': '', 'none': '', 'None': '', 'NaN': ''})
                legacy_clean = df_ventas['_status'].replace({'nan': '', 'none': '', 'None': '', 'NaN': ''})
                df_ventas['status'] = status_clean.mask(status_clean == '', legacy_clean)
            elif '_status' in df_ventas.columns:
                df_ventas['status'] = df_ventas['_status'].replace({'nan': '', 'none': '', 'None': '', 'NaN': ''})

            # Construir identificador robusto de venta.
            # Prioridad: idsales -> idsale -> numero.
            idsales = df_ventas['idsales'].astype(str).str.strip() if 'idsales' in df_ventas.columns else pd.Series('', index=df_ventas.index)
            idsale = df_ventas['idsale'].astype(str).str.strip() if 'idsale' in df_ventas.columns else pd.Series('', index=df_ventas.index)
            numero = df_ventas['numero'].astype(str).str.strip() if 'numero' in df_ventas.columns else pd.Series('', index=df_ventas.index)

            idsales = idsales.replace({'nan': '', 'none': '', 'None': '', 'NaN': ''})
            idsale = idsale.replace({'nan': '', 'none': '', 'None': '', 'NaN': ''})
            numero = numero.replace({'nan': '', 'none': '', 'None': '', 'NaN': ''})

            df_ventas['sale_key'] = idsales
            df_ventas.loc[df_ventas['sale_key'] == '', 'sale_key'] = idsale
            df_ventas.loc[df_ventas['sale_key'] == '', 'sale_key'] = numero

            before_filter = len(df_ventas)
            df_ventas = df_ventas[df_ventas['sale_key'] != ''].copy()
            print(f"    Filas removidas sin identificador de venta: {before_filter - len(df_ventas)}")

            if 'fecha' in df_ventas.columns:
                df_ventas = df_ventas[df_ventas['fecha'].notna()].copy()

            # Convertir columnas numericas
            for col in ['numitems', 'numitemsprocesados', 'num_lineas', 'productos_unicos', 'qty_pedida', 'qty_despachada']:
                if col in df_ventas.columns:
                    df_ventas[col] = pd.to_numeric(df_ventas[col], errors='coerce').fillna(0)

            for col in ['numitems', 'numitemsprocesados', 'num_lineas', 'productos_unicos']:
                if col in df_ventas.columns:
                    df_ventas[col] = pd.to_numeric(df_ventas[col], errors='coerce').fillna(0).astype(int)

            before_dups_v = len(df_ventas)
            if 'sale_key' in df_ventas.columns:
                agg_v = {
                    'numitems': 'max',
                    'numitemsprocesados': 'max',
                    'num_lineas': 'max',
                    'productos_unicos': 'max',
                    'qty_pedida': 'sum',
                    'qty_despachada': 'sum',
                    'fecha': 'max',
                    'numero': 'first',
                    'estado': 'first',
                    'cliente': 'first',
                }
                agg_v = {k: v for k, v in agg_v.items() if k in df_ventas.columns}
                df_ventas = df_ventas.groupby('sale_key', as_index=False).agg(agg_v)
            print(f"    Duplicados consolidados quickbooks_ventas: {before_dups_v - len(df_ventas)}")

            if before_dups_v > 0 and len(df_ventas) == 0:
                raise RuntimeError(
                    'Transformacion quickbooks_ventas produjo 0 filas desde un origen no vacio. '
                    'Revisar reglas de identificador/filtro.'
                )

            # Calcular metricas
            df_ventas['qty_pendiente'] = df_ventas['qty_pedida'] - df_ventas['qty_despachada']
            df_ventas['tasa_cumplimiento'] = np.where(
                df_ventas['qty_pedida'] > 0,
                (df_ventas['qty_despachada'] / df_ventas['qty_pedida']) * 100,
                0
            )
            df_ventas['tasa_cumplimiento'] = pd.to_numeric(df_ventas['tasa_cumplimiento'], errors='coerce').fillna(0).clip(0, 100)

            # Metadatos
            df_ventas['es_dato_calidado'] = True
            df_ventas['fecha_carga'] = datetime.now()
            df_ventas['pipeline_id'] = pipeline_id
            df_ventas['batch_id'] = batch_id

            silver_cols_ventas = [
                'idsales', 'idsale', 'numero',
                'fecha', 'estado', 'cliente',
                'idcliente', 'status',
                'numitems', 'numitemsprocesados',
                'num_lineas', 'productos_unicos',
                'qty_pedida', 'qty_despachada',
                'qty_pendiente', 'tasa_cumplimiento',
                'es_dato_calidado',
                'fecha_carga', 'pipeline_id', 'batch_id',
            ]
            for c in silver_cols_ventas:
                if c not in df_ventas.columns:
                    df_ventas[c] = None
            df_ventas = df_ventas[silver_cols_ventas].copy()

            resultados['quickbooks_ventas'] = df_ventas
            print(f"    Registros finales: {len(df_ventas)}")
            print(f"    Qty total pedida: {df_ventas['qty_pedida'].sum():,.0f}")
            print(f"    Qty total despachada: {df_ventas['qty_despachada'].sum():,.0f}")

    # =========================================================================
    # TRANSFORMAR: Transacciones reales para Apriori (ticket-item)
    # =========================================================================

    if 'kronos_ventas_detalle_raw' in dfs:
        print(f"\n[4] Transformando kronos_ventas_detalle_raw para Apriori...")

        df_tx = dfs['kronos_ventas_detalle_raw']
        if isinstance(df_tx, list):
            df_tx = pd.DataFrame(df_tx)
        elif isinstance(df_tx, pd.DataFrame):
            df_tx = df_tx.copy()
        else:
            df_tx = pd.DataFrame()

        if len(df_tx) > 0:
            # Normalizacion minima
            df_tx['fecha'] = pd.to_datetime(df_tx.get('fecha_factura'), errors='coerce')
            id_factura = df_tx.get('id_factura').astype(str).str.strip()
            numero_factura = df_tx.get('numero_factura').astype(str).str.strip()
            df_tx['id_factura'] = np.where(
                id_factura.notna()
                & (id_factura != '')
                & (id_factura.str.lower() != 'nan')
                & (id_factura.str.lower() != 'none'),
                id_factura,
                numero_factura,
            )
            df_tx['producto_raw'] = df_tx.get('descripcion_producto').astype(str).str.strip()
            df_tx['agencia_raw'] = df_tx.get('id_sucursal').astype(str).str.strip()
            df_tx['cliente_raw'] = df_tx.get('nombre_comercial').astype(str).str.strip()
            qty_tx = parse_numeric_robusto(df_tx.get('cantidad')).fillna(0)
            mask_qty_tx_x100 = (np.abs(qty_tx) >= 100) & ((np.abs(qty_tx) % 100) < 1e-9)
            df_tx['qty'] = np.where(mask_qty_tx_x100, qty_tx / 100, qty_tx)
            valor_unitario_tx = parse_numeric_robusto(df_tx.get('valor_unitario')).fillna(0)
            valor_total_tx = parse_numeric_robusto(df_tx.get('valor_total')).fillna(0)

            precio_imp_tx = np.where(df_tx['qty'] > 0, valor_total_tx / df_tx['qty'], np.nan)
            ratio_tx = np.where(
                np.isfinite(precio_imp_tx) & (precio_imp_tx > 0),
                valor_unitario_tx / precio_imp_tx,
                np.nan,
            )
            mask_tx_x100 = np.isfinite(ratio_tx) & (ratio_tx >= 80) & (ratio_tx <= 120)
            valor_unitario_tx_norm = np.where(mask_tx_x100, valor_unitario_tx / 100, valor_unitario_tx)

            denom_tx = valor_unitario_tx_norm * df_tx['qty']
            ratio_total_tx = np.where(
                (denom_tx > 0) & np.isfinite(denom_tx),
                valor_total_tx / denom_tx,
                np.nan,
            )
            mask_total_tx_x100 = np.isfinite(ratio_total_tx) & (ratio_total_tx >= 0.8) & (ratio_total_tx <= 1.2)

            df_tx['amount'] = np.where(mask_total_tx_x100, valor_total_tx / 100, valor_total_tx)
            df_tx['tipo_doc'] = df_tx.get('tipo').astype(str).str.upper().str.strip()

            # Filtrar lineas utiles para market basket
            df_tx = df_tx[
                df_tx['fecha'].notna()
                & df_tx['id_factura'].notna()
                & (df_tx['id_factura'] != '')
                & (df_tx['id_factura'].str.lower() != 'none')
                & (df_tx['id_factura'].str.lower() != 'nan')
                & df_tx['producto_raw'].notna()
                & (df_tx['producto_raw'] != '')
                & (df_tx['qty'] > 0)
                & (df_tx['amount'] > 0)
                & (df_tx['tipo_doc'].str.contains('FACTURA', na=False))
            ].copy()

            # Definicion de transaccion real (factura)
            df_tx['transaccion_id'] = df_tx['id_factura'].astype(str)
            df_tx['agencia'] = df_tx['agencia_raw'].replace({'nan': 'sin_agencia', '': 'sin_agencia'})
            df_tx['cliente'] = df_tx['cliente_raw'].replace({'nan': 'sin_cliente', '': 'sin_cliente'})

            def limpiar_producto(texto):
                t = str(texto).strip()
                partes = [p.strip() for p in t.split(':') if p is not None]
                nombre = partes[-1].strip() if len(partes) > 0 else t
                if not nombre:
                    nombre = t
                return nombre

            df_tx['producto'] = df_tx['producto_raw'].apply(limpiar_producto)
            df_tx['categoria'] = df_tx.get('nombre_subgrupo').astype(str).str.upper().str.strip()
            df_tx['categoria'] = df_tx['categoria'].replace({'NAN': 'SIN_CATEGORIA', '': 'SIN_CATEGORIA'})
            df_tx['fuente'] = 'kronos'
            df_tx['pipeline_id'] = pipeline_id
            df_tx['batch_id'] = batch_id
            df_tx['fecha_carga'] = datetime.now()

            # Evitar duplicado exacto en la misma transaccion
            df_tx = df_tx.drop_duplicates(subset=['transaccion_id', 'producto'])

            out_cols = [
                'transaccion_id', 'fecha', 'agencia', 'cliente',
                'producto', 'categoria', 'qty', 'amount',
                'fuente', 'pipeline_id', 'batch_id', 'fecha_carga',
            ]
            resultados['apriori_transacciones'] = df_tx[out_cols].copy()

            print(f"    Registros finales Apriori Kronos: {len(df_tx)}")
            print(f"    Transacciones unicas: {df_tx['transaccion_id'].nunique()}")
            print(f"    Productos unicos: {df_tx['producto'].nunique()}")

    if 'quickbooks_sales_local_raw' in dfs and 'apriori_transacciones' not in resultados:
        print(f"\n[4] Transformando quickbooks_sales_local_raw para Apriori...")

        df_tx = dfs['quickbooks_sales_local_raw']
        if isinstance(df_tx, list):
            df_tx = pd.DataFrame(df_tx)
        elif isinstance(df_tx, pd.DataFrame):
            df_tx = df_tx.copy()
        else:
            df_tx = pd.DataFrame()

        if len(df_tx) > 0:
            # Normalizacion minima
            df_tx['fecha'] = pd.to_datetime(df_tx.get('fecha'), errors='coerce')
            df_tx['numero'] = df_tx.get('numero').astype(str).str.strip()
            df_tx['item'] = df_tx.get('item').astype(str).str.strip()
            df_tx['asesor'] = df_tx.get('asesor').astype(str).str.strip().str.lower()
            df_tx['cliente'] = df_tx.get('cliente').astype(str).str.strip()
            df_tx['qty'] = pd.to_numeric(df_tx.get('qty'), errors='coerce').fillna(0)
            df_tx['amount'] = pd.to_numeric(df_tx.get('amount'), errors='coerce').fillna(0)

            # Filtrar lineas no utiles
            df_tx = df_tx[
                df_tx['fecha'].notna()
                & df_tx['numero'].notna()
                & (df_tx['numero'] != '')
                & df_tx['item'].notna()
                & (df_tx['item'] != '')
                & (df_tx['qty'] > 0)
            ].copy()

            # Definicion de transaccion real (ticket por dia)
            df_tx['transaccion_id'] = (
                df_tx['numero'].astype(str)
                + '-'
                + df_tx['fecha'].dt.strftime('%Y%m%d')
            )
            df_tx['agencia'] = df_tx['asesor'].replace({'nan': 'sin_agencia', '': 'sin_agencia'})
            raw_item = df_tx['item'].astype(str)

            # Depuracion de nombre de producto para analitica y dashboard
            def limpiar_producto(texto):
                t = str(texto).strip()
                partes = [p.strip() for p in t.split(':') if p is not None]
                nombre = partes[-1].strip() if len(partes) > 0 else t
                if not nombre:
                    nombre = t
                return nombre

            def extraer_categoria(texto):
                t = str(texto).strip()
                partes = [p.strip() for p in t.split(':') if p is not None]
                if len(partes) >= 2:
                    return partes[-2].upper()
                return 'SIN_CATEGORIA'

            df_tx['producto'] = raw_item.apply(limpiar_producto)
            df_tx['categoria'] = raw_item.apply(extraer_categoria)
            df_tx['fuente'] = 'quickbooks'
            df_tx['pipeline_id'] = pipeline_id
            df_tx['batch_id'] = batch_id
            df_tx['fecha_carga'] = datetime.now()

            # Evitar duplicado exacto en la misma transaccion
            df_tx = df_tx.drop_duplicates(subset=['transaccion_id', 'producto'])

            out_cols = [
                'transaccion_id', 'fecha', 'agencia', 'cliente',
                'producto', 'categoria', 'qty', 'amount',
                'fuente', 'pipeline_id', 'batch_id', 'fecha_carga',
            ]
            resultados['apriori_transacciones'] = df_tx[out_cols].copy()

            print(f"    Registros finales Apriori: {len(df_tx)}")
            print(f"    Transacciones unicas: {df_tx['transaccion_id'].nunique()}")
            print(f"    Productos unicos: {df_tx['producto'].nunique()}")

    # =========================================================================
    # 5. TRANSFORMAR: Catalogo EAN limpio
    # =========================================================================
    if 'quickbooks_catalogo_ean_raw' in dfs:
        print(f"\n[5] Transformando quickbooks_catalogo_ean_raw...")
        df_cat = dfs['quickbooks_catalogo_ean_raw']
        if isinstance(df_cat, list):
            df_cat = pd.DataFrame(df_cat)
        elif isinstance(df_cat, pd.DataFrame):
            df_cat = df_cat.copy()
        else:
            df_cat = pd.DataFrame()

        if len(df_cat) > 0:
            for col in ['item', 'description', 'ean13', 'ean14', 'um']:
                if col not in df_cat.columns:
                    df_cat[col] = ''
                df_cat[col] = df_cat[col].astype(str).str.strip().replace({'nan': ''})

            if 'price' not in df_cat.columns:
                df_cat['price'] = 0
            df_cat['price'] = pd.to_numeric(df_cat['price'], errors='coerce').fillna(0)

            df_cat = df_cat[df_cat['item'].ne('')].copy()

            df_cat['item_tail'] = df_cat['item'].str.split(':').str[-1].str.strip()
            df_cat['codigo_producto'] = (
                df_cat['item']
                .str.extract(r'\((\d+)\)')[0]
                .fillna(df_cat['item'].str.extract(r'(\d+)$')[0])
                .fillna('')
                .astype(str)
                .str.zfill(4)
            )
            df_cat['tipo_producto'] = df_cat['item'].str.split(':').str[0].str.upper().str.strip()
            df_cat.loc[~df_cat['tipo_producto'].isin(['PT', 'PP']), 'tipo_producto'] = 'OTRO'

            df_cat['ean13'] = df_cat['ean13'].str.replace(r'\D', '', regex=True)
            df_cat['ean14'] = df_cat['ean14'].str.replace(r'\D', '', regex=True)
            df_cat['flag_ean13_valido'] = df_cat['ean13'].str.len().eq(13)

            genericos = {'', 'PT', 'PP', 'PRODUCTO TERMINADO', '1 CONDIMENSA', 'NONE', 'NAN'}
            df_cat['flag_desc_generica'] = df_cat['description'].str.upper().isin(genericos)
            df_cat['producto_dashboard'] = np.where(
                ~df_cat['flag_desc_generica'] & df_cat['description'].ne(''),
                df_cat['description'],
                df_cat['item_tail'],
            )

            df_cat['fecha_carga'] = datetime.now()
            df_cat['pipeline_id'] = pipeline_id
            df_cat['batch_id'] = batch_id

            keep_cols = [
                'item', 'item_tail', 'description', 'producto_dashboard', 'tipo_producto',
                'codigo_producto', 'ean13', 'ean14', 'um', 'price',
                'flag_ean13_valido', 'flag_desc_generica', 'fecha_carga', 'pipeline_id', 'batch_id'
            ]
            for c in keep_cols:
                if c not in df_cat.columns:
                    df_cat[c] = None

            resultados['catalogo_ean_clean'] = df_cat[keep_cols].copy()
            print(f"    Registros catalogo limpio: {len(df_cat)}")

    # =========================================================================
    # 6. TRANSFORMAR: Ventas econespecias mensual limpia
    # =========================================================================
    if 'quickbooks_ventas_econespecias_raw' in dfs:
        print(f"\n[6] Transformando quickbooks_ventas_econespecias_raw...")
        df_ve = dfs['quickbooks_ventas_econespecias_raw']
        if isinstance(df_ve, list):
            df_ve = pd.DataFrame(df_ve)
        elif isinstance(df_ve, pd.DataFrame):
            df_ve = df_ve.copy()
        else:
            df_ve = pd.DataFrame()

        if len(df_ve) > 0:
            rename_map = {'recuento de cliente': 'recuento_cliente', 'año': 'anio', 'ano': 'anio'}
            for old, new in rename_map.items():
                if old in df_ve.columns and new not in df_ve.columns:
                    df_ve[new] = df_ve[old]

            for c in ['marca', 'familia', 'producto', 'mes']:
                if c not in df_ve.columns:
                    df_ve[c] = ''
                df_ve[c] = df_ve[c].astype(str).str.strip().replace({'nan': ''})

            for c in ['recuento_cliente', 'cantidad', 'ventas', 'anio']:
                if c not in df_ve.columns:
                    df_ve[c] = 0
                df_ve[c] = pd.to_numeric(df_ve[c], errors='coerce').fillna(0)

            month_map = {
                'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6,
                'julio': 7, 'agosto': 8, 'septiembre': 9, 'setiembre': 9,
                'octubre': 10, 'noviembre': 11, 'diciembre': 12,
            }
            if 'periodo' not in df_ve.columns:
                df_ve['mes_num'] = df_ve['mes'].str.lower().map(month_map)
                df_ve['periodo'] = pd.to_datetime(
                    dict(year=df_ve['anio'], month=df_ve['mes_num'], day=1), errors='coerce'
                )
            else:
                df_ve['periodo'] = pd.to_datetime(df_ve['periodo'], errors='coerce')

            df_ve = df_ve[df_ve['periodo'].notna() & df_ve['producto'].ne('')].copy()

            df_ve['codigo_producto'] = (
                df_ve['producto'].str.extract(r'\((\d+)\)')[0].fillna('').astype(str).str.zfill(4)
            )

            df_ve = (
                df_ve.groupby(['marca', 'familia', 'producto', 'codigo_producto', 'periodo'], as_index=False)
                .agg(
                    anio=('anio', 'max'),
                    mes=('mes', 'first'),
                    recuento_cliente=('recuento_cliente', 'sum'),
                    cantidad=('cantidad', 'sum'),
                    ventas=('ventas', 'sum'),
                )
            )

            df_ve['fecha_carga'] = datetime.now()
            df_ve['pipeline_id'] = pipeline_id
            df_ve['batch_id'] = batch_id

            resultados['ventas_econespecias_mensual_clean'] = df_ve.copy()
            print(f"    Registros ventas mensual limpia: {len(df_ve)}")

    # =========================================================================
    # 7. DIMENSION CANONICA + BASE FORECASTING
    # =========================================================================
    if 'catalogo_ean_clean' in resultados and 'ventas_econespecias_mensual_clean' in resultados:
        print(f"\n[7] Construyendo dim_producto_canonico y forecasting_base_mensual_v1...")
        cat = resultados['catalogo_ean_clean'].copy()
        ven = resultados['ventas_econespecias_mensual_clean'].copy()

        cat['score'] = (
            cat['flag_ean13_valido'].astype(int) * 4
            + (~cat['flag_desc_generica']).astype(int) * 3
            + cat['description'].ne('').astype(int) * 2
            + cat['item_tail'].ne('').astype(int)
        )
        cat = cat.sort_values(['codigo_producto', 'score'], ascending=[True, False])
        dim = cat.drop_duplicates(subset=['codigo_producto']).copy()

        conflict = (
            cat[cat['flag_ean13_valido']]
            .groupby('ean13', as_index=False)['producto_dashboard']
            .nunique()
            .rename(columns={'producto_dashboard': 'n_names'})
        )
        conflict['flag_conflicto_ean13'] = conflict['n_names'] > 1
        dim = dim.merge(conflict[['ean13', 'flag_conflicto_ean13']], on='ean13', how='left')
        dim['flag_conflicto_ean13'] = dim['flag_conflicto_ean13'].fillna(False)

        codes_sales = set(ven['codigo_producto'].astype(str))
        dim['estado_match'] = np.where(
            dim['codigo_producto'].astype(str).isin(codes_sales),
            'exacto',
            'sin_match',
        )

        dim = dim.rename(
            columns={
                'item': 'item_canonico',
                'description': 'description_canonica',
            }
        )
        dim_cols = [
            'codigo_producto', 'ean13', 'ean14', 'item_canonico', 'description_canonica',
            'producto_dashboard', 'tipo_producto', 'estado_match', 'flag_conflicto_ean13',
            'fecha_carga', 'pipeline_id', 'batch_id'
        ]
        for c in dim_cols:
            if c not in dim.columns:
                dim[c] = None
        dim = dim[dim_cols].copy()
        resultados['dim_producto_canonico'] = dim

        base = ven.merge(dim, on='codigo_producto', how='left', suffixes=('', '_dim'))
        base['producto_item'] = base['item_canonico'].fillna(base['producto'])
        base['producto_dashboard'] = base['producto_dashboard'].fillna(base['producto'])
        base['tipo_producto'] = base['tipo_producto'].fillna('OTRO')
        base['ean13'] = base['ean13'].fillna('')
        base['flag_catalogo_conflicto'] = base['flag_conflicto_ean13'].fillna(False)

        base['periodo'] = pd.to_datetime(base['periodo'], errors='coerce')
        max_period = base['periodo'].max()
        key = np.where(base['ean13'].astype(str).str.len() == 13, base['ean13'], base['codigo_producto'])
        base['prod_key'] = key

        last_p = base.groupby('prod_key', as_index=False)['periodo'].max().rename(columns={'periodo': 'last_period'})
        base = base.merge(last_p, on='prod_key', how='left')
        base['months_since_last'] = (
            (max_period.year - base['last_period'].dt.year) * 12
            + (max_period.month - base['last_period'].dt.month)
        )

        month_act = (
            base[base['cantidad'] > 0]
            .groupby(['prod_key', base['periodo'].dt.month], as_index=False)
            .size()
            .groupby('prod_key', as_index=False)
            .size()
            .rename(columns={'size': 'active_months'})
        )
        base = base.merge(month_act[['prod_key', 'active_months']], on='prod_key', how='left')
        base['active_months'] = base['active_months'].fillna(0)

        base['estado_producto'] = np.where(
            base['months_since_last'] >= 6,
            'INACTIVO',
            np.where(base['active_months'] <= 4, 'ESTACIONAL', 'ACTIVO'),
        )

        base['anio'] = base['periodo'].dt.year
        base['mes'] = base['periodo'].dt.month
        base['fecha_carga'] = datetime.now()
        base['pipeline_id'] = pipeline_id
        base['batch_id'] = batch_id

        out_cols = [
            'periodo', 'anio', 'mes', 'marca', 'familia', 'codigo_producto', 'ean13',
            'producto_item', 'producto_dashboard', 'tipo_producto', 'cantidad', 'ventas',
            'recuento_cliente', 'estado_producto', 'flag_catalogo_conflicto',
            'fecha_carga', 'pipeline_id', 'batch_id'
        ]
        for c in out_cols:
            if c not in base.columns:
                base[c] = None
        base = base[out_cols].rename(
            columns={
                'cantidad': 'qty_vendida',
                'ventas': 'ventas_valor',
                'recuento_cliente': 'clientes',
            }
        )
        resultados['forecasting_base_mensual_v1'] = base

        print(f"    dim_producto_canonico: {len(dim)}")
        print(f"    forecasting_base_mensual_v1: {len(base)}")

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
