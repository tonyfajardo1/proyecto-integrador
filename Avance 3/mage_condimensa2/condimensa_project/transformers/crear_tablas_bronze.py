"""
Transformer: Crear tablas de la Capa Bronze
Pipeline: etl_bronze
Crea las tablas de la capa Bronze en el Data Warehouse.
"""
from mage_ai.settings.repo import get_repo_path
from mage_ai.io.config import ConfigFileLoader
from mage_ai.io.postgres import Postgres
from os import path

if 'transformer' not in dir():
    from mage_ai.data_preparation.decorators import transformer
if 'test' not in dir():
    from mage_ai.data_preparation.decorators import test


@transformer
def crear_tablas_bronze(*args, **kwargs):
    """
    Crea la estructura fisica de la capa Bronze.

    Criterios de diseno:
    - Re-crear tablas de forma controlada sin eliminar el esquema completo.
    - Mantener una tabla por fuente granular (Kronos y QuickBooks).
    - Preservar columnas de trazabilidad para auditoria de lote.
    """

    config_path = path.join(get_repo_path(), 'io_config.yaml')
    config_profile = 'local_dwh'

    # Nota operativa:
    # Se usa DROP TABLE por tabla para evitar efectos colaterales de un
    # DROP SCHEMA CASCADE sobre objetos ajenos al pipeline.
    sql = '''
    -- Esquema Bronze
    CREATE SCHEMA IF NOT EXISTS bronze;

    -- Reset controlado de tablas Bronze (evita DROP SCHEMA CASCADE)
    DROP TABLE IF EXISTS bronze.kronos_ventas_raw;
    DROP TABLE IF EXISTS bronze.kronos_ventas_detalle_raw;
    DROP TABLE IF EXISTS bronze.kronos_ventas_resumen_raw;
    DROP TABLE IF EXISTS bronze.quickbooks_produccion_raw;
    DROP TABLE IF EXISTS bronze.quickbooks_ventas_raw;
    DROP TABLE IF EXISTS bronze.quickbooks_catalogo_ean_raw;
    DROP TABLE IF EXISTS bronze.quickbooks_ventas_econespecias_raw;

    -- Tabla: kronos_ventas_raw (16 columnas: ultima es MES)
    CREATE TABLE bronze.kronos_ventas_raw (
        id SERIAL PRIMARY KEY,
        columna_1 VARCHAR(255), columna_2 VARCHAR(255), columna_3 VARCHAR(255),
        columna_4 VARCHAR(255), columna_5 VARCHAR(255), columna_6 VARCHAR(255),
        columna_7 VARCHAR(255), columna_8 VARCHAR(255), columna_9 VARCHAR(255),
        columna_10 VARCHAR(255), columna_11 VARCHAR(255), columna_12 VARCHAR(255),
        columna_13 VARCHAR(255), columna_14 VARCHAR(255), columna_15 VARCHAR(255),
        columna_16 VARCHAR(50),
        fuente VARCHAR(50), nombre_tabla_origen VARCHAR(100),
        fecha_ingesta TIMESTAMP, pipeline_id VARCHAR(50), batch_id VARCHAR(50)
    );

    -- Tabla: kronos_ventas_detalle_raw (transaccional para Apriori)
    CREATE TABLE bronze.kronos_ventas_detalle_raw (
        id SERIAL PRIMARY KEY,
        id_factura BIGINT,
        serie TEXT,
        numero_factura BIGINT,
        fecha_ingreso TIMESTAMP,
        fecha_factura TIMESTAMP,
        fecha_vencimiento TIMESTAMP,
        vendedor TEXT,
        empleado TEXT,
        titulo_gratuito NUMERIC(15,4),
        id_detalle BIGINT,
        cantidad NUMERIC(15,4),
        valor_unitario NUMERIC(15,4),
        valor_total NUMERIC(15,4),
        descuento NUMERIC(15,4),
        id_producto BIGINT,
        id_unidad BIGINT,
        costo NUMERIC(15,4),
        id_promocion BIGINT,
        tipo_precio BIGINT,
        tipo_producto BIGINT,
        id_motivo BIGINT,
        id_cliente BIGINT,
        id_sucursal BIGINT,
        vendedor_name_rutero TEXT,
        supervisor_name TEXT,
        cod_rutero TEXT,
        nombre_rutero TEXT,
        ci_empleado TEXT,
        ci_empleado_s TEXT,
        razon_social TEXT,
        nombre_comercial TEXT,
        codigo_producto TEXT,
        descripcion_producto TEXT,
        nombre_subgrupo TEXT,
        descripcion_grupo TEXT,
        nombre_marca TEXT,
        linea_name TEXT,
        tipo TEXT,
        fuente VARCHAR(50),
        nombre_tabla_origen VARCHAR(100),
        fecha_ingesta TIMESTAMP,
        pipeline_id VARCHAR(50),
        batch_id VARCHAR(50)
    );

    -- Tabla: kronos_ventas_resumen_raw (reporte mensual normalizado desde Excel)
    CREATE TABLE bronze.kronos_ventas_resumen_raw (
        id SERIAL PRIMARY KEY,
        centro_costo VARCHAR(100),
        codigo_producto VARCHAR(50),
        codigo_alterno VARCHAR(50),
        producto VARCHAR(255),
        mes VARCHAR(20),
        anio INTEGER,
        cant_venta NUMERIC(15,4),
        total_venta NUMERIC(15,4),
        cant_nc NUMERIC(15,4),
        total_nc NUMERIC(15,4),
        cant_devolucion NUMERIC(15,4),
        total_devolucion NUMERIC(15,4),
        cant_neto NUMERIC(15,4),
        total_neto NUMERIC(15,4),
        costo_venta NUMERIC(15,4),
        rentabilidad NUMERIC(15,4),
        prc_rentabilidad NUMERIC(15,6),
        fuente VARCHAR(50),
        nombre_tabla_origen VARCHAR(100),
        fecha_ingesta TIMESTAMP,
        pipeline_id VARCHAR(50),
        batch_id VARCHAR(50)
    );

    -- Tabla: quickbooks_produccion_raw
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
        fuente VARCHAR(50), nombre_tabla_origen VARCHAR(100),
        fecha_ingesta TIMESTAMP, pipeline_id VARCHAR(50), batch_id VARCHAR(50)
    );

    -- Tabla: quickbooks_ventas_raw
    CREATE TABLE bronze.quickbooks_ventas_raw (
        idsales VARCHAR(50),
        idsale VARCHAR(50),
        nick VARCHAR(100),
        fecha DATE,
        numitemsprocesados INTEGER,
        estado VARCHAR(50),
        numero VARCHAR(50),
        cliente VARCHAR(255),
        idcliente VARCHAR(50),
        numitems INTEGER,
        qb VARCHAR(80),
        _status VARCHAR(50),
        idinvoice VARCHAR(80),
        numitemsopen INTEGER,
        num_lineas INTEGER,
        productos_unicos INTEGER,
        qty_pedida NUMERIC(15,2),
        qty_despachada NUMERIC(15,2),
        fuente VARCHAR(50), nombre_tabla_origen VARCHAR(100),
        fecha_ingesta TIMESTAMP, pipeline_id VARCHAR(50), batch_id VARCHAR(50)
    );

    -- Tabla: quickbooks_catalogo_ean_raw (staging Supabase)
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

    -- Tabla: quickbooks_ventas_econespecias_raw (staging Supabase)
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
    print(f"CREANDO TABLAS BRONZE")
    print(f"{'='*70}\n")

    with Postgres.with_config(ConfigFileLoader(config_path, config_profile)) as loader:
        loader.execute(sql)

    print(
        "[OK] Tablas Bronze creadas: kronos_ventas_raw, kronos_ventas_detalle_raw, "
        "kronos_ventas_resumen_raw, quickbooks_produccion_raw, quickbooks_ventas_raw, "
        "quickbooks_catalogo_ean_raw, quickbooks_ventas_econespecias_raw"
    )
    print(f"\n{'='*70}\n")

    return {'status': 'SUCCESS'}


@test
def test_output(output, *args) -> None:
    assert output is not None, 'Fallo al crear tablas Bronze'
    print(f"OK: {output}")
