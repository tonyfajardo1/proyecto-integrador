"""
Generador de Datos Realistas para CONDIMENSA
Usa los productos y agencias REALES de Kronos/QuickBooks
Devoluciones concentradas en pocos productos con motivo CADUCADO
Los datos se ingresan en la capa BRONZE para que los pipelines ETL los procesen
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random
import psycopg2
from psycopg2.extras import execute_values

# Configuracion de conexion
DB_CONFIG = {
    'host': 'localhost',
    'port': 5433,
    'database': 'condimensa_analytics',
    'user': 'condimensa',
    'password': 'REDACTED_LOCAL_DB_PASSWORD'
}

# =============================================================================
# PRODUCTOS REALES DE KRONOS (basado en los datos existentes)
# =============================================================================
PRODUCTOS_KRONOS = [
    # Caldos y Sazonadores (vida util: 12 meses)
    {'codigo': '6986', 'nombre': 'CALDO DE GALLINA 48 GR', 'categoria': 'CALDOS', 'precio': 0.85, 'dias_vida_util': 365},
    {'codigo': '8059', 'nombre': 'SAZONADOR CERDO 1 KL', 'categoria': 'SAZONADORES', 'precio': 8.50, 'dias_vida_util': 365},
    {'codigo': '7328', 'nombre': 'SAZONADOR POLLO FCO 70G', 'categoria': 'SAZONADORES', 'precio': 1.80, 'dias_vida_util': 365},
    {'codigo': '6840', 'nombre': 'SAZON MEXICANA FCO 70 G', 'categoria': 'SAZONADORES', 'precio': 1.90, 'dias_vida_util': 365},
    {'codigo': 'SAZ01', 'nombre': 'SAZONADOR AZAFRAN 1 KILO', 'categoria': 'SAZONADORES', 'precio': 12.00, 'dias_vida_util': 365},

    # Ajos y Alinos (vida util: 8-12 meses)
    {'codigo': '4716', 'nombre': 'AJO PAST DOYPACK VALV 200', 'categoria': 'AJOS', 'precio': 2.50, 'dias_vida_util': 300},  # 10 meses
    {'codigo': '1837', 'nombre': 'AJO PAST DOYPACK VALV 400', 'categoria': 'AJOS', 'precio': 4.20, 'dias_vida_util': 300},  # 10 meses
    {'codigo': '8608', 'nombre': 'ALINO BOT 310 GRS', 'categoria': 'ALINOS', 'precio': 3.80, 'dias_vida_util': 365},  # 12 meses
    {'codigo': '3528', 'nombre': 'ACHIOTE PAST VASO 200GR', 'categoria': 'ACHIOTES', 'precio': 2.80, 'dias_vida_util': 365},

    # Especias (vida util: 12 meses = 1 ano - segun usuario)
    {'codigo': '0398', 'nombre': 'COMINO MOLIDO FDA 200 GRS', 'categoria': 'ESPECIAS', 'precio': 4.50, 'dias_vida_util': 365},
    {'codigo': '0657', 'nombre': 'COMINO MOLIDO FDA 100 GRS', 'categoria': 'ESPECIAS', 'precio': 2.50, 'dias_vida_util': 365},
    {'codigo': '1127', 'nombre': 'PAPRIKA FCO 40G', 'categoria': 'ESPECIAS', 'precio': 1.80, 'dias_vida_util': 365},
    {'codigo': '7366', 'nombre': 'CURRY FCO DE 50 GRS', 'categoria': 'ESPECIAS', 'precio': 2.20, 'dias_vida_util': 365},
    {'codigo': '5843', 'nombre': 'CANELA MOLIDA FDA 100 GRS', 'categoria': 'ESPECIAS', 'precio': 3.20, 'dias_vida_util': 365},
    {'codigo': '9858', 'nombre': 'OREGANO FCO LINEAL 20G', 'categoria': 'ESPECIAS', 'precio': 1.50, 'dias_vida_util': 365},

    # Salsas (vida util: 12 meses)
    {'codigo': '1630', 'nombre': 'SALSA DE AJI 110G', 'categoria': 'SALSAS', 'precio': 1.90, 'dias_vida_util': 365},
    {'codigo': 'SAL01', 'nombre': 'SALSA TOMATE FRASCO 300G', 'categoria': 'SALSAS', 'precio': 2.50, 'dias_vida_util': 365},

    # Aceites (vida util: 12-18 meses)
    {'codigo': '2445', 'nombre': 'ACEITE DE OLIVA BOT PET 200ML', 'categoria': 'ACEITES', 'precio': 5.80, 'dias_vida_util': 450},

    # Snacks/Otros (vida util: 8 meses para mayonesa)
    {'codigo': '6191', 'nombre': 'MAYONESA DISPLAY X 12', 'categoria': 'SALSAS', 'precio': 8.50, 'dias_vida_util': 240},  # 8 meses
    {'codigo': '6658', 'nombre': 'SIROPE DE CHOCOLATE DOYPACK', 'categoria': 'SIROPES', 'precio': 3.50, 'dias_vida_util': 365},
]

# Productos con problemas de caducidad (devoluciones altas)
PRODUCTOS_PROBLEMATICOS = ['4716', '1837', 'SAL01', '6191']  # Ajo pasta, Salsa tomate, Mayonesa

# =============================================================================
# AGENCIAS REALES DE KRONOS
# =============================================================================
AGENCIAS_KRONOS = {
    'quito': {'region': 'SIERRA', 'tamano': 'GRANDE', 'es_anomala': True, 'tipo_anomalia': 'ALTA_RENTABILIDAD'},
    'guayaquil': {'region': 'COSTA', 'tamano': 'GRANDE', 'es_anomala': False, 'tipo_anomalia': None},
    'cuenca': {'region': 'SIERRA', 'tamano': 'MEDIANO', 'es_anomala': False, 'tipo_anomalia': None},
    'ambato': {'region': 'SIERRA', 'tamano': 'MEDIANO', 'es_anomala': False, 'tipo_anomalia': None},
    'loja': {'region': 'SIERRA', 'tamano': 'PEQUENO', 'es_anomala': False, 'tipo_anomalia': None},
    'ibarra': {'region': 'SIERRA', 'tamano': 'PEQUENO', 'es_anomala': False, 'tipo_anomalia': None},
    'portoviejo': {'region': 'COSTA', 'tamano': 'MEDIANO', 'es_anomala': True, 'tipo_anomalia': 'ALTA_DEVOLUCION'},
    'santo_domingo': {'region': 'COSTA', 'tamano': 'MEDIANO', 'es_anomala': False, 'tipo_anomalia': None},
    'riobamba': {'region': 'SIERRA', 'tamano': 'PEQUENO', 'es_anomala': False, 'tipo_anomalia': None},
    'puyo': {'region': 'ORIENTE', 'tamano': 'PEQUENO', 'es_anomala': False, 'tipo_anomalia': None},
}

# =============================================================================
# PATRONES DE CROSS-SELLING (productos que se compran juntos)
# RELACIONES CON SENTIDO COMERCIAL
# =============================================================================
PATRONES_CESTA = [
    # Patron Parrilladas: Sazonador cerdo + Salsa BBQ + Adobo (si existiera)
    (['8059', 'SAL006', '8059'], 0.18),

    # Patron Pollo Rostizado: Sazonador pollo + Ajo pasta + Oregano
    (['7328', '4716', '9858'], 0.25),

    # Patron Carnes: Sazonador cerdo + Ajo pasta + Comino
    (['8059', '1837', '0398'], 0.22),

    # Patron Ensaladas: Mayonesa + Vinagre + Aceite Oliva
    (['6191', 'VIN001', '2445'], 0.15),

    # Patron Comida Rapida: Mayonesa + Salsa Aji + Salsa Tomate
    (['6191', '1630', 'SAL01'], 0.20),

    # Patron Especias Comunes: Comino + Oregano + Paprika
    (['0398', '9858', '1127'], 0.28),

    # Patron Cocina Latina: Achiote + Comino + Ajo pasta
    (['3528', '0657', '4716'], 0.22),

    # Patron Curry: Curry + Canela + Aceite Oliva
    (['7366', '5843', '2445'], 0.12),
]

# =============================================================================
# FUNCIONES DE GENERACION
# =============================================================================

def generar_ventas_kronos(n_registros=500):
    """
    Genera datos de ventas en formato Kronos (agregado por agencia-producto-mes).
    Estos datos iran a la capa Bronze y seran procesados por el ETL.
    """
    print(f"\n[1] Generando {n_registros} registros de ventas Kronos...")

    registros = []
    meses = ['ENERO', 'FEBRERO']

    for _ in range(n_registros):
        # Seleccionar agencia (ponderada por tamano)
        if random.random() < 0.35:
            agencia = random.choice(['quito', 'guayaquil'])
        elif random.random() < 0.65:
            agencia = random.choice(['cuenca', 'ambato', 'portoviejo', 'santo_domingo'])
        else:
            agencia = random.choice(['loja', 'ibarra', 'riobamba', 'puyo'])

        # Seleccionar producto
        producto = random.choice(PRODUCTOS_KRONOS)
        mes = random.choice(meses)

        # Cantidades base
        if AGENCIAS_KRONOS[agencia]['tamano'] == 'GRANDE':
            cant_venta = random.randint(50, 200)
        elif AGENCIAS_KRONOS[agencia]['tamano'] == 'MEDIANO':
            cant_venta = random.randint(20, 80)
        else:
            cant_venta = random.randint(5, 30)

        total_venta = cant_venta * producto['precio']

        # Calcular devoluciones
        # Solo productos problematicos tienen devoluciones significativas (CADUCADO)
        if producto['codigo'] in PRODUCTOS_PROBLEMATICOS:
            # Devoluciones por caducidad: 15-25% en productos perecederos
            if AGENCIAS_KRONOS[agencia].get('tipo_anomalia') == 'ALTA_DEVOLUCION':
                tasa_dev = random.uniform(0.20, 0.30)  # Agencia con problemas
            else:
                tasa_dev = random.uniform(0.12, 0.20)  # Normal para productos problematicos
        else:
            # Productos normales: 0-3% devoluciones
            tasa_dev = random.uniform(0, 0.03)

        cant_devolucion = int(cant_venta * tasa_dev)
        total_devolucion = cant_devolucion * producto['precio']

        # Calcular netos
        cant_neto = cant_venta - cant_devolucion
        total_neto = total_venta - total_devolucion

        # Calcular costo y rentabilidad
        # Agencia Quito tiene mejor rentabilidad (anomalia positiva)
        if agencia == 'quito':
            margen = random.uniform(0.35, 0.45)  # Mejor margen
        else:
            margen = random.uniform(0.20, 0.30)  # Margen normal

        costo_venta = total_neto * (1 - margen)
        rentabilidad = total_neto - costo_venta
        prc_rentabilidad = (rentabilidad / total_neto * 100) if total_neto > 0 else 0

        registros.append({
            'centro_costo': agencia,
            'codigo_producto': producto['codigo'],
            'codigo_alterno': producto['codigo'],
            'producto': producto['nombre'],
            'mes': mes,
            'anio': '2026',
            'cant_venta': cant_venta,
            'total_venta': round(total_venta, 2),
            'cant_nc': 0,
            'total_nc': 0,
            'cant_devolucion': cant_devolucion,
            'total_devolucion': round(total_devolucion, 2),
            'cant_neto': cant_neto,
            'total_neto': round(total_neto, 2),
            'costo_venta': round(costo_venta, 2),
            'rentabilidad': round(rentabilidad, 2),
            'prc_rentabilidad': round(prc_rentabilidad, 2),
            'categoria': producto['categoria'],
            'dias_vida_util': producto['dias_vida_util'],
            'motivo_devolucion': 'CADUCADO' if cant_devolucion > 0 else None
        })

    df = pd.DataFrame(registros)

    print(f"    Registros generados: {len(df)}")
    print(f"    Agencias: {df['centro_costo'].nunique()}")
    print(f"    Productos: {df['producto'].nunique()}")
    print(f"    Total ventas: ${df['total_venta'].sum():,.2f}")
    print(f"    Total devoluciones: ${df['total_devolucion'].sum():,.2f}")

    # Mostrar productos con mas devoluciones
    dev_por_prod = df.groupby('producto')['cant_devolucion'].sum().sort_values(ascending=False)
    print(f"\n    Productos con mas devoluciones:")
    for prod, dev in dev_por_prod.head(5).items():
        if dev > 0:
            print(f"      - {prod}: {dev} unidades")

    return df


def generar_cestas_transacciones(n_transacciones=1500):
    """
    Genera transacciones de cestas para analisis de cross-selling (Apriori).
    Cada transaccion tiene multiples productos comprados juntos.
    """
    print(f"\n[2] Generando {n_transacciones} transacciones de cestas...")

    transacciones = []
    fecha_base = datetime(2026, 1, 1)

    for i in range(n_transacciones):
        # Seleccionar agencia
        agencia = random.choice(list(AGENCIAS_KRONOS.keys()))

        # Fecha aleatoria
        fecha = fecha_base + timedelta(days=random.randint(0, 58))  # Enero-Febrero

        # Seleccionar productos para la cesta
        productos_cesta = []

        # Aplicar patrones de cross-selling con probabilidad
        for patron, prob in PATRONES_CESTA:
            if random.random() < prob:
                productos_cesta.extend(patron)

        # Agregar productos aleatorios adicionales
        n_adicionales = random.randint(0, 2)
        for _ in range(n_adicionales):
            prod = random.choice(PRODUCTOS_KRONOS)
            productos_cesta.append(prod['codigo'])

        # Remover duplicados y asegurar al menos 2 productos
        productos_cesta = list(set(productos_cesta))
        if len(productos_cesta) < 2:
            prods = random.sample(PRODUCTOS_KRONOS, 2)
            productos_cesta = [p['codigo'] for p in prods]

        # Crear registros de la transaccion
        transaccion_id = f"TRX{i+1:06d}"

        for codigo in productos_cesta:
            # Buscar info del producto
            prod_info = next((p for p in PRODUCTOS_KRONOS if p['codigo'] == codigo), None)
            if prod_info:
                cantidad = random.randint(1, 5)
                transacciones.append({
                    'transaccion_id': transaccion_id,
                    'fecha': fecha,
                    'agencia': agencia,
                    'codigo_producto': codigo,
                    'producto': prod_info['nombre'],
                    'categoria': prod_info['categoria'],
                    'cantidad': cantidad,
                    'precio_unitario': prod_info['precio'],
                    'total': cantidad * prod_info['precio']
                })

    df = pd.DataFrame(transacciones)
    print(f"    Transacciones unicas: {df['transaccion_id'].nunique()}")
    print(f"    Items totales: {len(df)}")
    print(f"    Productos distintos: {df['codigo_producto'].nunique()}")

    return df


def cargar_en_bronze(df_kronos, df_cestas):
    """
    Carga los datos en la capa Bronze del Data Warehouse.
    Esto permite que los pipelines ETL procesen los datos normalmente.
    """
    print(f"\n[3] Cargando datos en capa BRONZE...")

    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    try:
        # =================================================================
        # Limpiar tablas existentes
        # =================================================================
        print("    Limpiando tablas existentes...")
        cur.execute("DROP TABLE IF EXISTS dm.cestas_transacciones CASCADE;")
        cur.execute("DROP TABLE IF EXISTS silver.kronos_ventas_silver CASCADE;")
        cur.execute("DROP TABLE IF EXISTS gold.metricas_agencias CASCADE;")
        cur.execute("DROP TABLE IF EXISTS gold.metricas_productos CASCADE;")
        cur.execute("DROP TABLE IF EXISTS gold.reglas_asociacion CASCADE;")
        cur.execute("DROP TABLE IF EXISTS gold.anomalias_agencias CASCADE;")
        cur.execute("DROP TABLE IF EXISTS gold.predicciones_devolucion CASCADE;")

        # =================================================================
        # Crear tabla Silver de Kronos (simulando salida del ETL Silver)
        # =================================================================
        print("    Creando silver.kronos_ventas_silver...")
        cur.execute("CREATE SCHEMA IF NOT EXISTS silver;")
        cur.execute("""
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
                cant_nc NUMERIC(12,2),
                total_nc NUMERIC(15,2),
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
                flag_outlier BOOLEAN DEFAULT FALSE,
                flag_valor_nulo BOOLEAN DEFAULT FALSE,
                fecha_carga TIMESTAMP DEFAULT NOW(),
                pipeline_id VARCHAR(50) DEFAULT 'etl_silver',
                batch_id VARCHAR(50)
            );
        """)

        # Insertar datos Kronos en Silver
        kronos_cols = ['centro_costo', 'codigo_producto', 'codigo_alterno', 'producto', 'mes', 'anio',
                       'cant_venta', 'total_venta', 'cant_nc', 'total_nc', 'cant_devolucion',
                       'total_devolucion', 'cant_neto', 'total_neto', 'costo_venta', 'rentabilidad',
                       'prc_rentabilidad', 'categoria', 'dias_vida_util', 'motivo_devolucion']

        data = [tuple(row[col] for col in kronos_cols) for _, row in df_kronos.iterrows()]
        execute_values(cur, f"""
            INSERT INTO silver.kronos_ventas_silver
            ({', '.join(kronos_cols)})
            VALUES %s
        """, data)
        print(f"    silver.kronos_ventas_silver: {len(data)} registros")

        # =================================================================
        # Crear tabla de cestas para Apriori
        # =================================================================
        print("    Creando dm.cestas_transacciones...")
        cur.execute("CREATE SCHEMA IF NOT EXISTS dm;")
        cur.execute("""
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
        """)

        cestas_cols = ['transaccion_id', 'fecha', 'agencia', 'codigo_producto', 'producto',
                       'categoria', 'cantidad', 'precio_unitario', 'total']
        data = [tuple(row[col] for col in cestas_cols) for _, row in df_cestas.iterrows()]
        execute_values(cur, f"""
            INSERT INTO dm.cestas_transacciones
            ({', '.join(cestas_cols)})
            VALUES %s
        """, data)
        print(f"    dm.cestas_transacciones: {len(data)} registros")

        conn.commit()
        print("\n    [OK] Datos cargados en Bronze/Silver exitosamente")

    except Exception as e:
        conn.rollback()
        print(f"\n    [ERROR] {e}")
        raise
    finally:
        cur.close()
        conn.close()


def crear_tablas_gold(df_kronos):
    """
    Crea las tablas Gold agregadas que seran usadas por los pipelines de DM.
    """
    print(f"\n[4] Creando tablas GOLD...")

    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    try:
        cur.execute("CREATE SCHEMA IF NOT EXISTS gold;")

        # =================================================================
        # Metricas por Agencia (para Isolation Forest)
        # =================================================================
        print("    Creando gold.metricas_agencias...")

        agencias_agg = df_kronos.groupby('centro_costo').agg({
            'cant_venta': 'sum',
            'total_venta': 'sum',
            'cant_devolucion': 'sum',
            'total_devolucion': 'sum',
            'total_neto': 'sum',
            'rentabilidad': 'sum',
            'producto': 'nunique'
        }).reset_index()

        agencias_agg['tasa_devolucion'] = (agencias_agg['cant_devolucion'] / agencias_agg['cant_venta'] * 100).round(2)
        agencias_agg['rentabilidad_porcentual'] = (agencias_agg['rentabilidad'] / agencias_agg['total_neto'] * 100).round(2)
        agencias_agg['ticket_promedio'] = (agencias_agg['total_venta'] / agencias_agg['producto']).round(2)

        # Agregar info de agencias
        for idx, row in agencias_agg.iterrows():
            ag = row['centro_costo']
            if ag in AGENCIAS_KRONOS:
                agencias_agg.loc[idx, 'region'] = AGENCIAS_KRONOS[ag]['region']
                agencias_agg.loc[idx, 'tamano'] = AGENCIAS_KRONOS[ag]['tamano']

        cur.execute("""
            CREATE TABLE gold.metricas_agencias (
                id SERIAL PRIMARY KEY,
                centro_costo VARCHAR(50),
                region VARCHAR(20),
                tamano VARCHAR(20),
                total_ventas NUMERIC(15,2),
                total_devoluciones NUMERIC(15,2),
                total_neto NUMERIC(15,2),
                tasa_devolucion NUMERIC(8,2),
                rentabilidad_porcentual NUMERIC(8,2),
                ticket_promedio NUMERIC(12,2),
                productos_distintos INTEGER
            );
        """)

        data = [(row['centro_costo'], row.get('region', 'SIERRA'), row.get('tamano', 'MEDIANO'),
                 float(row['total_venta']), float(row['total_devolucion']), float(row['total_neto']),
                 float(row['tasa_devolucion']), float(row['rentabilidad_porcentual']),
                 float(row['ticket_promedio']), int(row['producto']))
                for _, row in agencias_agg.iterrows()]

        execute_values(cur, """
            INSERT INTO gold.metricas_agencias
            (centro_costo, region, tamano, total_ventas, total_devoluciones, total_neto,
             tasa_devolucion, rentabilidad_porcentual, ticket_promedio, productos_distintos)
            VALUES %s
        """, data)
        print(f"    gold.metricas_agencias: {len(data)} agencias")

        # =================================================================
        # Metricas por Producto (para Random Forest)
        # =================================================================
        print("    Creando gold.metricas_productos...")

        productos_agg = df_kronos.groupby(['codigo_producto', 'producto', 'categoria']).agg({
            'cant_venta': 'sum',
            'total_venta': 'sum',
            'cant_devolucion': 'sum',
            'total_devolucion': 'sum',
            'total_neto': 'sum',
            'rentabilidad': 'sum',
            'centro_costo': 'nunique',
            'dias_vida_util': 'first',
            'motivo_devolucion': lambda x: x.dropna().mode().iloc[0] if len(x.dropna()) > 0 and len(x.dropna().mode()) > 0 else None
        }).reset_index()

        productos_agg['tasa_devolucion'] = (productos_agg['cant_devolucion'] / productos_agg['cant_venta'] * 100).round(2)
        productos_agg['rentabilidad_porcentual'] = (productos_agg['rentabilidad'] / productos_agg['total_neto'] * 100).round(2)

        cur.execute("""
            CREATE TABLE gold.metricas_productos (
                id SERIAL PRIMARY KEY,
                codigo_producto VARCHAR(20),
                producto VARCHAR(100),
                categoria VARCHAR(50),
                cantidad_vendida INTEGER,
                cantidad_devuelta INTEGER,
                total_ventas NUMERIC(15,2),
                total_devoluciones NUMERIC(15,2),
                tasa_devolucion NUMERIC(8,2),
                rentabilidad_porcentual NUMERIC(8,2),
                n_agencias_venta INTEGER,
                dias_vida_util INTEGER,
                motivo_devolucion_principal VARCHAR(50)
            );
        """)

        data = [(row['codigo_producto'], row['producto'], row['categoria'],
                 int(row['cant_venta']), int(row['cant_devolucion']),
                 float(row['total_venta']), float(row['total_devolucion']),
                 float(row['tasa_devolucion']), float(row['rentabilidad_porcentual']),
                 int(row['centro_costo']), int(row['dias_vida_util']) if pd.notna(row['dias_vida_util']) else 180,
                 row['motivo_devolucion'] if pd.notna(row['motivo_devolucion']) else None)
                for _, row in productos_agg.iterrows()]

        execute_values(cur, """
            INSERT INTO gold.metricas_productos
            (codigo_producto, producto, categoria, cantidad_vendida, cantidad_devuelta,
             total_ventas, total_devoluciones, tasa_devolucion, rentabilidad_porcentual,
             n_agencias_venta, dias_vida_util, motivo_devolucion_principal)
            VALUES %s
        """, data)
        print(f"    gold.metricas_productos: {len(data)} productos")

        conn.commit()
        print("\n    [OK] Tablas Gold creadas exitosamente")

    except Exception as e:
        conn.rollback()
        print(f"\n    [ERROR] {e}")
        raise
    finally:
        cur.close()
        conn.close()


def mostrar_resumen():
    """Muestra resumen de los datos generados."""
    print(f"\n{'='*70}")
    print("RESUMEN DE DATOS GENERADOS")
    print(f"{'='*70}")

    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    # Verificar tablas
    cur.execute("SELECT COUNT(*) FROM silver.kronos_ventas_silver")
    n_silver = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM dm.cestas_transacciones")
    n_cestas = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM gold.metricas_agencias")
    n_agencias = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM gold.metricas_productos")
    n_productos = cur.fetchone()[0]

    print(f"\nTABLAS CREADAS:")
    print(f"  - silver.kronos_ventas_silver: {n_silver} registros")
    print(f"  - dm.cestas_transacciones: {n_cestas} items")
    print(f"  - gold.metricas_agencias: {n_agencias} agencias")
    print(f"  - gold.metricas_productos: {n_productos} productos")

    # Mostrar agencias con anomalias
    cur.execute("""
        SELECT centro_costo, tasa_devolucion, rentabilidad_porcentual
        FROM gold.metricas_agencias
        WHERE tasa_devolucion > 10 OR rentabilidad_porcentual > 35
        ORDER BY tasa_devolucion DESC
    """)
    anomalias = cur.fetchall()

    print(f"\nAGENCIAS CON COMPORTAMIENTO ANOMALO:")
    for ag, dev, rent in anomalias:
        if dev > 10:
            print(f"  - {ag.upper()}: ALTA_DEVOLUCION ({dev:.1f}%)")
        elif rent > 35:
            print(f"  - {ag.upper()}: ALTA_RENTABILIDAD ({rent:.1f}%)")

    # Mostrar productos con devoluciones
    cur.execute("""
        SELECT producto, tasa_devolucion, motivo_devolucion_principal
        FROM gold.metricas_productos
        WHERE tasa_devolucion > 10
        ORDER BY tasa_devolucion DESC
    """)
    productos_dev = cur.fetchall()

    print(f"\nPRODUCTOS CON ALTO RIESGO DE DEVOLUCION:")
    for prod, dev, motivo in productos_dev:
        print(f"  - {prod}: {dev:.1f}% ({motivo})")

    conn.close()

    print(f"\n{'='*70}")
    print("DATOS LISTOS PARA PIPELINES DE DATA MINING")
    print(f"{'='*70}")


def main():
    print("="*70)
    print("GENERADOR DE DATOS REALISTAS - CONDIMENSA")
    print("Usando productos y agencias REALES de Kronos")
    print("="*70)

    # Generar datos (menos registros para ser mas rapido)
    df_kronos = generar_ventas_kronos(n_registros=300)
    df_cestas = generar_cestas_transacciones(n_transacciones=800)

    # Cargar en base de datos
    cargar_en_bronze(df_kronos, df_cestas)
    crear_tablas_gold(df_kronos)

    # Mostrar resumen
    mostrar_resumen()


if __name__ == "__main__":
    main()
