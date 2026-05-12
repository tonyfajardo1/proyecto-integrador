"""Funciones auxiliares de limpieza y normalizacion para forecasting_v3."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Any

import pandas as pd


MONTH_MAP = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}

MONTH_NAMES_ES = {
    1: "enero",
    2: "febrero",
    3: "marzo",
    4: "abril",
    5: "mayo",
    6: "junio",
    7: "julio",
    8: "agosto",
    9: "septiembre",
    10: "octubre",
    11: "noviembre",
    12: "diciembre",
}


def strip_accents(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = str(value).replace("Ñ", "N").replace("ñ", "n")
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch)
    )


def normalize_header(value: Any) -> str:
    text = strip_accents(value).lower().strip()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def clean_string(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if text.lower() in {"nan", "none", "nat"}:
        return ""
    return text


def normalize_product_name(value: Any) -> str:
    text = strip_accents(value).upper().strip()
    text = text.replace("&", " Y ")
    text = text.replace("$", " ")
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def item_leaf(value: Any) -> str:
    text = clean_string(value)
    if ":" in text:
        return text.split(":")[-1].strip()
    return text


def remove_product_prefix(value: Any) -> str:
    text = clean_string(value)
    upper = text.upper().strip()
    if upper.startswith("PT:") or upper.startswith("PP:"):
        return text.split(":", 1)[1].strip()
    if upper.startswith("PP SMART SELECTION:"):
        return text.split(":", 1)[1].strip()
    return text


def extract_product_code(value: Any) -> str:
    text = clean_string(value)
    if not text:
        return ""

    paren_codes = re.findall(r"\((?:[^\d]*)(\d{3,6})(?:[^\d]*)\)", text)
    if paren_codes:
        return paren_codes[-1]

    codes = re.findall(r"(?<!\d)(\d{4,6})(?!\d)", text)
    if codes:
        return codes[-1]
    return ""


def make_product_id(prefix: str, code: str, normalized_name: str) -> str:
    if code:
        return f"{prefix}_{code}"
    digest = hashlib.sha1(normalized_name.encode("utf-8")).hexdigest()[:10]
    return f"{prefix}_{digest}"


def infer_product_type(value: Any) -> str:
    text = clean_string(value).upper()
    if text.startswith("PT:"):
        return "PT"
    if text.startswith("PP"):
        return "PP"
    return "OTHER"


def month_to_number(value: Any) -> float:
    text = strip_accents(value).lower().strip()
    return MONTH_MAP.get(text, float("nan"))


def to_month_start(year: pd.Series, month: pd.Series) -> pd.Series:
    month_num = month.map(month_to_number)
    return pd.to_datetime(
        {
            "year": pd.to_numeric(year, errors="coerce"),
            "month": month_num,
            "day": 1,
        },
        errors="coerce",
    )


def as_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0.0)


def mode_or_blank(series: pd.Series) -> str:
    values = [clean_string(v) for v in series if clean_string(v)]
    if not values:
        return ""
    return pd.Series(values).mode().iloc[0]
