# NUEVO ENFOQUE: Data Mining para CONDIMENSA
## Preguntas de Negocio Especificas y Tecnicas de Mineria de Datos

---

# PREGUNTAS DE NEGOCIO IDENTIFICADAS

| # | Pregunta de Negocio | Area | Impacto |
|---|---------------------|------|---------|
| 1 | Por que existen muchas devoluciones? | Comercial | Reducir perdidas por devoluciones |
| 2 | Que jefes de agencia presentan anomalias financieras? | Control Interno | Deteccion de fraude |
| 3 | Como optimizar las rutas de vendedores? | Logistica/Ventas | Reducir costos, aumentar cobertura |
| 4 | Como reducir los desperdicios en produccion? | Produccion | Reducir costos, mejorar eficiencia |
| 5 | Como optimizar las ordenes de produccion? | Produccion | Mejor planificacion, cumplimiento |

---

# PREGUNTA 1: ANALISIS DE DEVOLUCIONES

## Pregunta
> **"Por que existen muchas devoluciones y como se pueden reducir?"**

## Objetivo de Data Mining
Identificar los factores (producto, cliente, vendedor, ruta, temporada, condiciones) que predicen una devolucion para tomar acciones preventivas.

## Tecnicas de Data Mining

### 1.1 Clasificacion - Prediccion de Devoluciones
```
Modelo: Random Forest / XGBoost
Target: devolucion (SI/NO)
Features:
  - producto_id, categoria, precio_unitario
  - cliente_id, tipo_cliente, historial_devoluciones
  - vendedor_id, agencia
  - cantidad_pedida, monto_total
  - dia_semana, mes, temporada
  - tiempo_entrega, distancia_ruta
  - condiciones_almacenamiento
```

**Metricas de evaluacion:**
- Accuracy, Precision, Recall, F1-Score
- AUC-ROC
- Confusion Matrix

### 1.2 Reglas de Asociacion - Patrones de Devolucion
```
Tecnica: Apriori / FP-Growth
Objetivo: Encontrar reglas como:
  - "Si producto=SALSA_X y cliente=MAYORISTA y cantidad>100 → devolucion (75% confianza)"
  - "Si vendedor=V23 y mes=DICIEMBRE → devolucion (60% confianza)"
```

**Metricas:**
- Support (frecuencia)
- Confidence (confianza)
- Lift (relevancia)

### 1.3 Arbol de Decision - Reglas Interpretables
```
Objetivo: Generar reglas de negocio claras
Salida esperada:
  IF cantidad > 50 AND producto = "CONDIMENTO_X" AND cliente_nuevo = TRUE
  THEN probabilidad_devolucion = 0.72
```

## Datos Requeridos
- Historial de ventas con flag de devolucion
- Informacion de productos (categoria, precio, vida util)
- Informacion de clientes (tipo, ubicacion, historial)
- Informacion de vendedores y rutas
- Fechas y temporadas

## Resultado Esperado
1. **Modelo predictivo** que identifique pedidos con alta probabilidad de devolucion
2. **Factores clave** que causan devoluciones (ej: "productos X tienen 3x mas devoluciones")
3. **Recomendaciones** para reducir devoluciones

---

# PREGUNTA 2: DETECCION DE ANOMALIAS FINANCIERAS EN AGENCIAS

## Pregunta
> **"Que jefes de agencia presentan patrones anomalos que podrian indicar irregularidades financieras?"**

## Objetivo de Data Mining
Detectar comportamientos atipicos en las transacciones y reportes de cada agencia que se desvien significativamente del patron esperado.

## Tecnicas de Data Mining

### 2.1 Deteccion de Anomalias - Isolation Forest
```python
# Algoritmo: Isolation Forest
# Detecta puntos que son "faciles de aislar" del resto

Variables a monitorear por agencia:
  - descuentos_otorgados vs promedio_empresa
  - devoluciones_aceptadas vs promedio_empresa
  - notas_credito_emitidas
  - diferencias_inventario
  - ventas_anuladas
  - tiempo_entre_venta_y_cobro
  - margen_promedio vs margen_esperado
```

### 2.2 Analisis de Desviacion Estadistica (Z-Score)
```
Para cada agencia, calcular:
  z_score = (valor_agencia - promedio_todas_agencias) / desviacion_estandar

Alertar si |z_score| > 2.5 (3 desviaciones estandar)
```

### 2.3 Clustering de Comportamiento de Agencias
```
Tecnica: K-Means / DBSCAN
Objetivo: Agrupar agencias por comportamiento similar
         Identificar agencias que no pertenecen a ningun grupo (outliers)

Features:
  - ratio_descuentos_sobre_ventas
  - ratio_devoluciones_sobre_ventas
  - ratio_notas_credito_sobre_ventas
  - diferencia_inventario_teorico_vs_fisico
  - tiempo_promedio_cobro
  - variabilidad_en_margenes
```

### 2.4 Analisis de Series Temporales - Cambio de Comportamiento
```
Detectar cambios abruptos en el comportamiento de una agencia:
  - Incremento repentino en descuentos
  - Cambio en patron de devoluciones
  - Alteraciones en inventario

Tecnicas: CUSUM, Change Point Detection
```

## Metricas y Scores
| Metrica | Descripcion |
|---------|-------------|
| Anomaly Score | Puntuacion de "rareza" (0-1) |
| Z-Score por variable | Desviacion en cada indicador |
| Percentil | Posicion relativa vs otras agencias |

## Dashboard de Alertas
```
+------------------------------------------------------------------+
|  PANEL DE ALERTAS - ANOMALIAS POR AGENCIA                        |
+------------------------------------------------------------------+
| Agencia  | Score | Descuentos | Devoluc. | Inventario | Alertas  |
|----------|-------|------------|----------|------------|----------|
| AGN-05   | 0.89  |    +45%    |   +30%   |    -12%    | CRITICO  |
| AGN-12   | 0.72  |    +25%    |   +15%   |     -5%    | ALTO     |
| AGN-03   | 0.45  |    +10%    |    +5%   |     -2%    | MEDIO    |
+------------------------------------------------------------------+
```

## Datos Requeridos
- Transacciones por agencia (ventas, descuentos, devoluciones)
- Notas de credito emitidas
- Inventario teorico vs fisico
- Tiempos de cobro
- Margenes por transaccion

## Consideraciones Eticas
- El modelo **detecta anomalias**, no acusa directamente
- Los resultados son **indicadores para investigacion**, no pruebas
- Debe complementarse con **auditoria manual**

---

# PREGUNTA 3: OPTIMIZACION DE RUTAS DE VENDEDORES

## Pregunta
> **"Como optimizar las rutas de los vendedores basandose en el historico de clientes, zona geografica y contexto?"**

## Objetivo de Data Mining
Descubrir patrones de visita optimos y segmentar territorios para maximizar ventas y minimizar costos de desplazamiento.

## Tecnicas de Data Mining

### 3.1 Clustering Geografico de Clientes
```
Tecnica: K-Means / DBSCAN con coordenadas
Objetivo: Agrupar clientes por cercania geografica

Features:
  - latitud, longitud
  - frecuencia_compra
  - monto_promedio
  - dia_preferido_compra
  - tipo_cliente
```

**Resultado:** Zonas optimizadas para asignar a cada vendedor

### 3.2 Analisis de Patrones de Compra Temporal
```
Tecnica: Reglas de Asociacion Temporal
Objetivo: Descubrir CUANDO cada cliente prefiere comprar

Ejemplo de reglas:
  - "Cliente C45 compra LUNES o MIERCOLES con 85% frecuencia"
  - "Clientes tipo RESTAURANTE compran MARTES-JUEVES"
  - "Zona Norte tiene pico de pedidos entre 9-11 AM"
```

### 3.3 Segmentacion de Clientes por Valor y Frecuencia (RFM)
```
Analisis RFM adaptado:
  R = Recency (dias desde ultima compra)
  F = Frequency (numero de compras en periodo)
  M = Monetary (monto total)

Segmentos resultantes:
  - Champions: R alto, F alto, M alto → Prioridad maxima en ruta
  - Loyal: F alto, M medio → Visitas regulares
  - At Risk: R bajo, F bajo → Requiere visita urgente
  - Lost: R muy bajo → Evaluar si mantener en ruta
```

### 3.4 Prediccion de Demanda por Cliente
```
Tecnica: Regresion / Series Temporales
Objetivo: Predecir cuanto comprara cada cliente la proxima semana

Esto permite:
  - Priorizar clientes con alta demanda esperada
  - Preparar inventario del vendedor
  - Planificar tiempo de visita
```

### 3.5 Optimizacion de Secuencia de Visitas
```
Basado en los clusters y predicciones:
1. Agrupar clientes por zona (clustering)
2. Ordenar por prioridad (RFM score + demanda predicha)
3. Optimizar secuencia (Traveling Salesman Problem - TSP)

Herramientas: OR-Tools (Google), NetworkX
```

## Datos Requeridos
- Ubicacion de clientes (direccion o coordenadas)
- Historial de compras por cliente
- Horarios y dias de operacion de clientes
- Informacion de vendedores y zonas actuales
- Tiempos de desplazamiento (opcional: API de Google Maps)

## Resultado Esperado
1. **Mapa de zonas optimizadas** por vendedor
2. **Calendario de visitas** basado en patrones de compra
3. **Priorizacion de clientes** por valor y riesgo de perdida
4. **Rutas sugeridas** con secuencia optima

---

# PREGUNTA 4: REDUCCION DE DESPERDICIOS EN PRODUCCION

## Pregunta
> **"Como se pueden reducir los desperdicios en el proceso de produccion?"**

## Objetivo de Data Mining
Identificar los factores (materia prima, lote, operario, maquina, turno, condiciones) que causan mayor desperdicio para tomar acciones correctivas.

## Tecnicas de Data Mining

### 4.1 Regresion - Factores que Afectan el Desperdicio
```
Modelo: Regresion Lineal / Ridge / Lasso
Target: porcentaje_desperdicio o cantidad_desperdicio

Features:
  - producto_id, tipo_producto
  - lote_materia_prima, proveedor
  - operario_id, experiencia_operario
  - maquina_id, antiguedad_maquina, ultimo_mantenimiento
  - turno (manana/tarde/noche)
  - temperatura_ambiente, humedad
  - cantidad_producida
  - dia_semana
```

**Salida:** Coeficientes que indican impacto de cada factor
```
Ejemplo de resultado:
  - turno_noche: +2.3% desperdicio
  - maquina_antigua: +1.8% desperdicio
  - proveedor_B: +0.9% desperdicio
  - operario_experimentado: -1.5% desperdicio
```

### 4.2 Arboles de Decision - Reglas de Alto Desperdicio
```
Tecnica: Decision Tree / Random Forest con interpretabilidad
Objetivo: Identificar combinaciones que causan desperdicio

Reglas descubiertas ejemplo:
  IF maquina = "MAQ-03" AND turno = "NOCHE" AND producto = "SALSA_X"
  THEN desperdicio_esperado = 8.5% (vs promedio 3.2%)

  IF proveedor_mp = "PROV-B" AND humedad > 70%
  THEN desperdicio_esperado = 6.2%
```

### 4.3 Deteccion de Anomalias en Lotes
```
Tecnica: Isolation Forest / Z-Score
Objetivo: Identificar lotes con desperdicio anormalmente alto

Alertar cuando:
  desperdicio_lote > promedio + 2*desviacion_estandar
```

### 4.4 Analisis de Series Temporales
```
Objetivo: Detectar tendencias y estacionalidad en desperdicios

Preguntas:
  - El desperdicio aumenta con el tiempo? (desgaste de maquinas)
  - Hay dias/turnos con patron de mayor desperdicio?
  - Hay estacionalidad (humedad, temperatura)?
```

### 4.5 Clustering de Ordenes de Produccion
```
Tecnica: K-Means
Objetivo: Agrupar ordenes por perfil de desperdicio

Clusters esperados:
  - Cluster 1: "Produccion eficiente" - bajo desperdicio
  - Cluster 2: "Produccion problematica" - alto desperdicio
  - Cluster 3: "Produccion variable" - inconsistente

Analizar caracteristicas de cada cluster
```

## Datos Requeridos
- Ordenes de produccion con cantidad planificada vs real
- Registro de desperdicios por orden/lote
- Informacion de materias primas (lote, proveedor)
- Informacion de maquinas (id, antiguedad, mantenimientos)
- Informacion de operarios
- Condiciones ambientales (si disponible)
- Turnos de produccion

## Resultado Esperado
1. **Ranking de factores** que mas impactan el desperdicio
2. **Reglas de negocio** para prevenir desperdicio
3. **Alertas tempranas** para condiciones de alto riesgo
4. **Recomendaciones** (ej: "Evitar producto X en turno noche en MAQ-03")

---

# PREGUNTA 5: OPTIMIZACION DE ORDENES DE PRODUCCION

## Pregunta
> **"Como se pueden optimizar las ordenes de produccion para mejorar el cumplimiento del plan?"**

## Objetivo de Data Mining
Predecir que ordenes tienen riesgo de incumplimiento y descubrir la secuencia/configuracion optima de produccion.

## Tecnicas de Data Mining

### 5.1 Clasificacion - Prediccion de Cumplimiento
```
Modelo: Random Forest / XGBoost / Logistic Regression
Target: cumple_plan (SI/NO) o desviacion_porcentaje

Features:
  - producto_id, complejidad_producto
  - cantidad_planificada
  - maquina_asignada, disponibilidad_maquina
  - materia_prima_disponible
  - personal_disponible, experiencia_promedio
  - ordenes_previas_dia (carga de trabajo)
  - dia_semana, turno
  - historial_cumplimiento_producto
```

**Salida:**
```
Orden #1234:
  - Probabilidad de cumplimiento: 65%
  - Factores de riesgo:
    * Alta carga de trabajo (+15 ordenes previas)
    * Producto complejo
    * Turno noche
  - Recomendacion: Reprogramar a turno manana
```

### 5.2 Analisis de Factores de Incumplimiento
```
Tecnica: SHAP Values / Feature Importance
Objetivo: Entender POR QUE fallan las ordenes

Resultado esperado:
  Top factores de incumplimiento:
  1. Cantidad planificada muy alta (25% importancia)
  2. Falta de materia prima (20% importancia)
  3. Maquina con mantenimiento pendiente (18% importancia)
  4. Turno noche (12% importancia)
```

### 5.3 Reglas de Asociacion - Patrones de Falla
```
Tecnica: Apriori
Objetivo: Encontrar combinaciones problematicas

Reglas:
  "producto=SALSA_X, cantidad>500, turno=NOCHE → incumplimiento (70%)"
  "maquina=MAQ-02, dias_sin_mantenimiento>30 → incumplimiento (65%)"
```

### 5.4 Clustering de Ordenes
```
Tecnica: K-Means
Objetivo: Identificar perfiles de ordenes

Clusters:
  - "Ordenes simples": Alta tasa de cumplimiento, baja cantidad
  - "Ordenes complejas": Requieren mas tiempo y recursos
  - "Ordenes problematicas": Historicamente fallan
```

### 5.5 Optimizacion de Secuencia (Scheduling)
```
Basado en predicciones, optimizar:
  1. Orden de produccion (que producir primero)
  2. Asignacion de maquinas
  3. Asignacion de turnos
  4. Balance de carga

Tecnica: Algoritmos geneticos / Programacion lineal
```

### 5.6 Prediccion de Tiempo de Produccion
```
Modelo: Regresion
Target: tiempo_real_produccion

Permite:
  - Estimar mejor los tiempos
  - Identificar cuellos de botella
  - Planificar capacidad
```

## Datos Requeridos
- Historial de ordenes de produccion (plan vs real)
- Tiempos de produccion por orden
- Informacion de productos (complejidad, tiempo estandar)
- Disponibilidad de recursos (maquinas, personal, MP)
- Calendarios y turnos
- Historial de mantenimiento de maquinas

## Resultado Esperado
1. **Sistema de alertas tempranas** para ordenes en riesgo
2. **Recomendaciones de reprogramacion**
3. **Reglas de planificacion** (ej: "No programar producto X en turno noche")
4. **Dashboard de prediccion** con probabilidad de cumplimiento

---

# RESUMEN DE TECNICAS POR PREGUNTA

| Pregunta | Tecnicas Principales | Tipo de Problema |
|----------|---------------------|------------------|
| Devoluciones | Clasificacion, Reglas Asociacion | Prediccion + Patrones |
| Anomalias Agencias | Isolation Forest, Z-Score, Clustering | Deteccion de Anomalias |
| Rutas Vendedores | Clustering Geografico, RFM, TSP | Segmentacion + Optimizacion |
| Desperdicios | Regresion, Arboles Decision | Prediccion + Interpretacion |
| Ordenes Produccion | Clasificacion, SHAP, Scheduling | Prediccion + Optimizacion |

---

