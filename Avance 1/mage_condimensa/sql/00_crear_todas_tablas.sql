-- ============================================================================
-- CONDIMENSA - DATA WAREHOUSE COMPLETO
-- Arquitectura Medallion: Bronze → Silver → Gold
-- Autor: Anthony Fajardo
-- Fecha: Febrero 2026
-- ============================================================================

-- ============================================================================
-- ESQUEMAS
-- ============================================================================

-- BRONZE: Datos crudos exactamente como vienen de las fuentes
DROP SCHEMA IF EXISTS bronze CASCADE;
CREATE SCHEMA bronze;
COMMENT ON SCHEMA bronze IS 'Capa Bronze: Datos crudos tal como se ingestan desde las fuentes';

-- SILVER: Datos curados, limpiados, normalizados y validados
DROP SCHEMA IF EXISTS silver CASCADE;
CREATE SCHEMA silver;
COMMENT ON SCHEMA silver IS 'Capa Silver: Datos curados, limpiados, normalizados con reglas de negocio';

-- GOLD: Datos analiticos, KPIs calculados y resultados de Data Mining
DROP SCHEMA IF EXISTS gold CASCADE;
CREATE SCHEMA gold;
COMMENT ON SCHEMA gold IS 'Capa Gold: Datos analiticos listos para consumo, KPIs y resultados de ML';

-- LOGS: Auditoria y trazabilidad
DROP SCHEMA IF EXISTS logs CASCADE;
CREATE SCHEMA logs;
COMMENT ON SCHEMA logs IS 'Capa de Logs: Registro de ejecucion de pipelines para trazabilidad';

-- ============================================================================
-- TABLAS BRONZE
-- ============================================================================

-- Bron: Ventas de Kronos
DROP TABLE IF EXISTS bronze.kronos_ventas_raw;
CREATE TABLE bronze.kronos_ventas_raw (
    id SERIAL PRIMARY KEY,
    columna_1 VARCHAR(255), columna_2 VARCHAR(255), columna_3 VARCHAR(255),
    columna_4 VARCHAR(255), columna_5 VARCHAR(255), columna_6 VARCHAR(255),
    columna_7 VARCHAR(255), columna_8 VARCHAR(255), columna_9 VARCHAR(255),
    columna_10 VARCHAR(255), columna_11 VARCHAR(255), columna_12 VARCHAR(255),
    columna_13 VARCHAR(255), columna_14 VARCHAR(255), columna_15 VARCHAR(255),
    fuente VARCHAR(50) DEFAULT 'kronos',
    nombre_tabla_origen VARCHAR(100),
    fecha_ingesta TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pipeline_id VARCHAR(50),
    batch_id VARCHAR(50)
);

-- Bronze: Produccion de QuickBooks
DROP TABLE IF EXISTS bronze.quickbooks_produccion_raw;
CREATE TABLE bronze.quickbooks_produccion_raw (
    id SERIAL PRIMARY KEY,
    idsales VARCHAR(50), idsale VARCHAR(50), numero VARCHAR(50),
    fecha DATE, estado VARCHAR(50), cliente VARCHAR(255),
    idcliente VARCHAR(50), status VARCHAR(50), numitems INTEGER,
    numitemsprocesados INTEGER, num_lineas INTEGER,
    qty_pedida NUMERIC(15,2), qty_despachada NUMERIC(15,2),
    fuente VARCHAR(50) DEFAULT 'quickbooks',
    nombre_tabla_origen VARCHAR(100),
    fecha_ingesta TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pipeline_id VARCHAR(50),
    batch_id VARCHAR(50)
);

-- Bronze: Ventas de QuickBooks
DROP TABLE IF EXISTS bronze.quickbooks_ventas_raw;
CREATE TABLE bronze.quickbooks_ventas_raw (
    id SERIAL PRIMARY KEY,
    idsales VARCHAR(50), idsale VARCHAR(50), numero VARCHAR(50),
    fecha DATE, estado VARCHAR(50), cliente VARCHAR(255),
    idcliente VARCHAR(50), status VARCHAR(50), numitems INTEGER,
    numitemsprocesados INTEGER, num_lineas INTEGER, productos_unicos INTEGER,
    qty_pedida NUMERIC(15,2), qty_despachada NUMERIC(15,2),
    fuente VARCHAR(50) DEFAULT 'quickbooks',
    nombre_tabla_origen VARCHAR(100),
    fecha_ingesta TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pipeline_id VARCHAR(50),
    batch_id VARCHAR(50)
);

-- ============================================================================
-- TABLAS SILVER
-- ============================================================================

-- Silver: Ventas de Kronos curadas
DROP TABLE IF EXISTS silver.kronos_ventas;
CREATE TABLE silver.kronos_ventas (
    id SERIAL PRIMARY KEY,
    centro_costo VARCHAR(100) NOT NULL,
    codigo_producto VARCHAR(50),
    codigo_alterno VARCHAR(50),
    producto VARCHAR(255) NOT NULL,
    mes VARCHAR(20) NOT NULL,
    anio INTEGER,
    cant_venta NUMERIC(15,2) DEFAULT 0,
    total_venta NUMERIC(15,2) DEFAULT 0,
    cant_nc NUMERIC(15,2) DEFAULT 0,
    total_nc NUMERIC(15,2) DEFAULT 0,
    cant_devolucion NUMERIC(15,2) DEFAULT 0,
    total_devolucion NUMERIC(15,2) DEFAULT 0,
    cant_neto NUMERIC(15,2) DEFAULT 0,
    total_neto NUMERIC(15,2) DEFAULT 0,
    costo_venta NUMERIC(15,2) DEFAULT 0,
    rentabilidad NUMERIC(15,2) DEFAULT 0,
    prc_rentabilidad NUMERIC(8,4) DEFAULT 0,
    es_dato_calidado BOOLEAN DEFAULT TRUE,
    flag_outlier BOOLEAN DEFAULT FALSE,
    flag_valor_nulo BOOLEAN DEFAULT FALSE,
    fecha_carga TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_actualizacion TIMESTAMP,
    pipeline_id VARCHAR(50),
    batch_id VARCHAR(50),
    registro_fuente VARCHAR(50)
);

-- Silver: Produccion de QuickBooks curada
DROP TABLE IF EXISTS silver.quickbooks_produccion;
CREATE TABLE silver.quickbooks_produccion (
    id SERIAL PRIMARY KEY,
    idsales VARCHAR(50), idsale VARCHAR(50), numero_orden VARCHAR(50),
    fecha DATE NOT NULL, fecha_creacion TIMESTAMP, estado VARCHAR(50),
    cliente VARCHAR(255), idcliente VARCHAR(50), status_orden VARCHAR(50),
    items_planificados INTEGER DEFAULT 0, items_procesados INTEGER DEFAULT 0,
    items_pendientes INTEGER DEFAULT 0, num_lineas INTEGER DEFAULT 0,
    qty_total_planificada NUMERIC(15,2) DEFAULT 0,
    qty_total_despachada NUMERIC(15,2) DEFAULT 0,
    qty_pendiente NUMERIC(15,2) DEFAULT 0,
    desviacion_absoluta NUMERIC(15,2) DEFAULT 0,
    desviacion_porcentual NUMERIC(8,4) DEFAULT 0,
    tasa_cumplimiento NUMERIC(8,4) DEFAULT 0,
    es_dato_calidado BOOLEAN DEFAULT TRUE,
    flag_orden_atrasada BOOLEAN DEFAULT FALSE,
    fecha_carga TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pipeline_id VARCHAR(50),
    batch_id VARCHAR(50)
);

-- Silver: Catalogo de Productos
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
    fecha_carga TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pipeline_id VARCHAR(50)
);

-- Silver: Catalogo de Agencias
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
    fecha_carga TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pipeline_id VARCHAR(50)
);

-- ============================================================================
-- TABLAS GOLD
-- ============================================================================

-- Gold: KPIs de Ventas
DROP TABLE IF EXISTS gold.kpis_ventas;
CREATE TABLE gold.kpis_ventas (
    id SERIAL PRIMARY KEY,
    centro_costo VARCHAR(100) NOT NULL,
    codigo_producto VARCHAR(50),
    producto VARCHAR(255),
    mes VARCHAR(20),
    anio INTEGER,
    cant_venta NUMERIC(15,2) DEFAULT 0,
    total_venta NUMERIC(15,2) DEFAULT 0,
    cant_neto NUMERIC(15,2) DEFAULT 0,
    total_neto NUMERIC(15,2) DEFAULT 0,
    cant_devolucion NUMERIC(15,2) DEFAULT 0,
    total_devolucion NUMERIC(15,2) DEFAULT 0,
    tasa_devolucion_cant NUMERIC(8,4) DEFAULT 0,
    tasa_devolucion_valor NUMERIC(8,4) DEFAULT 0,
    nivel_devolucion VARCHAR(20),
    costo_venta NUMERIC(15,2) DEFAULT 0,
    rentabilidad NUMERIC(15,2) DEFAULT 0,
    prc_rentabilidad NUMERIC(8,4) DEFAULT 0,
    margen_bruto NUMERIC(8,4) DEFAULT 0,
    nivel_rentabilidad VARCHAR(20),
    ticket_promedio NUMERIC(15,2) DEFAULT 0,
    margen_contribucion NUMERIC(8,4) DEFAULT 0,
    fecha_calculo TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pipeline_id VARCHAR(50),
    batch_id VARCHAR(50)
);

-- Gold: KPIs de Produccion
DROP TABLE IF EXISTS gold.kpis_produccion;
CREATE TABLE gold.kpis_produccion (
    id SERIAL PRIMARY KEY,
    idsales VARCHAR(50),
    numero_orden VARCHAR(50),
    fecha DATE NOT NULL,
    fecha_creacion TIMESTAMP,
    estado VARCHAR(50),
    cliente VARCHAR(255),
    qty_total_planificada NUMERIC(15,2) DEFAULT 0,
    qty_total_despachada NUMERIC(15,2) DEFAULT 0,
    num_lineas INTEGER DEFAULT 0,
    desviacion_absoluta NUMERIC(15,2) DEFAULT 0,
    desviacion_porcentual NUMERIC(8,4) DEFAULT 0,
    tasa_cumplimiento NUMERIC(8,4) DEFAULT 0,
    clasificacion_cumplimiento VARCHAR(20),
    dia_semana INTEGER,
    dia_semana_nombre VARCHAR(20),
    mes INTEGER,
    mes_nombre VARCHAR(20),
    semana_ano INTEGER,
    es_inicio_mes BOOLEAN,
    es_fin_mes BOOLEAN,
    fecha_calculo TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pipeline_id VARCHAR(50),
    batch_id VARCHAR(50)
);

-- Gold: Anomalias de Agencias
DROP TABLE IF EXISTS gold.anomalias_agencias;
CREATE TABLE gold.anomalias_agencias (
    id SERIAL PRIMARY KEY,
    agencia VARCHAR(100) NOT NULL,
    ratio_devolucion NUMERIC(8,4),
    ratio_rentabilidad NUMERIC(8,4),
    ratio_costo NUMERIC(8,4),
    ticket_promedio NUMERIC(15,2),
    anomaly_score NUMERIC(10,6),
    es_anomalia BOOLEAN DEFAULT FALSE,
    nivel_alerta VARCHAR(20),
    zscore_devolucion NUMERIC(8,4),
    zscore_rentabilidad NUMERIC(8,4),
    zscore_costo NUMERIC(8,4),
    zscore_ticket NUMERIC(8,4),
    razon_alerta VARCHAR(255),
    modelo VARCHAR(50) DEFAULT 'IsolationForest',
    n_estimators INTEGER DEFAULT 100,
    contamination NUMERIC(4,2) DEFAULT 0.10,
    fecha_deteccion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pipeline_id VARCHAR(50)
);

-- Gold: Clusters de Productos
DROP TABLE IF EXISTS gold.clusters_productos;
CREATE TABLE gold.clusters_productos (
    id SERIAL PRIMARY KEY,
    producto VARCHAR(255) NOT NULL,
    tasa_devolucion NUMERIC(8,4),
    margen_rentabilidad NUMERIC(8,4),
    ticket_promedio NUMERIC(15,2),
    penetracion NUMERIC(8,4),
    total_ventas NUMERIC(15,2),
    cluster INTEGER,
    cluster_nombre VARCHAR(50),
    modelo VARCHAR(50) DEFAULT 'KMeans',
    n_clusters INTEGER,
    silhouette_score NUMERIC(6,4),
    fecha_clustering TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pipeline_id VARCHAR(50)
);

-- Gold: Reglas de Asociacion
DROP TABLE IF EXISTS gold.reglas_asociacion;
CREATE TABLE gold.reglas_asociacion (
    id SERIAL PRIMARY KEY,
    antecedente TEXT NOT NULL,
    consecuente TEXT NOT NULL,
    soporte NUMERIC(8,6),
    confianza NUMERIC(8,6),
    lift NUMERIC(10,4),
    tipo_regla VARCHAR(50),
    modelo VARCHAR(50) DEFAULT 'Apriori',
    min_support NUMERIC(6,4),
    min_confidence NUMERIC(6,4),
    fecha_generacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pipeline_id VARCHAR(50)
);

-- Gold: Predicciones de Devolucion
DROP TABLE IF EXISTS gold.predicciones_devolucion;
CREATE TABLE gold.predicciones_devolucion (
    id SERIAL PRIMARY KEY,
    centro_costo VARCHAR(100),
    producto VARCHAR(255),
    mes VARCHAR(20),
    tasa_devolucion_historica NUMERIC(8,4),
    margen_rentabilidad NUMERIC(8,4),
    ratio_costo NUMERIC(8,4),
    ticket_promedio NUMERIC(15,2),
    volumen NUMERIC(15,2),
    probabilidad_devolucion NUMERIC(5,4),
    prediccion_clase VARCHAR(20),
    nivel_riesgo VARCHAR(20),
    modelo VARCHAR(50) DEFAULT 'RandomForest',
    accuracy NUMERIC(5,4),
    precision_modelo NUMERIC(5,4),
    recall NUMERIC(5,4),
    f1_score NUMERIC(5,4),
    auc_roc NUMERIC(5,4),
    fecha_prediccion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pipeline_id VARCHAR(50)
);

-- Gold: Metricas de Agencias
DROP TABLE IF EXISTS gold.metricas_agencias;
CREATE TABLE gold.metricas_agencias (
    id SERIAL PRIMARY KEY,
    centro_costo VARCHAR(100) NOT NULL,
    total_venta NUMERIC(15,2) DEFAULT 0,
    total_neto NUMERIC(15,2) DEFAULT 0,
    num_ventas INTEGER DEFAULT 0,
    ticket_promedio NUMERIC(15,2) DEFAULT 0,
    total_devolucion NUMERIC(15,2) DEFAULT 0,
    tasa_devolucion NUMERIC(8,4) DEFAULT 0,
    rentabilidad_total NUMERIC(15,2) DEFAULT 0,
    rentabilidad_promedio NUMERIC(8,4) DEFAULT 0,
    margen_promedio NUMERIC(8,4) DEFAULT 0,
    costo_total NUMERIC(15,2) DEFAULT 0,
    ratio_costo NUMERIC(8,4) DEFAULT 0,
    total_nc NUMERIC(15,2) DEFAULT 0,
    tasa_nc NUMERIC(8,4) DEFAULT 0,
    fecha_calculo TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pipeline_id VARCHAR(50),
    batch_id VARCHAR(50)
);

-- Gold: Metricas de Productos
DROP TABLE IF EXISTS gold.metricas_productos;
CREATE TABLE gold.metricas_productos (
    id SERIAL PRIMARY KEY,
    producto VARCHAR(255) NOT NULL,
    categoria VARCHAR(100),
    total_venta NUMERIC(15,2) DEFAULT 0,
    cant_venta NUMERIC(15,2) DEFAULT 0,
    num_transacciones INTEGER DEFAULT 0,
    ticket_promedio NUMERIC(15,2) DEFAULT 0,
    total_devolucion NUMERIC(15,2) DEFAULT 0,
    tasa_devolucion NUMERIC(8,4) DEFAULT 0,
    rentabilidad_total NUMERIC(15,2) DEFAULT 0,
    rentabilidad_promedio NUMERIC(8,4) DEFAULT 0,
    num_agencias INTEGER DEFAULT 0,
    penetracion NUMERIC(8,4) DEFAULT 0,
    fecha_calculo TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pipeline_id VARCHAR(50),
    batch_id VARCHAR(50)
);

-- ============================================================================
-- TABLAS LOGS
-- ============================================================================

-- Logs: Ejecuciones de Pipelines
DROP TABLE IF EXISTS logs.pipeline_ejecuciones;
CREATE TABLE logs.pipeline_ejecuciones (
    id SERIAL PRIMARY KEY,
    pipeline_id VARCHAR(50) NOT NULL,
    nombre_pipeline VARCHAR(100) NOT NULL,
    run_id VARCHAR(50),
    estado VARCHAR(20) NOT NULL,
    mensaje_error TEXT,
    fecha_inicio TIMESTAMP NOT NULL,
    fecha_fin TIMESTAMP,
    duracion_segundos INTEGER,
    registros_leidos INTEGER DEFAULT 0,
    registros_escritos INTEGER DEFAULT 0,
    registros_error INTEGER DEFAULT 0,
    parametros JSONB,
    metadata JSONB
);

-- Logs: Calidad de Datos
DROP TABLE IF EXISTS logs.calidad_datos;
CREATE TABLE logs.calidad_datos (
    id SERIAL PRIMARY KEY,
    tabla VARCHAR(100) NOT NULL,
    columna VARCHAR(100),
    tipo_check VARCHAR(50) NOT NULL,
    total_registros INTEGER,
    registros_validos INTEGER,
    registros_invalidos INTEGER,
    porcentaje_calidad NUMERIC(5,2),
    detalle_error TEXT,
    fecha_check TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pipeline_id VARCHAR(50)
);

-- ============================================================================
-- INDICES
-- ============================================================================

CREATE INDEX idx_silver_kronos_cc ON silver.kronos_ventas(centro_costo);
CREATE INDEX idx_silver_kronos_prod ON silver.kronos_ventas(producto);
CREATE INDEX idx_silver_kronos_mes ON silver.kronos_ventas(mes);
CREATE INDEX idx_silver_prod_fecha ON silver.quickbooks_produccion(fecha);
CREATE INDEX idx_gold_kpis_ventas_cc ON gold.kpis_ventas(centro_costo);
CREATE INDEX idx_gold_kpis_prod_fecha ON gold.kpis_produccion(fecha);
CREATE INDEX idx_gold_anomalias_agencia ON gold.anomalias_agencias(agencia);
CREATE INDEX idx_gold_clusters_prod ON gold.clusters_productos(producto);
CREATE INDEX idx_gold_reglas_lift ON gold.reglas_asociacion(lift DESC);
CREATE INDEX idx_logs_pipeline_id ON logs.pipeline_ejecuciones(pipeline_id);
CREATE INDEX idx_logs_fecha ON logs.pipeline_ejecuciones(fecha_inicio);

-- ============================================================================
-- VERIFICACION
-- ============================================================================

SELECT 'Esquemas y tablas creados exitosamente' as resultado;
