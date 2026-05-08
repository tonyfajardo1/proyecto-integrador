-- ============================================================================
-- CONDIMENSA - DATA WAREHOUSE
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
COMMENT ON SCHEMA bronze IS 'Capa Bronze: Datos crudos tal como se ingestan desde las fuentes (QuickBooks, Kronos)';

-- SILVER: Datos curados, limpiados, normalizados y validados
DROP SCHEMA IF EXISTS silver CASCADE;
CREATE SCHEMA silver;
COMMENT ON SCHEMA silver IS 'Capa Silver: Datos curados, limpiados, normalizados con reglas de negocio aplicadas';

-- GOLD: Datos analiticos, KPIs calculados y resultados de Data Mining
DROP SCHEMA IF EXISTS gold CASCADE;
CREATE SCHEMA gold;
COMMENT ON SCHEMA gold IS 'Capa Gold: Datos analiticos listos para consumo, KPIs y resultados de ML';

-- LOGS: Auditoria y trazabilidad
DROP SCHEMA IF EXISTS logs CASCADE;
CREATE SCHEMA logs;
COMMENT ON SCHEMA logs IS 'Capa de Logs: Registro de ejecucion de pipelines para trazabilidad';

-- ============================================================================
-- VERIFICAR ESQUEMAS CREADOS
-- ============================================================================
SELECT 
    schema_name,
    obj_description(oid, 'pg_namespace') as descripcion
FROM information_schema.schemata s
JOIN pg_namespace n ON s.schema_name = n.nspname
WHERE schema_name IN ('bronze', 'silver', 'gold', 'logs')
ORDER BY schema_name;
