-- ============================================================================
-- CONDIMENSA - DATA WAREHOUSE
-- Capa BRONZE: Datos crudos exactamente como vienen de las fuentes
-- ============================================================================

-- ============================================================================
-- BRONZE: Ventas de Kronos (datos comerciales)
-- Fuente: Kronos ERP -> Supabase -> Bronze
-- ============================================================================
DROP TABLE IF EXISTS bronze.kronos_ventas_raw;
CREATE TABLE bronze.kronos_ventas_raw (
    id SERIAL PRIMARY KEY,
    
    -- Datos crudos como vienen del Excel/SQL
    columna_1 VARCHAR(255),
    columna_2 VARCHAR(255),
    columna_3 VARCHAR(255),
    columna_4 VARCHAR(255),
    columna_5 VARCHAR(255),
    columna_6 VARCHAR(255),
    columna_7 VARCHAR(255),
    columna_8 VARCHAR(255),
    columna_9 VARCHAR(255),
    columna_10 VARCHAR(255),
    columna_11 VARCHAR(255),
    columna_12 VARCHAR(255),
    columna_13 VARCHAR(255),
    columna_14 VARCHAR(255),
    columna_15 VARCHAR(255),
    
    -- Metadatos de ingesta
    fuente VARCHAR(50) DEFAULT 'kronos',
    nombre_tabla_origen VARCHAR(100),
    fecha_ingesta TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pipeline_id VARCHAR(50),
    batch_id VARCHAR(50)
);

COMMENT ON TABLE bronze.kronos_ventas_raw IS 'Datos crudos de ventas Kronos - sin transformar';

-- ============================================================================
-- BRONZE: Produccion de QuickBooks
-- Fuente: QuickBooks (MySQL) -> Supabase -> Bronze
-- ============================================================================
DROP TABLE IF EXISTS bronze.quickbooks_produccion_raw;
CREATE TABLE bronze.quickbooks_produccion_raw (
    id SERIAL PRIMARY KEY,
    
    -- Datos crudos
    idsales VARCHAR(50),
    idsale VARCHAR(50),
    numero VARCHAR(50),
    fecha DATE,
    estado VARCHAR(50),
    cliente VARCHAR(255),
    idcliente VARCHAR(50),
    status VARCHAR(50),
    numitems INTEGER,
    numitemsprocesados INTEGER,
    num_lineas INTEGER,
    qty_pedida NUMERIC(15,2),
    qty_despachada NUMERIC(15,2),
    
    -- Metadatos de ingesta
    fuente VARCHAR(50) DEFAULT 'quickbooks',
    nombre_tabla_origen VARCHAR(100),
    fecha_ingesta TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pipeline_id VARCHAR(50),
    batch_id VARCHAR(50)
);

COMMENT ON TABLE bronze.quickbooks_produccion_raw IS 'Datos crudos de produccion QuickBooks - sin transformar';

-- ============================================================================
-- BRONZE: Ventas de QuickBooks
-- ============================================================================
DROP TABLE IF EXISTS bronze.quickbooks_ventas_raw;
CREATE TABLE bronze.quickbooks_ventas_raw (
    id SERIAL PRIMARY KEY,
    
    -- Datos crudos
    idsales VARCHAR(50),
    idsale VARCHAR(50),
    numero VARCHAR(50),
    fecha DATE,
    estado VARCHAR(50),
    cliente VARCHAR(255),
    idcliente VARCHAR(50),
    status VARCHAR(50),
    numitems INTEGER,
    numitemsprocesados INTEGER,
    num_lineas INTEGER,
    productos_unicos INTEGER,
    qty_pedida NUMERIC(15,2),
    qty_despachada NUMERIC(15,2),
    
    -- Metadatos de ingesta
    fuente VARCHAR(50) DEFAULT 'quickbooks',
    nombre_tabla_origen VARCHAR(100),
    fecha_ingesta TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pipeline_id VARCHAR(50),
    batch_id VARCHAR(50)
);

COMMENT ON TABLE bronze.quickbooks_ventas_raw IS 'Datos crudos de ventas QuickBooks - sin transformar';

-- ============================================================================
-- BRONZE: Items/Productos de QuickBooks
-- ============================================================================
DROP TABLE IF EXISTS bronze.quickbooks_items_raw;
CREATE TABLE bronze.quickbooks_items_raw (
    id SERIAL PRIMARY KEY,
    
    -- Datos crudos
    iditem VARCHAR(50),
    nombre VARCHAR(255),
    sku VARCHAR(100),
    tipo VARCHAR(50),
    precio_venta NUMERIC(15,2),
    costo NUMERIC(15,2),
    cuenta_gastos VARCHAR(100),
    cuenta_inventario VARCHAR(100),
    
    -- Metadatos de ingesta
    fuente VARCHAR(50) DEFAULT 'quickbooks',
    nombre_tabla_origen VARCHAR(100),
    fecha_ingesta TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pipeline_id VARCHAR(50),
    batch_id VARCHAR(50)
);

COMMENT ON TABLE bronze.quickbooks_items_raw IS 'Datos crudos de items QuickBooks - sin transformar';

-- ============================================================================
-- INDICES PARA BRONZE
-- ============================================================================
CREATE INDEX idx_bronze_kronos_fecha ON bronze.kronos_ventas_raw(fecha_ingesta);
CREATE INDEX idx_bronze_quickbooks_fecha ON bronze.quickbooks_produccion_raw(fecha_ingesta);
CREATE INDEX idx_bronze_pipeline ON bronze.kronos_ventas_raw(pipeline_id);
CREATE INDEX idx_bronze_batch ON bronze.kronos_ventas_raw(batch_id);
