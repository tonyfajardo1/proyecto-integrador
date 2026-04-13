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


SILVER_TABLES = [
    'kronos_ventas',
    'quickbooks_produccion',
    'quickbooks_ventas',
    'apriori_transacciones',
    'productos',
    'agencias',
    'catalogo_ean_clean',
    'ventas_econespecias_mensual_clean',
    'dim_producto_canonico',
    'forecasting_base_mensual_v1',
    'dim_producto_master',
    'product_name_mapping',
    'product_code_conflicts',
    'product_quality_metrics',
    'pp_pt_mapping_manual',
    'pp_universe_produccion_2025',
    'forecasting_base_pp_produccion_v1',
    'forecasting_base_mensual_integrada_v1',
    'forecasting_v3_catalogo_pt_limpio',
    'forecasting_v3_pt_catalog_match_report',
    'forecasting_v3_pt_productos_no_catalogo',
    'forecasting_v3_pt_mensual_model',
    'forecasting_v3_pt_productos_model',
    'forecasting_v3_pp_mensual_model',
    'forecasting_v3_pp_productos_model',
]


@transformer
def crear_tablas_silver(*args, **kwargs):
    """
    Define el contrato fisico completo de Silver.

    Este bloque concentra el DDL de la capa. Los bloques posteriores solo leen,
    transforman y cargan datos sobre estas estructuras.
    """

    config_path = path.join(get_repo_path(), 'io_config.yaml')
    config_profile = 'local_dwh'

    sql = '''
    CREATE SCHEMA IF NOT EXISTS silver;

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
    DROP TABLE IF EXISTS silver.dim_producto_master;
    DROP TABLE IF EXISTS silver.product_name_mapping;
    DROP TABLE IF EXISTS silver.product_code_conflicts;
    DROP TABLE IF EXISTS silver.product_quality_metrics;
    DROP TABLE IF EXISTS silver.pp_pt_mapping_manual;
    DROP TABLE IF EXISTS silver.pp_universe_produccion_2025;
    DROP TABLE IF EXISTS silver.forecasting_base_pp_produccion_v1;
    DROP TABLE IF EXISTS silver.forecasting_base_mensual_integrada_v1;
    DROP TABLE IF EXISTS silver.forecasting_v3_catalogo_pt_limpio;
    DROP TABLE IF EXISTS silver.forecasting_v3_pt_catalog_match_report;
    DROP TABLE IF EXISTS silver.forecasting_v3_pt_productos_no_catalogo;
    DROP TABLE IF EXISTS silver.forecasting_v3_pt_mensual_model;
    DROP TABLE IF EXISTS silver.forecasting_v3_pt_productos_model;
    DROP TABLE IF EXISTS silver.forecasting_v3_pp_mensual_model;
    DROP TABLE IF EXISTS silver.forecasting_v3_pp_productos_model;

    CREATE TABLE silver.kronos_ventas (
        id SERIAL PRIMARY KEY,
        centro_costo VARCHAR(100),
        codigo_producto VARCHAR(50),
        codigo_alterno VARCHAR(50),
        producto VARCHAR(255),
        mes VARCHAR(20),
        anio INTEGER,
        cant_venta NUMERIC(15,2),
        total_venta NUMERIC(15,2),
        cant_nc NUMERIC(15,2),
        total_nc NUMERIC(15,2),
        cant_devolucion NUMERIC(15,2),
        total_devolucion NUMERIC(15,2),
        cant_neto NUMERIC(15,2),
        total_neto NUMERIC(15,2),
        costo_venta NUMERIC(15,2),
        rentabilidad NUMERIC(15,2),
        prc_rentabilidad NUMERIC(8,4),
        es_dato_calidado BOOLEAN,
        flag_outlier BOOLEAN,
        flag_valor_nulo BOOLEAN,
        fecha_carga TIMESTAMP,
        fecha_actualizacion TIMESTAMP,
        pipeline_id VARCHAR(50),
        batch_id VARCHAR(50),
        registro_fuente VARCHAR(50)
    );

    CREATE TABLE silver.quickbooks_produccion (
        id SERIAL PRIMARY KEY,
        idsales VARCHAR(50),
        idsale VARCHAR(50),
        numero_orden VARCHAR(50),
        fecha DATE,
        fecha_creacion TIMESTAMP,
        estado VARCHAR(50),
        cliente VARCHAR(255),
        idcliente VARCHAR(50),
        status_orden VARCHAR(50),
        items_planificados INTEGER,
        items_procesados INTEGER,
        items_pendientes INTEGER,
        num_lineas INTEGER,
        qty_total_planificada NUMERIC(15,2),
        qty_total_despachada NUMERIC(15,2),
        qty_pendiente NUMERIC(15,2),
        desviacion_absoluta NUMERIC(15,2),
        desviacion_porcentual NUMERIC(8,4),
        tasa_cumplimiento NUMERIC(8,4),
        clasificacion_cumplimiento VARCHAR(20),
        es_dato_calidado BOOLEAN,
        flag_orden_atrasada BOOLEAN,
        fecha_carga TIMESTAMP,
        pipeline_id VARCHAR(50),
        batch_id VARCHAR(50)
    );

    CREATE TABLE silver.quickbooks_ventas (
        id SERIAL PRIMARY KEY,
        idsales VARCHAR(50),
        idsale VARCHAR(50),
        numero VARCHAR(50),
        fecha DATE,
        estado VARCHAR(50),
        cliente VARCHAR(255),
        idcliente VARCHAR(50),
        status VARCHAR(50),
        _status VARCHAR(50),
        numitems INTEGER,
        numitemsprocesados INTEGER,
        num_lineas INTEGER,
        productos_unicos INTEGER,
        qty_pedida NUMERIC(15,2),
        qty_despachada NUMERIC(15,2),
        qty_pendiente NUMERIC(15,2),
        tasa_cumplimiento NUMERIC(8,4),
        es_dato_calidado BOOLEAN,
        fecha_carga TIMESTAMP,
        pipeline_id VARCHAR(50),
        batch_id VARCHAR(50)
    );

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

    CREATE TABLE silver.productos (
        id SERIAL PRIMARY KEY,
        codigo_producto VARCHAR(50) UNIQUE,
        nombre_producto VARCHAR(255),
        sku VARCHAR(100),
        categoria VARCHAR(100),
        subcategoria VARCHAR(100),
        unidad_medida VARCHAR(20),
        precio_venta NUMERIC(15,2),
        costo_unitario NUMERIC(15,2),
        proveedor VARCHAR(255),
        activo BOOLEAN,
        fecha_carga TIMESTAMP,
        pipeline_id VARCHAR(50)
    );

    CREATE TABLE silver.agencias (
        id SERIAL PRIMARY KEY,
        codigo_agencia VARCHAR(50) UNIQUE,
        nombre_agencia VARCHAR(255),
        ciudad VARCHAR(100),
        region VARCHAR(100),
        tipo_agencia VARCHAR(50),
        gerente VARCHAR(255),
        activo BOOLEAN,
        fecha_carga TIMESTAMP,
        pipeline_id VARCHAR(50)
    );

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

    CREATE TABLE silver.forecasting_base_mensual_v1 (
        id SERIAL PRIMARY KEY,
        periodo DATE,
        anio INTEGER,
        mes INTEGER,
        marca TEXT,
        familia TEXT,
        codigo_producto VARCHAR(20),
        sku_id VARCHAR(80),
        ean13 VARCHAR(20),
        producto_item TEXT,
        producto_dashboard TEXT,
        tipo_producto VARCHAR(20),
        categoria_producto TEXT,
        qty_vendida NUMERIC,
        ventas_valor NUMERIC,
        clientes INTEGER,
        estado_producto VARCHAR(20),
        flag_catalogo_conflicto BOOLEAN,
        calidad_sku VARCHAR(20),
        flag_codigo_conflicto BOOLEAN,
        flag_codigo_reciclado BOOLEAN,
        fecha_carga TIMESTAMP,
        pipeline_id VARCHAR(50),
        batch_id VARCHAR(50)
    );

    CREATE TABLE silver.dim_producto_master (
        id SERIAL PRIMARY KEY,
        sku_id VARCHAR(80),
        codigo_producto VARCHAR(20),
        producto_canonico TEXT,
        tipo_producto VARCHAR(20),
        categoria_producto TEXT,
        vigente_desde DATE,
        vigente_hasta DATE,
        activo BOOLEAN,
        calidad_sku VARCHAR(20),
        flag_codigo_reciclado BOOLEAN,
        fecha_carga TIMESTAMP,
        pipeline_id VARCHAR(50),
        batch_id VARCHAR(50)
    );

    CREATE TABLE silver.product_name_mapping (
        id SERIAL PRIMARY KEY,
        codigo_producto VARCHAR(20),
        nombre_original TEXT,
        nombre_normalizado TEXT,
        nombre_canonico TEXT,
        tipo_producto VARCHAR(20),
        categoria_producto TEXT,
        decision_sugerida VARCHAR(30),
        requiere_revision_manual BOOLEAN,
        flag_codigo_conflicto BOOLEAN,
        fecha_carga TIMESTAMP,
        pipeline_id VARCHAR(50),
        batch_id VARCHAR(50)
    );

    CREATE TABLE silver.product_code_conflicts (
        id SERIAL PRIMARY KEY,
        codigo_producto VARCHAR(20),
        nombres_distintos INTEGER,
        periodo_min DATE,
        periodo_max DATE,
        nombres_detectados TEXT,
        recomendacion VARCHAR(30),
        estado_resolucion VARCHAR(30),
        fecha_carga TIMESTAMP,
        pipeline_id VARCHAR(50),
        batch_id VARCHAR(50)
    );

    CREATE TABLE silver.product_quality_metrics (
        id SERIAL PRIMARY KEY,
        metric VARCHAR(80),
        metric_value TEXT,
        fecha_carga TIMESTAMP,
        pipeline_id VARCHAR(50),
        batch_id VARCHAR(50)
    );

    CREATE TABLE silver.pp_pt_mapping_manual (
        id SERIAL PRIMARY KEY,
        codigo_producto VARCHAR(20),
        nombre_normalizado TEXT,
        tipo_objetivo VARCHAR(10),
        estado VARCHAR(20),
        nota TEXT,
        fecha_carga TIMESTAMP,
        pipeline_id VARCHAR(50),
        batch_id VARCHAR(50)
    );

    CREATE TABLE silver.pp_universe_produccion_2025 (
        id SERIAL PRIMARY KEY,
        codigo_producto VARCHAR(20),
        nombre_normalizado TEXT,
        producto TEXT,
        tipo_objetivo VARCHAR(10),
        origen_regla VARCHAR(80),
        fecha_carga TIMESTAMP,
        pipeline_id VARCHAR(50),
        batch_id VARCHAR(50)
    );

    CREATE TABLE silver.forecasting_base_pp_produccion_v1 (
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
        categoria_producto TEXT,
        qty_vendida NUMERIC,
        ventas_valor NUMERIC,
        clientes INTEGER,
        estado_producto VARCHAR(20),
        flag_catalogo_conflicto BOOLEAN,
        fecha_carga TIMESTAMP,
        pipeline_id VARCHAR(50),
        batch_id VARCHAR(50)
    );

    CREATE TABLE silver.forecasting_base_mensual_integrada_v1 (
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
        categoria_producto TEXT,
        qty_vendida NUMERIC,
        ventas_valor NUMERIC,
        clientes INTEGER,
        estado_producto VARCHAR(20),
        flag_catalogo_conflicto BOOLEAN,
        fecha_carga TIMESTAMP,
        pipeline_id VARCHAR(50),
        batch_id VARCHAR(50)
    );

    CREATE TABLE silver.forecasting_v3_catalogo_pt_limpio (
        id SERIAL PRIMARY KEY,
        product_id VARCHAR(80),
        product_code VARCHAR(20),
        product_name TEXT,
        product_norm TEXT,
        item_leaf TEXT,
        item_leaf_norm TEXT,
        item_path TEXT,
        description TEXT,
        unit VARCHAR(20),
        price NUMERIC,
        ean13 VARCHAR(20),
        ean14 VARCHAR(20),
        is_leaf BOOLEAN,
        fecha_carga TIMESTAMP,
        pipeline_id VARCHAR(50),
        batch_id VARCHAR(50)
    );

    CREATE TABLE silver.forecasting_v3_pt_catalog_match_report (
        id SERIAL PRIMARY KEY,
        product_norm TEXT,
        producto_raw TEXT,
        product_code VARCHAR(20),
        cantidad_total NUMERIC,
        ventas_total NUMERIC,
        marca TEXT,
        familia TEXT,
        product_id VARCHAR(80),
        catalog_product_code VARCHAR(20),
        product_name TEXT,
        catalog_product_norm TEXT,
        item_leaf TEXT,
        item_leaf_norm TEXT,
        item_path TEXT,
        description TEXT,
        unit VARCHAR(20),
        price NUMERIC,
        ean13 VARCHAR(20),
        ean14 VARCHAR(20),
        is_leaf BOOLEAN,
        catalog_match_status VARCHAR(40),
        fecha_carga TIMESTAMP,
        pipeline_id VARCHAR(50),
        batch_id VARCHAR(50)
    );

    CREATE TABLE silver.forecasting_v3_pt_productos_no_catalogo (
        id SERIAL PRIMARY KEY,
        product_norm TEXT,
        producto_raw TEXT,
        product_code VARCHAR(20),
        cantidad_total NUMERIC,
        ventas_total NUMERIC,
        marca TEXT,
        familia TEXT,
        product_id VARCHAR(80),
        catalog_product_code VARCHAR(20),
        product_name TEXT,
        catalog_product_norm TEXT,
        item_leaf TEXT,
        item_leaf_norm TEXT,
        item_path TEXT,
        description TEXT,
        unit VARCHAR(20),
        price NUMERIC,
        ean13 VARCHAR(20),
        ean14 VARCHAR(20),
        is_leaf BOOLEAN,
        catalog_match_status VARCHAR(40),
        fecha_carga TIMESTAMP,
        pipeline_id VARCHAR(50),
        batch_id VARCHAR(50)
    );

    CREATE TABLE silver.forecasting_v3_pt_mensual_model (
        id SERIAL PRIMARY KEY,
        product_id VARCHAR(80),
        periodo DATE,
        target_qty NUMERIC,
        ventas NUMERIC,
        recuento_cliente NUMERIC,
        productos_raw_distintos INTEGER,
        target_qty_raw NUMERIC,
        product_code VARCHAR(20),
        product_name TEXT,
        product_norm TEXT,
        catalog_match_status VARCHAR(40),
        item_path TEXT,
        unit VARCHAR(20),
        price NUMERIC,
        ean13 VARCHAR(20),
        ean14 VARCHAR(20),
        marca TEXT,
        familia TEXT,
        cantidad_total_raw NUMERIC,
        ventas_total_raw NUMERIC,
        source_type VARCHAR(5),
        estado_producto VARCHAR(20),
        es_estacional BOOLEAN,
        share_top_3_meses NUMERIC(8,4),
        meses_estacionales_num TEXT,
        meses_estacionales TEXT,
        ultima_actividad DATE,
        dias_laborables NUMERIC,
        feriados_mes NUMERIC,
        promocion_general NUMERIC,
        temporada_alta_general NUMERIC,
        evento_comercial NUMERIC,
        variacion_precio_general_pct NUMERIC,
        pedidos_confirmados NUMERIC,
        preventa_confirmada NUMERIC,
        promocion_producto NUMERIC,
        cliente_grande_confirmado NUMERIC,
        cambio_pvp_pct NUMERIC,
        precio_planificado NUMERIC,
        riesgo_quiebre_stock NUMERIC,
        disponibilidad_materia_prima NUMERIC,
        ajuste_comercial_manual NUMERIC,
        fecha_carga TIMESTAMP,
        pipeline_id VARCHAR(50),
        batch_id VARCHAR(50)
    );

    CREATE TABLE silver.forecasting_v3_pt_productos_model (
        id SERIAL PRIMARY KEY,
        product_id VARCHAR(80),
        product_code VARCHAR(20),
        product_name TEXT,
        product_norm TEXT,
        catalog_match_status VARCHAR(40),
        item_path TEXT,
        unit VARCHAR(20),
        price NUMERIC,
        ean13 VARCHAR(20),
        ean14 VARCHAR(20),
        marca TEXT,
        familia TEXT,
        cantidad_total_raw NUMERIC,
        ventas_total_raw NUMERIC,
        source_type VARCHAR(5),
        total_qty NUMERIC,
        meses_en_serie INTEGER,
        primera_actividad DATE,
        ultima_actividad DATE,
        meses_con_actividad INTEGER,
        periodo_referencia DATE,
        corte_inactividad DATE,
        estado_producto VARCHAR(20),
        es_estacional BOOLEAN,
        share_top_3_meses NUMERIC(8,4),
        mediana_meses_activos_por_anio NUMERIC(8,2),
        meses_estacionales_num TEXT,
        meses_estacionales TEXT,
        fecha_carga TIMESTAMP,
        pipeline_id VARCHAR(50),
        batch_id VARCHAR(50)
    );

    CREATE TABLE silver.forecasting_v3_pp_mensual_model (
        id SERIAL PRIMARY KEY,
        product_id VARCHAR(80),
        periodo DATE,
        target_qty NUMERIC,
        q_planificada NUMERIC,
        q_liberada NUMERIC,
        q_fabricada NUMERIC,
        lotes INTEGER,
        ordenes INTEGER,
        target_qty_raw NUMERIC,
        product_code VARCHAR(20),
        product_name TEXT,
        product_norm TEXT,
        categoria_pp TEXT,
        source_type VARCHAR(5),
        catalog_match_status VARCHAR(40),
        estado_producto VARCHAR(20),
        es_estacional BOOLEAN,
        share_top_3_meses NUMERIC(8,4),
        meses_estacionales_num TEXT,
        meses_estacionales TEXT,
        ultima_actividad DATE,
        dias_laborables NUMERIC,
        feriados_mes NUMERIC,
        promocion_general NUMERIC,
        temporada_alta_general NUMERIC,
        evento_comercial NUMERIC,
        variacion_precio_general_pct NUMERIC,
        pedidos_confirmados NUMERIC,
        preventa_confirmada NUMERIC,
        promocion_producto NUMERIC,
        cliente_grande_confirmado NUMERIC,
        cambio_pvp_pct NUMERIC,
        precio_planificado NUMERIC,
        riesgo_quiebre_stock NUMERIC,
        disponibilidad_materia_prima NUMERIC,
        ajuste_comercial_manual NUMERIC,
        fecha_carga TIMESTAMP,
        pipeline_id VARCHAR(50),
        batch_id VARCHAR(50)
    );

    CREATE TABLE silver.forecasting_v3_pp_productos_model (
        id SERIAL PRIMARY KEY,
        product_id VARCHAR(80),
        product_code VARCHAR(20),
        product_name TEXT,
        product_norm TEXT,
        categoria_pp TEXT,
        source_type VARCHAR(5),
        catalog_match_status VARCHAR(40),
        total_qty NUMERIC,
        meses_en_serie INTEGER,
        primera_actividad DATE,
        ultima_actividad DATE,
        meses_con_actividad INTEGER,
        periodo_referencia DATE,
        corte_inactividad DATE,
        estado_producto VARCHAR(20),
        es_estacional BOOLEAN,
        share_top_3_meses NUMERIC(8,4),
        mediana_meses_activos_por_anio NUMERIC(8,2),
        meses_estacionales_num TEXT,
        meses_estacionales TEXT,
        fecha_carga TIMESTAMP,
        pipeline_id VARCHAR(50),
        batch_id VARCHAR(50)
    );
    '''

    print(f"\n{'='*70}")
    print("CREANDO TABLAS SILVER")
    print(f"{'='*70}\n")

    with Postgres.with_config(ConfigFileLoader(config_path, config_profile)) as loader:
        loader.execute(sql)
        loader.conn.commit()

    print("[OK] Tablas Silver creadas:")
    for table_name in SILVER_TABLES:
        print(f"  - silver.{table_name}")
    print(f"\n{'='*70}\n")

    return {'status': 'SUCCESS', 'tablas': SILVER_TABLES}


@test
def test_output(output, *args) -> None:
    assert output is not None, 'Fallo al crear tablas Silver'
    assert output.get('status') == 'SUCCESS', 'Status no es SUCCESS'
    print(f"OK: {output}")
