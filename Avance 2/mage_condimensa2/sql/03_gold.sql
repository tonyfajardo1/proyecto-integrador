-- ============================================================================
-- CONDIMENSA - DATA WAREHOUSE
-- Capa GOLD: Datos analiticos, KPIs y resultados de Data Mining
-- ============================================================================

-- ============================================================================
-- GOLD: KPIs de Ventas Comerciales
-- ============================================================================
DROP TABLE IF EXISTS gold.kpis_ventas;
CREATE TABLE gold.kpis_ventas (
    id SERIAL PRIMARY KEY,
    
    -- Dimensiones
    centro_costo VARCHAR(100) NOT NULL,
    codigo_producto VARCHAR(50),
    producto VARCHAR(255),
    mes VARCHAR(20),
    anio INTEGER,
    
    -- KPIs de Venta
    cant_venta NUMERIC(15,2) DEFAULT 0,
    total_venta NUMERIC(15,2) DEFAULT 0,
    cant_neto NUMERIC(15,2) DEFAULT 0,
    total_neto NUMERIC(15,2) DEFAULT 0,
    
    -- KPIs de Devoluciones
    cant_devolucion NUMERIC(15,2) DEFAULT 0,
    total_devolucion NUMERIC(15,2) DEFAULT 0,
    tasa_devolucion_cant NUMERIC(8,4) DEFAULT 0,
    tasa_devolucion_valor NUMERIC(8,4) DEFAULT 0,
    nivel_devolucion VARCHAR(20),
    
    -- KPIs de Rentabilidad
    costo_venta NUMERIC(15,2) DEFAULT 0,
    rentabilidad NUMERIC(15,2) DEFAULT 0,
    prc_rentabilidad NUMERIC(8,4) DEFAULT 0,
    margen_bruto NUMERIC(8,4) DEFAULT 0,
    nivel_rentabilidad VARCHAR(20),
    
    -- KPIs Adicionales
    ticket_promedio NUMERIC(15,2) DEFAULT 0,
    margen_contribucion NUMERIC(8,4) DEFAULT 0,
    
    -- Metadatos
    fecha_calculo TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pipeline_id VARCHAR(50),
    batch_id VARCHAR(50)
);

CREATE INDEX idx_gold_kpis_ventas_cc ON gold.kpis_ventas(centro_costo);
CREATE INDEX idx_gold_kpis_ventas_prod ON gold.kpis_ventas(producto);
CREATE INDEX idx_gold_kpis_ventas_mes ON gold.kpis_ventas(mes);

COMMENT ON TABLE gold.kpis_ventas IS 'KPIs de ventas comerciales calculados';

-- ============================================================================
-- GOLD: KPIs de Produccion (Plan vs Real)
-- ============================================================================
DROP TABLE IF EXISTS gold.kpis_produccion;
CREATE TABLE gold.kpis_produccion (
    id SERIAL PRIMARY KEY,
    
    -- Identificadores
    idsales VARCHAR(50),
    numero_orden VARCHAR(50),
    
    -- Dimensiones
    fecha DATE NOT NULL,
    fecha_creacion TIMESTAMP,
    estado VARCHAR(50),
    cliente VARCHAR(255),
    
    -- KPIs de Cantidad
    qty_total_planificada NUMERIC(15,2) DEFAULT 0,
    qty_total_despachada NUMERIC(15,2) DEFAULT 0,
    num_lineas INTEGER DEFAULT 0,
    
    -- KPIs de Desviacion
    desviacion_absoluta NUMERIC(15,2) DEFAULT 0,
    desviacion_porcentual NUMERIC(8,4) DEFAULT 0,
    tasa_cumplimiento NUMERIC(8,4) DEFAULT 0,
    clasificacion_cumplimiento VARCHAR(20),
    
    -- Dimensiones temporales
    dia_semana INTEGER,
    dia_semana_nombre VARCHAR(20),
    mes INTEGER,
    mes_nombre VARCHAR(20),
    semana_ano INTEGER,
    es_inicio_mes BOOLEAN,
    es_fin_mes BOOLEAN,
    
    -- Metadatos
    fecha_calculo TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pipeline_id VARCHAR(50),
    batch_id VARCHAR(50)
);

CREATE INDEX idx_gold_kpis_prod_fecha ON gold.kpis_produccion(fecha);
CREATE INDEX idx_gold_kpis_prod_clasif ON gold.kpis_produccion(clasificacion_cumplimiento);

COMMENT ON TABLE gold.kpis_produccion IS 'KPIs de produccion - Desviaciones Plan vs Real';

-- ============================================================================
-- GOLD: Metricas por Agencia (para anomalias y clustering)
-- ============================================================================
DROP TABLE IF EXISTS gold.metricas_agencias;
CREATE TABLE gold.metricas_agencias (
    id SERIAL PRIMARY KEY,
    
    -- Dimension
    centro_costo VARCHAR(100) NOT NULL,
    
    -- Metricas de venta
    total_venta NUMERIC(15,2) DEFAULT 0,
    total_neto NUMERIC(15,2) DEFAULT 0,
    num_ventas INTEGER DEFAULT 0,
    ticket_promedio NUMERIC(15,2) DEFAULT 0,
    
    -- Metricas de devolucion
    total_devolucion NUMERIC(15,2) DEFAULT 0,
    tasa_devolucion NUMERIC(8,4) DEFAULT 0,
    
    -- Metricas de rentabilidad
    rentabilidad_total NUMERIC(15,2) DEFAULT 0,
    rentabilidad_promedio NUMERIC(8,4) DEFAULT 0,
    margen_promedio NUMERIC(8,4) DEFAULT 0,
    
    -- Metricas de costo
    costo_total NUMERIC(15,2) DEFAULT 0,
    ratio_costo NUMERIC(8,4) DEFAULT 0,
    
    -- Metricas de notas de credito
    total_nc NUMERIC(15,2) DEFAULT 0,
    tasa_nc NUMERIC(8,4) DEFAULT 0,
    
    -- Metadatos
    fecha_calculo TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pipeline_id VARCHAR(50),
    batch_id VARCHAR(50)
);

CREATE INDEX idx_gold_met_agencias_cc ON gold.metricas_agencias(centro_costo);

COMMENT ON TABLE gold.metricas_agencias IS 'Metricas consolidadas por agencia para Data Mining';

-- ============================================================================
-- GOLD: Metricas por Producto (para clustering)
-- ============================================================================
DROP TABLE IF EXISTS gold.metricas_productos;
CREATE TABLE gold.metricas_productos (
    id SERIAL PRIMARY KEY,
    
    -- Dimension
    producto VARCHAR(255) NOT NULL,
    categoria VARCHAR(100),
    
    -- Metricas de venta
    total_venta NUMERIC(15,2) DEFAULT 0,
    cant_venta NUMERIC(15,2) DEFAULT 0,
    num_transacciones INTEGER DEFAULT 0,
    ticket_promedio NUMERIC(15,2) DEFAULT 0,
    
    -- Metricas de devolucion
    total_devolucion NUMERIC(15,2) DEFAULT 0,
    tasa_devolucion NUMERIC(8,4) DEFAULT 0,
    
    -- Metricas de rentabilidad
    rentabilidad_total NUMERIC(15,2) DEFAULT 0,
    rentabilidad_promedio NUMERIC(8,4) DEFAULT 0,
    
    -- Metricas de penetracion
    num_agencias INTEGER DEFAULT 0,
    penetracion NUMERIC(8,4) DEFAULT 0,
    
    -- Metadatos
    fecha_calculo TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pipeline_id VARCHAR(50),
    batch_id VARCHAR(50)
);

CREATE INDEX idx_gold_met_prod_prod ON gold.metricas_productos(producto);
CREATE INDEX idx_gold_met_prod_cat ON gold.metricas_productos(categoria);

COMMENT ON TABLE gold.metricas_productos IS 'Metricas consolidadas por producto para Data Mining';

-- ============================================================================
-- GOLD: Resultados - Anomalias Detectadas (Isolation Forest)
-- ============================================================================
DROP TABLE IF EXISTS gold.anomalias_agencias;
CREATE TABLE gold.anomalias_agencias (
    id SERIAL PRIMARY KEY,
    
    -- Dimension
    agencia VARCHAR(100) NOT NULL,
    
    -- Metricas originales
    ratio_devolucion NUMERIC(8,4),
    ratio_rentabilidad NUMERIC(8,4),
    ratio_costo NUMERIC(8,4),
    ticket_promedio NUMERIC(15,2),
    
    -- Resultados del modelo
    anomaly_score NUMERIC(10,6),
    es_anomalia BOOLEAN DEFAULT FALSE,
    nivel_alerta VARCHAR(20),
    
    -- Z-Scores para interpretabilidad
    zscore_devolucion NUMERIC(8,4),
    zscore_rentabilidad NUMERIC(8,4),
    zscore_costo NUMERIC(8,4),
    zscore_ticket NUMERIC(8,4),
    
    -- Clasificacion
    razon_alerta VARCHAR(255),
    
    -- Metadatos del modelo
    modelo VARCHAR(50) DEFAULT 'IsolationForest',
    n_estimators INTEGER DEFAULT 100,
    contamination NUMERIC(4,2) DEFAULT 0.10,
    fecha_deteccion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pipeline_id VARCHAR(50)
);

CREATE INDEX idx_gold_anomalias_agencia ON gold.anomalias_agencias(agencia);
CREATE INDEX idx_gold_anomalias_flag ON gold.anomalias_agencias(es_anomalia);
CREATE INDEX idx_gold_anomalias_nivel ON gold.anomalias_agencias(nivel_alerta);

COMMENT ON TABLE gold.anomalias_agencias IS 'Anomalias detectadas en agencias via Isolation Forest';

-- ============================================================================
-- GOLD: Resultados - Clusters de Productos (K-Means)
-- ============================================================================
DROP TABLE IF EXISTS gold.clusters_productos;
CREATE TABLE gold.clusters_productos (
    id SERIAL PRIMARY KEY,
    
    -- Dimension
    producto VARCHAR(255) NOT NULL,
    
    -- Metricas usadas
    tasa_devolucion NUMERIC(8,4),
    margen_rentabilidad NUMERIC(8,4),
    ticket_promedio NUMERIC(15,2),
    penetracion NUMERIC(8,4),
    total_ventas NUMERIC(15,2),
    
    -- Resultados del clustering
    cluster INTEGER,
    cluster_nombre VARCHAR(50),
    
    -- Metadatos del modelo
    modelo VARCHAR(50) DEFAULT 'KMeans',
    n_clusters INTEGER,
    silhouette_score NUMERIC(6,4),
    fecha_clustering TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pipeline_id VARCHAR(50)
);

CREATE INDEX idx_gold_clusters_prod ON gold.clusters_productos(producto);
CREATE INDEX idx_gold_clusters_id ON gold.clusters_productos(cluster);
CREATE INDEX idx_gold_clusters_nom ON gold.clusters_productos(cluster_nombre);

COMMENT ON TABLE gold.clusters_productos IS 'Segmentacion de productos via K-Means';

-- ============================================================================
-- GOLD: Resultados - Reglas de Asociacion (Apriori)
-- ============================================================================
DROP TABLE IF EXISTS gold.reglas_asociacion;
CREATE TABLE gold.reglas_asociacion (
    id SERIAL PRIMARY KEY,
    
    -- Regla
    antecedente TEXT NOT NULL,
    consecuente TEXT NOT NULL,
    
    -- Metricas de la regla
    soporte NUMERIC(8,6),
    confianza NUMERIC(8,6),
    lift NUMERIC(10,4),
    
    -- Clasificacion
    tipo_regla VARCHAR(50),
    
    -- Metadatos del modelo
    modelo VARCHAR(50) DEFAULT 'Apriori',
    min_support NUMERIC(6,4),
    min_confidence NUMERIC(6,4),
    fecha_generacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pipeline_id VARCHAR(50)
);

CREATE INDEX idx_gold_reglas_lift ON gold.reglas_asociacion(lift DESC);
CREATE INDEX idx_gold_reglas_conf ON gold.reglas_asociacion(confianza DESC);
CREATE INDEX idx_gold_reglas_tipo ON gold.reglas_asociacion(tipo_regla);

COMMENT ON TABLE gold.reglas_asociacion IS 'Reglas de asociacion descubiertas via Apriori';

-- ============================================================================
-- GOLD: Resultados - Predicciones de Devolucion
-- ============================================================================
DROP TABLE IF EXISTS gold.predicciones_devolucion;
CREATE TABLE gold.predicciones_devolucion (
    id SERIAL PRIMARY KEY,
    
    -- Dimension
    centro_costo VARCHAR(100),
    producto VARCHAR(255),
    mes VARCHAR(20),
    
    -- Features
    tasa_devolucion_historica NUMERIC(8,4),
    margen_rentabilidad NUMERIC(8,4),
    ratio_costo NUMERIC(8,4),
    ticket_promedio NUMERIC(15,2),
    volumen NUMERIC(15,2),
    
    -- Prediccion
    probabilidad_devolucion NUMERIC(5,4),
    prediccion_clase VARCHAR(20),
    nivel_riesgo VARCHAR(20),
    
    -- Metadatos del modelo
    modelo VARCHAR(50) DEFAULT 'RandomForest',
    accuracy NUMERIC(5,4),
    precision_modelo NUMERIC(5,4),
    recall NUMERIC(5,4),
    f1_score NUMERIC(5,4),
    auc_roc NUMERIC(5,4),
    fecha_prediccion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pipeline_id VARCHAR(50)
);

CREATE INDEX idx_gold_pred_cc ON gold.predicciones_devolucion(centro_costo);
CREATE INDEX idx_gold_pred_riesgo ON gold.predicciones_devolucion(nivel_riesgo);

COMMENT ON TABLE gold.predicciones_devolucion IS 'Predicciones de probabilidad de devolucion';

-- ============================================================================
-- LOGS: Tabla de ejecucion de pipelines
-- ============================================================================
DROP TABLE IF EXISTS logs.pipeline_ejecuciones;
CREATE TABLE logs.pipeline_ejecuciones (
    id SERIAL PRIMARY KEY,
    
    -- Identificacion
    pipeline_id VARCHAR(50) NOT NULL,
    nombre_pipeline VARCHAR(100) NOT NULL,
    run_id VARCHAR(50),
    
    -- Estado
    estado VARCHAR(20) NOT NULL,  -- STARTED, RUNNING, SUCCESS, FAILED
    mensaje_error TEXT,
    
    -- Tiempos
    fecha_inicio TIMESTAMP NOT NULL,
    fecha_fin TIMESTAMP,
    duracion_segundos INTEGER,
    
    -- Metricas
    registros_leidos INTEGER DEFAULT 0,
    registros_escritos INTEGER DEFAULT 0,
    registros_error INTEGER DEFAULT 0,
    
    -- Metadatos adicionales
    parametros JSONB,
    metadata JSONB
);

CREATE INDEX idx_logs_pipeline_id ON logs.pipeline_ejecuciones(pipeline_id);
CREATE INDEX idx_logs_estado ON logs.pipeline_ejecuciones(estado);
CREATE INDEX idx_logs_fecha ON logs.pipeline_ejecuciones(fecha_inicio);

COMMENT ON TABLE logs.pipeline_ejecuciones IS 'Log de ejecucion de pipelines para trazabilidad';

-- ============================================================================
-- LOGS: Tabla de calidad de datos
-- ============================================================================
DROP TABLE IF EXISTS logs.calidad_datos;
CREATE TABLE logs.calidad_datos (
    id SERIAL PRIMARY KEY,
    
    -- Identificacion
    tabla VARCHAR(100) NOT NULL,
    columna VARCHAR(100),
    
    -- Metrica de calidad
    tipo_check VARCHAR(50) NOT NULL,  -- NULL_CHECK, UNIQUE_CHECK, RANGE_CHECK, etc.
    total_registros INTEGER,
    registros_validos INTEGER,
    registros_invalidos INTEGER,
    porcentaje_calidad NUMERIC(5,2),
    
    -- Detalle
    detalle_error TEXT,
    
    -- Metadatos
    fecha_check TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pipeline_id VARCHAR(50)
);

CREATE INDEX idx_logs_calidad_tabla ON logs.calidad_datos(tabla);
CREATE INDEX idx_logs_calidad_fecha ON logs.calidad_datos(fecha_check);

COMMENT ON TABLE logs.calidad_datos IS 'Log de verificaciones de calidad de datos';
