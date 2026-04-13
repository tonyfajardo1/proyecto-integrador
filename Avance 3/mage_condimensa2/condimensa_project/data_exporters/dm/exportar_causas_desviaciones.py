"""
Data Exporter: Guardar pronostico de produccion y metricas.
Pipeline: dm_analisis_desviaciones
"""
from mage_ai.settings.repo import get_repo_path
from mage_ai.io.config import ConfigFileLoader
from mage_ai.io.postgres import Postgres
from os import path
from datetime import datetime
import pandas as pd
import re

if 'data_exporter' not in dir():
    from mage_ai.data_preparation.decorators import data_exporter
if 'test' not in dir():
    from mage_ai.data_preparation.decorators import test


@data_exporter
def exportar_causas_desviaciones(data, *args, **kwargs):
    pred = data['predicciones'].copy()
    metricas = data['metricas_modelo'].copy()
    importancia = data['importancia_features'].copy()
    serie_modelado = data.get('serie_modelado', pd.DataFrame()).copy()
    pipeline_id = kwargs.get('pipeline_id', 'dm_analisis_desviaciones')

    config_path = path.join(get_repo_path(), 'io_config.yaml')
    config_profile = 'local_dwh'

    ddl = """
    CREATE TABLE IF NOT EXISTS gold.pronostico_produccion_resultado (
        id SERIAL PRIMARY KEY,
        tipo_producto VARCHAR(20),
        categoria_producto VARCHAR(255),
        producto_base VARCHAR(255),
        producto VARCHAR(255),
        periodo DATE,
        periodo_prediccion DATE,
        qty_fabricada NUMERIC,
        qty_planificada NUMERIC,
        pronostico_qty NUMERIC,
        qty_recomendada NUMERIC,
        qty_min_recomendada NUMERIC,
        qty_max_recomendada NUMERIC,
        nivel_confianza VARCHAR(20),
        rolling_std_3 NUMERIC,
        n_ordenes INTEGER,
        sugerencia_accion TEXT,
        posibles_causas TEXT,
        pipeline_id VARCHAR(80),
        fecha_ejecucion TIMESTAMP DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS gold.metricas_pronostico_produccion (
        id SERIAL PRIMARY KEY,
        metrica VARCHAR(50),
        valor_modelo NUMERIC,
        valor_baseline NUMERIC,
        mejora_vs_baseline NUMERIC,
        pipeline_id VARCHAR(80),
        fecha_ejecucion TIMESTAMP DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS gold.importancia_features_pronostico (
        id SERIAL PRIMARY KEY,
        feature VARCHAR(100),
        importancia NUMERIC,
        pipeline_id VARCHAR(80),
        fecha_ejecucion TIMESTAMP DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS silver.catalogo_productos_planificacion (
        id SERIAL PRIMARY KEY,
        tipo_producto VARCHAR(20),
        categoria_producto VARCHAR(255),
        producto_base VARCHAR(255),
        producto VARCHAR(255),
        pipeline_id VARCHAR(80),
        fecha_ejecucion TIMESTAMP DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS silver.produccion_modelado_mensual (
        id SERIAL PRIMARY KEY,
        tipo_producto VARCHAR(20),
        categoria_producto VARCHAR(255),
        producto_base VARCHAR(255),
        producto VARCHAR(255),
        periodo DATE,
        qty_fabricada NUMERIC,
        qty_planificada NUMERIC,
        n_ordenes INTEGER,
        pipeline_id VARCHAR(80),
        fecha_ejecucion TIMESTAMP DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS gold.catalogo_productos_planificacion (
        id SERIAL PRIMARY KEY,
        tipo_producto VARCHAR(20),
        categoria_producto VARCHAR(255),
        producto_base VARCHAR(255),
        producto VARCHAR(255),
        pipeline_id VARCHAR(80),
        fecha_ejecucion TIMESTAMP DEFAULT NOW()
    );
    """

    with Postgres.with_config(ConfigFileLoader(config_path, config_profile)) as loader:
        loader.execute(ddl)
        loader.execute("ALTER TABLE gold.pronostico_produccion_resultado ADD COLUMN IF NOT EXISTS qty_min_recomendada NUMERIC")
        loader.execute("ALTER TABLE gold.pronostico_produccion_resultado ADD COLUMN IF NOT EXISTS qty_max_recomendada NUMERIC")
        loader.execute("ALTER TABLE gold.pronostico_produccion_resultado ADD COLUMN IF NOT EXISTS sugerencia_accion TEXT")
        loader.execute("ALTER TABLE gold.pronostico_produccion_resultado ADD COLUMN IF NOT EXISTS posibles_causas TEXT")
        loader.execute("ALTER TABLE gold.pronostico_produccion_resultado ADD COLUMN IF NOT EXISTS tipo_producto VARCHAR(20)")
        loader.execute("ALTER TABLE gold.pronostico_produccion_resultado ADD COLUMN IF NOT EXISTS categoria_producto VARCHAR(255)")
        loader.execute("ALTER TABLE gold.pronostico_produccion_resultado ADD COLUMN IF NOT EXISTS producto_base VARCHAR(255)")
        loader.execute("ALTER TABLE gold.pronostico_produccion_resultado ADD COLUMN IF NOT EXISTS es_vigente_operativo BOOLEAN")
        loader.execute("ALTER TABLE gold.pronostico_produccion_resultado ADD COLUMN IF NOT EXISTS razon_vigencia VARCHAR(50)")

        # Idempotencia total por pipeline (evita arrastre historico de versiones previas)
        loader.execute(f"DELETE FROM gold.pronostico_produccion_resultado WHERE pipeline_id = '{pipeline_id}'")

        loader.execute(f"DELETE FROM gold.metricas_pronostico_produccion WHERE pipeline_id = '{pipeline_id}'")
        loader.execute(f"DELETE FROM gold.importancia_features_pronostico WHERE pipeline_id = '{pipeline_id}'")
        loader.execute(f"DELETE FROM silver.catalogo_productos_planificacion WHERE pipeline_id = '{pipeline_id}'")
        loader.execute(f"DELETE FROM silver.produccion_modelado_mensual WHERE pipeline_id = '{pipeline_id}'")
        loader.execute(f"DELETE FROM gold.catalogo_productos_planificacion WHERE pipeline_id = '{pipeline_id}'")

        pred['fecha_ejecucion'] = datetime.now()
        metricas['fecha_ejecucion'] = datetime.now()
        importancia['fecha_ejecucion'] = datetime.now()

        loader.export(pred, 'gold', 'pronostico_produccion_resultado', index=False, if_exists='append')
        loader.export(metricas, 'gold', 'metricas_pronostico_produccion', index=False, if_exists='append')
        loader.export(importancia, 'gold', 'importancia_features_pronostico', index=False, if_exists='append')

        catalogo_raw = pred[
            ['tipo_producto', 'categoria_producto', 'producto_base', 'producto', 'pipeline_id']
        ].drop_duplicates().copy()

        # Canonizar catalogo para representar producto real (evitar duplicados por rutas/categorias alternativas)
        def _modo_primero(series):
            s = series.dropna().astype(str).str.strip()
            if len(s) == 0:
                return ''
            vc = s.value_counts()
            return vc.index[0]

        def _canon_texto(texto):
            t = re.sub(r'\s+', ' ', str(texto)).strip()
            t = re.sub(r'\bEXTR\b', 'EXT', t, flags=re.IGNORECASE)
            t = re.sub(r'^[^A-Za-z0-9]+', '', t)
            return t.upper()

        catalogo = (
            catalogo_raw.assign(
                producto_base_canon=catalogo_raw['producto_base'].apply(_canon_texto)
            )
            .groupby(['tipo_producto', 'producto_base_canon'], as_index=False)
            .agg(
                categoria_producto=('categoria_producto', _modo_primero),
                producto_base=('producto_base', _modo_primero),
                producto=('producto', _modo_primero),
                pipeline_id=('pipeline_id', 'first'),
            )
        )

        # Si la ruta elegida no contiene el nombre base, reconstruir una ruta limpia
        mask_reconstruir = ~catalogo.apply(
            lambda r: str(r.get('producto_base', '')).upper() in str(r.get('producto', '')).upper(),
            axis=1,
        )
        catalogo.loc[mask_reconstruir, 'producto'] = (
            catalogo.loc[mask_reconstruir, 'categoria_producto'].astype(str).str.strip()
            + ' > '
            + catalogo.loc[mask_reconstruir, 'producto_base'].astype(str).str.strip()
        )

        catalogo['producto'] = catalogo['producto'].astype(str).str.replace(r'\s+', ' ', regex=True).str.strip(' >')
        catalogo = catalogo[
            ['tipo_producto', 'categoria_producto', 'producto_base', 'producto', 'pipeline_id']
        ].copy()
        catalogo['fecha_ejecucion'] = datetime.now()
        loader.export(catalogo, 'silver', 'catalogo_productos_planificacion', index=False, if_exists='append')
        loader.export(catalogo, 'gold', 'catalogo_productos_planificacion', index=False, if_exists='append')

        if len(serie_modelado) > 0:
            serie_raw = serie_modelado[
                [
                    'tipo_producto', 'categoria_producto', 'producto_base', 'producto',
                    'periodo', 'qty_fabricada', 'qty_planificada', 'n_ordenes', 'pipeline_id',
                ]
            ].copy()

            serie = (
                serie_raw.assign(
                    producto_base_canon=serie_raw['producto_base'].apply(_canon_texto)
                )
                .groupby(['tipo_producto', 'producto_base_canon', 'periodo'], as_index=False)
                .agg(
                    categoria_producto=('categoria_producto', _modo_primero),
                    producto_base=('producto_base', _modo_primero),
                    producto=('producto', _modo_primero),
                    qty_fabricada=('qty_fabricada', 'sum'),
                    qty_planificada=('qty_planificada', 'sum'),
                    n_ordenes=('n_ordenes', 'sum'),
                    pipeline_id=('pipeline_id', 'first'),
                )
            )

            serie = serie[
                [
                    'tipo_producto', 'categoria_producto', 'producto_base', 'producto',
                    'periodo', 'qty_fabricada', 'qty_planificada', 'n_ordenes', 'pipeline_id',
                ]
            ].copy()

            serie['fecha_ejecucion'] = datetime.now()
            loader.export(serie, 'silver', 'produccion_modelado_mensual', index=False, if_exists='append')
        else:
            serie = pd.DataFrame()

    print(f"Pronosticos exportados: {len(pred)}")
    print(f"Metricas exportadas: {len(metricas)}")
    print(f"Features exportadas: {len(importancia)}")
    print(f"Catalogo PP/PT exportado (canonico): {len(catalogo)}")
    print(f"Serie mensual modelado exportada: {len(serie)}")

    return {
        'predicciones_exportadas': len(pred),
        'metricas_exportadas': len(metricas),
        'features_exportadas': len(importancia),
        'catalogo_exportado': len(catalogo),
        'serie_modelado_exportada': len(serie),
    }


@test
def test_output(output, *args) -> None:
    assert output is not None, 'Exportacion fallo'
    assert output['predicciones_exportadas'] > 0, 'No se exportaron pronosticos'
    print('OK: Pronostico exportado a gold')
