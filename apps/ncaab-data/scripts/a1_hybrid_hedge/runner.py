"""A1 experiment families A–G. Research only.

LIVE EXECUTION CHANGED: FALSE.
Does not overwrite V1–V5 warehouse artifacts.
Does not modify FIRST01 / Risk / Execution.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

from . import DATASET_VERSION, PROGRAM, UNIVERSE_VERSION
from .execution import NAMED_BANDS, SURFACE_BANDS, band_for, classify_opportunity
from .metrics import (
    block_bootstrap_mean,
    bootstrap_mean,
    pareto_front,
    plateau,
    summarize,
)
from .pnl import CostModel, fallback_pnl, hybrid_pnl
from .universe import BASELINE, config_hash, load_ledger, load_opportunity, reproduce_baseline

HERE = Path(__file__).resolve().parent
DOCS = Path("/Users/user/Desktop/Momento/docs/research/A1_HYBRID_HEDGE")
FRONT_DATA = Path("/Users/user/Desktop/Momento/frontend/a1-hybrid-hedge/public/data")
H_ALL = list(range(10, 61))
ENTRY = 80.0
AUDIT_HS = (20, 28, 30, 37, 38, 40, 42)
KEY_SPLIT = ("FULL", "TRAIN", "VALIDATION", "OOS")


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


def _costs() -> CostModel:
    return CostModel()


def _split_mask(led: pd.DataFrame, split: str) -> pd.Series:
    if split == "FULL":
        return pd.Series(True, index=led.index)
    return led["dataset_split"] == split


def _opp_at_h(opp: pd.DataFrame, h: int) -> pd.DataFrame:
    cols = [
        "game_id",
        "favorite_market",
        "opponent_market",
        "entry_time",
        "opportunity_close",
        "opportunity_high",
        "opportunity_quality_class",
        "touch_candle_close_cents",
        "touch_candle_high_cents",
        "persist_subsequent_min",
        "jump_10c",
        "first_touch_ts",
        "time_until_touch_s",
        "overshoot_close_cents",
        "favorite_price_at_touch_cents",
        "first80_favorite40",
    ]
    sub = opp.loc[opp["H"] == h, [c for c in cols if c in opp.columns]].copy()
    return sub.drop_duplicates(["game_id", "favorite_market"])


def _join(led: pd.DataFrame, opp: pd.DataFrame, h: int) -> pd.DataFrame:
    sub = _opp_at_h(opp, h)
    m = led.merge(
        sub,
        left_on=["event_id", "ticker"],
        right_on=["game_id", "favorite_market"],
        how="left",
    )
    return m


def _fallback_series(df: pd.DataFrame, model: str, costs: CostModel) -> np.ndarray:
    return np.array([fallback_pnl(r, model, costs) for r in df.to_dict("records")])


def _book_vectors(
    df: pd.DataFrame,
    band,
    persist_k: int,
    fallback_name: str,
    costs: CostModel,
) -> dict:
    fb = _fallback_series(df, fallback_name, costs)
    hold = df["pnl_hold"].to_numpy(float)
    stop = df["pnl_stop_80_40"].to_numpy(float)
    v1 = df["pnl_replace_h40"].to_numpy(float)
    n = len(df)
    theo = np.empty(n)
    causal = np.empty(n)
    look = np.empty(n)
    obs_px = np.full(n, np.nan)
    tier = []
    gap = np.zeros(n, dtype=bool)
    in_band = np.zeros(n, dtype=bool)
    close_hit = np.zeros(n, dtype=bool)
    theo_replace = np.empty(n)
    for i, r in enumerate(df.itertuples(index=False)):
        oc = getattr(r, "opportunity_close", False)
        if oc is None or (isinstance(oc, float) and np.isnan(oc)):
            oc = False
        else:
            oc = bool(oc)
        jmp = getattr(r, "jump_10c", False)
        if jmp is None or (isinstance(jmp, float) and np.isnan(jmp)):
            jmp = False
        else:
            jmp = bool(jmp)
        close_hit[i] = oc
        cls = classify_opportunity(
            oc,
            getattr(r, "touch_candle_close_cents", None),
            getattr(r, "persist_subsequent_min", None),
            jmp,
            band,
            persist_k,
        )
        tier.append(cls["tier"])
        gap[i] = cls["gap"]
        in_band[i] = cls["in_band"]
        px = cls["obs_px"]
        if px is not None:
            obs_px[i] = px
        locked_h = hybrid_pnl(fb[i], ENTRY, float(band.target_h), 1.0, 1.0, costs)
        # REPLACE: miss → hold. HYBRID theoretical: miss → fallback. Both fill @ H on any close≥H.
        theo[i] = locked_h if oc else fb[i]
        theo_replace[i] = locked_h if oc else hold[i]
        if cls["in_band"]:
            causal[i] = hybrid_pnl(fb[i], ENTRY, px, 1.0, 1.0, costs)
            look[i] = (
                hybrid_pnl(fb[i], ENTRY, px, 1.0, 1.0, costs)
                if cls["lookahead_t1"]
                else fb[i]
            )
        else:
            causal[i] = fb[i]
            look[i] = fb[i]
    return {
        "hold": hold,
        "stop": stop,
        "v1": v1,
        "theo": theo,
        "theo_replace": theo_replace,
        "causal": causal,
        "lookahead": look,
        "fallback": fb,
        "obs_px": obs_px,
        "tier": tier,
        "gap": gap,
        "in_band": in_band,
        "close_hit": close_hit,
    }


def _metrics_pack(vec, dates, stop) -> dict:
    s = summarize(vec, dates, baseline=stop)
    s["bootstrap_iid"] = bootstrap_mean(vec)
    s["bootstrap_block"] = block_bootstrap_mean(vec, dates)
    return s


def _surface_row(h, band_name, persist_k, fallback_name, split, vec, dates) -> dict:
    stop = vec["stop"]
    causal = vec["causal"]
    n = len(causal)
    filled = int(vec["in_band"].sum())
    gaps = int(vec["gap"].sum())
    hits = int(vec["close_hit"].sum())
    px = vec["obs_px"][vec["in_band"]]
    m = {
        "H": h,
        "band": band_name,
        "persist_k": persist_k,
        "fallback": fallback_name,
        "split": split,
        "n": n,
        "close_hits": hits,
        "in_band": filled,
        "gaps": gaps,
        "modeled_fill_rate_causal": round(filled / n, 6) if n else None,
        "jump_through_rate": round(gaps / n, 6) if n else None,
        "avg_obs_hedge": round(float(np.nanmean(px)), 4) if filled else None,
        "median_obs_hedge": round(float(np.nanmedian(px)), 4) if filled else None,
        "original": summarize(stop, dates),
        "hold": summarize(vec["hold"], dates),
        "theoretical_hybrid": summarize(vec["theo"], dates, stop),
        "theoretical_replace": summarize(vec["theo_replace"], dates, stop),
        "conservative_causal": summarize(causal, dates, stop),
        "lookahead_persist": summarize(vec["lookahead"], dates, stop),
        "theoretical_label": "THEORETICAL / NON-EXECUTION-AUDITED — fill @ H on any close≥H",
        "causal_label": "IN-BAND OBSERVED CLOSE — NOT CONFIRMED FILL",
        "lookahead_label": "LOOKAHEAD persist after first ≥lo close",
    }
    return m


def load_sport(sport: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    led = load_ledger(sport)
    opp = load_opportunity(sport)
    if sport == "ncaab":
        keep = set(led["event_id"])
        opp = opp[opp["game_id"].isin(keep)].copy()
    return led, opp


def run_all() -> dict:
    costs = _costs()
    code = git_rev()
    cfg = {
        "program": PROGRAM,
        "universe_version": UNIVERSE_VERSION,
        "dataset_version": DATASET_VERSION,
        "code_version": code,
        "timing": "STRICT_NEXT_BAR (V3 t > first_80_timestamp)",
        "ncaab": "P5_VS_P5",
        "fees": costs.label,
        "live_execution_changed": False,
    }
    cfg["config_hash"] = config_hash(cfg)

    sports = {}
    audit_rows = []
    for sport in ("nba", "ncaab"):
        print(f"A1 load {sport}", flush=True)
        led, opp = load_sport(sport)
        dates_full = led["game_date"].astype(str).to_numpy()
        repro = reproduce_baseline(led, sport)
        splits = {s: led.loc[_split_mask(led, s)].copy() for s in KEY_SPLIT}
        split_n = {s: int(len(d)) for s, d in splits.items()}

        # Experiment A
        exp_a = {
            "reproduction": repro,
            "hold": summarize(led.pnl_hold, dates_full),
            "stop_80_40": summarize(led.pnl_stop_80_40, dates_full),
            "v1_threshold_h40": summarize(led.pnl_replace_h40, dates_full),
            "by_split": {},
        }
        for s, d in splits.items():
            exp_a["by_split"][s] = {
                "n": int(len(d)),
                "hold": summarize(d.pnl_hold, d.game_date.astype(str)),
                "stop": summarize(d.pnl_stop_80_40, d.game_date.astype(str)),
                "v1": summarize(d.pnl_replace_h40, d.game_date.astype(str)),
            }

        surface = []
        named = []
        fallback_sens = []
        prob = []
        partial = []
        gaps = []

        headline_fb = "legacy_80_40"
        persist_k = 3

        print(f"  surface {sport}", flush=True)
        for h in H_ALL:
            for bname in SURFACE_BANDS:
                band = band_for(bname, h)
                use_h = band.lo
                j = _join(led, opp, use_h)
                for split in KEY_SPLIT:
                    df = j.loc[_split_mask(j, split)]
                    vec = _book_vectors(df, band, persist_k, headline_fb, costs)
                    surface.append(
                        _surface_row(
                            h, bname, persist_k, headline_fb, split, vec, df.game_date.astype(str)
                        )
                    )

        print(f"  named bands {sport}", flush=True)
        for bname in NAMED_BANDS:
            band = band_for(bname, 40)
            j = _join(led, opp, band.lo)
            for split in KEY_SPLIT:
                df = j.loc[_split_mask(j, split)]
                for k in (1, 2, 3, 5):
                    vec = _book_vectors(df, band, k, headline_fb, costs)
                    named.append(
                        _surface_row(
                            band.target_h, bname, k, headline_fb, split, vec, df.game_date.astype(str)
                        )
                    )

        print(f"  fallback / q / partial {sport}", flush=True)
        for bname, h in (("exact", 40), ("band_37_42", 40), ("exact", 20), ("exact", 30)):
            band = band_for(bname, h)
            j = _join(led, opp, band.lo)
            for split in KEY_SPLIT:
                df = j.loc[_split_mask(j, split)]
                dates = df.game_date.astype(str)
                for fb_name in (
                    "legacy_80_40",
                    "realistic_band_exit",
                    "conservative_next_observation",
                    "settlement_only",
                ):
                    vec = _book_vectors(df, band, persist_k, fb_name, costs)
                    fallback_sens.append(
                        {
                            **_surface_row(h, bname, persist_k, fb_name, split, vec, dates),
                        }
                    )
                vec = _book_vectors(df, band, persist_k, headline_fb, costs)
                for q in (0.0, 0.25, 0.5, 0.75, 1.0):
                    ev = np.where(
                        vec["in_band"],
                        q * vec["causal"] + (1 - q) * vec["fallback"],
                        vec["fallback"],
                    )
                    # in_band causal already IS hedge pnl; rebuild from lock
                    # Use hybrid with q on in-band trades only.
                    mixed = vec["fallback"].copy()
                    mixed[vec["in_band"]] = (
                        q * vec["causal"][vec["in_band"]]
                        + (1 - q) * vec["fallback"][vec["in_band"]]
                    )
                    pack = (
                        _metrics_pack(mixed, dates, vec["stop"])
                        if split == "FULL" and h == 40 and bname == "exact"
                        else summarize(mixed, dates, vec["stop"])
                    )
                    prob.append(
                        {
                            "H": h,
                            "band": bname,
                            "split": split,
                            "q": q,
                            "label": "SCENARIO fill probability on in-band closes. Not observed.",
                            **pack,
                        }
                    )
                for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
                    mixed = vec["fallback"].copy()
                    mixed[vec["in_band"]] = (
                        frac * vec["causal"][vec["in_band"]]
                        + (1 - frac) * vec["fallback"][vec["in_band"]]
                    )
                    pack = (
                        _metrics_pack(mixed, dates, vec["stop"])
                        if split == "FULL" and h == 40 and bname == "exact"
                        else summarize(mixed, dates, vec["stop"])
                    )
                    partial.append(
                        {
                            "H": h,
                            "band": bname,
                            "split": split,
                            "partial": frac,
                            "label": "SCENARIO hedge completion. Depth UNOBSERVED.",
                            **pack,
                        }
                    )

        # Experiment F — gap isolation at H=40 exact
        band40 = band_for("exact", 40)
        j40 = _join(led, opp, 40)
        vec40 = _book_vectors(j40, band40, persist_k, headline_fb, costs)
        fictional_on_gap = vec40["fallback"].copy()
        # Fictional: book H=40 even on gap (subset of theoretical)
        fictional_on_gap[vec40["gap"]] = hybrid_pnl(
            0, ENTRY, 40.0, 1.0, 1.0, costs
        )
        # Wait, fallback unused. Use lock -20 on gap.
        fictional = vec40["theo"]
        realistic_miss = vec40["causal"]  # gaps already fallback
        gaps.append(
            {
                "H": 40,
                "band": "exact",
                "n_gap": int(vec40["gap"].sum()),
                "n_in_band": int(vec40["in_band"].sum()),
                "n_no_touch": int((~vec40["close_hit"]).sum()),
                "fictional_threshold_ev": summarize(fictional, dates_full, vec40["stop"]),
                "realistic_miss_ev": summarize(realistic_miss, dates_full, vec40["stop"]),
                "delta_fiction_minus_real": round(
                    float(fictional.mean() - realistic_miss.mean()), 6
                ),
                "note": "23→75 is a gap. Threshold fill @40 is fictional.",
            }
        )
        # per-split gap
        for split in KEY_SPLIT:
            df = j40.loc[_split_mask(j40, split)]
            v = _book_vectors(df, band40, persist_k, headline_fb, costs)
            gaps.append(
                {
                    "H": 40,
                    "band": "exact",
                    "split": split,
                    "n_gap": int(v["gap"].sum()),
                    "n_in_band": int(v["in_band"].sum()),
                    "n_close": int(v["close_hit"].sum()),
                    "theo": summarize(v["theo"], df.game_date.astype(str), v["stop"]),
                    "causal": summarize(v["causal"], df.game_date.astype(str), v["stop"]),
                    "delta_theo_minus_causal": round(float(v["theo"].mean() - v["causal"].mean()), 6),
                }
            )

        # Experiment G — VAL lock on conservative causal exact
        val_exact = [
            r
            for r in surface
            if r["band"] == "exact" and r["split"] == "VALIDATION"
        ]
        val_front = pareto_front(
            [
                {
                    "H": r["H"],
                    "mean": r["conservative_causal"]["mean"],
                    "p05": r["conservative_causal"]["p05"],
                    "inc": r["conservative_causal"].get("inc_vs_original", 0),
                }
                for r in val_exact
            ]
        )
        val_evs = [r["conservative_causal"]["mean"] for r in val_exact]
        val_hs = [r["H"] for r in val_exact]
        plat = plateau(val_hs, val_evs, 0.15)
        stop_val = exp_a["by_split"]["VALIDATION"]["stop"]["mean"]
        candidates = [r for r in val_front if r["pareto"] and r["mean"] > stop_val]
        if candidates:
            locked_h = max(candidates, key=lambda r: (r["mean"], r["p05"]))["H"]
            lock_reason = "VAL Pareto + beats 80→40; plateau preferred if tied"
        else:
            # still lock a plateau best for OOS disclosure, labeled DOES_NOT_BEAT
            locked_h = plat["best_h"]
            lock_reason = "No VAL conservative causal exact config beat 80→40. Locked plateau best for disclosure only."

        def _at(split, h, band="exact"):
            for r in surface:
                if r["H"] == h and r["band"] == band and r["split"] == split:
                    return r
            return None

        def _enrich(row):
            if row is None:
                return None
            band = band_for(row["band"], row["H"])
            j = _join(led, opp, band.lo)
            df = j.loc[_split_mask(j, row["split"])]
            vec = _book_vectors(df, band, persist_k, headline_fb, costs)
            out = dict(row)
            out["conservative_causal"] = _metrics_pack(
                vec["causal"], df.game_date.astype(str), vec["stop"]
            )
            out["theoretical_replace"] = summarize(
                vec["theo_replace"], df.game_date.astype(str), vec["stop"]
            )
            return out

        oos = _enrich(_at("OOS", locked_h))
        val = _enrich(_at("VALIDATION", locked_h))
        train = _enrich(_at("TRAIN", locked_h))
        full = _enrich(_at("FULL", locked_h))

        # Neighbor stability on VAL
        neigh = [
            _at("VALIDATION", h)
            for h in range(max(10, locked_h - 2), min(60, locked_h + 2) + 1)
        ]
        neigh = [r for r in neigh if r]

        # Persist-k sensitivity at locked H exact FULL
        persist_sens = []
        band = band_for("exact", locked_h)
        jh = _join(led, opp, band.lo)
        for k in (1, 2, 3, 5):
            for split in KEY_SPLIT:
                df = jh.loc[_split_mask(jh, split)]
                vec = _book_vectors(df, band, k, headline_fb, costs)
                persist_sens.append(
                    _surface_row(
                        locked_h, "exact", k, headline_fb, split, vec, df.game_date.astype(str)
                    )
                )

        # Audit rows for key H
        for h in sorted(set(AUDIT_HS + (locked_h,))):
            band = band_for("exact", h)
            j = _join(led, opp, band.lo)
            vec = _book_vectors(j, band, persist_k, headline_fb, costs)
            for i, r in enumerate(j.itertuples(index=False)):
                q50 = (
                    0.5 * vec["causal"][i] + 0.5 * vec["fallback"][i]
                    if vec["in_band"][i]
                    else vec["fallback"][i]
                )
                audit_rows.append(
                    {
                        "sport": sport,
                        "trade_id": f"{sport}:{getattr(r, 'event_id')}:{getattr(r, 'ticker')}",
                        "game_id": getattr(r, "event_id"),
                        "a1_market": getattr(r, "ticker"),
                        "a2_market": getattr(r, "opponent_market", None),
                        "game_date": str(getattr(r, "game_date")),
                        "dataset_split": getattr(r, "dataset_split"),
                        "entry_ts": getattr(r, "entry_time", None),
                        "nominal_entry": ENTRY,
                        "actual_entry": "UNAVAILABLE_ON_V4_LEDGER",
                        "hedge_target": h,
                        "band_lo": band.lo,
                        "band_hi": band.hi,
                        "first_touch_ts": getattr(r, "first_touch_ts", None),
                        "obs_close": None if np.isnan(vec["obs_px"][i]) else float(vec["obs_px"][i]),
                        "tier": vec["tier"][i],
                        "gap": bool(vec["gap"][i]),
                        "in_band": bool(vec["in_band"][i]),
                        "v3_class": getattr(r, "opportunity_quality_class", None),
                        "persist": getattr(r, "persist_subsequent_min", None),
                        "a1_at_touch": getattr(r, "favorite_price_at_touch_cents", None),
                        "won": bool(getattr(r, "won")),
                        "stop_triggered": bool(getattr(r, "stop_close_triggered")),
                        "pnl_hold": float(vec["hold"][i]),
                        "pnl_original": float(vec["stop"][i]),
                        "pnl_theoretical": float(vec["theo"][i]),
                        "pnl_conservative": float(vec["causal"][i]),
                        "pnl_lookahead_k3": float(vec["lookahead"][i]),
                        "pnl_prob_q50": float(q50),
                        "inc_conservative": float(vec["causal"][i] - vec["stop"][i]),
                        "label": "OBSERVABLE EXECUTION CONFIDENCE — NOT CONFIRMED FILL",
                    }
                )

        # Verdict ingredients
        oos_inc = None if oos is None else oos["conservative_causal"].get("inc_vs_original")
        val_inc = None if val is None else val["conservative_causal"].get("inc_vs_original")
        val_beats = val_inc is not None and val_inc > 0
        oos_beats = oos_inc is not None and oos_inc > 0
        if not val_beats:
            verdict = "NO_ECONOMIC_CASE_FOR_HEDGING"
            verdict_note = (
                "Conservative causal in-band (observed close, miss gaps) "
                "does not beat 80→40 on VALIDATION."
            )
        elif not oos_beats:
            verdict = "RESULT_INCONCLUSIVE"
            verdict_note = "VAL improvement did not survive OOS."
        else:
            tail = oos["conservative_causal"].get("tail_p05_vs_original", 0)
            if oos_inc > 0 and tail > 0:
                verdict = "HEDGING_IMPROVES_BOTH_EV_AND_RISK"
            elif oos_inc > 0:
                verdict = "HEDGING_IMPROVES_RISK_ADJUSTED_RETURNS"
            else:
                verdict = "RESULT_INCONCLUSIVE"
            verdict_note = "See OOS table. Assumptions: causal in-band, fallback A, fees=0."

        sports[sport] = {
            "n": int(len(led)),
            "split_n": split_n,
            "date_min": str(led.game_date.min()),
            "date_max": str(led.game_date.max()),
            "experiment_a": exp_a,
            "surface": surface,
            "named_bands": named,
            "fallback_sensitivity": fallback_sens,
            "probabilistic": prob,
            "partial": partial,
            "gaps": gaps,
            "val_pareto": val_front,
            "plateau": plat,
            "locked_h": locked_h,
            "lock_reason": lock_reason,
            "locked": {"TRAIN": train, "VALIDATION": val, "OOS": oos, "FULL": full},
            "neighbors": neigh,
            "persist_k_sensitivity": persist_sens,
            "verdict": verdict,
            "verdict_note": verdict_note,
        }

    DOCS.mkdir(parents=True, exist_ok=True)
    FRONT_DATA.mkdir(parents=True, exist_ok=True)
    audit = pd.DataFrame(audit_rows)
    audit_path = DOCS / "trade_audit.parquet"
    audit.to_parquet(audit_path, index=False)

    dash = {
        "banner": "A1 HYBRID HEDGE — RESEARCH ONLY — LIVE EXECUTION CHANGED: FALSE — PRICE EVENT ≠ FILL — NCAAB = P5 vs P5 — FEES UNRESOLVED",
        "meta": {**cfg, "baseline_gates": BASELINE},
        "sports": {k: _slim_sport(v) for k, v in sports.items()},
        "audit_preview": audit.sample(min(80, len(audit)), random_state=7).to_dict("records")
        if len(audit)
        else [],
        "audit_path": str(audit_path),
        "audit_rows": int(len(audit)),
    }
    # keep full sports on disk
    full_path = DOCS / "experiment_full.json"
    slim_path = DOCS / "dashboard.json"
    # experiment_full can be large; write parquet surfaces too
    _write_full(sports, cfg, full_path)
    slim_path.write_text(json.dumps(_sanitize(dash), default=_js, allow_nan=False))
    (FRONT_DATA / "dashboard.json").write_text(
        json.dumps(_sanitize(dash), default=_js, allow_nan=False)
    )
    (DOCS / "universe_manifest.json").write_text(
        json.dumps(
            {
                **cfg,
                "nba_n": sports["nba"]["n"],
                "ncaab_p5_n": sports["ncaab"]["n"],
                "ncaab_warehouse_not_used": 4099,
                "repro": {
                    "nba": sports["nba"]["experiment_a"]["reproduction"],
                    "ncaab": sports["ncaab"]["experiment_a"]["reproduction"],
                },
            },
            indent=2,
            default=_js,
        )
    )
    return {"docs": str(DOCS), "dashboard": str(FRONT_DATA / "dashboard.json"), "dash": dash, "sports": sports}


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
    if isinstance(o, (pd.Timestamp,)):
        return str(o)
    return str(o)


def _sanitize(obj):
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    if isinstance(obj, float) and (np.isnan(obj) or np.isinf(obj)):
        return None
    return obj


def _slim_sport(s: dict) -> dict:
    """Dashboard payload: keep surfaces but drop persist-k FULL duplicates of unused splits in named."""
    return {
        "n": s["n"],
        "split_n": s["split_n"],
        "date_min": s["date_min"],
        "date_max": s["date_max"],
        "experiment_a": s["experiment_a"],
        "surface_full_exact": [r for r in s["surface"] if r["band"] == "exact"],
        "surface_val_exact": [
            r for r in s["surface"] if r["band"] == "exact" and r["split"] == "VALIDATION"
        ],
        "named_full": [r for r in s["named_bands"] if r["split"] == "FULL" and r["persist_k"] == 3],
        "fallback_full": [r for r in s["fallback_sensitivity"] if r["split"] == "FULL"],
        "prob_full": [r for r in s["probabilistic"] if r["split"] == "FULL"],
        "partial_full": [r for r in s["partial"] if r["split"] == "FULL"],
        "gaps": s["gaps"],
        "val_pareto": s["val_pareto"],
        "plateau": s["plateau"],
        "locked_h": s["locked_h"],
        "lock_reason": s["lock_reason"],
        "locked": s["locked"],
        "neighbors": s["neighbors"],
        "verdict": s["verdict"],
        "verdict_note": s["verdict_note"],
        "surface_sym_val": [
            r
            for r in s["surface"]
            if r["split"] == "VALIDATION" and r["band"] in SURFACE_BANDS
        ],
    }


def _write_full(sports: dict, cfg: dict, path: Path) -> None:
    # Write compact JSON without repeating huge locked objects' nested bootstrap 50 times — ok.
    payload = {"meta": cfg, "sports": {}}
    for sport, s in sports.items():
        payload["sports"][sport] = {
            k: s[k]
            for k in (
                "n",
                "split_n",
                "date_min",
                "date_max",
                "experiment_a",
                "val_pareto",
                "plateau",
                "locked_h",
                "lock_reason",
                "locked",
                "verdict",
                "verdict_note",
                "gaps",
            )
        }
        # surfaces as sidecar parquet
        pd.DataFrame(s["surface"]).to_parquet(path.parent / f"surface_{sport}.parquet", index=False)
        pd.DataFrame(s["named_bands"]).to_parquet(path.parent / f"named_{sport}.parquet", index=False)
        pd.DataFrame(s["probabilistic"]).to_parquet(path.parent / f"prob_{sport}.parquet", index=False)
        pd.DataFrame(s["partial"]).to_parquet(path.parent / f"partial_{sport}.parquet", index=False)
    path.write_text(json.dumps(_sanitize(payload), default=_js, allow_nan=False))
