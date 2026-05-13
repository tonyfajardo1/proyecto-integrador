"""
Generador de Datos Ficticios para CONDIMENSA
Genera datos realistas para responder las 3 preguntas analiticas:
1. Cross-selling (Apriori) - Productos que se venden juntos
2. Anomalias (Isolation Forest) - Agencias con comportamiento atipico
3. Predicciones (Random Forest) - Productos con alto riesgo de devolucion
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
    'password': 'change_me'
}

# =============================================================================
# CATALOGO DE PRODUCTOS CONDIMENSA (Realista para empresa de condimentos)
# =============================================================================
PRODUCTOS = {
    # Salsas (categoria principal)
    'SAL001': {'nombre': 'Salsa de Tomate 500ml', 'categoria': 'SALSAS', 'precio': 2.50, 'costo': 1.20},
    'SAL002': {'nombre': 'Salsa de Tomate 1L', 'categoria': 'SALSAS', 'precio': 4.20, 'costo': 2.00},
    'SAL003': {'nombre': 'Mayonesa 500g', 'categoria': 'SALSAS', 'precio': 3.80, 'costo': 1.80},
    'SAL004': {'nombre': 'Mayonesa 1kg', 'categoria': 'SALSAS', 'precio': 6.50, 'costo': 3.00},
    'SAL005': {'nombre': 'Mostaza 250g', 'categoria': 'SALSAS', 'precio': 2.20, 'costo': 1.00},
    'SAL006': {'nombre': 'Salsa BBQ 350ml', 'categoria': 'SALSAS', 'precio': 3.50, 'costo': 1.60},
    'SAL007': {'nombre': 'Salsa Picante 150ml', 'categoria': 'SALSAS', 'precio': 2.80, 'costo': 1.30},
    'SAL008': {'nombre': 'Salsa de Ajo 200ml', 'categoria': 'SALSAS', 'precio': 3.20, 'costo': 1.50},

    # Especias
    'ESP001': {'nombre': 'Sazonador Completo 100g', 'categoria': 'ESPECIAS', 'precio': 1.80, 'costo': 0.70},
    'ESP002': {'nombre': 'Pimienta Negra 50g', 'categoria': 'ESPECIAS', 'precio': 2.50, 'costo': 1.10},
    'ESP003': {'nombre': 'Comino Molido 50g', 'categoria': 'ESPECIAS', 'precio': 2.00, 'costo': 0.90},
    'ESP004': {'nombre': 'Oregano 25g', 'categoria': 'ESPECIAS', 'precio': 1.50, 'costo': 0.60},
    'ESP005': {'nombre': 'Achiote en Pasta 100g', 'categoria': 'ESPECIAS', 'precio': 1.80, 'costo': 0.75},
    'ESP006': {'nombre': 'Curry en Polvo 50g', 'categoria': 'ESPECIAS', 'precio': 2.80, 'costo': 1.20},

    # Vinagres y Aceites
    'VIN001': {'nombre': 'Vinagre Blanco 500ml', 'categoria': 'VINAGRES', 'precio': 1.80, 'costo': 0.80},
    'VIN002': {'nombre': 'Vinagre de Manzana 500ml', 'categoria': 'VINAGRES', 'precio': 2.50, 'costo': 1.10},
    'ACE001': {'nombre': 'Aceite Vegetal 1L', 'categoria': 'ACEITES', 'precio': 3.50, 'costo': 1.80},
    'ACE002': {'nombre': 'Aceite de Oliva 500ml', 'categoria': 'ACEITES', 'precio': 8.50, 'costo': 4.50},

    # Condimentos preparados
    'CON001': {'nombre': 'Adobo Listo 200g', 'categoria': 'CONDIMENTOS', 'precio': 2.80, 'costo': 1.30},
    'CON002': {'nombre': 'Marinada para Carnes 300ml', 'categoria': 'CONDIMENTOS', 'precio': 4.20, 'costo': 2.00},
    'CON003': {'nombre': 'Aliño Criollo 250ml', 'categoria': 'CONDIMENTOS', 'precio': 3.00, 'costo': 1.40},
    'CON004': {'nombre': 'Pasta de Ajo y Perejil 150g', 'categoria': 'CONDIMENTOS', 'precio': 3.50, 'costo': 1.60},

    # Productos problematicos (para detectar devoluciones)
    'PRB001': {'nombre': 'Salsa Experimental X 200ml', 'categoria': 'SALSAS', 'precio': 4.00, 'costo': 2.00},
    'PRB002': {'nombre': 'Condimento Fusion 100g', 'categoria': 'ESPECIAS', 'precio': 3.50, 'costo': 1.70},
}

# =============================================================================
# AGENCIAS (10 agencias con diferentes comportamientos)
# =============================================================================
AGENCIAS = {
    'quito': {'region': 'SIERRA', 'tamano': 'GRANDE', 'comportamiento': 'ANOMALO_POSITIVO'},
    'guayaquil': {'region': 'COSTA', 'tamano': 'GRANDE', 'comportamiento': 'NORMAL'},
    'cuenca': {'region': 'SIERRA', 'tamano': 'MEDIANO', 'comportamiento': 'NORMAL'},
    'ambato': {'region': 'SIERRA', 'tamano': 'MEDIANO', 'comportamiento': 'NORMAL'},
    'manta': {'region': 'COSTA', 'tamano': 'MEDIANO', 'comportamiento': 'ANOMALO_NEGATIVO'},
    'machala': {'region': 'COSTA', 'tamano': 'PEQUENO', 'comportamiento': 'NORMAL'},
    'loja': {'region': 'SIERRA', 'tamano': 'PEQUENO', 'comportamiento': 'NORMAL'},
    'riobamba': {'region': 'SIERRA', 'tamano': 'PEQUENO', 'comportamiento': 'NORMAL'},
    'esmeraldas': {'region': 'COSTA', 'tamano': 'PEQUENO', 'comportamiento': 'ANOMALO_NEGATIVO'},
    'santo_domingo': {'region': 'COSTA', 'tamano': 'MEDIANO', 'comportamiento': 'NORMAL'},
}

# =============================================================================
# PATRONES DE CROSS-SELLING (Productos que se compran juntos)
# =============================================================================
PATRONES_CESTA = [
    # Patron BBQ: Salsa BBQ + Marinada + Mostaza
    (['SAL006', 'CON002', 'SAL005'], 0.25),

    # Patron Ensaladas: Mayonesa + Vinagre + Aceite Oliva
    (['SAL003', 'VIN002', 'ACE002'], 0.20),

    # Patron Cocina Basica: Salsa Tomate + Sazonador + Aceite Vegetal
    (['SAL001', 'ESP001', 'ACE001'], 0.30),

    # Patron Parrilladas: Salsa BBQ + Salsa Picante + Adobo
    (['SAL006', 'SAL007', 'CON001'], 0.15),

    # Patron Gourmet: Aceite Oliva + Vinagre Manzana + Oregano + Pimienta
    (['ACE002', 'VIN002', 'ESP004', 'ESP002'], 0.10),

    # Patron Tradicional: Achiote + Comino + Aliño Criollo
    (['ESP005', 'ESP003', 'CON003'], 0.18),

    # Patron Salsas: Mayonesa + Mostaza + Salsa Ajo
    (['SAL003', 'SAL005', 'SAL008'], 0.22),
]

# =============================================================================
# FUNCIONES DE GENERACION DE DATOS
# =============================================================================

def generar_cestas(n_transacciones=2000):
    """
    Genera transacciones de cestas para analisis de asociacion (Apriori).
    Cada transaccion representa una compra con multiples productos.
    """
    print(f"\n[1] Generando {n_transacciones} transacciones de cestas...")

    transacciones = []
    fecha_base = datetime(2026, 1, 1)

    for i in range(n_transacciones):
        # Seleccionar agencia (ponderada por tamano)
        if random.random() < 0.4:
            agencia = random.choice(['quito', 'guayaquil'])
        elif random.random() < 0.7:
            agencia = random.choice(['cuenca', 'ambato', 'manta', 'santo_domingo'])
        else:
            agencia = random.choice(['machala', 'loja', 'riobamba', 'esmeraldas'])

        # Fecha aleatoria en enero 2026
        fecha = fecha_base + timedelta(days=random.randint(0, 30))

        # Seleccionar productos para la cesta
        productos_cesta = []

        # Aplicar patrones de cross-selling con probabilidad
        for patron, prob in PATRONES_CESTA:
            if random.random() < prob:
                productos_cesta.extend(patron)

        # Agregar productos aleatorios adicionales
        n_adicionales = random.randint(0, 3)
        productos_adicionales = random.sample(list(PRODUCTOS.keys()), min(n_adicionales, len(PRODUCTOS)))
        productos_cesta.extend(productos_adicionales)

        # Remover duplicados y asegurar al menos 2 productos
        productos_cesta = list(set(productos_cesta))
        if len(productos_cesta) < 2:
            productos_cesta = random.sample(list(PRODUCTOS.keys()), 2)

        # Crear registro de transaccion
        transaccion_id = f"TRX{i+1:06d}"

        for producto in productos_cesta:
            cantidad = random.randint(1, 10)
            precio = PRODUCTOS[producto]['precio']

            transacciones.append({
                'transaccion_id': transaccion_id,
                'fecha': fecha,
                'agencia': agencia,
                'codigo_producto': producto,
                'producto': PRODUCTOS[producto]['nombre'],
                'categoria': PRODUCTOS[producto]['categoria'],
                'cantidad': cantidad,
                'precio_unitario': precio,
                'total': cantidad * precio
            })

    df = pd.DataFrame(transacciones)
    print(f"    Transacciones unicas: {df['transaccion_id'].nunique()}")
    print(f"    Items totales: {len(df)}")
    print(f"    Productos distintos: {df['codigo_producto'].nunique()}")

    return df


def generar_datos_agencias(df_cestas):
    """
    Genera metricas agregadas por agencia para deteccion de anomalias.
    Incluye agencias con comportamiento anomalo intencional.
    """
    print(f"\n[2] Generando metricas de agencias...")

    agencias_data = []

    for agencia, info in AGENCIAS.items():
        df_ag = df_cestas[df_cestas['agencia'] == agencia]

        if len(df_ag) == 0:
            # Generar datos base si no hay transacciones
            total_ventas = random.uniform(5000, 20000)
            n_transacciones = random.randint(50, 200)
        else:
            total_ventas = df_ag['total'].sum()
            n_transacciones = df_ag['transaccion_id'].nunique()

        # Calcular metricas base
        ticket_promedio = total_ventas / max(n_transacciones, 1)

        # Generar devoluciones (normal: 2-5%, problematico: 15-25%)
        if info['comportamiento'] == 'ANOMALO_NEGATIVO':
            tasa_devolucion = random.uniform(15, 25)
            rentabilidad = random.uniform(5, 15)  # Baja rentabilidad
        elif info['comportamiento'] == 'ANOMALO_POSITIVO':
            tasa_devolucion = random.uniform(0.5, 2)
            rentabilidad = random.uniform(35, 50)  # Alta rentabilidad
        else:
            tasa_devolucion = random.uniform(2, 6)
            rentabilidad = random.uniform(18, 28)

        total_devoluciones = total_ventas * (tasa_devolucion / 100)
        total_neto = total_ventas - total_devoluciones

        # Productos distintos
        if len(df_ag) > 0:
            productos_distintos = df_ag['codigo_producto'].nunique()
        else:
            productos_distintos = random.randint(10, 20)

        agencias_data.append({
            'centro_costo': agencia,
            'region': info['region'],
            'tamano': info['tamano'],
            'total_transacciones': n_transacciones,
            'total_ventas': round(total_ventas, 2),
            'total_devoluciones': round(total_devoluciones, 2),
            'total_neto': round(total_neto, 2),
            'ticket_promedio': round(ticket_promedio, 2),
            'tasa_devolucion': round(tasa_devolucion, 2),
            'rentabilidad_porcentual': round(rentabilidad, 2),
            'productos_distintos': productos_distintos,
            'comportamiento_esperado': info['comportamiento']
        })

    df = pd.DataFrame(agencias_data)
    print(f"    Agencias procesadas: {len(df)}")
    print(f"    Anomalas esperadas: {len(df[df['comportamiento_esperado'] != 'NORMAL'])}")

    return df


def generar_datos_productos(df_cestas):
    """
    Genera metricas por producto para prediccion de devoluciones.
    Incluye productos con alta probabilidad de devolucion.
    """
    print(f"\n[3] Generando metricas de productos...")

    productos_data = []

    for codigo, info in PRODUCTOS.items():
        df_prod = df_cestas[df_cestas['codigo_producto'] == codigo]

        if len(df_prod) == 0:
            cantidad_vendida = random.randint(50, 500)
            total_ventas = cantidad_vendida * info['precio']
        else:
            cantidad_vendida = df_prod['cantidad'].sum()
            total_ventas = df_prod['total'].sum()

        # Calcular devoluciones (productos PRB tienen alta devolucion)
        if codigo.startswith('PRB'):
            tasa_devolucion = random.uniform(18, 30)
            motivo_principal = random.choice(['CALIDAD', 'SABOR', 'PRESENTACION'])
        elif info['categoria'] == 'SALSAS' and random.random() < 0.1:
            tasa_devolucion = random.uniform(8, 15)
            motivo_principal = 'VENCIMIENTO'
        else:
            tasa_devolucion = random.uniform(1, 5)
            motivo_principal = random.choice(['DANADO_TRANSPORTE', 'ERROR_PEDIDO', 'OTRO'])

        cantidad_devuelta = int(cantidad_vendida * (tasa_devolucion / 100))

        # Calcular rentabilidad
        costo_total = cantidad_vendida * info['costo']
        rentabilidad = ((total_ventas - costo_total) / total_ventas) * 100 if total_ventas > 0 else 0

        # Features para prediccion
        productos_data.append({
            'codigo_producto': codigo,
            'producto': info['nombre'],
            'categoria': info['categoria'],
            'precio_unitario': info['precio'],
            'costo_unitario': info['costo'],
            'cantidad_vendida': cantidad_vendida,
            'cantidad_devuelta': cantidad_devuelta,
            'total_ventas': round(total_ventas, 2),
            'total_devoluciones': round(cantidad_devuelta * info['precio'], 2),
            'tasa_devolucion': round(tasa_devolucion, 2),
            'rentabilidad_porcentual': round(rentabilidad, 2),
            'motivo_devolucion_principal': motivo_principal,
            'n_agencias_venta': df_prod['agencia'].nunique() if len(df_prod) > 0 else random.randint(3, 10),
            'ticket_promedio_producto': round(total_ventas / max(len(df_prod), 1), 2),
            'es_producto_nuevo': 1 if codigo.startswith('PRB') else 0,
            'dias_en_catalogo': 30 if codigo.startswith('PRB') else random.randint(180, 730)
        })

    df = pd.DataFrame(productos_data)
    print(f"    Productos procesados: {len(df)}")
    print(f"    Productos alto riesgo (>10% devolucion): {len(df[df['tasa_devolucion'] > 10])}")

    return df


def generar_kronos_silver(df_cestas):
    """
    Genera datos en formato Kronos Silver (agregado por agencia-producto-mes).
    """
    print(f"\n[4] Generando datos Kronos Silver...")

    # Agregar por agencia y producto
    agg = df_cestas.groupby(['agencia', 'codigo_producto', 'producto', 'categoria']).agg({
        'cantidad': 'sum',
        'total': 'sum',
        'transaccion_id': 'nunique'
    }).reset_index()

    agg.columns = ['centro_costo', 'codigo_producto', 'producto', 'categoria',
                   'cant_venta', 'total_venta', 'n_transacciones']

    # Generar devoluciones por fila
    agg['cant_devolucion'] = (agg['cant_venta'] * np.random.uniform(0.01, 0.08, len(agg))).astype(int)
    agg['total_devolucion'] = agg['total_venta'] * (agg['cant_devolucion'] / agg['cant_venta'].replace(0, 1))

    # Para productos PRB, aumentar devoluciones
    mask_prb = agg['codigo_producto'].str.startswith('PRB')
    agg.loc[mask_prb, 'cant_devolucion'] = (agg.loc[mask_prb, 'cant_venta'] * np.random.uniform(0.15, 0.25, mask_prb.sum())).astype(int)
    agg.loc[mask_prb, 'total_devolucion'] = agg.loc[mask_prb, 'total_venta'] * (agg.loc[mask_prb, 'cant_devolucion'] / agg.loc[mask_prb, 'cant_venta'].replace(0, 1))

    # Calcular netos y rentabilidad
    agg['cant_neto'] = agg['cant_venta'] - agg['cant_devolucion']
    agg['total_neto'] = agg['total_venta'] - agg['total_devolucion']
    agg['costo_venta'] = agg['total_neto'] * np.random.uniform(0.45, 0.55, len(agg))
    agg['rentabilidad'] = agg['total_neto'] - agg['costo_venta']
    agg['prc_rentabilidad'] = (agg['rentabilidad'] / agg['total_neto'].replace(0, 1)) * 100

    # Metadatos
    agg['mes'] = 'ENERO'
    agg['anio'] = '2026'
    agg['cant_nc'] = 0
    agg['total_nc'] = 0
    agg['codigo_alterno'] = agg['codigo_producto']
    agg['es_dato_calidado'] = True
    agg['flag_outlier'] = False
    agg['flag_valor_nulo'] = False
    agg['fecha_carga'] = datetime.now()
    agg['pipeline_id'] = 'dm_ficticios'
    agg['batch_id'] = 'batch_ficticios'

    print(f"    Registros generados: {len(agg)}")
    print(f"    Total ventas: ${agg['total_venta'].sum():,.2f}")

    return agg


def cargar_datos_postgresql(df_cestas, df_agencias, df_productos, df_kronos):
    """
    Carga los datos generados en PostgreSQL.
    """
    print(f"\n[5] Cargando datos en PostgreSQL...")

    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    try:
        # Crear esquemas si no existen
        cur.execute("CREATE SCHEMA IF NOT EXISTS silver;")
        cur.execute("CREATE SCHEMA IF NOT EXISTS gold;")
        cur.execute("CREATE SCHEMA IF NOT EXISTS dm;")

        # =================================================================
        # Tabla: dm.cestas_transacciones (para Apriori)
        # =================================================================
        cur.execute("DROP TABLE IF EXISTS dm.cestas_transacciones CASCADE;")
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

        # Insertar datos de cestas
        cestas_data = [tuple(x) for x in df_cestas[['transaccion_id', 'fecha', 'agencia',
            'codigo_producto', 'producto', 'categoria', 'cantidad', 'precio_unitario', 'total']].values]

        execute_values(cur, """
            INSERT INTO dm.cestas_transacciones
            (transaccion_id, fecha, agencia, codigo_producto, producto, categoria, cantidad, precio_unitario, total)
            VALUES %s
        """, cestas_data)

        print(f"    dm.cestas_transacciones: {len(cestas_data)} registros")

        # =================================================================
        # Tabla: silver.kronos_ventas_silver
        # =================================================================
        cur.execute("DROP TABLE IF EXISTS silver.kronos_ventas_silver CASCADE;")
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
                es_dato_calidado BOOLEAN,
                flag_outlier BOOLEAN,
                flag_valor_nulo BOOLEAN,
                fecha_carga TIMESTAMP,
                pipeline_id VARCHAR(50),
                batch_id VARCHAR(50)
            );
        """)

        # Insertar datos Kronos Silver
        kronos_cols = ['centro_costo', 'codigo_producto', 'codigo_alterno', 'producto', 'mes', 'anio',
                       'cant_venta', 'total_venta', 'cant_nc', 'total_nc', 'cant_devolucion',
                       'total_devolucion', 'cant_neto', 'total_neto', 'costo_venta', 'rentabilidad',
                       'prc_rentabilidad', 'es_dato_calidado', 'flag_outlier', 'flag_valor_nulo',
                       'fecha_carga', 'pipeline_id', 'batch_id']

        kronos_data = [tuple(x) for x in df_kronos[kronos_cols].values]

        execute_values(cur, f"""
            INSERT INTO silver.kronos_ventas_silver
            ({', '.join(kronos_cols)})
            VALUES %s
        """, kronos_data)

        print(f"    silver.kronos_ventas_silver: {len(kronos_data)} registros")

        # =================================================================
        # Tabla: gold.metricas_agencias (para Isolation Forest)
        # =================================================================
        cur.execute("DROP TABLE IF EXISTS gold.metricas_agencias CASCADE;")
        cur.execute("""
            CREATE TABLE gold.metricas_agencias (
                id SERIAL PRIMARY KEY,
                centro_costo VARCHAR(50),
                region VARCHAR(20),
                tamano VARCHAR(20),
                total_transacciones INTEGER,
                total_ventas NUMERIC(15,2),
                total_devoluciones NUMERIC(15,2),
                total_neto NUMERIC(15,2),
                ticket_promedio NUMERIC(10,2),
                tasa_devolucion NUMERIC(8,2),
                rentabilidad_porcentual NUMERIC(8,2),
                productos_distintos INTEGER,
                comportamiento_esperado VARCHAR(30)
            );
        """)

        agencias_data = [tuple(x) for x in df_agencias.values]

        execute_values(cur, """
            INSERT INTO gold.metricas_agencias
            (centro_costo, region, tamano, total_transacciones, total_ventas, total_devoluciones,
             total_neto, ticket_promedio, tasa_devolucion, rentabilidad_porcentual, productos_distintos,
             comportamiento_esperado)
            VALUES %s
        """, agencias_data)

        print(f"    gold.metricas_agencias: {len(agencias_data)} registros")

        # =================================================================
        # Tabla: gold.metricas_productos (para Random Forest)
        # =================================================================
        cur.execute("DROP TABLE IF EXISTS gold.metricas_productos CASCADE;")
        cur.execute("""
            CREATE TABLE gold.metricas_productos (
                id SERIAL PRIMARY KEY,
                codigo_producto VARCHAR(20),
                producto VARCHAR(100),
                categoria VARCHAR(50),
                precio_unitario NUMERIC(10,2),
                costo_unitario NUMERIC(10,2),
                cantidad_vendida INTEGER,
                cantidad_devuelta INTEGER,
                total_ventas NUMERIC(15,2),
                total_devoluciones NUMERIC(15,2),
                tasa_devolucion NUMERIC(8,2),
                rentabilidad_porcentual NUMERIC(8,2),
                motivo_devolucion_principal VARCHAR(50),
                n_agencias_venta INTEGER,
                ticket_promedio_producto NUMERIC(10,2),
                es_producto_nuevo INTEGER,
                dias_en_catalogo INTEGER
            );
        """)

        productos_cols = ['codigo_producto', 'producto', 'categoria', 'precio_unitario', 'costo_unitario',
                         'cantidad_vendida', 'cantidad_devuelta', 'total_ventas', 'total_devoluciones',
                         'tasa_devolucion', 'rentabilidad_porcentual', 'motivo_devolucion_principal',
                         'n_agencias_venta', 'ticket_promedio_producto', 'es_producto_nuevo', 'dias_en_catalogo']

        productos_data = [tuple(x) for x in df_productos[productos_cols].values]

        execute_values(cur, f"""
            INSERT INTO gold.metricas_productos
            ({', '.join(productos_cols)})
            VALUES %s
        """, productos_data)

        print(f"    gold.metricas_productos: {len(productos_data)} registros")

        conn.commit()
        print(f"\n[OK] Datos cargados exitosamente!")

    except Exception as e:
        conn.rollback()
        print(f"\n[ERROR] {e}")
        raise
    finally:
        cur.close()
        conn.close()


def main():
    print("="*70)
    print("GENERADOR DE DATOS FICTICIOS - CONDIMENSA")
    print("="*70)

    # Generar datos
    df_cestas = generar_cestas(n_transacciones=2000)
    df_agencias = generar_datos_agencias(df_cestas)
    df_productos = generar_datos_productos(df_cestas)
    df_kronos = generar_kronos_silver(df_cestas)

    # Cargar en PostgreSQL
    cargar_datos_postgresql(df_cestas, df_agencias, df_productos, df_kronos)

    print("\n" + "="*70)
    print("RESUMEN DE DATOS GENERADOS")
    print("="*70)
    print(f"\n1. CESTAS (para Apriori - Cross-selling):")
    print(f"   - {df_cestas['transaccion_id'].nunique()} transacciones")
    print(f"   - {len(df_cestas)} items totales")
    print(f"   - Patrones esperados: Salsa BBQ + Marinada, Mayonesa + Vinagre, etc.")

    print(f"\n2. AGENCIAS (para Isolation Forest - Anomalias):")
    print(f"   - {len(df_agencias)} agencias")
    anomalas = df_agencias[df_agencias['comportamiento_esperado'] != 'NORMAL']
    for _, row in anomalas.iterrows():
        print(f"   - {row['centro_costo']}: {row['comportamiento_esperado']} (tasa_dev={row['tasa_devolucion']}%, rent={row['rentabilidad_porcentual']}%)")

    print(f"\n3. PRODUCTOS (para Random Forest - Prediccion devoluciones):")
    print(f"   - {len(df_productos)} productos")
    alto_riesgo = df_productos[df_productos['tasa_devolucion'] > 10]
    for _, row in alto_riesgo.iterrows():
        print(f"   - {row['producto']}: {row['tasa_devolucion']:.1f}% devolucion ({row['motivo_devolucion_principal']})")

    print("\n" + "="*70)
    print("TABLAS CREADAS EN POSTGRESQL")
    print("="*70)
    print("  - dm.cestas_transacciones (para Apriori)")
    print("  - silver.kronos_ventas_silver (datos integrados)")
    print("  - gold.metricas_agencias (para Isolation Forest)")
    print("  - gold.metricas_productos (para Random Forest)")
    print("="*70)


if __name__ == "__main__":
    main()
