-- =============================================================================
-- SCRIPT SQL PARA GENERAR DATOS REALISTAS - CONDIMENSA
-- Productos reales de Kronos, devoluciones solo por CADUCADO en pocos productos
-- =============================================================================

-- Limpiar tablas existentes
DROP TABLE IF EXISTS dm.cestas_transacciones CASCADE;
DROP TABLE IF EXISTS gold.reglas_asociacion CASCADE;
DROP TABLE IF EXISTS gold.anomalias_agencias CASCADE;
DROP TABLE IF EXISTS gold.predicciones_devolucion CASCADE;

-- Recrear silver.kronos_ventas_silver con datos realistas
DROP TABLE IF EXISTS silver.kronos_ventas_silver CASCADE;
CREATE TABLE silver.kronos_ventas_silver (
    id SERIAL PRIMARY KEY,
    centro_costo VARCHAR(50),
    codigo_producto VARCHAR(20),
    codigo_alterno VARCHAR(20),
    producto VARCHAR(100),
    mes VARCHAR(20),
    anio VARCHAR(10),
    cant_venta NUMERIC(12,2),
    total_venta NUMERIC(15,2),
    cant_nc NUMERIC(12,2) DEFAULT 0,
    total_nc NUMERIC(15,2) DEFAULT 0,
    cant_devolucion NUMERIC(12,2),
    total_devolucion NUMERIC(15,2),
    cant_neto NUMERIC(12,2),
    total_neto NUMERIC(15,2),
    costo_venta NUMERIC(15,2),
    rentabilidad NUMERIC(15,2),
    prc_rentabilidad NUMERIC(8,2),
    categoria VARCHAR(50),
    dias_vida_util INTEGER,
    motivo_devolucion VARCHAR(50),
    es_dato_calidado BOOLEAN DEFAULT TRUE,
    fecha_carga TIMESTAMP DEFAULT NOW()
);

-- Insertar datos de ventas con productos reales de Kronos
-- Productos con devoluciones por CADUCADO: AJO PASTA y MAYONESA (vida util corta)
INSERT INTO silver.kronos_ventas_silver
(centro_costo, codigo_producto, producto, mes, anio, cant_venta, total_venta, cant_devolucion, total_devolucion, cant_neto, total_neto, costo_venta, rentabilidad, prc_rentabilidad, categoria, dias_vida_util, motivo_devolucion)
VALUES
-- QUITO (agencia con ALTA RENTABILIDAD - anomalia positiva)
('quito', '6986', 'CALDO DE GALLINA 48 GR', 'ENERO', '2026', 150, 127.50, 2, 1.70, 148, 125.80, 75.48, 50.32, 40.0, 'CALDOS', 365, NULL),
('quito', '7328', 'SAZONADOR POLLO FCO 70G', 'ENERO', '2026', 120, 216.00, 1, 1.80, 119, 214.20, 128.52, 85.68, 40.0, 'SAZONADORES', 180, NULL),
('quito', '0398', 'COMINO MOLIDO FDA 200 GRS', 'ENERO', '2026', 80, 360.00, 0, 0.00, 80, 360.00, 216.00, 144.00, 40.0, 'ESPECIAS', 365, NULL),
('quito', '4716', 'AJO PAST DOYPACK VALV 200', 'ENERO', '2026', 100, 250.00, 15, 37.50, 85, 212.50, 127.50, 85.00, 40.0, 'AJOS', 90, 'CADUCADO'),
('quito', '8608', 'ALINO BOT 310 GRS', 'ENERO', '2026', 90, 342.00, 2, 7.60, 88, 334.40, 200.64, 133.76, 40.0, 'ALINOS', 120, NULL),
('quito', '6191', 'MAYONESA DISPLAY X 12', 'ENERO', '2026', 60, 510.00, 12, 102.00, 48, 408.00, 244.80, 163.20, 40.0, 'SALSAS', 90, 'CADUCADO'),
('quito', '2445', 'ACEITE DE OLIVA BOT PET 200ML', 'ENERO', '2026', 40, 232.00, 0, 0.00, 40, 232.00, 139.20, 92.80, 40.0, 'ACEITES', 365, NULL),
('quito', '9858', 'OREGANO FCO LINEAL 20G', 'ENERO', '2026', 100, 150.00, 1, 1.50, 99, 148.50, 89.10, 59.40, 40.0, 'ESPECIAS', 365, NULL),

-- GUAYAQUIL (normal)
('guayaquil', '6986', 'CALDO DE GALLINA 48 GR', 'ENERO', '2026', 180, 153.00, 3, 2.55, 177, 150.45, 105.32, 45.14, 30.0, 'CALDOS', 365, NULL),
('guayaquil', '7328', 'SAZONADOR POLLO FCO 70G', 'ENERO', '2026', 140, 252.00, 2, 3.60, 138, 248.40, 173.88, 74.52, 30.0, 'SAZONADORES', 180, NULL),
('guayaquil', '0398', 'COMINO MOLIDO FDA 200 GRS', 'ENERO', '2026', 100, 450.00, 1, 4.50, 99, 445.50, 311.85, 133.65, 30.0, 'ESPECIAS', 365, NULL),
('guayaquil', '4716', 'AJO PAST DOYPACK VALV 200', 'ENERO', '2026', 120, 300.00, 18, 45.00, 102, 255.00, 178.50, 76.50, 30.0, 'AJOS', 90, 'CADUCADO'),
('guayaquil', '8608', 'ALINO BOT 310 GRS', 'ENERO', '2026', 110, 418.00, 3, 11.40, 107, 406.60, 284.62, 121.98, 30.0, 'ALINOS', 120, NULL),
('guayaquil', '6191', 'MAYONESA DISPLAY X 12', 'ENERO', '2026', 80, 680.00, 16, 136.00, 64, 544.00, 380.80, 163.20, 30.0, 'SALSAS', 90, 'CADUCADO'),
('guayaquil', '1127', 'PAPRIKA FCO 40G', 'ENERO', '2026', 60, 108.00, 0, 0.00, 60, 108.00, 75.60, 32.40, 30.0, 'ESPECIAS', 365, NULL),

-- CUENCA (normal)
('cuenca', '6986', 'CALDO DE GALLINA 48 GR', 'ENERO', '2026', 80, 68.00, 1, 0.85, 79, 67.15, 47.01, 20.15, 30.0, 'CALDOS', 365, NULL),
('cuenca', '7328', 'SAZONADOR POLLO FCO 70G', 'ENERO', '2026', 70, 126.00, 1, 1.80, 69, 124.20, 86.94, 37.26, 30.0, 'SAZONADORES', 180, NULL),
('cuenca', '0398', 'COMINO MOLIDO FDA 200 GRS', 'ENERO', '2026', 50, 225.00, 0, 0.00, 50, 225.00, 157.50, 67.50, 30.0, 'ESPECIAS', 365, NULL),
('cuenca', '4716', 'AJO PAST DOYPACK VALV 200', 'ENERO', '2026', 60, 150.00, 9, 22.50, 51, 127.50, 89.25, 38.25, 30.0, 'AJOS', 90, 'CADUCADO'),
('cuenca', '6191', 'MAYONESA DISPLAY X 12', 'ENERO', '2026', 40, 340.00, 8, 68.00, 32, 272.00, 190.40, 81.60, 30.0, 'SALSAS', 90, 'CADUCADO'),

-- PORTOVIEJO (agencia con ALTA DEVOLUCION - anomalia negativa)
('portoviejo', '6986', 'CALDO DE GALLINA 48 GR', 'ENERO', '2026', 70, 59.50, 2, 1.70, 68, 57.80, 43.35, 14.45, 25.0, 'CALDOS', 365, NULL),
('portoviejo', '7328', 'SAZONADOR POLLO FCO 70G', 'ENERO', '2026', 60, 108.00, 2, 3.60, 58, 104.40, 78.30, 26.10, 25.0, 'SAZONADORES', 180, NULL),
('portoviejo', '4716', 'AJO PAST DOYPACK VALV 200', 'ENERO', '2026', 80, 200.00, 20, 50.00, 60, 150.00, 112.50, 37.50, 25.0, 'AJOS', 90, 'CADUCADO'),
('portoviejo', '6191', 'MAYONESA DISPLAY X 12', 'ENERO', '2026', 50, 425.00, 15, 127.50, 35, 297.50, 223.13, 74.38, 25.0, 'SALSAS', 90, 'CADUCADO'),
('portoviejo', '8608', 'ALINO BOT 310 GRS', 'ENERO', '2026', 40, 152.00, 5, 19.00, 35, 133.00, 99.75, 33.25, 25.0, 'ALINOS', 120, NULL),

-- AMBATO (normal)
('ambato', '6986', 'CALDO DE GALLINA 48 GR', 'ENERO', '2026', 60, 51.00, 1, 0.85, 59, 50.15, 35.11, 15.05, 30.0, 'CALDOS', 365, NULL),
('ambato', '0398', 'COMINO MOLIDO FDA 200 GRS', 'ENERO', '2026', 40, 180.00, 0, 0.00, 40, 180.00, 126.00, 54.00, 30.0, 'ESPECIAS', 365, NULL),
('ambato', '4716', 'AJO PAST DOYPACK VALV 200', 'ENERO', '2026', 50, 125.00, 7, 17.50, 43, 107.50, 75.25, 32.25, 30.0, 'AJOS', 90, 'CADUCADO'),
('ambato', '9858', 'OREGANO FCO LINEAL 20G', 'ENERO', '2026', 50, 75.00, 0, 0.00, 50, 75.00, 52.50, 22.50, 30.0, 'ESPECIAS', 365, NULL),

-- LOJA (pequena, normal)
('loja', '6986', 'CALDO DE GALLINA 48 GR', 'ENERO', '2026', 30, 25.50, 0, 0.00, 30, 25.50, 17.85, 7.65, 30.0, 'CALDOS', 365, NULL),
('loja', '7328', 'SAZONADOR POLLO FCO 70G', 'ENERO', '2026', 25, 45.00, 0, 0.00, 25, 45.00, 31.50, 13.50, 30.0, 'SAZONADORES', 180, NULL),
('loja', '4716', 'AJO PAST DOYPACK VALV 200', 'ENERO', '2026', 20, 50.00, 3, 7.50, 17, 42.50, 29.75, 12.75, 30.0, 'AJOS', 90, 'CADUCADO'),

-- IBARRA (pequena, normal)
('ibarra', '6986', 'CALDO DE GALLINA 48 GR', 'ENERO', '2026', 35, 29.75, 0, 0.00, 35, 29.75, 20.83, 8.93, 30.0, 'CALDOS', 365, NULL),
('ibarra', '0657', 'COMINO MOLIDO FDA 100 GRS', 'ENERO', '2026', 30, 75.00, 0, 0.00, 30, 75.00, 52.50, 22.50, 30.0, 'ESPECIAS', 365, NULL),
('ibarra', '6191', 'MAYONESA DISPLAY X 12', 'ENERO', '2026', 15, 127.50, 3, 25.50, 12, 102.00, 71.40, 30.60, 30.0, 'SALSAS', 90, 'CADUCADO'),

-- SANTO DOMINGO (mediana, normal)
('santo_domingo', '6986', 'CALDO DE GALLINA 48 GR', 'ENERO', '2026', 70, 59.50, 1, 0.85, 69, 58.65, 41.06, 17.60, 30.0, 'CALDOS', 365, NULL),
('santo_domingo', '7328', 'SAZONADOR POLLO FCO 70G', 'ENERO', '2026', 60, 108.00, 1, 1.80, 59, 106.20, 74.34, 31.86, 30.0, 'SAZONADORES', 180, NULL),
('santo_domingo', '4716', 'AJO PAST DOYPACK VALV 200', 'ENERO', '2026', 55, 137.50, 8, 20.00, 47, 117.50, 82.25, 35.25, 30.0, 'AJOS', 90, 'CADUCADO'),

-- RIOBAMBA (pequena, normal)
('riobamba', '6986', 'CALDO DE GALLINA 48 GR', 'ENERO', '2026', 25, 21.25, 0, 0.00, 25, 21.25, 14.88, 6.38, 30.0, 'CALDOS', 365, NULL),
('riobamba', '9858', 'OREGANO FCO LINEAL 20G', 'ENERO', '2026', 30, 45.00, 0, 0.00, 30, 45.00, 31.50, 13.50, 30.0, 'ESPECIAS', 365, NULL),

-- PUYO (pequena, normal)
('puyo', '6986', 'CALDO DE GALLINA 48 GR', 'ENERO', '2026', 20, 17.00, 0, 0.00, 20, 17.00, 11.90, 5.10, 30.0, 'CALDOS', 365, NULL),
('puyo', '7328', 'SAZONADOR POLLO FCO 70G', 'ENERO', '2026', 15, 27.00, 0, 0.00, 15, 27.00, 18.90, 8.10, 30.0, 'SAZONADORES', 180, NULL);

-- =============================================================================
-- CREAR TABLA DE CESTAS PARA APRIORI (CROSS-SELLING)
-- =============================================================================
CREATE SCHEMA IF NOT EXISTS dm;
CREATE TABLE dm.cestas_transacciones (
    id SERIAL PRIMARY KEY,
    transaccion_id VARCHAR(20),
    fecha DATE,
    agencia VARCHAR(50),
    codigo_producto VARCHAR(20),
    producto VARCHAR(100),
    categoria VARCHAR(50),
    cantidad INTEGER,
    precio_unitario NUMERIC(10,2),
    total NUMERIC(12,2)
);

-- Insertar transacciones con patrones de cross-selling
-- Patron 1: Sazonadores juntos (SAZONADOR POLLO + CALDO GALLINA)
INSERT INTO dm.cestas_transacciones (transaccion_id, fecha, agencia, codigo_producto, producto, categoria, cantidad, precio_unitario, total)
SELECT
    'TRX' || LPAD(ROW_NUMBER() OVER()::text, 6, '0'),
    '2026-01-' || LPAD((1 + (ROW_NUMBER() OVER() % 30))::text, 2, '0'),
    (ARRAY['quito','guayaquil','cuenca','ambato'])[1 + (ROW_NUMBER() OVER() % 4)],
    '7328', 'SAZONADOR POLLO FCO 70G', 'SAZONADORES', 2, 1.80, 3.60
FROM generate_series(1, 300);

INSERT INTO dm.cestas_transacciones (transaccion_id, fecha, agencia, codigo_producto, producto, categoria, cantidad, precio_unitario, total)
SELECT
    'TRX' || LPAD(s::text, 6, '0'),
    '2026-01-' || LPAD((1 + (s % 30))::text, 2, '0'),
    (ARRAY['quito','guayaquil','cuenca','ambato'])[1 + (s % 4)],
    '6986', 'CALDO DE GALLINA 48 GR', 'CALDOS', 3, 0.85, 2.55
FROM generate_series(1, 250) s;

-- Patron 2: Especias juntas (COMINO + OREGANO)
INSERT INTO dm.cestas_transacciones (transaccion_id, fecha, agencia, codigo_producto, producto, categoria, cantidad, precio_unitario, total)
SELECT
    'TRX' || LPAD((300 + ROW_NUMBER() OVER())::text, 6, '0'),
    '2026-01-' || LPAD((1 + (ROW_NUMBER() OVER() % 30))::text, 2, '0'),
    (ARRAY['quito','guayaquil','cuenca'])[1 + (ROW_NUMBER() OVER() % 3)],
    '0398', 'COMINO MOLIDO FDA 200 GRS', 'ESPECIAS', 1, 4.50, 4.50
FROM generate_series(1, 200);

INSERT INTO dm.cestas_transacciones (transaccion_id, fecha, agencia, codigo_producto, producto, categoria, cantidad, precio_unitario, total)
SELECT
    'TRX' || LPAD((300 + s)::text, 6, '0'),
    '2026-01-' || LPAD((1 + (s % 30))::text, 2, '0'),
    (ARRAY['quito','guayaquil','cuenca'])[1 + (s % 3)],
    '9858', 'OREGANO FCO LINEAL 20G', 'ESPECIAS', 2, 1.50, 3.00
FROM generate_series(1, 180) s;

-- Patron 3: Ajo + Alino (AJO PASTA + ALINO)
INSERT INTO dm.cestas_transacciones (transaccion_id, fecha, agencia, codigo_producto, producto, categoria, cantidad, precio_unitario, total)
SELECT
    'TRX' || LPAD((500 + ROW_NUMBER() OVER())::text, 6, '0'),
    '2026-01-' || LPAD((1 + (ROW_NUMBER() OVER() % 30))::text, 2, '0'),
    (ARRAY['quito','guayaquil','portoviejo','santo_domingo'])[1 + (ROW_NUMBER() OVER() % 4)],
    '4716', 'AJO PAST DOYPACK VALV 200', 'AJOS', 1, 2.50, 2.50
FROM generate_series(1, 220);

INSERT INTO dm.cestas_transacciones (transaccion_id, fecha, agencia, codigo_producto, producto, categoria, cantidad, precio_unitario, total)
SELECT
    'TRX' || LPAD((500 + s)::text, 6, '0'),
    '2026-01-' || LPAD((1 + (s % 30))::text, 2, '0'),
    (ARRAY['quito','guayaquil','portoviejo','santo_domingo'])[1 + (s % 4)],
    '8608', 'ALINO BOT 310 GRS', 'ALINOS', 1, 3.80, 3.80
FROM generate_series(1, 200) s;

-- Patron 4: Salsas (MAYONESA + algun otro producto aleatorio)
INSERT INTO dm.cestas_transacciones (transaccion_id, fecha, agencia, codigo_producto, producto, categoria, cantidad, precio_unitario, total)
SELECT
    'TRX' || LPAD((720 + ROW_NUMBER() OVER())::text, 6, '0'),
    '2026-01-' || LPAD((1 + (ROW_NUMBER() OVER() % 30))::text, 2, '0'),
    (ARRAY['quito','guayaquil','cuenca','ibarra'])[1 + (ROW_NUMBER() OVER() % 4)],
    '6191', 'MAYONESA DISPLAY X 12', 'SALSAS', 1, 8.50, 8.50
FROM generate_series(1, 150);

-- =============================================================================
-- CREAR TABLAS GOLD
-- =============================================================================
CREATE SCHEMA IF NOT EXISTS gold;

-- Metricas por Agencia (para Isolation Forest)
DROP TABLE IF EXISTS gold.metricas_agencias CASCADE;
CREATE TABLE gold.metricas_agencias AS
SELECT
    centro_costo,
    CASE
        WHEN centro_costo IN ('quito', 'guayaquil') THEN 'SIERRA'
        WHEN centro_costo IN ('cuenca', 'ambato', 'loja', 'ibarra', 'riobamba') THEN 'SIERRA'
        ELSE 'COSTA'
    END as region,
    CASE
        WHEN centro_costo IN ('quito', 'guayaquil') THEN 'GRANDE'
        WHEN centro_costo IN ('cuenca', 'ambato', 'portoviejo', 'santo_domingo') THEN 'MEDIANO'
        ELSE 'PEQUENO'
    END as tamano,
    SUM(cant_venta) as cantidad_vendida,
    SUM(total_venta) as total_ventas,
    SUM(cant_devolucion) as cantidad_devuelta,
    SUM(total_devolucion) as total_devoluciones,
    SUM(total_neto) as total_neto,
    ROUND((SUM(cant_devolucion) / NULLIF(SUM(cant_venta), 0) * 100)::numeric, 2) as tasa_devolucion,
    ROUND((SUM(rentabilidad) / NULLIF(SUM(total_neto), 0) * 100)::numeric, 2) as rentabilidad_porcentual,
    ROUND((SUM(total_venta) / COUNT(DISTINCT producto))::numeric, 2) as ticket_promedio,
    COUNT(DISTINCT producto) as productos_distintos
FROM silver.kronos_ventas_silver
GROUP BY centro_costo;

-- Metricas por Producto (para Random Forest)
DROP TABLE IF EXISTS gold.metricas_productos CASCADE;
CREATE TABLE gold.metricas_productos AS
SELECT
    codigo_producto,
    producto,
    categoria,
    SUM(cant_venta) as cantidad_vendida,
    SUM(cant_devolucion) as cantidad_devuelta,
    SUM(total_venta) as total_ventas,
    SUM(total_devolucion) as total_devoluciones,
    ROUND((SUM(cant_devolucion) / NULLIF(SUM(cant_venta), 0) * 100)::numeric, 2) as tasa_devolucion,
    ROUND((SUM(rentabilidad) / NULLIF(SUM(total_neto), 0) * 100)::numeric, 2) as rentabilidad_porcentual,
    COUNT(DISTINCT centro_costo) as n_agencias_venta,
    MAX(dias_vida_util) as dias_vida_util,
    MAX(motivo_devolucion) as motivo_devolucion_principal
FROM silver.kronos_ventas_silver
GROUP BY codigo_producto, producto, categoria;

-- Verificar resultados
SELECT 'RESUMEN DE DATOS' as info;
SELECT 'silver.kronos_ventas_silver' as tabla, COUNT(*) as registros FROM silver.kronos_ventas_silver;
SELECT 'dm.cestas_transacciones' as tabla, COUNT(*) as registros FROM dm.cestas_transacciones;
SELECT 'gold.metricas_agencias' as tabla, COUNT(*) as registros FROM gold.metricas_agencias;
SELECT 'gold.metricas_productos' as tabla, COUNT(*) as registros FROM gold.metricas_productos;

SELECT 'AGENCIAS CON ANOMALIAS' as info;
SELECT centro_costo, tasa_devolucion, rentabilidad_porcentual
FROM gold.metricas_agencias
WHERE tasa_devolucion > 12 OR rentabilidad_porcentual > 35;

SELECT 'PRODUCTOS CON DEVOLUCIONES (CADUCADO)' as info;
SELECT producto, tasa_devolucion, motivo_devolucion_principal
FROM gold.metricas_productos
WHERE tasa_devolucion > 10
ORDER BY tasa_devolucion DESC;
