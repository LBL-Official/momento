#!/usr/bin/env python3
"""Build complete pre-80 arrival curves. No post-80 information."""

from __future__ import annotations

import bisect
import pickle
import sys
from functools import lru_cache

import numpy as np

from common import (
    GRID_N,
    MIN_PATH_POINTS,
    OUT,
    e4_to_cents,
    load_crosswalk,
    read_parquet_rows,
    resample_series,
    downsample,
    utc_now,
    write_json,
    write_parquet,
)
from pbp_align import (
    box_header,
    classify_confidence,
    enrich_actions,
    load_box,
    load_pbp,
    replay_residuals,
    snap_to_entry,
    team_scores,
)


@lru_cache(maxsize=2048)
def enriched(nba_id: str):
    pbp = load_pbp(nba_id)
    header = box_header(load_box(nba_id))
    actions = enrich_actions((pbp or {}).get("game", {}).get("actions") or [], header)
    index = [i for i, a in enumerate(actions) if a["modeled_wall_ts"] is not None]
    ts = [actions[i]["modeled_wall_ts"] for i in index]
    residuals = replay_residuals(actions)
    return actions, tuple(index), tuple(ts), header, tuple(residuals)


def snap_at(actions, index, ts_list, t):
    if not ts_list:
        return None
    k = bisect.bisect_right(ts_list, t) - 1
    if k < 0:
        return None
    return actions[index[k]]


def local_vol(cents, n=5):
    if len(cents) < n + 1:
        return None
    d = np.diff(cents[-n - 1 :])
    if len(d) < 2:
        return None
    return float(np.std(d, ddof=1))


def functionals(ts, cents):
    n = len(cents)
    if n < 2:
        return {
            "n_candles": n,
            "duration_minutes": 0.0,
            "total_variation_cents": None,
            "path_efficiency": None,
            "n_reversals": 0,
            "min_bid_cents": None if not n else float(min(cents)),
            "max_bid_cents": None if not n else float(max(cents)),
            "mean_bid_cents": None if not n else float(np.mean(cents)),
            "frac_below_50": None,
            "frac_below_60": None,
            "frac_below_70": None,
            "path_vol_proxy_cents": None,
            "volatility_kind": "1-MINUTE CANDLE VOLATILITY PROXY",
        }
    d = np.diff(cents)
    tv = float(np.sum(np.abs(d)))
    net = float(cents[-1] - cents[0])
    rev = 0
    for a, b in zip(d[:-1], d[1:]):
        if a * b < 0:
            rev += 1
    return {
        "n_candles": n,
        "duration_minutes": (ts[-1] - ts[0]) / 60.0,
        "total_variation_cents": tv,
        "path_efficiency": None if tv <= 0 else abs(net) / tv,
        "n_reversals": rev,
        "min_bid_cents": float(min(cents)),
        "max_bid_cents": float(max(cents)),
        "mean_bid_cents": float(np.mean(cents)),
        "frac_below_50": float(np.mean(np.array(cents) < 50.0)),
        "frac_below_60": float(np.mean(np.array(cents) < 60.0)),
        "frac_below_70": float(np.mean(np.array(cents) < 70.0)),
        "path_vol_proxy_cents": float(np.std(d, ddof=1)) if len(d) >= 2 else None,
        "volatility_kind": "1-MINUTE CANDLE VOLATILITY PROXY",
    }


def from50_slice(ts, cents):
    """Last close < 50 before first-80, then the remainder including 80."""
    last_below = None
    for i in range(len(cents) - 1, -1, -1):
        if cents[i] < 50.0:
            last_below = i
            break
    if last_below is None:
        return None, None, "NEVER_BELOW_50"
    sl_t = ts[last_below:]
    sl_c = cents[last_below:]
    if len(sl_c) < MIN_PATH_POINTS:
        return sl_t, sl_c, "INSUFFICIENT"
    return sl_t, sl_c, "OK"


def main() -> int:
    trades = read_parquet_rows(OUT / "first80_trades.parquet")
    if len(trades) != 1230:
        print("need 1230 trades", file=sys.stderr)
        return 1
    quotes = pickle.loads((OUT / "_quotes_cache.pkl").read_bytes())
    xwalk = load_crosswalk()
    n = len(trades)
    full_grid = np.full((n, GRID_N), np.nan)
    from50_grid = np.full((n, GRID_N), np.nan)
    score_grid = np.full((n, GRID_N), np.nan)
    raw_full = []
    rows = []
    for i, tr in enumerate(trades):
        series = quotes.get(tr["ticker"], [])
        entry = int(tr["entry_decision_time"])
        pre = [q for q in series if q["ts"] <= entry and q["bid_c"] is not None]
        rec = {
            "trade_id": tr["trade_id"],
            "dataset_split": tr["dataset_split"],
            "Y_40_CLOSE": tr["Y_40_CLOSE"],
            "game_date": tr["game_date"],
            "entry_decision_time": entry,
            "feature_maximum_source_timestamp": entry if not pre else int(pre[-1]["ts"]),
            "path_status": "INSUFFICIENT",
            "from50_status": "INSUFFICIENT",
            "alignment_confidence": "UNUSABLE",
            "game_feature_status": "UNAVAILABLE",
            "same_bar_limitation": "SAME_BAR_1M_LIMITATION",
        }
        if len(pre) < MIN_PATH_POINTS:
            rec["n_candles"] = len(pre)
            rows.append(rec)
            raw_full.append(np.array([]))
            continue
        ts = [int(q["ts"]) for q in pre]
        cents = [e4_to_cents(q["bid_c"]) for q in pre]
        rec["path_status"] = "OK"
        rec.update(functionals(ts, cents))
        rec["minutes_from_50_to_80"] = None
        sl_t, sl_c, st50 = from50_slice(ts, cents)
        rec["from50_status"] = st50
        if st50 == "OK":
            rec["minutes_from_50_to_80"] = (sl_t[-1] - sl_t[0]) / 60.0
            from50_grid[i] = resample_series(sl_t, sl_c)
        full_grid[i] = resample_series(ts, cents)
        raw_full.append(downsample(cents))
        # state / local competitor
        rec["state_entry_bid_cents"] = cents[-1]
        ask = e4_to_cents(pre[-1]["ask_c"])
        rec["state_spread_cents"] = None if ask is None else ask - cents[-1]
        rec["state_minutes_to_close"] = (
            None
            if tr.get("close_ts") is None
            else (int(tr["close_ts"]) - entry) / 60.0
        )
        rec["state_vol_5m_cents"] = local_vol(cents, 5)
        rec["state_feature_family"] = "STATE_OR_LOCAL"
        # game path along the same timestamps
        cw = xwalk.get(tr["event_id"]) or {}
        nba_id = cw.get("nba_game_id")
        code = (tr.get("team_code") or "").upper()
        home = (tr.get("home_team_code") or "").upper()
        team_home = True if code and code == home else False if code else None
        score_ts, score_vals = [], []
        if nba_id and cw.get("match_status") == "MATCHED" and team_home is not None:
            pack = enriched(nba_id)
            actions, index, ts_list, header, residuals = pack
            index, ts_list = list(index), list(ts_list)
            residuals = list(residuals)
            snap_meta = snap_to_entry(actions, entry)
            conf, reason = classify_confidence(actions, snap_meta, entry, header, residuals)
            rec["alignment_confidence"] = conf
            rec["alignment_reason"] = reason
            rec["game_phase"] = snap_meta.get("game_phase")
            prev_diff = None
            n_lc = 0
            diffs = []
            for t, _c in zip(ts, cents):
                row = snap_at(actions, index, ts_list, t)
                team_s, opp_s = team_scores(row, team_home)
                if team_s is None:
                    continue
                d = team_s - opp_s
                score_ts.append(t)
                score_vals.append(float(d))
                diffs.append(d)
                if prev_diff is not None and (
                    (prev_diff <= 0 < d) or (prev_diff >= 0 > d)
                ):
                    n_lc += 1
                prev_diff = d
            rec["n_lead_changes_pre80"] = n_lc
            if diffs:
                rec["score_diff_at_80"] = diffs[-1]
                rec["score_diff_at_path_start"] = diffs[0]
                rec["net_score_change_pre80"] = diffs[-1] - diffs[0]
                rec["score_tv"] = float(np.sum(np.abs(np.diff(diffs)))) if len(diffs) > 1 else 0.0
                rec["frac_path_leading"] = float(np.mean(np.array(diffs) > 0))
            if conf in ("HIGH", "MEDIUM") and score_ts:
                rec["game_feature_status"] = "AVAILABLE"
                score_grid[i] = resample_series(score_ts, score_vals)
        else:
            rec["alignment_reason"] = "UNMATCHED" if not nba_id else "NO_TEAM"
        if rec["feature_maximum_source_timestamp"] > entry:
            rec["leakage_flag"] = True
        else:
            rec["leakage_flag"] = False
        rows.append(rec)
    write_parquet(OUT / "path_functionals.parquet", rows)
    np.savez(
        OUT / "arrival_curves.npz",
        full_grid=full_grid,
        from50_grid=from50_grid,
        score_grid=score_grid,
        y=np.array([r["Y_40_CLOSE"] for r in trades], dtype=np.int64),
        allow_pickle=True,
    )
    # raw sequences for DTW
    np.save(OUT / "raw_full_paths.npy", np.array(raw_full, dtype=object), allow_pickle=True)
    n_ok = sum(1 for r in rows if r.get("path_status") == "OK")
    n_50 = sum(1 for r in rows if r.get("from50_status") == "OK")
    n_g = sum(1 for r in rows if r.get("game_feature_status") == "AVAILABLE")
    write_json(
        OUT / "curve_build_summary.json",
        {
            "written_utc": utc_now(),
            "n": n,
            "full_window_ok": n_ok,
            "from50_ok": n_50,
            "game_available": n_g,
            "grid_n": GRID_N,
            "leakage_flags": sum(1 for r in rows if r.get("leakage_flag")),
        },
    )
    print(f"curves full_ok={n_ok} from50_ok={n_50} game={n_g}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
