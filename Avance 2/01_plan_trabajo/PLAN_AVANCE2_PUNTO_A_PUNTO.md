# Plan de trabajo Avance 2 (punto por punto)

## 1) Correcciones del profesor -> accion concreta

| Observacion del profesor | Accion en Avance 2 | Evidencia esperada | Estado |
|---|---|---|---|
| Mejorar presentacion y ajustar al tiempo | Usar guion de 5 minutos con tiempos por slide | `04_presentacion/GUION_PRESENTACION_AVANCE2_5MIN.md` | **COMPLETADO** |
| Documento mal organizado | Reestructurar: problema -> metodologia -> arquitectura -> experimentos -> resultados | `02_documento/PLANTILLA_AVANCE2_COMPLETA.md` llena | **COMPLETADO** |
| Arquitectura no debe ir en anexos | Integrar arquitectura en seccion central (metodologia/implementacion) | Seccion 5 completa en documento | **COMPLETADO** |
| Estado del arte debe mostrar trabajos relacionados | Incluir tabla comparativa de papers/casos | Seccion 2.2 + tabla comparativa | **COMPLETADO** |
| Comprender OLTP y OLAP para justificar Medallion | Agregar seccion conceptual con justificacion tecnica | Seccion 3 completa | **COMPLETADO** |
| AUC-ROC muy alto (0.9993) sospechoso | Aplicar checklist anti-leakage y reevaluar modelo | `03_modelado/CHECKLIST_ANTI_LEAKAGE_Y_EVALUACION.md` | **COMPLETADO** |
| Posible leakage / overfitting / split incorrecto | Separacion temporal train/validation/test y exclusion de variables derivadas del target | Seccion 6 + matriz de metricas | **COMPLETADO** |
| Falta tamano de dataset y casos de devolucion | Reportar N total, N clase positiva y distribucion de clases | Seccion 6.1.2 | **COMPLETADO** |
| Accuracy puede ser trivial por desbalance | Reportar recall minoritaria, precision, F1, AUPRC | `03_modelado/MATRIZ_METRICAS_EXPERIMENTOS.md` | **COMPLETADO** |
| Crear repositorio con control de versiones | Mantener repo actualizado con estructura de avance | `Avance 2/` versionado en Git | **COMPLETADO** |

## 2) Aplicacion de aprendizajes de PSet2

| Leccion de PSet2 | Adaptacion para CONDIMENSA | Estado |
|---|---|---|
| Ingesta idempotente | Cargas reproducibles por periodo sin duplicacion | **COMPLETADO** |
| Quality gates automatizados | Reglas de calidad y validacion antes de modelado | **COMPLETADO** |
| Evidencia tecnica en README | Evidencias por experimento y por pipeline | **COMPLETADO** |
| Trazabilidad Bronze/Silver/Gold | Separacion de datos crudos, curados y analiticos | **COMPLETADO** |
| Seguridad en configuracion | Evitar credenciales hardcodeadas, usar variables/secrets | **COMPLETADO** |

## 3) Sprint de ejecucion recomendado

### Sprint A - Documento base y metodologia
- [x] Completar introduccion, preguntas no triviales y alcance.
- [x] Completar estado del arte con trabajos relacionados.
- [x] Completar seccion OLTP vs OLAP + justificacion Medallion.

### Sprint B - Validacion de modelos
- [x] Verificar target y features para evitar leakage.
- [x] Implementar split temporal (train/validation/test).
- [x] Reportar metrica completa (incluyendo AUPRC).
- [x] Interpretar matriz de confusion con foco en clase minoritaria.

### Sprint C - Presentacion y evidencias
- [x] Preparar slides con narrativa problema -> metodo -> hallazgo -> accion.
- [x] Ajustar presentacion a 5 minutos con cronometro.
- [x] Guardar capturas de resultados, metricas y arquitectura.

## 4) Definition of Done (DoD) del Avance 2

- [x] Documento tecnico completo y coherente.
- [x] Arquitectura integrada en cuerpo principal (no anexos).
- [x] Estado del arte con comparacion critica de trabajos.
- [x] Evaluacion robusta sin leakage, con split temporal.
- [x] Metricas completas: accuracy, precision, recall, F1, AUC-ROC, AUPRC.
- [x] Distribucion de clases y tamano de dataset reportados.
- [x] Presentacion ajustada al tiempo y con guion practicado.

## 5) Pendientes finales

- [ ] Obtener firma del tutor en documentos.
- [ ] Hacer push final al repositorio GitHub.
- [ ] Subir a D2L antes del 29 marzo 22:00.
