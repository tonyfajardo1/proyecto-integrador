# Proyecto Integrador - CONDIMENSA

Repositorio principal del proyecto integrador desarrollado sobre el caso de CONDIMENSA.

Este repositorio esta organizado como un **monorepo academico** que conserva la evolucion completa del trabajo, desde los avances iniciales hasta la version final de tesis. La idea no es mostrar un unico entregable aislado, sino documentar el proceso de construccion, refinamiento metodologico e implementacion tecnica del proyecto.

## Que contiene este repositorio

El trabajo fue desarrollado por etapas. Cada carpeta principal representa un momento distinto del proyecto:

### `Avance 1`

Primer acercamiento al problema, con el planteamiento inicial de arquitectura, ETL y tecnicas de data mining.

Aqui se encuentran principalmente:

- primeras versiones de pipelines en Mage AI;
- exploraciones iniciales de analitica comercial;
- estructura temprana del dashboard;
- documentos y materiales del primer entregable.

### `Avance 2`

Fase intermedia de consolidacion metodologica y experimentacion.

Incluye:

- mayor formalizacion del modelado;
- benchmarking inicial de tecnicas de forecasting;
- materiales de documento y presentacion del segundo entregable;
- artefactos de comparacion de modelos y sensibilidad.

### `Avance 3`

Fase donde se consolida la propuesta tecnica mas cercana a la version final.

Incluye:

- desarrollo de `forecasting_v3`;
- integracion con Mage, Supabase y Power BI;
- validacion temporal, walk-forward y explicabilidad SHAP;
- materiales de tesis, presentacion y respuestas de defensa.

### `Avance Final`

Version final publicada del proyecto de tesis.

Esta es la carpeta **mas importante del repositorio** si quieres revisar el resultado final, porque concentra la solucion refinada y depurada para presentacion publica:

- `mage_condimensa2` con pipelines ETL, dashboard y modulos de analitica;
- `Modelado/forecasting_v3` con el pipeline final de forecasting;
- `Modelado/forecasting_tesis_v2` como referencia comparativa;
- `docs/images` con figuras tomadas de la tesis y la presentacion final;
- documentacion publica adaptada para GitHub.

## Por donde empezar

Si es tu primera vez revisando este repositorio, la ruta recomendada es:

1. Entrar a [`Avance Final`](./Avance%20Final) para ver la version final del proyecto.
2. Leer [`Avance Final/README.md`](./Avance%20Final/README.md) para entender la arquitectura y los resultados.
3. Revisar [`Avance Final/Modelado/forecasting_v3`](./Avance%20Final/Modelado/forecasting_v3) para la metodologia de forecasting.
4. Revisar [`Avance Final/mage_condimensa2`](./Avance%20Final/mage_condimensa2) para ETL, dashboard y pipelines productivos.
5. Si te interesa la evolucion metodologica, comparar luego con `Avance 2` y `Avance 3`.

## Tema del proyecto

El proyecto aborda la integracion de datos empresariales y la construccion de una plataforma analitica con foco en:

- arquitectura Medallion (`Bronze / Silver / Gold`);
- ETL y orquestacion en Mage AI;
- forecasting para productos terminados (`PT`) y productos/proceso (`PP`);
- cross-selling con Apriori;
- deteccion de anomalias con Isolation Forest;
- dashboard operativo para consumo de negocio;
- sincronizacion de datos analiticos con Supabase y Power BI.

## Tecnologias principales

- Python
- PostgreSQL
- SQL
- Mage AI
- Supabase
- scikit-learn
- Streamlit
- Power BI

## Nota sobre datos y privacidad

Este repositorio conserva codigo, notebooks, configuraciones, reportes seleccionados y materiales academicos, pero **no publica de forma abierta todos los datos empresariales crudos ni credenciales sensibles**.

En varias carpetas se mantuvieron versiones documentales o publicas del trabajo para evitar exponer informacion interna de negocio.

## Objetivo de este monorepo

El valor de este repositorio no esta solo en la version final, sino tambien en la trazabilidad del proceso:

- como evoluciono la arquitectura;
- como cambio el enfoque de modelado;
- como se corrigieron problemas metodologicos;

## Autor

**Anthony Fajardo**  
Proyecto Integrador - Ingenieria en Ciencias de la Computacion  
Caso aplicado: **CONDIMENSA**
