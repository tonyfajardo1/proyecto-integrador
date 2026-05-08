# Evidencias requeridas para Avance 2

Guardar en esta carpeta evidencia visual y tecnica, con nombres claros por fecha.

## 1) Evidencias de metodologia

- Diagrama de arquitectura integrado al documento.
- Tabla OLTP vs OLAP completa.
- Mapeo CRISP-DM aplicado al proyecto.

## 2) Evidencias de calidad de datos

- Resultado de reglas de calidad (PASS/FAIL).
- Cobertura de datos por periodo/fuente.
- Conteo de nulos y duplicados antes/despues.

## 3) Evidencias de modelado

- Distribucion de clases del dataset.
- Definicion de split temporal (train/validation/test).
- Matriz de confusion.
- Tabla de metricas: accuracy, precision, recall, F1, AUC-ROC, AUPRC.
- Ranking de variables importantes.

## 4) Evidencias anti-leakage

- Lista de variables excluidas por riesgo de leakage.
- Verificacion de que no se usan datos futuros para predecir.
- Resultado final del checklist anti-leakage.

## 5) Evidencias de presentacion

- Slide con problema e impacto.
- Slide con resultados y acciones de negocio.
- Cronometraje de 5 minutos (captura o nota de ensayo).

## Convencion de nombres sugerida

- `YYYYMMDD_arquitectura_v1.png`
- `YYYYMMDD_metricas_modelo_devoluciones.csv`
- `YYYYMMDD_matriz_confusion_devoluciones.png`
- `YYYYMMDD_checklist_anti_leakage.pdf`
