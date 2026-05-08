"""
Transformer: Limpiar y transformar datos de Bronze a Silver
Pipeline: etl_silver
"""
import pandas as pd
import numpy as np
import re
import hashlib
import unicodedata
from difflib import get_close_matches
from pathlib import Path
from datetime import datetime

try:
    from mage_ai.settings.repo import get_repo_path
except Exception:
    get_repo_path = None

if 'transformer' not in dir():
    from mage_ai.data_preparation.decorators import transformer
if 'test' not in dir():
    from mage_ai.data_preparation.decorators import test


@transformer
def transformar_kronos_silver(data, *args, **kwargs):
    """
    Transforma datos crudos de Bronze a Silver.

    Guia de exposicion por bloques:
    [0] Kronos resumen normalizado (prioridad para KPI comercial)
    [1] Kronos detalle (fallback de parsing cuando no hay resumen)
    [2] QuickBooks produccion (cumplimiento de ordenes)
    [3] QuickBooks ventas (consolidacion por venta)
    [4] Transacciones para Apriori (canasta de compra)
    [5] Catalogo EAN limpio (homologacion)
    [6] Ventas mensuales limpias (serie temporal)
    [7] Dimension canonica + base de forecasting

    Cada bloque estandariza esquema, corrige tipos y agrega metadatos para
    trazabilidad (`pipeline_id`, `batch_id`, `fecha_carga`).
    """

    dfs = data.get('dfs', {})
    batch_id = data.get('batch_id')
    pipeline_id = data.get('pipeline_id')

    print(f"\n{'='*70}")
    print(f"TRANSFORMACION - BRONZE A SILVER")
    print(f"{'='*70}\n")

    resultados = {}

    def parse_numeric_robusto(series):
        """Convierte texto numerico mixto (., ,, miles, cientifica) a float."""
        if series is None:
            return pd.Series(dtype='float64')

        def _parse_one(value):
            if pd.isna(value):
                return np.nan
            if isinstance(value, (int, float, np.number)):
                return float(value)

            s = str(value).strip()
            if not s:
                return np.nan

            s_up = s.upper()
            if s_up in {'NULL', 'NONE', 'NAN'}:
                return np.nan

            s_norm = s.replace(' ', '').replace(',', '.')

            try:
                if 'E' in s_norm.upper():
                    return float(s_norm)

                if s_norm.count('.') > 1:
                    parts = s_norm.split('.')
                    s_norm = ''.join(parts[:-1]) + '.' + parts[-1]

                return float(s_norm)
            except Exception:
                return np.nan

        return series.apply(_parse_one)

    def normalize_zone_label_v3(series):
        normalized = series.fillna('').astype(str).str.strip().str.upper()
        normalized = normalized.apply(
            lambda value: ''.join(
                ch for ch in unicodedata.normalize('NFKD', value)
                if not unicodedata.combining(ch)
            )
        )
        return normalized.str.replace(r'\s+', ' ', regex=True).str.strip()

    def exclude_kronos_unassigned_zones_v3(df, centro_col, source_label):
        if len(df) == 0 or centro_col not in df.columns:
            return df

        excluded_mask = normalize_zone_label_v3(df[centro_col]).str.contains(
            r'SIN ASIGNAR|FALTA ASIGNAR',
            regex=True,
            na=False,
        )
        if excluded_mask.any():
            print(
                f"    Filtrando {int(excluded_mask.sum())} filas de {source_label} "
                "con zona sin asignar/falta asignar."
            )
            return df.loc[~excluded_mask].copy()
        return df

    def normalize_product_name(value):
        import re as _re

        text = '' if value is None else str(value)
        text = text.upper().strip()
        text = ''.join(
            c for c in unicodedata.normalize('NFKD', text)
            if not unicodedata.combining(c)
        )
        # Quitar tokens de precio para evitar falsos duplicados de naming.
        text = _re.sub(r'\(\s*\$?\s*\d+[\.,]\d+\s*\)', ' ', text)
        text = _re.sub(r'\$\s*\d+[\.,]\d+', ' ', text)
        text = text.replace('*', ' ')
        text = _re.sub(r'\bPT\s*:', ' ', text)
        text = _re.sub(r'\bPP\s*:', ' ', text)
        text = _re.sub(r'\s+', ' ', text)

        repl = {
            ' GRS ': ' G ',
            ' GRS': ' G',
            ' GR ': ' G ',
            ' DOYPACK ': ' DP ',
            ' D/P ': ' DP ',
        }
        text = f' {text} '
        for old, new in repl.items():
            text = text.replace(old, new)
        text = _re.sub(r'\s+', ' ', text).strip()
        return text

    def stable_hash(text):
        return hashlib.md5(text.encode('utf-8')).hexdigest()[:10]

    month_names_es = {
        1: 'enero',
        2: 'febrero',
        3: 'marzo',
        4: 'abril',
        5: 'mayo',
        6: 'junio',
        7: 'julio',
        8: 'agosto',
        9: 'septiembre',
        10: 'octubre',
        11: 'noviembre',
        12: 'diciembre',
    }
    exogenous_feature_columns = [
        'dias_laborables',
        'feriados_mes',
        'promocion_general',
        'temporada_alta_general',
        'evento_comercial',
        'variacion_precio_general_pct',
        'pedidos_confirmados',
        'preventa_confirmada',
        'promocion_producto',
        'cliente_grande_confirmado',
        'cambio_pvp_pct',
        'precio_planificado',
        'riesgo_quiebre_stock',
        'disponibilidad_materia_prima',
        'ajuste_comercial_manual',
    ]

    def clean_string_v3(value):
        if pd.isna(value):
            return ''
        text = str(value).strip()
        if text.lower() in {'nan', 'none', 'nat'}:
            return ''
        return text

    def strip_accents_v3(value):
        if pd.isna(value):
            return ''
        text = str(value).replace('Ã‘', 'N').replace('Ã±', 'n')
        return ''.join(
            ch for ch in unicodedata.normalize('NFKD', text)
            if not unicodedata.combining(ch)
        )

    def normalize_product_name_v3(value):
        text = strip_accents_v3(value).upper().strip()
        text = re.sub(r'\(\s*\$?\s*\d+[\.,]\d+\s*\)', ' ', text)
        text = re.sub(r'\$\s*\d+[\.,]\d+', ' ', text)
        text = text.replace('&', ' Y ')
        text = text.replace('$', ' ')
        text = re.sub(r'(\d)([A-Z])', r'\1 \2', text)
        text = re.sub(r'([A-Z])(\d)', r'\1 \2', text)
        text = re.sub(r'[^A-Z0-9]+', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()

        # Remueve marcas/prefijos comerciales que no ayudan al match PT.
        text = re.sub(
            r'\b(CONDIMENSA|EL ARTESANAL|SABOR A CAMPO|AK|SX|LO|4B)\b',
            ' ',
            text,
        )
        text = re.sub(r'\s+', ' ', text).strip()

        # Equivalencias comerciales frecuentes PT.
        replacements = [
            (r'\bBTLLA\b', ' BOTELLA '),
            (r'\bBOT\b', ' BOTELLA '),
            (r'\bFDA\b', ' FUNDA '),
            (r'\bFCO\b', ' FRASCO '),
            (r'\bCOMP\b', ' COMPLETO '),
            (r'\bDISP\b', ' DISPLAY '),
            (r'\bDISPL\b', ' DISPLAY '),
            (r'\bDISPX\b', ' DISPLAY X '),
            (r'\bDISPLAYX\b', ' DISPLAY X '),
            (r'\bDOY PACK\b', ' DOYPACK '),
            (r'\bDOYPACK DE\b', ' DOYPACK '),
            (r'\bACHIO\b', ' ACHIOTE '),
            (r'\bPAST\b', ' PASTA '),
            (r'\bGRS\b', ' G '),
            (r'\bGR\b', ' G '),
            (r'\bKIL\b', ' KG '),
            (r'\bKL\b', ' KG '),
            (r'\bC\b', ' ML '),
            (r'\bSAZON COMPLETA\b', ' SAZONADOR COMPLETO '),
            (r'\bSAZON\b', ' SAZONADOR '),
            (r'\bMANI PASTA\b', ' MANI EN PASTA '),
            (r'\bPASTA MANI\b', ' PASTA DE MANI '),
            (r'\bAJO PASTA\b', ' AJO EN PASTA '),
            (r'\bAJO PAST\b', ' AJO EN PASTA '),
            (r'\bACHIOTE PASTA\b', ' ACHIOTE EN PASTA '),
            (r'\bACHIOTE PAST\b', ' ACHIOTE EN PASTA '),
            (r'\bMAYONESA DOYPACK\b', ' DOYPACK MAYONESA '),
            (r'\bMOSTAZA DOYPACK\b', ' DOYPACK MOSTAZA '),
            (r'\bFLOR DE JAMAICA DOYPACK\b', ' DOYPACK FLOR DE JAMAICA '),
            (r'\bBICARBONATO DE SODIO\b', ' BICARBONATO LIMPIEZA '),
            (r'\bAPANAD\b', ' APANADURA '),
            # En ventas PT "ALINO" suele venir sin el descriptor operativo.
            (r'\bALINO\b(?!\s+(COMPLETO|AHUMADO|PREPARADO))', ' ALINO PREPARADO '),
        ]
        for pattern, repl in replacements:
            text = re.sub(pattern, repl, text)

        # Limpieza final y estandarizacion de medidas/empaques.
        text = re.sub(r'\bMLS?\b', ' ML ', text)
        text = re.sub(r'\bVALV\b', ' ', text)
        text = re.sub(r'\bREDONDA\b', ' ', text)
        text = re.sub(r'\bDE\b', ' ', text)
        text = re.sub(r'\b(X\s*\d+)\s+0\s+\d{1,2}\b', r'\1', text)
        text = re.sub(r'\b(\d{4,6})\b$', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def token_set_v3(value):
        text = normalize_product_name_v3(value)
        if not text:
            return set()
        stopwords = {'DE', 'X'}
        return {tok for tok in text.split() if tok and tok not in stopwords}

    def token_overlap_score_v3(left_tokens, right_tokens):
        if not left_tokens or not right_tokens:
            return 0.0
        inter = len(left_tokens & right_tokens)
        union = len(left_tokens | right_tokens)
        if union == 0:
            return 0.0
        return inter / union

    def token_signature_v3(value):
        text = normalize_product_name_v3(value)
        if not text:
            return ''
        tokens = [tok for tok in text.split() if tok and tok not in {'DE'}]
        if not tokens:
            return ''
        return ' '.join(sorted(tokens))

    def extract_size_signature_v3(value):
        text = normalize_product_name_v3(value)
        if not text:
            return ''
        matches = re.findall(r'\b(\d+(?:\.\d+)?)\s*(G|ML|KG|L)\b', text)
        if not matches:
            return ''
        num, unit = matches[-1]
        amount = float(num)
        if unit == 'KG':
            amount *= 1000
            unit = 'G'
        elif unit == 'L':
            amount *= 1000
            unit = 'ML'
        amount_txt = str(int(amount)) if float(amount).is_integer() else f'{amount:.2f}'.rstrip('0').rstrip('.')
        return f'{amount_txt} {unit}'

    def extract_pack_signature_v3(value):
        text = normalize_product_name_v3(value)
        if not text:
            return ''
        for pack in ['DOYPACK', 'BOTELLA', 'FUNDA', 'FRASCO', 'VASO', 'BALDE', 'DISPLAY']:
            if re.search(rf'\b{pack}\b', text):
                return pack
        return ''

    def is_compatible_candidate_v3(row, candidate):
        row_size = clean_string_v3(row.get('size_key'))
        candidate_size = clean_string_v3(candidate.get('size_key'))
        if row_size and candidate_size and row_size != candidate_size:
            return False

        row_pack = clean_string_v3(row.get('pack_key'))
        candidate_pack = clean_string_v3(candidate.get('pack_key'))
        if row_pack and candidate_pack and row_pack != candidate_pack:
            return False

        return True

    def item_leaf_v3(value):
        text = clean_string_v3(value)
        if ':' in text:
            return text.split(':')[-1].strip()
        return text

    def remove_product_prefix_v3(value):
        text = clean_string_v3(value)
        upper = text.upper().strip()
        if upper.startswith('PT:') or upper.startswith('PP:'):
            return text.split(':', 1)[1].strip()
        if upper.startswith('PP SMART SELECTION:'):
            return text.split(':', 1)[1].strip()
        return text

    def extract_product_code_v3(value):
        text = clean_string_v3(value)
        if not text:
            return ''

        paren_codes = re.findall(r'\((?:[^\d]*)(\d{3,6})(?:[^\d]*)\)', text)
        if paren_codes:
            return paren_codes[-1]

        codes = re.findall(r'(?<!\d)(\d{4,6})(?!\d)', text)
        if codes:
            return codes[-1]
        return ''

    def make_product_id_v3(prefix, code, normalized_name):
        code = clean_string_v3(code)
        if code:
            return f'{prefix}_{code}'
        digest = hashlib.sha1(clean_string_v3(normalized_name).encode('utf-8')).hexdigest()[:10]
        return f'{prefix}_{digest}'

    def infer_product_type_v3(value):
        text = clean_string_v3(value).upper()
        if text.startswith('PT:'):
            return 'PT'
        if text.startswith('PP'):
            return 'PP'
        return 'OTHER'

    def mode_or_blank_v3(series):
        values = [clean_string_v3(v) for v in series if clean_string_v3(v)]
        if not values:
            return ''
        return pd.Series(values).mode().iloc[0]

    def has_child_v3(item, all_items):
        prefix = f'{item}:'
        return any(other.startswith(prefix) for other in all_items if other != item)

    def unique_map_v3(df, key_col):
        if len(df) == 0 or key_col not in df.columns:
            return {}
        tmp = df[df[key_col].fillna('').astype(str).ne('')].copy()
        counts = tmp.groupby(key_col)['product_id'].nunique()
        unique_keys = set(counts[counts.eq(1)].index)
        out = {}
        for key, row in tmp[tmp[key_col].isin(unique_keys)].drop_duplicates(key_col).set_index(key_col).iterrows():
            out[key] = row.to_dict()
        return out

    def grouped_rows_v3(df, key_col):
        if len(df) == 0 or key_col not in df.columns:
            return {}
        tmp = df[df[key_col].fillna('').astype(str).ne('')].copy()
        grouped = {}
        for key, group in tmp.groupby(key_col):
            grouped[key] = group.to_dict(orient='records')
        return grouped

    def best_candidate_v3(row, candidates):
        if not candidates:
            return None

        row_tokens = token_set_v3(row.get('producto_raw', ''))
        row_norm = clean_string_v3(row.get('product_norm', ''))
        row_code = clean_string_v3(row.get('product_code', ''))
        row_size = clean_string_v3(row.get('size_key', ''))
        row_pack = clean_string_v3(row.get('pack_key', ''))

        compatible = [c for c in candidates if is_compatible_candidate_v3(row, c)]
        pool = compatible if compatible else candidates

        best = None
        best_score = -1.0
        for candidate in pool:
            cand_name = clean_string_v3(candidate.get('product_name', ''))
            cand_norm = clean_string_v3(candidate.get('product_norm', ''))
            cand_tokens = token_set_v3(cand_name)
            score = token_overlap_score_v3(row_tokens, cand_tokens)

            if row_norm and cand_norm and row_norm == cand_norm:
                score += 3.0
            if row_code and clean_string_v3(candidate.get('product_code', '')) == row_code:
                score += 4.0
            if row_size and clean_string_v3(candidate.get('size_key', '')) == row_size:
                score += 1.5
            if row_pack and clean_string_v3(candidate.get('pack_key', '')) == row_pack:
                score += 1.0

            if score > best_score:
                best_score = score
                best = candidate

        return best.copy() if best is not None else None

    def catalog_lookup_v3(catalog):
        norm_map = unique_map_v3(catalog, 'product_norm')
        leaf_map = unique_map_v3(catalog, 'item_leaf_norm')
        code_map = unique_map_v3(catalog, 'product_code')
        match_key_map = unique_map_v3(catalog, 'match_key')
        leaf_match_key_map = unique_map_v3(catalog, 'item_leaf_match_key')
        code_group_map = grouped_rows_v3(catalog, 'product_code')
        match_key_group_map = grouped_rows_v3(catalog, 'match_key')
        leaf_match_key_group_map = grouped_rows_v3(catalog, 'item_leaf_match_key')
        fuzzy_to_row = {**norm_map, **leaf_map}
        fuzzy_match_key_to_row = {**match_key_map, **leaf_match_key_map}
        fuzzy_choices = sorted(fuzzy_to_row.keys())
        fuzzy_match_keys = sorted(fuzzy_match_key_to_row.keys())
        return {
            'norm': norm_map,
            'leaf': leaf_map,
            'code': code_map,
            'match_key': match_key_map,
            'leaf_match_key': leaf_match_key_map,
            'code_group': code_group_map,
            'match_key_group': match_key_group_map,
            'leaf_match_key_group': leaf_match_key_group_map,
            'fuzzy_choices': fuzzy_choices,
            'fuzzy_to_row': fuzzy_to_row,
            'fuzzy_match_keys': fuzzy_match_keys,
            'fuzzy_match_key_to_row': fuzzy_match_key_to_row,
        }

    def match_pt_product_v3(row, lookup):
        norm = row['product_norm']
        code = row['product_code']
        match_key = row.get('match_key', '')

        if norm in lookup['norm']:
            match = lookup['norm'][norm].copy()
            match['catalog_match_status'] = 'exact_description'
            return match
        if norm in lookup['leaf']:
            match = lookup['leaf'][norm].copy()
            if is_compatible_candidate_v3(row, match):
                match['catalog_match_status'] = 'exact_item_leaf'
                return match
        if code and code in lookup['code']:
            match = lookup['code'][code].copy()
            match['catalog_match_status'] = 'product_code'
            return match
        if code and code in lookup['code_group']:
            match = best_candidate_v3(row, lookup['code_group'][code])
            if match is not None:
                match['catalog_match_status'] = 'product_code_best'
                return match
        if match_key and match_key in lookup['match_key']:
            match = lookup['match_key'][match_key].copy()
            if is_compatible_candidate_v3(row, match):
                match['catalog_match_status'] = 'exact_token_key'
                return match
        if match_key and match_key in lookup['match_key_group']:
            match = best_candidate_v3(row, lookup['match_key_group'][match_key])
            if match is not None:
                match['catalog_match_status'] = 'exact_token_key_best'
                return match
        if match_key and match_key in lookup['leaf_match_key']:
            match = lookup['leaf_match_key'][match_key].copy()
            if is_compatible_candidate_v3(row, match):
                match['catalog_match_status'] = 'exact_leaf_token_key'
                return match
        if match_key and match_key in lookup['leaf_match_key_group']:
            match = best_candidate_v3(row, lookup['leaf_match_key_group'][match_key])
            if match is not None:
                match['catalog_match_status'] = 'exact_leaf_token_key_best'
                return match

        close = get_close_matches(norm, lookup['fuzzy_choices'], n=1, cutoff=0.88)
        if close:
            match = lookup['fuzzy_to_row'][close[0]].copy()
            if is_compatible_candidate_v3(row, match):
                match['catalog_match_status'] = 'fuzzy_name'
                return match
        if match_key:
            close_key = get_close_matches(match_key, lookup['fuzzy_match_keys'], n=1, cutoff=0.86)
            if close_key:
                match = lookup['fuzzy_match_key_to_row'][close_key[0]].copy()
                if is_compatible_candidate_v3(row, match):
                    match['catalog_match_status'] = 'fuzzy_token_key'
                    return match

        if row_tokens := token_set_v3(row.get('producto_raw', '')):
            candidate = best_candidate_v3(
                row,
                [
                    candidate
                    for candidate in lookup['fuzzy_to_row'].values()
                    if token_overlap_score_v3(row_tokens, token_set_v3(candidate.get('product_name', ''))) >= 0.6
                ],
            )
            if candidate is not None:
                candidate['catalog_match_status'] = 'token_overlap'
                return candidate

        return {
            'product_id': make_product_id_v3('PT_UNMATCHED', code, norm),
            'product_code': code,
            'product_name': row['producto_raw'],
            'product_norm': norm,
            'item_leaf': '',
            'item_leaf_norm': '',
            'item_path': '',
            'description': '',
            'unit': '',
            'price': 0.0,
            'ean13': '',
            'ean14': '',
            'is_leaf': False,
            'catalog_match_status': 'no_catalog_match',
        }

    def complete_monthly_grid_v3(monthly, products, value_columns, latest_period=None):
        if len(monthly) == 0 or len(products) == 0:
            return monthly.iloc[0:0].copy()
        if latest_period is None:
            latest_period = monthly['periodo'].max()

        activity = (
            monthly[monthly['target_qty'].gt(0)]
            .groupby('product_id')['periodo']
            .min()
            .rename('first_period')
            .reset_index()
        )
        products_with_start = products.merge(activity, on='product_id', how='inner')

        grids = []
        for row in products_with_start.itertuples(index=False):
            periods = pd.date_range(row.first_period, latest_period, freq='MS')
            grids.append(pd.DataFrame({'product_id': row.product_id, 'periodo': periods}))

        if not grids:
            return monthly.iloc[0:0].copy()

        grid = pd.concat(grids, ignore_index=True)
        out = grid.merge(monthly, on=['product_id', 'periodo'], how='left')
        for col in value_columns:
            out[col] = pd.to_numeric(out[col], errors='coerce').fillna(0.0)
        return out.merge(products, on='product_id', how='left')

    def summarize_products_v3(monthly, inactive_months=12, seasonal_top_3_month_share=0.6, seasonal_max_active_months_per_year=4):
        if len(monthly) == 0:
            return pd.DataFrame(
                columns=[
                    'product_id', 'producto', 'total_qty', 'meses_en_serie', 'primera_actividad',
                    'ultima_actividad', 'meses_con_actividad', 'periodo_referencia',
                    'corte_inactividad', 'estado_producto', 'es_estacional',
                    'share_top_3_meses', 'mediana_meses_activos_por_anio',
                    'meses_estacionales_num', 'meses_estacionales',
                ]
            )

        data = monthly.copy()
        data['periodo'] = pd.to_datetime(data['periodo'])
        latest_period = data['periodo'].max()
        cutoff = latest_period - pd.DateOffset(months=inactive_months - 1)

        active_rows = data[data['target_qty'].gt(0)].copy()
        base_summary = (
            data.groupby('product_id', as_index=False)
            .agg(
                producto=('product_name', 'first'),
                total_qty=('target_qty', 'sum'),
                meses_en_serie=('periodo', 'nunique'),
            )
        )
        activity = (
            active_rows.groupby('product_id', as_index=False)
            .agg(
                primera_actividad=('periodo', 'min'),
                ultima_actividad=('periodo', 'max'),
                meses_con_actividad=('periodo', 'nunique'),
            )
        )
        summary = base_summary.merge(activity, on='product_id', how='left')
        summary['periodo_referencia'] = latest_period
        summary['corte_inactividad'] = cutoff
        summary['estado_producto'] = summary['ultima_actividad'].apply(
            lambda value: 'activo' if pd.notna(value) and value >= cutoff else 'inactivo'
        )

        by_month = active_rows.assign(month_num=active_rows['periodo'].dt.month)
        month_qty = by_month.groupby(['product_id', 'month_num'], as_index=False)['target_qty'].sum()

        seasonal_rows = []
        for product_id, group in month_qty.groupby('product_id'):
            total = group['target_qty'].sum()
            sorted_months = group.sort_values('target_qty', ascending=False)
            top3_share = 0.0 if total <= 0 else sorted_months.head(3)['target_qty'].sum() / total
            top_months = sorted_months.head(3)['month_num'].astype(int).tolist()
            product_history = data[data['product_id'].eq(product_id)].copy()
            active_per_year = (
                product_history[product_history['target_qty'].gt(0)]
                .assign(year=lambda x: x['periodo'].dt.year)
                .groupby('year')['periodo']
                .nunique()
            )
            median_active_months = float(active_per_year.median()) if len(active_per_year) else 0.0
            active_years = int(active_per_year.shape[0])
            is_seasonal = active_years >= 2 and (
                top3_share >= seasonal_top_3_month_share
                or median_active_months <= seasonal_max_active_months_per_year
            )
            seasonal_rows.append(
                {
                    'product_id': product_id,
                    'es_estacional': bool(is_seasonal),
                    'share_top_3_meses': round(float(top3_share), 4),
                    'mediana_meses_activos_por_anio': round(median_active_months, 2),
                    'meses_estacionales_num': ','.join(str(m) for m in top_months),
                    'meses_estacionales': ', '.join(month_names_es[m] for m in top_months),
                }
            )

        seasonal = pd.DataFrame(seasonal_rows)
        summary = summary.merge(seasonal, on='product_id', how='left')
        summary['es_estacional'] = summary['es_estacional'].fillna(False)
        summary['share_top_3_meses'] = summary['share_top_3_meses'].fillna(0.0)
        summary['mediana_meses_activos_por_anio'] = summary['mediana_meses_activos_por_anio'].fillna(0.0)
        summary['meses_estacionales_num'] = summary['meses_estacionales_num'].fillna('')
        summary['meses_estacionales'] = summary['meses_estacionales'].fillna('')
        return summary

    def add_exogenous_defaults_v3(df):
        out = df.copy()
        for col in exogenous_feature_columns:
            if col not in out.columns:
                out[col] = 0.0
            out[col] = pd.to_numeric(out[col], errors='coerce').fillna(0.0)
        return out

    def add_metadata_v3(df):
        out = df.copy()
        out['fecha_carga'] = datetime.now()
        out['pipeline_id'] = pipeline_id
        out['batch_id'] = batch_id
        return out

    # Catalogo de familias PP. Si no existe una tabla dedicada, se deriva
    # desde la propia produccion usando el prefijo PP: / PP.
    pp_family_norm_set = set()
    if 'quickbooks_produccion_categorias_pp_raw' in dfs:
        df_ppcat = dfs['quickbooks_produccion_categorias_pp_raw']
        if isinstance(df_ppcat, list):
            df_ppcat = pd.DataFrame(df_ppcat)
        elif isinstance(df_ppcat, pd.DataFrame):
            df_ppcat = df_ppcat.copy()
        else:
            df_ppcat = pd.DataFrame()

        if len(df_ppcat) > 0:
            if 'familia' not in df_ppcat.columns:
                fam_col = next((c for c in df_ppcat.columns if 'famil' in str(c).lower()), None)
                if fam_col:
                    df_ppcat['familia'] = df_ppcat[fam_col]
                else:
                    df_ppcat['familia'] = ''

            pp_family_norm_set = {
                normalize_product_name(x)
                for x in df_ppcat['familia'].dropna().astype(str).tolist()
                if str(x).strip() not in {'', 'nan', 'None'}
            }

    if not pp_family_norm_set and 'quickbooks_produccion_raw' in dfs:
        df_prod_pp_source = dfs['quickbooks_produccion_raw']
        if isinstance(df_prod_pp_source, list):
            df_prod_pp_source = pd.DataFrame(df_prod_pp_source)
        elif isinstance(df_prod_pp_source, pd.DataFrame):
            df_prod_pp_source = df_prod_pp_source.copy()
        else:
            df_prod_pp_source = pd.DataFrame()

        if len(df_prod_pp_source) > 0 and 'producto' in df_prod_pp_source.columns:
            pp_family_norm_set = {
                normalize_product_name(remove_product_prefix_v3(value))
                for value in df_prod_pp_source['producto'].dropna().astype(str).tolist()
                if infer_product_type_v3(value) == 'PP'
            }

    print(f"[INFO] Familias PP catalogadas (normalizadas): {len(pp_family_norm_set)}")

    # Universo PP desde PRODUCCION2025 (familias PP). Este se usa como referencia,
    # mientras que forecasting de ventas_econespecias se mantiene en PT por defecto.
    if len(pp_family_norm_set) > 0 and 'quickbooks_produccion_raw' in dfs:
        df_prod_pp = dfs['quickbooks_produccion_raw']
        if isinstance(df_prod_pp, list):
            df_prod_pp = pd.DataFrame(df_prod_pp)
        elif isinstance(df_prod_pp, pd.DataFrame):
            df_prod_pp = df_prod_pp.copy()
        else:
            df_prod_pp = pd.DataFrame()

        if len(df_prod_pp) > 0 and 'producto' in df_prod_pp.columns:
            df_prod_pp['producto'] = df_prod_pp['producto'].fillna('').astype(str)
            df_prod_pp['nombre_normalizado'] = df_prod_pp['producto'].apply(normalize_product_name)

            def _is_pp_name(name_norm: str) -> bool:
                txt = f" {name_norm} "
                for fam in pp_family_norm_set:
                    if fam and (fam in txt or txt.strip() in fam):
                        return True
                return False

            df_prod_pp['flag_pp_catalogo'] = df_prod_pp['nombre_normalizado'].apply(_is_pp_name)

            code_extracted = (
                df_prod_pp['producto'].str.extract(r'\((\d+)\)')[0]
                .fillna(df_prod_pp['producto'].str.extract(r'(\d+)$')[0])
            )
            df_prod_pp['codigo_producto'] = code_extracted.apply(
                lambda x: str(x).strip().zfill(4)
                if pd.notna(x) and str(x).strip() not in {'', 'nan', 'None'}
                else ''
            )

            pp_ref = df_prod_pp[df_prod_pp['flag_pp_catalogo']].copy()
            pp_ref['tipo_objetivo'] = 'PP'
            pp_ref['origen_regla'] = 'PRODUCCION2025_CATEGORIAS_PP'
            pp_ref['fecha_carga'] = datetime.now()
            pp_ref['pipeline_id'] = pipeline_id
            pp_ref['batch_id'] = batch_id

            pp_ref = pp_ref[
                ['codigo_producto', 'nombre_normalizado', 'producto', 'tipo_objetivo', 'origen_regla', 'fecha_carga', 'pipeline_id', 'batch_id']
            ].drop_duplicates()
            resultados['pp_universe_produccion_2025'] = pp_ref
            print(f"[INFO] Universo PP (produccion 2025): {len(pp_ref)} registros")

    # Mapeo manual puente PP/PT (editable por negocio).
    manual_mapping_df = pd.DataFrame(
        columns=['codigo_producto', 'nombre_normalizado', 'tipo_objetivo', 'estado', 'nota']
    )
    if get_repo_path:
        mapping_path = Path(get_repo_path()) / 'data' / 'manual' / 'pp_pt_mapping_manual.csv'
    else:
        mapping_path = Path.cwd() / 'data' / 'manual' / 'pp_pt_mapping_manual.csv'
    if mapping_path.exists():
        try:
            mm = pd.read_csv(mapping_path)
            mm.columns = [str(c).strip().lower() for c in mm.columns]
            ren = {
                'tipo_objetivo': 'tipo_objetivo',
                'tipo_destino': 'tipo_objetivo',
                'tipo_final': 'tipo_objetivo',
                'codigo': 'codigo_producto',
                'codigo_prod': 'codigo_producto',
                'nombre_norm': 'nombre_normalizado',
                'estado_mapping': 'estado',
            }
            mm = mm.rename(columns={k: v for k, v in ren.items() if k in mm.columns})
            for c in ['codigo_producto', 'nombre_normalizado', 'tipo_objetivo', 'estado', 'nota']:
                if c not in mm.columns:
                    mm[c] = ''

            mm['codigo_producto'] = mm['codigo_producto'].fillna('').astype(str).str.strip()
            mm['nombre_normalizado'] = mm['nombre_normalizado'].fillna('').astype(str).apply(normalize_product_name)
            mm['tipo_objetivo'] = mm['tipo_objetivo'].fillna('').astype(str).str.upper().str.strip()
            mm['estado'] = mm['estado'].fillna('ACTIVO').astype(str).str.upper().str.strip()
            mm['nota'] = mm['nota'].fillna('').astype(str)

            mm = mm[mm['tipo_objetivo'].isin({'PP', 'PT'})].copy()
            mm = mm[mm['estado'].isin({'ACTIVO', ''})].copy()
            mm = mm[(mm['codigo_producto'] != '') | (mm['nombre_normalizado'] != '')].copy()

            manual_mapping_df = mm[['codigo_producto', 'nombre_normalizado', 'tipo_objetivo', 'estado', 'nota']].drop_duplicates()
            print(f"[INFO] Mapeo manual PP/PT cargado: {len(manual_mapping_df)} reglas")
        except Exception as e:
            print(f"[WARN] No se pudo cargar mapeo manual PP/PT: {e}")

    # =========================================================================
    # 0. FUENTE PRIORITARIA: KRONOS RESUMEN NORMALIZADO (EXCEL)
    # =========================================================================
    if 'kronos_ventas_resumen_raw' in dfs:
        print("[0] Transformando kronos_ventas_resumen_raw (prioridad para KPIs)...")

        df_res = dfs['kronos_ventas_resumen_raw']
        if isinstance(df_res, list):
            df_res = pd.DataFrame(df_res)
        elif isinstance(df_res, pd.DataFrame):
            df_res = df_res.copy()
        else:
            df_res = pd.DataFrame()

        if len(df_res) > 0:
            mapeo = {
                'centro_costo': 'centro_costo',
                'codigo_producto': 'codigo_producto',
                'codigo_alterno': 'codigo_alterno',
                'producto': 'producto',
                'mes': 'mes',
                'anio': 'anio',
                'cant_venta': 'cant_venta',
                'total_venta': 'total_venta',
                'cant_nc': 'cant_nc',
                'total_nc': 'total_nc',
                'cant_devolucion': 'cant_devolucion',
                'total_devolucion': 'total_devolucion',
                'cant_neto': 'cant_neto',
                'total_neto': 'total_neto',
                'costo_venta': 'costo_venta',
                'rentabilidad': 'rentabilidad',
                'prc_rentabilidad': 'prc_rentabilidad',
            }

            for col in mapeo.keys():
                if col not in df_res.columns:
                    df_res[col] = None

            df_k = df_res[list(mapeo.keys())].copy()

            for col in [
                'cant_venta', 'total_venta', 'cant_nc', 'total_nc',
                'cant_devolucion', 'total_devolucion', 'cant_neto', 'total_neto',
                'costo_venta', 'rentabilidad', 'prc_rentabilidad',
            ]:
                df_k[col] = parse_numeric_robusto(df_k[col]).fillna(0)

            df_k['anio'] = pd.to_numeric(df_k['anio'], errors='coerce').fillna(2026).astype(int)
            df_k['mes'] = df_k['mes'].astype(str).str.upper().str.strip()
            df_k['centro_costo'] = df_k['centro_costo'].astype(str).str.strip()
            df_k['codigo_producto'] = df_k['codigo_producto'].astype(str).str.strip()
            df_k['codigo_alterno'] = df_k['codigo_alterno'].astype(str).str.strip()
            df_k['producto'] = df_k['producto'].astype(str).str.strip()

            df_k = df_k[df_k['mes'].notna() & (df_k['mes'] != '') & (df_k['mes'] != 'NAN')].copy()
            df_k = df_k[df_k['producto'].notna() & (df_k['producto'] != '') & (df_k['producto'] != 'NAN')].copy()

            df_k = (
                df_k.groupby(
                    ['centro_costo', 'codigo_producto', 'codigo_alterno', 'producto', 'mes', 'anio'],
                    as_index=False,
                )
                .sum(numeric_only=True)
            )

            devolucion_excede_venta = (
                (df_k['cant_devolucion'] > df_k['cant_venta'])
                | (df_k['total_devolucion'] > df_k['total_venta'])
            )
            neto_negativo = (df_k['cant_neto'] < 0) | (df_k['total_neto'] < 0)

            df_k['es_dato_calidado'] = True
            df_k['flag_outlier'] = devolucion_excede_venta | neto_negativo
            df_k['flag_valor_nulo'] = False
            df_k['fecha_carga'] = datetime.now()
            df_k['pipeline_id'] = pipeline_id
            df_k['batch_id'] = batch_id
            df_k = exclude_kronos_unassigned_zones_v3(
                df_k,
                'centro_costo',
                'kronos_ventas_resumen_raw',
            )

            resultados['kronos_ventas'] = df_k
            print(f"    kronos_ventas desde resumen normalizado: {len(df_k)}")

    if 'kronos_resumen_ejecutivo_raw' in dfs:
        print("[0b] Transformando kronos_resumen_ejecutivo_raw para resumen ejecutivo...")

        df_exec = dfs['kronos_resumen_ejecutivo_raw']
        if isinstance(df_exec, list):
            df_exec = pd.DataFrame(df_exec)
        elif isinstance(df_exec, pd.DataFrame):
            df_exec = df_exec.copy()
        else:
            df_exec = pd.DataFrame()

        if len(df_exec) > 0:
            required_cols = [
                'centro_costo', 'mes', 'anio',
                'cant_venta', 'total_venta', 'cant_devolucion', 'total_devolucion',
                'cant_neto', 'total_neto', 'costo_venta', 'rentabilidad', 'prc_rentabilidad',
            ]
            for col in required_cols:
                if col not in df_exec.columns:
                    df_exec[col] = None

            df_exec = df_exec[required_cols].copy()

            for col in [
                'cant_venta', 'total_venta', 'cant_devolucion', 'total_devolucion',
                'cant_neto', 'total_neto', 'costo_venta', 'rentabilidad', 'prc_rentabilidad',
            ]:
                df_exec[col] = parse_numeric_robusto(df_exec[col]).fillna(0)

            df_exec['anio'] = pd.to_numeric(df_exec['anio'], errors='coerce').fillna(0).astype(int)
            df_exec['mes'] = df_exec['mes'].astype(str).str.upper().str.strip()
            df_exec['centro_costo'] = df_exec['centro_costo'].astype(str).str.strip()

            df_exec = df_exec[
                df_exec['centro_costo'].notna() & (df_exec['centro_costo'] != '') &
                df_exec['mes'].notna() & (df_exec['mes'] != '') & (df_exec['mes'] != 'NAN') &
                (df_exec['anio'] > 0)
            ].copy()

            df_exec = (
                df_exec.groupby(['centro_costo', 'mes', 'anio'], as_index=False)
                .sum(numeric_only=True)
            )

            devolucion_excede_venta = df_exec['total_devolucion'] > df_exec['total_venta']
            neto_negativo = (df_exec['cant_neto'] < 0) | (df_exec['total_neto'] < 0)

            df_exec['es_dato_calidado'] = True
            df_exec['flag_outlier'] = devolucion_excede_venta | neto_negativo
            df_exec['flag_valor_nulo'] = False
            df_exec['fecha_carga'] = datetime.now()
            df_exec['pipeline_id'] = pipeline_id
            df_exec['batch_id'] = batch_id
            df_exec = exclude_kronos_unassigned_zones_v3(
                df_exec,
                'centro_costo',
                'kronos_resumen_ejecutivo_raw',
            )

            resultados['kronos_resumen_ejecutivo'] = df_exec
            print(f"    kronos_resumen_ejecutivo: {len(df_exec)}")

    # =========================================================================
    # 0. NUEVA FUENTE KRONOS TRANSACCIONAL (detalle factura-item)
    # =========================================================================
    if 'kronos_ventas_detalle_raw' in dfs and 'kronos_ventas' not in resultados:
        print("[0] Transformando kronos_ventas_detalle_raw (transaccional)...")

        df_det = dfs['kronos_ventas_detalle_raw']
        if isinstance(df_det, list):
            df_det = pd.DataFrame(df_det)
        elif isinstance(df_det, pd.DataFrame):
            df_det = df_det.copy()
        else:
            df_det = pd.DataFrame()

        if len(df_det) > 0:
            # Normalizar tipos
            for col in ['cantidad', 'valor_unitario', 'valor_total', 'costo', 'descuento']:
                if col in df_det.columns:
                    df_det[col] = parse_numeric_robusto(df_det[col]).fillna(0)
                else:
                    df_det[col] = 0

            if 'fecha_factura' in df_det.columns:
                df_det['fecha_factura'] = pd.to_datetime(df_det['fecha_factura'], errors='coerce')
            else:
                df_det['fecha_factura'] = pd.NaT

            # Filtrar filas utiles
            df_det = df_det[df_det['fecha_factura'].notna()].copy()
            df_det['tipo'] = df_det.get('tipo', '').astype(str).str.upper().str.strip()

            # Campos base
            df_det['centro_costo'] = df_det.get('id_sucursal', '').astype(str)
            df_det['codigo_producto'] = df_det.get('codigo_producto', '').astype(str)
            df_det['codigo_alterno'] = df_det.get('id_producto', '').astype(str)
            df_det['producto'] = df_det.get('descripcion_producto', '').astype(str)
            df_det['mes'] = df_det['fecha_factura'].dt.month.map({
                1: 'ENERO', 2: 'FEBRERO', 3: 'MARZO', 4: 'ABRIL', 5: 'MAYO', 6: 'JUNIO',
                7: 'JULIO', 8: 'AGOSTO', 9: 'SEPTIEMBRE', 10: 'OCTUBRE', 11: 'NOVIEMBRE', 12: 'DICIEMBRE'
            })
            df_det['anio'] = df_det['fecha_factura'].dt.year

            # Separar por tipo de documento
            is_factura = df_det['tipo'].str.contains('FACTURA', na=False)
            is_nc = df_det['tipo'].str.contains('NC', na=False)

            # En esta fuente, cantidad suele venir escalada x100 (100=1 unidad).
            mask_qty_x100 = (np.abs(df_det['cantidad']) >= 100) & ((np.abs(df_det['cantidad']) % 100) < 1e-9)
            df_det['cantidad_norm'] = np.where(mask_qty_x100, df_det['cantidad'] / 100, df_det['cantidad'])

            # Normalizar precio unitario cuando viene escalado x100.
            # Regla: si valor_unitario ~= 100 * (valor_total / cantidad), dividir por 100.
            precio_implicito = np.where(
                df_det['cantidad_norm'] > 0,
                df_det['valor_total'] / df_det['cantidad_norm'],
                np.nan,
            )
            ratio_precio = np.where(
                np.isfinite(precio_implicito) & (precio_implicito > 0),
                df_det['valor_unitario'] / precio_implicito,
                np.nan,
            )

            mask_precio_x100 = (
                np.isfinite(ratio_precio)
                & (ratio_precio >= 80)
                & (ratio_precio <= 120)
            )

            df_det['valor_unitario_norm'] = np.where(
                mask_precio_x100,
                df_det['valor_unitario'] / 100,
                df_det['valor_unitario'],
            )

            # Normalizar valor_total cuando viene escalado x100 respecto a unitario*cantidad.
            denom_total = df_det['valor_unitario_norm'] * df_det['cantidad_norm']
            ratio_total = np.where(
                (denom_total > 0) & np.isfinite(denom_total),
                df_det['valor_total'] / denom_total,
                np.nan,
            )
            mask_total_x100 = (
                np.isfinite(ratio_total)
                & (ratio_total >= 0.8)
                & (ratio_total <= 1.2)
            )

            mask_reconstruir_total = (df_det['valor_total'] <= 0)
            df_det['valor_total_norm'] = np.where(
                mask_total_x100,
                df_det['valor_total'] / 100,
                df_det['valor_total'],
            )

            df_det['cant_venta'] = np.where(is_factura, df_det['cantidad_norm'].clip(lower=0), 0)
            df_det['total_venta'] = np.where(is_factura, df_det['valor_total_norm'].clip(lower=0), 0)

            df_det['cant_nc'] = np.where(is_nc, np.abs(df_det['cantidad_norm']), 0)
            df_det['total_nc'] = np.where(is_nc, np.abs(df_det['valor_total_norm']), 0)

            # Devolucion aproximada via NC DEV
            is_nc_dev = df_det['tipo'].str.contains('NC DEV', na=False)
            df_det['cant_devolucion'] = np.where(is_nc_dev, np.abs(df_det['cantidad_norm']), 0)
            df_det['total_devolucion'] = np.where(is_nc_dev, np.abs(df_det['valor_total_norm']), 0)

            df_det['cant_neto'] = df_det['cant_venta'] - df_det['cant_nc']
            df_det['total_neto'] = df_det['total_venta'] - df_det['total_nc']
            # En la fuente Kronos, `costo` viene a nivel de linea (no unitario).
            # Multiplicar por cantidad infla costos y distorsiona rentabilidad.
            df_det['costo_venta'] = np.where(is_factura, np.abs(df_det['costo']), 0)
            df_det['rentabilidad'] = df_det['total_neto'] - df_det['costo_venta']
            df_det['prc_rentabilidad'] = np.where(
                df_det['total_neto'] > 0,
                (df_det['rentabilidad'] / df_det['total_neto']) * 100,
                0,
            )

            agg_cols = [
                'centro_costo', 'codigo_producto', 'codigo_alterno', 'producto', 'mes', 'anio',
                'cant_venta', 'total_venta', 'cant_nc', 'total_nc',
                'cant_devolucion', 'total_devolucion', 'cant_neto', 'total_neto',
                'costo_venta', 'rentabilidad', 'prc_rentabilidad',
            ]
            df_k = df_det[agg_cols].groupby(
                ['centro_costo', 'codigo_producto', 'codigo_alterno', 'producto', 'mes', 'anio'],
                as_index=False,
            ).sum(numeric_only=True)

            devolucion_excede_venta = (
                (df_k['cant_devolucion'] > df_k['cant_venta'])
                | (df_k['total_devolucion'] > df_k['total_venta'])
            )
            neto_negativo = (df_k['cant_neto'] < 0) | (df_k['total_neto'] < 0)

            df_k['es_dato_calidado'] = True
            df_k['flag_outlier'] = devolucion_excede_venta | neto_negativo
            df_k['flag_valor_nulo'] = False
            df_k['fecha_carga'] = datetime.now()
            df_k['pipeline_id'] = pipeline_id
            df_k['batch_id'] = batch_id
            df_k = exclude_kronos_unassigned_zones_v3(
                df_k,
                'centro_costo',
                'kronos_ventas_detalle_raw',
            )

            resultados['kronos_ventas'] = df_k
            print(f"    kronos_ventas desde detalle: {len(df_k)}")
            print(f"    precios unitarios normalizados x100: {int(mask_precio_x100.sum())}")
            print(f"    totales normalizados x100: {int(mask_total_x100.sum())}")
            print(f"    cantidades normalizadas x100: {int(mask_qty_x100.sum())}")
            print(f"    lineas sin total util (no se imputan): {int(mask_reconstruir_total.sum())}")

    # Buscar la tabla de ventas
    key_ventas = None
    for key in dfs.keys():
        if 'ventas' in key.lower() or 'kronos' in key.lower():
            key_ventas = key
            break

    if key_ventas and 'kronos_ventas' not in resultados:
        print(f"[1] Transformando {key_ventas}...")

        dato = dfs[key_ventas]

        # Convertir a DataFrame
        if isinstance(dato, list):
            df_raw = pd.DataFrame(dato)
        elif isinstance(dato, pd.DataFrame):
            df_raw = dato.copy()
        else:
            df_raw = pd.DataFrame()

        print(f"    Filas iniciales: {len(df_raw)}")
        print(f"    Columnas: {df_raw.columns.tolist()}")

        # =========================================================================
        # 1. BUSCAR FILA DE ENCABEZADOS REALES
        # El archivo Excel de Kronos tiene:
        # - Filas 0-6: Titulos del reporte
        # - Fila 7: Encabezados reales (CENTRO_COSTO, CODIGO_PRODUCTO, etc.)
        # - Fila 8+: Datos
        # =========================================================================

        header_row = None
        mes_extraido = None  # Para extraer el mes del encabezado del reporte
        col_busqueda = df_raw.columns[0] if len(df_raw.columns) > 0 else None

        # Extraer AÑO del encabezado del reporte (no MES, porque cada fila tiene su MES)
        # El formato es: "Agrupado por: ... Desde: DD/MM/YYYY Hasta: DD/MM/YYYY"
        import re as _re_header
        anio_extraido = None

        if col_busqueda:
            for idx in range(min(10, len(df_raw))):
                try:
                    val = str(df_raw.iloc[idx][col_busqueda]) if pd.notna(df_raw.iloc[idx][col_busqueda]) else ''
                    # Buscar patrón "Desde: DD/MM/YYYY" para extraer el AÑO
                    match = _re_header.search(r'Desde:\s*(\d{1,2})/(\d{1,2})/(\d{4})', val)
                    if match:
                        anio_extraido = match.group(3)  # Extraer el año (2026)
                        print(f"    Año extraído del encabezado: {anio_extraido}")
                        break
                except:
                    continue

        if col_busqueda:
            for idx in range(min(50, len(df_raw))):
                try:
                    val = str(df_raw.iloc[idx][col_busqueda]).upper().strip() if pd.notna(df_raw.iloc[idx][col_busqueda]) else ''
                    # Buscar EXACTAMENTE "CENTRO_COSTO" (no solo "CENTRO")
                    if val == 'CENTRO_COSTO':
                        header_row = idx
                        print(f"    Encabezado encontrado en fila {idx}: '{val}'")
                        break
                except:
                    continue

        # Si no encontramos CENTRO_COSTO exacto, buscar por patron de columnas
        if header_row is None:
            print(f"    [INFO] Buscando encabezados por patron...")
            for idx in range(min(50, len(df_raw))):
                try:
                    # Verificar si esta fila tiene aspecto de encabezados
                    row_values = [str(df_raw.iloc[idx][c]).upper().strip() for c in df_raw.columns[:4]]
                    # Los encabezados reales tienen valores cortos y especificos
                    if any('CENTRO' in v and len(v) < 20 for v in row_values):
                        if any('CODIGO' in v or 'PRODUCTO' in v for v in row_values):
                            header_row = idx
                            print(f"    Encabezado encontrado por patron en fila {idx}")
                            break
                except:
                    continue

        # =========================================================================
        # 2. CREAR DATAFRAME CON DATOS LIMPIOS
        # =========================================================================

        if header_row is not None:
            # Obtener encabezados
            encabezados = []
            for c in df_raw.columns:
                val = df_raw.iloc[header_row][c]
                enc = str(val).strip().upper() if pd.notna(val) else f'COL_{c}'
                encabezados.append(enc)

            print(f"    Encabezados detectados: {encabezados[:8]}")

            # Crear nuevo DataFrame con datos (filas despues del encabezado)
            df = df_raw.iloc[header_row + 1:].copy()
            df.columns = encabezados

            # Limpiar filas vacias y totales
            df = df.replace('', np.nan)
            df = df.dropna(how='all')

            # Filtrar filas que son totales o subtotales
            first_col = df.columns[0]
            df = df[~df[first_col].astype(str).str.contains('Total|TOTAL|Subtotal', na=False, case=False)]
            df = df[df[first_col].notna()]

            print(f"    Filas de datos: {len(df)}")
        else:
            print(f"    [WARN] No se encontraron encabezados, usando estructura por defecto")
            df = df_raw.iloc[7:].copy()  # Saltar las 7 primeras filas tipicas
            df.columns = ['CENTRO_COSTO', 'CODIGO_PRODUCTO', 'ALTERNO', 'PRODUCTO',
                         'CANT_VENTA', 'TOTAL_VENTA', 'CANT_NC', 'TOTAL_NC',
                         'CANT_DEVOLUCION', 'TOTAL_DEVOLUCION', 'CANT_NETO', 'TOTAL_NETO',
                         'COSTO_VENTA', 'RENTABILIDAD', 'PRC_RENTABILIDAD', 'MES'][:len(df.columns)]

        # =========================================================================
        # 3. MAPEAR COLUMNAS A NOMBRES ESTANDAR
        # El archivo Kronos tiene columnas en orden especifico.
        # Usamos mapeo EXACTO para evitar duplicados.
        # =========================================================================

        # Mapeo EXACTO (sin coincidencias parciales)
        mapeo_exacto = {
            'CENTRO_COSTO': 'centro_costo',
            'CENTRO COSTO': 'centro_costo',
            'CODIGO_PRODUCTO': 'codigo_producto',
            'CODIGO PRODUCTO': 'codigo_producto',
            'ALTERNO': 'codigo_alterno',
            'CODIGO_ALTERNO': 'codigo_alterno',
            'CODIGO ALTERNO': 'codigo_alterno',
            'PRODUCTO': 'producto',
            'NOMBRE': 'producto',
            'NOMBRE_PRODUCTO': 'producto',
            # Columnas de cantidad - EXACTAS
            'CANT': 'cant_venta',
            'CANT_VENTA': 'cant_venta',
            'CANT VENTA': 'cant_venta',
            'CANTIDAD': 'cant_venta',
            'CANT NC': 'cant_nc',
            'CANT_NC': 'cant_nc',
            'CANT DV': 'cant_devolucion',
            'CANT_DV': 'cant_devolucion',
            'CANT DEVOLUCION': 'cant_devolucion',
            'CANT_DEVOLUCION': 'cant_devolucion',
            'CANT NC DV': 'cant_devolucion',
            'CANT_NC_DV': 'cant_devolucion',
            'CANT NETO': 'cant_neto',
            'CANT_NETO': 'cant_neto',
            # Columnas de totales - EXACTAS
            'TOTAL': 'total_venta',
            'TOTAL_VENTA': 'total_venta',
            'TOTAL VENTA': 'total_venta',
            'VENTA': 'total_venta',
            'TOTAL NC': 'total_nc',
            'TOTAL_NC': 'total_nc',
            'TOTAL DV': 'total_devolucion',
            'TOTAL_DV': 'total_devolucion',
            'TOTAL DEVOLUCION': 'total_devolucion',
            'TOTAL_DEVOLUCION': 'total_devolucion',
            'TOTAL NC DV': 'total_devolucion',
            'TOTAL_NC_DV': 'total_devolucion',
            'TOTAL NETO': 'total_neto',
            'TOTAL_NETO': 'total_neto',
            'NETO': 'total_neto',
            # Otras columnas
            'COSTO': 'costo_venta',
            'COSTO_VENTA': 'costo_venta',
            'COSTO VENTA': 'costo_venta',
            'RENTABILIDAD': 'rentabilidad',
            'RENT': 'rentabilidad',
            'PRC_RENTABILIDAD': 'prc_rentabilidad',
            'PRC RENTABILIDAD': 'prc_rentabilidad',
            '% RENT': 'prc_rentabilidad',
            '%RENT': 'prc_rentabilidad',
            'MARGEN': 'prc_rentabilidad',
            'MES': 'mes'
        }

        # Mapear solo con coincidencias EXACTAS
        rename_dict = {}
        columnas_ya_mapeadas = set()

        for col in df.columns:
            col_upper = str(col).upper().strip()
            if col_upper in mapeo_exacto:
                destino = mapeo_exacto[col_upper]
                # Evitar duplicados - si ya mapeamos a este destino, agregar sufijo
                if destino in columnas_ya_mapeadas:
                    print(f"    [WARN] Columna duplicada ignorada: {col} -> {destino}")
                    continue
                rename_dict[col] = destino
                columnas_ya_mapeadas.add(destino)

        df = df.rename(columns=rename_dict)

        print(f"    Columnas mapeadas: {list(rename_dict.values())}")

        print(f"    Columnas finales: {df.columns.tolist()[:10]}")

        # =========================================================================
        # 4. CONVERTIR COLUMNAS NUMERICAS
        # =========================================================================

        columnas_numericas = ['cant_venta', 'total_venta', 'cant_nc', 'total_nc',
                             'cant_devolucion', 'total_devolucion', 'cant_neto', 'total_neto',
                             'costo_venta', 'rentabilidad', 'prc_rentabilidad']

        for col in columnas_numericas:
            if col in df.columns:
                try:
                    df[col] = df[col].astype(str)
                    df[col] = df[col].str.replace(',', '').str.replace('$', '').str.replace('%', '').str.strip()
                    df[col] = df[col].replace(['nan', 'None', '', 'NaN'], '0')
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                except Exception as e:
                    print(f"    [WARN] Error convirtiendo {col}: {e}")
                    df[col] = 0.0
            else:
                df[col] = 0.0

        # =========================================================================
        # 5. CALCULOS ADICIONALES
        # =========================================================================

        # Si no hay cant_neto, calcularlo
        if df['cant_neto'].sum() == 0 and df['cant_venta'].sum() > 0:
            df['cant_neto'] = df['cant_venta'] - df['cant_devolucion']

        if df['total_neto'].sum() == 0 and df['total_venta'].sum() > 0:
            df['total_neto'] = df['total_venta'] - df['total_devolucion']

        # Calcular rentabilidad si no existe
        if df['rentabilidad'].sum() == 0:
            df['rentabilidad'] = df['total_neto'] - df['costo_venta']

        # Calcular porcentaje de rentabilidad
        df['prc_rentabilidad'] = np.where(
            df['total_neto'] > 0,
            (df['rentabilidad'] / df['total_neto']) * 100,
            0
        )

        # =========================================================================
        # 6. AGREGAR METADATOS
        # =========================================================================

        devolucion_excede_venta = (
            (df['cant_devolucion'] > df['cant_venta'])
            | (df['total_devolucion'] > df['total_venta'])
        )
        neto_negativo = (df['cant_neto'] < 0) | (df['total_neto'] < 0)

        df['es_dato_calidado'] = True
        df['flag_outlier'] = devolucion_excede_venta | neto_negativo
        df['flag_valor_nulo'] = df.isnull().any(axis=1)
        df['fecha_carga'] = datetime.now()

        # Verificar y limpiar columna MES (cada fila tiene su propio MES de la columna 16)
        if 'mes' in df.columns:
            # Limpiar valores de MES
            df['mes'] = df['mes'].astype(str).str.strip().str.upper()
            # Filtrar valores inválidos (headers, None, etc.)
            df['mes'] = df['mes'].replace(['MES', 'NONE', 'NAN', ''], np.nan)
            # Contar valores válidos
            mes_validos = df['mes'].dropna().value_counts()
            if len(mes_validos) > 0:
                print(f"    Distribución de MES: {dict(mes_validos)}")
            else:
                print(f"    [WARN] No se encontraron valores de MES válidos")
                df['mes'] = 'ENERO'  # Valor por defecto
        else:
            print(f"    [WARN] Columna MES no encontrada, asignando valor por defecto")
            df['mes'] = 'ENERO'

        # Asignar AÑO extraído del encabezado del reporte
        if anio_extraido:
            df['anio'] = anio_extraido
            print(f"    Año asignado a todos los registros: {anio_extraido}")
        else:
            df['anio'] = '2026'  # Valor por defecto basado en los datos
            print(f"    [WARN] Año no encontrado, asignando valor por defecto: 2026")

        # Columnas finales para Silver
        columnas_finales = [
            'centro_costo', 'codigo_producto', 'codigo_alterno', 'producto', 'mes', 'anio',
            'cant_venta', 'total_venta', 'cant_nc', 'total_nc',
            'cant_devolucion', 'total_devolucion', 'cant_neto', 'total_neto',
            'costo_venta', 'rentabilidad', 'prc_rentabilidad',
            'es_dato_calidado', 'flag_outlier', 'flag_valor_nulo', 'fecha_carga'
        ]

        # Asegurar que todas las columnas existen
        for col in columnas_finales:
            if col not in df.columns:
                df[col] = None

        df_export = df[columnas_finales].copy()

        # =========================================================================
        # 7. NORMALIZAR TEXTOS (IMPORTANTE: evita inconsistencias)
        # =========================================================================
        if 'centro_costo' in df_export.columns:
            df_export['centro_costo'] = df_export['centro_costo'].astype(str).str.strip().str.lower()

        df_export['pipeline_id'] = pipeline_id
        df_export['batch_id'] = batch_id
        df_export = exclude_kronos_unassigned_zones_v3(
            df_export,
            'centro_costo',
            key_ventas,
        )

        # Estadisticas
        print(f"\n    === RESUMEN ===")
        print(f"    Registros finales: {len(df_export)}")
        print(f"    Centros de costo unicos: {df_export['centro_costo'].nunique()}")
        print(f"    Productos unicos: {df_export['producto'].nunique()}")
        print(f"    Total ventas: ${df_export['total_venta'].sum():,.2f}")
        print(f"    Meses: {df_export['mes'].value_counts().to_dict()}")
        print(f"    Año: {df_export['anio'].unique()}")

        resultados['kronos_ventas'] = df_export
    elif 'kronos_ventas' not in resultados:
        print("[WARN] No se encontro tabla de ventas Kronos en los datos")

    # =========================================================================
    # [2] TRANSFORMAR: QuickBooks Produccion
    # Convierte lineas operativas en un dataset consolidado por orden.
    # =========================================================================

    if 'quickbooks_produccion_raw' in dfs:
        print(f"\n[2] Transformando quickbooks_produccion_raw...")

        df_prod = dfs['quickbooks_produccion_raw']
        if isinstance(df_prod, list):
            df_prod = pd.DataFrame(df_prod)
        elif isinstance(df_prod, pd.DataFrame):
            df_prod = df_prod.copy()
        else:
            df_prod = pd.DataFrame()

        if len(df_prod) > 0:
            print(f"    Filas iniciales: {len(df_prod)}")

            # Estandarizar nombres esperados (compatibilidad de fuentes)
            if 'qty_planificada' not in df_prod.columns and 'qty_pedida' in df_prod.columns:
                df_prod['qty_planificada'] = df_prod['qty_pedida']
            if 'qty_despachada' not in df_prod.columns:
                if 'qty_fabricada' in df_prod.columns:
                    df_prod['qty_despachada'] = df_prod['qty_fabricada']
                elif 'qty_liberada' in df_prod.columns:
                    df_prod['qty_despachada'] = df_prod['qty_liberada']
                else:
                    df_prod['qty_despachada'] = 0
            if 'numero_orden' not in df_prod.columns and 'numero' in df_prod.columns:
                df_prod['numero_orden'] = df_prod['numero']

            # Normalizacion minima de texto/identificadores
            for col in ['idsale', 'idsales', 'numero_orden', 'estado', 'cliente']:
                if col in df_prod.columns:
                    df_prod[col] = df_prod[col].astype(str).str.strip()

            # Eliminar filas sin identificador o fecha valida
            if 'fecha' in df_prod.columns:
                df_prod['fecha'] = pd.to_datetime(df_prod['fecha'], errors='coerce')
            if 'fecha_creacion' in df_prod.columns:
                df_prod['fecha_creacion'] = pd.to_datetime(df_prod['fecha_creacion'], errors='coerce')

            id_col = None
            for cand in ['idsale', 'idsales', 'numero_orden', 'numero', 'id_registro']:
                if cand in df_prod.columns:
                    id_col = cand
                    break
            if id_col is not None:
                df_prod = df_prod[
                    df_prod[id_col].notna()
                    & (df_prod[id_col] != '')
                    & (df_prod[id_col].str.lower() != 'nan')
                    & (df_prod[id_col].str.lower() != 'none')
                ].copy()
            if 'fecha' in df_prod.columns:
                df_prod = df_prod[df_prod['fecha'].notna()].copy()

            # Convertir columnas numericas
            for col in ['numitems', 'numitemsprocesados', 'num_lineas', 'qty_planificada', 'qty_despachada']:
                if col in df_prod.columns:
                    df_prod[col] = pd.to_numeric(df_prod[col], errors='coerce').fillna(0)

            # Consolidar duplicados por orden (si existen por reingestas)
            before_dups = len(df_prod)
            if id_col is not None:
                agg_num = {
                    'numitems': 'max',
                    'numitemsprocesados': 'max',
                    'num_lineas': 'max',
                    'qty_planificada': 'sum',
                    'qty_despachada': 'sum',
                    'fecha': 'max',
                    'fecha_creacion': 'max',
                    'numero_orden': 'first',
                    'estado': 'first',
                    'cliente': 'first',
                }
                agg_num = {k: v for k, v in agg_num.items() if k in df_prod.columns}
                df_prod = df_prod.groupby(id_col, as_index=False).agg(agg_num)
            print(f"    Duplicados consolidados quickbooks_produccion: {before_dups - len(df_prod)}")

            # Calcular desviacion
            df_prod['desviacion_absoluta'] = df_prod['qty_planificada'] - df_prod['qty_despachada']
            df_prod['desviacion_porcentual'] = np.where(
                df_prod['qty_planificada'] > 0,
                (df_prod['desviacion_absoluta'] / df_prod['qty_planificada']) * 100,
                0
            )
            df_prod['tasa_cumplimiento'] = np.where(
                df_prod['qty_planificada'] > 0,
                (df_prod['qty_despachada'] / df_prod['qty_planificada']) * 100,
                0
            )

            # Limitar rangos para ajustarse al tipo NUMERIC(8,4) en Silver
            df_prod['desviacion_porcentual'] = pd.to_numeric(df_prod['desviacion_porcentual'], errors='coerce').fillna(0).clip(-9999, 9999)
            df_prod['tasa_cumplimiento'] = pd.to_numeric(df_prod['tasa_cumplimiento'], errors='coerce').fillna(0).clip(0, 100)

            # Clasificar cumplimiento
            def clasificar_cumplimiento(tasa):
                if tasa >= 95:
                    return 'OPTIMO'
                elif tasa >= 80:
                    return 'ACEPTABLE'
                elif tasa >= 50:
                    return 'DEFICIENTE'
                else:
                    return 'CRITICO'

            df_prod['clasificacion_cumplimiento'] = df_prod['tasa_cumplimiento'].apply(clasificar_cumplimiento)

            # Estandarizar nombres al esquema silver.quickbooks_produccion
            rename_cols = {
                'numero': 'numero_orden',
                'status': 'status_orden',
                'numitems': 'items_planificados',
                'numitemsprocesados': 'items_procesados',
                'qty_planificada': 'qty_total_planificada',
                'qty_despachada': 'qty_total_despachada',
            }
            rename_cols = {k: v for k, v in rename_cols.items() if k in df_prod.columns}
            df_prod = df_prod.rename(columns=rename_cols)

            if 'items_pendientes' not in df_prod.columns:
                if 'items_planificados' in df_prod.columns and 'items_procesados' in df_prod.columns:
                    df_prod['items_pendientes'] = (df_prod['items_planificados'] - df_prod['items_procesados']).clip(lower=0)
                else:
                    df_prod['items_pendientes'] = 0

            if 'qty_pendiente' not in df_prod.columns:
                if 'qty_total_planificada' in df_prod.columns and 'qty_total_despachada' in df_prod.columns:
                    df_prod['qty_pendiente'] = (df_prod['qty_total_planificada'] - df_prod['qty_total_despachada']).clip(lower=0)
                else:
                    df_prod['qty_pendiente'] = 0

            if 'flag_orden_atrasada' not in df_prod.columns:
                df_prod['flag_orden_atrasada'] = False

            # Metadatos
            df_prod['es_dato_calidado'] = True
            df_prod['fecha_carga'] = datetime.now()
            df_prod['pipeline_id'] = pipeline_id
            df_prod['batch_id'] = batch_id

            silver_cols = [
                'idsales', 'idsale', 'numero_orden',
                'fecha', 'fecha_creacion', 'estado', 'cliente',
                'idcliente', 'status_orden', 'items_planificados',
                'items_procesados', 'items_pendientes', 'num_lineas',
                'qty_total_planificada', 'qty_total_despachada',
                'qty_pendiente', 'desviacion_absoluta',
                'desviacion_porcentual', 'tasa_cumplimiento',
                'clasificacion_cumplimiento',
                'es_dato_calidado', 'flag_orden_atrasada',
                'fecha_carga', 'pipeline_id', 'batch_id',
            ]
            for c in silver_cols:
                if c not in df_prod.columns:
                    df_prod[c] = None
            df_prod = df_prod[silver_cols].copy()

            resultados['quickbooks_produccion'] = df_prod
            print(f"    Registros finales: {len(df_prod)}")
            print(f"    Tasa cumplimiento promedio: {df_prod['tasa_cumplimiento'].mean():.2f}%")

    # =========================================================================
    # [3] TRANSFORMAR: QuickBooks Ventas
    # Consolida detalle por identificador robusto y calcula cumplimiento.
    # =========================================================================

    if 'quickbooks_ventas_raw' in dfs:
        print(f"\n[3] Transformando quickbooks_ventas_raw...")

        df_ventas = dfs['quickbooks_ventas_raw']
        if isinstance(df_ventas, list):
            df_ventas = pd.DataFrame(df_ventas)
        elif isinstance(df_ventas, pd.DataFrame):
            df_ventas = df_ventas.copy()
        else:
            df_ventas = pd.DataFrame()

        if len(df_ventas) > 0:
            print(f"    Filas iniciales: {len(df_ventas)}")

            # Normalizacion de texto/identificadores para evitar falsos
            # duplicados por espacios/capitalizacion del origen.
            for col in ['idsale', 'idsales', 'numero', 'estado', 'cliente', 'status', '_status']:
                if col in df_ventas.columns:
                    df_ventas[col] = df_ventas[col].astype(str).str.strip()
            if 'fecha' in df_ventas.columns:
                df_ventas['fecha'] = pd.to_datetime(df_ventas['fecha'], errors='coerce')

            # Canonizar estado: legado `_status` se estandariza en `status`.
            if 'status' in df_ventas.columns and '_status' in df_ventas.columns:
                status_clean = df_ventas['status'].replace({'nan': '', 'none': '', 'None': '', 'NaN': ''})
                legacy_clean = df_ventas['_status'].replace({'nan': '', 'none': '', 'None': '', 'NaN': ''})
                df_ventas['status'] = status_clean.mask(status_clean == '', legacy_clean)
            elif '_status' in df_ventas.columns:
                df_ventas['status'] = df_ventas['_status'].replace({'nan': '', 'none': '', 'None': '', 'NaN': ''})

            # Construir identificador robusto de venta.
            # Prioridad: idsales -> idsale -> numero.
            idsales = df_ventas['idsales'].astype(str).str.strip() if 'idsales' in df_ventas.columns else pd.Series('', index=df_ventas.index)
            idsale = df_ventas['idsale'].astype(str).str.strip() if 'idsale' in df_ventas.columns else pd.Series('', index=df_ventas.index)
            numero = df_ventas['numero'].astype(str).str.strip() if 'numero' in df_ventas.columns else pd.Series('', index=df_ventas.index)

            idsales = idsales.replace({'nan': '', 'none': '', 'None': '', 'NaN': ''})
            idsale = idsale.replace({'nan': '', 'none': '', 'None': '', 'NaN': ''})
            numero = numero.replace({'nan': '', 'none': '', 'None': '', 'NaN': ''})

            df_ventas['sale_key'] = idsales
            df_ventas.loc[df_ventas['sale_key'] == '', 'sale_key'] = idsale
            df_ventas.loc[df_ventas['sale_key'] == '', 'sale_key'] = numero

            before_filter = len(df_ventas)
            df_ventas = df_ventas[df_ventas['sale_key'] != ''].copy()
            print(f"    Filas removidas sin identificador de venta: {before_filter - len(df_ventas)}")

            if 'fecha' in df_ventas.columns:
                df_ventas = df_ventas[df_ventas['fecha'].notna()].copy()

            # Convertir columnas numericas
            for col in ['numitems', 'numitemsprocesados', 'num_lineas', 'productos_unicos', 'qty_pedida', 'qty_despachada']:
                if col in df_ventas.columns:
                    df_ventas[col] = pd.to_numeric(df_ventas[col], errors='coerce').fillna(0)

            for col in ['numitems', 'numitemsprocesados', 'num_lineas', 'productos_unicos']:
                if col in df_ventas.columns:
                    df_ventas[col] = pd.to_numeric(df_ventas[col], errors='coerce').fillna(0).astype(int)

            before_dups_v = len(df_ventas)
            if 'sale_key' in df_ventas.columns:
                agg_v = {
                    'numitems': 'max',
                    'numitemsprocesados': 'max',
                    'num_lineas': 'max',
                    'productos_unicos': 'max',
                    'qty_pedida': 'sum',
                    'qty_despachada': 'sum',
                    'fecha': 'max',
                    'numero': 'first',
                    'estado': 'first',
                    'cliente': 'first',
                }
                agg_v = {k: v for k, v in agg_v.items() if k in df_ventas.columns}
                df_ventas = df_ventas.groupby('sale_key', as_index=False).agg(agg_v)
            print(f"    Duplicados consolidados quickbooks_ventas: {before_dups_v - len(df_ventas)}")

            if before_dups_v > 0 and len(df_ventas) == 0:
                raise RuntimeError(
                    'Transformacion quickbooks_ventas produjo 0 filas desde un origen no vacio. '
                    'Revisar reglas de identificador/filtro.'
                )

            # Calcular metricas
            df_ventas['qty_pendiente'] = df_ventas['qty_pedida'] - df_ventas['qty_despachada']
            df_ventas['tasa_cumplimiento'] = np.where(
                df_ventas['qty_pedida'] > 0,
                (df_ventas['qty_despachada'] / df_ventas['qty_pedida']) * 100,
                0
            )
            df_ventas['tasa_cumplimiento'] = pd.to_numeric(df_ventas['tasa_cumplimiento'], errors='coerce').fillna(0).clip(0, 100)

            # Metadatos
            df_ventas['es_dato_calidado'] = True
            df_ventas['fecha_carga'] = datetime.now()
            df_ventas['pipeline_id'] = pipeline_id
            df_ventas['batch_id'] = batch_id

            silver_cols_ventas = [
                'idsales', 'idsale', 'numero',
                'fecha', 'estado', 'cliente',
                'idcliente', 'status',
                'numitems', 'numitemsprocesados',
                'num_lineas', 'productos_unicos',
                'qty_pedida', 'qty_despachada',
                'qty_pendiente', 'tasa_cumplimiento',
                'es_dato_calidado',
                'fecha_carga', 'pipeline_id', 'batch_id',
            ]
            for c in silver_cols_ventas:
                if c not in df_ventas.columns:
                    df_ventas[c] = None
            df_ventas = df_ventas[silver_cols_ventas].copy()

            resultados['quickbooks_ventas'] = df_ventas
            print(f"    Registros finales: {len(df_ventas)}")
            print(f"    Qty total pedida: {df_ventas['qty_pedida'].sum():,.0f}")
            print(f"    Qty total despachada: {df_ventas['qty_despachada'].sum():,.0f}")

    # =========================================================================
    # TRANSFORMAR: Transacciones reales para Apriori (ticket-item)
    # =========================================================================

    if 'kronos_ventas_detalle_raw' in dfs:
        print(f"\n[4] Transformando kronos_ventas_detalle_raw para Apriori...")

        df_tx = dfs['kronos_ventas_detalle_raw']
        if isinstance(df_tx, list):
            df_tx = pd.DataFrame(df_tx)
        elif isinstance(df_tx, pd.DataFrame):
            df_tx = df_tx.copy()
        else:
            df_tx = pd.DataFrame()

        if len(df_tx) > 0:
            # Normalizacion minima
            df_tx['fecha'] = pd.to_datetime(df_tx.get('fecha_factura'), errors='coerce')
            id_factura = df_tx.get('id_factura').astype(str).str.strip()
            numero_factura = df_tx.get('numero_factura').astype(str).str.strip()
            df_tx['id_factura'] = np.where(
                id_factura.notna()
                & (id_factura != '')
                & (id_factura.str.lower() != 'nan')
                & (id_factura.str.lower() != 'none'),
                id_factura,
                numero_factura,
            )
            df_tx['producto_raw'] = df_tx.get('descripcion_producto').astype(str).str.strip()
            df_tx['agencia_raw'] = df_tx.get('id_sucursal').astype(str).str.strip()
            df_tx['cliente_raw'] = df_tx.get('nombre_comercial').astype(str).str.strip()
            qty_tx = parse_numeric_robusto(df_tx.get('cantidad')).fillna(0)
            mask_qty_tx_x100 = (np.abs(qty_tx) >= 100) & ((np.abs(qty_tx) % 100) < 1e-9)
            df_tx['qty'] = np.where(mask_qty_tx_x100, qty_tx / 100, qty_tx)
            valor_unitario_tx = parse_numeric_robusto(df_tx.get('valor_unitario')).fillna(0)
            valor_total_tx = parse_numeric_robusto(df_tx.get('valor_total')).fillna(0)

            precio_imp_tx = np.where(df_tx['qty'] > 0, valor_total_tx / df_tx['qty'], np.nan)
            ratio_tx = np.where(
                np.isfinite(precio_imp_tx) & (precio_imp_tx > 0),
                valor_unitario_tx / precio_imp_tx,
                np.nan,
            )
            mask_tx_x100 = np.isfinite(ratio_tx) & (ratio_tx >= 80) & (ratio_tx <= 120)
            valor_unitario_tx_norm = np.where(mask_tx_x100, valor_unitario_tx / 100, valor_unitario_tx)

            denom_tx = valor_unitario_tx_norm * df_tx['qty']
            ratio_total_tx = np.where(
                (denom_tx > 0) & np.isfinite(denom_tx),
                valor_total_tx / denom_tx,
                np.nan,
            )
            mask_total_tx_x100 = np.isfinite(ratio_total_tx) & (ratio_total_tx >= 0.8) & (ratio_total_tx <= 1.2)

            df_tx['amount'] = np.where(mask_total_tx_x100, valor_total_tx / 100, valor_total_tx)
            df_tx['tipo_doc'] = df_tx.get('tipo').astype(str).str.upper().str.strip()

            # Filtrar lineas utiles para market basket
            df_tx = df_tx[
                df_tx['fecha'].notna()
                & df_tx['id_factura'].notna()
                & (df_tx['id_factura'] != '')
                & (df_tx['id_factura'].str.lower() != 'none')
                & (df_tx['id_factura'].str.lower() != 'nan')
                & df_tx['producto_raw'].notna()
                & (df_tx['producto_raw'] != '')
                & (df_tx['qty'] > 0)
                & (df_tx['amount'] > 0)
                & (df_tx['tipo_doc'].str.contains('FACTURA', na=False))
            ].copy()

            # Definicion de transaccion real (factura)
            df_tx['transaccion_id'] = df_tx['id_factura'].astype(str)
            df_tx['agencia'] = df_tx['agencia_raw'].replace({'nan': 'sin_agencia', '': 'sin_agencia'})
            df_tx['cliente'] = df_tx['cliente_raw'].replace({'nan': 'sin_cliente', '': 'sin_cliente'})

            def limpiar_producto(texto):
                t = str(texto).strip()
                partes = [p.strip() for p in t.split(':') if p is not None]
                nombre = partes[-1].strip() if len(partes) > 0 else t
                if not nombre:
                    nombre = t
                return nombre

            df_tx['producto'] = df_tx['producto_raw'].apply(limpiar_producto)
            df_tx['categoria'] = df_tx.get('nombre_subgrupo').astype(str).str.upper().str.strip()
            df_tx['categoria'] = df_tx['categoria'].replace({'NAN': 'SIN_CATEGORIA', '': 'SIN_CATEGORIA'})
            df_tx['fuente'] = 'kronos'
            df_tx['pipeline_id'] = pipeline_id
            df_tx['batch_id'] = batch_id
            df_tx['fecha_carga'] = datetime.now()

            # Evitar duplicado exacto en la misma transaccion
            df_tx = df_tx.drop_duplicates(subset=['transaccion_id', 'producto'])

            out_cols = [
                'transaccion_id', 'fecha', 'agencia', 'cliente',
                'producto', 'categoria', 'qty', 'amount',
                'fuente', 'pipeline_id', 'batch_id', 'fecha_carga',
            ]
            resultados['apriori_transacciones'] = df_tx[out_cols].copy()

            print(f"    Registros finales Apriori Kronos: {len(df_tx)}")
            print(f"    Transacciones unicas: {df_tx['transaccion_id'].nunique()}")
            print(f"    Productos unicos: {df_tx['producto'].nunique()}")

    if 'quickbooks_sales_local_raw' in dfs and 'apriori_transacciones' not in resultados:
        print(f"\n[4] Transformando quickbooks_sales_local_raw para Apriori...")

        df_tx = dfs['quickbooks_sales_local_raw']
        if isinstance(df_tx, list):
            df_tx = pd.DataFrame(df_tx)
        elif isinstance(df_tx, pd.DataFrame):
            df_tx = df_tx.copy()
        else:
            df_tx = pd.DataFrame()

        if len(df_tx) > 0:
            # Normalizacion minima
            df_tx['fecha'] = pd.to_datetime(df_tx.get('fecha'), errors='coerce')
            df_tx['numero'] = df_tx.get('numero').astype(str).str.strip()
            df_tx['item'] = df_tx.get('item').astype(str).str.strip()
            df_tx['asesor'] = df_tx.get('asesor').astype(str).str.strip().str.lower()
            df_tx['cliente'] = df_tx.get('cliente').astype(str).str.strip()
            df_tx['qty'] = pd.to_numeric(df_tx.get('qty'), errors='coerce').fillna(0)
            df_tx['amount'] = pd.to_numeric(df_tx.get('amount'), errors='coerce').fillna(0)

            # Filtrar lineas no utiles
            df_tx = df_tx[
                df_tx['fecha'].notna()
                & df_tx['numero'].notna()
                & (df_tx['numero'] != '')
                & df_tx['item'].notna()
                & (df_tx['item'] != '')
                & (df_tx['qty'] > 0)
            ].copy()

            # Definicion de transaccion real (ticket por dia)
            df_tx['transaccion_id'] = (
                df_tx['numero'].astype(str)
                + '-'
                + df_tx['fecha'].dt.strftime('%Y%m%d')
            )
            df_tx['agencia'] = df_tx['asesor'].replace({'nan': 'sin_agencia', '': 'sin_agencia'})
            raw_item = df_tx['item'].astype(str)

            # Depuracion de nombre de producto para analitica y dashboard
            def limpiar_producto(texto):
                t = str(texto).strip()
                partes = [p.strip() for p in t.split(':') if p is not None]
                nombre = partes[-1].strip() if len(partes) > 0 else t
                if not nombre:
                    nombre = t
                return nombre

            def extraer_categoria(texto):
                t = str(texto).strip()
                partes = [p.strip() for p in t.split(':') if p is not None]
                if len(partes) >= 2:
                    return partes[-2].upper()
                return 'SIN_CATEGORIA'

            df_tx['producto'] = raw_item.apply(limpiar_producto)
            df_tx['categoria'] = raw_item.apply(extraer_categoria)
            df_tx['fuente'] = 'quickbooks'
            df_tx['pipeline_id'] = pipeline_id
            df_tx['batch_id'] = batch_id
            df_tx['fecha_carga'] = datetime.now()

            # Evitar duplicado exacto en la misma transaccion
            df_tx = df_tx.drop_duplicates(subset=['transaccion_id', 'producto'])

            out_cols = [
                'transaccion_id', 'fecha', 'agencia', 'cliente',
                'producto', 'categoria', 'qty', 'amount',
                'fuente', 'pipeline_id', 'batch_id', 'fecha_carga',
            ]
            resultados['apriori_transacciones'] = df_tx[out_cols].copy()

            print(f"    Registros finales Apriori: {len(df_tx)}")
            print(f"    Transacciones unicas: {df_tx['transaccion_id'].nunique()}")
            print(f"    Productos unicos: {df_tx['producto'].nunique()}")

    # =========================================================================
    # 5. TRANSFORMAR: Catalogo EAN limpio
    # =========================================================================
    if 'quickbooks_catalogo_ean_raw' in dfs:
        print(f"\n[5] Transformando quickbooks_catalogo_ean_raw...")
        df_cat = dfs['quickbooks_catalogo_ean_raw']
        if isinstance(df_cat, list):
            df_cat = pd.DataFrame(df_cat)
        elif isinstance(df_cat, pd.DataFrame):
            df_cat = df_cat.copy()
        else:
            df_cat = pd.DataFrame()

        if len(df_cat) > 0:
            for col in ['item', 'description', 'ean13', 'ean14', 'um']:
                if col not in df_cat.columns:
                    df_cat[col] = ''
                df_cat[col] = df_cat[col].astype(str).str.strip().replace({'nan': ''})

            if 'price' not in df_cat.columns:
                df_cat['price'] = 0
            df_cat['price'] = pd.to_numeric(df_cat['price'], errors='coerce').fillna(0)

            df_cat = df_cat[df_cat['item'].ne('')].copy()

            df_cat['item_tail'] = df_cat['item'].str.split(':').str[-1].str.strip()
            code_cat = (
                df_cat['item']
                .str.extract(r'\((\d+)\)')[0]
                .fillna(df_cat['item'].str.extract(r'(\d+)$')[0])
            )
            df_cat['codigo_producto'] = code_cat.apply(
                lambda x: str(x).strip().zfill(4)
                if pd.notna(x) and str(x).strip() not in {'', 'nan', 'None'}
                else ''
            )
            df_cat['tipo_producto'] = df_cat['item'].str.split(':').str[0].str.upper().str.strip()
            df_cat.loc[~df_cat['tipo_producto'].isin(['PT', 'PP']), 'tipo_producto'] = 'OTRO'

            df_cat['ean13'] = df_cat['ean13'].str.replace(r'\D', '', regex=True)
            df_cat['ean14'] = df_cat['ean14'].str.replace(r'\D', '', regex=True)
            df_cat['flag_ean13_valido'] = df_cat['ean13'].str.len().eq(13)

            genericos = {'', 'PT', 'PP', 'PRODUCTO TERMINADO', '1 CONDIMENSA', 'NONE', 'NAN'}
            df_cat['flag_desc_generica'] = df_cat['description'].str.upper().isin(genericos)
            df_cat['producto_dashboard'] = np.where(
                ~df_cat['flag_desc_generica'] & df_cat['description'].ne(''),
                df_cat['description'],
                df_cat['item_tail'],
            )

            df_cat['fecha_carga'] = datetime.now()
            df_cat['pipeline_id'] = pipeline_id
            df_cat['batch_id'] = batch_id

            keep_cols = [
                'item', 'item_tail', 'description', 'producto_dashboard', 'tipo_producto',
                'codigo_producto', 'ean13', 'ean14', 'um', 'price',
                'flag_ean13_valido', 'flag_desc_generica', 'fecha_carga', 'pipeline_id', 'batch_id'
            ]
            for c in keep_cols:
                if c not in df_cat.columns:
                    df_cat[c] = None

            resultados['catalogo_ean_clean'] = df_cat[keep_cols].copy()
            print(f"    Registros catalogo limpio: {len(df_cat)}")

    # =========================================================================
    # 6. TRANSFORMAR: Ventas econespecias mensual limpia
    # =========================================================================
    if 'quickbooks_ventas_econespecias_raw' in dfs:
        print(f"\n[6] Transformando quickbooks_ventas_econespecias_raw...")
        df_ve = dfs['quickbooks_ventas_econespecias_raw']
        if isinstance(df_ve, list):
            df_ve = pd.DataFrame(df_ve)
        elif isinstance(df_ve, pd.DataFrame):
            df_ve = df_ve.copy()
        else:
            df_ve = pd.DataFrame()

        if len(df_ve) > 0:
            rename_map = {'recuento de cliente': 'recuento_cliente', 'año': 'anio', 'ano': 'anio'}
            for old, new in rename_map.items():
                if old in df_ve.columns and new not in df_ve.columns:
                    df_ve[new] = df_ve[old]

            for c in ['marca', 'familia', 'producto', 'mes']:
                if c not in df_ve.columns:
                    df_ve[c] = ''
                df_ve[c] = df_ve[c].astype(str).str.strip().replace({'nan': ''})

            for c in ['recuento_cliente', 'cantidad', 'ventas', 'anio']:
                if c not in df_ve.columns:
                    df_ve[c] = 0
                df_ve[c] = pd.to_numeric(df_ve[c], errors='coerce').fillna(0)

            month_map = {
                'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6,
                'julio': 7, 'agosto': 8, 'septiembre': 9, 'setiembre': 9,
                'octubre': 10, 'noviembre': 11, 'diciembre': 12,
            }
            if 'periodo' not in df_ve.columns:
                df_ve['mes_num'] = df_ve['mes'].str.lower().map(month_map)
                df_ve['periodo'] = pd.to_datetime(
                    dict(year=df_ve['anio'], month=df_ve['mes_num'], day=1), errors='coerce'
                )
            else:
                df_ve['periodo'] = pd.to_datetime(df_ve['periodo'], errors='coerce')

            df_ve = df_ve[df_ve['periodo'].notna() & df_ve['producto'].ne('')].copy()

            code_ve = df_ve['producto'].str.extract(r'\((\d+)\)')[0]
            df_ve['codigo_producto'] = code_ve.apply(
                lambda x: str(x).strip().zfill(4)
                if pd.notna(x) and str(x).strip() not in {'', 'nan', 'None'}
                else ''
            )

            df_ve = (
                df_ve.groupby(['marca', 'familia', 'producto', 'codigo_producto', 'periodo'], as_index=False)
                .agg(
                    anio=('anio', 'max'),
                    mes=('mes', 'first'),
                    recuento_cliente=('recuento_cliente', 'sum'),
                    cantidad=('cantidad', 'sum'),
                    ventas=('ventas', 'sum'),
                )
            )

            df_ve['fecha_carga'] = datetime.now()
            df_ve['pipeline_id'] = pipeline_id
            df_ve['batch_id'] = batch_id

            resultados['ventas_econespecias_mensual_clean'] = df_ve.copy()
            print(f"    Registros ventas mensual limpia: {len(df_ve)}")

    # =========================================================================
    # 7. DIMENSION CANONICA + BASE FORECASTING
    # =========================================================================
    if 'catalogo_ean_clean' in resultados and 'ventas_econespecias_mensual_clean' in resultados:
        print(f"\n[7] Construyendo dim_producto_canonico y forecasting_base_mensual_v1...")
        cat = resultados['catalogo_ean_clean'].copy()
        ven = resultados['ventas_econespecias_mensual_clean'].copy()

        cat['score'] = (
            cat['flag_ean13_valido'].astype(int) * 4
            + (~cat['flag_desc_generica']).astype(int) * 3
            + cat['description'].ne('').astype(int) * 2
            + cat['item_tail'].ne('').astype(int)
        )
        cat = cat.sort_values(['codigo_producto', 'score'], ascending=[True, False])
        dim = cat.drop_duplicates(subset=['codigo_producto']).copy()

        conflict = (
            cat[cat['flag_ean13_valido']]
            .groupby('ean13', as_index=False)['producto_dashboard']
            .nunique()
            .rename(columns={'producto_dashboard': 'n_names'})
        )
        conflict['flag_conflicto_ean13'] = conflict['n_names'] > 1
        dim = dim.merge(conflict[['ean13', 'flag_conflicto_ean13']], on='ean13', how='left')
        dim['flag_conflicto_ean13'] = dim['flag_conflicto_ean13'].fillna(False)

        codes_sales = set(ven['codigo_producto'].astype(str))
        dim['estado_match'] = np.where(
            dim['codigo_producto'].astype(str).isin(codes_sales),
            'exacto',
            'sin_match',
        )

        dim = dim.rename(
            columns={
                'item': 'item_canonico',
                'description': 'description_canonica',
            }
        )
        dim['tipo_producto'] = dim['tipo_producto'].fillna('PT').astype(str).str.upper().str.strip()
        dim['tipo_producto'] = np.where(dim['tipo_producto'].eq('PP'), 'PP', 'PT')
        dim_cols = [
            'codigo_producto', 'ean13', 'ean14', 'item_canonico', 'description_canonica',
            'producto_dashboard', 'tipo_producto', 'estado_match', 'flag_conflicto_ean13',
            'fecha_carga', 'pipeline_id', 'batch_id'
        ]
        for c in dim_cols:
            if c not in dim.columns:
                dim[c] = None
        dim = dim[dim_cols].copy()
        resultados['dim_producto_canonico'] = dim

        base = ven.merge(dim, on='codigo_producto', how='left', suffixes=('', '_dim'))
        base['producto_item'] = base['item_canonico'].fillna(base['producto'])
        base['producto_dashboard'] = base['producto_dashboard'].fillna(base['producto'])
        base['tipo_producto'] = base['tipo_producto'].fillna('OTRO').astype(str).str.upper().str.strip()
        base['tipo_producto_original'] = base['tipo_producto']

        # Resolver solapamientos OTRO vs PT por nombre normalizado: mantener PT.
        base['nombre_norm_tipo'] = base['producto_dashboard'].apply(normalize_product_name)
        pt_names = set(base.loc[base['tipo_producto_original'] == 'PT', 'nombre_norm_tipo'])
        overlap_mask = (
            base['tipo_producto_original'].eq('OTRO')
            & base['nombre_norm_tipo'].isin(pt_names)
        )
        overlap_removed = int(overlap_mask.sum())
        if overlap_removed > 0:
            base = base.loc[~overlap_mask].copy()

        # Regla solicitada: en ventas_econespecias solo PT y OTRO.
        base['tipo_producto'] = np.where(base['tipo_producto_original'].eq('PT'), 'PT', 'OTRO')

        base['categoria_producto'] = base['familia'].astype(str).str.upper().str.strip()
        base['ean13'] = base['ean13'].fillna('')
        base['flag_catalogo_conflicto'] = base['flag_conflicto_ean13'].fillna(False)

        base['periodo'] = pd.to_datetime(base['periodo'], errors='coerce')
        max_period = base['periodo'].max()
        key = np.where(base['ean13'].astype(str).str.len() == 13, base['ean13'], base['codigo_producto'])
        base['prod_key'] = key

        last_p = base.groupby('prod_key', as_index=False)['periodo'].max().rename(columns={'periodo': 'last_period'})
        base = base.merge(last_p, on='prod_key', how='left')
        base['months_since_last'] = (
            (max_period.year - base['last_period'].dt.year) * 12
            + (max_period.month - base['last_period'].dt.month)
        )

        month_act = (
            base[base['cantidad'] > 0]
            .groupby(['prod_key', base['periodo'].dt.month], as_index=False)
            .size()
            .groupby('prod_key', as_index=False)
            .size()
            .rename(columns={'size': 'active_months'})
        )
        base = base.merge(month_act[['prod_key', 'active_months']], on='prod_key', how='left')
        base['active_months'] = base['active_months'].fillna(0)

        base['estado_producto'] = np.where(
            base['months_since_last'] >= 6,
            'INACTIVO',
            np.where(base['active_months'] <= 4, 'ESTACIONAL', 'ACTIVO'),
        )

        base['anio'] = base['periodo'].dt.year
        base['mes'] = base['periodo'].dt.month
        base['fecha_carga'] = datetime.now()
        base['pipeline_id'] = pipeline_id
        base['batch_id'] = batch_id

        # Consolidar naming por codigo + periodo para evitar duplicidades textuales.
        base['producto_item'] = base['producto_item'].fillna('').astype(str)
        base['producto_dashboard'] = base['producto_dashboard'].fillna('').astype(str)
        base = (
            base.groupby(
                [
                    'periodo', 'anio', 'mes', 'marca', 'familia', 'codigo_producto', 'ean13',
                    'tipo_producto', 'categoria_producto', 'estado_producto',
                    'flag_catalogo_conflicto', 'fecha_carga', 'pipeline_id', 'batch_id',
                ],
                as_index=False,
            )
            .agg(
                producto_item=('producto_item', lambda s: s.mode().iloc[0] if len(s.mode()) > 0 else s.iloc[0]),
                producto_dashboard=('producto_dashboard', lambda s: s.mode().iloc[0] if len(s.mode()) > 0 else s.iloc[0]),
                cantidad=('cantidad', 'sum'),
                ventas=('ventas', 'sum'),
                recuento_cliente=('recuento_cliente', 'sum'),
            )
        )

        out_cols = [
            'periodo', 'anio', 'mes', 'marca', 'familia', 'codigo_producto', 'ean13',
            'producto_item', 'producto_dashboard', 'tipo_producto', 'categoria_producto', 'cantidad', 'ventas',
            'recuento_cliente', 'estado_producto', 'flag_catalogo_conflicto',
            'fecha_carga', 'pipeline_id', 'batch_id'
        ]
        for c in out_cols:
            if c not in base.columns:
                base[c] = None
        base = base[out_cols].rename(
            columns={
                'cantidad': 'qty_vendida',
                'ventas': 'ventas_valor',
                'recuento_cliente': 'clientes',
            }
        )
        resultados['forecasting_base_mensual_v1'] = base

        # Construir base PP desde produccion 2025 (separada de ventas econespecias).
        pp_base = pd.DataFrame()
        if len(pp_family_norm_set) > 0 and 'quickbooks_produccion_raw' in dfs:
            df_prod_raw = dfs['quickbooks_produccion_raw']
            if isinstance(df_prod_raw, list):
                df_prod_raw = pd.DataFrame(df_prod_raw)
            elif isinstance(df_prod_raw, pd.DataFrame):
                df_prod_raw = df_prod_raw.copy()
            else:
                df_prod_raw = pd.DataFrame()

            if len(df_prod_raw) > 0 and 'producto' in df_prod_raw.columns and 'fecha' in df_prod_raw.columns:
                df_prod_raw['producto'] = df_prod_raw['producto'].fillna('').astype(str)
                df_prod_raw['nombre_normalizado'] = df_prod_raw['producto'].apply(normalize_product_name)

                def _is_pp_name(name_norm: str) -> bool:
                    txt = f" {name_norm} "
                    for fam in pp_family_norm_set:
                        if fam and (fam in txt or txt.strip() in fam):
                            return True
                    return False

                df_prod_raw['flag_pp_catalogo'] = df_prod_raw['nombre_normalizado'].apply(_is_pp_name)
                df_prod_raw = df_prod_raw[df_prod_raw['flag_pp_catalogo']].copy()

                if len(df_prod_raw) > 0:
                    code_prod = (
                        df_prod_raw['producto'].str.extract(r'\((\d+)\)')[0]
                        .fillna(df_prod_raw['producto'].str.extract(r'(\d+)$')[0])
                    )
                    df_prod_raw['codigo_producto'] = code_prod.apply(
                        lambda x: str(x).strip().zfill(4)
                        if pd.notna(x) and str(x).strip() not in {'', 'nan', 'None'}
                        else ''
                    )

                    qty_candidates = ['qty_fabricada', 'qty_liberada', 'qty_planificada']
                    qty_col = next((c for c in qty_candidates if c in df_prod_raw.columns), None)
                    if qty_col is None:
                        df_prod_raw['qty_base'] = 0.0
                    else:
                        df_prod_raw['qty_base'] = pd.to_numeric(df_prod_raw[qty_col], errors='coerce').fillna(0)

                    df_prod_raw['periodo'] = pd.to_datetime(df_prod_raw['fecha'], errors='coerce').dt.to_period('M').dt.to_timestamp()
                    df_prod_raw = df_prod_raw.dropna(subset=['periodo']).copy()
                    df_prod_raw['anio'] = df_prod_raw['periodo'].dt.year
                    df_prod_raw['mes'] = df_prod_raw['periodo'].dt.month

                    pp_base = (
                        df_prod_raw.groupby(['periodo', 'anio', 'mes', 'codigo_producto', 'producto'], as_index=False)
                        .agg(qty_vendida=('qty_base', 'sum'))
                    )
                    pp_base['marca'] = 'PRODUCCION'
                    pp_base['familia'] = 'PP_PRODUCCION'
                    pp_base['ean13'] = ''
                    pp_base['producto_item'] = pp_base['producto']
                    pp_base['producto_dashboard'] = pp_base['producto']
                    pp_base['tipo_producto'] = 'PP'
                    pp_base['categoria_producto'] = 'PP_PRODUCCION'
                    pp_base['ventas_valor'] = 0.0
                    pp_base['clientes'] = 0
                    pp_base['estado_producto'] = 'ACTIVO'
                    pp_base['flag_catalogo_conflicto'] = False
                    pp_base['fecha_carga'] = datetime.now()
                    pp_base['pipeline_id'] = pipeline_id
                    pp_base['batch_id'] = batch_id
                    pp_base = pp_base[
                        [
                            'periodo', 'anio', 'mes', 'marca', 'familia', 'codigo_producto', 'ean13',
                            'producto_item', 'producto_dashboard', 'tipo_producto', 'categoria_producto',
                            'qty_vendida', 'ventas_valor', 'clientes', 'estado_producto', 'flag_catalogo_conflicto',
                            'fecha_carga', 'pipeline_id', 'batch_id',
                        ]
                    ]

        resultados['forecasting_base_pp_produccion_v1'] = pp_base
        if len(pp_base) > 0:
            resultados['forecasting_base_mensual_integrada_v1'] = pd.concat([base, pp_base], ignore_index=True)
        else:
            resultados['forecasting_base_mensual_integrada_v1'] = base.copy()

        if len(manual_mapping_df) > 0:
            mm_out = manual_mapping_df.copy()
            mm_out['fecha_carga'] = datetime.now()
            mm_out['pipeline_id'] = pipeline_id
            mm_out['batch_id'] = batch_id
            resultados['pp_pt_mapping_manual'] = mm_out

        print(f"    dim_producto_canonico: {len(dim)}")
        print(f"    forecasting_base_mensual_v1: {len(base)}")
        print(f"    forecasting_base_pp_produccion_v1: {len(pp_base)}")
        print(f"    forecasting_base_mensual_integrada_v1: {len(resultados['forecasting_base_mensual_integrada_v1'])}")
        print(f"    solapamientos OTRO/PT removidos (se conserva PT): {overlap_removed}")

    # =========================================================================
    # 8. IDENTIDAD MAESTRA SKU + CALIDAD FORECASTING
    # =========================================================================
    if 'forecasting_base_mensual_v1' in resultados:
        print("\n[8] Construyendo identidad maestra SKU y controles de calidad...")

        base_fc = resultados['forecasting_base_mensual_v1'].copy()
        base_fc['periodo'] = pd.to_datetime(base_fc['periodo'], errors='coerce')
        base_fc['codigo_producto'] = base_fc['codigo_producto'].fillna('').astype(str).str.strip()
        base_fc['producto_dashboard'] = base_fc['producto_dashboard'].fillna('').astype(str)
        base_fc['nombre_normalizado'] = base_fc['producto_dashboard'].apply(normalize_product_name)

        coded = base_fc[base_fc['codigo_producto'] != ''].copy()
        no_code = base_fc[base_fc['codigo_producto'] == ''].copy()

        coded_names = (
            coded.groupby('codigo_producto', as_index=False)
            .agg(
                nombres_distintos=('nombre_normalizado', 'nunique'),
                periodo_min=('periodo', 'min'),
                periodo_max=('periodo', 'max'),
            )
        )
        coded_conflicts = coded_names[coded_names['nombres_distintos'] > 1].copy()

        if len(coded_conflicts) > 0:
            nombres = (
                coded.groupby('codigo_producto')['nombre_normalizado']
                .apply(lambda s: ' | '.join(sorted(set(s.dropna().astype(str)))[:8]))
                .reset_index(name='nombres_detectados')
            )
            coded_conflicts = coded_conflicts.merge(nombres, on='codigo_producto', how='left')
        else:
            coded_conflicts['nombres_detectados'] = ''

        coded_conflicts['recomendacion'] = np.where(
            coded_conflicts['nombres_distintos'] <= 2,
            'REVISAR_MERGE',
            'REVISAR_SPLIT',
        )
        coded_conflicts['estado_resolucion'] = 'PENDIENTE_MANUAL'
        coded_conflicts['fecha_carga'] = datetime.now()
        coded_conflicts['pipeline_id'] = pipeline_id
        coded_conflicts['batch_id'] = batch_id

        map_df = base_fc[
            ['codigo_producto', 'producto_dashboard', 'nombre_normalizado', 'tipo_producto', 'categoria_producto', 'periodo', 'qty_vendida']
        ].copy()
        map_df = map_df.rename(columns={'producto_dashboard': 'nombre_original'})
        map_df['qty_vendida'] = pd.to_numeric(map_df['qty_vendida'], errors='coerce').fillna(0)

        canonical = (
            map_df.groupby(['codigo_producto', 'nombre_normalizado'], as_index=False)
            .agg(qty_total=('qty_vendida', 'sum'))
            .sort_values(['codigo_producto', 'qty_total'], ascending=[True, False])
            .drop_duplicates(subset=['codigo_producto'], keep='first')
            .rename(columns={'nombre_normalizado': 'nombre_canonico'})
        )
        map_df = map_df.merge(canonical[['codigo_producto', 'nombre_canonico']], on='codigo_producto', how='left')
        map_df.loc[map_df['codigo_producto'] == '', 'nombre_canonico'] = map_df.loc[
            map_df['codigo_producto'] == '', 'nombre_normalizado'
        ]

        conflict_codes = set(coded_conflicts['codigo_producto'].astype(str))
        map_df['flag_codigo_conflicto'] = map_df['codigo_producto'].astype(str).isin(conflict_codes)
        map_df['decision_sugerida'] = np.where(
            map_df['flag_codigo_conflicto'],
            'MANUAL_REVIEW',
            'AUTO_MERGE',
        )
        map_df['requiere_revision_manual'] = map_df['flag_codigo_conflicto']
        map_df['fecha_carga'] = datetime.now()
        map_df['pipeline_id'] = pipeline_id
        map_df['batch_id'] = batch_id

        map_df = map_df[
            [
                'codigo_producto', 'nombre_original', 'nombre_normalizado', 'nombre_canonico',
                'tipo_producto', 'categoria_producto', 'decision_sugerida', 'requiere_revision_manual',
                'flag_codigo_conflicto', 'fecha_carga', 'pipeline_id', 'batch_id',
            ]
        ].drop_duplicates()

        # SCD2 basico por codigo con historial temporal del nombre dominante.
        master_rows = []
        period_code_rows = []

        for code, g in coded.groupby('codigo_producto'):
            g2 = g[['periodo', 'nombre_normalizado', 'qty_vendida', 'tipo_producto', 'categoria_producto']].copy()
            g2['qty_vendida'] = pd.to_numeric(g2['qty_vendida'], errors='coerce').fillna(0)
            dominant = (
                g2.groupby(['periodo', 'nombre_normalizado'], as_index=False)
                .agg(qty=('qty_vendida', 'sum'))
                .sort_values(['periodo', 'qty'], ascending=[True, False])
                .drop_duplicates(subset=['periodo'], keep='first')
                .sort_values('periodo')
            )
            if len(dominant) == 0:
                continue

            dominant['segmento'] = (dominant['nombre_normalizado'] != dominant['nombre_normalizado'].shift(1)).cumsum()
            segs = (
                dominant.groupby(['segmento', 'nombre_normalizado'], as_index=False)
                .agg(vigente_desde=('periodo', 'min'), vigente_hasta=('periodo', 'max'))
                .sort_values('vigente_desde')
            )

            for idx, seg in segs.reset_index(drop=True).iterrows():
                if len(segs) == 1:
                    sku_id = f'SKU_{code}'
                else:
                    sku_id = f'SKU_{code}_V{idx + 1}'

                seg_name = seg['nombre_normalizado']
                seg_data = g2[g2['nombre_normalizado'] == seg_name]
                tipo = (
                    seg_data['tipo_producto'].mode().iloc[0]
                    if len(seg_data['tipo_producto'].dropna()) > 0
                    else 'OTRO'
                )
                categoria = (
                    seg_data['categoria_producto'].mode().iloc[0]
                    if len(seg_data['categoria_producto'].dropna()) > 0
                    else 'SIN_CATEGORIA'
                )

                master_rows.append(
                    {
                        'sku_id': sku_id,
                        'codigo_producto': code,
                        'producto_canonico': seg_name,
                        'tipo_producto': tipo,
                        'categoria_producto': categoria,
                        'vigente_desde': seg['vigente_desde'],
                        'vigente_hasta': seg['vigente_hasta'],
                        'activo': idx == (len(segs) - 1),
                        'calidad_sku': 'MEDIA' if len(segs) > 1 else 'ALTA',
                        'flag_codigo_reciclado': len(segs) > 1,
                        'fecha_carga': datetime.now(),
                        'pipeline_id': pipeline_id,
                        'batch_id': batch_id,
                    }
                )

                for period in dominant[dominant['segmento'] == seg['segmento']]['periodo'].tolist():
                    period_code_rows.append({'codigo_producto': code, 'periodo': period, 'sku_id': sku_id})

        for name_norm, g in no_code.groupby('nombre_normalizado'):
            if not name_norm:
                continue
            sku_id = f'NO_CODE_{stable_hash(name_norm)}'
            tipo = (
                g['tipo_producto'].mode().iloc[0]
                if len(g['tipo_producto'].dropna()) > 0
                else 'OTRO'
            )
            categoria = (
                g['categoria_producto'].mode().iloc[0]
                if len(g['categoria_producto'].dropna()) > 0
                else 'SIN_CATEGORIA'
            )
            master_rows.append(
                {
                    'sku_id': sku_id,
                    'codigo_producto': '',
                    'producto_canonico': name_norm,
                    'tipo_producto': tipo,
                    'categoria_producto': categoria,
                    'vigente_desde': g['periodo'].min(),
                    'vigente_hasta': g['periodo'].max(),
                    'activo': True,
                    'calidad_sku': 'BAJA',
                    'flag_codigo_reciclado': False,
                    'fecha_carga': datetime.now(),
                    'pipeline_id': pipeline_id,
                    'batch_id': batch_id,
                }
            )

        master_df = pd.DataFrame(master_rows)
        if len(master_df) == 0:
            master_df = pd.DataFrame(
                columns=[
                    'sku_id', 'codigo_producto', 'producto_canonico', 'tipo_producto', 'categoria_producto',
                    'vigente_desde', 'vigente_hasta', 'activo', 'calidad_sku', 'flag_codigo_reciclado',
                    'fecha_carga', 'pipeline_id', 'batch_id',
                ]
            )

        period_code_df = pd.DataFrame(period_code_rows)
        base_enriched = base_fc.copy()
        if len(period_code_df) > 0:
            base_enriched = base_enriched.merge(period_code_df, on=['codigo_producto', 'periodo'], how='left')
        else:
            base_enriched['sku_id'] = None

        no_code_map = master_df[master_df['codigo_producto'] == ''][['sku_id', 'producto_canonico']].copy()
        if len(no_code_map) > 0:
            base_enriched = base_enriched.merge(
                no_code_map,
                left_on='nombre_normalizado',
                right_on='producto_canonico',
                how='left',
                suffixes=('', '_no_code'),
            )
            base_enriched['sku_id'] = base_enriched['sku_id'].fillna(base_enriched['sku_id_no_code'])
            base_enriched = base_enriched.drop(columns=['sku_id_no_code', 'producto_canonico'], errors='ignore')

        base_enriched['sku_id'] = base_enriched['sku_id'].fillna(
            base_enriched['codigo_producto'].apply(
                lambda c: f'SKU_{c}' if c not in {'', 'nan', 'None'} else None
            )
        )

        master_quality = master_df[['sku_id', 'calidad_sku', 'flag_codigo_reciclado']].drop_duplicates()
        base_enriched = base_enriched.merge(master_quality, on='sku_id', how='left')
        base_enriched['calidad_sku'] = base_enriched['calidad_sku'].fillna('BAJA')
        base_enriched['flag_codigo_conflicto'] = base_enriched['codigo_producto'].astype(str).isin(conflict_codes)

        pct_rows_no_code = float((base_enriched['codigo_producto'] == '').mean()) if len(base_enriched) > 0 else 0.0
        pct_unmapped = float(base_enriched['sku_id'].isna().mean()) if len(base_enriched) > 0 else 0.0
        n_codes = int((coded['codigo_producto'].nunique())) if len(coded) > 0 else 0
        pct_codes_conflict = float(len(coded_conflicts) / n_codes) if n_codes > 0 else 0.0
        pct_exact_match = 1.0 - pct_unmapped

        status = 'PASS'
        if pct_codes_conflict > 0.02 or pct_rows_no_code > 0.05 or pct_unmapped > 0.02:
            status = 'WARNING'
        if pct_codes_conflict > 0.05 or pct_rows_no_code > 0.10 or pct_unmapped > 0.05:
            status = 'FAIL'

        quality_df = pd.DataFrame(
            [
                {'metric': 'pct_codigos_con_conflicto', 'value': pct_codes_conflict},
                {'metric': 'pct_filas_sin_codigo', 'value': pct_rows_no_code},
                {'metric': 'pct_nombres_no_mapeados', 'value': pct_unmapped},
                {'metric': 'pct_match_exacto_maestro', 'value': pct_exact_match},
                {'metric': 'status_calidad', 'value': status},
                {'metric': 'threshold_conflict_warn', 'value': 0.02},
                {'metric': 'threshold_no_code_warn', 'value': 0.05},
                {'metric': 'threshold_unmapped_warn', 'value': 0.02},
            ]
        )
        quality_df['fecha_carga'] = datetime.now()
        quality_df['pipeline_id'] = pipeline_id
        quality_df['batch_id'] = batch_id

        strict_quality = bool(kwargs.get('strict_quality', False))
        if strict_quality and status == 'FAIL':
            raise RuntimeError('Calidad Silver FAIL segun umbrales de identidad SKU.')

        base_enriched = base_enriched.drop(columns=['nombre_normalizado'], errors='ignore')
        resultados['forecasting_base_mensual_v1'] = base_enriched
        resultados['dim_producto_master'] = master_df
        resultados['product_name_mapping'] = map_df
        resultados['product_code_conflicts'] = coded_conflicts
        resultados['product_quality_metrics'] = quality_df

        print(f"    dim_producto_master: {len(master_df)}")
        print(f"    product_name_mapping: {len(map_df)}")
        print(f"    product_code_conflicts: {len(coded_conflicts)}")
        print(f"    product_quality_metrics: {len(quality_df)}")
        print(f"    status_calidad_identidad_sku: {status}")

    # =========================================================================
    # 9. DATASETS QUICKBOOKS FORECASTING V3 (compatibles con proyecto VS Code)
    # =========================================================================
    if 'catalogo_ean_clean' in resultados:
        print("\n[9] Construyendo datasets curados QuickBooks Forecasting v3...")

        cat_src = resultados['catalogo_ean_clean'].copy()
        cat_v3 = cat_src.rename(
            columns={
                'item': 'item_path',
                'um': 'unit',
            }
        ).copy()

        for col in ['item_path', 'description', 'unit', 'ean13', 'ean14']:
            if col not in cat_v3.columns:
                cat_v3[col] = ''
            cat_v3[col] = cat_v3[col].map(clean_string_v3)
        if 'price' not in cat_v3.columns:
            cat_v3['price'] = 0.0
        cat_v3['price'] = pd.to_numeric(cat_v3['price'], errors='coerce').fillna(0.0)

        cat_v3 = cat_v3[cat_v3['item_path'].ne('')].copy()
        cat_v3['product_type'] = cat_v3['item_path'].map(infer_product_type_v3)
        cat_pt = cat_v3[cat_v3['product_type'].eq('PT')].copy()
        if len(cat_pt) == 0 and len(cat_v3) > 0:
            # El catalogo EAN limpio alimenta ventas comerciales PT, pero en esta fuente
            # no vienen prefijos "PT:"/"PP:" en item_path. Si todo queda como OTHER,
            # tratamos el catalogo como PT para no vaciar el modelo de forecasting PT.
            print(
                "[WARN] catalogo_ean_clean no contiene prefijos PT detectables; "
                "se usa el catalogo completo como base PT para forecasting v3."
            )
            cat_pt = cat_v3.copy()
            cat_pt['product_type'] = 'PT'

        if len(cat_pt) > 0:
            item_set = set(cat_pt['item_path'])
            cat_pt['is_leaf'] = ~cat_pt['item_path'].map(lambda item: has_child_v3(item, item_set))
            cat_pt['item_leaf'] = cat_pt['item_path'].map(item_leaf_v3)
            cat_pt['product_name'] = cat_pt['description'].where(cat_pt['description'].ne(''), cat_pt['item_leaf'])
            cat_pt['product_norm'] = cat_pt['product_name'].map(normalize_product_name_v3)
            cat_pt['item_leaf_norm'] = cat_pt['item_leaf'].map(normalize_product_name_v3)
            cat_pt['match_key'] = cat_pt['product_name'].map(token_signature_v3)
            cat_pt['item_leaf_match_key'] = cat_pt['item_leaf'].map(token_signature_v3)
            cat_pt['size_key'] = cat_pt['product_name'].map(extract_size_signature_v3)
            cat_pt['pack_key'] = cat_pt['product_name'].map(extract_pack_signature_v3)
            if 'codigo_producto' in cat_pt.columns:
                cat_pt['codigo_producto'] = cat_pt['codigo_producto'].map(clean_string_v3)
            else:
                cat_pt['codigo_producto'] = ''
            cat_pt['product_code'] = cat_pt['codigo_producto']
            missing_code = cat_pt['product_code'].eq('')
            cat_pt.loc[missing_code, 'product_code'] = cat_pt.loc[missing_code, 'product_name'].map(extract_product_code_v3)
            missing_code = cat_pt['product_code'].eq('')
            cat_pt.loc[missing_code, 'product_code'] = cat_pt.loc[missing_code, 'item_leaf'].map(extract_product_code_v3)
            cat_pt['product_id'] = [
                make_product_id_v3('PT', code, norm)
                for code, norm in zip(cat_pt['product_code'], cat_pt['product_norm'])
            ]

            cat_pt = cat_pt[cat_pt['is_leaf'] & cat_pt['product_norm'].ne('')].copy()
            cat_pt['quality_score'] = (
                cat_pt['ean13'].ne('').astype(int) * 4
                + cat_pt['ean14'].ne('').astype(int) * 4
                + cat_pt['unit'].ne('').astype(int) * 2
                + cat_pt['price'].gt(0).astype(int)
                + cat_pt['item_path'].str.len().fillna(0) / 10000
            )
            cat_pt['_ean13_sort'] = pd.to_numeric(cat_pt['ean13'], errors='coerce').fillna(0)
            cat_pt = (
                cat_pt.sort_values(
                    ['product_id', 'quality_score', '_ean13_sort'],
                    ascending=[True, False, False],
                )
                .drop_duplicates('product_id', keep='first')
                .drop(columns=['quality_score', '_ean13_sort'], errors='ignore')
                .reset_index(drop=True)
            )
        else:
            cat_pt = pd.DataFrame()

        cat_pt_lookup = cat_pt.copy()

        catalog_cols = [
            'product_id', 'product_code', 'product_name', 'product_norm',
            'item_leaf', 'item_leaf_norm', 'item_path', 'description',
            'unit', 'price', 'ean13', 'ean14', 'is_leaf',
        ]
        for col in catalog_cols:
            if col not in cat_pt.columns:
                cat_pt[col] = None
        cat_pt = add_metadata_v3(cat_pt[catalog_cols].copy())
        resultados['forecasting_v3_catalogo_pt_limpio'] = cat_pt
        print(f"    forecasting_v3_catalogo_pt_limpio: {len(cat_pt)}")

        if 'ventas_econespecias_mensual_clean' in resultados:
            ven_v3 = resultados['ventas_econespecias_mensual_clean'].copy()
            ven_v3 = ven_v3.rename(columns={'producto': 'producto_raw'})
            for col in ['marca', 'familia', 'producto_raw']:
                if col not in ven_v3.columns:
                    ven_v3[col] = ''
                ven_v3[col] = ven_v3[col].map(clean_string_v3)

            for col in ['cantidad', 'ventas', 'recuento_cliente']:
                if col not in ven_v3.columns:
                    ven_v3[col] = 0.0
                ven_v3[col] = pd.to_numeric(ven_v3[col], errors='coerce').fillna(0.0)

            ven_v3['periodo'] = pd.to_datetime(ven_v3.get('periodo'), errors='coerce')
            ven_v3 = ven_v3[ven_v3['periodo'].notna() & ven_v3['producto_raw'].ne('')].copy()
            ven_v3['periodo'] = ven_v3['periodo'].dt.to_period('M').dt.to_timestamp()
            ven_v3['product_norm'] = ven_v3['producto_raw'].map(normalize_product_name_v3)
            ven_v3['match_key'] = ven_v3['producto_raw'].map(token_signature_v3)
            ven_v3['size_key'] = ven_v3['producto_raw'].map(extract_size_signature_v3)
            ven_v3['pack_key'] = ven_v3['producto_raw'].map(extract_pack_signature_v3)
            ven_v3['product_code'] = ven_v3['producto_raw'].map(extract_product_code_v3)

            lookup = catalog_lookup_v3(cat_pt_lookup)
            unique_products = (
                ven_v3.groupby('product_norm', as_index=False)
                .agg(
                    producto_raw=('producto_raw', mode_or_blank_v3),
                    match_key=('match_key', mode_or_blank_v3),
                    size_key=('size_key', mode_or_blank_v3),
                    pack_key=('pack_key', mode_or_blank_v3),
                    product_code=('product_code', mode_or_blank_v3),
                    cantidad_total=('cantidad', 'sum'),
                    ventas_total=('ventas', 'sum'),
                    marca=('marca', mode_or_blank_v3),
                    familia=('familia', mode_or_blank_v3),
                )
                .sort_values('cantidad_total', ascending=False)
            )

            matches = pd.DataFrame(
                [match_pt_product_v3(row, lookup) for _, row in unique_products.iterrows()]
            )
            if len(matches) == 0:
                matches = pd.DataFrame(
                    columns=[
                        'product_id', 'product_code', 'product_name', 'product_norm',
                        'item_leaf', 'item_leaf_norm', 'item_path', 'description',
                        'unit', 'price', 'ean13', 'ean14', 'is_leaf',
                        'catalog_match_status',
                    ]
                )
            matches = matches.rename(
                columns={
                    'product_code': 'catalog_product_code',
                    'product_norm': 'catalog_product_norm',
                }
            )
            match_table = pd.concat(
                [unique_products.reset_index(drop=True), matches.reset_index(drop=True)],
                axis=1,
            )

            match_cols = [
                'product_norm', 'producto_raw', 'product_code', 'cantidad_total', 'ventas_total',
                'marca', 'familia', 'product_id', 'catalog_product_code', 'product_name',
                'catalog_product_norm', 'item_leaf', 'item_leaf_norm', 'item_path',
                'description', 'unit', 'price', 'ean13', 'ean14', 'is_leaf',
                'catalog_match_status',
            ]
            for col in match_cols:
                if col not in match_table.columns:
                    match_table[col] = None
            match_table = add_metadata_v3(match_table[match_cols].copy())
            resultados['forecasting_v3_pt_catalog_match_report'] = match_table

            unmatched = (
                match_table[match_table['catalog_match_status'].eq('no_catalog_match')]
                .sort_values('cantidad_total', ascending=False)
                .copy()
            )
            resultados['forecasting_v3_pt_productos_no_catalogo'] = unmatched[match_cols + ['fecha_carga', 'pipeline_id', 'batch_id']].copy()

            ven_v3 = ven_v3.merge(
                match_table[['product_norm', 'product_id', 'product_name', 'catalog_match_status']],
                on='product_norm',
                how='left',
            )
            monthly_pt = (
                ven_v3.groupby(['product_id', 'periodo'], as_index=False)
                .agg(
                    target_qty=('cantidad', 'sum'),
                    ventas=('ventas', 'sum'),
                    recuento_cliente=('recuento_cliente', 'sum'),
                    productos_raw_distintos=('producto_raw', 'nunique'),
                )
            )
            monthly_pt['target_qty_raw'] = monthly_pt['target_qty']
            monthly_pt['target_qty'] = monthly_pt['target_qty'].clip(lower=0.0)

            product_meta_pt = (
                match_table.groupby('product_id', as_index=False)
                .agg(
                    product_code=('catalog_product_code', mode_or_blank_v3),
                    product_name=('product_name', 'first'),
                    product_norm=('product_norm', 'first'),
                    catalog_match_status=('catalog_match_status', 'first'),
                    item_path=('item_path', 'first'),
                    unit=('unit', 'first'),
                    price=('price', 'first'),
                    ean13=('ean13', 'first'),
                    ean14=('ean14', 'first'),
                    marca=('marca', mode_or_blank_v3),
                    familia=('familia', mode_or_blank_v3),
                    cantidad_total_raw=('cantidad_total', 'sum'),
                    ventas_total_raw=('ventas_total', 'sum'),
                )
            )
            product_meta_pt['source_type'] = 'PT'

            grid_pt = complete_monthly_grid_v3(
                monthly_pt,
                product_meta_pt,
                ['target_qty', 'target_qty_raw', 'ventas', 'recuento_cliente', 'productos_raw_distintos'],
            )
            product_meta_pt = product_meta_pt[product_meta_pt['product_id'].isin(grid_pt.get('product_id', pd.Series(dtype=str)).unique())].copy()
            summary_pt = summarize_products_v3(grid_pt)
            products_pt = product_meta_pt.merge(summary_pt.drop(columns=['producto'], errors='ignore'), on='product_id', how='left')

            if len(grid_pt) > 0 and len(products_pt) > 0:
                grid_pt = grid_pt.merge(
                    products_pt[
                        [
                            'product_id', 'estado_producto', 'es_estacional',
                            'share_top_3_meses', 'meses_estacionales_num',
                            'meses_estacionales', 'ultima_actividad',
                        ]
                    ],
                    on='product_id',
                    how='left',
                )

            matched_ids = set(products_pt[~products_pt['catalog_match_status'].eq('no_catalog_match')]['product_id']) if len(products_pt) else set()
            grid_pt_model = grid_pt[grid_pt['product_id'].isin(matched_ids)].copy() if len(grid_pt) else grid_pt.copy()
            products_pt_model = products_pt[products_pt['product_id'].isin(matched_ids)].copy() if len(products_pt) else products_pt.copy()

            grid_pt_model = add_exogenous_defaults_v3(grid_pt_model)
            grid_pt_model = add_metadata_v3(grid_pt_model)
            products_pt_model = add_metadata_v3(products_pt_model)

            for col in ['productos_raw_distintos']:
                if col in grid_pt_model.columns:
                    grid_pt_model[col] = pd.to_numeric(grid_pt_model[col], errors='coerce').fillna(0).astype(int)
            for col in ['meses_en_serie', 'meses_con_actividad']:
                if col in products_pt_model.columns:
                    products_pt_model[col] = pd.to_numeric(products_pt_model[col], errors='coerce').fillna(0).astype(int)

            pt_monthly_cols = [
                'product_id', 'periodo', 'target_qty', 'ventas', 'recuento_cliente',
                'productos_raw_distintos', 'target_qty_raw', 'product_code',
                'product_name', 'product_norm', 'catalog_match_status', 'item_path',
                'unit', 'price', 'ean13', 'ean14', 'marca', 'familia',
                'cantidad_total_raw', 'ventas_total_raw', 'source_type',
                'estado_producto', 'es_estacional', 'share_top_3_meses',
                'meses_estacionales_num', 'meses_estacionales', 'ultima_actividad',
                *exogenous_feature_columns, 'fecha_carga', 'pipeline_id', 'batch_id',
            ]
            pt_products_cols = [
                'product_id', 'product_code', 'product_name', 'product_norm',
                'catalog_match_status', 'item_path', 'unit', 'price', 'ean13',
                'ean14', 'marca', 'familia', 'cantidad_total_raw', 'ventas_total_raw',
                'source_type', 'total_qty', 'meses_en_serie', 'primera_actividad',
                'ultima_actividad', 'meses_con_actividad', 'periodo_referencia',
                'corte_inactividad', 'estado_producto', 'es_estacional',
                'share_top_3_meses', 'mediana_meses_activos_por_anio',
                'meses_estacionales_num', 'meses_estacionales',
                'fecha_carga', 'pipeline_id', 'batch_id',
            ]
            for col in pt_monthly_cols:
                if col not in grid_pt_model.columns:
                    grid_pt_model[col] = None
            for col in pt_products_cols:
                if col not in products_pt_model.columns:
                    products_pt_model[col] = None

            resultados['forecasting_v3_pt_mensual_model'] = grid_pt_model[pt_monthly_cols].copy()
            resultados['forecasting_v3_pt_productos_model'] = products_pt_model[pt_products_cols].copy()

            print(f"    forecasting_v3_pt_catalog_match_report: {len(match_table)}")
            print(f"    forecasting_v3_pt_productos_no_catalogo: {len(unmatched)}")
            print(f"    forecasting_v3_pt_mensual_model: {len(resultados['forecasting_v3_pt_mensual_model'])}")
            print(f"    forecasting_v3_pt_productos_model: {len(resultados['forecasting_v3_pt_productos_model'])}")

        if 'quickbooks_produccion_raw' in dfs:
            prod_v3 = dfs['quickbooks_produccion_raw']
            if isinstance(prod_v3, list):
                prod_v3 = pd.DataFrame(prod_v3)
            elif isinstance(prod_v3, pd.DataFrame):
                prod_v3 = prod_v3.copy()
            else:
                prod_v3 = pd.DataFrame()

            if len(prod_v3) > 0:
                for col in ['producto', 'lote', 'numero']:
                    if col not in prod_v3.columns:
                        prod_v3[col] = ''
                    prod_v3[col] = prod_v3[col].map(clean_string_v3)

                prod_v3 = prod_v3.rename(columns={'producto': 'producto_raw'})
                prod_v3['product_type'] = prod_v3['producto_raw'].map(infer_product_type_v3)
                pp_mask = prod_v3['product_type'].eq('PP')
                if not pp_mask.any() and len(pp_family_norm_set) > 0:
                    prod_v3['producto_norm_tmp'] = prod_v3['producto_raw'].map(normalize_product_name_v3)
                    pp_mask = prod_v3['producto_norm_tmp'].apply(
                        lambda name: any(fam and (fam in f' {name} ' or name in fam) for fam in pp_family_norm_set)
                    )
                prod_v3 = prod_v3[pp_mask].copy()

                if len(prod_v3) > 0:
                    prod_v3['fecha'] = pd.to_datetime(prod_v3.get('fecha'), errors='coerce')
                    prod_v3 = prod_v3[prod_v3['fecha'].notna()].copy()
                    prod_v3['periodo'] = prod_v3['fecha'].dt.to_period('M').dt.to_timestamp()

                    qty_aliases = {
                        'q_planificada': ['q_planificada', 'qty_planificada', 'qty_total_planificada'],
                        'q_liberada': ['q_liberada', 'qty_liberada'],
                        'q_fabricada': ['q_fabricada', 'qty_fabricada', 'qty_total_despachada'],
                    }
                    for target_col, candidates in qty_aliases.items():
                        source_col = next((c for c in candidates if c in prod_v3.columns), None)
                        prod_v3[target_col] = (
                            pd.to_numeric(prod_v3[source_col], errors='coerce').fillna(0.0)
                            if source_col else 0.0
                        )

                    prod_v3['target_qty'] = prod_v3['q_fabricada'].where(prod_v3['q_fabricada'].gt(0), prod_v3['q_liberada'])
                    prod_v3['target_qty'] = prod_v3['target_qty'].where(prod_v3['target_qty'].gt(0), prod_v3['q_planificada']).fillna(0.0)
                    prod_v3['product_name'] = prod_v3['producto_raw'].map(remove_product_prefix_v3)
                    prod_v3['product_norm'] = prod_v3['producto_raw'].map(normalize_product_name_v3)
                    prod_v3['product_id'] = [
                        make_product_id_v3('PP', '', norm)
                        for norm in prod_v3['product_norm']
                    ]
                    prod_v3['product_code'] = ''

                    categories = {}
                    if 'quickbooks_produccion_categorias_pp_raw' in dfs:
                        df_ppcat = dfs['quickbooks_produccion_categorias_pp_raw']
                        if isinstance(df_ppcat, list):
                            df_ppcat = pd.DataFrame(df_ppcat)
                        elif isinstance(df_ppcat, pd.DataFrame):
                            df_ppcat = df_ppcat.copy()
                        else:
                            df_ppcat = pd.DataFrame()
                        if len(df_ppcat) > 0:
                            for col in ['familia', 'categoria_pp']:
                                if col not in df_ppcat.columns:
                                    df_ppcat[col] = ''
                            df_ppcat['familia_norm'] = df_ppcat['familia'].map(normalize_product_name_v3)
                            categories = {
                                row.familia_norm: clean_string_v3(row.categoria_pp)
                                for row in df_ppcat.itertuples(index=False)
                                if row.familia_norm and clean_string_v3(row.categoria_pp)
                            }

                    if not categories:
                        categories = {
                            normalize_product_name_v3(remove_product_prefix_v3(value)): clean_string_v3(remove_product_prefix_v3(value))
                            for value in prod_v3['producto_raw'].dropna().astype(str).tolist()
                            if infer_product_type_v3(value) == 'PP'
                        }

                    prod_v3['product_leaf_norm'] = prod_v3['product_name'].map(normalize_product_name_v3)
                    prod_v3['categoria_pp'] = prod_v3['product_leaf_norm'].map(categories).fillna('')

                    monthly_pp = (
                        prod_v3.groupby(['product_id', 'periodo'], as_index=False)
                        .agg(
                            target_qty=('target_qty', 'sum'),
                            q_planificada=('q_planificada', 'sum'),
                            q_liberada=('q_liberada', 'sum'),
                            q_fabricada=('q_fabricada', 'sum'),
                            lotes=('lote', 'nunique'),
                            ordenes=('numero', 'nunique'),
                        )
                    )
                    monthly_pp['target_qty_raw'] = monthly_pp['target_qty']
                    monthly_pp['target_qty'] = monthly_pp['target_qty'].clip(lower=0.0)

                    product_meta_pp = (
                        prod_v3.groupby('product_id', as_index=False)
                        .agg(
                            product_code=('product_code', 'first'),
                            product_name=('product_name', mode_or_blank_v3),
                            product_norm=('product_norm', 'first'),
                            categoria_pp=('categoria_pp', mode_or_blank_v3),
                        )
                    )
                    product_meta_pp['source_type'] = 'PP'
                    product_meta_pp['catalog_match_status'] = 'production_pp'

                    grid_pp = complete_monthly_grid_v3(
                        monthly_pp,
                        product_meta_pp,
                        ['target_qty', 'target_qty_raw', 'q_planificada', 'q_liberada', 'q_fabricada', 'lotes', 'ordenes'],
                    )
                    product_meta_pp = product_meta_pp[product_meta_pp['product_id'].isin(grid_pp.get('product_id', pd.Series(dtype=str)).unique())].copy()
                    summary_pp = summarize_products_v3(grid_pp)
                    products_pp = product_meta_pp.merge(summary_pp.drop(columns=['producto'], errors='ignore'), on='product_id', how='left')

                    if len(grid_pp) > 0 and len(products_pp) > 0:
                        grid_pp = grid_pp.merge(
                            products_pp[
                                [
                                    'product_id', 'estado_producto', 'es_estacional',
                                    'share_top_3_meses', 'meses_estacionales_num',
                                    'meses_estacionales', 'ultima_actividad',
                                ]
                            ],
                            on='product_id',
                            how='left',
                        )

                    grid_pp = add_exogenous_defaults_v3(grid_pp)
                    grid_pp = add_metadata_v3(grid_pp)
                    products_pp = add_metadata_v3(products_pp)

                    for col in ['lotes', 'ordenes']:
                        if col in grid_pp.columns:
                            grid_pp[col] = pd.to_numeric(grid_pp[col], errors='coerce').fillna(0).astype(int)
                    for col in ['meses_en_serie', 'meses_con_actividad']:
                        if col in products_pp.columns:
                            products_pp[col] = pd.to_numeric(products_pp[col], errors='coerce').fillna(0).astype(int)

                    pp_monthly_cols = [
                        'product_id', 'periodo', 'target_qty', 'q_planificada',
                        'q_liberada', 'q_fabricada', 'lotes', 'ordenes',
                        'target_qty_raw', 'product_code', 'product_name',
                        'product_norm', 'categoria_pp', 'source_type',
                        'catalog_match_status', 'estado_producto', 'es_estacional',
                        'share_top_3_meses', 'meses_estacionales_num',
                        'meses_estacionales', 'ultima_actividad',
                        *exogenous_feature_columns, 'fecha_carga', 'pipeline_id', 'batch_id',
                    ]
                    pp_products_cols = [
                        'product_id', 'product_code', 'product_name', 'product_norm',
                        'categoria_pp', 'source_type', 'catalog_match_status',
                        'total_qty', 'meses_en_serie', 'primera_actividad',
                        'ultima_actividad', 'meses_con_actividad',
                        'periodo_referencia', 'corte_inactividad',
                        'estado_producto', 'es_estacional', 'share_top_3_meses',
                        'mediana_meses_activos_por_anio', 'meses_estacionales_num',
                        'meses_estacionales', 'fecha_carga', 'pipeline_id', 'batch_id',
                    ]
                    for col in pp_monthly_cols:
                        if col not in grid_pp.columns:
                            grid_pp[col] = None
                    for col in pp_products_cols:
                        if col not in products_pp.columns:
                            products_pp[col] = None

                    resultados['forecasting_v3_pp_mensual_model'] = grid_pp[pp_monthly_cols].copy()
                    resultados['forecasting_v3_pp_productos_model'] = products_pp[pp_products_cols].copy()

                    print(f"    forecasting_v3_pp_mensual_model: {len(resultados['forecasting_v3_pp_mensual_model'])}")
                    print(f"    forecasting_v3_pp_productos_model: {len(resultados['forecasting_v3_pp_productos_model'])}")

    # =========================================================================
    # RESUMEN FINAL
    # =========================================================================

    print(f"\n{'='*70}")
    print(f"RESUMEN TRANSFORMACION SILVER")
    print(f"{'='*70}")
    for tabla, df in resultados.items():
        print(f"  {tabla}: {len(df)} registros")
    print(f"{'='*70}\n")

    return {
        'dfs': resultados,
        'pipeline_id': pipeline_id,
        'batch_id': batch_id,
        'metadata': data.get('metadata', {})
    }


@test
def test_output(output, *args) -> None:
    assert output is not None, 'Output es None'
    assert 'dfs' in output, 'Falta dfs en output'
    if len(output['dfs']) > 0:
        print(f"OK: Transformacion completada con {len(output['dfs'])} tablas")
    else:
        print("WARN: No se transformaron datos")
