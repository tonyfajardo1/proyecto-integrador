"""
Data Exporter: Cargar datos a Silver
Pipeline: etl_silver
Persiste los datos transformados en la capa Silver.
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
def cargar_silver(data, *args, **kwargs):
    """
    Carga datos transformados a la capa Silver en PostgreSQL.

    Estructura del bloque (para defensa):
    1) Lee salida del transformador (`dfs`) y metadatos de trazabilidad.
    2) Ejecuta carga tabla por tabla con contrato de esquema explicito.
    3) Registra conteos por tabla para auditoria operativa.
    4) Valida que todas las tablas criticas hayan sido cargadas.

    Nota:
    - `quickbooks_ventas` usa insercion SQL manual para evitar conflictos del
      helper `loader.export` cuando el origen trae variaciones legacy.
    """
    
    print(f"\n[DEBUG] Tipo de data recibida: {type(data)}")
    
    # Extraer dataframes
    if isinstance(data, dict):
        dfs = data.get('dfs', {})
        pipeline_id = data.get('pipeline_id', 'etl_silver')
        batch_id = data.get('batch_id')
    else:
        dfs = {}
        pipeline_id = 'etl_silver'
        batch_id = None
    
    print(f"\n{'='*70}")
    print(f"CARGA - A CAPA SILVER")
    print(f"{'='*70}")
    print(f"Pipeline: {pipeline_id}")
    print(f"Batch: {batch_id}")
    print(f"Keys en dfs: {list(dfs.keys())}")
    print(f"{'='*70}\n")
    
    # Configurar conexion a DWH local
    config_path = path.join(get_repo_path(), 'io_config.yaml')
    config_profile = 'local_dwh'
    
    resultados = {}
    
    with Postgres.with_config(ConfigFileLoader(config_path, config_profile)) as loader:

        # =====================================================================
        # 1. CARGAR: Kronos Ventas
        # =====================================================================
        if 'kronos_ventas' in dfs:
            print(f"[1] Cargando kronos_ventas a silver.kronos_ventas...")

            dato = dfs['kronos_ventas']
            if isinstance(dato, list):
                df = pd.DataFrame(dato)
            elif isinstance(dato, pd.DataFrame):
                df = dato.copy()
            else:
                df = pd.DataFrame()

            if len(df) > 0:
                loader.execute("ALTER TABLE silver.kronos_ventas ALTER COLUMN cant_venta TYPE NUMERIC(15,2) USING cant_venta::numeric")
                loader.execute("ALTER TABLE silver.kronos_ventas ALTER COLUMN total_venta TYPE NUMERIC(15,2) USING total_venta::numeric")
                loader.execute("ALTER TABLE silver.kronos_ventas ALTER COLUMN cant_nc TYPE NUMERIC(15,2) USING cant_nc::numeric")
                loader.execute("ALTER TABLE silver.kronos_ventas ALTER COLUMN total_nc TYPE NUMERIC(15,2) USING total_nc::numeric")
                loader.execute("ALTER TABLE silver.kronos_ventas ALTER COLUMN cant_devolucion TYPE NUMERIC(15,2) USING cant_devolucion::numeric")
                loader.execute("ALTER TABLE silver.kronos_ventas ALTER COLUMN total_devolucion TYPE NUMERIC(15,2) USING total_devolucion::numeric")
                loader.execute("ALTER TABLE silver.kronos_ventas ALTER COLUMN cant_neto TYPE NUMERIC(15,2) USING cant_neto::numeric")
                loader.execute("ALTER TABLE silver.kronos_ventas ALTER COLUMN total_neto TYPE NUMERIC(15,2) USING total_neto::numeric")
                loader.execute('TRUNCATE TABLE silver.kronos_ventas')
                loader.export(df, schema_name='silver', table_name='kronos_ventas', if_exists='append')
                print(f"    Registros cargados: {len(df)}")
                resultados['kronos_ventas'] = len(df)

        # =====================================================================
        # 2. CARGAR: QuickBooks Produccion
        # =====================================================================
        if 'quickbooks_produccion' in dfs:
            print(f"[2] Cargando quickbooks_produccion a silver.quickbooks_produccion...")

            dato = dfs['quickbooks_produccion']
            if isinstance(dato, list):
                df = pd.DataFrame(dato)
            elif isinstance(dato, pd.DataFrame):
                df = dato.copy()
            else:
                df = pd.DataFrame()

            loader.execute(
                """
                CREATE TABLE IF NOT EXISTS silver.quickbooks_produccion (
                    id SERIAL PRIMARY KEY,
                    idsales VARCHAR(50), idsale VARCHAR(50), numero_orden VARCHAR(50),
                    fecha DATE, fecha_creacion TIMESTAMP, estado VARCHAR(50), cliente VARCHAR(255),
                    idcliente VARCHAR(50), status_orden VARCHAR(50), items_planificados INTEGER,
                    items_procesados INTEGER, items_pendientes INTEGER, num_lineas INTEGER,
                    qty_total_planificada NUMERIC(15,2), qty_total_despachada NUMERIC(15,2),
                    qty_pendiente NUMERIC(15,2), desviacion_absoluta NUMERIC(15,2),
                    desviacion_porcentual NUMERIC(8,4), tasa_cumplimiento NUMERIC(8,4),
                    clasificacion_cumplimiento VARCHAR(20),
                    es_dato_calidado BOOLEAN, flag_orden_atrasada BOOLEAN,
                    fecha_carga TIMESTAMP, pipeline_id VARCHAR(50), batch_id VARCHAR(50)
                )
                """
            )
            loader.execute('TRUNCATE TABLE silver.quickbooks_produccion')
            if len(df) > 0:
                loader.export(df, schema_name='silver', table_name='quickbooks_produccion', if_exists='append')
                print(f"    Registros cargados: {len(df)}")
                resultados['quickbooks_produccion'] = len(df)
            else:
                print("    Registros cargados: 0 (tabla truncada)")
                resultados['quickbooks_produccion'] = 0

        # =====================================================================
        # 3. CARGAR: QuickBooks Ventas
        # =====================================================================
        if 'quickbooks_ventas' in dfs:
            print(f"[3] Cargando quickbooks_ventas a silver.quickbooks_ventas...")

            dato = dfs['quickbooks_ventas']
            if isinstance(dato, list):
                df = pd.DataFrame(dato)
            elif isinstance(dato, pd.DataFrame):
                df = dato.copy()
            else:
                df = pd.DataFrame()

            # Reset estricto para evitar arrastrar esquemas legacy inferidos por export.
            loader.execute('DROP TABLE IF EXISTS silver.quickbooks_ventas')
            loader.execute(
                """
                CREATE TABLE silver.quickbooks_ventas (
                    id SERIAL PRIMARY KEY,
                    idsales VARCHAR(50), idsale VARCHAR(50), numero VARCHAR(50),
                    fecha DATE, estado VARCHAR(50), cliente VARCHAR(255),
                    idcliente VARCHAR(50), status VARCHAR(50), _status VARCHAR(50),
                    numitems INTEGER, numitemsprocesados INTEGER,
                    num_lineas INTEGER, productos_unicos INTEGER,
                    qty_pedida NUMERIC(15,2), qty_despachada NUMERIC(15,2),
                    qty_pendiente NUMERIC(15,2), tasa_cumplimiento NUMERIC(8,4),
                    es_dato_calidado BOOLEAN,
                    fecha_carga TIMESTAMP, pipeline_id VARCHAR(50), batch_id VARCHAR(50)
                )
                """
            )
            if len(df) > 0:
                cols_qv = [
                    'idsales', 'idsale', 'numero',
                    'fecha', 'estado', 'cliente',
                    'idcliente', 'status', '_status',
                    'numitems', 'numitemsprocesados',
                    'num_lineas', 'productos_unicos',
                    'qty_pedida', 'qty_despachada',
                    'qty_pendiente', 'tasa_cumplimiento',
                    'es_dato_calidado',
                    'fecha_carga', 'pipeline_id', 'batch_id',
                ]
                for c in cols_qv:
                    if c not in df.columns:
                        df[c] = None
                if 'status' in df.columns and '_status' in df.columns:
                    df['status'] = df['status'].fillna(df['_status'])
                elif '_status' in df.columns:
                    df['status'] = df['_status']
                if 'status' in df.columns:
                    df['status'] = df['status'].fillna('')
                df['_status'] = df['status']
                # Construir dataframe estricto por registros para evitar problemas
                # cuando el origen trae columnas duplicadas con el mismo nombre.
                # Este enfoque garantiza un esquema unico y estable para COPY.
                rows = df.to_dict(orient='records')
                df_export = pd.DataFrame(
                    [{c: row.get(c) for c in cols_qv} for row in rows],
                    columns=cols_qv,
                )
                # Re-materializar para eliminar cualquier metadata ambigua
                # de Pandas y garantizar nombres de columna simples y unicos.
                df_export = pd.DataFrame(df_export.to_numpy(), columns=cols_qv)
                df_export.columns = pd.Index([str(c).strip() for c in df_export.columns])
                if df_export.columns.duplicated().any():
                    raise RuntimeError(
                        'quickbooks_ventas tiene columnas duplicadas antes de exportar: '
                        + str(df_export.columns[df_export.columns.duplicated()].tolist())
                    )
                print(f"    Columnas export quickbooks_ventas: {df_export.columns.tolist()}")

                # Carga manual para este bloque: evita conflictos internos de
                # mage_ai.io.postgres.upload_dataframe con columnas legacy.
                # Se conserva una insercion determinista basada en el contrato
                # de `cols_qv` para asegurar reproducibilidad.
                insert_cols = list(df_export.columns)
                placeholders = ', '.join(['%s'] * len(insert_cols))
                insert_sql = (
                    f"INSERT INTO silver.quickbooks_ventas ({', '.join(insert_cols)}) "
                    f"VALUES ({placeholders})"
                )

                rows_to_insert = []
                for row in df_export.itertuples(index=False, name=None):
                    rows_to_insert.append(
                        tuple(None if pd.isna(v) else v for v in row)
                    )

                with loader.conn.cursor() as cur:
                    cur.executemany(insert_sql, rows_to_insert)
                loader.conn.commit()

                print(f"    Registros cargados: {len(df)}")
                resultados['quickbooks_ventas'] = len(df)
            else:
                print("    Registros cargados: 0 (tabla truncada)")
                resultados['quickbooks_ventas'] = 0

        # =====================================================================
        # 4. CARGAR: Transacciones Apriori
        # =====================================================================
        if 'apriori_transacciones' in dfs:
            print(f"[4] Cargando apriori_transacciones a silver.apriori_transacciones...")

            dato = dfs['apriori_transacciones']
            if isinstance(dato, list):
                df = pd.DataFrame(dato)
            elif isinstance(dato, pd.DataFrame):
                df = dato.copy()
            else:
                df = pd.DataFrame()

            loader.execute('TRUNCATE TABLE silver.apriori_transacciones')
            if len(df) > 0:
                loader.export(df, schema_name='silver', table_name='apriori_transacciones', if_exists='append')
                print(f"    Registros cargados: {len(df)}")
                resultados['apriori_transacciones'] = len(df)
            else:
                print("    Registros cargados: 0 (tabla truncada)")
                resultados['apriori_transacciones'] = 0

        # =====================================================================
        # 5. CARGAR: catalogo_ean_clean
        # =====================================================================
        if 'catalogo_ean_clean' in dfs:
            print(f"[5] Cargando catalogo_ean_clean a silver.catalogo_ean_clean...")
            dato = dfs['catalogo_ean_clean']
            df = pd.DataFrame(dato) if isinstance(dato, list) else (dato.copy() if isinstance(dato, pd.DataFrame) else pd.DataFrame())
            loader.execute(
                """
                CREATE TABLE IF NOT EXISTS silver.catalogo_ean_clean (
                    id SERIAL PRIMARY KEY,
                    item TEXT,
                    item_tail TEXT,
                    description TEXT,
                    producto_dashboard TEXT,
                    tipo_producto VARCHAR(20),
                    codigo_producto VARCHAR(20),
                    ean13 VARCHAR(20),
                    ean14 VARCHAR(20),
                    um VARCHAR(20),
                    price NUMERIC,
                    flag_ean13_valido BOOLEAN,
                    flag_desc_generica BOOLEAN,
                    fecha_carga TIMESTAMP,
                    pipeline_id VARCHAR(50),
                    batch_id VARCHAR(50)
                )
                """
            )
            loader.execute('TRUNCATE TABLE silver.catalogo_ean_clean')
            if len(df) > 0:
                loader.export(df, schema_name='silver', table_name='catalogo_ean_clean', if_exists='append')
            resultados['catalogo_ean_clean'] = len(df)
            print(f"    Registros cargados: {len(df)}")

        # =====================================================================
        # 6. CARGAR: ventas_econespecias_mensual_clean
        # =====================================================================
        if 'ventas_econespecias_mensual_clean' in dfs:
            print("[6] Cargando ventas_econespecias_mensual_clean a silver.ventas_econespecias_mensual_clean...")
            dato = dfs['ventas_econespecias_mensual_clean']
            df = pd.DataFrame(dato) if isinstance(dato, list) else (dato.copy() if isinstance(dato, pd.DataFrame) else pd.DataFrame())
            loader.execute(
                """
                CREATE TABLE IF NOT EXISTS silver.ventas_econespecias_mensual_clean (
                    id SERIAL PRIMARY KEY,
                    marca TEXT,
                    familia TEXT,
                    producto TEXT,
                    codigo_producto VARCHAR(20),
                    periodo DATE,
                    anio INTEGER,
                    mes TEXT,
                    recuento_cliente INTEGER,
                    cantidad NUMERIC,
                    ventas NUMERIC,
                    fecha_carga TIMESTAMP,
                    pipeline_id VARCHAR(50),
                    batch_id VARCHAR(50)
                )
                """
            )
            loader.execute('TRUNCATE TABLE silver.ventas_econespecias_mensual_clean')
            if len(df) > 0:
                loader.export(df, schema_name='silver', table_name='ventas_econespecias_mensual_clean', if_exists='append')
            resultados['ventas_econespecias_mensual_clean'] = len(df)
            print(f"    Registros cargados: {len(df)}")

        # =====================================================================
        # 7. CARGAR: dim_producto_canonico
        # =====================================================================
        if 'dim_producto_canonico' in dfs:
            print("[7] Cargando dim_producto_canonico a silver.dim_producto_canonico...")
            dato = dfs['dim_producto_canonico']
            df = pd.DataFrame(dato) if isinstance(dato, list) else (dato.copy() if isinstance(dato, pd.DataFrame) else pd.DataFrame())
            loader.execute(
                """
                CREATE TABLE IF NOT EXISTS silver.dim_producto_canonico (
                    id SERIAL PRIMARY KEY,
                    codigo_producto VARCHAR(20),
                    ean13 VARCHAR(20),
                    ean14 VARCHAR(20),
                    item_canonico TEXT,
                    description_canonica TEXT,
                    producto_dashboard TEXT,
                    tipo_producto VARCHAR(20),
                    estado_match VARCHAR(20),
                    flag_conflicto_ean13 BOOLEAN,
                    fecha_carga TIMESTAMP,
                    pipeline_id VARCHAR(50),
                    batch_id VARCHAR(50)
                )
                """
            )
            loader.execute('TRUNCATE TABLE silver.dim_producto_canonico')
            if len(df) > 0:
                loader.export(df, schema_name='silver', table_name='dim_producto_canonico', if_exists='append')
            resultados['dim_producto_canonico'] = len(df)
            print(f"    Registros cargados: {len(df)}")

        # =====================================================================
        # 8. CARGAR: forecasting_base_mensual_v1
        # =====================================================================
        if 'forecasting_base_mensual_v1' in dfs:
            print("[8] Cargando forecasting_base_mensual_v1 a silver.forecasting_base_mensual_v1...")
            dato = dfs['forecasting_base_mensual_v1']
            df = pd.DataFrame(dato) if isinstance(dato, list) else (dato.copy() if isinstance(dato, pd.DataFrame) else pd.DataFrame())
            loader.execute(
                """
                CREATE TABLE IF NOT EXISTS silver.forecasting_base_mensual_v1 (
                    id SERIAL PRIMARY KEY,
                    periodo DATE,
                    anio INTEGER,
                    mes INTEGER,
                    marca TEXT,
                    familia TEXT,
                    codigo_producto VARCHAR(20),
                    ean13 VARCHAR(20),
                    producto_item TEXT,
                    producto_dashboard TEXT,
                    tipo_producto VARCHAR(20),
                    qty_vendida NUMERIC,
                    ventas_valor NUMERIC,
                    clientes INTEGER,
                    estado_producto VARCHAR(20),
                    flag_catalogo_conflicto BOOLEAN,
                    fecha_carga TIMESTAMP,
                    pipeline_id VARCHAR(50),
                    batch_id VARCHAR(50)
                )
                """
            )
            loader.execute('TRUNCATE TABLE silver.forecasting_base_mensual_v1')
            if len(df) > 0:
                loader.export(df, schema_name='silver', table_name='forecasting_base_mensual_v1', if_exists='append')
            resultados['forecasting_base_mensual_v1'] = len(df)
            print(f"    Registros cargados: {len(df)}")

    print(f"\n{'='*70}")
    print(f"RESUMEN CARGA A SILVER")
    print(f"{'='*70}")
    for tabla, registros in resultados.items():
        print(f"  {tabla}: {registros} registros")
    print(f"{'='*70}")

    required_loaded = [
        'kronos_ventas',
        'quickbooks_produccion',
        'quickbooks_ventas',
        'apriori_transacciones',
        'catalogo_ean_clean',
        'ventas_econespecias_mensual_clean',
        'dim_producto_canonico',
        'forecasting_base_mensual_v1',
    ]
    missing_loaded = [t for t in required_loaded if t not in resultados]
    if missing_loaded:
        raise RuntimeError(
            'Carga Silver incompleta. Tablas criticas no cargadas: '
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
    assert 'status' in output, 'Falta status'
    assert output['status'] == 'SUCCESS', 'Status no es SUCCESS'
    print(f"OK: Carga completada - {output['registros']}")
