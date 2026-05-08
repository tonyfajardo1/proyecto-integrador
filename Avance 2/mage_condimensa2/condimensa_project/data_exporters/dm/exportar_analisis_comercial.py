"""
Data Exporter: Guardar resultados del analisis comercial de Kronos
Pipeline: dm_analisis_comercial_kronos
Exporta a gold.kpis_comercial_agencia, gold.kpis_comercial_producto, gold.kpis_comercial_mes
"""
from mage_ai.settings.repo import get_repo_path
from mage_ai.io.config import ConfigFileLoader
from mage_ai.io.postgres import Postgres
from os import path
import pandas as pd
from datetime import datetime

if 'data_exporter' not in dir():
    from mage_ai.data_preparation.decorators import data_exporter
if 'test' not in dir():
    from mage_ai.data_preparation.decorators import test


@data_exporter
def exportar_analisis_comercial(data, *args, **kwargs):
    """
    Exporta los KPIs comerciales al Data Warehouse.

    Tablas destino:
    - gold.kpis_comercial_agencia: KPIs por agencia
    - gold.kpis_comercial_producto: KPIs por producto
    - gold.kpis_comercial_mes: KPIs por mes
    """

    kpis_agencia = data['kpis_agencia']
    kpis_producto = data['kpis_producto']
    kpis_mes = data['kpis_mes']
    resumen = data['resumen']

    config_path = path.join(get_repo_path(), 'io_config.yaml')
    config_profile = 'local_dwh'

    print(f"\n{'='*70}")
    print(f"EXPORTANDO ANALISIS COMERCIAL - KRONOS")
    print(f"{'='*70}\n")

    # =========================================================================
    # 1. CREAR TABLAS
    # =========================================================================

    ddl_agencia = """
    CREATE TABLE IF NOT EXISTS gold.kpis_comercial_agencia (
        id SERIAL PRIMARY KEY,
        agencia VARCHAR(100),
        total_ventas NUMERIC,
        unidades_vendidas NUMERIC,
        total_devoluciones NUMERIC,
        unidades_devueltas NUMERIC,
        rentabilidad_total NUMERIC,
        costo_total NUMERIC,
        productos_vendidos INT,
        margen_promedio NUMERIC,
        tasa_devolucion NUMERIC,
        ticket_promedio NUMERIC,
        margen_neto NUMERIC,
        ranking_ventas INT,
        ranking_rentabilidad INT,
        participacion_mercado NUMERIC,
        fecha_analisis TIMESTAMP DEFAULT NOW()
    );
    """

    ddl_producto = """
    CREATE TABLE IF NOT EXISTS gold.kpis_comercial_producto (
        id SERIAL PRIMARY KEY,
        producto VARCHAR(500),
        codigo VARCHAR(50),
        total_ventas NUMERIC,
        unidades INT,
        rentabilidad NUMERIC,
        devoluciones INT,
        margen_promedio NUMERIC,
        agencias_venta INT,
        tasa_devolucion NUMERIC,
        precio_promedio NUMERIC,
        ranking_ventas INT,
        ranking_rentabilidad INT,
        participacion NUMERIC,
        participacion_acumulada NUMERIC,
        es_pareto_80 BOOLEAN,
        fecha_analisis TIMESTAMP DEFAULT NOW()
    );
    """

    ddl_mes = """
    CREATE TABLE IF NOT EXISTS gold.kpis_comercial_mes (
        id SERIAL PRIMARY KEY,
        mes VARCHAR(20),
        anio INT,
        total_ventas NUMERIC,
        unidades INT,
        rentabilidad NUMERIC,
        devoluciones INT,
        margen NUMERIC,
        fecha_analisis TIMESTAMP DEFAULT NOW()
    );
    """

    with Postgres.with_config(ConfigFileLoader(config_path, config_profile)) as loader:
        loader.execute(ddl_agencia)
        loader.execute(ddl_producto)
        loader.execute(ddl_mes)
        print("[1] Tablas creadas/verificadas en gold schema")

        # Limpiar datos anteriores
        loader.execute("TRUNCATE TABLE gold.kpis_comercial_agencia;")
        loader.execute("TRUNCATE TABLE gold.kpis_comercial_producto;")
        loader.execute("TRUNCATE TABLE gold.kpis_comercial_mes;")
        print("[2] Datos anteriores limpiados")

    # =========================================================================
    # 2. EXPORTAR KPIs POR AGENCIA
    # =========================================================================

    kpis_agencia['fecha_analisis'] = datetime.now()

    with Postgres.with_config(ConfigFileLoader(config_path, config_profile)) as loader:
        loader.export(
            kpis_agencia,
            'gold',
            'kpis_comercial_agencia',
            index=False,
            if_exists='append'
        )
    print(f"[3] Exportados {len(kpis_agencia)} KPIs de agencia a gold.kpis_comercial_agencia")

    # =========================================================================
    # 3. EXPORTAR KPIs POR PRODUCTO
    # =========================================================================

    kpis_producto['fecha_analisis'] = datetime.now()

    with Postgres.with_config(ConfigFileLoader(config_path, config_profile)) as loader:
        loader.export(
            kpis_producto,
            'gold',
            'kpis_comercial_producto',
            index=False,
            if_exists='append'
        )
    print(f"[4] Exportados {len(kpis_producto)} KPIs de producto a gold.kpis_comercial_producto")

    # =========================================================================
    # 4. EXPORTAR KPIs POR MES
    # =========================================================================

    kpis_mes['fecha_analisis'] = datetime.now()

    with Postgres.with_config(ConfigFileLoader(config_path, config_profile)) as loader:
        loader.export(
            kpis_mes,
            'gold',
            'kpis_comercial_mes',
            index=False,
            if_exists='append'
        )
    print(f"[5] Exportados {len(kpis_mes)} KPIs mensuales a gold.kpis_comercial_mes")

    # =========================================================================
    # 5. RESUMEN
    # =========================================================================

    print(f"\n{'='*70}")
    print(f"RESUMEN DE EXPORTACION - ANALISIS COMERCIAL KRONOS")
    print(f"{'='*70}")
    print(f"  - KPIs Agencias: {len(kpis_agencia)} registros")
    print(f"  - KPIs Productos: {len(kpis_producto)} registros")
    print(f"  - KPIs Mensuales: {len(kpis_mes)} registros")
    print(f"\n[METRICAS GLOBALES]")
    print(f"  - Total Ventas: ${resumen['total_ventas']:,.2f}")
    print(f"  - Mejor Agencia: {resumen['mejor_agencia']}")
    print(f"  - Margen Promedio: {resumen['margen_promedio']:.1f}%")
    print(f"  - Productos Pareto (80%): {resumen['productos_pareto']}")
    print(f"\n{'='*70}\n")

    return {
        'agencias_exportadas': len(kpis_agencia),
        'productos_exportados': len(kpis_producto),
        'meses_exportados': len(kpis_mes)
    }


@test
def test_output(output, *args) -> None:
    assert output is not None, 'Exportacion fallo'
    assert output['agencias_exportadas'] > 0, 'No se exportaron agencias'
    print(f"OK: Exportacion comercial completada")
