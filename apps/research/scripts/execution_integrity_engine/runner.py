"""EIE + DRE_BASELINE_V1 runner. Additive. Does not overwrite A1."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from . import A1_CONFIG_HASH, DRE_BASELINE, LIVE_EXECUTION_CHANGED, PROGRAM, UNIVERSE_VERSION
from .classify import classify_l2
from .enums import E0, E1, E2, E_HOLD, E_STOP, E_THEO, L1, L3, L4, NOT_AVAILABLE
from .expectancy import concentration, decompose, describe
from .invariants import check
from .models import e0_observation_only, e1_conservative, e2_scenario, e3_empirical, e4_l2_queue, e_theoretical_threshold
from .payoff import payoff_class

A1_SCRIPTS = Path("/Users/user/Desktop/Momento/apps/ncaab-data/scripts")
sys.path.insert(0, str(A1_SCRIPTS))
from a1_hybrid_hedge.universe import (  # noqa: E402
    BASELINE,
    config_hash,
    load_ledger,
    load_opportunity,
    reproduce_baseline,
)

DOCS = Path("/Users/user/Desktop/Momento/docs/research/EXECUTION_INTEGRITY_ENGINE")
FRONT = Path("/Users/user/Desktop/Momento/frontend/execution-integrity/public/data")
H_BASE = 40
BAND_LO = 40
BAND_HI = 40
ENTRY = 80.0
EXPECTED_N = {"nba": 1230, "ncaab": 721}
E2_Q = (0.25, 0.50, 0.75, 1.00)
E2_PARTIAL = (0.25, 0.50, 0.75, 1.00)


def git_rev() -> str:
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd="/Users/user/Desktop/Momento",
                stderr=subprocess.DEVNULL,
            )
            .decode()
            .strip()
        )
    except Exception:
        return "UNKNOWN"


def _sha(obj) -> str:
    raw = json.dumps(obj, sort_keys=True, default=str).encode()
    return hashlib.sha256(raw).hexdigest()[:16]


def _join(led: pd.DataFrame, opp: pd.DataFrame, h: int) -> pd.DataFrame:
    cols = [
        c
        for c in (
            "game_id",
            "favorite_market",
            "opponent_market",
            "entry_time",
            "opportunity_close",
            "opportunity_high",
            "opportunity_quality_class",
            "touch_candle_close_cents",
            "touch_candle_high_cents",
            "touch_candle_low_cents",
            "persist_subsequent_min",
            "jump_10c",
            "first_touch_ts",
            "time_until_touch_s",
            "favorite_price_at_touch_cents",
            "overshoot_close_cents",
        )
        if c in opp.columns
    ]
    sub = opp.loc[opp["H"] == h, cols].drop_duplicates(["game_id", "favorite_market"])
    return led.merge(
        sub,
        left_on=["event_id", "ticker"],
        right_on=["game_id", "favorite_market"],
        how="left",
    )


def _truthy(x) -> bool:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return False
    return bool(x)


def build_sport(sport: str) -> dict:
    led = load_ledger(sport)
    opp = load_opportunity(sport)
    if sport == "ncaab":
        keep = set(led["event_id"])
        opp = opp[opp["game_id"].isin(keep)].copy()
    repro = reproduce_baseline(led, sport)
    j = _join(led, opp, H_BASE)
    trades = []
    opp_rows = []
    for r in j.itertuples(index=False):
        oc = _truthy(getattr(r, "opportunity_close", False))
        oh = _truthy(getattr(r, "opportunity_high", False))
        jmp = _truthy(getattr(r, "jump_10c", False))
        obs = getattr(r, "touch_candle_close_cents", None)
        l2 = classify_l2(oc, oh, obs, jmp, H_BASE, BAND_LO, BAND_HI)
        hold = float(r.pnl_hold)
        stop = float(r.pnl_stop_80_40)
        v1 = float(r.pnl_replace_h40)
        e0 = e0_observation_only()
        e1 = e1_conservative(l2, stop, ENTRY)
        et = e_theoretical_threshold(l2, hold, H_BASE, ENTRY)
        # Prefer V4 V1 identity when close≥H (same algebra). Keep both.
        e2s = {}
        for q in E2_Q:
            for f in E2_PARTIAL:
                e2s[f"q{q}_p{f}"] = e2_scenario(l2, stop, q, f, ENTRY)
        won = bool(r.won)
        stopped = bool(r.stop_close_triggered)
        cls = payoff_class(won, stopped, l2, e1)
        trade_id = f"{sport}:{r.event_id}:{r.ticker}"
        entry_ts = getattr(r, "entry_time", None)
        rec = {
            "trade_id": trade_id,
            "strategy_id": "FIRST80_HYBRID_DRE_BASELINE",
            "universe_version": UNIVERSE_VERSION,
            "a1_config_hash": A1_CONFIG_HASH,
            "sport": sport,
            "event_id": r.event_id,
            "ticker": r.ticker,
            "a2_market": getattr(r, "opponent_market", None),
            "game_date": str(r.game_date),
            "dataset_split": r.dataset_split,
            "entry_ts": None if pd.isna(entry_ts) else entry_ts,
            "entry_price_assumed": ENTRY,
            "entry_price_observed": NOT_AVAILABLE,
            "entry_evidence_level": L1,
            "threshold": H_BASE,
            "band_lo": BAND_LO,
            "band_hi": BAND_HI,
            "strict_next_bar": True,
            "won": won,
            "stop_triggered": stopped,
            "opportunity_class": l2["opportunity_class"],
            "market_occupancy_status": l2["market_occupancy_status"],
            "threshold_crossing": l2["threshold_crossing"],
            "gap_through": l2["gap_through"],
            "observed_a2_close": l2.get("observed_price"),
            "observed_a2_high": getattr(r, "touch_candle_high_cents", None),
            "a1_at_touch": getattr(r, "favorite_price_at_touch_cents", None),
            "hedge_signal_ts": getattr(r, "first_touch_ts", None),
            "time_until_touch_s": getattr(r, "time_until_touch_s", None),
            "v3_class": getattr(r, "opportunity_quality_class", None),
            "persist_subsequent_min": getattr(r, "persist_subsequent_min", None),
            "evidence_level_l1": L1,
            "evidence_level_l2": l2["evidence_level"],
            "evidence_level_l4_claimed": None,
            "pnl_hold": hold,
            "pnl_stop_80_40": stop,
            "pnl_v1_theoretical": v1,
            "pnl_e0": None,
            "pnl_e1": e1["pnl"],
            "pnl_e_theo": et["pnl"],
            "pnl_actual_execution": None,
            "execution_model_e0": E0,
            "execution_model_e1": e1["execution_model_id"],
            "execution_model_e_theo": E_THEO,
            "e1_hedge_filled": e1["hedge_filled"],
            "e1_hedge_price": e1.get("hedge_price"),
            "e1_observed_in_band": l2["opportunity_class"]
            in ("EXACT_OBSERVATION", "BAND_OBSERVATION"),
            "e1_fill_claim": e1["fill_claim"],
            "fallback_triggered": e1.get("fallback_triggered"),
            "fallback_reason": e1.get("fallback_reason"),
            "path_class": cls,
            "final_payoff_class": cls,
            "fill_claim_l4": NOT_AVAILABLE,
            "live_execution_changed": LIVE_EXECUTION_CHANGED,
        }
        for k, ev in e2s.items():
            rec[f"pnl_e2_{k}"] = ev["pnl"]
        trades.append(rec)
        opp_rows.append(
            {
                "opportunity_id": f"{trade_id}:H{H_BASE}",
                "trade_id": trade_id,
                "sport": sport,
                "event_id": r.event_id,
                "ticker": r.ticker,
                "threshold": H_BASE,
                "band_lo": BAND_LO,
                "band_hi": BAND_HI,
                "previous_observed_price": NOT_AVAILABLE,
                "current_observed_price": l2.get("observed_price"),
                **{k: l2[k] for k in l2 if k != "observed_price"},
                "strict_next_bar": True,
                "source_artifact": "V3_opportunity_dataset",
            }
        )

    inv = check(trades, sport, EXPECTED_N[sport])
    df = pd.DataFrame(trades)
    dates = df.game_date.astype(str)

    def pack(col, model):
        d = describe(df[col])
        d["execution_model_id"] = model
        d["evidence"] = "MODELED" if model.startswith("E") or model.startswith("E_") else "OBSERVED_RESOLUTION"
        if model == E_HOLD:
            d["evidence"] = "L1_SETTLEMENT_ONLY"
        if model == E_STOP:
            d["evidence"] = "L3_FALLBACK_MODEL_A"
        if model == E_THEO:
            d["evidence"] = "ILLEGAL_PROMOTION_BENCHMARK"
        if col == "pnl_e1":
            d["evidence"] = "L3_E1_MODELED"
        return d

    ev = {
        "EV_L1_hold": pack("pnl_hold", E_HOLD),
        "EV_L3_E0": {**e0_observation_only(), "pnl": None, "note": "E0 has no P&L."},
        "EV_L3_E1": pack("pnl_e1", E1),
        "EV_L3_E_THEO": pack("pnl_e_theo", E_THEO),
        "EV_80_40": pack("pnl_stop_80_40", E_STOP),
        "EV_V4_V1": pack("pnl_v1_theoretical", E_THEO),
        "EV_L4": {"status": NOT_AVAILABLE, "evidence": "ACTUAL", "n": 0},
        "EV_L3_E3": e3_empirical(),
        "EV_L3_E4": e4_l2_queue(),
    }
    e2_ev = {}
    for q in E2_Q:
        col = f"pnl_e2_q{q}_p1.0"
        e2_ev[f"q={q},partial=1"] = pack(col, E2)
    decomp = decompose(df.pnl_e1, df.path_class)
    inv.append({"id": "INV4_DECOMP_RECONCILES", "ok": decomp["identity_ok"], "detail": decomp})

    # splits
    by_split = {}
    for split, g in df.groupby("dataset_split"):
        by_split[str(split)] = {
            "n": int(len(g)),
            "e1": describe(g.pnl_e1),
            "stop": describe(g.pnl_stop_80_40),
            "hold": describe(g.pnl_hold),
            "theo": describe(g.pnl_e_theo),
        }
        if len(g) < 40:
            by_split[str(split)]["sample_flag"] = "INSUFFICIENT_SAMPLE"

    # opportunity counts
    counts = df.opportunity_class.value_counts().to_dict()
    occ = df.market_occupancy_status.value_counts().to_dict()

    # waterfall identity: hold + (stop-hold) + (e1-stop) = e1
    w_hold = float(df.pnl_hold.mean())
    w_stop = float(df.pnl_stop_80_40.mean())
    w_e1 = float(df.pnl_e1.mean())
    w_theo = float(df.pnl_e_theo.mean())
    waterfall = {
        "hold": round(w_hold, 6),
        "plus_stop_protection": round(w_stop - w_hold, 6),
        "equals_80_40": round(w_stop, 6),
        "plus_e1_hedge_vs_stop": round(w_e1 - w_stop, 6),
        "equals_e1": round(w_e1, 6),
        "theo_minus_e1_gap_fiction": round(w_theo - w_e1, 6),
        "identity_hold_stop_e1": abs((w_hold + (w_stop - w_hold) + (w_e1 - w_stop)) - w_e1)
        < 1e-8,
    }

    # concentration
    conc = concentration(df.pnl_e1)

    # counterfactual means
    cf = {
        "hold": w_hold,
        "stop_80_40": w_stop,
        "hybrid_e1": w_e1,
        "theoretical_threshold": w_theo,
        "actual": NOT_AVAILABLE,
    }

    return {
        "sport": sport,
        "n": int(len(df)),
        "reproduction": repro,
        "invariants": inv,
        "expectancy": ev,
        "e2": e2_ev,
        "decomposition": decomp,
        "by_split": by_split,
        "opportunity_counts": {str(k): int(v) for k, v in counts.items()},
        "occupancy_counts": {str(k): int(v) for k, v in occ.items()},
        "waterfall": waterfall,
        "concentration": conc,
        "counterfactual": cf,
        "date_min": str(df.game_date.min()),
        "date_max": str(df.game_date.max()),
        "split_n": {str(k): int(v) for k, v in df.dataset_split.value_counts().items()},
        "trades": trades,
        "opportunities": opp_rows,
        "df": df,
    }


def run_all() -> dict:
    meta = {
        "program": PROGRAM,
        "dre_baseline": DRE_BASELINE,
        "universe_version": UNIVERSE_VERSION,
        "a1_config_hash": A1_CONFIG_HASH,
        "code_version": git_rev(),
        "run_ts": datetime.now(timezone.utc).isoformat(),
        "live_execution_changed": LIVE_EXECUTION_CHANGED,
        "threshold": H_BASE,
        "band": [BAND_LO, BAND_HI],
        "timing": "STRICT_NEXT_BAR via V3",
        "ncaab": "P5_VS_P5",
        "fees": "GROSS_UNRESOLVED",
        "l4": NOT_AVAILABLE,
    }
    meta["config_hash"] = config_hash(meta)
    sports = {}
    all_trades = []
    all_opp = []
    for sport in ("nba", "ncaab"):
        print(f"EIE {sport}", flush=True)
        sports[sport] = build_sport(sport)
        all_trades.extend(sports[sport]["trades"])
        all_opp.extend(sports[sport]["opportunities"])

    DOCS.mkdir(parents=True, exist_ok=True)
    FRONT.mkdir(parents=True, exist_ok=True)
    audit = pd.DataFrame(all_trades)
    opp = pd.DataFrame(all_opp)
    # drop helper
    for s in sports.values():
        s.pop("df", None)
        s.pop("trades", None)
        s.pop("opportunities", None)

    audit.to_parquet(DOCS / "trade_level_audit.parquet", index=False)
    opp.to_parquet(DOCS / "opportunity_audit.parquet", index=False)
    pd.DataFrame(
        [
            {
                "evidence_level": L4,
                "status": NOT_AVAILABLE,
                "n": 0,
                "note": "No live Momento fill tape in warehouse. Do not label candles as L4.",
            }
        ]
    ).to_parquet(DOCS / "execution_model_audit.parquet", index=False)

    # slim dashboard
    dash = {
        "banner": "EIE + DRE_BASELINE_V1 — RESEARCH ONLY — LIVE_EXECUTION_CHANGED=FALSE — L1≠L2≠L3≠L4 — NCAAB=P5 — NO A1 OVERWRITE",
        "meta": meta,
        "sports": sports,
        "pyramid": {
            "L1": "Raw / frozen observed snapshot (V3+V4). Immutable.",
            "L2": "Opportunity + occupancy. Crossing ≠ occupancy.",
            "L3": "E0 none · E1 conservative · E2 scenario · E3/E4 NOT_AVAILABLE",
            "L4": NOT_AVAILABLE,
        },
        "audit_preview": audit.sample(min(60, len(audit)), random_state=3).to_dict("records"),
        "audit_rows": int(len(audit)),
    }
    payload = _sanitize(dash)
    (DOCS / "dashboard.json").write_text(json.dumps(payload, allow_nan=False, default=_js))
    (FRONT / "dashboard.json").write_text(json.dumps(payload, allow_nan=False, default=_js))
    (DOCS / "manifest.json").write_text(json.dumps(meta, indent=2, default=str))
    return {"docs": str(DOCS), "dash": payload, "sports": sports, "audit": audit}


def _js(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating, float)):
        v = float(o)
        if np.isnan(v) or np.isinf(v):
            return None
        return v
    if isinstance(o, np.ndarray):
        return o.tolist()
    return str(o)


def _sanitize(obj):
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    if isinstance(obj, float) and (np.isnan(obj) or np.isinf(obj)):
        return None
    return obj
