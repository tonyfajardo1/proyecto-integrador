"""
Transformer: Crear tablas de la Capa Silver
Pipeline: etl_silver
Crea las tablas de la capa Silver en el Data Warehouse.
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
def crear_tablas_silver(*args, **kwargs):
    """
    Crea la estructura fisica de la capa Silver.

    Flujo del bloque:
    1) Garantiza existencia del esquema `silver`.
    2) Hace reset controlado por tabla (sin CASCADE a nivel esquema).
    3) Crea todas las tablas curadas consumidas por ETL Silver y Forecasting.

    Nota para defensa:
    - Este bloque define el contrato de datos (nombres, tipos y granularidad)
      que deben respetar transformacion y carga.
    """

    config_path = path.join(get_repo_path(), 'io_config.yaml')
    config_profile = 'local_dwh'

    # SQL unificado: deja la capa en estado deterministicamente reproducible.
    sql = '''
    -- Esquema Silver
    CREATE SCHEMA IF NOT EXISTS silver;

    -- Reset controlado de tablas Silver (evita DROP SCHEMA CASCADE)
    DROP TABLE IF EXISTS silver.kronos_ventas;
    DROP TABLE IF EXISTS silver.quickbooks_produccion;
    DROP TABLE IF EXISTS silver.quickbooks_ventas;
    DROP TABLE IF EXISTS silver.apriori_transacciones;
    DROP TABLE IF EXISTS silver.productos;
    DROP TABLE IF EXISTS silver.agencias;
    DROP TABLE IF EXISTS silver.catalogo_ean_clean;
    DROP TABLE IF EXISTS silver.ventas_econespecias_mensual_clean;
    DROP TABLE IF EXISTS silver.dim_producto_canonico;
    DROP TABLE IF EXISTS silver.forecasting_base_mensual_v1;

    -- Tabla: kronos_ventas (datos curados)
    CREATE TABLE silver.kronos_ventas (
        id SERIAL PRIMARY KEY,
        centro_costo VARCHAR(100), codigo_producto VARCHAR(50), codigo_alterno VARCHAR(50),
        producto VARCHAR(255), mes VARCHAR(20), anio INTEGER,
        cant_venta NUMERIC(15,2), total_venta NUMERIC(15,2),
        cant_nc NUMERIC(15,2), total_nc NUMERIC(15,2),
        cant_devolucion NUMERIC(15,2), total_devolucion NUMERIC(15,2),
        cant_neto NUMERIC(15,2), total_neto NUMERIC(15,2),
        costo_venta NUMERIC(15,2), rentabilidad NUMERIC(15,2), prc_rentabilidad NUMERIC(8,4),
        es_dato_calidado BOOLEAN, flag_outlier BOOLEAN, flag_valor_nulo BOOLEAN,
        fecha_carga TIMESTAMP, fecha_actualizacion TIMESTAMP, pipeline_id VARCHAR(50), batch_id VARCHAR(50),
        registro_fuente VARCHAR(50)
    );

    -- Tabla: quickbooks_produccion (datos curados)
    CREATE TABLE silver.quickbooks_produccion (
        id SERIAL PRIMARY KEY,
        idsales VARCHAR(50), idsale VARCHAR(50), numero_orden VARCHAR(50),
        fecha DATE, fecha_creacion TIMESTAMP, estado VARCHAR(50), cliente VARCHAR(255),
        idcliente VARCHAR(50), status_orden VARCHAR(50), items_planificados INTEGER,
        items_procesados INTEGER, items_pendientes INTEGER, num_lineas INTEGER,
        qty_total_planificada NUMERIC(15,2), qty_total_despachada NUMERIC(15,2),
        qty_pendiente NUMERIC(15,2), desviacion_absoluta NUMERIC(15,2),
        desviacion_porcentual NUMERIC(8,4), tasa_cumplimiento NUMERIC(8,4),
        es_dato_calidado BOOLEAN, flag_orden_atrasada BOOLEAN,
        fecha_carga TIMESTAMP, pipeline_id VARCHAR(50), batch_id VARCHAR(50)
    );

    -- Tabla: quickbooks_ventas (datos curados)
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
    );

    -- Tabla: transacciones para Apriori (granularidad ticket-item)
    CREATE TABLE silver.apriori_transacciones (
        id SERIAL PRIMARY KEY,
        transaccion_id VARCHAR(120),
        fecha DATE,
        agencia VARCHAR(100),
        cliente VARCHAR(255),
        producto VARCHAR(255),
        categoria VARCHAR(120),
        qty NUMERIC(15,2),
        amount NUMERIC(15,2),
        fuente VARCHAR(50),
        pipeline_id VARCHAR(50),
        batch_id VARCHAR(50),
        fecha_carga TIMESTAMP
    );

    -- Tabla: productos (catalogo)
    CREATE TABLE silver.productos (
        id SERIAL PRIMARY KEY,
        codigo_producto VARCHAR(50) UNIQUE,
        nombre_producto VARCHAR(255), sku VARCHAR(100),
        categoria VARCHAR(100), subcategoria VARCHAR(100),
        unidad_medida VARCHAR(20), precio_venta NUMERIC(15,2),
        costo_unitario NUMERIC(15,2), proveedor VARCHAR(255),
        activo BOOLEAN, fecha_carga TIMESTAMP, pipeline_id VARCHAR(50)
    );

    -- Tabla: agencias (catalogo)
    CREATE TABLE silver.agencias (
        id SERIAL PRIMARY KEY,
        codigo_agencia VARCHAR(50) UNIQUE, nombre_agencia VARCHAR(255),
        ciudad VARCHAR(100), region VARCHAR(100), tipo_agencia VARCHAR(50),
        gerente VARCHAR(255), activo BOOLEAN,
        fecha_carga TIMESTAMP, pipeline_id VARCHAR(50)
    );

    -- Tabla: catalogo EAN limpio
    CREATE TABLE silver.catalogo_ean_clean (
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
    );

    -- Tabla: ventas econespecias mensual limpia
    CREATE TABLE silver.ventas_econespecias_mensual_clean (
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
    );

    -- Tabla: dimension canonica de producto
    CREATE TABLE silver.dim_producto_canonico (
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
    );

    -- Tabla base final para forecasting
    CREATE TABLE silver.forecasting_base_mensual_v1 (
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
    );
    '''

    print(f"\n{'='*70}")
    print(f"CREANDO TABLAS SILVER")
    print(f"{'='*70}\n")

    with Postgres.with_config(ConfigFileLoader(config_path, config_profile)) as loader:
        loader.execute(sql)

    print(
        "[OK] Tablas Silver creadas: kronos_ventas, quickbooks_produccion, quickbooks_ventas, "
        "apriori_transacciones, productos, agencias, catalogo_ean_clean, "
        "ventas_econespecias_mensual_clean, dim_producto_canonico, forecasting_base_mensual_v1"
    )
    print(f"\n{'='*70}\n")

    return {'status': 'SUCCESS'}


@test
def test_output(output, *args) -> None:
    assert output is not None, 'Fallo al crear tablas Silver'
    print(f"OK: {output}")
