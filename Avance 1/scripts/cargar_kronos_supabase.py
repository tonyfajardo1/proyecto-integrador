"""
Script para cargar datos de Kronos (Excel) a Supabase (PostgreSQL)
"""
import pandas as pd
from sqlalchemy import create_engine, text
import os

# =============================================================================
# CONFIGURACIÓN - Reemplaza con tus credenciales de Supabase (PROYECTO KRONOS)
# =============================================================================
SUPABASE_CONFIG = {
    'host': 'TU_HOST_KRONOS_AQUI',  # <-- Reemplaza con el host del proyecto Kronos
    'port': 5432,
    'database': 'postgres',
    'user': 'postgres',
    'password': 'TU_PASSWORD_AQUI'  # <-- Reemplaza con tu contraseña
}

# Ruta a los archivos Excel de Kronos
KRONOS_PATH = '/Users/ulisesfajardo/Documents/Proyecto Integrador/Avance 1/Comercial Kronos'

# =============================================================================
# FUNCIONES
# =============================================================================

def get_connection_string():
    """Genera la cadena de conexión para PostgreSQL"""
    return f"postgresql://{SUPABASE_CONFIG['user']}:{SUPABASE_CONFIG['password']}@{SUPABASE_CONFIG['host']}:{SUPABASE_CONFIG['port']}/{SUPABASE_CONFIG['database']}"

def clean_column_names(df):
    """Limpia los nombres de columnas para PostgreSQL"""
    df.columns = [
        col.lower()
        .replace(' ', '_')
        .replace('.', '')
        .replace('(', '')
        .replace(')', '')
        .replace('/', '_')
        .replace('-', '_')
        .replace('á', 'a')
        .replace('é', 'e')
        .replace('í', 'i')
        .replace('ó', 'o')
        .replace('ú', 'u')
        .replace('ñ', 'n')
        for col in df.columns
    ]
    return df

def load_excel_file(filepath):
    """Lee un archivo Excel y retorna DataFrame"""
    try:
        # Intentar leer todas las hojas
        excel_file = pd.ExcelFile(filepath)
        sheets = excel_file.sheet_names

        dfs = {}
        for sheet in sheets:
            df = pd.read_excel(filepath, sheet_name=sheet)
            if not df.empty:
                df = clean_column_names(df)
                dfs[sheet.lower().replace(' ', '_')] = df
                print(f"   Hoja '{sheet}': {len(df)} registros, {len(df.columns)} columnas")

        return dfs
    except Exception as e:
        print(f"Error leyendo {filepath}: {e}")
        return None

def load_to_supabase(df, table_name, engine, schema='kronos'):
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
    print("CARGANDO DATOS DE KRONOS A SUPABASE")
    print("=" * 60)

    # Verificar credenciales
    if SUPABASE_CONFIG['password'] == 'TU_PASSWORD_AQUI':
        print("\n⚠️  ERROR: Debes configurar tu contraseña de Supabase")
        print("   Edita este archivo y reemplaza las credenciales")
        return

    if SUPABASE_CONFIG['host'] == 'TU_HOST_KRONOS_AQUI':
        print("\n⚠️  ERROR: Debes configurar el host de Supabase")
        print("   Edita este archivo y reemplaza 'TU_HOST_KRONOS_AQUI'")
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

    # Archivos Excel a cargar
    excel_files = [
        'Ventas_general.xlsx',
        'Ventas_general (3).xlsx',
        'Ventas_general (4).xlsx'
    ]

    print(f"\n📁 Procesando {len(excel_files)} archivos Excel...")

    success_count = 0
    for excel_file in excel_files:
        filepath = os.path.join(KRONOS_PATH, excel_file)

        if not os.path.exists(filepath):
            print(f"⚠️  Archivo no encontrado: {excel_file}")
            continue

        print(f"\n📄 Procesando: {excel_file}")
        dfs = load_excel_file(filepath)

        if dfs:
            for sheet_name, df in dfs.items():
                # Crear nombre de tabla único
                base_name = excel_file.replace('.xlsx', '').replace(' ', '_').replace('(', '').replace(')', '').lower()
                table_name = f"{base_name}_{sheet_name}" if len(dfs) > 1 else base_name

                if load_to_supabase(df, table_name, engine, schema='kronos'):
                    success_count += 1

    print("\n" + "=" * 60)
    print(f"RESUMEN: {success_count} tablas cargadas exitosamente")
    print("=" * 60)

    # Mostrar tablas creadas
    print("\n📊 Para ver las tablas en Supabase:")
    print("   1. Ve a tu proyecto en supabase.com")
    print("   2. Click en 'Table Editor' en el menú izquierdo")
    print("   3. Selecciona el schema 'kronos' en el dropdown")

if __name__ == "__main__":
    main()
