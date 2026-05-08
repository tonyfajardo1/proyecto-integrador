# Estructura de Modelado (Limpia)

## Proyecto activo
- `forecasting_tesis_v2/`: implementacion vigente para ejecucion, publicacion en Gold y consumo de dashboard.

## Proyecto legado (solo referencia historica)
- `tesis_forecasting/`: experimentos anteriores conservados como respaldo metodologico.

## Regla operativa
- Para ejecuciones productivas, usar unicamente `forecasting_tesis_v2`.
- No mezclar artefactos de `tesis_forecasting` con el flujo operativo actual.

## Comandos oficiales (proyecto activo)
```bash
python scripts/run_modeling.py --source dwh_forecasting_v1
python scripts/publish_predictions_to_gold.py
python scripts/export_catalog_quality_reports.py
```
