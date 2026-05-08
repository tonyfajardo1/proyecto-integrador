"""
Data Exporter: Cargar datos a Bronze
Pipeline: etl_bronze
Persiste los datos crudos extraidos en la capa Bronze.
"""
from mage_ai.settings.repo import get_repo_path
from mage_ai.io.config import ConfigFileLoader
from mage_ai.io.postgres import Postgres
from os import path
import pandas as pd

if 'data_exporter' not in dir():
    from mage_ai.data_preparation.decorators import data_exporter
if 'test' not in dir():
    from mage_ai.data_preparation.decorators import test


@data_exporter
def cargar_bronze(data, *args, **kwargs):
    """
    Carga datos crudos a la capa Bronze en PostgreSQL.

    Convenciones de carga:
    - Carga completa por tabla (truncate + append o replace segun caso).
    - Ajuste dinamico de columnas para absorber variaciones menores en origen.
    - Validacion final de tablas criticas cargadas.
    """
    
    # Extraer dfs del data
    if isinstance(data, dict):
        if 'dfs' in data:
            dfs = data.get('dfs', {})
            pipeline_id = data.get('pipeline_id', 'etl_bronze')
            batch_id = data.get('batch_id')
        else:
            dfs = data
            pipeline_id = kwargs.get('pipeline_id', 'etl_bronze')
            batch_id = None
    else:
        dfs = {}
        pipeline_id = 'etl_bronze'
        batch_id = None
    
    print(f"\n{'='*70}")
    print(f"CARGA - A CAPA BRONZE")
    print(f"{'='*70}")
    print(f"Pipeline: {pipeline_id}")
    print(f"Batch: {batch_id}")
    print(f"Tablas a cargar: {list(dfs.keys())}")
    print(f"{'='*70}\n")
    
    config_path = path.join(get_repo_path(), 'io_config.yaml')
    config_profile = 'local_dwh'
    
    resultados = {}

    # Helper para recuperar DataFrame desde multiples alias de llave.
    # Esto permite compatibilidad con cambios de nombre en el loader.
    def get_df(posibles_keys):
        for key in posibles_keys:
            if key in dfs:
                dato = dfs[key]
                if isinstance(dato, list):
                    return key, pd.DataFrame(dato)
                if isinstance(dato, pd.DataFrame):
                    return key, dato.copy()
                return key, pd.DataFrame()
        return None, pd.DataFrame()
    
    with Postgres.with_config(ConfigFileLoader(config_path, config_profile)) as loader:

        # =====================================================================
        # 1) KRONOS: carga raw y detalle transaccional
        # =====================================================================
        key_kronos, df = get_df(['kronos.ventas_general_4', 'kronos.ventas_detalle'])
        if key_kronos:
            print(f"[1] Cargando {key_kronos} a bronze.kronos_ventas_raw...")

            if len(df) > 0:
                df_original = df.copy()

                # Columnas de metadata que NO deben renombrarse
                METADATA_COLS = ['fuente', 'nombre_tabla_origen', 'pipeline_id', 'batch_id', 'fecha_ingesta']

                # Separar columnas de datos y metadata
                cols_datos = [c for c in df.columns if c not in METADATA_COLS]

                # Renombrar columnas de datos a formato Bronze (columna_1, columna_2, ..., columna_16)
                columnas_bronze = {}
                for i, col in enumerate(cols_datos, 1):
                    columnas_bronze[col] = f'columna_{i}'
                df = df.rename(columns=columnas_bronze)

                print(f"    Columnas de datos: {len(cols_datos)}")

                # Asegurar que existen las 16 columnas de datos
                for i in range(1, 17):
                    col_name = f'columna_{i}'
                    if col_name not in df.columns:
                        df[col_name] = None

                # Columnas finales: 16 datos + metadata
                columnas_finales = [f'columna_{i}' for i in range(1, 17)]
                columnas_finales += METADATA_COLS
                columnas_existentes = [c for c in columnas_finales if c in df.columns]
                df_export = df[columnas_existentes].copy()

                # Mostrar valores de columna_16 (MES)
                if 'columna_16' in df_export.columns:
                    mes_valores = df_export['columna_16'].value_counts().head(5)
                    print(f"    Valores en columna_16 (MES): {dict(mes_valores)}")

                loader.export(df_export, schema_name='bronze', table_name='kronos_ventas_raw', if_exists='replace')
                print(f"    Registros cargados: {len(df_export)}")
                resultados['kronos_ventas_raw'] = len(df_export)

                # Cargar version transaccional completa para Apriori/Kronos detalle
                print(f"    Cargando version transaccional completa a bronze.kronos_ventas_detalle_raw...")
                df_det = df_original.copy()
                df_det.columns = [
                    str(c).replace('ï»¿', '').replace('\ufeff', '').strip().lower()
                    for c in df_det.columns
                ]

                # Normalizar nombres esperados
                rename_det = {
                    'id_factura': 'id_factura',
                    'serie': 'serie',
                    'numero_factura': 'numero_factura',
                    'fecha_ingreso': 'fecha_ingreso',
                    'fecha_factura': 'fecha_factura',
                    'fecha_vencimiento': 'fecha_vencimiento',
                    'vendedor': 'vendedor',
                    'empleado': 'empleado',
                    'titulo_gratuito': 'titulo_gratuito',
                    'id_detalle': 'id_detalle',
                    'cantidad': 'cantidad',
                    'valor_unitario': 'valor_unitario',
                    'valor_total': 'valor_total',
                    'descuento': 'descuento',
                    'id_producto': 'id_producto',
                    'id_unidad': 'id_unidad',
                    'costo': 'costo',
                    'id_promocion': 'id_promocion',
                    'tipo_precio': 'tipo_precio',
                    'tipo_producto': 'tipo_producto',
                    'id_motivo': 'id_motivo',
                    'id_cliente': 'id_cliente',
                    'id_sucursal': 'id_sucursal',
                    'vendedor_name_rutero': 'vendedor_name_rutero',
                    'supervisor_name': 'supervisor_name',
                    'cod_rutero': 'cod_rutero',
                    'nombre_rutero': 'nombre_rutero',
                    'ci_empleado': 'ci_empleado',
                    'ci_empleado_s': 'ci_empleado_s',
                    'razon_social': 'razon_social',
                    'nombre_comercial': 'nombre_comercial',
                    'codigo_producto': 'codigo_producto',
                    'descripcion_producto': 'descripcion_producto',
                    'nombre_subgrupo': 'nombre_subgrupo',
                    'descripcion_grupo': 'descripcion_grupo',
                    'nombre_marca': 'nombre_marca',
                    'linea_name': 'linea_name',
                    'tipo': 'tipo',
                    'fuente': 'fuente',
                    'nombre_tabla_origen': 'nombre_tabla_origen',
                    'pipeline_id': 'pipeline_id',
                    'batch_id': 'batch_id',
                    'fecha_ingesta': 'fecha_ingesta',
                }
                df_det = df_det.rename(columns=rename_det)

                cols_det = [
                    'id_factura', 'serie', 'numero_factura', 'fecha_ingreso', 'fecha_factura', 'fecha_vencimiento',
                    'vendedor', 'empleado', 'titulo_gratuito', 'id_detalle', 'cantidad', 'valor_unitario', 'valor_total',
                    'descuento', 'id_producto', 'id_unidad', 'costo', 'id_promocion', 'tipo_precio', 'tipo_producto',
                    'id_motivo', 'id_cliente', 'id_sucursal', 'vendedor_name_rutero', 'supervisor_name', 'cod_rutero',
                    'nombre_rutero', 'ci_empleado', 'ci_empleado_s', 'razon_social', 'nombre_comercial',
                    'codigo_producto', 'descripcion_producto', 'nombre_subgrupo', 'descripcion_grupo', 'nombre_marca',
                    'linea_name', 'tipo', 'fuente', 'nombre_tabla_origen', 'fecha_ingesta', 'pipeline_id', 'batch_id',
                ]
                for c in cols_det:
                    if c not in df_det.columns:
                        df_det[c] = None

                loader.export(
                    df_det[cols_det],
                    schema_name='bronze',
                    table_name='kronos_ventas_detalle_raw',
                    if_exists='replace',
                )
                print(f"    Registros cargados detalle: {len(df_det)}")
                resultados['kronos_ventas_detalle_raw'] = len(df_det)

        # Sub-bloque Kronos resumen para KPIs (tabla mensual normalizada).
        key_resumen, df_resumen = get_df(['kronos.ventas_resumen'])
        if key_resumen and len(df_resumen) > 0:
            print(f"[1b] Cargando {key_resumen} a bronze.kronos_ventas_resumen_raw...")

            cols_resumen = [
                'centro_costo', 'codigo_producto', 'codigo_alterno', 'producto', 'mes', 'anio',
                'cant_venta', 'total_venta', 'cant_nc', 'total_nc',
                'cant_devolucion', 'total_devolucion', 'cant_neto', 'total_neto',
                'costo_venta', 'rentabilidad', 'prc_rentabilidad',
                'fuente', 'nombre_tabla_origen', 'fecha_ingesta', 'pipeline_id', 'batch_id',
            ]

            for c in cols_resumen:
                if c not in df_resumen.columns:
                    df_resumen[c] = None

            loader.export(
                df_resumen[cols_resumen],
                schema_name='bronze',
                table_name='kronos_ventas_resumen_raw',
                if_exists='replace',
            )
            print(f"    Registros cargados resumen: {len(df_resumen)}")
            resultados['kronos_ventas_resumen_raw'] = len(df_resumen)

        # =====================================================================
        # 2) QUICKBOOKS: produccion raw
        # =====================================================================
        if 'quickbooks.produccion' in dfs:
            print(f"[2] Cargando quickbooks.produccion a bronze.quickbooks_produccion_raw...")
            dato = dfs['quickbooks.produccion']

            if isinstance(dato, list):
                df = pd.DataFrame(dato)
            elif isinstance(dato, pd.DataFrame):
                df = dato.copy()
            else:
                df = pd.DataFrame()

            if len(df) > 0:
                cols_dest = loader.load("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'bronze'
                      AND table_name = 'quickbooks_produccion_raw'
                    ORDER BY ordinal_position
                """)['column_name'].tolist()
                cols_prod = [c for c in cols_dest if c != 'id']

                for c in cols_prod:
                    if c not in df.columns:
                        df[c] = None

                loader.execute("TRUNCATE TABLE bronze.quickbooks_produccion_raw")
                loader.export(
                    df[cols_prod],
                    schema_name='bronze',
                    table_name='quickbooks_produccion_raw',
                    if_exists='append',
                )
                print(f"    Registros cargados: {len(df)}")
                resultados['quickbooks_produccion_raw'] = len(df)

        # =====================================================================
        # 3) QUICKBOOKS: ventas raw
        # =====================================================================
        if 'quickbooks.sales' in dfs:
            print(f"[3] Cargando quickbooks.sales a bronze.quickbooks_ventas_raw...")
            dato = dfs['quickbooks.sales']

            if isinstance(dato, list):
                df = pd.DataFrame(dato)
            elif isinstance(dato, pd.DataFrame):
                df = dato.copy()
            else:
                df = pd.DataFrame()

            if len(df) > 0:
                cols_dest = loader.load("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'bronze'
                      AND table_name = 'quickbooks_ventas_raw'
                    ORDER BY ordinal_position
                """)['column_name'].tolist()
                cols_ventas = [c for c in cols_dest if c != 'id']

                for c in cols_ventas:
                    if c not in df.columns:
                        df[c] = None

                loader.execute("TRUNCATE TABLE bronze.quickbooks_ventas_raw")
                loader.export(
                    df[cols_ventas],
                    schema_name='bronze',
                    table_name='quickbooks_ventas_raw',
                    if_exists='append',
                )
                print(f"    Registros cargados: {len(df)}")
                resultados['quickbooks_ventas_raw'] = len(df)

        # =====================================================================
        # 4) QUICKBOOKS STAGING: catalogo EAN raw
        # =====================================================================
        if 'quickbooks.stg_catalogo_ean_raw' in dfs:
            print(f"[4] Cargando quickbooks.stg_catalogo_ean_raw a bronze.quickbooks_catalogo_ean_raw...")
            dato = dfs['quickbooks.stg_catalogo_ean_raw']

            if isinstance(dato, list):
                df = pd.DataFrame(dato)
            elif isinstance(dato, pd.DataFrame):
                df = dato.copy()
            else:
                df = pd.DataFrame()

            if len(df) > 0:
                loader.execute("""
                    CREATE TABLE IF NOT EXISTS bronze.quickbooks_catalogo_ean_raw (
                        id SERIAL PRIMARY KEY,
                        item TEXT,
                        description TEXT,
                        um TEXT,
                        price NUMERIC,
                        ean13 TEXT,
                        ean14 TEXT,
                        source_file TEXT,
                        source_sheet TEXT,
                        load_ts TIMESTAMPTZ,
                        row_hash TEXT,
                        fuente VARCHAR(50),
                        nombre_tabla_origen VARCHAR(100),
                        fecha_ingesta TIMESTAMP,
                        pipeline_id VARCHAR(50),
                        batch_id VARCHAR(50)
                    )
                """)
                cols_dest = loader.load("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'bronze'
                      AND table_name = 'quickbooks_catalogo_ean_raw'
                    ORDER BY ordinal_position
                """)['column_name'].tolist()
                cols_cat = [c for c in cols_dest if c != 'id']

                for c in cols_cat:
                    if c not in df.columns:
                        df[c] = None

                loader.execute("TRUNCATE TABLE bronze.quickbooks_catalogo_ean_raw")
                loader.export(
                    df[cols_cat],
                    schema_name='bronze',
                    table_name='quickbooks_catalogo_ean_raw',
                    if_exists='append',
                )
                print(f"    Registros cargados: {len(df)}")
                resultados['quickbooks_catalogo_ean_raw'] = len(df)

        # =====================================================================
        # 5) QUICKBOOKS STAGING: ventas Econespecias raw
        # =====================================================================
        if 'quickbooks.stg_ventas_econespecias_raw' in dfs:
            print(
                "[5] Cargando quickbooks.stg_ventas_econespecias_raw "
                "a bronze.quickbooks_ventas_econespecias_raw..."
            )
            dato = dfs['quickbooks.stg_ventas_econespecias_raw']

            if isinstance(dato, list):
                df = pd.DataFrame(dato)
            elif isinstance(dato, pd.DataFrame):
                df = dato.copy()
            else:
                df = pd.DataFrame()

            if len(df) > 0:
                loader.execute("""
                    CREATE TABLE IF NOT EXISTS bronze.quickbooks_ventas_econespecias_raw (
                        id SERIAL PRIMARY KEY,
                        marca TEXT,
                        familia TEXT,
                        producto TEXT,
                        recuento_cliente INTEGER,
                        cantidad NUMERIC,
                        ventas NUMERIC,
                        anio INTEGER,
                        mes TEXT,
                        periodo DATE,
                        source_file TEXT,
                        source_sheet TEXT,
                        load_ts TIMESTAMPTZ,
                        row_hash TEXT,
                        fuente VARCHAR(50),
                        nombre_tabla_origen VARCHAR(100),
                        fecha_ingesta TIMESTAMP,
                        pipeline_id VARCHAR(50),
                        batch_id VARCHAR(50)
                    )
                """)
                cols_dest = loader.load("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'bronze'
                      AND table_name = 'quickbooks_ventas_econespecias_raw'
                    ORDER BY ordinal_position
                """)['column_name'].tolist()
                cols_ven = [c for c in cols_dest if c != 'id']

                for c in cols_ven:
                    if c not in df.columns:
                        df[c] = None

                loader.execute("TRUNCATE TABLE bronze.quickbooks_ventas_econespecias_raw")
                loader.export(
                    df[cols_ven],
                    schema_name='bronze',
                    table_name='quickbooks_ventas_econespecias_raw',
                    if_exists='append',
                )
                print(f"    Registros cargados: {len(df)}")
                resultados['quickbooks_ventas_econespecias_raw'] = len(df)

    print(f"\n{'='*70}")
    print(f"RESUMEN CARGA A BRONZE")
    print(f"{'='*70}")
    for tabla, registros in resultados.items():
        print(f"  {tabla}: {registros} registros")
    print(f"{'='*70}")

    # Verificacion final: evita reportar SUCCESS cuando faltan tablas clave.
    required_loaded = [
        'kronos_ventas_detalle_raw',
        'quickbooks_produccion_raw',
        'quickbooks_catalogo_ean_raw',
        'quickbooks_ventas_econespecias_raw',
    ]
    missing_loaded = [t for t in required_loaded if t not in resultados]
    if missing_loaded:
        raise RuntimeError(
            'Carga Bronze incompleta. Tablas criticas no cargadas: '
            + ', '.join(missing_loaded)
        )
    
    return {
        'tablas': list(resultados.keys()),
        'registros': resultados,
        'pipeline_id': pipeline_id,
        'batch_id': batch_id,
        'status': 'SUCCESS'
    }


@test
def test_output(output, *args) -> None:
    assert output is not None, 'Carga fallo'
    assert output.get('status') == 'SUCCESS', 'Status no es SUCCESS'
    print(f"OK: Carga a Bronze completada - {output['registros']}")
