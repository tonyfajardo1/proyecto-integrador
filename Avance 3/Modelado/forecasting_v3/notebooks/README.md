# Notebooks

Los notebooks documentan el proyecto paso a paso:

- `01_exploracion_datos.ipynb`: revision de archivos crudos, columnas, fechas y posibles duplicados.
- `02_limpieza_y_catalogo.ipynb`: limpieza PT/PP, matching contra catalogo y reglas de actividad/estacionalidad.
- `03_entrenamiento_modelos.ipynb`: entrenamiento, tuning y comparacion de modelos ML.
- `04_resultados_y_predicciones.ipynb`: predicciones finales, validacion experta y plantillas de stock.

El pipeline productivo sigue viviendo en `scripts/` y `src/quickbooks_forecast/`. Si necesitas regenerar los notebooks:

```bash
python3 scripts/create_notebooks.py
```

Si quieres validarlos ejecutandolos automaticamente:

```bash
python3 -B scripts/run_notebooks.py
```
