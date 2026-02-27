-- ============================================================================
-- CONDIMENSA - DATA WAREHOUSE
-- Capa SILVER: Datos curados, limpiados, normalizados
-- ============================================================================

-- ============================================================================
-- SILVER: Ventas de Kronos curadas
-- ============================================================================
DROP TABLE IF EXISTS silver.kronos_ventas;
CREATE TABLE silver.kronos_ventas (
    id SERIAL PRIMARY KEY,
    
    -- Dimensiones normalizadas
    centro_costo VARCHAR(100) NOT NULL,
    codigo_producto VARCHAR(50),
    codigo_alterno VARCHAR(50),
    producto VARCHAR(255) NOT NULL,
    mes VARCHAR(20) NOT NULL,
    anio INTEGER,
    
    -- Metricas de Venta
    cant_venta NUMERIC(15,2) DEFAULT 0,
    total_venta NUMERIC(15,2) DEFAULT 0,
    
    -- Metricas de Notas de Credito
    cant_nc NUMERIC(15,2) DEFAULT 0,
    total_nc NUMERIC(15,2) DEFAULT 0,
    
    -- Metricas de Devoluciones
    cant_devolucion NUMERIC(15,2) DEFAULT 0,
    total_devolucion NUMERIC(15,2) DEFAULT 0,
    
    -- Metricas Netas
    cant_neto NUMERIC(15,2) DEFAULT 0,
    total_neto NUMERIC(15,2) DEFAULT 0,
    
    -- Metricas de Rentabilidad
    costo_venta NUMERIC(15,2) DEFAULT 0,
    rentabilidad NUMERIC(15,2) DEFAULT 0,
    prc_rentabilidad NUMERIC(8,4) DEFAULT 0,
    
    -- Flags de calidad
    es_dato_calidado BOOLEAN DEFAULT TRUE,
    flag_outlier BOOLEAN DEFAULT FALSE,
    flag_valor_nulo BOOLEAN DEFAULT FALSE,
    
    -- Metadatos
    fecha_carga TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_actualizacion TIMESTAMP,
    pipeline_id VARCHAR(50),
    batch_id VARCHAR(50),
    registro_fuente VARCHAR(50)  -- ID del registro en bronze
);

-- Indices
CREATE INDEX idx_silver_kronos_cc ON silver.kronos_ventas(centro_costo);
CREATE INDEX idx_silver_kronos_prod ON silver.kronos_ventas(producto);
CREATE INDEX idx_silver_kronos_mes ON silver.kronos_ventas(mes);
CREATE INDEX idx_silver_kronos_anio ON silver.kronos_ventas(anio);
CREATE INDEX idx_silver_kronos_batch ON silver.kronos_ventas(batch_id);

COMMENT ON TABLE silver.kronos_ventas IS 'Datos curados de ventas Kronos - limpiados y validados';

-- ============================================================================
-- SILVER: Produccion de QuickBooks curada
-- ============================================================================
DROP TABLE IF EXISTS silver.quickbooks_produccion;
CREATE TABLE silver.quickbooks_produccion (
    id SERIAL PRIMARY KEY,
    
    -- Identificadores
    idsales VARCHAR(50),
    idsale VARCHAR(50),
    numero_orden VARCHAR(50),
    
    -- Dimensiones
    fecha DATE NOT NULL,
    fecha_creacion TIMESTAMP,
    estado VARCHAR(50),
    cliente VARCHAR(255),
    idcliente VARCHAR(50),
    status_orden VARCHAR(50),
    
    -- Metricas de Items
    items_planificados INTEGER DEFAULT 0,
    items_procesados INTEGER DEFAULT 0,
    items_pendientes INTEGER DEFAULT 0,
    num_lineas INTEGER DEFAULT 0,
    
    -- Metricas de Cantidad
    qty_total_planificada NUMERIC(15,2) DEFAULT 0,
    qty_total_despachada NUMERIC(15,2) DEFAULT 0,
    qty_pendiente NUMERIC(15,2) DEFAULT 0,
    
    -- Metricas de Desviacion
    desviacion_absoluta NUMERIC(15,2) DEFAULT 0,
    desviacion_porcentual NUMERIC(8,4) DEFAULT 0,
    tasa_cumplimiento NUMERIC(8,4) DEFAULT 0,
    
    -- Dimensiones temporales
    dia_semana INTEGER,
    dia_semana_nombre VARCHAR(20),
    mes INTEGER,
    mes_nombre VARCHAR(20),
    semana_ano INTEGER,
    es_inicio_mes BOOLEAN DEFAULT FALSE,
    es_fin_mes BOOLEAN DEFAULT FALSE,
    es_fin_semana BOOLEAN DEFAULT FALSE,
    
    -- Flags de calidad
    es_dato_calidado BOOLEAN DEFAULT TRUE,
    flag_orden_atrasada BOOLEAN DEFAULT FALSE,
    
    -- Metadatos
    fecha_carga TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pipeline_id VARCHAR(50),
    batch_id VARCHAR(50),
    registro_fuente VARCHAR(50)
);

CREATE INDEX idx_silver_prod_fecha ON silver.quickbooks_produccion(fecha);
CREATE INDEX idx_silver_prod_estado ON silver.quickbooks_produccion(estado);
CREATE INDEX idx_silver_prod_cliente ON silver.quickbooks_produccion(cliente);
CREATE INDEX idx_silver_prod_batch ON silver.quickbooks_produccion(batch_id);

COMMENT ON TABLE silver.quickbooks_produccion IS 'Datos curados de produccion QuickBooks - con metricas calculadas';

-- ============================================================================
-- SILVER: Ventas de QuickBooks curada
-- ============================================================================
DROP TABLE IF EXISTS silver.quickbooks_ventas;
CREATE TABLE silver.quickbooks_ventas (
    id SERIAL PRIMARY KEY,
    
    -- Identificadores
    idsales VARCHAR(50),
    idsale VARCHAR(50),
    numero_orden VARCHAR(50),
    
    -- Dimensiones
    fecha DATE NOT NULL,
    fecha_creacion TIMESTAMP,
    estado VARCHAR(50),
    cliente VARCHAR(255),
    idcliente VARCHAR(50),
    status_orden VARCHAR(50),
    
    -- Metricas
    num_items INTEGER DEFAULT 0,
    num_items_procesados INTEGER DEFAULT 0,
    num_lineas INTEGER DEFAULT 0,
    productos_unicos INTEGER DEFAULT 0,
    qty_pedida NUMERIC(15,2) DEFAULT 0,
    qty_despachada NUMERIC(15,2) DEFAULT 0,
    
    -- Dimensiones temporales
    dia_semana INTEGER,
    mes INTEGER,
    semana_ano INTEGER,
    
    -- Flags de calidad
    es_dato_calidado BOOLEAN DEFAULT TRUE,
    
    -- Metadatos
    fecha_carga TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pipeline_id VARCHAR(50),
    batch_id VARCHAR(50)
);

CREATE INDEX idx_silver_qb_ventas_fecha ON silver.quickbooks_ventas(fecha);
CREATE INDEX idx_silver_qb_ventas_cliente ON silver.quickbooks_ventas(cliente);

COMMENT ON TABLE silver.quickbooks_ventas IS 'Datos curados de ventas QuickBooks';

-- ============================================================================
-- SILVER: Catalogo de Productos
-- ============================================================================
DROP TABLE IF EXISTS silver.productos;
CREATE TABLE silver.productos (
    id SERIAL PRIMARY KEY,
    
    codigo_producto VARCHAR(50) UNIQUE,
    nombre_producto VARCHAR(255) NOT NULL,
    sku VARCHAR(100),
    categoria VARCHAR(100),
    subcategoria VARCHAR(100),
    unidad_medida VARCHAR(20),
    precio_venta NUMERIC(15,2),
    costo_unitario NUMERIC(15,2),
    proveedor VARCHAR(255),
    activo BOOLEAN DEFAULT TRUE,
    
    -- Metadatos
    fecha_carga TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pipeline_id VARCHAR(50)
);

CREATE INDEX idx_silver_prod_codigo ON silver.productos(codigo_producto);
CREATE INDEX idx_silver_prod_categoria ON silver.productos(categoria);

COMMENT ON TABLE silver.productos IS 'Catalogo de productos unificado';

-- ============================================================================
-- SILVER: Catalogo de Agencias/Centros de Costo
-- ============================================================================
DROP TABLE IF EXISTS silver.agencias;
CREATE TABLE silver.agencias (
    id SERIAL PRIMARY KEY,
    
    codigo_agencia VARCHAR(50) UNIQUE NOT NULL,
    nombre_agencia VARCHAR(255) NOT NULL,
    ciudad VARCHAR(100),
    region VARCHAR(100),
    tipo_agencia VARCHAR(50),
    gerente VARCHAR(255),
    activo BOOLEAN DEFAULT TRUE,
    
    -- Metadatos
    fecha_carga TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pipeline_id VARCHAR(50)
);

CREATE INDEX idx_silver_agencias_codigo ON silver.agencias(codigo_agencia);
CREATE INDEX idx_silver_agencias_ciudad ON silver.agencias(ciudad);

COMMENT ON TABLE silver.agencias IS 'Catalogo de agencias/centros de costo';
