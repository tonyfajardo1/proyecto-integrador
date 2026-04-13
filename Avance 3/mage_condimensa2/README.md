# CONDIMENSA - Proyecto funcional para Avance 2

Este directorio es una copia funcional del proyecto de `Avance 1`, usada para aplicar correcciones metodologicas en `Avance 2` sin romper la base anterior.

## Cambios principales de Avance 2

- Se agrego enfoque metodologico anti-leakage en prediccion de devoluciones.
- Se prioriza split temporal cuando existe `periodo_id`.
- Se reportan metricas completas de clasificacion: Accuracy, Precision+, Recall+, F1+, AUC-ROC y AUPRC.
- Se removieron defaults inseguros de passwords en `io_config.yaml`.

## Inicio rapido

1. Copia `.env.example` a `.env` y completa credenciales.
2. Levanta servicios:

```bash
docker-compose up -d
```

3. Accede a:
- Mage: `http://localhost:6789`
- Streamlit: `http://localhost:8501`
- pgAdmin: `http://localhost:5050`

## Servicios

- `mage`: orquestacion de pipelines.
- `postgres_local`: Data Warehouse analitico.
- `pgadmin`: administracion de BD.
- `dashboard`: visualizacion de resultados.

## Rutas clave para correcciones

- `condimensa_project/data_loaders/preparar_datos_prediccion.py`
- `condimensa_project/transformers/entrenar_modelo_prediccion.py`
- `condimensa_project/io_config.yaml`

## Nota

Los artefactos de metodologia, documento y presentacion del avance estan en la carpeta superior `Avance 2/`.
