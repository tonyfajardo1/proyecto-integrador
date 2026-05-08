"""
Transformer: Crear esquemas y tablas del Data Warehouse
Pipeline: etl_bronze (primer bloque)
Ejecuta el script SQL para crear todos los esquemas y tablas.
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
def crear_estructura_dw(*args, **kwargs):
    """
    Crea todos los esquemas y tablas del Data Warehouse.
    Este bloque debe ejecutarse una sola vez antes de cargar datos.
    """

    config_path = path.join(get_repo_path(), 'io_config.yaml')
    config_profile = 'local_dwh'

    sql = '''
    -- ESQUEMAS
    DROP SCHEMA IF EXISTS bronze CASCADE;
    CREATE SCHEMA bronze;
    
    DROP SCHEMA IF EXISTS silver CASCADE;
    CREATE SCHEMA silver;
    
    DROP SCHEMA IF EXISTS gold CASCADE;
    CREATE SCHEMA gold;
    
    DROP SCHEMA IF EXISTS logs CASCADE;
    CREATE SCHEMA logs;

    -- BRONZE
    CREATE TABLE bronze.kronos_ventas_raw (id SERIAL PRIMARY KEY,
        columna_1 VARCHAR(255), columna_2 VARCHAR(255), columna_3 VARCHAR(255),
        columna_4 VARCHAR(255), columna_5 VARCHAR(255), columna_6 VARCHAR(255),
        columna_7 VARCHAR(255), columna_8 VARCHAR(255), columna_9 VARCHAR(255),
        columna_10 VARCHAR(255), columna_11 VARCHAR(255), columna_12 VARCHAR(255),
        columna_13 VARCHAR(255), columna_14 VARCHAR(255), columna_15 VARCHAR(255),
        fuente VARCHAR(50), nombre_tabla_origen VARCHAR(100),
        fecha_ingesta TIMESTAMP, pipeline_id VARCHAR(50), batch_id VARCHAR(50));

    CREATE TABLE bronze.quickbooks_produccion_raw (id SERIAL PRIMARY KEY,
        idsales VARCHAR(50), idsale VARCHAR(50), numero VARCHAR(50),
        fecha DATE, estado VARCHAR(50), cliente VARCHAR(255), idcliente VARCHAR(50),
        status VARCHAR(50), numitems INTEGER, numitemsprocesados INTEGER,
        num_lineas INTEGER, qty_pedida NUMERIC(15,2), qty_despachada NUMERIC(15,2),
        fuente VARCHAR(50), nombre_tabla_origen VARCHAR(100),
        fecha_ingesta TIMESTAMP, pipeline_id VARCHAR(50), batch_id VARCHAR(50));

    -- SILVER
    CREATE TABLE silver.kronos_ventas (id SERIAL PRIMARY KEY,
        centro_costo VARCHAR(100), codigo_producto VARCHAR(50), codigo_alterno VARCHAR(50),
        producto VARCHAR(255), mes VARCHAR(20), anio INTEGER,
        cant_venta NUMERIC(15,2), total_venta NUMERIC(15,2),
        cant_nc NUMERIC(15,2), total_nc NUMERIC(15,2),
        cant_devolucion NUMERIC(15,2), total_devolucion NUMERIC(15,2),
        cant_neto NUMERIC(15,2), total_neto NUMERIC(15,2),
        costo_venta NUMERIC(15,2), rentabilidad NUMERIC(15,2), prc_rentabilidad NUMERIC(8,4),
        es_dato_calidado BOOLEAN, flag_outlier BOOLEAN, flag_valor_nulo BOOLEAN,
        fecha_carga TIMESTAMP, fecha_actualizacion TIMESTAMP, pipeline_id VARCHAR(50), batch_id VARCHAR(50),
        registro_fuente VARCHAR(50));

    CREATE TABLE silver.quickbooks_produccion (id SERIAL PRIMARY KEY,
        idsales VARCHAR(50), idsale VARCHAR(50), numero_orden VARCHAR(50),
        fecha DATE, fecha_creacion TIMESTAMP, estado VARCHAR(50), cliente VARCHAR(255),
        idcliente VARCHAR(50), status_orden VARCHAR(50), items_planificados INTEGER,
        items_procesados INTEGER, items_pendientes INTEGER, num_lineas INTEGER,
        qty_total_planificada NUMERIC(15,2), qty_total_despachada NUMERIC(15,2),
        qty_pendiente NUMERIC(15,2), desviacion_absoluta NUMERIC(15,2),
        desviacion_porcentual NUMERIC(8,4), tasa_cumplimiento NUMERIC(8,4),
        es_dato_calidado BOOLEAN, flag_orden_atrasada BOOLEAN,
        fecha_carga TIMESTAMP, pipeline_id VARCHAR(50), batch_id VARCHAR(50));

    -- GOLD
    CREATE TABLE gold.kpis_ventas (id SERIAL PRIMARY KEY,
        centro_costo VARCHAR(100), codigo_producto VARCHAR(50), producto VARCHAR(255),
        mes VARCHAR(20), anio INTEGER, cant_venta NUMERIC(15,2), total_venta NUMERIC(15,2),
        cant_neto NUMERIC(15,2), total_neto NUMERIC(15,2), cant_devolucion NUMERIC(15,2),
        total_devolucion NUMERIC(15,2), tasa_devolucion_cant NUMERIC(8,4),
        tasa_devolucion_valor NUMERIC(8,4), nivel_devolucion VARCHAR(20),
        costo_venta NUMERIC(15,2), rentabilidad NUMERIC(15,2), prc_rentabilidad NUMERIC(8,4),
        margen_bruto NUMERIC(8,4), nivel_rentabilidad VARCHAR(20),
        ticket_promedio NUMERIC(15,2), margen_contribucion NUMERIC(8,4),
        fecha_calculo TIMESTAMP, pipeline_id VARCHAR(50), batch_id VARCHAR(50));

    CREATE TABLE gold.kpis_produccion (id SERIAL PRIMARY KEY,
        idsales VARCHAR(50), numero_orden VARCHAR(50), fecha DATE,
        fecha_creacion TIMESTAMP, estado VARCHAR(50), cliente VARCHAR(255),
        qty_total_planificada NUMERIC(15,2), qty_total_despachada NUMERIC(15,2),
        num_lineas INTEGER, desviacion_absoluta NUMERIC(15,2),
        desviacion_porcentual NUMERIC(8,4), tasa_cumplimiento NUMERIC(8,4),
        clasificacion_cumplimiento VARCHAR(20), dia_semana INTEGER,
        dia_semana_nombre VARCHAR(20), mes INTEGER, mes_nombre VARCHAR(20),
        semana_ano INTEGER, es_inicio_mes BOOLEAN, es_fin_mes BOOLEAN,
        fecha_calculo TIMESTAMP, pipeline_id VARCHAR(50), batch_id VARCHAR(50));

    CREATE TABLE gold.anomalias_agencias (id SERIAL PRIMARY KEY,
        agencia VARCHAR(100), ratio_devolucion NUMERIC(8,4), ratio_rentabilidad NUMERIC(8,4),
        ratio_costo NUMERIC(8,4), ticket_promedio NUMERIC(15,2),
        anomaly_score NUMERIC(10,6), es_anomalia BOOLEAN, nivel_alerta VARCHAR(20),
        zscore_devolucion NUMERIC(8,4), zscore_rentabilidad NUMERIC(8,4),
        zscore_costo NUMERIC(8,4), zscore_ticket NUMERIC(8,4),
        razon_alerta VARCHAR(255), modelo VARCHAR(50), n_estimators INTEGER,
        contamination NUMERIC(4,2), fecha_deteccion TIMESTAMP, pipeline_id VARCHAR(50));

    CREATE TABLE gold.clusters_productos (id SERIAL PRIMARY KEY,
        producto VARCHAR(255), tasa_devolucion NUMERIC(8,4), margen_rentabilidad NUMERIC(8,4),
        ticket_promedio NUMERIC(15,2), penetracion NUMERIC(8,4), total_ventas NUMERIC(15,2),
        cluster INTEGER, cluster_nombre VARCHAR(50), modelo VARCHAR(50), n_clusters INTEGER,
        silhouette_score NUMERIC(6,4), fecha_clustering TIMESTAMP, pipeline_id VARCHAR(50));

    CREATE TABLE gold.reglas_asociacion (id SERIAL PRIMARY KEY,
        antecedente TEXT, consecuente TEXT, soporte NUMERIC(8,6),
        confianza NUMERIC(8,6), lift NUMERIC(10,4), tipo_regla VARCHAR(50),
        modelo VARCHAR(50), min_support NUMERIC(6,4), min_confidence NUMERIC(6,4),
        fecha_generacion TIMESTAMP, pipeline_id VARCHAR(50));

    CREATE TABLE gold.predicciones_devolucion (id SERIAL PRIMARY KEY,
        centro_costo VARCHAR(100), producto VARCHAR(255), mes VARCHAR(20),
        tasa_devolucion_historica NUMERIC(8,4), margen_rentabilidad NUMERIC(8,4),
        ratio_costo NUMERIC(8,4), ticket_promedio NUMERIC(15,2), volumen NUMERIC(15,2),
        probabilidad_devolucion NUMERIC(5,4), prediccion_clase VARCHAR(20),
        nivel_riesgo VARCHAR(20), modelo VARCHAR(50), accuracy NUMERIC(5,4),
        precision_modelo NUMERIC(5,4), recall NUMERIC(5,4), f1_score NUMERIC(5,4),
        auc_roc NUMERIC(5,4), fecha_prediccion TIMESTAMP, pipeline_id VARCHAR(50));

    -- LOGS
    CREATE TABLE logs.pipeline_ejecuciones (id SERIAL PRIMARY KEY,
        pipeline_id VARCHAR(50), nombre_pipeline VARCHAR(100), run_id VARCHAR(50),
        estado VARCHAR(20), mensaje_error TEXT, fecha_inicio TIMESTAMP, fecha_fin TIMESTAMP,
        duracion_segundos INTEGER, registros_leidos INTEGER, registros_escritos INTEGER,
        registros_error INTEGER, parametros JSONB, metadata JSONB);

    CREATE TABLE logs.calidad_datos (id SERIAL PRIMARY KEY,
        tabla VARCHAR(100), columna VARCHAR(100), tipo_check VARCHAR(50),
        total_registros INTEGER, registros_validos INTEGER, registros_invalidos INTEGER,
        porcentaje_calidad NUMERIC(5,2), detalle_error TEXT,
        fecha_check TIMESTAMP, pipeline_id VARCHAR(50));
    '''

    print(f"\n{'='*70}")
    print(f"CREANDO ESTRUCTURA DEL DATA WAREHOUSE")
    print(f"{'='*70}\n")

    with Postgres.with_config(ConfigFileLoader(config_path, config_profile)) as loader:
        loader.execute(sql)

    print(f"[OK] Esquemas creados: bronze, silver, gold, logs")
    print(f"[OK] Tablas creadas exitosamente")
    print(f"\n{'='*70}\n")

    return {'status': 'SUCCESS', 'message': 'Data Warehouse creado correctamente'}


@test
def test_output(output, *args) -> None:
    assert output is not None, 'Fallo al crear estructura'
    print(f"OK: {output}")
