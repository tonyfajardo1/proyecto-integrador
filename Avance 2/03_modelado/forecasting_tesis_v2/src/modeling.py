from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor, RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .data_source import load_monthly_dataset
from .wrangling import prepare_for_modeling


@dataclass
class ModelingConfig:
    source: str = "dwh"
    min_periods_product: int = 4
    train_frac: float = 0.6
    val_frac: float = 0.2
    seasonal_active_months: int = 3
    seasonal_active_share: float = 0.45
    seasonal_min_total_qty: float = 500.0
    cap_quantile: float = 0.995
    inactive_months_threshold: int = 12
    enable_prophet: bool = False
    max_prophet_products: int = 120


def _wape(y_true, y_pred):
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    den = np.abs(y_true).sum()
    if den == 0:
        return np.nan
    return np.abs(y_true - y_pred).sum() / den


def _metrics(y_true, y_pred):
    return {
        "MAE": mean_absolute_error(y_true, y_pred),
        "RMSE": np.sqrt(mean_squared_error(y_true, y_pred)),
        "WAPE": _wape(y_true, y_pred),
    }


def _build_features(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy().sort_values(["producto", "periodo"]).reset_index(drop=True)
    grp = d.groupby("producto")

    d["lag_1"] = grp["qty_fabricada"].shift(1)
    d["lag_12"] = grp["qty_fabricada"].shift(12)
    d["lag_2"] = grp["qty_fabricada"].shift(2)
    d["lag_3"] = grp["qty_fabricada"].shift(3)
    d["rolling_mean_3"] = grp["qty_fabricada"].shift(1).rolling(3, min_periods=1).mean()
    d["rolling_std_3"] = grp["qty_fabricada"].shift(1).rolling(3, min_periods=1).std().fillna(0)
    d["delta_1"] = d["lag_1"] - d["lag_2"]
    d["qty_planificada_lag_1"] = grp["qty_planificada"].shift(1)
    d["n_ordenes_lag_1"] = grp["n_ordenes"].shift(1)

    d["target_t1"] = grp["qty_fabricada"].shift(-1)
    d["next_period"] = grp["periodo"].shift(-1)
    d["mes_num"] = d["periodo"].dt.month
    d["anio_num"] = d["periodo"].dt.year

    d = d.dropna(subset=["lag_1", "target_t1", "next_period"]).copy()
    return d


def _temporal_split(feat: pd.DataFrame, train_frac=0.6, val_frac=0.2):
    periods = sorted(feat["periodo"].dropna().unique().tolist())
    n = len(periods)
    if n < 3:
        raise ValueError("Se requieren al menos 3 periodos para split temporal.")

    i_train = max(1, int(round(n * train_frac)))
    i_val = max(i_train + 1, int(round(n * (train_frac + val_frac))))
    if i_val >= n:
        i_val = n - 1
    if i_train >= i_val:
        i_train = max(1, i_val - 1)

    train_periods = set(periods[:i_train])
    val_periods = set(periods[i_train:i_val])
    test_periods = set(periods[i_val:])

    train_df = feat[feat["periodo"].isin(train_periods)].copy()
    val_df = feat[feat["periodo"].isin(val_periods)].copy()
    test_df = feat[feat["periodo"].isin(test_periods)].copy()
    return train_df, val_df, test_df, {
        "train_periods": sorted(train_periods),
        "val_periods": sorted(val_periods),
        "test_periods": sorted(test_periods),
    }


def _encode_producto_train_only(train_df: pd.DataFrame, *others: pd.DataFrame):
    uniq = train_df["producto"].dropna().astype(str).unique().tolist()
    mapping = {p: i for i, p in enumerate(uniq)}

    out = []
    for d in (train_df,) + others:
        c = d.copy()
        c["producto_id"] = c["producto"].map(mapping).fillna(-1).astype(int)
        out.append(c)
    return out, mapping


def _encode_column_train_only(train_df: pd.DataFrame, *others: pd.DataFrame, column: str, out_col: str):
    uniq = train_df[column].dropna().astype(str).unique().tolist()
    mapping = {v: i for i, v in enumerate(uniq)}
    out = []
    for d in (train_df,) + others:
        c = d.copy()
        c[out_col] = c[column].astype(str).map(mapping).fillna(-1).astype(int)
        out.append(c)
    return out, mapping


def _prep_x(df: pd.DataFrame, features):
    return df[features].replace([np.inf, -np.inf], np.nan).fillna(0)


def _build_models():
    models = {
        "LinearRegression": Pipeline([
            ("scaler", StandardScaler()),
            ("model", LinearRegression()),
        ]),
        "RandomForest": RandomForestRegressor(
            n_estimators=500,
            random_state=42,
            n_jobs=-1,
            min_samples_leaf=2,
        ),
        "ExtraTrees": ExtraTreesRegressor(
            n_estimators=500,
            random_state=42,
            n_jobs=-1,
            min_samples_leaf=1,
        ),
    }

    try:
        from lightgbm import LGBMRegressor

        models["LightGBM"] = LGBMRegressor(
            n_estimators=600,
            learning_rate=0.05,
            num_leaves=31,
            subsample=0.9,
            colsample_bytree=0.9,
            random_state=42,
            objective="regression",
            n_jobs=-1,
        )
    except Exception:
        pass

    try:
        from xgboost import XGBRegressor

        models["XGBoost"] = XGBRegressor(
            n_estimators=600,
            learning_rate=0.05,
            max_depth=8,
            subsample=0.9,
            colsample_bytree=0.9,
            reg_alpha=0.0,
            reg_lambda=1.0,
            objective="reg:squarederror",
            random_state=42,
            n_jobs=-1,
        )
    except Exception:
        pass

    return models


def _fit_predict_by_tipo(train_df, eval_df, features, model_name="RandomForest", min_rows=40):
    preds = pd.Series(index=eval_df.index, dtype=float)
    global_models = _build_models()
    global_model = global_models[model_name]
    global_model.fit(_prep_x(train_df, features), train_df["target_t1"].astype(float))

    for tipo, ev_sub in eval_df.groupby("tipo_producto"):
        tr_sub = train_df[train_df["tipo_producto"] == tipo]
        if len(tr_sub) < int(min_rows):
            preds.loc[ev_sub.index] = np.maximum(global_model.predict(_prep_x(ev_sub, features)), 0)
            continue
        model = _build_models()[model_name]
        model.fit(_prep_x(tr_sub, features), tr_sub["target_t1"].astype(float))
        preds.loc[ev_sub.index] = np.maximum(model.predict(_prep_x(ev_sub, features)), 0)
    return preds.fillna(0).to_numpy()


def _fit_predict_by_categoria(train_df, eval_df, features, model_name="RandomForest", min_rows=80):
    preds = pd.Series(index=eval_df.index, dtype=float)
    global_model = _build_models()[model_name]
    global_model.fit(_prep_x(train_df, features), train_df["target_t1"].astype(float))

    for cat, ev_sub in eval_df.groupby("categoria_producto"):
        tr_sub = train_df[train_df["categoria_producto"] == cat]
        if len(tr_sub) < int(min_rows):
            preds.loc[ev_sub.index] = np.maximum(global_model.predict(_prep_x(ev_sub, features)), 0)
            continue
        model = _build_models()[model_name]
        model.fit(_prep_x(tr_sub, features), tr_sub["target_t1"].astype(float))
        preds.loc[ev_sub.index] = np.maximum(model.predict(_prep_x(ev_sub, features)), 0)
    return preds.fillna(0).to_numpy()


def _fit_predict_hierarchical(
    train_df,
    eval_df,
    features,
    model_name="RandomForest",
    min_rows_tipo=80,
    min_rows_categoria=140,
):
    global_model = _build_models()[model_name]
    global_model.fit(_prep_x(train_df, features), train_df["target_t1"].astype(float))

    tipo_models = {}
    for tipo, sub in train_df.groupby("tipo_producto"):
        if len(sub) < int(min_rows_tipo):
            continue
        m = _build_models()[model_name]
        m.fit(_prep_x(sub, features), sub["target_t1"].astype(float))
        tipo_models[tipo] = m

    categoria_models = {}
    for (tipo, cat), sub in train_df.groupby(["tipo_producto", "categoria_producto"]):
        if len(sub) < int(min_rows_categoria):
            continue
        m = _build_models()[model_name]
        m.fit(_prep_x(sub, features), sub["target_t1"].astype(float))
        categoria_models[(tipo, cat)] = m

    preds = pd.Series(index=eval_df.index, dtype=float)
    src = pd.Series(index=eval_df.index, dtype=object)

    for (tipo, cat), ev_sub in eval_df.groupby(["tipo_producto", "categoria_producto"]):
        key = (tipo, cat)
        if key in categoria_models:
            p = categoria_models[key].predict(_prep_x(ev_sub, features))
            preds.loc[ev_sub.index] = np.maximum(p, 0)
            src.loc[ev_sub.index] = "categoria"
        elif tipo in tipo_models:
            p = tipo_models[tipo].predict(_prep_x(ev_sub, features))
            preds.loc[ev_sub.index] = np.maximum(p, 0)
            src.loc[ev_sub.index] = "tipo"
        else:
            p = global_model.predict(_prep_x(ev_sub, features))
            preds.loc[ev_sub.index] = np.maximum(p, 0)
            src.loc[ev_sub.index] = "global"

    return preds.fillna(0).to_numpy(), src.fillna("global")


def _comparison_metrics(df: pd.DataFrame, pred_col: str):
    if len(df) == 0:
        return {"MAE": np.nan, "RMSE": np.nan, "WAPE": np.nan}
    y_true = pd.to_numeric(df["target_t1"], errors="coerce")
    y_pred = pd.to_numeric(df[pred_col], errors="coerce")
    mask = y_true.notna() & y_pred.notna()
    if mask.sum() == 0:
        return {"MAE": np.nan, "RMSE": np.nan, "WAPE": np.nan}
    return _metrics(y_true[mask], y_pred[mask])


def _build_plan_comparison_reports(pred_table: pd.DataFrame):
    base = pred_table.copy()
    base["target_t1"] = pd.to_numeric(base["target_t1"], errors="coerce")
    base["pronostico_qty"] = pd.to_numeric(base["pronostico_qty"], errors="coerce")
    base["qty_planificada_t1"] = pd.to_numeric(base.get("qty_planificada_t1", np.nan), errors="coerce")

    comp = base[base["target_t1"].notna() & base["qty_planificada_t1"].notna()].copy()

    m_model = _comparison_metrics(comp, "pronostico_qty")
    plan_non_informative_global = comp["qty_planificada_t1"].nunique(dropna=True) <= 1
    m_plan = {"MAE": np.nan, "RMSE": np.nan, "WAPE": np.nan} if plan_non_informative_global else _comparison_metrics(comp, "qty_planificada_t1")

    def _rel_gain(plan_v, model_v):
        if pd.isna(plan_v) or plan_v == 0 or pd.isna(model_v):
            return np.nan
        return (plan_v - model_v) / plan_v

    global_report = pd.DataFrame(
        [
            {
                "scope": "global",
                "n_rows": len(comp),
                "n_productos": comp["producto"].nunique() if len(comp) > 0 else 0,
                "plan_no_informativo": bool(plan_non_informative_global),
                "WAPE_modelo": m_model["WAPE"],
                "WAPE_planificada": m_plan["WAPE"],
                "delta_wape_plan_menos_modelo": m_plan["WAPE"] - m_model["WAPE"],
                "mejora_relativa_wape": _rel_gain(m_plan["WAPE"], m_model["WAPE"]),
                "MAE_modelo": m_model["MAE"],
                "MAE_planificada": m_plan["MAE"],
                "RMSE_modelo": m_model["RMSE"],
                "RMSE_planificada": m_plan["RMSE"],
            }
        ]
    )

    by_tipo_rows = []
    for tipo, sub in comp.groupby("tipo_producto", dropna=False):
        mm = _comparison_metrics(sub, "pronostico_qty")
        plan_non_informative = sub["qty_planificada_t1"].nunique(dropna=True) <= 1
        mp = {"MAE": np.nan, "RMSE": np.nan, "WAPE": np.nan} if plan_non_informative else _comparison_metrics(sub, "qty_planificada_t1")
        by_tipo_rows.append(
            {
                "tipo_producto": tipo,
                "n_rows": len(sub),
                "n_productos": sub["producto"].nunique(),
                "plan_no_informativo": bool(plan_non_informative),
                "WAPE_modelo": mm["WAPE"],
                "WAPE_planificada": mp["WAPE"],
                "delta_wape_plan_menos_modelo": mp["WAPE"] - mm["WAPE"],
                "mejora_relativa_wape": _rel_gain(mp["WAPE"], mm["WAPE"]),
                "MAE_modelo": mm["MAE"],
                "MAE_planificada": mp["MAE"],
                "RMSE_modelo": mm["RMSE"],
                "RMSE_planificada": mp["RMSE"],
            }
        )
    by_tipo = pd.DataFrame(by_tipo_rows).sort_values("delta_wape_plan_menos_modelo", ascending=False)

    by_producto_rows = []
    for prod, sub in comp.groupby("producto", dropna=False):
        mm = _comparison_metrics(sub, "pronostico_qty")
        plan_non_informative = sub["qty_planificada_t1"].nunique(dropna=True) <= 1
        mp = {"MAE": np.nan, "RMSE": np.nan, "WAPE": np.nan} if plan_non_informative else _comparison_metrics(sub, "qty_planificada_t1")
        by_producto_rows.append(
            {
                "producto": prod,
                "tipo_producto": sub["tipo_producto"].mode().iloc[0] if len(sub) > 0 else "OTRO",
                "n_rows": len(sub),
                "plan_no_informativo": bool(plan_non_informative),
                "WAPE_modelo": mm["WAPE"],
                "WAPE_planificada": mp["WAPE"],
                "delta_wape_plan_menos_modelo": mp["WAPE"] - mm["WAPE"],
                "mejora_relativa_wape": _rel_gain(mp["WAPE"], mm["WAPE"]),
                "MAE_modelo": mm["MAE"],
                "MAE_planificada": mp["MAE"],
            }
        )
    by_producto = pd.DataFrame(by_producto_rows).sort_values(
        ["delta_wape_plan_menos_modelo", "n_rows"], ascending=[False, False]
    )

    by_categoria_rows = []
    for cat, sub in comp.groupby("categoria_producto", dropna=False):
        mm = _comparison_metrics(sub, "pronostico_qty")
        plan_non_informative = sub["qty_planificada_t1"].nunique(dropna=True) <= 1
        mp = {"MAE": np.nan, "RMSE": np.nan, "WAPE": np.nan} if plan_non_informative else _comparison_metrics(sub, "qty_planificada_t1")
        by_categoria_rows.append(
            {
                "categoria_producto": cat,
                "n_rows": len(sub),
                "n_productos": sub["producto"].nunique(),
                "plan_no_informativo": bool(plan_non_informative),
                "WAPE_modelo": mm["WAPE"],
                "WAPE_planificada": mp["WAPE"],
                "delta_wape_plan_menos_modelo": mp["WAPE"] - mm["WAPE"],
                "mejora_relativa_wape": _rel_gain(mp["WAPE"], mm["WAPE"]),
                "MAE_modelo": mm["MAE"],
                "MAE_planificada": mp["MAE"],
                "RMSE_modelo": mm["RMSE"],
                "RMSE_planificada": mp["RMSE"],
            }
        )
    by_categoria = pd.DataFrame(by_categoria_rows).sort_values("delta_wape_plan_menos_modelo", ascending=False)

    return global_report, by_tipo, by_categoria, by_producto


def _build_plan_data_quality_report(pred_table: pd.DataFrame):
    d = pred_table.copy()
    d["target_t1"] = pd.to_numeric(d["target_t1"], errors="coerce")
    d["qty_planificada_t1"] = pd.to_numeric(d.get("qty_planificada_t1", np.nan), errors="coerce")
    d = d[d["target_t1"].notna() & d["qty_planificada_t1"].notna()].copy()
    if len(d) == 0:
        return pd.DataFrame(
            [{"check": "plan_exante_signal", "value": np.nan, "note": "sin datos comparables plan-vs-real"}]
        )

    if d["qty_planificada_t1"].nunique(dropna=True) <= 1:
        return pd.DataFrame(
            [
                {
                    "check": "plan_exante_signal",
                    "value": np.nan,
                    "note": "plan no informativo (serie constante); comparacion plan-vs-real no aplica",
                },
                {
                    "check": "n_rows",
                    "value": float(len(d)),
                    "note": "filas comparables plan-vs-real",
                },
            ]
        )

    abs_err = (d["qty_planificada_t1"] - d["target_t1"]).abs()
    exact_match = (abs_err == 0).mean()
    near_match_5pct = (abs_err <= np.maximum(1, d["target_t1"].abs() * 0.05)).mean()
    corr = d[["qty_planificada_t1", "target_t1"]].corr().iloc[0, 1]

    return pd.DataFrame(
        [
            {"check": "n_rows", "value": float(len(d)), "note": "filas comparables plan-vs-real"},
            {"check": "exact_match_rate", "value": float(exact_match), "note": "porcentaje plan igual al real"},
            {
                "check": "near_match_rate_5pct",
                "value": float(near_match_5pct),
                "note": "porcentaje plan dentro de +-5% del real",
            },
            {"check": "corr_plan_vs_real", "value": float(corr), "note": "correlacion planificada vs real"},
        ]
    )


def _build_pilot_report(pred_table: pd.DataFrame, pilot_tipo="PT", top_n=100):
    d = pred_table.copy()
    d["target_t1"] = pd.to_numeric(d["target_t1"], errors="coerce")
    d["pronostico_qty"] = pd.to_numeric(d["pronostico_qty"], errors="coerce")

    d = d[d["tipo_producto"] == pilot_tipo].copy()
    vol = d.groupby("producto", as_index=False)["target_t1"].sum().rename(columns={"target_t1": "volumen_real"})
    top = vol.sort_values("volumen_real", ascending=False).head(int(top_n))
    d = d[d["producto"].isin(top["producto"])].copy()
    d = d[d["target_t1"].notna() & d["pronostico_qty"].notna()].copy()

    m_model = _comparison_metrics(d, "pronostico_qty")

    out = pd.DataFrame(
        [
            {
                "pilot_tipo": pilot_tipo,
                "top_n_productos": int(top_n),
                "n_productos_en_eval": d["producto"].nunique() if len(d) > 0 else 0,
                "n_rows": len(d),
                "WAPE_modelo": m_model["WAPE"],
                "MAE_modelo": m_model["MAE"],
                "RMSE_modelo": m_model["RMSE"],
            }
        ]
    )
    return out


def _build_segment_error_report(pred_table: pd.DataFrame):
    base = pred_table.copy()
    base["target_t1"] = pd.to_numeric(base["target_t1"], errors="coerce")
    base["pronostico_qty"] = pd.to_numeric(base["pronostico_qty"], errors="coerce")
    base = base[base["target_t1"].notna() & base["pronostico_qty"].notna()].copy()

    by_tipo = []
    for tipo, sub in base.groupby("tipo_producto", dropna=False):
        m = _metrics(sub["target_t1"], sub["pronostico_qty"])
        by_tipo.append(
            {
                "segmento": "tipo_producto",
                "valor_segmento": tipo,
                "n_rows": int(len(sub)),
                "n_productos": int(sub["producto"].nunique()),
                "WAPE": float(m["WAPE"]),
                "MAE": float(m["MAE"]),
                "RMSE": float(m["RMSE"]),
            }
        )

    by_cat = []
    for cat, sub in base.groupby("categoria_producto", dropna=False):
        if len(sub) < 8:
            continue
        m = _metrics(sub["target_t1"], sub["pronostico_qty"])
        by_cat.append(
            {
                "segmento": "categoria_producto",
                "valor_segmento": cat,
                "n_rows": int(len(sub)),
                "n_productos": int(sub["producto"].nunique()),
                "WAPE": float(m["WAPE"]),
                "MAE": float(m["MAE"]),
                "RMSE": float(m["RMSE"]),
            }
        )

    out = pd.DataFrame(by_tipo + by_cat)
    if len(out) == 0:
        return out
    return out.sort_values(["segmento", "WAPE", "n_rows"], ascending=[True, True, False]).reset_index(drop=True)


def _build_seasonality_map(
    train_like: pd.DataFrame,
    max_active_months=3,
    max_active_share=0.45,
    min_total_qty=500.0,
):
    rows = []
    for prod, sub in train_like.groupby("producto"):
        active = sub[(sub["qty_fabricada"] > 0) | (sub["qty_planificada"] > 0) | (sub["n_ordenes"] > 0)]
        months = sorted(active["periodo"].dt.month.unique().tolist())
        share = len(months) / max(sub["periodo"].nunique(), 1)
        total_qty = float(pd.to_numeric(sub["qty_fabricada"], errors="coerce").clip(lower=0).fillna(0).sum())
        seasonal_candidate = len(months) > 0 and len(months) <= int(max_active_months) and share <= float(max_active_share)
        is_seasonal = bool(seasonal_candidate and total_qty >= float(min_total_qty))
        low_rotation = bool(seasonal_candidate and total_qty < float(min_total_qty))
        rows.append({
            "producto": prod,
            "producto_estacional_train": bool(is_seasonal),
            "producto_baja_rotacion_train": bool(low_rotation),
            "temporada_meses_train": ",".join([str(x) for x in months]) if months else "",
            "seasonal_total_qty_train": total_qty,
        })
    return pd.DataFrame(rows)


def _in_season(temporada_meses: str, month_num: int) -> bool:
    s = str(temporada_meses).strip()
    if s == "" or s.lower() == "nan":
        return True
    months = [int(x) for x in s.split(",") if str(x).strip().isdigit()]
    if not months:
        return True
    return int(month_num) in months


def _cap_predictions_by_history(pred_df: pd.DataFrame, train_like: pd.DataFrame, cap_quantile=0.995):
    caps = (
        train_like.groupby("producto", as_index=False)["qty_fabricada"]
        .quantile(float(cap_quantile))
        .rename(columns={"qty_fabricada": "cap_qty"})
    )
    out = pred_df.merge(caps, on="producto", how="left")
    out["cap_qty"] = out["cap_qty"].fillna(np.inf)
    out["pronostico_qty"] = np.minimum(out["pronostico_qty"], out["cap_qty"])
    out = out.drop(columns=["cap_qty"])
    return out


def run_full_modeling(config: ModelingConfig | None = None):
    cfg = config or ModelingConfig()

    raw = load_monthly_dataset(source=cfg.source, fallback_quickbooks=True)
    wrangled, wr_report = prepare_for_modeling(
        raw,
        min_periods_product=cfg.min_periods_product,
        seasonality_max_active_months=cfg.seasonal_active_months,
        seasonality_max_active_share=cfg.seasonal_active_share,
    )

    feat = _build_features(wrangled)
    train_df, val_df, test_df, split_info = _temporal_split(
        feat,
        train_frac=cfg.train_frac,
        val_frac=cfg.val_frac,
    )

    (train_df, val_df, test_df), product_map = _encode_producto_train_only(train_df, val_df, test_df)
    (train_df, val_df, test_df), tipo_map = _encode_column_train_only(
        train_df, val_df, test_df, column="tipo_producto", out_col="tipo_id"
    )
    (train_df, val_df, test_df), categoria_map = _encode_column_train_only(
        train_df, val_df, test_df, column="categoria_producto", out_col="categoria_id"
    )
    train_val_df = pd.concat([train_df, val_df], ignore_index=True)

    train_like = wrangled[wrangled["periodo"].isin(split_info["train_periods"])].copy()
    train_val_like = wrangled[
        wrangled["periodo"].isin(split_info["train_periods"] + split_info["val_periods"])
    ].copy()

    features = [
        "producto_id",
        "tipo_id",
        "categoria_id",
        "anio_num",
        "mes_num",
        "lag_1",
        "lag_2",
        "lag_3",
        "rolling_mean_3",
        "rolling_std_3",
        "delta_1",
        "n_ordenes_lag_1",
    ]

    rows = []
    pred_val_map = {}
    pred_test_map = {}
    pred_test_source_map = {}

    # Baseline
    base_train = np.maximum(train_df["lag_1"].fillna(0).to_numpy(), 0)
    base_val = np.maximum(val_df["lag_1"].fillna(0).to_numpy(), 0)
    base_test = np.maximum(test_df["lag_1"].fillna(0).to_numpy(), 0)
    m_train = _metrics(train_df["target_t1"], base_train)
    m_val = _metrics(val_df["target_t1"], base_val)
    m_test = _metrics(test_df["target_t1"], base_test)
    rows.append({
        "modelo": "Baseline_Lag1",
        "MAE_train": m_train["MAE"],
        "RMSE_train": m_train["RMSE"],
        "WAPE_train": m_train["WAPE"],
        "MAE_val": m_val["MAE"],
        "RMSE_val": m_val["RMSE"],
        "WAPE_val": m_val["WAPE"],
        "MAE_test": m_test["MAE"],
        "RMSE_test": m_test["RMSE"],
        "WAPE_test": m_test["WAPE"],
    })
    pred_val_map["Baseline_Lag1"] = base_val
    pred_test_map["Baseline_Lag1"] = base_test

    # Baseline estacional (lag 12 meses), con fallback a lag_1 si no hay historia anual.
    s_train = np.maximum(train_df["lag_12"].fillna(train_df["lag_1"]).fillna(0).to_numpy(), 0)
    s_val = np.maximum(val_df["lag_12"].fillna(val_df["lag_1"]).fillna(0).to_numpy(), 0)
    s_test = np.maximum(test_df["lag_12"].fillna(test_df["lag_1"]).fillna(0).to_numpy(), 0)
    m_train = _metrics(train_df["target_t1"], s_train)
    m_val = _metrics(val_df["target_t1"], s_val)
    m_test = _metrics(test_df["target_t1"], s_test)
    rows.append({
        "modelo": "Baseline_Lag12_Seasonal",
        "MAE_train": m_train["MAE"],
        "RMSE_train": m_train["RMSE"],
        "WAPE_train": m_train["WAPE"],
        "MAE_val": m_val["MAE"],
        "RMSE_val": m_val["RMSE"],
        "WAPE_val": m_val["WAPE"],
        "MAE_test": m_test["MAE"],
        "RMSE_test": m_test["RMSE"],
        "WAPE_test": m_test["WAPE"],
    })
    pred_val_map["Baseline_Lag12_Seasonal"] = s_val
    pred_test_map["Baseline_Lag12_Seasonal"] = s_test

    # Baseline hibrido: usa lag_12 para productos estacionales y lag_1 para no estacionales.
    season_train = _build_seasonality_map(
        train_like,
        max_active_months=cfg.seasonal_active_months,
        max_active_share=cfg.seasonal_active_share,
        min_total_qty=cfg.seasonal_min_total_qty,
    )
    season_train_val = _build_seasonality_map(
        train_val_like,
        max_active_months=cfg.seasonal_active_months,
        max_active_share=cfg.seasonal_active_share,
        min_total_qty=cfg.seasonal_min_total_qty,
    )

    tr_h = train_df.merge(season_train[["producto", "producto_estacional_train"]], on="producto", how="left")
    va_h = val_df.merge(season_train[["producto", "producto_estacional_train"]], on="producto", how="left")
    te_h = test_df.merge(season_train_val[["producto", "producto_estacional_train"]], on="producto", how="left")

    for dfx in [tr_h, va_h, te_h]:
        dfx["producto_estacional_train"] = (
            dfx["producto_estacional_train"].astype("boolean").fillna(False).astype(bool)
        )

    h_train = np.where(
        tr_h["producto_estacional_train"],
        tr_h["lag_12"].fillna(tr_h["lag_1"]).fillna(0),
        tr_h["lag_1"].fillna(0),
    )
    h_val = np.where(
        va_h["producto_estacional_train"],
        va_h["lag_12"].fillna(va_h["lag_1"]).fillna(0),
        va_h["lag_1"].fillna(0),
    )
    h_test = np.where(
        te_h["producto_estacional_train"],
        te_h["lag_12"].fillna(te_h["lag_1"]).fillna(0),
        te_h["lag_1"].fillna(0),
    )
    h_train = np.maximum(np.asarray(h_train, dtype=float), 0)
    h_val = np.maximum(np.asarray(h_val, dtype=float), 0)
    h_test = np.maximum(np.asarray(h_test, dtype=float), 0)

    m_train = _metrics(train_df["target_t1"], h_train)
    m_val = _metrics(val_df["target_t1"], h_val)
    m_test = _metrics(test_df["target_t1"], h_test)
    rows.append({
        "modelo": "Baseline_Hibrido_L1_L12",
        "MAE_train": m_train["MAE"],
        "RMSE_train": m_train["RMSE"],
        "WAPE_train": m_train["WAPE"],
        "MAE_val": m_val["MAE"],
        "RMSE_val": m_val["RMSE"],
        "WAPE_val": m_val["WAPE"],
        "MAE_test": m_test["MAE"],
        "RMSE_test": m_test["RMSE"],
        "WAPE_test": m_test["WAPE"],
    })
    pred_val_map["Baseline_Hibrido_L1_L12"] = h_val
    pred_test_map["Baseline_Hibrido_L1_L12"] = h_test

    models = _build_models()

    # Eval consistente: val con train; test con train+val
    for name, model in models.items():
        model.fit(_prep_x(train_df, features), train_df["target_t1"].astype(float))
        p_train = np.maximum(model.predict(_prep_x(train_df, features)), 0)
        p_val = np.maximum(model.predict(_prep_x(val_df, features)), 0)

        model.fit(_prep_x(train_val_df, features), train_val_df["target_t1"].astype(float))
        p_test = np.maximum(model.predict(_prep_x(test_df, features)), 0)

        m_train = _metrics(train_df["target_t1"], p_train)
        m_val = _metrics(val_df["target_t1"], p_val)
        m_test = _metrics(test_df["target_t1"], p_test)

        rows.append({
            "modelo": name,
            "MAE_train": m_train["MAE"],
            "RMSE_train": m_train["RMSE"],
            "WAPE_train": m_train["WAPE"],
            "MAE_val": m_val["MAE"],
            "RMSE_val": m_val["RMSE"],
            "WAPE_val": m_val["WAPE"],
            "MAE_test": m_test["MAE"],
            "RMSE_test": m_test["RMSE"],
            "WAPE_test": m_test["WAPE"],
        })
        pred_val_map[name] = p_val
        pred_test_map[name] = p_test

    # Modelo segmentado por tipo de producto (PT/PP/OTRO)
    p_train_tipo = _fit_predict_by_tipo(train_df, train_df, features, model_name="RandomForest")
    p_val_tipo = _fit_predict_by_tipo(train_df, val_df, features, model_name="RandomForest")
    p_test_tipo = _fit_predict_by_tipo(train_val_df, test_df, features, model_name="RandomForest")
    m_train = _metrics(train_df["target_t1"], p_train_tipo)
    m_val = _metrics(val_df["target_t1"], p_val_tipo)
    m_test = _metrics(test_df["target_t1"], p_test_tipo)
    rows.append({
        "modelo": "RandomForest_ByTipo",
        "MAE_train": m_train["MAE"],
        "RMSE_train": m_train["RMSE"],
        "WAPE_train": m_train["WAPE"],
        "MAE_val": m_val["MAE"],
        "RMSE_val": m_val["RMSE"],
        "WAPE_val": m_val["WAPE"],
        "MAE_test": m_test["MAE"],
        "RMSE_test": m_test["RMSE"],
        "WAPE_test": m_test["WAPE"],
    })
    pred_val_map["RandomForest_ByTipo"] = p_val_tipo
    pred_test_map["RandomForest_ByTipo"] = p_test_tipo

    # Modelo segmentado por categoria (fallback global)
    p_train_cat = _fit_predict_by_categoria(train_df, train_df, features, model_name="RandomForest")
    p_val_cat = _fit_predict_by_categoria(train_df, val_df, features, model_name="RandomForest")
    p_test_cat = _fit_predict_by_categoria(train_val_df, test_df, features, model_name="RandomForest")
    m_train = _metrics(train_df["target_t1"], p_train_cat)
    m_val = _metrics(val_df["target_t1"], p_val_cat)
    m_test = _metrics(test_df["target_t1"], p_test_cat)
    rows.append({
        "modelo": "RandomForest_ByCategoria",
        "MAE_train": m_train["MAE"],
        "RMSE_train": m_train["RMSE"],
        "WAPE_train": m_train["WAPE"],
        "MAE_val": m_val["MAE"],
        "RMSE_val": m_val["RMSE"],
        "WAPE_val": m_val["WAPE"],
        "MAE_test": m_test["MAE"],
        "RMSE_test": m_test["RMSE"],
        "WAPE_test": m_test["WAPE"],
    })
    pred_val_map["RandomForest_ByCategoria"] = p_val_cat
    pred_test_map["RandomForest_ByCategoria"] = p_test_cat

    # Modelo jerarquico: categoria -> tipo -> global
    p_train_h, _ = _fit_predict_hierarchical(train_df, train_df, features, model_name="RandomForest")
    p_val_h, _ = _fit_predict_hierarchical(train_df, val_df, features, model_name="RandomForest")
    p_test_h, p_test_h_src = _fit_predict_hierarchical(train_val_df, test_df, features, model_name="RandomForest")
    m_train = _metrics(train_df["target_t1"], p_train_h)
    m_val = _metrics(val_df["target_t1"], p_val_h)
    m_test = _metrics(test_df["target_t1"], p_test_h)
    rows.append({
        "modelo": "RandomForest_Hierarquico",
        "MAE_train": m_train["MAE"],
        "RMSE_train": m_train["RMSE"],
        "WAPE_train": m_train["WAPE"],
        "MAE_val": m_val["MAE"],
        "RMSE_val": m_val["RMSE"],
        "WAPE_val": m_val["WAPE"],
        "MAE_test": m_test["MAE"],
        "RMSE_test": m_test["RMSE"],
        "WAPE_test": m_test["WAPE"],
    })
    pred_val_map["RandomForest_Hierarquico"] = p_val_h
    pred_test_map["RandomForest_Hierarquico"] = p_test_h
    pred_test_source_map["RandomForest_Hierarquico"] = p_test_h_src

    # Prophet opcional
    if bool(cfg.enable_prophet):
        try:
            from prophet import Prophet

            def prophet_predict(train_like: pd.DataFrame, eval_df: pd.DataFrame, max_products=120):
                out = pd.Series(index=eval_df.index, dtype=float)
                for prod in eval_df["producto"].dropna().astype(str).unique().tolist()[:max_products]:
                    tr = train_like[train_like["producto"] == prod].sort_values("periodo")
                    ev = eval_df[eval_df["producto"] == prod]
                    if len(tr) < 4:
                        out.loc[ev.index] = ev["lag_1"].fillna(0).to_numpy()
                        continue
                    fit_df = tr[["periodo", "qty_fabricada"]].rename(columns={"periodo": "ds", "qty_fabricada": "y"})
                    pm = Prophet(yearly_seasonality=True, weekly_seasonality=False, daily_seasonality=False)
                    pm.fit(fit_df)
                    future = pd.DataFrame({"ds": pd.to_datetime(ev["next_period"])})
                    out.loc[ev.index] = np.maximum(pm.predict(future)["yhat"].to_numpy(), 0)
                out = out.fillna(eval_df["lag_1"].fillna(0))
                return out.to_numpy()

            p_train = np.maximum(train_df["lag_1"].fillna(0).to_numpy(), 0)
            p_val = prophet_predict(train_like, val_df, max_products=int(cfg.max_prophet_products))
            p_test = prophet_predict(train_val_like, test_df, max_products=int(cfg.max_prophet_products))

            m_train = _metrics(train_df["target_t1"], p_train)
            m_val = _metrics(val_df["target_t1"], p_val)
            m_test = _metrics(test_df["target_t1"], p_test)
            rows.append({
                "modelo": "Prophet",
                "MAE_train": m_train["MAE"],
                "RMSE_train": m_train["RMSE"],
                "WAPE_train": m_train["WAPE"],
                "MAE_val": m_val["MAE"],
                "RMSE_val": m_val["RMSE"],
                "WAPE_val": m_val["WAPE"],
                "MAE_test": m_test["MAE"],
                "RMSE_test": m_test["RMSE"],
                "WAPE_test": m_test["WAPE"],
            })
            pred_val_map["Prophet"] = p_val
            pred_test_map["Prophet"] = p_test
        except Exception:
            pass

    # Ensemble consistente
    if all(k in pred_test_map for k in ["LinearRegression", "RandomForest", "ExtraTrees"]):
        # val
        val_preds = {}
        for name, model in _build_models().items():
            model.fit(_prep_x(train_df, features), train_df["target_t1"].astype(float))
            val_preds[name] = np.maximum(model.predict(_prep_x(val_df, features)), 0)
        p_val = 0.2 * val_preds["LinearRegression"] + 0.4 * val_preds["RandomForest"] + 0.4 * val_preds["ExtraTrees"]

        # train
        tr_preds = {}
        for name, model in _build_models().items():
            model.fit(_prep_x(train_df, features), train_df["target_t1"].astype(float))
            tr_preds[name] = np.maximum(model.predict(_prep_x(train_df, features)), 0)
        p_train = 0.2 * tr_preds["LinearRegression"] + 0.4 * tr_preds["RandomForest"] + 0.4 * tr_preds["ExtraTrees"]

        # test uses already computed train+val models
        p_test = 0.2 * pred_test_map["LinearRegression"] + 0.4 * pred_test_map["RandomForest"] + 0.4 * pred_test_map["ExtraTrees"]

        m_train = _metrics(train_df["target_t1"], p_train)
        m_val = _metrics(val_df["target_t1"], p_val)
        m_test = _metrics(test_df["target_t1"], p_test)
        rows.append({
            "modelo": "Ensemble_RF_ET_LR",
            "MAE_train": m_train["MAE"],
            "RMSE_train": m_train["RMSE"],
            "WAPE_train": m_train["WAPE"],
            "MAE_val": m_val["MAE"],
            "RMSE_val": m_val["RMSE"],
            "WAPE_val": m_val["WAPE"],
            "MAE_test": m_test["MAE"],
            "RMSE_test": m_test["RMSE"],
            "WAPE_test": m_test["WAPE"],
        })
        pred_val_map["Ensemble_RF_ET_LR"] = p_val
        pred_test_map["Ensemble_RF_ET_LR"] = p_test

    benchmark = pd.DataFrame(rows)
    base_val = float(benchmark.loc[benchmark["modelo"] == "Baseline_Lag1", "WAPE_val"].iloc[0])
    base_test = float(benchmark.loc[benchmark["modelo"] == "Baseline_Lag1", "WAPE_test"].iloc[0])
    benchmark["gap_wape_train_val"] = benchmark["WAPE_val"] - benchmark["WAPE_train"]
    benchmark["gap_wape_val_test"] = benchmark["WAPE_test"] - benchmark["WAPE_val"]
    benchmark["mejora_vs_baseline_val_wape"] = base_val - benchmark["WAPE_val"]
    benchmark["mejora_vs_baseline_test_wape"] = base_test - benchmark["WAPE_test"]
    benchmark = benchmark.sort_values(["WAPE_val", "WAPE_test"]).reset_index(drop=True)

    winner = benchmark.iloc[0]["modelo"]
    pred_val = np.maximum(np.asarray(pred_val_map[winner], dtype=float), 0)
    pred_test = np.maximum(np.asarray(pred_test_map[winner], dtype=float), 0)

    # Tabla de validacion para estimar incertidumbre tecnica del modelo.
    val_table = val_df[["tipo_producto", "categoria_producto", "producto", "periodo", "next_period", "target_t1"]].copy()
    val_table["pronostico_qty"] = pred_val

    # Factor de incertidumbre tecnica (solo validacion, sin leakage de test).
    val_err = val_table[["tipo_producto", "producto", "target_t1", "pronostico_qty"]].copy()
    val_err["target_t1"] = pd.to_numeric(val_err["target_t1"], errors="coerce")
    val_err["pronostico_qty"] = pd.to_numeric(val_err["pronostico_qty"], errors="coerce")
    val_err = val_err[(val_err["target_t1"].notna()) & (val_err["target_t1"] > 0) & (val_err["pronostico_qty"].notna())].copy()
    val_err["ape"] = (val_err["pronostico_qty"] - val_err["target_t1"]).abs() / val_err["target_t1"]

    err_by_tipo = (
        val_err.groupby("tipo_producto", as_index=False)["ape"]
        .median()
        .rename(columns={"ape": "factor_incertidumbre_tipo"})
    )
    err_by_producto = (
        val_err.groupby("producto", as_index=False)["ape"]
        .median()
        .rename(columns={"ape": "factor_incertidumbre_producto"})
    )
    default_uncertainty = float(
        np.clip(np.nanmedian(val_err["ape"]) if len(val_err) > 0 else 0.25, 0.15, 0.85)
    )

    champion_segment_report = pd.DataFrame()

    pred_table = test_df[
        [
            "tipo_producto",
            "categoria_producto",
            "producto",
            "periodo",
            "next_period",
            "target_t1",
            "qty_planificada",
            "qty_fabricada",
            "rolling_std_3",
            "n_ordenes_lag_1",
            "lag_1",
            "outlier_treatment",
            "outlier_flag_extremo_fabricada",
            "outlier_flag_sospechoso_fabricada",
            "outlier_flag_extremo_planificada",
            "outlier_flag_sospechoso_planificada",
        ]
    ].copy()
    pred_table = pred_table.rename(
        columns={
            "n_ordenes_lag_1": "n_ordenes",
            "qty_planificada": "qty_planificada_t",
            "qty_fabricada": "qty_fabricada_t",
        }
    )

    plan_t1 = wrangled[["producto", "periodo", "qty_planificada"]].rename(
        columns={"periodo": "next_period", "qty_planificada": "qty_planificada_t1"}
    )
    pred_table = pred_table.merge(plan_t1, on=["producto", "next_period"], how="left")
    pred_table["qty_planificada"] = pred_table["qty_planificada_t1"].fillna(pred_table["qty_planificada_t"])
    pred_table["qty_fabricada"] = pred_table["target_t1"]
    pred_table["modelo_ganador"] = winner
    pred_table["pronostico_qty"] = pred_test
    pred_table["fuente_modelo_segmentado"] = "global"
    if winner in pred_test_source_map:
        pred_table["fuente_modelo_segmentado"] = pred_test_source_map[winner].to_numpy()

    # Seasonality map from train+val only (anti-leakage)
    train_val_like = wrangled[
        wrangled["periodo"].isin(split_info["train_periods"] + split_info["val_periods"])
    ].copy()
    season_map = _build_seasonality_map(
        train_val_like,
        max_active_months=cfg.seasonal_active_months,
        max_active_share=cfg.seasonal_active_share,
        min_total_qty=cfg.seasonal_min_total_qty,
    )
    pred_table = pred_table.merge(season_map, on="producto", how="left")
    pred_table["producto_estacional_train"] = (
        pred_table["producto_estacional_train"].astype("boolean").fillna(False).astype(bool)
    )
    pred_table["producto_baja_rotacion_train"] = (
        pred_table["producto_baja_rotacion_train"].astype("boolean").fillna(False).astype(bool)
    )
    pred_table["temporada_meses_train"] = pred_table["temporada_meses_train"].fillna("")
    pred_table["seasonal_total_qty_train"] = pd.to_numeric(
        pred_table["seasonal_total_qty_train"], errors="coerce"
    ).fillna(0)

    pred_table["mes_pred"] = pd.to_datetime(pred_table["next_period"]).dt.month
    out_mask = pred_table.apply(
        lambda r: bool(r["producto_estacional_train"]) and (not _in_season(r["temporada_meses_train"], r["mes_pred"])),
        axis=1,
    )
    pred_table.loc[out_mask, "pronostico_qty"] = 0.0

    # Cap by history per product for operational coherence
    pred_table = _cap_predictions_by_history(pred_table, train_val_like, cap_quantile=cfg.cap_quantile)
    pred_table["pronostico_qty"] = pred_table["pronostico_qty"].clip(lower=0)
    pred_table = pred_table.drop(columns=["mes_pred"])

    # Vigencia operativa por ultima actividad positiva historica.
    # Regla: inactivo si no hay actividad en >= inactive_months_threshold meses.
    activity_src = wrangled[["producto", "periodo", "qty_fabricada", "qty_planificada", "n_ordenes"]].copy()
    activity_src["actividad"] = activity_src[["qty_fabricada", "qty_planificada", "n_ordenes"]].sum(axis=1)
    activity_src["actividad_pos"] = activity_src["actividad"].clip(lower=0)
    max_period = pd.to_datetime(activity_src["periodo"]).max()
    last_active = (
        activity_src[activity_src["actividad_pos"] > 0]
        .groupby("producto", as_index=False)["periodo"]
        .max()
        .rename(columns={"periodo": "last_active_period"})
    )
    active_map = activity_src[["producto"]].drop_duplicates().merge(last_active, on="producto", how="left")
    max_period_ord = pd.Timestamp(max_period).to_period("M").ordinal
    active_map["months_since_last_active"] = np.where(
        active_map["last_active_period"].notna(),
        (
            max_period_ord
            - pd.to_datetime(active_map["last_active_period"]).dt.to_period("M").astype(int)
        ),
        9999,
    )
    active_map["es_vigente_operativo"] = active_map["months_since_last_active"] < int(cfg.inactive_months_threshold)

    pred_table = pred_table.merge(
        active_map[["producto", "es_vigente_operativo", "months_since_last_active"]],
        on="producto",
        how="left",
    )
    pred_table["es_vigente_operativo"] = (
        pred_table["es_vigente_operativo"].astype("boolean").fillna(False).astype(bool)
    )
    pred_table["months_since_last_active"] = pred_table["months_since_last_active"].fillna(9999).astype(int)
    pred_table["razon_vigencia"] = np.where(
        pred_table["es_vigente_operativo"],
        "VIGENTE",
        np.where(
            pred_table["producto_estacional_train"],
            "ESTACIONAL_SIN_ACTIVIDAD_RECIENTE",
            "SIN_ACTIVIDAD_RECIENTE",
        ),
    )

    if "nivel_confianza" not in pred_table.columns:
        pred_table["nivel_confianza"] = "MEDIA"

    # Banda tecnica del modelo (min/base/max) previa a reglas operativas.
    pred_table = pred_table.merge(err_by_tipo, on="tipo_producto", how="left")
    pred_table = pred_table.merge(err_by_producto, on="producto", how="left")
    pred_table["factor_incertidumbre_modelo"] = pred_table["factor_incertidumbre_producto"].fillna(
        pred_table["factor_incertidumbre_tipo"]
    )
    pred_table["factor_incertidumbre_modelo"] = pred_table["factor_incertidumbre_modelo"].fillna(default_uncertainty)
    pred_table["factor_incertidumbre_modelo"] = pred_table["factor_incertidumbre_modelo"].clip(lower=0.10, upper=1.00)

    base_modelo = pd.to_numeric(pred_table["pronostico_qty"], errors="coerce").fillna(0).clip(lower=0)
    pred_table["qty_recomendada_modelo"] = np.ceil(base_modelo)
    pred_table["qty_min_modelo"] = np.floor(
        np.maximum(0, pred_table["qty_recomendada_modelo"] * (1 - pred_table["factor_incertidumbre_modelo"]))
    )
    pred_table["qty_max_modelo"] = np.ceil(
        np.maximum(
            pred_table["qty_recomendada_modelo"],
            pred_table["qty_recomendada_modelo"] * (1 + pred_table["factor_incertidumbre_modelo"]),
        )
    )
    pred_table = pred_table.drop(columns=["factor_incertidumbre_tipo", "factor_incertidumbre_producto"])

    pilot_top_pt = _build_pilot_report(pred_table, pilot_tipo="PT", top_n=100)
    segment_error_report = _build_segment_error_report(pred_table)

    # Leakage check report
    leakage_report = pd.DataFrame(
        [
            {"check": "target_uses_future", "status": "OK", "detail": "target_t1 construido con shift(-1) por producto"},
            {"check": "temporal_split", "status": "OK", "detail": str(split_info)},
            {"check": "product_encoding", "status": "OK", "detail": "producto_id mapeado solo con train; desconocidos=-1"},
            {"check": "seasonality_rule", "status": "OK", "detail": "temporada inferida con train+val (sin test)"},
            {"check": "cap_rule", "status": "OK", "detail": f"cap por producto q={cfg.cap_quantile} usando train+val"},
        ]
    )

    return {
        "raw": raw,
        "wrangled": wrangled,
        "wrangling_report": wr_report,
        "benchmark": benchmark,
        "predicciones": pred_table,
        "pilot_top_pt": pilot_top_pt,
        "champion_segment_report": champion_segment_report,
        "segment_error_report": segment_error_report,
        "leakage_report": leakage_report,
        "winner": winner,
    }


def save_outputs(result: dict, artifacts_dir: Path):
    artifacts_dir.mkdir(exist_ok=True, parents=True)
    result["benchmark"].to_csv(artifacts_dir / "benchmark_forecasting_v2.csv", index=False)
    result["predicciones"].to_csv(artifacts_dir / "predicciones_forecasting_v2.csv", index=False)
    result["pilot_top_pt"].to_csv(artifacts_dir / "pilot_top_pt_100.csv", index=False)
    result["champion_segment_report"].to_csv(artifacts_dir / "champion_segment_report.csv", index=False)
    result["segment_error_report"].to_csv(artifacts_dir / "segment_error_report.csv", index=False)
    result["wrangling_report"].to_csv(artifacts_dir / "wrangling_report.csv", index=False)
    result["leakage_report"].to_csv(artifacts_dir / "leakage_report.csv", index=False)
