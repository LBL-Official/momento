"""Chronological walk-forward on the 78/67 feature names."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from roller.austin.config import band_contracts
from roller.austin.errors import AustinError
from roller.austin.knn import match_query
from roller.austin.leakage import assert_train_before_eval
from roller.austin.pca import fit_pca, transform_row
from roller.austin.sizing import all_bands, simulate_sleeve
from roller.austin.walkforward import _calibrate
from roller.austin_first78.config import CFG, EV_DEFINITION


def _months(frame: pd.DataFrame) -> list[str]:
    return sorted({str(x) for x in frame["calendar_month"].dropna().tolist() if str(x)})


def _meta(row: pd.Series) -> dict[str, Any]:
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
        "pnl_hold_after_t": row.get("pnl_hold_after_t"),
        "pnl_8040_after_t": row.get("pnl_7867_after_t", row.get("pnl_8040_after_t")),
        "pnl_8040_after_t_status": row.get("pnl_7867_after_t_status", row.get("pnl_8040_after_t_status")),
        "t40_already": bool(row.get("t67_already", row.get("t40_already"))),
        "final_pnl_taker_8040_cents": row.get("final_pnl_taker_7867_cents", row.get("final_pnl_taker_8040_cents")),
        "final_pnl_hold_cents": row.get("final_pnl_hold_cents"),
        "csv_t40": bool(row.get("t67", row.get("csv_t40"))),
        "hit_40_after": bool(row.get("hit_67_after", row.get("hit_40_after"))),
        "settlement": row.get("settlement"),
        "won": bool(row.get("won")),
    }


def _actual(row: Any) -> float | None:
    val = getattr(row, "pnl_hold_after_t", None)
    if val is None or pd.isna(val):
        return None
    return float(val)


def run_walkforward(snapshots: pd.DataFrame) -> dict[str, Any]:
    if snapshots.empty:
        raise AustinError("DATA_REQUIRED", "no snapshots for walk-forward")
    names = list(CFG.default_knn)
    entries = snapshots[snapshots["kind"] == "entry"].copy()
    months = _months(entries)
    if len(months) < 3:
        raise AustinError("INSUFFICIENT_SAMPLE", f"need >=3 months, got {months}")
    n = len(months)
    i_train = max(1, n // 2)
    i_val = max(i_train + 1, i_train + max(1, n // 4))
    train_months = months[:i_train]
    val_months = months[i_train:i_val]
    oos_months = months[i_val:] or [months[-1]]
    if not months[i_val:]:
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
        test_min = str(test["game_date"].min())
        train = train[train["game_date"] < test_min]
        if train.empty:
            continue
        assert_train_before_eval(str(train["game_date"].max()), test_min)
        model = fit_pca(train, names, k=CFG.pca_k, cfg=CFG)
        meta = [_meta(train.loc[idx]) for idx in model["index"]]
        preds = []
        for rec in test.itertuples(index=False):
            vec = transform_row({name: getattr(rec, name, None) for name in names}, model)
            if vec is None:
                continue
            match = match_query(vec, model["scores"], meta, k=CFG.k_default, cfg=CFG, exclude_trade_id=str(rec.trade_id))
            actual = _actual(rec)
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
    sims = _simulate(entries, oos_rows, cal)
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
        "snapshot_oos": {"n": 0, "note": "Entry walk-forward is the validation record."},
        "pca_k": CFG.pca_k,
        "k": CFG.k_default,
        "distance_metric": "euclidean_pca",
        "ev_definition": EV_DEFINITION,
        "feature_names": names,
    }


def _simulate(entries: pd.DataFrame, oos_rows: list[dict[str, Any]], cal: dict[str, Any]) -> dict[str, Any]:
    by_id = {r["trade_id"]: r for r in oos_rows}
    oos = entries[entries["trade_id"].isin(by_id)].sort_values("game_date")
    pnls = []
    for rec in oos.to_dict("records"):
        val = rec.get("pnl_hold_after_t")
        if val is None:
            continue
        pnls.append(float(val))
    out = {
        str(pct): simulate_sleeve(pnls, band_contracts(pct, entry_cents=CFG.entry_cents), start_cents=CFG.starting_bankroll_cents)
        for pct in (3, 4, 5)
    }
    out["bands"] = all_bands(cfg=CFG)
    out["calibration_status"] = cal.get("status")
    out["role"] = "ENTRY_SIZING_REFERENCE"
    return out
