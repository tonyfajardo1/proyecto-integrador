"""
Script SIMPLE para cargar datos de QuickBooks a Supabase
Usa regex para extraer datos de los dumps MySQL
"""
import pandas as pd
import re
from sqlalchemy import create_engine, text
import os
from io import StringIO

# =============================================================================
# CONFIGURACIÓN
# =============================================================================

# PROYECTO QUICKBOOKS en Supabase (Transaction Pooler - IPv4 compatible)
QUICKBOOKS_DB = {
    'host': 'your-quickbooks-host.supabase.com',
    'port': 6543,
    'database': 'postgres',
    'user': 'postgres.your-quickbooks-project-ref',
    'password': 'REDACTED_SECRET'
}

# PROYECTO KRONOS en Supabase (Transaction Pooler - IPv4 compatible)
KRONOS_DB = {
    'host': 'your-kronos-host.supabase.com',
    'port': 6543,
    'database': 'postgres',
    'user': 'postgres.your-kronos-project-ref',
    'password': 'REDACTED_SECRET'
}

# Rutas
QUICKBOOKS_PATH = '/Users/ulisesfajardo/Documents/Proyecto Integrador/Avance 1/Quickbooks/Dump20260217'
KRONOS_PATH = '/Users/ulisesfajardo/Documents/Proyecto Integrador/Avance 1/Comercial Kronos'

# =============================================================================
# FUNCIONES AUXILIARES
# =============================================================================

def get_engine(config):
    """Crea conexión a la base de datos"""
    conn_str = f"postgresql://{config['user']}:{config['password']}@{config['host']}:{config['port']}/{config['database']}"
    return create_engine(conn_str)

def extract_mysql_data(sql_file_path):
    """
    Extrae datos de un archivo SQL de MySQL dump
    Retorna: (nombre_tabla, columnas, datos)
    """
    with open(sql_file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    # Obtener nombre de tabla
    table_match = re.search(r'CREATE TABLE `(\w+)`', content)
    if not table_match:
        return None, None, None
    table_name = table_match.group(1)

    # Obtener columnas del CREATE TABLE
    create_match = re.search(r'CREATE TABLE `\w+` \((.*?)\)\s*(?:ENGINE|;)', content, re.DOTALL)
    if not create_match:
        return table_name, None, None

    create_body = create_match.group(1)

    # Extraer nombres de columnas (ignorar PRIMARY KEY, etc.)
    columns = []
    for line in create_body.split('\n'):
        line = line.strip()
        if line.startswith('`'):
            col_match = re.match(r'`(\w+)`', line)
            if col_match:
                columns.append(col_match.group(1))

    # Extraer INSERT VALUES
    insert_match = re.search(r'INSERT INTO `\w+` VALUES\s*(.*?);(?:\s*$|\s*UNLOCK)', content, re.DOTALL)
    if not insert_match:
        return table_name, columns, []

    values_str = insert_match.group(1)

    # Parsear valores - método simple
    rows = []
    current_row = []
    in_string = False
    current_value = ''
    depth = 0

    i = 0
    while i < len(values_str):
        char = values_str[i]

        if char == '(' and not in_string:
            depth += 1
            if depth == 1:
                current_row = []
                current_value = ''
        elif char == ')' and not in_string:
            depth -= 1
            if depth == 0:
                # Agregar último valor
                if current_value or current_row:
                    current_row.append(parse_mysql_value(current_value.strip()))
                if current_row:
                    rows.append(current_row)
                current_value = ''
        elif char == "'" and (i == 0 or values_str[i-1] != '\\'):
            in_string = not in_string
            current_value += char
        elif char == ',' and not in_string and depth == 1:
            current_row.append(parse_mysql_value(current_value.strip()))
            current_value = ''
        elif depth >= 1:
            current_value += char

        i += 1

    return table_name, columns, rows

def parse_mysql_value(val):
    """Convierte valor MySQL a Python"""
    if not val or val.upper() == 'NULL':
        return None
    if val.startswith("'") and val.endswith("'"):
        # Quitar comillas y decodificar escapes
        return val[1:-1].replace("\\'", "'").replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\\\", "\\")
    try:
        if '.' in val:
            return float(val)
        return int(val)
    except ValueError:
        return val

def load_quickbooks():
    """Carga todos los archivos de QuickBooks"""
    print("\n" + "="*60)
    print("CARGANDO QUICKBOOKS A SUPABASE")
    print("="*60)

    if QUICKBOOKS_DB['password'] == 'TU_PASSWORD_QUICKBOOKS':
        print("⚠️  Configura la contraseña de QuickBooks en el script")
        return

    try:
        engine = get_engine(QUICKBOOKS_DB)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("✓ Conexión a Supabase (QuickBooks) exitosa")
    except Exception as e:
        print(f"✗ Error de conexión: {e}")
        return

    # Crear schema
    with engine.connect() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS quickbooks"))
        conn.commit()

    # Archivos SQL
    sql_files = [
        'odin_sales.sql',
        'odin_sales_lineas.sql',
        'odin_compras.sql',
        'odin_compras_lineas.sql',
        'odin_produccion.sql',
        'odin_produccion_lineas.sql',
        'odin_items.sql',
        'odin_invoices.sql',
        'odin_invoices_lineas.sql',
    ]

    for sql_file in sql_files:
        filepath = os.path.join(QUICKBOOKS_PATH, sql_file)
        if not os.path.exists(filepath):
            print(f"⚠️  No encontrado: {sql_file}")
            continue

        print(f"\n📄 Procesando: {sql_file}")

        try:
            table_name, columns, rows = extract_mysql_data(filepath)

            if not columns or not rows:
                print(f"   ⚠️  Sin datos o columnas")
                continue

            # Asegurar que todas las filas tengan el mismo número de columnas
            rows = [row[:len(columns)] for row in rows if len(row) >= len(columns)]

            df = pd.DataFrame(rows, columns=columns)
            print(f"   📊 {len(df)} registros, {len(columns)} columnas")

            # Cargar a Supabase
            df.to_sql(
                table_name.replace('odin_', ''),  # Quitar prefijo odin_
                engine,
                schema='quickbooks',
                if_exists='replace',
                index=False,
                method='multi',
                chunksize=500
            )
            print(f"   ✓ Tabla quickbooks.{table_name.replace('odin_', '')} creada")

        except Exception as e:
            print(f"   ✗ Error: {e}")

def load_kronos():
    """Carga archivos Excel de Kronos"""
    print("\n" + "="*60)
    print("CARGANDO KRONOS A SUPABASE")
    print("="*60)

    if KRONOS_DB['host'] == 'TU_HOST_KRONOS':
        print("⚠️  Configura el host de Kronos en el script")
        print("   Primero crea un segundo proyecto en Supabase para Kronos")
        return

    if KRONOS_DB['password'] == 'TU_PASSWORD_KRONOS':
        print("⚠️  Configura la contraseña de Kronos en el script")
        return

    try:
        engine = get_engine(KRONOS_DB)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("✓ Conexión a Supabase (Kronos) exitosa")
    except Exception as e:
        print(f"✗ Error de conexión: {e}")
        return

    # Crear schema
    with engine.connect() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS kronos"))
        conn.commit()

    # Archivos Excel
    excel_files = [
        'Ventas_general.xlsx',
        'Ventas_general (3).xlsx',
        'Ventas_general (4).xlsx'
    ]

    for excel_file in excel_files:
        filepath = os.path.join(KRONOS_PATH, excel_file)
        if not os.path.exists(filepath):
            print(f"⚠️  No encontrado: {excel_file}")
            continue

        print(f"\n📄 Procesando: {excel_file}")

        try:
            # Leer Excel
            df = pd.read_excel(filepath)

            # Limpiar nombres de columnas
            df.columns = [
                str(col).lower()
                .replace(' ', '_')
                .replace('.', '')
                .replace('(', '')
                .replace(')', '')
                .replace('/', '_')
                for col in df.columns
            ]

            print(f"   📊 {len(df)} registros, {len(df.columns)} columnas")

            # Nombre de tabla
            table_name = excel_file.replace('.xlsx', '').replace(' ', '_').replace('(', '').replace(')', '').lower()

            # Cargar a Supabase
            df.to_sql(
                table_name,
                engine,
                schema='kronos',
                if_exists='replace',
                index=False
            )
            print(f"   ✓ Tabla kronos.{table_name} creada")

        except Exception as e:
            print(f"   ✗ Error: {e}")

# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════╗
║     CARGA DE DATOS A SUPABASE - CONDIMENSA                   ║
╠══════════════════════════════════════════════════════════════╣
║  1. QuickBooks → Proyecto 1 de Supabase (schema: quickbooks) ║
║  2. Kronos     → Proyecto 2 de Supabase (schema: kronos)     ║
╚══════════════════════════════════════════════════════════════╝
    """)

    print("¿Qué deseas cargar?")
    print("  1. Solo QuickBooks")
    print("  2. Solo Kronos")
    print("  3. Ambos")

    opcion = input("\nOpción [1/2/3]: ").strip()

    if opcion == '1':
        load_quickbooks()
    elif opcion == '2':
        load_kronos()
    elif opcion == '3':
        load_quickbooks()
        load_kronos()
    else:
        print("Opción no válida")

    print("\n✅ Proceso completado!")
    print("\nPróximos pasos:")
    print("  1. Ve a supabase.com → Tu proyecto")
    print("  2. Click en 'Table Editor'")
    print("  3. Selecciona el schema 'quickbooks' o 'kronos'")
    print("  4. Verifica que las tablas estén creadas")
