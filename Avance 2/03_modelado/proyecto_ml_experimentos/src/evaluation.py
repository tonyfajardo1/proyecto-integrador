import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error


def wape(y_true, y_pred):
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    den = np.abs(y_true).sum()
    if den == 0:
        return np.nan
    return np.abs(y_true - y_pred).sum() / den


def regression_metrics(y_true, y_pred):
    return {
        "MAE": mean_absolute_error(y_true, y_pred),
        "RMSE": np.sqrt(mean_squared_error(y_true, y_pred)),
        "WAPE": wape(y_true, y_pred),
    }


def to_metrics_table(results):
    return pd.DataFrame(results).sort_values("WAPE", ascending=True).reset_index(drop=True)


def temporal_split_by_period(df, period_col="periodo", train_frac=0.6, val_frac=0.2):
    d = df.copy().sort_values(period_col).reset_index(drop=True)
    periods = sorted(d[period_col].dropna().unique().tolist())
    if len(periods) < 3:
        raise ValueError("Se requieren al menos 3 periodos para train/val/test temporal.")

    n = len(periods)
    i_train = max(1, int(round(n * train_frac)))
    i_val = max(i_train + 1, int(round(n * (train_frac + val_frac))))

    if i_val >= n:
        i_val = n - 1
    if i_train >= i_val:
        i_train = max(1, i_val - 1)

    train_periods = set(periods[:i_train])
    val_periods = set(periods[i_train:i_val])
    test_periods = set(periods[i_val:])

    train = d[d[period_col].isin(train_periods)].copy()
    val = d[d[period_col].isin(val_periods)].copy()
    test = d[d[period_col].isin(test_periods)].copy()

    return train, val, test, {
        "train_periods": sorted(train_periods),
        "val_periods": sorted(val_periods),
        "test_periods": sorted(test_periods),
    }
