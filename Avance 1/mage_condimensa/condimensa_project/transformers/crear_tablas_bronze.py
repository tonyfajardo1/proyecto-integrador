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
    """Crea las tablas de la capa Bronze."""

    config_path = path.join(get_repo_path(), 'io_config.yaml')
    config_profile = 'local_dwh'

    sql = '''
    -- Esquema Bronze
    DROP SCHEMA IF EXISTS bronze CASCADE;
    CREATE SCHEMA bronze;

    -- Tabla: kronos_ventas_raw
    CREATE TABLE bronze.kronos_ventas_raw (
        id SERIAL PRIMARY KEY,
        columna_1 VARCHAR(255), columna_2 VARCHAR(255), columna_3 VARCHAR(255),
        columna_4 VARCHAR(255), columna_5 VARCHAR(255), columna_6 VARCHAR(255),
        columna_7 VARCHAR(255), columna_8 VARCHAR(255), columna_9 VARCHAR(255),
        columna_10 VARCHAR(255), columna_11 VARCHAR(255), columna_12 VARCHAR(255),
        columna_13 VARCHAR(255), columna_14 VARCHAR(255), columna_15 VARCHAR(255),
        fuente VARCHAR(50), nombre_tabla_origen VARCHAR(100),
        fecha_ingesta TIMESTAMP, pipeline_id VARCHAR(50), batch_id VARCHAR(50)
    );

    -- Tabla: quickbooks_produccion_raw
    CREATE TABLE bronze.quickbooks_produccion_raw (
        id SERIAL PRIMARY KEY,
        idsales VARCHAR(50), idsale VARCHAR(50), numero VARCHAR(50),
        fecha DATE, estado VARCHAR(50), cliente VARCHAR(255), idcliente VARCHAR(50),
        status VARCHAR(50), numitems INTEGER, numitemsprocesados INTEGER,
        num_lineas INTEGER, qty_pedida NUMERIC(15,2), qty_despachada NUMERIC(15,2),
        fuente VARCHAR(50), nombre_tabla_origen VARCHAR(100),
        fecha_ingesta TIMESTAMP, pipeline_id VARCHAR(50), batch_id VARCHAR(50)
    );

    -- Tabla: quickbooks_ventas_raw
    CREATE TABLE bronze.quickbooks_ventas_raw (
        id SERIAL PRIMARY KEY,
        idsales VARCHAR(50), idsale VARCHAR(50), numero VARCHAR(50),
        fecha DATE, estado VARCHAR(50), cliente VARCHAR(255), idcliente VARCHAR(50),
        status VARCHAR(50), numitems INTEGER, numitemsprocesados INTEGER,
        num_lineas INTEGER, productos_unicos INTEGER,
        qty_pedida NUMERIC(15,2), qty_despachada NUMERIC(15,2),
        fuente VARCHAR(50), nombre_tabla_origen VARCHAR(100),
        fecha_ingesta TIMESTAMP, pipeline_id VARCHAR(50), batch_id VARCHAR(50)
    );
    '''

    print(f"\n{'='*70}")
    print(f"CREANDO TABLAS BRONZE")
    print(f"{'='*70}\n")

    with Postgres.with_config(ConfigFileLoader(config_path, config_profile)) as loader:
        loader.execute(sql)

    print(f"[OK] Tablas Bronze creadas: kronos_ventas_raw, quickbooks_produccion_raw, quickbooks_ventas_raw")
    print(f"\n{'='*70}\n")

    return {'status': 'SUCCESS'}


@test
def test_output(output, *args) -> None:
    assert output is not None, 'Fallo al crear tablas Bronze'
    print(f"OK: {output}")
