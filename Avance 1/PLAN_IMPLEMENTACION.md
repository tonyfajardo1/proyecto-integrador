# PLAN DE IMPLEMENTACIÓN - Data Mining CONDIMENSA

## FASE 1: Configuración Local (Mientras esperas APIs)

### 1.1 Levantar PostgreSQL local con Docker

```bash
# docker-compose.yaml
version: '3.8'
services:
  postgres:
    image: postgres:15
    container_name: condimensa_db
    environment:
      POSTGRES_USER: condimensa
      POSTGRES_PASSWORD: REDACTED_LOCAL_DB_PASSWORD
      POSTGRES_DB: condimensa_dwh
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

### 1.2 Estructura de Schemas

```sql
-- Crear schemas para separar fuentes
CREATE SCHEMA raw_quickbooks;    -- Datos crudos de QuickBooks
CREATE SCHEMA raw_kronos;        -- Datos crudos de Kronos
CREATE SCHEMA staging;           -- Datos limpios/transformados
CREATE SCHEMA analytics;         -- Tablas para Data Mining
```

### 1.3 Cargar dumps SQL

```bash
# Cargar datos de QuickBooks
psql -U condimensa -d condimensa_dwh -f odin_sales.sql
psql -U condimensa -d condimensa_dwh -f odin_sales_lineas.sql
psql -U condimensa -d condimensa_dwh -f odin_produccion.sql
psql -U condimensa -d condimensa_dwh -f odin_produccion_lineas.sql
psql -U condimensa -d condimensa_dwh -f odin_items.sql
psql -U condimensa -d condimensa_dwh -f odin_compras.sql
```

---

## FASE 2: Pipelines en Mage AI

### Pipeline 1: Ingesta QuickBooks → PostgreSQL
```
[SQL Files] → [Data Loader] → [Transformer] → [PostgreSQL]
```

### Pipeline 2: Ingesta Kronos Excel → PostgreSQL
```
[Excel Files] → [Data Loader] → [Transformer] → [PostgreSQL]
```

### Pipeline 3: Transformación para Analytics
```
[raw_quickbooks] + [raw_kronos] → [staging] → [analytics]
```

---

## FASE 3: Data Mining (Responder preguntas del profesor)

### PREGUNTA 1: Patrones de producción (desviaciones plan vs real)

**Datos necesarios:**
- `odin_produccion` (plan)
- `odin_produccion_lineas` (real)

**Técnicas:**
- Regresión para predecir desviación
- Árboles de decisión para identificar factores
- Clustering de órdenes problemáticas

**Métricas:**
- R², MAE, RMSE para regresión
- Accuracy, F1 para clasificación

**Código ejemplo:**
```python
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split

# Clasificar si una orden cumplirá el plan
X = df[['producto_id', 'cantidad_plan', 'dia_semana', 'mes']]
y = df['cumple_plan']  # 1 si real >= 95% plan, 0 si no

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)
model = RandomForestClassifier(n_estimators=100)
model.fit(X_train, y_train)

# Feature importance
importances = pd.DataFrame({
    'feature': X.columns,
    'importance': model.feature_importances_
}).sort_values('importance', ascending=False)
```

---

### PREGUNTA 2: Combinaciones producto-cliente-periodo con ineficiencias

**Datos necesarios:**
- `odin_sales` + `odin_sales_lineas`
- Ventas_general.xlsx (Kronos)

**Técnicas:**
- Reglas de Asociación (Apriori)
- Análisis de cohortes
- Segmentación RFM

**Código ejemplo:**
```python
from mlxtend.frequent_patterns import apriori, association_rules

# Preparar datos para Market Basket Analysis
basket = df.groupby(['cliente', 'producto'])['cantidad'].sum().unstack().fillna(0)
basket = basket.applymap(lambda x: 1 if x > 0 else 0)

# Encontrar itemsets frecuentes
frequent_items = apriori(basket, min_support=0.05, use_colnames=True)

# Generar reglas
rules = association_rules(frequent_items, metric="lift", min_threshold=1.2)
```

---

### PREGUNTA 3: Detección de comportamientos atípicos

**Datos necesarios:**
- Ventas por agencia/vendedor
- Descuentos, devoluciones, notas de crédito

**Técnicas:**
- Isolation Forest
- Z-Score analysis
- DBSCAN para outliers

**Código ejemplo:**
```python
from sklearn.ensemble import IsolationForest

# Detectar anomalías en comportamiento de agencias
X = df_agencias[['ratio_descuentos', 'ratio_devoluciones', 'margen_promedio']]

model = IsolationForest(contamination=0.1, random_state=42)
df_agencias['anomaly_score'] = model.fit_predict(X)

# -1 = anomalía, 1 = normal
anomalias = df_agencias[df_agencias['anomaly_score'] == -1]
```

---

## FASE 4: Dashboard de Hallazgos

### Streamlit App
```python
import streamlit as st
import pandas as pd
import plotly.express as px

st.title("Data Mining CONDIMENSA - Hallazgos")

# Pestaña 1: Predicción de Producción
st.header("1. Predicción de Cumplimiento de Producción")
# Mostrar modelo, métricas, feature importance

# Pestaña 2: Patrones de Ineficiencia
st.header("2. Combinaciones Producto-Cliente Ineficientes")
# Mostrar reglas de asociación, heatmaps

# Pestaña 3: Anomalías
st.header("3. Detección de Anomalías")
# Mostrar alertas, scores de anomalía
```

---

## CRONOGRAMA SUGERIDO

| Semana | Actividad |
|--------|-----------|
| 1 | Configurar PostgreSQL + Cargar datos locales |
| 2 | Crear pipelines de ingesta en Mage AI |
| 3 | EDA + Preparación de features |
| 4 | Implementar modelo de predicción producción |
| 5 | Implementar análisis de asociación |
| 6 | Implementar detección de anomalías |
| 7 | Crear dashboard de hallazgos |
| 8 | Documentación + Presentación |

---

## ARCHIVOS DE DATOS DISPONIBLES

### QuickBooks (en /Avance 1/Quickbooks/Dump20260217/)
- odin_sales.sql
- odin_sales_lineas.sql
- odin_compras.sql
- odin_compras_lineas.sql
- odin_produccion.sql
- odin_produccion_lineas.sql
- odin_items.sql
- odin_invoices.sql
- odin_invoices_lineas.sql

### Kronos (en /Avance 1/Comercial Kronos/)
- Ventas_general.xlsx
- Ventas_general (3).xlsx
- Ventas_general (4).xlsx

---

## PRÓXIMOS PASOS INMEDIATOS

1. [ ] Levantar PostgreSQL con Docker
2. [ ] Convertir dumps MySQL a PostgreSQL
3. [ ] Cargar datos a PostgreSQL local
4. [ ] Crear proyecto Mage AI
5. [ ] Implementar primer pipeline de prueba
