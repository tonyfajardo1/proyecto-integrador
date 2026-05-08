"""
Transformer: Crear tablas de la Capa Gold
Pipeline: etl_gold
Crea las tablas de la capa Gold en el Data Warehouse.
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
def crear_tablas_gold(*args, **kwargs):
    """
    Crea la estructura de la capa Gold y del esquema de logs.

    Flujo del bloque:
    1) Garantiza existencia de esquemas `gold` y `logs`.
    2) Ejecuta reset controlado por tablas (sin `DROP SCHEMA ... CASCADE`).
    3) Crea tablas finales para KPIs y monitoreo de ejecuciones.

    Nota para defensa:
    - Este bloque define el contrato final de analitica consumido por
      dashboard y entregables, con tipos de datos estables y trazabilidad.
    """

    config_path = path.join(get_repo_path(), 'io_config.yaml')
    config_profile = 'local_dwh'

    # SQL unificado de inicializacion. Se evita CASCADE para proteger objetos
    # fuera del alcance del pipeline y mantener operaciones reversibles.
    sql = '''
    -- Esquemas base
    CREATE SCHEMA IF NOT EXISTS gold;
    CREATE SCHEMA IF NOT EXISTS logs;

    -- Reset controlado por tabla (sin DROP SCHEMA CASCADE)
    DROP TABLE IF EXISTS gold.kpis_ventas;
    DROP TABLE IF EXISTS gold.kpis_produccion;
    DROP TABLE IF EXISTS gold.kpis_quickbooks_ventas;
    DROP TABLE IF EXISTS gold.anomalias_agencias;
    DROP TABLE IF EXISTS gold.clusters_productos;
    DROP TABLE IF EXISTS gold.reglas_asociacion;
    DROP TABLE IF EXISTS gold.predicciones_devolucion;
    DROP TABLE IF EXISTS gold.metricas_agencias;
    DROP TABLE IF EXISTS gold.metricas_productos;
    DROP TABLE IF EXISTS gold.forecasting_productos_estacionales_v1;
    DROP TABLE IF EXISTS gold.forecasting_productos_inactivos_v1;
    DROP TABLE IF EXISTS logs.pipeline_ejecuciones;
    DROP TABLE IF EXISTS logs.calidad_datos;

    -- Gold: KPIs de Ventas
    CREATE TABLE gold.kpis_ventas (
        id SERIAL PRIMARY KEY,
        centro_costo VARCHAR(100), codigo_producto VARCHAR(50), producto VARCHAR(255),
        mes VARCHAR(20), anio INTEGER, cant_venta NUMERIC(15,2), total_venta NUMERIC(15,2),
        cant_neto NUMERIC(15,2), total_neto NUMERIC(15,2), cant_devolucion NUMERIC(15,2),
        total_devolucion NUMERIC(15,2), tasa_devolucion_cant NUMERIC(8,4),
        tasa_devolucion_valor NUMERIC(8,4), nivel_devolucion VARCHAR(20),
        costo_venta NUMERIC(15,2), rentabilidad NUMERIC(15,2), prc_rentabilidad NUMERIC(8,4),
        margen_bruto NUMERIC(8,4), nivel_rentabilidad VARCHAR(20),
        ticket_promedio NUMERIC(15,2), margen_contribucion NUMERIC(8,4),
        fecha_calculo TIMESTAMP, pipeline_id VARCHAR(50), batch_id VARCHAR(50)
    );

    -- Gold: KPIs de Produccion (agregado por cliente/orden)
    CREATE TABLE gold.kpis_produccion (
        id SERIAL PRIMARY KEY,
        cliente VARCHAR(255),
        numero_orden VARCHAR(50),
        qty_total_planificada NUMERIC(15,2), qty_total_despachada NUMERIC(15,2),
        total_lineas NUMERIC(15,2), num_ordenes INTEGER,
        tasa_cumplimiento NUMERIC(8,4), desviacion_total NUMERIC(15,2),
        fecha_calculo TIMESTAMP, pipeline_id VARCHAR(50), batch_id VARCHAR(50)
    );

    -- Gold: KPIs de Ventas QuickBooks (agregado por cliente)
    CREATE TABLE gold.kpis_quickbooks_ventas (
        id SERIAL PRIMARY KEY,
        cliente VARCHAR(255),
        qty_total_pedida NUMERIC(15,2),
        qty_total_despachada NUMERIC(15,2),
        total_lineas NUMERIC(15,2),
        total_productos NUMERIC(15,2),
        num_ordenes INTEGER,
        tasa_cumplimiento NUMERIC(8,4),
        fecha_calculo TIMESTAMP, pipeline_id VARCHAR(50), batch_id VARCHAR(50)
    );

    -- Gold: Anomalias de Agencias
    CREATE TABLE gold.anomalias_agencias (
        id SERIAL PRIMARY KEY,
        agencia VARCHAR(100), ratio_devolucion NUMERIC(8,4), ratio_rentabilidad NUMERIC(8,4),
        ratio_costo NUMERIC(8,4), ticket_promedio NUMERIC(15,2),
        anomaly_score NUMERIC(10,6), es_anomalia BOOLEAN, nivel_alerta VARCHAR(20),
        zscore_devolucion NUMERIC(8,4), zscore_rentabilidad NUMERIC(8,4),
        zscore_costo NUMERIC(8,4), zscore_ticket NUMERIC(8,4),
        razon_alerta VARCHAR(255), modelo VARCHAR(50), n_estimators INTEGER,
        contamination NUMERIC(4,2), fecha_deteccion TIMESTAMP, pipeline_id VARCHAR(50)
    );

    -- Gold: Clusters de Productos
    CREATE TABLE gold.clusters_productos (
        id SERIAL PRIMARY KEY,
        producto VARCHAR(255), tasa_devolucion NUMERIC(8,4), margen_rentabilidad NUMERIC(8,4),
        ticket_promedio NUMERIC(15,2), penetracion NUMERIC(8,4), total_ventas NUMERIC(15,2),
        cluster INTEGER, cluster_nombre VARCHAR(50), modelo VARCHAR(50), n_clusters INTEGER,
        silhouette_score NUMERIC(6,4), fecha_clustering TIMESTAMP, pipeline_id VARCHAR(50)
    );

    -- Gold: Reglas de Asociacion
    CREATE TABLE gold.reglas_asociacion (
        id SERIAL PRIMARY KEY,
        antecedente TEXT, consecuente TEXT, soporte NUMERIC(8,6),
        confianza NUMERIC(8,6), lift NUMERIC(10,4), tipo_regla VARCHAR(50),
        modelo VARCHAR(50), min_support NUMERIC(6,4), min_confidence NUMERIC(6,4),
        fecha_generacion TIMESTAMP, pipeline_id VARCHAR(50)
    );

    -- Gold: Predicciones de Devolucion
    CREATE TABLE gold.predicciones_devolucion (
        id SERIAL PRIMARY KEY,
        centro_costo VARCHAR(100), producto VARCHAR(255), mes VARCHAR(20),
        tasa_devolucion_historica NUMERIC(8,4), margen_rentabilidad NUMERIC(8,4),
        ratio_costo NUMERIC(8,4), ticket_promedio NUMERIC(15,2), volumen NUMERIC(15,2),
        probabilidad_devolucion NUMERIC(5,4), prediccion_clase VARCHAR(20),
        nivel_riesgo VARCHAR(20), modelo VARCHAR(50), accuracy NUMERIC(5,4),
        precision_modelo NUMERIC(5,4), recall NUMERIC(5,4), f1_score NUMERIC(5,4),
        auc_roc NUMERIC(5,4), fecha_prediccion TIMESTAMP, pipeline_id VARCHAR(50)
    );

    -- Gold: Metricas de Agencias (alineado a calculo actual)
    CREATE TABLE gold.metricas_agencias (
        id SERIAL PRIMARY KEY,
        centro_costo VARCHAR(100),
        total_venta NUMERIC(15,2),
        total_neto NUMERIC(15,2),
        cant_venta INTEGER,
        total_devolucion NUMERIC(15,2),
        rentabilidad NUMERIC(15,2),
        ticket_promedio NUMERIC(15,2),
        tasa_devolucion NUMERIC(8,4),
        rentabilidad_promedio NUMERIC(8,4),
        fecha_calculo TIMESTAMP,
        pipeline_id VARCHAR(50),
        batch_id VARCHAR(50)
    );

    -- Gold: Metricas de Productos (alineado a calculo actual)
    CREATE TABLE gold.metricas_productos (
        id SERIAL PRIMARY KEY,
        producto VARCHAR(255),
        total_venta NUMERIC(15,2),
        total_neto NUMERIC(15,2),
        cant_venta INTEGER,
        total_devolucion NUMERIC(15,2),
        rentabilidad NUMERIC(15,2),
        ticket_promedio NUMERIC(15,2),
        tasa_devolucion NUMERIC(8,4),
        rentabilidad_promedio NUMERIC(8,4),
        fecha_calculo TIMESTAMP,
        pipeline_id VARCHAR(50),
        batch_id VARCHAR(50)
    );

    -- Gold: Productos estacionales para analisis de forecasting
    CREATE TABLE gold.forecasting_productos_estacionales_v1 (
        id SERIAL PRIMARY KEY,
        producto_dashboard VARCHAR(255),
        tipo_producto VARCHAR(20),
        temporada_meses VARCHAR(50),
        meses_activos INTEGER,
        meses_observados INTEGER,
        active_share NUMERIC(8,4),
        total_qty_historica NUMERIC(18,2),
        producto_baja_rotacion BOOLEAN,
        pipeline_id VARCHAR(50),
        batch_id VARCHAR(50),
        fecha_ejecucion TIMESTAMP
    );

    -- Gold: Productos inactivos para analisis de forecasting
    CREATE TABLE gold.forecasting_productos_inactivos_v1 (
        id SERIAL PRIMARY KEY,
        producto_dashboard VARCHAR(255),
        tipo_producto VARCHAR(20),
        last_active_period DATE,
        months_since_last_active INTEGER,
        razon_vigencia VARCHAR(80),
        pipeline_id VARCHAR(50),
        batch_id VARCHAR(50),
        fecha_ejecucion TIMESTAMP
    );

    -- Logs: Ejecuciones de Pipelines
    CREATE TABLE logs.pipeline_ejecuciones (
        id SERIAL PRIMARY KEY,
        pipeline_id VARCHAR(50), nombre_pipeline VARCHAR(100), run_id VARCHAR(50),
        estado VARCHAR(20), mensaje_error TEXT, fecha_inicio TIMESTAMP, fecha_fin TIMESTAMP,
        duracion_segundos INTEGER, registros_leidos INTEGER, registros_escritos INTEGER,
        registros_error INTEGER, parametros JSONB, metadata JSONB
    );

    -- Logs: Calidad de Datos
    CREATE TABLE logs.calidad_datos (
        id SERIAL PRIMARY KEY,
        tabla VARCHAR(100), columna VARCHAR(100), tipo_check VARCHAR(50),
        total_registros INTEGER, registros_validos INTEGER, registros_invalidos INTEGER,
        porcentaje_calidad NUMERIC(5,2), detalle_error TEXT,
        fecha_check TIMESTAMP, pipeline_id VARCHAR(50)
    );
    '''

    print(f"\n{'='*70}")
    print(f"CREANDO TABLAS GOLD")
    print(f"{'='*70}\n")

    with Postgres.with_config(ConfigFileLoader(config_path, config_profile)) as loader:
        loader.execute(sql)

    print(f"[OK] Tablas Gold creadas: kpis_ventas, kpis_produccion, kpis_quickbooks_ventas, anomalias_agencias, clusters_productos, reglas_asociacion, predicciones_devolucion, metricas_agencias, metricas_productos, forecasting_productos_estacionales_v1, forecasting_productos_inactivos_v1")
    print(f"[OK] Tablas Logs creadas: pipeline_ejecuciones, calidad_datos")
    print(f"\n{'='*70}\n")

    return {'status': 'SUCCESS'}


@test
def test_output(output, *args) -> None:
    assert output is not None, 'Fallo al crear tablas Gold'
    print(f"OK: {output}")
