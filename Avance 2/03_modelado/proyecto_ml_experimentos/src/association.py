import time
import numpy as np
import pandas as pd


def _build_baskets(df):
    transacciones = df.groupby("transaccion_id")["producto"].apply(list).tolist()
    transacciones = [x for x in transacciones if len(x) >= 2]
    return transacciones


def _split_transactions(df):
    d = df.copy()
    if "fecha" in d.columns:
        d["fecha"] = pd.to_datetime(d["fecha"], errors="coerce")
        tx = d.groupby("transaccion_id", as_index=False)["fecha"].min()
        tx = tx.sort_values("fecha").reset_index(drop=True)
    else:
        tx = pd.DataFrame({"transaccion_id": d["transaccion_id"].dropna().unique()})
        tx = tx.sort_values("transaccion_id").reset_index(drop=True)

    n = len(tx)
    if n < 30:
        raise ValueError("Muy pocas transacciones para split train/val/test robusto.")

    i_train = max(1, int(round(n * 0.6)))
    i_val = max(i_train + 1, int(round(n * 0.8)))
    if i_val >= n:
        i_val = n - 1

    train_ids = set(tx.iloc[:i_train]["transaccion_id"].astype(str))
    val_ids = set(tx.iloc[i_train:i_val]["transaccion_id"].astype(str))
    test_ids = set(tx.iloc[i_val:]["transaccion_id"].astype(str))

    d["transaccion_id"] = d["transaccion_id"].astype(str)
    return (
        d[d["transaccion_id"].isin(train_ids)].copy(),
        d[d["transaccion_id"].isin(val_ids)].copy(),
        d[d["transaccion_id"].isin(test_ids)].copy(),
    )


def _rules_to_key_set(reglas):
    if len(reglas) == 0:
        return set()
    keys = set()
    for _, r in reglas.iterrows():
        ant = tuple(sorted(list(r["antecedents"])))
        cons = tuple(sorted(list(r["consequents"])))
        keys.add((ant, cons))
    return keys


def _jaccard(a, b):
    if not a and not b:
        return 1.0
    den = len(a | b)
    if den == 0:
        return 0.0
    return len(a & b) / den


def _realized_confidence(rule_row, baskets):
    ant = set(rule_row["antecedents"])
    cons = set(rule_row["consequents"])
    ant_count = 0
    ant_cons_count = 0
    for b in baskets:
        sb = set(b)
        if ant.issubset(sb):
            ant_count += 1
            if cons.issubset(sb):
                ant_cons_count += 1
    if ant_count == 0:
        return np.nan
    return ant_cons_count / ant_count


def _realized_support(rule_row, baskets):
    full_set = set(rule_row["antecedents"]) | set(rule_row["consequents"])
    if len(baskets) == 0:
        return np.nan
    full_count = 0
    for b in baskets:
        if full_set.issubset(set(b)):
            full_count += 1
    return full_count / len(baskets)


def _rank_norm(series):
    if len(series) == 0:
        return series
    return series.rank(pct=True, method="average")


def _run_algorithm(
    algo_name,
    algo_fn,
    train_df,
    val_df,
    test_df,
    min_support,
    min_confidence,
    top_k,
    min_realized_conf_val,
    min_realized_conf_test,
    min_realized_support,
):
    from mlxtend.preprocessing import TransactionEncoder
    from mlxtend.frequent_patterns import association_rules

    train_baskets = _build_baskets(train_df)
    val_baskets = _build_baskets(val_df)
    test_baskets = _build_baskets(test_df)

    te = TransactionEncoder()
    arr_train = te.fit(train_baskets).transform(train_baskets, sparse=True)
    X_train = pd.DataFrame.sparse.from_spmatrix(arr_train, columns=te.columns_)

    t0 = time.perf_counter()
    itemsets_train = algo_fn(X_train, min_support=min_support, use_colnames=True, max_len=2)
    reglas_train = association_rules(itemsets_train, metric="confidence", min_threshold=min_confidence) if len(itemsets_train) > 0 else pd.DataFrame()
    fit_time = time.perf_counter() - t0

    if len(reglas_train) == 0:
        return {
            "algoritmo": algo_name,
            "reglas_train": 0,
            "lift_med_train": 0.0,
            "conf_val_prom": 0.0,
            "conf_test_prom": 0.0,
            "jaccard_train_val": 0.0,
            "jaccard_train_test": 0.0,
            "tiempo_seg": float(fit_time),
            "n_tx_train": len(train_baskets),
            "n_tx_val": len(val_baskets),
            "n_tx_test": len(test_baskets),
        }

    # Estabilidad de reglas contra splits holdout
    te_val = TransactionEncoder()
    arr_val = te_val.fit(val_baskets).transform(val_baskets, sparse=True)
    X_val = pd.DataFrame.sparse.from_spmatrix(arr_val, columns=te_val.columns_)
    itemsets_val = algo_fn(X_val, min_support=min_support, use_colnames=True, max_len=2)
    reglas_val = association_rules(itemsets_val, metric="confidence", min_threshold=min_confidence) if len(itemsets_val) > 0 else pd.DataFrame()

    te_test = TransactionEncoder()
    arr_test = te_test.fit(test_baskets).transform(test_baskets, sparse=True)
    X_test = pd.DataFrame.sparse.from_spmatrix(arr_test, columns=te_test.columns_)
    itemsets_test = algo_fn(X_test, min_support=min_support, use_colnames=True, max_len=2)
    reglas_test = association_rules(itemsets_test, metric="confidence", min_threshold=min_confidence) if len(itemsets_test) > 0 else pd.DataFrame()

    keys_train = _rules_to_key_set(reglas_train)
    keys_val = _rules_to_key_set(reglas_val)
    keys_test = _rules_to_key_set(reglas_test)

    reglas_eval = reglas_train.copy()
    reglas_eval["rule_key"] = [
        (tuple(sorted(list(r["antecedents"]))), tuple(sorted(list(r["consequents"]))))
        for _, r in reglas_eval.iterrows()
    ]
    reglas_eval["conf_val_realized"] = [
        _realized_confidence(r, val_baskets) for _, r in reglas_eval.iterrows()
    ]
    reglas_eval["conf_test_realized"] = [
        _realized_confidence(r, test_baskets) for _, r in reglas_eval.iterrows()
    ]
    reglas_eval["support_val_realized"] = [
        _realized_support(r, val_baskets) for _, r in reglas_eval.iterrows()
    ]
    reglas_eval["support_test_realized"] = [
        _realized_support(r, test_baskets) for _, r in reglas_eval.iterrows()
    ]
    reglas_eval["estabilidad_split"] = (
        reglas_eval["rule_key"].apply(lambda k: 1.0 if k in keys_val else 0.0)
        + reglas_eval["rule_key"].apply(lambda k: 1.0 if k in keys_test else 0.0)
    ) / 2.0

    reglas_filtradas = reglas_eval[
        (reglas_eval["conf_val_realized"].fillna(0) >= min_realized_conf_val)
        & (reglas_eval["conf_test_realized"].fillna(0) >= min_realized_conf_test)
        & (
            reglas_eval[["support_val_realized", "support_test_realized"]]
            .max(axis=1)
            .fillna(0)
            >= min_realized_support
        )
    ].copy()

    reglas_consenso = reglas_filtradas.copy()
    if len(reglas_consenso) > 0:
        reglas_consenso["rank_lift"] = _rank_norm(reglas_consenso["lift"].fillna(0))
        reglas_consenso["rank_conf_train"] = _rank_norm(reglas_consenso["confidence"].fillna(0))
        reglas_consenso["rank_conf_test"] = _rank_norm(reglas_consenso["conf_test_realized"].fillna(0))
        reglas_consenso["score_consenso"] = (
            reglas_consenso["rank_lift"] * 0.30
            + reglas_consenso["rank_conf_train"] * 0.25
            + reglas_consenso["rank_conf_test"] * 0.25
            + reglas_consenso["estabilidad_split"] * 0.20
        )
        reglas_top = reglas_consenso.sort_values("score_consenso", ascending=False).head(top_k).copy()
    else:
        reglas_top = reglas_train.sort_values("lift", ascending=False).head(top_k).copy()
        reglas_top["conf_val_realized"] = [
            _realized_confidence(r, val_baskets) for _, r in reglas_top.iterrows()
        ]
        reglas_top["conf_test_realized"] = [
            _realized_confidence(r, test_baskets) for _, r in reglas_top.iterrows()
        ]
        reglas_top["support_val_realized"] = [
            _realized_support(r, val_baskets) for _, r in reglas_top.iterrows()
        ]
        reglas_top["support_test_realized"] = [
            _realized_support(r, test_baskets) for _, r in reglas_top.iterrows()
        ]

    conf_val = reglas_top["conf_val_realized"].tolist() if "conf_val_realized" in reglas_top.columns else []
    conf_test = reglas_top["conf_test_realized"].tolist() if "conf_test_realized" in reglas_top.columns else []

    return {
        "algoritmo": algo_name,
        "reglas_train": int(len(reglas_train)),
        "reglas_filtradas_calidad": int(len(reglas_filtradas)),
        "reglas_top_consenso": int(len(reglas_top)),
        "lift_med_train": float(reglas_train["lift"].median()),
        "conf_val_prom": float(np.nanmean(conf_val)) if len(conf_val) > 0 else 0.0,
        "conf_test_prom": float(np.nanmean(conf_test)) if len(conf_test) > 0 else 0.0,
        "support_val_prom": float(np.nanmean(reglas_top.get("support_val_realized", pd.Series(dtype=float)))) if len(reglas_top) > 0 else 0.0,
        "support_test_prom": float(np.nanmean(reglas_top.get("support_test_realized", pd.Series(dtype=float)))) if len(reglas_top) > 0 else 0.0,
        "jaccard_train_val": float(_jaccard(keys_train, keys_val)),
        "jaccard_train_test": float(_jaccard(keys_train, keys_test)),
        "tiempo_seg": float(fit_time),
        "umbral_conf_val": float(min_realized_conf_val),
        "umbral_conf_test": float(min_realized_conf_test),
        "umbral_support_realized": float(min_realized_support),
        "n_tx_train": len(train_baskets),
        "n_tx_val": len(val_baskets),
        "n_tx_test": len(test_baskets),
    }


def benchmark_association(
    df,
    min_support=0.02,
    min_confidence=0.25,
    top_k=20,
    min_realized_conf_val=0.25,
    min_realized_conf_test=0.25,
    min_realized_support=0.005,
):
    from mlxtend.preprocessing import TransactionEncoder
    from mlxtend.frequent_patterns import apriori, fpgrowth

    _ = TransactionEncoder  # keep local dependency check

    train_df, val_df, test_df = _split_transactions(df)

    rows = []

    for nombre, algo in [("Apriori", apriori), ("FPGrowth", fpgrowth)]:
        rows.append(
            _run_algorithm(
                nombre,
                algo,
                train_df,
                val_df,
                test_df,
                min_support=min_support,
                min_confidence=min_confidence,
                top_k=top_k,
                min_realized_conf_val=min_realized_conf_val,
                min_realized_conf_test=min_realized_conf_test,
                min_realized_support=min_realized_support,
            )
        )

    out = pd.DataFrame(rows)
    out["score_general"] = (
        out["conf_test_prom"].fillna(0) * 0.4
        + out["jaccard_train_test"].fillna(0) * 0.3
        + out["lift_med_train"].fillna(0) * 0.2
        - out["tiempo_seg"].fillna(0) * 0.1 / (out["tiempo_seg"].max() + 1e-9)
    )
    return out.sort_values("score_general", ascending=False).reset_index(drop=True)


def benchmark_association_sensitivity(
    df,
    support_grid=(0.015, 0.02, 0.03),
    confidence_grid=(0.25, 0.30, 0.35),
    top_k=50,
    min_realized_conf_val=0.25,
    min_realized_conf_test=0.25,
    min_realized_support=0.005,
):
    all_rows = []
    for s in support_grid:
        for c in confidence_grid:
            try:
                res = benchmark_association(
                    df,
                    min_support=float(s),
                    min_confidence=float(c),
                    top_k=top_k,
                    min_realized_conf_val=min_realized_conf_val,
                    min_realized_conf_test=min_realized_conf_test,
                    min_realized_support=min_realized_support,
                ).copy()
                res["min_support"] = float(s)
                res["min_confidence"] = float(c)
                all_rows.append(res)
            except Exception:
                continue

    if not all_rows:
        return pd.DataFrame()

    out = pd.concat(all_rows, ignore_index=True)
    cols = [
        "algoritmo",
        "min_support",
        "min_confidence",
        "reglas_train",
        "reglas_filtradas_calidad",
        "reglas_top_consenso",
        "lift_med_train",
        "conf_val_prom",
        "conf_test_prom",
        "support_val_prom",
        "support_test_prom",
        "jaccard_train_val",
        "jaccard_train_test",
        "tiempo_seg",
        "umbral_conf_val",
        "umbral_conf_test",
        "umbral_support_realized",
        "score_general",
    ]
    cols = [c for c in cols if c in out.columns]
    return out[cols].sort_values("score_general", ascending=False).reset_index(drop=True)
