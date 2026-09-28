#!/usr/bin/env python3
"""NCAAB P5 conditional path decomposition — Level 2 residual Δ.

Empirical state-conditioned expected move vs observed ΔP.
Candle-path greek-like state vector, not option greeks, not W9.

Does not reopen the rejected H2 vol-normalization object.
Does not select a residual cell as a strategy.
Does not change live FIRST01.

```
RESEARCH ONLY
Δ ≠ EDGE
Γ ≠ EDGE
VOLATILITY ≠ EDGE
RESIDUAL ≠ EDGE
SEARCH FOR STRUCTURAL REPLICATION, NOT A PROFITABLE CELL
LIVE EXECUTION = FALSE
```
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

NCAAB_SCRIPTS = Path(__file__).resolve().parent
if str(NCAAB_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(NCAAB_SCRIPTS))

import ncaab_h1_h2_vol_greeks as G  # noqa: E402
import ncaab_h2_opening_vol_shock as V  # noqa: E402

REPO = Path("/Users/user/Desktop/Momento")
REPORTS = REPO / "research" / "ncaab_conditional_path_decomp"
DOCS = REPO / "docs" / "research" / "ncaab_conditional_path_decomp"
WH_OUT = (
    REPO
    / "Backtesting Suite"
    / "Data"
    / "NCAAB"
    / "2025-2026"
    / "warehouse"
    / "derived"
    / "ncaab"
    / "conditional_path_decomp"
)

CLOCK_BINS = ("H1_1", "H1_2", "H2_OPEN", "H2_MID", "H2_LATE")
MARGIN_BANDS = ("M0_3", "M4_7", "M8_12", "M13P")
RESIDUAL_BUCKETS = (
    "EXTREME_NEG",
    "MOD_NEG",
    "NORMAL",
    "MOD_POS",
    "EXTREME_POS",
)
TRAIN_SPLIT = "IN_SAMPLE"
MIN_CELL = 40
RECENT_K = 8
RECENT_MIN = 4
LOOKS = (1, 5, 10)
STATUS = {
    "level": 2,
    "title": "CONDITIONAL PATH DECOMPOSITION",
    "level_2": "MEASUREMENT_SUCCESSFUL_RECOVERY_HYPOTHESIS_FAILED",
    "level_3": "MEASUREMENT_STORED_REVERSAL_HYPOTHESIS_NOT_SUPPORTED",
    "levels_4_5": "NO_MATERIAL_STRUCTURE_OBSERVED",
    "next_question": "CAN_NONLINEAR_STATE_TRANSITIONS_EXPLAIN_RESIDUAL_VARIATION",
    "next_objective": "STOP_THIS_BRANCH",
    "state_transition": "EXPLANATORY_IMPROVEMENT_FAILED",
    "strategy_authorized": False,
    "cell_selection_authorized": False,
    "further_optimization_authorized": False,
    "live_execution": False,
    "possession_unavailable": True,
    "rejected_parent": "ncaab_h2_opening_vol_shock",
}

TRANS_CLASSES = (
    "LEAD_SHRINK",
    "LEAD_EXTEND",
    "LEAD_TO_TIE",
    "LEAD_TO_TRAIL",
    "TRAIL_WIDEN",
    "TRAIL_SHRINK",
    "TRAIL_TO_TIE",
    "TRAIL_TO_LEAD",
    "TIE_TO_LEAD",
    "TIE_TO_TRAIL",
)
MATERIAL_VAL_REDUCTION = 0.10
MATERIAL_OOS_REDUCTION = 0.05


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def clock_bin(period, remaining_s) -> str | None:
    if period is None or remaining_s is None:
        return None
    p = int(period)
    rem = float(remaining_s)
    if p == 1:
        return "H1_1" if rem > 600.0 else "H1_2"
    if p == 2:
        if rem > 900.0:
            return "H2_OPEN"
        if rem > 300.0:
            return "H2_MID"
        return "H2_LATE"
    if p >= 3:
        return "OT"
    return None


def margin_band(abs_m: float | None) -> str | None:
    if abs_m is None:
        return None
    a = abs(float(abs_m))
    if a <= 3:
        return "M0_3"
    if a <= 7:
        return "M4_7"
    if a <= 12:
        return "M8_12"
    return "M13P"


def price_band(p: float | None) -> str | None:
    if p is None:
        return None
    if p < 40:
        return "P_LT40"
    if p < 60:
        return "P40_60"
    if p < 75:
        return "P60_75"
    return "P75P"


def residual_bucket(eps: float | None) -> str | None:
    if eps is None:
        return None
    if eps <= -3.0:
        return "EXTREME_NEG"
    if eps <= -1.0:
        return "MOD_NEG"
    if eps < 1.0:
        return "NORMAL"
    if eps < 3.0:
        return "MOD_POS"
    return "EXTREME_POS"


def residual(dp: float, dm: float, beta: float | None) -> float | None:
    if beta is None:
        return None
    return dp - beta * dm


def shrink_beta(cell_n, cell_b, clock_n, clock_b, glob_b, min_n: int = MIN_CELL):
    if cell_n >= min_n and cell_b is not None:
        return cell_b, "clock_margin"
    if clock_n >= min_n and clock_b is not None:
        return clock_b, "clock"
    return glob_b, "global"


def trans_class(m_pre: float | None, m_post: float | None) -> str | None:
    """Signed margin transition. Not |M|, not ΔM alone."""
    if m_pre is None or m_post is None:
        return None
    a, b = float(m_pre), float(m_post)
    if a > 0 and b > 0:
        return "LEAD_SHRINK" if b < a else "LEAD_EXTEND"
    if a > 0 and b == 0:
        return "LEAD_TO_TIE"
    if a > 0 and b < 0:
        return "LEAD_TO_TRAIL"
    if a < 0 and b < 0:
        return "TRAIL_WIDEN" if b < a else "TRAIL_SHRINK"
    if a < 0 and b == 0:
        return "TRAIL_TO_TIE"
    if a < 0 and b > 0:
        return "TRAIL_TO_LEAD"
    if a == 0 and b > 0:
        return "TIE_TO_LEAD"
    if a == 0 and b < 0:
        return "TIE_TO_TRAIL"
    return None


def resid_var(xs: list[float]) -> float | None:
    ys = [float(x) for x in xs if x is not None]
    if len(ys) < 2:
        return None
    return statistics.variance(ys)


def r2_of(dp: list[float], eps: list[float]) -> float | None:
    vd = resid_var(dp)
    ve = resid_var(eps)
    if vd is None or ve is None or vd == 0:
        return None
    return 1.0 - ve / vd


def rel_reduction(new_var: float | None, old_var: float | None) -> float | None:
    if new_var is None or old_var is None or old_var == 0:
        return None
    return 1.0 - new_var / old_var


def yhat_ab(dm: float, rec: dict) -> float | None:
    if rec.get("beta") is None or rec.get("intercept") is None:
        return None
    return rec["intercept"] + rec["beta"] * dm


def fit_st_model(rows: list[dict]) -> dict:
    scoring = [
        r
        for r in rows
        if r.get("dm") not in (None, 0) and r.get("trans") in TRANS_CLASSES
    ]
    by_ct: dict[tuple[str, str], list] = defaultdict(list)
    by_t: dict[str, list] = defaultdict(list)
    by_ctp: dict[tuple[str, str, str], list] = defaultdict(list)
    for r in scoring:
        cb, tr, pb = r.get("clock_bin"), r.get("trans"), r.get("price_band")
        if cb in CLOCK_BINS:
            by_ct[(cb, tr)].append(r)
            by_t[tr].append(r)
            if pb:
                by_ctp[(cb, tr, pb)].append(r)

    def pack(vs):
        return G.ols_slope([r["dm"] for r in vs], [r["dp"] for r in vs])

    return {
        "n_train": len(scoring),
        "clock_trans": {f"{a}|{b}": pack(vs) for (a, b), vs in by_ct.items()},
        "trans": {k: pack(vs) for k, vs in by_t.items()},
        "clock_trans_price": {
            f"{a}|{b}|{c}": pack(vs) for (a, b, c), vs in by_ctp.items()
        },
    }


def apply_st(row: dict, st: dict) -> dict:
    dm = row.get("dm")
    if dm in (None, 0) or row.get("trans") not in TRANS_CLASSES:
        return {**row, "expected_st": None, "eps_st": None, "st_src": None}
    cb, tr, pb = row.get("clock_bin"), row.get("trans"), row.get("price_band")
    ctp = st["clock_trans_price"].get(f"{cb}|{tr}|{pb}", {})
    ct = st["clock_trans"].get(f"{cb}|{tr}", {})
    tonly = st["trans"].get(tr, {})
    yhat, src = None, None
    if (ctp.get("n") or 0) >= MIN_CELL:
        yhat, src = yhat_ab(dm, ctp), "clock_trans_price"
    if yhat is None and (ct.get("n") or 0) >= MIN_CELL:
        yhat, src = yhat_ab(dm, ct), "clock_trans"
    if yhat is None and (tonly.get("n") or 0) >= MIN_CELL:
        yhat, src = yhat_ab(dm, tonly), "trans"
    if yhat is None:
        yhat, src = row.get("expected_dp"), "fallback_l2"
    eps = None if yhat is None else row["dp"] - yhat
    return {
        **row,
        "expected_st": yhat,
        "eps_st": eps,
        "st_src": src,
        "residual_bucket_st": residual_bucket(eps),
    }


def _pairs(rows: list[dict], key: str) -> tuple[list[float], list[float]]:
    dps, eps = [], []
    for r in rows:
        if r.get(key) is None:
            continue
        dps.append(r["dp"])
        eps.append(r[key])
    return dps, eps


def explain_split(rows: list[dict]) -> dict:
    dg, eg = _pairs(rows, "eps_global")
    d2, e2 = _pairs(rows, "eps")
    ds, es = _pairs(rows, "eps_st")
    vg, v2, vs = resid_var(eg), resid_var(e2), resid_var(es)
    return {
        "n": len(rows),
        "n_st": len(es),
        "var_dp": resid_var([r["dp"] for r in rows]),
        "var_eps_global": vg,
        "var_eps_l2": v2,
        "var_eps_st": vs,
        "r2_global": r2_of(dg, eg),
        "r2_l2": r2_of(d2, e2),
        "r2_st": r2_of(ds, es),
        "st_vs_l2": rel_reduction(vs, v2),
        "st_vs_global": rel_reduction(vs, vg),
        "l2_vs_global": rel_reduction(v2, vg),
    }


def h1_vol_for_period(period, h1_sigma: float | None) -> float | None:
    if period != 2:
        return None
    return h1_sigma


def recent_sigma(prior: list[float]) -> float | None:
    tail = prior[-RECENT_K:]
    if len(tail) < RECENT_MIN:
        return None
    return statistics.stdev(tail)


def in_play_pair(prev: dict, cur: dict) -> bool:
    if prev.get("phase") != "IN_PERIOD" or cur.get("phase") != "IN_PERIOD":
        return False
    if prev.get("period") is None or cur.get("period") is None:
        return False
    return prev["period"] == cur["period"]


def tertile_cuts(xs: list[float]) -> tuple[float, float] | None:
    ys = sorted(x for x in xs if x is not None)
    if len(ys) < 9:
        return None
    return V.pctile(ys, 1.0 / 3.0), V.pctile(ys, 2.0 / 3.0)


def tertile_of(x: float | None, cuts: tuple[float, float] | None) -> str | None:
    if x is None or cuts is None:
        return None
    if x <= cuts[0]:
        return "LOW"
    if x <= cuts[1]:
        return "MID"
    return "HIGH"


def fit_betas(rows: list[dict]) -> dict:
    scoring = [r for r in rows if r.get("dm") not in (None, 0)]
    glob = G.ols_slope([r["dm"] for r in scoring], [r["dp"] for r in scoring])
    by_clock: dict[str, list] = defaultdict(list)
    by_cell: dict[tuple[str, str], list] = defaultdict(list)
    for r in scoring:
        cb, mb = r.get("clock_bin"), r.get("margin_band")
        if cb in CLOCK_BINS:
            by_clock[cb].append(r)
        if cb in CLOCK_BINS and mb in MARGIN_BANDS:
            by_cell[(cb, mb)].append(r)
    clock_b = {
        k: G.ols_slope([r["dm"] for r in vs], [r["dp"] for r in vs])
        for k, vs in by_clock.items()
    }
    cell_b = {
        f"{a}|{b}": G.ols_slope([r["dm"] for r in vs], [r["dp"] for r in vs])
        for (a, b), vs in by_cell.items()
    }
    return {
        "n_train_scoring": len(scoring),
        "global": glob,
        "clock": clock_b,
        "cell": cell_b,
    }


def apply_expected(row: dict, model: dict) -> dict:
    dm = row.get("dm")
    if dm in (None, 0):
        return {
            **row,
            "beta_used": None,
            "beta_src": None,
            "expected_dp": None,
            "eps": None,
            "eps_global": None,
            "residual_bucket": None,
        }
    cb, mb = row.get("clock_bin"), row.get("margin_band")
    cell = model["cell"].get(f"{cb}|{mb}", {})
    clock = model["clock"].get(cb, {})
    glob_b = model["global"].get("beta")
    beta, src = shrink_beta(
        cell.get("n") or 0,
        cell.get("beta"),
        clock.get("n") or 0,
        clock.get("beta"),
        glob_b,
    )
    exp = None if beta is None else beta * dm
    eps = residual(row["dp"], dm, beta)
    eps_g = residual(row["dp"], dm, glob_b)
    return {
        **row,
        "beta_used": beta,
        "beta_src": src,
        "expected_dp": exp,
        "eps": eps,
        "eps_global": eps_g,
        "residual_bucket": residual_bucket(eps),
    }


def side_bars(quotes: list[dict], snap_fn, team_is_home: bool, market: dict, game: dict) -> list[dict]:
    pairs = V.quality_pairs(quotes)
    rows = []
    prior_dp: list[float] = []
    h1_dps: list[float] = []
    prev_dp = None
    prev_delta = None
    prev_recent = None
    for p in pairs:
        prev = snap_fn(p["prev_ts"])
        cur = snap_fn(p["ts"])
        if not in_play_pair(prev, cur):
            prior_dp.append(p["dp_cents"])
            prev_dp = p["dp_cents"]
            continue
        m_pre = V.margin_of(prev["score"], team_is_home)
        m_post = V.margin_of(cur["score"], team_is_home)
        dm = None if m_pre is None or m_post is None else m_post - m_pre
        p_pre = p["prev_bid_c"] / 100.0
        p_cur = p["bid_c"] / 100.0
        dp = p["dp_cents"]
        cb = clock_bin(cur["period"], cur["remaining_s"])
        if cur["period"] == 1:
            h1_dps.append(dp)
        delta = None if dm in (None, 0) else dp / dm
        gamma_p = None if prev_dp is None else dp - prev_dp
        gamma_s = None if prev_delta is None or delta is None else delta - prev_delta
        v_rec = recent_sigma(prior_dp)
        dv = None if v_rec is None or prev_recent is None else v_rec - prev_recent
        rows.append(
            {
                "event_id": game["event_id"],
                "game_date": game.get("game_date"),
                "split": V.split_of(game.get("game_date")),
                "ticker": market.get("ticker"),
                "team": market.get("team"),
                "side": "home" if team_is_home else "away",
                "ts": p["ts"],
                "period": cur["period"],
                "remaining_s": cur["remaining_s"],
                "clock_bin": cb,
                "p_pre": p_pre,
                "p": p_cur,
                "price_band": price_band(p_pre),
                "m_pre": m_pre,
                "m_post": m_post,
                "trans": trans_class(m_pre, m_post),
                "margin_band": margin_band(None if m_pre is None else abs(m_pre)),
                "dm": dm,
                "dp": dp,
                "delta": delta,
                "gamma_p": gamma_p,
                "gamma_score": gamma_s,
                "v_recent": v_rec,
                "dv": dv,
                "theta_bar": dm == 0,
                "possession": None,
                "W": V.A.settled_yes(market),
                "_quotes": quotes,
            }
        )
        prior_dp.append(dp)
        prev_dp = dp
        if delta is not None:
            prev_delta = delta
        prev_recent = v_rec
    h1_sigma = None
    if len(h1_dps) >= V.H1_MIN_DIFFS:
        h1_sigma = statistics.stdev(h1_dps)
    for r in rows:
        r["v_h1"] = h1_vol_for_period(r["period"], h1_sigma)
        r["v_h1_status"] = "UNAVAILABLE" if r["v_h1"] is None else "H1_COMPLETE"
    return rows


def attach_path(row: dict) -> dict:
    qs = row.pop("_quotes")
    entry = row["p"]
    ts = row["ts"]
    out = dict(row)
    for h in LOOKS:
        nxt = V.bid_after(qs, ts, h * 60, V.LOOKAHEAD_SLACK_S)
        out[f"r_{h}"] = None if nxt is None else nxt - entry
    exc = V.path_excursions(qs, ts, entry, 600)
    out["mae"] = exc["mae_down"]
    out["mfe"] = exc["mfe_up"]
    return out


def surface(rows: list[dict], key: str, values: tuple[str, ...], label: str) -> list[dict]:
    out = []
    for val in values:
        sub = [r for r in rows if r.get(key) == val]
        rec = {
            "label": f"{label}={val}",
            "key": key,
            "value": val,
            "n": len(sub),
            "n_games": len({r["event_id"] for r in sub}),
            "mean_eps": V.summarize([r.get("eps") for r in sub]),
            "mean_dp": V.summarize([r.get("dp") for r in sub]),
        }
        for h in LOOKS:
            rec[f"r_{h}"] = V.summarize([r.get(f"r_{h}") for r in sub])
        rec["mae"] = V.summarize([r.get("mae") for r in sub])
        rec["mfe"] = V.summarize([r.get("mfe") for r in sub])
        w = [r.get("W") for r in sub if r.get("W") is not None]
        rec["p_w"] = None if not w else sum(1 for x in w if x) / len(w)
        out.append(rec)
    return out


def collect() -> dict:
    games_by, by_event, quotes, xwalk, cache = V.load_universe()
    raw_rows = []
    n_pbp = 0
    for event_id, ms in by_event.items():
        game = games_by[event_id]
        sides = {}
        for m in ms:
            side = V.match_side(m.get("team"), game)
            if side is None:
                continue
            sides[side] = m
        if set(sides) != {"home", "away"}:
            continue
        cw = xwalk.get(event_id) or {}
        espn_id = cw.get("espn_game_id")
        if cw.get("match_status") != "MATCHED" or not espn_id:
            continue
        actions = V.HBS._pbp_pack(espn_id, cache)
        if not actions:
            continue
        n_pbp += 1
        snap_fn = V.build_snapper(actions)
        for side, market in sides.items():
            raw_rows.extend(
                side_bars(
                    quotes.get(market["ticker"], []),
                    snap_fn,
                    side == "home",
                    market,
                    game,
                )
            )
    V.halt_if(len(raw_rows) < 1000, f"HALT few bars {len(raw_rows)}")
    train = [
        r
        for r in raw_rows
        if r["split"] == TRAIN_SPLIT and r.get("clock_bin") in CLOCK_BINS
    ]
    model = fit_betas(train)
    V.halt_if(model["n_train_scoring"] < 200, "HALT thin TRAIN scoring")
    tagged = []
    for r in raw_rows:
        if r.get("clock_bin") not in CLOCK_BINS:
            continue
        tagged.append(apply_expected(r, model))
    tagged = [attach_path(r) for r in tagged]
    scoring = [r for r in tagged if r.get("dm") not in (None, 0) and r.get("eps") is not None]
    train_sc = [r for r in scoring if r["split"] == TRAIN_SPLIT]
    v_h1_cuts = tertile_cuts([r["v_h1"] for r in train_sc if r.get("v_h1") is not None])
    v_rec_cuts = tertile_cuts([r["v_recent"] for r in train_sc if r.get("v_recent") is not None])
    for r in tagged:
        r["v_h1_tertile"] = tertile_of(r.get("v_h1"), v_h1_cuts)
        r["v_recent_tertile"] = tertile_of(r.get("v_recent"), v_rec_cuts)
        r["vol_expanding"] = None if r.get("dv") is None else r["dv"] > 0
    scoring = [r for r in tagged if r.get("dm") not in (None, 0) and r.get("eps") is not None]
    st_model = fit_st_model([r for r in scoring if r["split"] == TRAIN_SPLIT])
    scoring = [apply_st(r, st_model) for r in scoring]
    explain = {
        name: explain_split([r for r in scoring if name == "FULL" or r["split"] == name])
        for name in ("IN_SAMPLE", "VALIDATION", "OOS", "FULL")
    }
    explain["FULL"] = explain_split(scoring)
    val_red = explain["VALIDATION"]["st_vs_l2"]
    oos_red = explain["OOS"]["st_vs_l2"]
    explanatory_pass = bool(
        val_red is not None
        and oos_red is not None
        and val_red >= MATERIAL_VAL_REDUCTION
        and oos_red >= MATERIAL_OOS_REDUCTION
    )
    trans_diag = {}
    for split in ("IN_SAMPLE", "VALIDATION", "OOS"):
        sub = [r for r in scoring if r["split"] == split]
        trans_diag[split] = []
        for tr in TRANS_CLASSES:
            chunk = [r for r in sub if r.get("trans") == tr]
            trans_diag[split].append(
                {
                    "trans": tr,
                    "n": len(chunk),
                    "mean_dp": V.summarize([r["dp"] for r in chunk]),
                    "mean_eps_l2": V.summarize([r.get("eps") for r in chunk]),
                    "mean_eps_st": V.summarize([r.get("eps_st") for r in chunk]),
                    "mean_dm": V.summarize([r["dm"] for r in chunk]),
                }
            )
    st_path = None
    if explanatory_pass:
        st_path = {
            split: surface(
                [r for r in scoring if r["split"] == split and r.get("eps_st") is not None],
                "residual_bucket_st",
                RESIDUAL_BUCKETS,
                "ε_ST",
            )
            for split in ("VALIDATION", "OOS")
        }

    def by_split(name: str | None) -> list[dict]:
        if name is None:
            return scoring
        return [r for r in scoring if r["split"] == name]

    surfaces = {}
    for split in (None, "IN_SAMPLE", "VALIDATION", "OOS"):
        sub = by_split(split)
        key = "FULL" if split is None else split
        surfaces[key] = {
            "n": len(sub),
            "residual": surface(sub, "residual_bucket", RESIDUAL_BUCKETS, "ε"),
            "clock": surface(sub, "clock_bin", CLOCK_BINS, "clock"),
        }
    for r in scoring:
        gp = r.get("gamma_p")
        r["gamma_flag"] = None if gp is None else ("HIGH_NEG_G" if gp <= -3.0 else "OTHER_G")
    for split in (None, "IN_SAMPLE", "VALIDATION", "OOS"):
        sub = by_split(split)
        key = "FULL" if split is None else split
        surfaces[key]["gamma"] = surface(
            [r for r in sub if r.get("gamma_flag")],
            "gamma_flag",
            ("HIGH_NEG_G", "OTHER_G"),
            "Γ",
        )
        surfaces[key]["v_h1"] = surface(
            [r for r in sub if r.get("v_h1_tertile")],
            "v_h1_tertile",
            ("LOW", "MID", "HIGH"),
            "V_H1",
        )
        surfaces[key]["v_recent"] = surface(
            [r for r in sub if r.get("v_recent_tertile")],
            "v_recent_tertile",
            ("LOW", "MID", "HIGH"),
            "V_recent",
        )
        exp = [r for r in sub if r.get("vol_expanding") is True]
        con = [r for r in sub if r.get("vol_expanding") is False]
        surfaces[key]["vol_path"] = [
            {
                "label": "vol_expanding",
                "n": len(exp),
                "r_5": V.summarize([r.get("r_5") for r in exp]),
                "mean_eps": V.summarize([r.get("eps") for r in exp]),
            },
            {
                "label": "vol_contracting",
                "n": len(con),
                "r_5": V.summarize([r.get("r_5") for r in con]),
                "mean_eps": V.summarize([r.get("eps") for r in con]),
            },
        ]
        ext = [r for r in sub if r.get("residual_bucket") == "EXTREME_NEG"]
        surfaces[key]["extreme_neg_by_vh1"] = surface(
            [r for r in ext if r.get("v_h1_tertile")],
            "v_h1_tertile",
            ("LOW", "MID", "HIGH"),
            "εEXT×V_H1",
        )

    theta = [r for r in tagged if r.get("theta_bar") and r.get("clock_bin") in CLOCK_BINS]
    theta_surf = {}
    for split in (None, "IN_SAMPLE", "VALIDATION", "OOS"):
        sub = theta if split is None else [r for r in theta if r["split"] == split]
        key = "FULL" if split is None else split
        theta_surf[key] = {
            "n": len(sub),
            "mean_dp": V.summarize([r["dp"] for r in sub]),
            "by_clock": surface(sub, "clock_bin", CLOCK_BINS, "Θ clock"),
        }

    slim_events = []
    for r in scoring:
        slim_events.append(
            {
                k: r[k]
                for k in (
                    "event_id",
                    "game_date",
                    "split",
                    "side",
                    "ts",
                    "clock_bin",
                    "margin_band",
                    "price_band",
                    "m_pre",
                    "m_post",
                    "trans",
                    "dm",
                    "dp",
                    "delta",
                    "gamma_p",
                    "gamma_score",
                    "v_recent",
                    "v_h1",
                    "dv",
                    "eps",
                    "eps_st",
                    "eps_global",
                    "expected_dp",
                    "expected_st",
                    "st_src",
                    "beta_used",
                    "beta_src",
                    "residual_bucket",
                    "v_h1_tertile",
                    "v_recent_tertile",
                    "vol_expanding",
                    "r_1",
                    "r_5",
                    "r_10",
                    "mae",
                    "mfe",
                    "W",
                )
                if k in r
            }
        )

    return {
        "written_utc": utc_now(),
        "research_only": True,
        "live_execution_changed": False,
        "not_w9": True,
        "separate_from_first75": True,
        "status": STATUS,
        "explanatory_gate": {
            "metric": "residual_variance_reduction_st_vs_l2",
            "val_threshold": MATERIAL_VAL_REDUCTION,
            "oos_threshold": MATERIAL_OOS_REDUCTION,
            "val_reduction": val_red,
            "oos_reduction": oos_red,
            "passed": explanatory_pass,
            "st_path_evaluated": explanatory_pass,
        },
        "explain": explain,
        "st_model": {
            "n_train": st_model["n_train"],
            "clock_trans": st_model["clock_trans"],
            "trans": st_model["trans"],
        },
        "trans_diag": trans_diag,
        "st_path": st_path,
        "universe": "KXNCAAMBGAME 2025-26 P5 vs P5",
        "p5_games": V.P5_GAMES_EXPECTED,
        "n_matched_pbp": n_pbp,
        "n_in_play_bars": len(tagged),
        "n_scoring": len(scoring),
        "possession": "UNAVAILABLE",
        "model_train_split": TRAIN_SPLIT,
        "model": {
            "n_train_scoring": model["n_train_scoring"],
            "global_beta": model["global"],
            "clock": {k: v for k, v in model["clock"].items()},
            "cell": {k: v for k, v in model["cell"].items()},
        },
        "v_h1_cuts": v_h1_cuts,
        "v_recent_cuts": v_rec_cuts,
        "surfaces": surfaces,
        "theta": theta_surf,
        "events": slim_events,
    }


def _f(x, d=3):
    if x is None:
        return "—"
    return f"{x:.{d}f}"


def _surf_row(rec: dict) -> str:
    return (
        f"| {rec['label']} | {rec['n']} | {rec['n_games']} | "
        f"{_f((rec.get('mean_eps') or {}).get('mean'))} | "
        f"{_f((rec.get('r_1') or {}).get('mean'))} | "
        f"{_f((rec.get('r_5') or {}).get('mean'))} | "
        f"{_f((rec.get('r_10') or {}).get('mean'))} | "
        f"{_f((rec.get('mae') or {}).get('mean'))} | "
        f"{_f((rec.get('mfe') or {}).get('mean'))} | "
        f"{_f(None if rec.get('p_w') is None else 100.0 * rec['p_w'], 1)} |"
    )


def write_spec() -> str:
    return """# CONDITIONAL PATH DECOMPOSITION — Level 2 residual Δ

```
RESEARCH ONLY
Δ ≠ EDGE
Γ ≠ EDGE
VOLATILITY ≠ EDGE
RESIDUAL ≠ EDGE
A GREEK-LIKE STATE VARIABLE IS NOT AN AUTHORIZATION TO TRADE
SEARCH FOR STRUCTURAL REPLICATION, NOT A PROFITABLE CELL
LIVE EXECUTION = FALSE
```

Not W9. Not option greeks. Not FIRST75. Not the rejected H2
vol-normalization entry object.

## Frozen status

```
LEVEL 2: MEASUREMENT SUCCESSFUL; RECOVERY HYPOTHESIS FAILED
LEVEL 3: MEASUREMENT STORED; REVERSAL HYPOTHESIS NOT SUPPORTED
LEVELS 4–5: NO MATERIAL STRUCTURE OBSERVED
STATE TRANSITION: EXPLANATORY IMPROVEMENT FAILED
NEXT OBJECTIVE: STOP THIS BRANCH
NOT: PROFITABLE SUBSET DISCOVERY
```

## Hierarchy

1. Raw price move — **REJECTED** as a recovery signal
   (`ncaab_h2_opening_vol_shock`, RESULT NEGATIVE).
2. State-adjusted residual Δ — measurement successful; recovery failed.
3. Gamma / acceleration — stored; reversal not supported.
4. Volatility interaction — no material structure.
5. Time-state / theta — no material structure.
6. Signed M(t-1) → M(t) transitions — measured; residual-variance
   reduction **failed**. Remaining-residual R5 was not evaluated.

## Residual

ε_t = ΔP_t − β(clock, |M|) · ΔM_t

β is fit on **IN_SAMPLE scoring minutes only**, then applied forward.
Cell β (clock × margin band) if n ≥ 40, else clock β, else global β.
Global β is stored only as a baseline, not the primary expected move.

## Causal F_τ

- clock_bin, P_pre, M_pre, ΔM, sign(ΔM)
- V_recent = σ of prior ≤8 signed ΔP (strictly before t)
- V_h1 = H1 σ only after H1 completes (period 2). UNAVAILABLE in H1.
- possession: **UNAVAILABLE** (not invented)

## Frozen residual buckets (cents, not fit to R5)

EXTREME_NEG ε≤−3 · MOD_NEG (−3,−1] · NORMAL (−1,1)
MOD_POS [1,3) · EXTREME_POS ≥3

Do not promote the bucket with the largest R5.

## Replication gate (not a strategy)

A residual bucket is *structurally interesting* only if VAL and OOS
mean R5 have the same sign, |R5| ≥ 1.0¢, and OOS n ≥ 30.
Failing the gate is a result. Do not retune buckets to pass it.

## State-transition model (explanatory)

Ŷ = α(clock, trans) + β(clock, trans)·ΔM
trans ∈ LEAD_SHRINK / LEAD_TO_TRAIL / TRAIL_WIDEN / …

Fit on IN_SAMPLE only. Shrink to trans-only, then to Level-2 Ŷ.
Optional richer cell adds P_pre band if n≥40.

Primary outcome: 1 − Var(ε_ST)/Var(ε_L2) on VAL and OOS.
Material if VAL ≥ 10% and OOS ≥ 5%. Remaining residual R5 is
**not evaluated** unless that gate passes. This is not a rescue of
EXTREME_NEG.
"""


def write_report(doc: dict) -> str:
    s = doc["surfaces"]
    m = doc["model"]
    lines = [
        "# Conditional path decomposition — residual Δ (Level 2)",
        "",
        "```",
        "RESEARCH ONLY",
        "Δ ≠ EDGE   Γ ≠ EDGE   VOLATILITY ≠ EDGE   RESIDUAL ≠ EDGE",
        "SEARCH FOR STRUCTURAL REPLICATION, NOT A PROFITABLE CELL",
        "LIVE EXECUTION = FALSE",
        "```",
        "",
        "State-conditioned residual, not raw vol. Not W9. Not FIRST75.",
        "Parent H2 vol-normalization object remains **REJECTED**.",
        "",
        f"P5 games {doc['p5_games']}. MATCHED PBP {doc['n_matched_pbp']}.",
        f"In-play bars {doc['n_in_play_bars']}. Scoring bars {doc['n_scoring']}.",
        f"TRAIN (IN_SAMPLE) scoring used to fit β: **{m['n_train_scoring']}**.",
        f"Global TRAIN β = {_f((m['global_beta'] or {}).get('beta'))} ¢/pt "
        f"(r={_f((m['global_beta'] or {}).get('r'))}). Possession UNAVAILABLE.",
        "",
        "## TRAIN clock β (¢/pt)",
        "",
        "| Clock | n | β | r |",
        "|---|---:|---:|---:|",
    ]
    for k in CLOCK_BINS:
        b = m["clock"].get(k) or {}
        lines.append(f"| {k} | {b.get('n', 0)} | {_f(b.get('beta'))} | {_f(b.get('r'))} |")
    lines.extend(
        [
            "",
            "## Level 2 — residual response surface",
            "",
            "IN_SAMPLE residuals are in-sample to the β fit. VAL / OOS are",
            "the confirmation windows. Do not pick a cell.",
            "",
        ]
    )
    for split in ("IN_SAMPLE", "VALIDATION", "OOS"):
        lines.extend(
            [
                f"### {split}",
                "",
                "| Bucket | N | Games | mean ε | R1 | R5 | R10 | MAE | MFE | P(W)% |",
                "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for rec in s[split]["residual"]:
            lines.append(_surf_row(rec))
        lines.append("")
    lines.extend(
        [
            "## Clock (Level 5 descriptive)",
            "",
            "VALIDATION only — time-state, not a selected hour.",
            "",
            "| Bucket | N | Games | mean ε | R1 | R5 | R10 | MAE | MFE | P(W)% |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for rec in s["VALIDATION"]["clock"]:
        lines.append(_surf_row(rec))
    lines.extend(
        [
            "",
            "## Level 3 — price acceleration Γ = ΔP_t − ΔP_{t−1} (VAL)",
            "",
            "| Bucket | N | Games | mean ε | R1 | R5 | R10 | MAE | MFE | P(W)% |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for rec in s["VALIDATION"]["gamma"]:
        lines.append(_surf_row(rec))
    lines.extend(
        [
            "",
            "## Level 4 — H1-vol tertiles (TRAIN cuts, VAL rows)",
            "",
            "| Bucket | N | Games | mean ε | R1 | R5 | R10 | MAE | MFE | P(W)% |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for rec in s["VALIDATION"]["v_h1"]:
        lines.append(_surf_row(rec))
    lines.extend(
        [
            "",
            "EXTREME_NEG residual × H1-vol tertile (VAL):",
            "",
            "| Bucket | N | Games | mean ε | R1 | R5 | R10 | MAE | MFE | P(W)% |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for rec in s["VALIDATION"]["extreme_neg_by_vh1"]:
        lines.append(_surf_row(rec))
    vp = s["VALIDATION"]["vol_path"]
    lines.extend(
        [
            "",
            f"VAL vol expanding n={vp[0]['n']} R5={_f(vp[0]['r_5']['mean'])} "
            f"mean ε={_f(vp[0]['mean_eps']['mean'])}.",
            f"VAL vol contracting n={vp[1]['n']} R5={_f(vp[1]['r_5']['mean'])} "
            f"mean ε={_f(vp[1]['mean_eps']['mean'])}.",
            "",
            "## Theta-like (ΔM = 0) — VAL mean ΔP by clock",
            "",
            "| Clock | N | mean ΔP |",
            "|---|---:|---:|",
        ]
    )
    for rec in doc["theta"]["VALIDATION"]["by_clock"]:
        lines.append(
            f"| {rec['value']} | {rec['n']} | {_f((rec.get('mean_dp') or {}).get('mean'))} |"
        )
    # replication gate
    lines.extend(
        [
            "",
            "## Replication gate (frozen; not a strategy)",
            "",
            "Same sign of mean R5 on VAL and OOS, |R5| ≥ 1.0¢, OOS n ≥ 30.",
            "",
            "| ε bucket | VAL R5 | VAL n | OOS R5 | OOS n | gate |",
            "|---|---:|---:|---:|---:|---|",
        ]
    )
    val_r = {r["value"]: r for r in s["VALIDATION"]["residual"]}
    oos_r = {r["value"]: r for r in s["OOS"]["residual"]}
    for b in RESIDUAL_BUCKETS:
        vr = val_r[b]["r_5"]["mean"]
        vn = val_r[b]["n"]
        o5 = oos_r[b]["r_5"]["mean"]
        on = oos_r[b]["n"]
        ok = (
            vr is not None
            and o5 is not None
            and ((vr > 0 and o5 > 0) or (vr < 0 and o5 < 0))
            and abs(vr) >= 1.0
            and abs(o5) >= 1.0
            and on >= 30
        )
        lines.append(
            f"| {b} | {_f(vr)} | {vn} | {_f(o5)} | {on} | "
            f"{'PASS' if ok else 'FAIL'} |"
        )
    lines.extend(
        [
            "",
            "FAIL on every bucket means Level 2 has not produced a",
            "replicated residual-recovery phenomenon. That is a result.",
            "Do not retune the cents cuts to manufacture a PASS.",
            "",
            "## Reading (descriptive)",
            "",
            "Excess movement **exists**: TRAIN clock β rises from 0.79 ¢/pt",
            "in H1_1 to 1.30 in H2_LATE, and EXTREME residual buckets have",
            "|mean ε| ≈ 5.7–6.0¢. A global 0.93 ¢/pt does not absorb the",
            "state. That answers “does excess exist?” with yes, as variation.",
            "",
            "It does **not** answer “does excess reverse?” with a replicated",
            "yes. VAL EXTREME_NEG R5 is +0.39¢ after a −5.8¢ residual",
            "(same economic class as the rejected +0.14¢ raw-shock bounce).",
            "EXTREME_POS is the mirror (−0.29¢). OOS flips both signs.",
            "Median R is 0 wherever we stored it. Γ HIGH_NEG continues down",
            "(VAL R5 −0.21¢): acceleration looks like information, not",
            "overshoot. H1-vol tertiles do not move mean ε or R5.",
            "",
            "Do not promote εEXT × V_H1. VAL R5 is +0.45 to +0.60 across",
            "all three tertiles; that is still sub-cent, and OOS cells are",
            "thin. Expanding vs contracting vol is a wash.",
            "",
            "Theta (ΔM=0) mean ΔP is ~0 at every clock bin. Time alone is",
            "not a drift we can see at one-minute resolution on this tape.",
            "",
            "Level 2 status: **excess exists; replicated recovery does not.**",
            "The parent vol-norm object stays rejected. No cell is authorized.",
            "",
            "Signed M(t-1) → M(t) transitions were measured next.",
            "They do not reduce residual variance versus Level 2.",
            "See `STATUS.md` and `STATE_TRANSITION.md`. Stop this branch.",
            "",
            "## What this is not",
            "",
            "- Not an entry, fade, or normalization-buy rule.",
            "- Not a promotion of the best residual cell.",
            "- Not W9 / option greeks / L2 / fills.",
            "- Not a reopening of the rejected H2 vol-norm object.",
            "- Not MLB FIRST01.",
            "",
            "**LIVE DEPLOYMENT: NOT AUTHORIZED**",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def write_status() -> str:
    return """# CONDITIONAL PATH DECOMPOSITION — status

```
LEVEL 2:
MEASUREMENT SUCCESSFUL
RECOVERY HYPOTHESIS FAILED

LEVEL 3:
MEASUREMENT STORED
REVERSAL HYPOTHESIS NOT SUPPORTED

LEVELS 4–5:
NO MATERIAL STRUCTURE OBSERVED

STATE TRANSITION:
EXPLANATORY IMPROVEMENT FAILED
(VAL residual variance rose vs Level 2;
 OOS residual variance rose vs Level 2)

NEXT OBJECTIVE:
STOP THIS BRANCH

NOT:
PROFITABLE SUBSET DISCOVERY
NOT:
LEVEL 6
NOT:
RESCUE EXTREME_NEG

LIVE EXECUTION = FALSE
```

Raw shock, state-conditioned excess, acceleration, volatility
regime, and simple clock drift are **not** demonstrated
five-minute recovery mechanisms in this P5 population.

A richer signed M(t-1) → M(t) surface does **not** explain
the residual variation Level 2 leaves. Mean geometry differs
across LEAD_SHRINK / LEAD_TO_TRAIL / TRAIL_WIDEN. That is a
diagnostic, not the gate, and not a recovery signal.

See `STATE_TRANSITION.md`.
"""


def write_st_report(doc: dict) -> str:
    g = doc["explanatory_gate"]
    lines = [
        "# State-transition explanation — residual variance, not R5",
        "",
        "```",
        "EXPLANATORY IMPROVEMENT FAILED",
        "NOT A RESCUE OF EXTREME_NEG",
        "NOT PROFITABLE SUBSET DISCOVERY",
        "LIVE EXECUTION = FALSE",
        "```",
        "",
        r"Question: can \(E[\Delta P \mid M_{t-1}, M_t, P_{t-1}, \mathrm{clock}]\)",
        "explain residual variation that Level 2 leaves unexplained?",
        "",
        "Level 2: Ŷ = β(clock, |M|)·ΔM",
        "State-transition: Ŷ = α(clock, trans) + β(clock, trans)·ΔM",
        "with optional P_pre band if the cell is thick enough.",
        "",
        f"Material gate (frozen): VAL relative Var reduction ≥ "
        f"{MATERIAL_VAL_REDUCTION:.0%} and OOS ≥ {MATERIAL_OOS_REDUCTION:.0%}.",
        f"VAL = {_f(None if g['val_reduction'] is None else 100.0 * g['val_reduction'], 1)}% · "
        f"OOS = {_f(None if g['oos_reduction'] is None else 100.0 * g['oos_reduction'], 1)}% · "
        f"**{'PASS' if g['passed'] else 'FAIL'}**.",
        "",
        "Remaining-residual R5 is "
        + (
            "shown below only because the explanatory gate passed."
            if g["passed"]
            else "**not evaluated** — the gate failed."
        ),
        "",
        "## Residual variance by split",
        "",
        "| Split | n | Var ΔP | Var ε global | Var ε L2 | Var ε ST | R² L2 | R² ST | ST vs L2 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name in ("IN_SAMPLE", "VALIDATION", "OOS"):
        e = doc["explain"][name]
        lines.append(
            f"| {name} | {e['n']} | {_f(e['var_dp'])} | {_f(e['var_eps_global'])} | "
            f"{_f(e['var_eps_l2'])} | {_f(e['var_eps_st'])} | "
            f"{_f(e['r2_l2'])} | {_f(e['r2_st'])} | {_f(e['st_vs_l2'])} |"
        )
    lines.extend(
        [
            "",
            "## VAL Level-2 residual by signed transition",
            "",
            "If L2 ε concentrates on LEAD_TO_TRAIL / TIE crossings, the",
            "residual is geometry, not an anomalous market response.",
            "",
            "| Transition | N | mean ΔM | mean ΔP | mean ε L2 | mean ε ST |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for rec in doc["trans_diag"]["VALIDATION"]:
        lines.append(
            f"| {rec['trans']} | {rec['n']} | "
            f"{_f(rec['mean_dm']['mean'])} | {_f(rec['mean_dp']['mean'])} | "
            f"{_f(rec['mean_eps_l2']['mean'])} | {_f(rec['mean_eps_st']['mean'])} |"
        )
    if g["passed"] and doc.get("st_path"):
        lines.extend(
            [
                "",
                "## Secondary — ST residual path (gate passed only)",
                "",
                "Not a strategy. Same frozen cents buckets on ε_ST.",
                "",
            ]
        )
        for split in ("VALIDATION", "OOS"):
            lines.extend(
                [
                    f"### {split}",
                    "",
                    "| Bucket | N | Games | mean ε | R1 | R5 | R10 | MAE | MFE | P(W)% |",
                    "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
                ]
            )
            for rec in doc["st_path"][split]:
                lines.append(_surf_row(rec))
            lines.append("")
    else:
        lines.extend(
            [
                "",
                "No ST residual R5 table. Explanatory improvement was not",
                "material. Do not inspect path statistics to rescue a cell.",
                "",
            ]
        )
    lines.extend(
        [
            "## Reading",
            "",
            "The gate is residual-variance reduction, not a mean residual",
            "in one transition cell. VAL and OOS both fail: ST raises",
            "Var(ε) versus Level 2. IN_SAMPLE is already slightly worse,",
            "so this is not only a calendar shift.",
            "",
            "LEAD_TO_TRAIL still has a more negative Level-2 mean residual",
            "than LEAD_SHRINK or TRAIL_WIDEN. Same-size ΔM is not the same",
            "state. That diagnostic does not authorize a richer model, a",
            "recovery rule, or inspection of ST residual R5.",
            "",
            "Stop this branch. Do not invent Level 6 to rescue the residual.",
            "",
            "## What this is not",
            "",
            "- Not a new Greek.",
            "- Not Level 6 replication of a recovery rule.",
            "- Not authorization to retune EXTREME_NEG.",
            "- Not live FIRST01.",
            "",
            "**LIVE DEPLOYMENT: NOT AUTHORIZED**",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def write_outputs(doc: dict) -> None:
    events = doc.pop("events")
    spec = write_spec()
    report = write_report(doc)
    status = write_status()
    st = write_st_report(doc)
    payload = json.dumps(doc, indent=2) + "\n"
    events_txt = "\n".join(json.dumps(e) for e in events) + "\n"
    for dest in (REPORTS, DOCS, WH_OUT):
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "SPEC.md").write_text(spec)
        (dest / "STATUS.md").write_text(status)
        (dest / "REPORT.md").write_text(report)
        (dest / "STATE_TRANSITION.md").write_text(st)
        (dest / "summary.json").write_text(payload)
        (dest / "events.jsonl").write_text(events_txt)


def main() -> int:
    doc = collect()
    write_outputs(doc)
    val = doc["surfaces"]["VALIDATION"]["residual"]
    ext = next(r for r in val if r["value"] == "EXTREME_NEG")
    print(
        json.dumps(
            {
                "n_scoring": doc["n_scoring"],
                "train_n": doc["model"]["n_train_scoring"],
                "global_beta": doc["model"]["global_beta"].get("beta"),
                "val_extreme_neg_n": ext["n"],
                "val_extreme_neg_r5": ext["r_5"]["mean"],
                "st_vs_l2_val": doc["explanatory_gate"]["val_reduction"],
                "st_vs_l2_oos": doc["explanatory_gate"]["oos_reduction"],
                "explanatory_pass": doc["explanatory_gate"]["passed"],
                "out": str(REPORTS),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
