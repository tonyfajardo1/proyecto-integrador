"""
Transformer: Limpiar y transformar datos de Bronze a Silver
Pipeline: etl_silver_kronos
Limpia, normaliza y valida datos desde Bronze hacia Silver.
"""
import pandas as pd
import numpy as np

if 'transformer' not in dir():
    from mage_ai.data_preparation.decorators import transformer
if 'test' not in dir():
    from mage_ai.data_preparation.decorators import test


@transformer
def transformar_kronos_silver(data, *args, **kwargs):
    """
    Transforma datos crudos de Bronze a Silver.
    - Limpia datos
    - Normaliza nombres de columnas
    - Aplica reglas de negocio
    - Valida calidad
    """
    
    # Extraer dataframes del input
    dfs = data.get('dfs', {})
    batch_id = data.get('batch_id')
    pipeline_id = data.get('pipeline_id')
    
    print(f"\n{'='*70}")
    print(f"TRANSFORMACION - BRONZE A SILVER")
    print(f"{'='*70}")
    print(f"Pipeline: {pipeline_id}")
    print(f"Batch: {batch_id}")
    print(f"{'='*70}\n")
    
    resultados = {}
    
    # =========================================================================
    # TRANSFORMAR: Kronos Ventas
    # =========================================================================
    
    # Buscar la tabla de ventas - puede venir como 'kronos_ventas_raw' o 'ventas_general_4'
    key_ventas = None
    for key in dfs.keys():
        if 'ventas' in key.lower() or 'kronos' in key.lower():
            key_ventas = key
            break
    
    if key_ventas:
        print(f"[1] Transformando {key_ventas}...")
        
        df_raw = dfs[key_ventas].copy()
        
        # =========================================================================
        # 1. IDENTIFICAR ENCABEZADOS (el Excel tiene filas de encabezado)
        # =========================================================================
        
        # Buscar la fila donde estan los verdaderos encabezados
        header_row = None
        for idx, row in df_raw.iterrows():
            first_val = str(row.iloc[0]).upper().strip() if pd.notna(row.iloc[0]) else ''
            if 'CENTRO' in first_val or first_val.startswith('CENTRO'):
                header_row = idx
                break
        
        if header_row is not None:
            # Usar esa fila como encabezado
            df_raw.columns = df_raw.iloc[header_row]
            df_raw = df_raw.iloc[header_row + 1:].copy()
        
        # =========================================================================
        # 2. RENOMBRAR COLUMNAS
        # =========================================================================
        
        # Mapeo de nombres de columnas
        column_mapping = {
            'CENTRO_COSTO': 'centro_costo',
            'CODIGO_PRODUCTO': 'codigo_producto',
            'CODIGO_ALTERNO': 'codigo_alterno',
            'PRODUCTO': 'producto',
            'CANT_VENTA': 'cant_venta',
            'TOTAL_VENTA': 'total_venta',
            'CANT_NC': 'cant_nc',
            'TOTAL_NC': 'total_nc',
            'CANT_DEVOLUCION': 'cant_devolucion',
            'TOTAL_DEVOLUCION': 'total_devolucion',
            'CANT_NETO': 'cant_neto',
            'TOTAL_NETO': 'total_neto',
            'COSTO_VENTA': 'costo_venta',
            'RENTABILIDAD': 'rentabilidad',
            'PRC_RENTABILIDAD': 'prc_rentabilidad',
            'MES': 'mes'
        }
        
        # Aplicar mapeo (ignorar columnas que no existen)
        df = pd.DataFrame()
        for old_col, new_col in column_mapping.items():
            # Buscar columna que contenga el nombre
            for col in df_raw.columns:
                if old_col.upper() in str(col).upper():
                    df[new_col] = df_raw[col].values
                    break
        
        # =========================================================================
        # 3. LIMPIAR DATOS
        # =========================================================================
        
        # Filtrar filas vacias
        df = df[df['centro_costo'].notna()]
        
        # Filtrar filas de totales/subtotales
        df = df[~df['centro_costo'].astype(str).str.contains('TOTAL|SUBTOTAL|CENTRO', case=False, na=False)]
        
        # =========================================================================
        # 4. CONVERTIR NUMERICOS
        # =========================================================================
        
        numeric_cols = ['cant_venta', 'total_venta', 'cant_nc', 'total_nc',
                       'cant_devolucion', 'total_devolucion', 'cant_neto', 'total_neto',
                       'costo_venta', 'rentabilidad', 'prc_rentabilidad']
        
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        # =========================================================================
        # 5. NORMALIZAR TEXTOS
        # =========================================================================
        
        if 'centro_costo' in df.columns:
            df['centro_costo'] = df['centro_costo'].astype(str).str.strip().str.lower()
        if 'producto' in df.columns:
            df['producto'] = df['producto'].astype(str).str.strip()
        if 'mes' in df.columns:
            df['mes'] = df['mes'].astype(str).str.strip().str.upper()
        
        # =========================================================================
        # 6. AGREGAR METADATOS
        # =========================================================================
        
        df['pipeline_id'] = pipeline_id
        df['batch_id'] = batch_id
        df['fecha_carga'] = pd.Timestamp.now()
        
        # Extraer año del mes si es posible
        def extraer_anio(mes):
            meses_año = {
                'ENERO': 2025, 'FEBRERO': 2025, 'MARZO': 2025,
                'ABRIL': 2025, 'MAYO': 2025, 'JUNIO': 2025,
                'JULIO': 2025, 'AGOSTO': 2025, 'SEPTIEMBRE': 2025,
                'OCTUBRE': 2025, 'NOVIEMBRE': 2025, 'DICIEMBRE': 2025
            }
            return meses_año.get(str(mes).upper(), 2025)
        
        if 'mes' in df.columns:
            df['anio'] = df['mes'].apply(extraer_anio)
        
        # =========================================================================
        # 7. FLAGS DE CALIDAD
        # =========================================================================
        
        df['es_dato_calidado'] = True
        df['flag_outlier'] = False
        df['flag_valor_nulo'] = False
        
        # Verificar outliers en metricas principales
        for col in ['total_venta', 'total_devolucion', 'rentabilidad']:
            if col in df.columns:
                q1 = df[col].quantile(0.25)
                q3 = df[col].quantile(0.75)
                iqr = q3 - q1
                outliers = (df[col] < q1 - 1.5*iqr) | (df[col] > q3 + 1.5*iqr)
                df.loc[outliers, 'flag_outlier'] = True
        
        print(f"    Registros transformados: {len(df)}")
        print(f"    Outliers detectados: {df['flag_outlier'].sum()}")
        
        resultados['kronos_ventas'] = df
    
    print(f"\n[OK] Transformacion completada")
    
    return {
        'dfs': resultados,
        'pipeline_id': pipeline_id,
        'batch_id': batch_id,
        'metadata': data.get('metadata', {})
    }


@test
def test_output(output, *args) -> None:
    assert output is not None, 'Transformacion fallo'
    assert 'dfs' in output, 'Falta diccionario de resultados'
    print(f"OK: Transformacion completada")
