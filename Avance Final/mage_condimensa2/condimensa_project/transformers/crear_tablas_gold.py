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
    DROP TABLE IF EXISTS gold.resumen_ejecutivo_kronos;
    DROP TABLE IF EXISTS gold.metricas_agencias;
    DROP TABLE IF EXISTS gold.metricas_productos;
    DROP TABLE IF EXISTS gold.quickbooks_indicadores_comerciales;
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

    -- Gold: Resumen Ejecutivo Kronos (sin dependencia de producto)
    CREATE TABLE gold.resumen_ejecutivo_kronos (
        id SERIAL PRIMARY KEY,
        centro_costo VARCHAR(100),
        mes VARCHAR(20),
        anio INTEGER,
        cant_venta NUMERIC(15,2),
        total_venta NUMERIC(15,2),
        cant_neto NUMERIC(15,2),
        total_neto NUMERIC(15,2),
        cant_devolucion NUMERIC(15,2),
        total_devolucion NUMERIC(15,2),
        costo_venta NUMERIC(15,2),
        rentabilidad NUMERIC(15,2),
        tasa_devolucion NUMERIC(8,4),
        rentabilidad_promedio NUMERIC(8,4),
        ticket_promedio NUMERIC(15,2),
        fecha_calculo TIMESTAMP,
        pipeline_id VARCHAR(50),
        batch_id VARCHAR(50)
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

    -- Gold: Indicadores comerciales QuickBooks
    CREATE TABLE gold.quickbooks_indicadores_comerciales (
        id SERIAL PRIMARY KEY,
        fecha DATE,
        anio INTEGER,
        mes INTEGER,
        mes_nombre VARCHAR(20),
        agencia VARCHAR(100),
        cliente VARCHAR(255),
        familia VARCHAR(120),
        producto VARCHAR(255),
        cantidad NUMERIC(15,2),
        venta_neta NUMERIC(15,2),
        transacciones INTEGER,
        fuente_dato VARCHAR(60),
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
        loader.conn.commit()

    print(
        "[OK] Tablas Gold creadas: "
        "kpis_ventas, resumen_ejecutivo_kronos, metricas_agencias, "
        "metricas_productos, quickbooks_indicadores_comerciales"
    )
    print(f"[OK] Tablas Logs creadas: pipeline_ejecuciones, calidad_datos")
    print(f"\n{'='*70}\n")

    return {'status': 'SUCCESS'}


@test
def test_output(output, *args) -> None:
    assert output is not None, 'Fallo al crear tablas Gold'
    print(f"OK: {output}")
