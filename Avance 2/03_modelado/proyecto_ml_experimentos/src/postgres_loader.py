import os
from pathlib import Path
import pandas as pd
import psycopg2


def _load_env_candidates():
    """Carga variables desde .env locales si no estan en el entorno."""
    base = Path(__file__).resolve().parents[3]  # .../Avance 2
    candidates = [
        base / "mage_condimensa2" / ".env",
        base / ".env",
        Path.cwd() / ".env",
    ]

    values = {}
    for p in candidates:
        if not p.exists():
            continue
        for raw in p.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            values[k.strip()] = v.strip().strip('"').strip("'")
    return values


_ENV_FILE_VALUES = _load_env_candidates()


def _env(name, default=None):
    val = os.getenv(name)
    if val is not None and val != "":
        return val
    return _ENV_FILE_VALUES.get(name, default)


def _connect_dwh():
    return psycopg2.connect(
        host=_env("DWH_HOST", "localhost"),
        port=int(_env("DWH_PORT", "5433")),
        dbname=_env("DWH_DB", "condimensa_analytics"),
        user=_env("DWH_USER", "condimensa"),
        password=_env("DWH_PASSWORD", "REDACTED_LOCAL_DB_PASSWORD"),
    )


def _connect_quickbooks():
    return psycopg2.connect(
        host=_env("QUICKBOOKS_HOST", "your-quickbooks-host.supabase.com"),
        port=int(_env("QUICKBOOKS_PORT", "6543")),
        dbname=_env("QUICKBOOKS_DB", "postgres"),
        user=_env("QUICKBOOKS_USER", "postgres.your-quickbooks-project-ref"),
        password=_env("QUICKBOOKS_PASSWORD"),
        sslmode=_env("QUICKBOOKS_SSLMODE", "require"),
    )


def resolved_connection_defaults():
    """Devuelve configuracion efectiva (sin exponer passwords)."""
    return {
        "quickbooks": {
            "host": _env("QUICKBOOKS_HOST", "your-quickbooks-host.supabase.com"),
            "port": int(_env("QUICKBOOKS_PORT", "6543")),
            "dbname": _env("QUICKBOOKS_DB", "postgres"),
            "user": _env("QUICKBOOKS_USER", "postgres.your-quickbooks-project-ref"),
        },
        "dwh": {
            "host": _env("DWH_HOST", "localhost"),
            "port": int(_env("DWH_PORT", "5433")),
            "dbname": _env("DWH_DB", "condimensa_analytics"),
            "user": _env("DWH_USER", "condimensa"),
        },
    }


def load_dwh_query(query: str) -> pd.DataFrame:
    with _connect_dwh() as conn:
        return pd.read_sql_query(query, conn)


def load_quickbooks_query(query: str) -> pd.DataFrame:
    with _connect_quickbooks() as conn:
        return pd.read_sql_query(query, conn)
