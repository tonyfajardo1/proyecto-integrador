"""
Transformer: Crear tablas de la Capa Bronze
Pipeline: etl_bronze
Crea solo las tablas raw vigentes de Kronos y QuickBooks.
"""
from os import path

from mage_ai.io.config import ConfigFileLoader
from mage_ai.io.postgres import Postgres
from mage_ai.settings.repo import get_repo_path

if 'transformer' not in dir():
    from mage_ai.data_preparation.decorators import transformer
if 'test' not in dir():
    from mage_ai.data_preparation.decorators import test


BRONZE_TABLES = [
    'kronos_ventas_raw',
    'kronos_rentabilidad_raw',
    'quickbooks_produccion_raw',
    'quickbooks_ventas_raw',
    'quickbooks_catalogo_ean_raw',
    'quickbooks_ventas_econespecias_raw',
]


@transformer
def crear_tablas_bronze(*args, **kwargs):
    """
    Crea la estructura fisica minima de Bronze.

    Principio aplicado:
    - Bronze solo almacena las 6 tablas fuente reales.
    - No se guardan tablas derivadas, resueltas o agregadas en esta capa.
    """

    config_path = path.join(get_repo_path(), 'io_config.yaml')
    config_profile = 'local_dwh'

    sql = '''
    CREATE SCHEMA IF NOT EXISTS bronze;

    DROP TABLE IF EXISTS bronze.kronos_ventas_raw;
    DROP TABLE IF EXISTS bronze.kronos_rentabilidad_raw;
    DROP TABLE IF EXISTS bronze.quickbooks_produccion_raw;
    DROP TABLE IF EXISTS bronze.quickbooks_ventas_raw;
    DROP TABLE IF EXISTS bronze.quickbooks_catalogo_ean_raw;
    DROP TABLE IF EXISTS bronze.quickbooks_ventas_econespecias_raw;

    CREATE TABLE bronze.kronos_ventas_raw (
        id SERIAL PRIMARY KEY,
        fecha_factura TEXT,
        zonas TEXT,
        marca TEXT,
        nombre_producto TEXT,
        venta_neta TEXT,
        cantidad TEXT,
        source_file TEXT,
        extracted_at TIMESTAMPTZ,
        fuente VARCHAR(50),
        nombre_tabla_origen VARCHAR(100),
        fecha_ingesta TIMESTAMP,
        pipeline_id VARCHAR(50),
        batch_id VARCHAR(50)
    );

    CREATE TABLE bronze.kronos_rentabilidad_raw (
        id SERIAL PRIMARY KEY,
        fecha_factura TEXT,
        zonas TEXT,
        marca_producto TEXT,
        nombre_producto TEXT,
        venta_neta TEXT,
        costo TEXT,
        rentabilidad TEXT,
        source_file TEXT,
        extracted_at TIMESTAMPTZ,
        fuente VARCHAR(50),
        nombre_tabla_origen VARCHAR(100),
        fecha_ingesta TIMESTAMP,
        pipeline_id VARCHAR(50),
        batch_id VARCHAR(50)
    );

    CREATE TABLE bronze.quickbooks_produccion_raw (
        id SERIAL PRIMARY KEY,
        id_registro VARCHAR(50),
        fecha DATE,
        numero VARCHAR(50),
        lote VARCHAR(80),
        producto TEXT,
        qty_planificada NUMERIC(15,2),
        qty_liberada NUMERIC(15,2),
        qty_fabricada NUMERIC(15,2),
        fuente VARCHAR(50),
        nombre_tabla_origen VARCHAR(100),
        fecha_ingesta TIMESTAMP,
        pipeline_id VARCHAR(50),
        batch_id VARCHAR(50)
    );

    CREATE TABLE bronze.quickbooks_ventas_raw (
        id SERIAL PRIMARY KEY,
        idsales VARCHAR(50),
        idsale VARCHAR(50),
        numero VARCHAR(50),
        fecha TIMESTAMP,
        estado VARCHAR(80),
        status VARCHAR(80),
        _status VARCHAR(80),
        cliente TEXT,
        idcliente VARCHAR(50),
        asesor TEXT,
        item TEXT,
        tipo_documento VARCHAR(80),
        numitems INTEGER,
        numitemsprocesados INTEGER,
        numitemsopen INTEGER,
        num_lineas INTEGER,
        productos_unicos INTEGER,
        qty_pedida NUMERIC(15,2),
        qty_despachada NUMERIC(15,2),
        qty NUMERIC(15,2),
        sales_price NUMERIC(15,4),
        amount NUMERIC(15,2),
        nick VARCHAR(100),
        qb VARCHAR(80),
        idinvoice VARCHAR(80),
        fuente VARCHAR(50),
        nombre_tabla_origen VARCHAR(100),
        fecha_ingesta TIMESTAMP,
        pipeline_id VARCHAR(50),
        batch_id VARCHAR(50)
    );

    CREATE TABLE bronze.quickbooks_catalogo_ean_raw (
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
    );

    CREATE TABLE bronze.quickbooks_ventas_econespecias_raw (
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
    );
    '''

    print(f"\n{'='*70}")
    print('CREANDO TABLAS BRONZE')
    print(f"{'='*70}\n")

    with Postgres.with_config(ConfigFileLoader(config_path, config_profile)) as loader:
        loader.execute(sql)
        loader.conn.commit()

    print('[OK] Tablas Bronze creadas:')
    for table_name in BRONZE_TABLES:
        print(f'  - bronze.{table_name}')
    print(f"\n{'='*70}\n")

    return {'status': 'SUCCESS', 'tablas': BRONZE_TABLES}


@test
def test_output(output, *args) -> None:
    assert output is not None, 'Fallo al crear tablas Bronze'
    assert output.get('status') == 'SUCCESS', 'Status no es SUCCESS'
    print(f"OK: {output}")
