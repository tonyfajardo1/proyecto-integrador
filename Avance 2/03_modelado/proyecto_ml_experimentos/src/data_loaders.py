from pathlib import Path
import pandas as pd


def load_csv(path):
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"No existe archivo: {p}")
    return pd.read_csv(p)


def ensure_datetime(df, col):
    out = df.copy()
    out[col] = pd.to_datetime(out[col], errors="coerce")
    return out
