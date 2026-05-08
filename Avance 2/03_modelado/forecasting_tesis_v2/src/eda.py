import numpy as np
import pandas as pd


def quality_summary(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "rows": [len(df)],
            "productos": [df["producto"].nunique() if "producto" in df.columns else 0],
            "periodos": [df["periodo"].nunique() if "periodo" in df.columns else 0],
            "duplicados_producto_periodo": [
                int(df.duplicated(["producto", "periodo"]).sum()) if {"producto", "periodo"}.issubset(df.columns) else 0
            ],
            "null_qty_fabricada": [int(df["qty_fabricada"].isna().sum()) if "qty_fabricada" in df.columns else 0],
            "null_qty_planificada": [int(df["qty_planificada"].isna().sum()) if "qty_planificada" in df.columns else 0],
        }
    )


def product_volatility(df: pd.DataFrame) -> pd.DataFrame:
    stats = (
        df.groupby("producto", as_index=False)
        .agg(
            media_fabricada=("qty_fabricada", "mean"),
            std_fabricada=("qty_fabricada", "std"),
            periodos=("periodo", "nunique"),
        )
    )
    stats["std_fabricada"] = stats["std_fabricada"].fillna(0)
    stats["cv_fabricada"] = np.where(
        stats["media_fabricada"] > 0,
        stats["std_fabricada"] / stats["media_fabricada"],
        np.nan,
    )
    return stats.sort_values("media_fabricada", ascending=False).reset_index(drop=True)
