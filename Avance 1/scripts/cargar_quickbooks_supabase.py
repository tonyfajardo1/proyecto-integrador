"""
Script para cargar datos de QuickBooks (MySQL dump) a Supabase (PostgreSQL)
"""
import pandas as pd
import re
from sqlalchemy import create_engine, text
import os

# =============================================================================
# CONFIGURACIÓN - Reemplaza con tus credenciales de Supabase
# =============================================================================
SUPABASE_CONFIG = {
    'host': 'db.your-kronos-project-ref.supabase.co',
    'port': 5432,
    'database': 'postgres',
    'user': 'postgres',
    'password': 'TU_PASSWORD_AQUI'  # <-- Reemplaza con tu contraseña
}

# Ruta a los archivos SQL
SQL_DUMP_PATH = '/Users/ulisesfajardo/Documents/Proyecto Integrador/Avance 1/Quickbooks/Dump20260217'

# =============================================================================
# FUNCIONES
# =============================================================================

def get_connection_string():
    """Genera la cadena de conexión para PostgreSQL"""
    return f"postgresql://{SUPABASE_CONFIG['user']}:{SUPABASE_CONFIG['password']}@{SUPABASE_CONFIG['host']}:{SUPABASE_CONFIG['port']}/{SUPABASE_CONFIG['database']}"

def parse_mysql_insert(sql_content, table_name):
    """
    Parsea un INSERT de MySQL y extrae los datos como lista de tuplas
    """
    # Buscar la estructura CREATE TABLE para obtener columnas
    create_match = re.search(r'CREATE TABLE `' + table_name + r'` \((.*?)\) ENGINE', sql_content, re.DOTALL)

    columns = []
    if create_match:
        create_body = create_match.group(1)
        # Extraer nombres de columnas
        col_matches = re.findall(r'`(\w+)`\s+(?:int|varchar|text|date|tinyint|decimal|float|double)', create_body, re.IGNORECASE)
        columns = col_matches

    # Buscar INSERT INTO
    insert_match = re.search(r'INSERT INTO `' + table_name + r'` VALUES (.*?);', sql_content, re.DOTALL)

    if not insert_match:
        return None, None

    values_str = insert_match.group(1)

    # Parsear los valores - esto es simplificado, puede necesitar ajustes
    rows = []
    # Buscar cada tupla de valores
    pattern = r'\(([^)]+)\)'
    matches = re.findall(pattern, values_str)

    for match in matches:
        # Parsear valores individuales
        values = []
        in_string = False
        current_val = ''
        i = 0
        while i < len(match):
            char = match[i]
            if char == "'" and (i == 0 or match[i-1] != '\\'):
                in_string = not in_string
                current_val += char
            elif char == ',' and not in_string:
                values.append(parse_value(current_val.strip()))
                current_val = ''
            else:
                current_val += char
            i += 1
        if current_val:
            values.append(parse_value(current_val.strip()))
        rows.append(values)

    return columns, rows

def parse_value(val):
    """Convierte un valor de MySQL a Python"""
    if val == 'NULL':
        return None
    if val.startswith("'") and val.endswith("'"):
        return val[1:-1].replace("\\'", "'").replace("\\r\\n", "\n").replace("\\n", "\n")
    try:
        if '.' in val:
            return float(val)
        return int(val)
    except:
        return val

def mysql_to_postgresql_schema(mysql_sql):
    """Convierte schema de MySQL a PostgreSQL"""
    pg_sql = mysql_sql

    # Remover backticks
    pg_sql = pg_sql.replace('`', '"')

    # Cambiar tipos de datos
    pg_sql = re.sub(r'int\(\d+\)', 'INTEGER', pg_sql, flags=re.IGNORECASE)
    pg_sql = re.sub(r'tinyint\(\d+\)', 'SMALLINT', pg_sql, flags=re.IGNORECASE)
    pg_sql = re.sub(r'bigint\(\d+\)', 'BIGINT', pg_sql, flags=re.IGNORECASE)
    pg_sql = re.sub(r'varchar\((\d+)\)', r'VARCHAR(\1)', pg_sql, flags=re.IGNORECASE)
    pg_sql = re.sub(r'double', 'DOUBLE PRECISION', pg_sql, flags=re.IGNORECASE)
    pg_sql = re.sub(r'datetime', 'TIMESTAMP', pg_sql, flags=re.IGNORECASE)

    # Remover opciones específicas de MySQL
    pg_sql = re.sub(r'ENGINE=\w+', '', pg_sql)
    pg_sql = re.sub(r'DEFAULT CHARSET=\w+', '', pg_sql)
    pg_sql = re.sub(r'COLLATE=\w+', '', pg_sql)
    pg_sql = re.sub(r'AUTO_INCREMENT=\d+', '', pg_sql)
    pg_sql = re.sub(r'AUTO_INCREMENT', 'SERIAL', pg_sql)
    pg_sql = re.sub(r'UNSIGNED', '', pg_sql)

    # Remover comentarios de MySQL
    pg_sql = re.sub(r'/\*!.*?\*/', '', pg_sql, flags=re.DOTALL)
    pg_sql = re.sub(r'--.*$', '', pg_sql, flags=re.MULTILINE)

    return pg_sql

def load_sql_file_to_dataframe(filepath):
    """
    Lee un archivo SQL de MySQL y lo convierte a DataFrame
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Obtener nombre de tabla
    table_match = re.search(r'CREATE TABLE `(\w+)`', content)
    if not table_match:
        print(f"No se encontró CREATE TABLE en {filepath}")
        return None, None

    table_name = table_match.group(1)

    # Parsear columnas y datos
    columns, rows = parse_mysql_insert(content, table_name)

    if not columns or not rows:
        print(f"No se pudieron extraer datos de {filepath}")
        return None, None

    # Crear DataFrame
    df = pd.DataFrame(rows, columns=columns)

    return table_name, df

def load_to_supabase(df, table_name, engine, schema='quickbooks'):
    """Carga un DataFrame a Supabase"""
    try:
        # Crear schema si no existe
        with engine.connect() as conn:
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
            conn.commit()

        # Cargar datos
        df.to_sql(
            table_name,
            engine,
            schema=schema,
            if_exists='replace',
            index=False
        )
        print(f"✓ Tabla {schema}.{table_name} cargada: {len(df)} registros")
        return True
    except Exception as e:
        print(f"✗ Error cargando {table_name}: {e}")
        return False

# =============================================================================
# EJECUCIÓN PRINCIPAL
# =============================================================================

def main():
    print("=" * 60)
    print("CARGANDO DATOS DE QUICKBOOKS A SUPABASE")
    print("=" * 60)

    # Verificar credenciales
    if SUPABASE_CONFIG['password'] == 'TU_PASSWORD_AQUI':
        print("\n⚠️  ERROR: Debes configurar tu contraseña de Supabase")
        print("   Edita este archivo y reemplaza 'TU_PASSWORD_AQUI' con tu contraseña real")
        return

    # Crear conexión
    print("\n📡 Conectando a Supabase...")
    try:
        engine = create_engine(get_connection_string())
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("✓ Conexión exitosa!")
    except Exception as e:
        print(f"✗ Error de conexión: {e}")
        return

    # Archivos a cargar
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
        'odin_testigo.sql',
        'odin_vagos.sql'
    ]

    print(f"\n📁 Procesando {len(sql_files)} archivos...")

    success_count = 0
    for sql_file in sql_files:
        filepath = os.path.join(SQL_DUMP_PATH, sql_file)

        if not os.path.exists(filepath):
            print(f"⚠️  Archivo no encontrado: {sql_file}")
            continue

        print(f"\n📄 Procesando: {sql_file}")
        table_name, df = load_sql_file_to_dataframe(filepath)

        if df is not None:
            if load_to_supabase(df, table_name, engine, schema='quickbooks'):
                success_count += 1

    print("\n" + "=" * 60)
    print(f"RESUMEN: {success_count}/{len(sql_files)} tablas cargadas exitosamente")
    print("=" * 60)

if __name__ == "__main__":
    main()
