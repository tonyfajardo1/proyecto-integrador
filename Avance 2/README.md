# Avance 2 - Proyecto Integrador CONDIMENSA

Esta carpeta corresponde a la segunda fase del proyecto integrador y documenta la etapa intermedia de consolidacion tecnica y metodologica del trabajo.

En este avance se fortalecio principalmente la parte de:

- modelado y experimentacion en forecasting;
- benchmarking de tecnicas de data mining;
- integracion de pipelines ETL y dashboard sobre `Mage AI`;
- preparacion de materiales para el segundo entregable academico.

## Objetivo de este avance

El objetivo de `Avance 2` fue pasar de una propuesta inicial a una version mas estructurada del proyecto, con mayor enfasis en:

- comparar alternativas de modelado;
- formalizar experimentos reproducibles;
- preparar una base mas solida para la evolucion posterior hacia `Avance 3` y `Avance Final`.

## Estructura principal

En la version publica de este repositorio, `Avance 2` se concentra en dos directorios tecnicos principales:

- `03_modelado`
- `mage_condimensa2`

### `03_modelado`

Contiene la parte de analitica y experimentacion del avance, incluyendo tres lineas de trabajo:

- `forecasting_tesis_v2`
  - primera version estructurada del pipeline de forecasting usado en la tesis;
  - scripts y modulos para modelado, backtesting, intermitencia y segmentacion.

- `proyecto_ml_experimentos`
  - benchmarking comparativo de tecnicas de forecasting, anomalias y reglas de asociacion;
  - scripts para sensibilidad, evaluacion y reportes.

- `tesis_forecasting`
  - prototipos y experimentos adicionales orientados al problema de forecasting de la tesis.

### `mage_condimensa2`

Contiene la evolucion del entorno de integracion y consumo analitico:

- proyecto Mage AI con pipelines ETL;
- transformaciones y cargas para capas de datos;
- dashboard en Streamlit;
- integracion inicial entre analitica, data mining y consumo de negocio.

## Relacion con otros avances

`Avance 2` debe entenderse como una etapa intermedia del proyecto:

- **Avance 1**: planteamiento inicial de arquitectura y primeros pipelines.
- **Avance 2**: consolidacion de experimentos, ETL y estructura metodologica.
- **Avance 3**: refinamiento del forecasting y mayor robustez metodologica.
- **Avance Final**: version final de tesis publicada en el repositorio.

Si quieres revisar el resultado final del proyecto, la carpeta recomendada es:

- [`../Avance Final`](../Avance%20Final)

## Tecnologias presentes en este avance

- Python
- PostgreSQL
- SQL
- Mage AI
- Streamlit
- scikit-learn

## Nota de publicacion

Esta carpeta fue publicada como parte del historial del monorepo y puede contener trabajo exploratorio o versiones intermedias que luego fueron refinadas en avances posteriores.

Por eso, para entender la solucion final completa, conviene complementar esta revision con:

- [`../Avance 3`](../Avance%203)
- [`../Avance Final`](../Avance%20Final)

## Autor

**Anthony Fajardo**  
Proyecto Integrador - Ingenieria en Ciencias de la Computacion  
Caso aplicado: **CONDIMENSA**
