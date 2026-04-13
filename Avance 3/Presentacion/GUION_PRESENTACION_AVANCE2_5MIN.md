# Guion de presentacion Avance 2 (5 minutos)

## Estructura y tiempos

1. **Problema e impacto (40s)**
2. **Preguntas analiticas (40s)**
3. **OLTP vs OLAP + Medallion (50s)**
4. **Metodologia CRISP-DM (40s)**
5. **Resultados de modelos y metricas (90s)**
6. **Hallazgos accionables y siguientes pasos (40s)**

Total: 5:00

---

## Script sugerido

### 1) Problema e impacto (0:00 - 0:40)
"CONDIMENSA integra datos de produccion y comercial en sistemas separados. Esto dificulta identificar causas de devoluciones y desviaciones operativas. En este avance nos enfocamos en responder preguntas analiticas con metodologia de Data Mining validable."

### 2) Preguntas analiticas (0:40 - 1:20)
"Nos enfocamos en tres preguntas: 
1) que factores explican devoluciones, 
2) que patrones explican desviaciones plan vs real, y 
3) que agencias muestran comportamiento atipico para investigacion."

### 3) OLTP vs OLAP + Medallion (1:20 - 2:10)
"Separamos OLTP y OLAP para no afectar sistemas transaccionales. Aplicamos Medallion: Bronze para datos crudos, Silver para datos limpios y Gold para analitica. Esto mejora trazabilidad, calidad y reproducibilidad."

### 4) Metodologia CRISP-DM (2:10 - 2:50)
"Aplicamos CRISP-DM de forma iterativa: negocio, datos, preparacion, modelado, evaluacion y despliegue parcial. La diferencia clave frente al avance anterior es que ahora la evaluacion metodologica es estricta y centrada en negocio."

### 5) Resultados y metricas (2:50 - 4:20)
"Para clasificacion reportamos distribucion de clases, precision, recall, F1, AUC-ROC y AUPRC. Ademas usamos split temporal para evitar leakage. Presentamos matriz de confusion y factores principales del modelo para traducir resultados a decisiones operativas."

### 6) Cierre y siguientes pasos (4:20 - 5:00)
"Con este avance validamos una base metodologica confiable para decisiones. Como siguientes pasos: robustecer datos historicos, recalibrar modelos y extender despliegue en dashboard para usuarios de negocio."

---

## Preguntas probables y respuesta corta

**P:** "Por que no basta con accuracy?"  
**R:** "Porque con clases desbalanceadas puede ser enganoso; por eso reportamos recall, F1 y AUPRC de la clase minoritaria."

**P:** "Como evitaron data leakage?"  
**R:** "Con split temporal, exclusion de variables derivadas del target y transformaciones ajustadas solo en train."

**P:** "Por que Medallion en este caso?"  
**R:** "Permite separar datos crudos, curados y analiticos, sin impactar OLTP y con trazabilidad completa."
