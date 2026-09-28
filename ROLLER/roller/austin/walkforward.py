"""Chronological walk-forward. Train dates strictly before evaluation."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from roller.austin.config import DEFAULT, AustinConfig, band_contracts
from roller.austin.errors import AustinError
from roller.austin.knn import match_query
from roller.austin.leakage import assert_train_before_eval
from roller.austin.pca import fit_pca, transform_row
from roller.austin.registry import load_registry
from roller.austin.sizing import all_bands, simulate_sleeve


def _months(frame: pd.DataFrame) -> list[str]:
    return sorted({str(x) for x in frame["calendar_month"].dropna().tolist() if str(x)})


def _entry_frame(snapshots: pd.DataFrame) -> pd.DataFrame:
    return snapshots[snapshots["kind"] == "entry"].copy()


def _meta_row(row: pd.Series) -> dict[str, Any]:
    return {
        "snapshot_id": row["snapshot_id"],
        "trade_id": row["trade_id"],
        "game_date": row["game_date"],
        "quarter": row.get("quarter"),
        "ticker": row.get("ticker"),
        "kind": row.get("kind"),
        "entry_price_cents": row.get("entry_price_cents"),
        "current_price_cents": row.get("current_price_cents"),
        "score_differential": row.get("score_differential"),
        "time_since_entry": row.get("time_since_entry"),
        "price_travel": row.get("price_travel"),
        "pnl_hold_after_t": row.get("pnl_hold_after_t", row.get("final_pnl_hold_cents")),
        "pnl_8040_after_t": row.get("pnl_8040_after_t"),
        "pnl_8040_after_t_status": row.get("pnl_8040_after_t_status"),
        "t40_already": bool(row.get("t40_already")),
        "final_pnl_taker_8040_cents": row.get("final_pnl_taker_8040_cents"),
        "final_pnl_hold_cents": row.get("final_pnl_hold_cents"),
        "csv_t40": bool(row.get("csv_t40")),
        "hit_40_after": bool(row.get("hit_40_after")),
        "settlement": row.get("settlement"),
        "won": bool(row.get("won")),
    }


def run_walkforward(snapshots: pd.DataFrame, *, cfg: AustinConfig = DEFAULT) -> dict[str, Any]:
    if snapshots.empty:
        raise AustinError("DATA_REQUIRED", "no snapshots for walk-forward")
    names = list(load_registry()["default_knn"])
    entries = _entry_frame(snapshots)
    months = _months(entries)
    if len(months) < 3:
        raise AustinError("INSUFFICIENT_SAMPLE", f"need >=3 months, got {months}")
    # TRAIN = earliest 50%, VAL = next 25%, OOS = last 25% of months (at least 1 each)
    n = len(months)
    i_train = max(1, n // 2)
    i_val = max(i_train + 1, i_train + max(1, n // 4))
    train_months = months[:i_train]
    val_months = months[i_train:i_val]
    oos_months = months[i_val:]
    if not oos_months:
        oos_months = [months[-1]]
        val_months = months[i_train:-1] or [months[i_train]]
        train_months = months[:i_train]

    folds = []
    oos_rows: list[dict[str, Any]] = []
    for label, test_months, prior in (
        ("validation", val_months, train_months),
        ("oos", oos_months, train_months + val_months),
    ):
        train = snapshots[snapshots["calendar_month"].isin(prior)].copy()
        test = entries[entries["calendar_month"].isin(test_months)].copy()
        if train.empty or test.empty:
            continue
        train_max = str(train["game_date"].max())
        test_min = str(test["game_date"].min())
        assert_train_before_eval(train_max, test_min) if train_max < test_min else None
        if train_max >= test_min:
            train = train[train["game_date"] < test_min]
            if train.empty:
                continue
            assert_train_before_eval(str(train["game_date"].max()), test_min)
        model = fit_pca(train, names, k=cfg.pca_k, cfg=cfg)
        vecs = model["scores"]
        meta = [_meta_row(train.loc[idx]) for idx in model["index"]]
        preds = []
        for rec in test.itertuples(index=False):
            numeric = {name: getattr(rec, name, None) for name in names}
            vec = transform_row(numeric, model)
            if vec is None:
                continue
            match = match_query(vec, vecs, meta, k=cfg.k_default, cfg=cfg, exclude_trade_id=str(rec.trade_id))
            actual = getattr(rec, "pnl_hold_after_t", None)
            if actual is None:
                actual = rec.final_pnl_taker_8040_cents
            row = {
                "trade_id": rec.trade_id,
                "game_date": rec.game_date,
                "calendar_month": rec.calendar_month,
                "actual_pnl": actual,
                "weighted_mean_EV": match.get("weighted_mean_EV"),
                "median_distance": match.get("median_distance"),
                "effective_neighbors": match.get("effective_neighbors"),
            }
            preds.append(row)
            if label == "oos":
                oos_rows.append(row)
        actuals = [p["actual_pnl"] for p in preds if p["actual_pnl"] is not None]
        evs = [p["weighted_mean_EV"] for p in preds if p["weighted_mean_EV"] is not None]
        folds.append(
            {
                "label": label,
                "train_months": prior,
                "test_months": list(test_months),
                "n_train_snapshots": int(len(train)),
                "n_test_trades": int(len(preds)),
                "mean_actual_pnl": None if not actuals else float(np.mean(actuals)),
                "mean_weighted_ev": None if not evs else float(np.mean(evs)),
            }
        )

    cal = _calibrate(oos_rows)
    sims = _simulate(entries, oos_rows, cal, cfg)
    path_oos = _snapshot_oos(snapshots, oos_months, train_months + val_months, cfg)
    return {
        "months": months,
        "train_months": train_months,
        "validation_months": val_months,
        "oos_months": oos_months,
        "train_n": int(entries[entries["calendar_month"].isin(train_months)].shape[0]),
        "validation_n": int(entries[entries["calendar_month"].isin(val_months)].shape[0]),
        "oos_n": int(entries[entries["calendar_month"].isin(oos_months)].shape[0]),
        "folds": folds,
        "calibration": cal,
        "bankroll": sims,
        "snapshot_oos": path_oos,
        "pca_k": cfg.pca_k,
        "k": cfg.k_default,
        "distance_metric": "euclidean_pca",
        "ev_definition": "hold_80_to_settlement",
    }


def _calibrate(oos_rows: list[dict[str, Any]]) -> dict[str, Any]:
    usable = [r for r in oos_rows if r.get("weighted_mean_EV") is not None and r.get("actual_pnl") is not None]
    if len(usable) < 20:
        return {
            "status": "INSUFFICIENT_SAMPLE",
            "reason": f"OOS n={len(usable)} < 20",
            "threshold_4": None,
            "threshold_5": None,
            "table": [],
        }
    ev = np.array([float(r["weighted_mean_EV"]) for r in usable], dtype=float)
    actual = np.array([float(r["actual_pnl"]) for r in usable], dtype=float)
    q20, q40, q60, q80 = np.quantile(ev, [0.2, 0.4, 0.6, 0.8])
    edges = [(-1e18, q20), (q20, q40), (q40, q60), (q60, q80), (q80, 1e18)]
    labels = ["D1-2", "D3-4", "D5-6", "D7-8", "D9-10"]
    table = []
    for (lo, hi), lab in zip(edges, labels):
        if hi >= 1e17:
            mask = ev >= lo
        elif lo <= -1e17:
            mask = ev <= hi
        else:
            mask = (ev >= lo) & (ev < hi)
        sub = actual[mask]
        n = int(sub.size)
        table.append(
            {
                "band": lab,
                "knn_ev_lo": None if lo <= -1e17 else float(lo),
                "knn_ev_hi": None if hi >= 1e17 else float(hi),
                "n": n,
                "realized_PNL": None if n == 0 else float(sub.mean()),
                "drawdown": None if n == 0 else float(min(0.0, float(sub.min()))),
                "recommended_band": 5 if lab == "D9-10" else (4 if lab == "D7-8" else 3),
            }
        )
    top = actual[ev >= q80]
    mid = actual[(ev >= q40) & (ev < q60)]
    bot = actual[ev <= q20]
    if top.size == 0 or mid.size == 0 or bot.size == 0:
        return {
            "status": "INSUFFICIENT_SAMPLE",
            "reason": "empty EV decile",
            "threshold_4": None,
            "threshold_5": None,
            "table": table,
        }
    top_m, mid_m, bot_m = float(top.mean()), float(mid.mean()), float(bot.mean())
    separated = top_m > mid_m + 1.0 and mid_m > bot_m
    if not separated:
        return {
            "status": "INSUFFICIENT_SAMPLE",
            "reason": f"OOS top/mid/bot EV {top_m:.3f}/{mid_m:.3f}/{bot_m:.3f} do not separate",
            "top_mean_pnl": top_m,
            "mid_mean_pnl": mid_m,
            "bot_mean_pnl": bot_m,
            "threshold_4": None,
            "threshold_5": None,
            "table": table,
        }
    return {
        "status": "SEPARATED",
        "reason": "OOS KNN EV deciles separate actual PnL",
        "top_mean_pnl": top_m,
        "mid_mean_pnl": mid_m,
        "bot_mean_pnl": bot_m,
        "threshold_4": float(q60),
        "threshold_5": float(q80),
        "table": table,
        "oos_n": int(len(usable)),
    }


def _simulate(
    entries: pd.DataFrame,
    oos_rows: list[dict[str, Any]],
    cal: dict[str, Any],
    cfg: AustinConfig,
) -> dict[str, Any]:
    by_id = {r["trade_id"]: r for r in oos_rows}
    oos = entries[entries["trade_id"].isin(by_id)].sort_values("game_date")
    def _actual(rec: dict[str, Any]) -> float:
        val = rec.get("pnl_hold_after_t")
        if val is None:
            val = rec.get("final_pnl_taker_8040_cents")
        return float(val)

    pnls = [_actual(r) for r in oos.to_dict("records")]
    bands = all_bands(cfg=cfg)
    out = {
        "3": simulate_sleeve(pnls, band_contracts(3), start_cents=cfg.starting_bankroll_cents),
        "4": simulate_sleeve(pnls, band_contracts(4), start_cents=cfg.starting_bankroll_cents),
        "5": simulate_sleeve(pnls, band_contracts(5), start_cents=cfg.starting_bankroll_cents),
    }
    dyn = []
    for rec in oos.to_dict("records"):
        pred = by_id[rec["trade_id"]]
        if cal.get("status") != "SEPARATED":
            pct = 3
        else:
            ev = pred.get("weighted_mean_EV")
            pct = 3
            if ev is not None and ev >= cal["threshold_5"]:
                pct = 5
            elif ev is not None and ev >= cal["threshold_4"]:
                pct = 4
        dyn.append(_actual(rec) * band_contracts(pct) / band_contracts(3))
    # simulate_sleeve multiplies by contracts; normalize dyn to 3% contracts so dollars are correct
    out["austin_dynamic"] = simulate_sleeve(dyn, band_contracts(3), start_cents=cfg.starting_bankroll_cents)
    out["bands"] = bands
    out["calibration_status"] = cal.get("status")
    return out


def compare_models(snapshots: pd.DataFrame, *, cfg: AustinConfig = DEFAULT) -> list[dict[str, Any]]:
    names = list(load_registry()["default_knn"])
    entries = _entry_frame(snapshots).sort_values("game_date")
    months = _months(entries)
    if len(months) < 3:
        return []
    prior = months[:-1]
    test_m = [months[-1]]
    train = snapshots[snapshots["calendar_month"].isin(prior)]
    test = entries[entries["calendar_month"].isin(test_m)]
    test = test[test["game_date"] > str(train["game_date"].max())] if not train.empty else test
    rows = []
    for k in cfg.pca_compare:
        try:
            model = fit_pca(train, names, k=k, cfg=cfg)
        except AustinError:
            continue
        vecs = model["scores"]
        meta = [_meta_row(train.loc[idx]) for idx in model["index"]]
        evs = []
        acts = []
        for rec in test.itertuples(index=False):
            vec = transform_row({n: getattr(rec, n, None) for n in names}, model)
            if vec is None:
                continue
            match = match_query(vec, vecs, meta, cfg=cfg, exclude_trade_id=str(rec.trade_id))
            if match.get("weighted_mean_EV") is None:
                continue
            evs.append(float(match["weighted_mean_EV"]))
            acts.append(float(rec.final_pnl_taker_8040_cents))
        rows.append(
            {
                "model": f"pca_{k}",
                "n": len(acts),
                "mean_weighted_ev": None if not evs else float(np.mean(evs)),
                "mean_actual_pnl": None if not acts else float(np.mean(acts)),
            }
        )
    return rows


def _snapshot_oos(
    snapshots: pd.DataFrame,
    oos_months: list[str],
    prior: list[str],
    cfg: AustinConfig,
) -> dict[str, Any]:
    """Paper-query at mid-path OOS states. Does not replace entry walk-forward."""
    names = list(load_registry()["default_knn"])
    train = snapshots[snapshots["calendar_month"].isin(prior)].copy()
    test = snapshots[snapshots["calendar_month"].isin(oos_months)].copy()
    if train.empty or test.empty:
        return {"n": 0, "note": "no snapshot OOS rows"}
    test_min = str(test["game_date"].min())
    train = train[train["game_date"] < test_min]
    if train.empty:
        return {"n": 0, "note": "no prior snapshots"}
    model = fit_pca(train, names, k=cfg.pca_k, cfg=cfg)
    vecs = model["scores"]
    meta = [_meta_row(train.loc[idx]) for idx in model["index"]]
    rows = []
    for rec in test.itertuples(index=False):
        numeric = {name: getattr(rec, name, None) for name in names}
        vec = transform_row(numeric, model)
        if vec is None:
            continue
        match = match_query(
            vec,
            vecs,
            meta,
            k=cfg.k_default,
            cfg=cfg,
            exclude_trade_id=str(rec.trade_id),
            exclude_snapshot_id=str(rec.snapshot_id),
        )
        actual = getattr(rec, "pnl_hold_after_t", None)
        if actual is None:
            actual = getattr(rec, "final_pnl_hold_cents", None)
        rows.append(
            {
                "trade_id": rec.trade_id,
                "snapshot_id": rec.snapshot_id,
                "kind": rec.kind,
                "current_price_cents": getattr(rec, "current_price_cents", None),
                "predicted_ev": match.get("weighted_mean_EV"),
                "actual_pnl_hold_after_t": None if actual is None else float(actual),
            }
        )
    usable = [r for r in rows if r["predicted_ev"] is not None and r["actual_pnl_hold_after_t"] is not None]
    err = None
    if usable:
        err = float(
            np.mean(
                [
                    abs(float(r["predicted_ev"]) - float(r["actual_pnl_hold_after_t"]))
                    for r in usable
                ]
            )
        )
    return {
        "n": len(usable),
        "n_evaluated": len(rows),
        "mean_abs_error_cents": err,
        "note": "Snapshot-level OOS paper query. Neighbors restricted to earlier dates. After-t hold PNL.",
    }
