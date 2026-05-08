import os
from pathlib import Path

import pandas as pd
import psycopg2


def _load_env_candidates() -> dict:
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


_ENV = _load_env_candidates()


def env(name: str, default=None):
    val = os.getenv(name)
    if val is not None and val != "":
        return val
    return _ENV.get(name, default)


def connect_dwh():
    return psycopg2.connect(
        host=env("DWH_HOST", "localhost"),
        port=int(env("DWH_PORT", "5433")),
        dbname=env("DWH_DB", "condimensa_analytics"),
        user=env("DWH_USER", "condimensa"),
        password=env("DWH_PASSWORD", "REDACTED_LOCAL_DB_PASSWORD"),
    )


def connect_quickbooks():
    return psycopg2.connect(
        host=env("QUICKBOOKS_HOST", "your-quickbooks-host.supabase.com"),
        port=int(env("QUICKBOOKS_PORT", "6543")),
        dbname=env("QUICKBOOKS_DB", "postgres"),
        user=env("QUICKBOOKS_USER", "postgres.your-quickbooks-project-ref"),
        password=env("QUICKBOOKS_PASSWORD"),
        sslmode=env("QUICKBOOKS_SSLMODE", "require"),
    )


def query_df(conn, query: str, params=None) -> pd.DataFrame:
    with conn.cursor() as cur:
        cur.execute(query, params or ())
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description] if cur.description else []
    return pd.DataFrame(rows, columns=cols)
