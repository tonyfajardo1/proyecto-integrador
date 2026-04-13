"""
Transformer: Calcular KPIs y mover a Gold
Pipeline: etl_gold_kpis
Calcula KPIs y metricas desde Silver hacia Gold.
"""
import pandas as pd
import numpy as np

if 'transformer' not in dir():
    from mage_ai.data_preparation.decorators import transformer
if 'test' not in dir():
    from mage_ai.data_preparation.decorators import test


@transformer
def calcular_kpis_gold(*args, **kwargs):
    """
    Calcula KPIs desde Silver y los prepara para Gold.
    - KPIs de ventas
    - Metricas por agencia
    - Metricas por producto
    """
    
    # Obtener datos desde Silver (simulado - en Mage vendria del Data Loader)
    # En la practica, esto recibiria los datos del paso anterior
    
    print(f"\n{'='*70}")
    print(f"CALCULO DE KPIs - SILVER A GOLD")
    print(f"{'='*70}\n")
    
    pipeline_id = kwargs.get('pipeline_id', 'etl_gold_kpis')
    
    return {
        'status': 'READY_FOR_GOLD',
        'pipeline_id': pipeline_id
    }


@transformer
def calcular_kpis_ventas(data, *args, **kwargs):
    """
    Calcula KPIs de ventas comerciales.
    """
    # Este transformador recibe datos desde Silver y calcula KPIs
    
    print(f"\n{'='*70}")
    print(f"CALCULO KPIs DE VENTAS")
    print(f"{'='*70}\n")
    
    pipeline_id = kwargs.get('pipeline_id', 'etl_gold_kpis')
    
    # Los KPIs se calculan desde silver.kronos_ventas
    # Este transformador retorna la instruccion SQL o datos listos
    
    return {
        'sql_kpis_ventas': """
            INSERT INTO gold.kpis_ventas (
                centro_costo, producto, mes, anio,
                cant_venta, total_venta, cant_neto, total_neto,
                cant_devolucion, total_devolucion,
                tasa_devolucion_cant, tasa_devolucion_valor,
                nivel_devolucion, costo_venta, rentabilidad,
                prc_rentabilidad, margen_bruto, nivel_rentabilidad,
                ticket_promedio, fecha_calculo, pipeline_id
            )
            SELECT 
                centro_costo,
                producto,
                mes,
                anio,
                SUM(cant_venta) as cant_venta,
                SUM(total_venta) as total_venta,
                SUM(cant_neto) as cant_neto,
                SUM(total_neto) as total_neto,
                SUM(cant_devolucion) as cant_devolucion,
                SUM(total_devolucion) as total_devolucion,
                CASE 
                    WHEN SUM(cant_venta) > 0 THEN (SUM(cant_devolucion)::NUMERIC / SUM(cant_venta)) * 100
                    ELSE 0 
                END as tasa_devolucion_cant,
                CASE 
                    WHEN SUM(total_venta) > 0 THEN (SUM(total_devolucion)::NUMERIC / SUM(total_venta)) * 100
                    ELSE 0 
                END as tasa_devolucion_valor,
                CASE 
                    WHEN (SUM(total_devolucion)::NUMERIC / NULLIF(SUM(total_venta), 0)) * 100 > 20 THEN 'CRITICA'
                    WHEN (SUM(total_devolucion)::NUMERIC / NULLIF(SUM(total_venta), 0)) * 100 > 10 THEN 'ELEVADA'
                    WHEN SUM(total_devolucion) > 0 THEN 'NORMAL'
                    ELSE 'SIN_DEVOLUCION'
                END as nivel_devolucion,
                SUM(costo_venta) as costo_venta,
                SUM(rentabilidad) as rentabilidad,
                AVG(prc_rentabilidad) as prc_rentabilidad,
                CASE 
                    WHEN SUM(total_venta) > 0 THEN (SUM(rentabilidad)::NUMERIC / SUM(total_venta)) * 100
                    ELSE 0 
                END as margen_bruto,
                CASE 
                    WHEN (SUM(rentabilidad)::NUMERIC / NULLIF(SUM(total_venta), 0)) * 100 > 30 THEN 'ALTA'
                    WHEN (SUM(rentabilidad)::NUMERIC / NULLIF(SUM(total_venta), 0)) * 100 > 15 THEN 'NORMAL'
                    WHEN (SUM(rentabilidad)::NUMERIC / NULLIF(SUM(total_venta), 0)) * 100 > 0 THEN 'BAJA'
                    ELSE 'PERDIDA'
                END as nivel_rentabilidad,
                CASE 
                    WHEN SUM(cant_venta) > 0 THEN SUM(total_venta) / SUM(cant_venta)
                    ELSE 0 
                END as ticket_promedio,
                CURRENT_TIMESTAMP as fecha_calculo,
                :pipeline_id as pipeline_id
            FROM silver.kronos_ventas
            WHERE es_dato_calidado = TRUE
            GROUP BY centro_costo, producto, mes, anio
        """,
        'pipeline_id': pipeline_id
    }


@transformer
def calcular_metricas_agencias(data, *args, **kwargs):
    """
    Calcula metricas consolidadas por agencia.
    """
    print(f"\n{'='*70}")
    print(f"CALCULO METRICAS POR AGENCIA")
    print(f"{'='*70}\n")
    
    pipeline_id = kwargs.get('pipeline_id', 'etl_gold_kpis')
    
    return {
        'sql_metricas_agencias': """
            INSERT INTO gold.metricas_agencias (
                centro_costo, total_venta, total_neto, num_ventas, ticket_promedio,
                total_devolucion, tasa_devolucion, rentabilidad_total, rentabilidad_promedio,
                margen_promedio, costo_total, ratio_costo, total_nc, tasa_nc,
                fecha_calculo, pipeline_id
            )
            SELECT 
                centro_costo,
                SUM(total_venta) as total_venta,
                SUM(total_neto) as total_neto,
                COUNT(*) as num_ventas,
                AVG(total_venta) as ticket_promedio,
                SUM(total_devolucion) as total_devolucion,
                CASE 
                    WHEN SUM(total_venta) > 0 THEN (SUM(total_devolucion)::NUMERIC / SUM(total_venta)) * 100
                    ELSE 0 
                END as tasa_devolucion,
                SUM(rentabilidad) as rentabilidad_total,
                AVG(prc_rentabilidad) as rentabilidad_promedio,
                CASE 
                    WHEN SUM(total_venta) > 0 THEN (SUM(rentabilidad)::NUMERIC / SUM(total_venta)) * 100
                    ELSE 0 
                END as margen_promedio,
                SUM(costo_venta) as costo_total,
                CASE 
                    WHEN SUM(total_venta) > 0 THEN (SUM(costo_venta)::NUMERIC / SUM(total_venta)) * 100
                    ELSE 0 
                END as ratio_costo,
                SUM(total_nc) as total_nc,
                CASE 
                    WHEN SUM(total_venta) > 0 THEN (SUM(total_nc)::NUMERIC / SUM(total_venta)) * 100
                    ELSE 0 
                END as tasa_nc,
                CURRENT_TIMESTAMP as fecha_calculo,
                :pipeline_id as pipeline_id
            FROM silver.kronos_ventas
            WHERE es_dato_calidado = TRUE
            GROUP BY centro_costo
        """,
        'pipeline_id': pipeline_id
    }


@transformer
def calcular_metricas_productos(data, *args, **kwargs):
    """
    Calcula metricas consolidadas por producto.
    """
    print(f"\n{'='*70}")
    print(f"CALCULO METRICAS POR PRODUCTO")
    print(f"{'='*70}\n")
    
    pipeline_id = kwargs.get('pipeline_id', 'etl_gold_kpis')
    
    return {
        'sql_metricas_productos': """
            INSERT INTO gold.metricas_productos (
                producto, categoria, total_venta, cant_venta, num_transacciones,
                ticket_promedio, total_devolucion, tasa_devolucion,
                rentabilidad_total, rentabilidad_promedio, num_agencias, penetracion,
                fecha_calculo, pipeline_id
            )
            SELECT 
                producto,
                SPLIT_PART(producto, ' ', 1) as categoria,
                SUM(total_venta) as total_venta,
                SUM(cant_venta) as cant_venta,
                COUNT(*) as num_transacciones,
                AVG(total_venta) as ticket_promedio,
                SUM(total_devolucion) as total_devolucion,
                CASE 
                    WHEN SUM(total_venta) > 0 THEN (SUM(total_devolucion)::NUMERIC / SUM(total_venta)) * 100
                    ELSE 0 
                END as tasa_devolucion,
                SUM(rentabilidad) as rentabilidad_total,
                AVG(prc_rentabilidad) as rentabilidad_promedio,
                COUNT(DISTINCT centro_costo) as num_agencias,
                (COUNT(DISTINCT centro_costo)::NUMERIC / 
                    (SELECT COUNT(DISTINCT centro_costo) FROM silver.kronos_ventas) * 100) as penetracion,
                CURRENT_TIMESTAMP as fecha_calculo,
                :pipeline_id as pipeline_id
            FROM silver.kronos_ventas
            WHERE es_dato_calidado = TRUE
            GROUP BY producto
        """,
        'pipeline_id': pipeline_id
    }


@test
def test_output(output, *args) -> None:
    assert output is not None, 'Calculo fallo'
    print(f"OK: KPIs calculados")
