# Dashboard Streamlit

Esta carpeta contiene la aplicacion de consumo del proyecto final. Su funcion es
mostrar resultados ya transformados en capas Gold o en salidas del forecasting.

## Archivos principales

- `app.py`: punto de entrada y enrutamiento de vistas.
- `config.py`: configuracion visual y constantes compartidas.
- `database.py`: consultas y acceso a la base de datos.
- `components.py`: helpers de interfaz reutilizables.
- `views/`: una vista por pregunta analitica o modulo de negocio.

## Vistas incluidas

- `resumen.py`: resumen ejecutivo del sistema.
- `quickbooks_comercial.py`: indicadores comerciales provenientes de QuickBooks.
- `combinaciones.py`: reglas de asociacion para cross-selling.
- `alertas.py`: anomalias por agencia o comportamiento atipico.
- `predicciones.py`: forecast y tabla de planificacion.

## Como se conecta con el resto del repo

El dashboard no genera los datos por si mismo. Consume:

- tablas Gold del ETL;
- salidas del pipeline `forecasting_v3_quickbooks`;
- resultados de Apriori e Isolation Forest publicados por Mage.

## Recomendacion de lectura

Si quieres entender primero la logica de negocio visible, empieza aqui. Si
quieres entender de donde salen los datos, vuelve a
[../condimensa_project/README.md](../condimensa_project/README.md).
