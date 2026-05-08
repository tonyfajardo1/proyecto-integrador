"""
Cliente ODIN WS v2 para extraer datos de QuickBooks via API REST.
"""
import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd


DEFAULT_BASE_URL = 'http://52.5.30.107:8081/api/v1/odin'


def _build_token(function_name: str) -> str:
    public_key = os.getenv('ODIN_PUBLIC_KEY', '').strip()
    private_key = os.getenv('ODIN_PRIVATE_KEY', '').strip()

    if not public_key or not private_key:
        raise ValueError('Faltan ODIN_PUBLIC_KEY y/o ODIN_PRIVATE_KEY en variables de entorno')

    utc_now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')
    raw = f'{public_key}{utc_now}{function_name}{private_key}'
    return hashlib.sha1(raw.encode('utf-8')).hexdigest().upper()


def _parse_data(data):
    if data is None:
        return []
    if isinstance(data, (dict, list)):
        return data
    if isinstance(data, str):
        stripped = data.strip()
        if not stripped:
            return []
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            return []
    return []


def odin_get(endpoint: str, function_name: str, params: Dict) -> Dict:
    base_url = os.getenv('ODIN_BASE_URL', DEFAULT_BASE_URL).rstrip('/')
    payload = {'token': _build_token(function_name), **params}
    url = f"{base_url}/{endpoint}?{urlencode(payload)}"

    with urlopen(url, timeout=60) as response:
        body = response.read().decode('utf-8')
        data = json.loads(body)

    if data.get('status') != 'OK':
        raise RuntimeError(f"ODIN {endpoint}: {data.get('message', 'Error desconocido')}")

    return data


def fetch_orders(endpoint: str, estado: str, date: Optional[str] = None, nick: Optional[str] = None, page_size: int = 500) -> pd.DataFrame:
    offset = 0
    rows: List[Dict] = []

    while True:
        params = {
            'estado': estado,
            'from': offset,
            'skip': page_size,
        }
        if date:
            params['date'] = date
        if nick:
            params['nick'] = nick

        response = odin_get(endpoint=endpoint, function_name='Sales', params=params)
        page_rows = _parse_data(response.get('data'))

        if not page_rows:
            break

        rows.extend(page_rows)

        if len(page_rows) < page_size:
            break

        offset += page_size

    return pd.DataFrame(rows)


def fetch_lines(endpoint: str, idsales: List[str], page_size: int = 500) -> pd.DataFrame:
    rows: List[Dict] = []

    for idsale in idsales:
        offset = 0

        while True:
            response = odin_get(
                endpoint=endpoint,
                function_name='SaleLines',
                params={
                    'idsale': idsale,
                    'from': offset,
                    'skip': page_size,
                },
            )

            page_rows = _parse_data(response.get('data'))

            if not page_rows:
                break

            rows.extend(page_rows)

            if len(page_rows) < page_size:
                break

            offset += page_size

    return pd.DataFrame(rows)


def load_quickbooks_sales_from_odin(estado: str, date: Optional[str] = None, nick: Optional[str] = None, page_size: int = 500):
    orders = fetch_orders(endpoint='sales', estado=estado, date=date, nick=nick, page_size=page_size)
    if orders.empty:
        return orders, pd.DataFrame()

    idsale_list = orders['idsale'].dropna().astype(str).unique().tolist()
    lines = fetch_lines(endpoint='lines', idsales=idsale_list, page_size=page_size)
    return orders, lines


def load_quickbooks_produccion_from_odin(estado: str, date: Optional[str] = None, nick: Optional[str] = None, page_size: int = 500):
    orders = fetch_orders(endpoint='produccion', estado=estado, date=date, nick=nick, page_size=page_size)
    if orders.empty:
        return orders, pd.DataFrame()

    idsale_list = orders['idsale'].dropna().astype(str).unique().tolist()
    lines = fetch_lines(endpoint='produccionlines', idsales=idsale_list, page_size=page_size)
    return orders, lines
