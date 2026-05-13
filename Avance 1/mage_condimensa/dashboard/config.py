"""
Configuracion del Dashboard CONDIMENSA
"""
import os

# Configuracion de base de datos
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'postgres_local'),
    'port': os.getenv('DB_PORT', 5432),
    'dbname': os.getenv('DB_NAME', 'condimensa_analytics'),
    'user': os.getenv('DB_USER', 'condimensa'),
    'password': os.getenv('DB_PASSWORD', 'change_me')
}

# Configuracion de la aplicacion
APP_CONFIG = {
    'title': 'CONDIMENSA - Data Mining Dashboard',
    'version': '3.1',
    'cache_ttl': 300  # segundos
}

# Colores corporativos
COLORS = {
    'primary': '#1e3a5f',
    'secondary': '#2d5a87',
    'accent': '#f39c12',
    'success': '#27ae60',
    'warning': '#f39c12',
    'danger': '#e74c3c',
    'light': '#f8f9fa',
    'dark': '#2c3e50'
}

# Estilos CSS
CSS_STYLES = """
<style>
    .main {
        background-color: #f8f9fa;
    }
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1e3a5f 0%, #2d5a87 100%);
    }
    [data-testid="stSidebar"] * {
        color: white !important;
    }
    [data-testid="metric-container"] {
        background-color: white;
        border-radius: 8px;
        padding: 15px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.08);
        border-left: 4px solid #1e3a5f;
    }
    h1 {
        color: #1e3a5f;
        border-bottom: 3px solid #f39c12;
        padding-bottom: 10px;
        font-weight: 600;
    }
    h2, h3 {
        color: #2d5a87;
        font-weight: 500;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: white;
        border-radius: 4px;
        padding: 10px 20px;
    }
    div[data-testid="stExpander"] {
        background-color: white;
        border-radius: 8px;
        border: 1px solid #e0e0e0;
    }
</style>
"""

# Nombres de paginas (sin emojis)
PAGINAS = [
    "Resumen Ejecutivo",
    "KPIs Comerciales",
    "Alertas Tempranas",
    "Combinaciones Ineficientes",
    "Plan vs Real Produccion",
    "Tendencias y Evolucion",
    "Clustering y Segmentacion"
]
