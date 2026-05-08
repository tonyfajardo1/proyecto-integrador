"""
Data Loader: Preparar datos para pronostico mensual de produccion.
Pipeline: dm_analisis_desviaciones
Pregunta: Cuanto deberia producirse por producto para el siguiente mes?
"""
from mage_ai.settings.repo import get_repo_path
from mage_ai.io.config import ConfigFileLoader
from mage_ai.io.postgres import Postgres
from os import path
import pandas as pd
import numpy as np
import re

if 'data_loader' not in dir():
    from mage_ai.data_preparation.decorators import data_loader
if 'test' not in dir():
    from mage_ai.data_preparation.decorators import test


@data_loader
def preparar_datos_desviaciones(*args, **kwargs):
    """
    Carga produccion historica desde QuickBooks (Supabase) y arma serie producto-mes.
    """
    query = """
    SELECT
        producto,
        fecha,
        qty_planificada,
        qty_fabricada
    FROM quickbooks.produccion
    WHERE producto IS NOT NULL
      AND fecha IS NOT NULL
    """

    config_path = path.join(get_repo_path(), 'io_config.yaml')

    with Postgres.with_config(ConfigFileLoader(config_path, 'quickbooks')) as loader:
        df = loader.load(query)

    print(f"\n{'='*70}")
    print("PREPARACION DATOS - PRONOSTICO PRODUCCION")
    print(f"{'='*70}")
    print(f"Registros fuente: {len(df)}")

    if len(df) == 0:
        return df

    # Normalizacion y calidad
    df['producto'] = df['producto'].astype(str).str.strip()
    df = df[df['producto'].notna() & (df['producto'] != '') & (df['producto'].str.lower() != 'nan')].copy()

    def _normalizar_producto(texto):
        s = re.sub(r'\s+', ' ', str(texto)).strip(' :,-')
        if not s:
            return 'OTRO', 'SIN_PRODUCTO', 'SIN_PRODUCTO', 'SIN_CATEGORIA'

        partes = [p.strip(' :,-') for p in s.split(':') if p and p.strip(' :,-')]
        tipo = 'OTRO'
        if partes and partes[0].upper() in {'PP', 'PT'}:
            tipo = partes[0].upper()
            partes = partes[1:]

        limpias = []
        for seg in partes:
            seg_norm = re.sub(r'\s+', ' ', seg).strip(' ,.-*')
            seg_norm = re.sub(r'^[^A-Za-z0-9]+', '', seg_norm)
            seg_norm = re.sub(r'\bEXTR\b', 'EXT', seg_norm, flags=re.IGNORECASE)
            if not seg_norm:
                continue
            if limpias:
                prev = limpias[-1]
                prev_u = prev.upper().strip()
                seg_u = seg_norm.upper().strip()
                prev_cmp = re.sub(r'^[^A-Z0-9]+', '', prev_u)
                seg_cmp = re.sub(r'^[^A-Z0-9]+', '', seg_u)
                prev_cmp = re.sub(r'^(EL|LA|LOS|LAS)\s+', '', prev_cmp)
                seg_cmp = re.sub(r'^(EL|LA|LOS|LAS)\s+', '', seg_cmp)
                if seg_cmp == prev_cmp:
                    continue
                if seg_cmp.startswith(prev_cmp + ' ') or seg_cmp.startswith(prev_cmp):
                    limpias[-1] = seg_norm
                    continue
            limpias.append(seg_norm)

        if not limpias:
            limpias = [s]

        producto_nombre = ' > '.join(limpias)
        producto_base = re.sub(r'^[^A-Za-z0-9]+', '', limpias[-1]).strip()
        categoria_producto = limpias[0] if len(limpias) > 1 else 'GENERAL'
        return tipo, producto_nombre, producto_base, categoria_producto

    # Resolver tipo real (PT/PP) desde Bronze, para no perder clasificacion
    # cuando en la fuente operativa el nombre ya viene sin prefijo PT:/PP:.
    tipo_catalogo = pd.DataFrame(columns=['producto_nombre', 'tipo_producto_ref'])
    try:
        query_tipo_ref = """
        SELECT producto, fecha
        FROM bronze.quickbooks_produccion_raw
        WHERE producto IS NOT NULL
        """
        with Postgres.with_config(ConfigFileLoader(config_path, 'local_dwh')) as dwh_loader:
            ref = dwh_loader.load(query_tipo_ref)

        if len(ref) > 0:
            ref['producto'] = ref['producto'].astype(str).str.strip()
            ref = ref[ref['producto'] != ''].copy()
            ref['fecha'] = pd.to_datetime(ref.get('fecha'), errors='coerce')

            parsed_ref = ref['producto'].apply(_normalizar_producto)
            parsed_ref_df = pd.DataFrame(
                parsed_ref.tolist(),
                columns=['tipo_producto_ref', 'producto_nombre', 'producto_base_ref', 'categoria_ref'],
                index=ref.index,
            )
            ref = pd.concat([ref, parsed_ref_df], axis=1)
            ref = ref[ref['tipo_producto_ref'].isin(['PT', 'PP'])].copy()

            if len(ref) > 0:
                agg_ref = (
                    ref.groupby(['producto_nombre', 'tipo_producto_ref'], as_index=False)
                    .agg(
                        n=('tipo_producto_ref', 'size'),
                        fecha_max=('fecha', 'max'),
                    )
                    .sort_values(['producto_nombre', 'n', 'fecha_max'], ascending=[True, False, False])
                )
                tipo_catalogo = agg_ref.drop_duplicates(subset=['producto_nombre'])[
                    ['producto_nombre', 'tipo_producto_ref']
                ].copy()
    except Exception as e:
        print(f"[WARN] No se pudo cargar catalogo PT/PP desde bronze: {e}")

    parsed = df['producto'].apply(_normalizar_producto)
    parsed_df = pd.DataFrame(
        parsed.tolist(),
        columns=['tipo_producto', 'producto_nombre', 'producto_base', 'categoria_producto'],
        index=df.index,
    )
    df = pd.concat([df, parsed_df], axis=1)

    if len(tipo_catalogo) > 0:
        df = df.merge(tipo_catalogo, on='producto_nombre', how='left')
        df['tipo_producto'] = np.where(
            df['tipo_producto'].isin(['PT', 'PP']),
            df['tipo_producto'],
            df['tipo_producto_ref'],
        )
        df = df.drop(columns=['tipo_producto_ref'])

    df['tipo_producto'] = df['tipo_producto'].fillna('OTRO').astype(str).str.upper().str.strip()
    df.loc[~df['tipo_producto'].isin(['PT', 'PP']), 'tipo_producto'] = 'OTRO'

    df['producto_raw'] = df['producto']
    df['producto'] = df['producto_nombre']
    df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce')
    df = df[df['fecha'].notna()].copy()
    df['qty_fabricada'] = pd.to_numeric(df.get('qty_fabricada', 0), errors='coerce').fillna(0)
    df['qty_planificada'] = pd.to_numeric(df.get('qty_planificada', 0), errors='coerce').fillna(0)

    before_dups = len(df)
    df = df.drop_duplicates(subset=['tipo_producto', 'producto', 'fecha', 'qty_fabricada', 'qty_planificada']).copy()
    print(f"Duplicados removidos (producto-fecha-qty): {before_dups - len(df)}")

    # Agregar por producto-mes
    df['anio'] = df['fecha'].dt.year
    df['mes'] = df['fecha'].dt.month

    mensual = (
        df.groupby(['tipo_producto', 'categoria_producto', 'producto_base', 'producto', 'anio', 'mes'], as_index=False)
        .agg(
            qty_fabricada=('qty_fabricada', 'sum'),
            qty_planificada=('qty_planificada', 'sum'),
            n_ordenes=('producto', 'count'),
        )
    )

    mensual['periodo'] = pd.to_datetime(
        mensual['anio'].astype(str) + '-' + mensual['mes'].astype(str).str.zfill(2) + '-01',
        errors='coerce',
    )
    mensual = mensual.sort_values(['producto', 'periodo']).reset_index(drop=True)

    # Quality gate basico de nulos
    for col in ['qty_fabricada', 'qty_planificada', 'n_ordenes']:
        mensual[col] = pd.to_numeric(mensual[col], errors='coerce').fillna(0)

    print(f"Productos: {mensual['producto'].nunique()}")
    print(f"Tipos producto: {mensual['tipo_producto'].value_counts().to_dict()}")
    print(f"Periodos: {mensual['periodo'].nunique()}")
    print(f"Rango: {mensual['periodo'].min().date()} a {mensual['periodo'].max().date()}")
    print(f"{'='*70}\n")

    return mensual


@test
def test_output(output, *args) -> None:
    assert output is not None, 'No se cargaron datos'
    assert len(output) > 0, 'Sin datos para pronostico'
    assert 'periodo' in output.columns, 'Falta columna periodo'
    assert 'qty_fabricada' in output.columns, 'Falta qty_fabricada'
    print(f"OK: {len(output)} filas producto-mes listas")
