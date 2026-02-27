# CONDIMENSA - Proyecto Data Mining con Mage AI

## Arquitectura

```
┌─────────────────────────────────────────────────────────────────┐
│                        FUENTES DE DATOS                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│   ┌─────────────────┐           ┌─────────────────┐              │
│   │   QUICKBOOKS    │           │     KRONOS      │              │
│   │   (Supabase)    │           │   (Supabase)    │              │
│   │                 │           │                 │              │
│   │ - sales         │           │ - ventas_       │              │
│   │ - produccion    │           │   general       │              │
│   │ - compras       │           │                 │              │
│   │ - items         │           │                 │              │
│   └────────┬────────┘           └────────┬────────┘              │
│            │                             │                        │
│            └──────────┬──────────────────┘                        │
│                       ▼                                           │
│            ┌─────────────────────┐                               │
│            │      MAGE AI        │                               │
│            │   (Docker Local)    │                               │
│            │                     │                               │
│            │  - Data Loaders     │                               │
│            │  - Transformers     │                               │
│            │  - Data Mining      │                               │
│            └──────────┬──────────┘                               │
│                       ▼                                           │
│            ┌─────────────────────┐                               │
│            │   PostgreSQL Local  │                               │
│            │  (Data Warehouse)   │                               │
│            │  - Resultados DM    │                               │
│            │  - Modelos          │                               │
│            └─────────────────────┘                               │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

## Inicio Rápido

### 1. Iniciar los servicios

```bash
cd mage_condimensa
docker-compose up -d
```

### 2. Acceder a Mage AI

Abre tu navegador en: **http://localhost:6789**

### 3. Verificar conexiones

En Mage AI:
1. Ve a **Pipelines** → **New Pipeline**
2. Agrega un **Data Loader** → **SQL**
3. Selecciona el profile **quickbooks** o **kronos**
4. Ejecuta una consulta de prueba

## Conexiones Configuradas

### QuickBooks (Supabase)
- **Profile:** `quickbooks`
- **Schema:** `quickbooks`
- **Tablas:** sales, sales_lineas, produccion, produccion_lineas, compras, compras_lineas, items

### Kronos (Supabase)
- **Profile:** `kronos`
- **Schema:** `kronos`
- **Tablas:** ventas_general, ventas_general_3, ventas_general_4

### Data Warehouse Local
- **Profile:** `local_dwh`
- **Host:** postgres_local:5432
- **Database:** condimensa_analytics

## Estructura del Proyecto

```
mage_condimensa/
├── docker-compose.yml          # Configuración de Docker
├── README.md                   # Este archivo
└── condimensa_project/
    ├── io_config.yaml          # Conexiones a bases de datos
    ├── metadata.yaml           # Metadata del proyecto
    ├── requirements.txt        # Dependencias Python
    ├── data_loaders/           # Extractores de datos
    │   ├── load_quickbooks_sales.py
    │   ├── load_quickbooks_produccion.py
    │   └── load_kronos_ventas.py
    ├── transformers/           # Transformaciones
    │   └── analisis_produccion.py
    ├── data_exporters/         # Exportadores
    ├── pipelines/              # Pipelines definidos
    └── custom/                 # Código personalizado
```

## Preguntas de Data Mining a Responder

### 1. Patrones de Producción (Desviaciones plan vs real)
- **Datos:** quickbooks.produccion, quickbooks.produccion_lineas
- **Técnicas:** Clasificación, Regresión, Árboles de Decisión

### 2. Combinaciones Producto-Cliente-Periodo con Ineficiencias
- **Datos:** quickbooks.sales, kronos.ventas_general_4
- **Técnicas:** Reglas de Asociación (Apriori), Segmentación RFM

### 3. Detección de Comportamientos Atípicos
- **Datos:** quickbooks.sales por cliente/vendedor
- **Técnicas:** Isolation Forest, Z-Score, DBSCAN

## Comandos Útiles

```bash
# Iniciar servicios
docker-compose up -d

# Ver logs de Mage
docker-compose logs -f mage

# Detener servicios
docker-compose down

# Reiniciar Mage
docker-compose restart mage

# Acceder al contenedor de Mage
docker exec -it mage_condimensa bash

# Acceder a PostgreSQL local
docker exec -it condimensa_dwh psql -U condimensa -d condimensa_analytics
```

## Próximos Pasos

1. [ ] Crear pipeline de ingesta completa
2. [ ] Implementar EDA (Análisis Exploratorio)
3. [ ] Crear modelos de Data Mining
4. [ ] Generar dashboard de hallazgos
