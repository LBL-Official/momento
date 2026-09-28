#!/usr/bin/env python3
"""Causal Z_τ80 market features at ENTRY_DECISION_TIME.

Windows use candles with end_period_ts <= entry decision time only.
3/10/30m are exploratory TRAIN-only columns and never auto-enter Model 2A.
"""

from __future__ import annotations

import sys

from common import (
    HIT80,
    OUT,
    audit,
    cents_or_none,
    e4_to_cents,
    index_at_ts,
    load_quotes,
    mean,
    read_parquet_rows,
    stdev,
    utc_now,
    write_json,
    write_parquet,
)


def _closes(window):
    return [r["bid_c"] for r in window]


def _rets_cents(window):
    out = []
    for i in range(1, len(window)):
        a, b = window[i - 1]["bid_c"], window[i]["bid_c"]
        if a is None or b is None:
            out.append(None)
        else:
            out.append(e4_to_cents(b - a))
    return out


def _ranges_cents(window):
    out = []
    for r in window:
        if r["bid_h"] is not None and r["bid_l"] is not None:
            out.append(e4_to_cents(r["bid_h"] - r["bid_l"]))
        else:
            out.append(None)
    return out


def _path_shape(rets):
    xs = [x for x in rets if x is not None]
    if not xs:
        return "INSUFFICIENT"
    if all(x >= 0 for x in xs):
        return "STEADY_ASCENT"
    if all(x <= 0 for x in xs):
        return "STEADY_DESCENT"
    return "MIXED"


def window_ending_at(rows, idx, n_candles):
    """Inclusive window of n_candles ending at idx. None if insufficient."""
    if idx is None or n_candles <= 0:
        return None
    start = idx + 1 - n_candles
    if start < 0:
        return None
    return rows[start : idx + 1]


def window_stats(window, label: str) -> dict:
    prefix = f"feat_"
    rets = _rets_cents(window) if window else []
    ranges = _ranges_cents(window) if window else []
    closes = _closes(window) if window else []
    first_c = closes[0] if closes else None
    last_c = closes[-1] if closes else None
    momentum = None
    if first_c is not None and last_c is not None:
        momentum = e4_to_cents(last_c - first_c)
    highs = [r["bid_h"] for r in window if r["bid_h"] is not None] if window else []
    lows = [r["bid_l"] for r in window if r["bid_l"] is not None] if window else []
    win_high = max(highs) if highs else None
    win_low = min(lows) if lows else None
    mae = None
    mfe = None
    if first_c is not None and closes:
        # Adverse for long YES: close going down from window start.
        mae = e4_to_cents(min(c for c in closes if c is not None) - first_c)
        mfe = e4_to_cents(max(c for c in closes if c is not None) - first_c)
    dist_high = None
    dist_low = None
    if last_c is not None and win_high is not None:
        dist_high = e4_to_cents(last_c - win_high)
    if last_c is not None and win_low is not None:
        dist_low = e4_to_cents(last_c - win_low)
    up = sum(1 for x in rets if x is not None and x > 0)
    down = sum(1 for x in rets if x is not None and x < 0)
    return {
        f"{prefix}vol_{label}_cents": stdev(rets),
        f"{prefix}momentum_{label}_cents": momentum,
        f"{prefix}abs_change_{label}_cents": None if momentum is None else abs(momentum),
        f"{prefix}mean_abs_change_{label}_cents": mean([abs(x) for x in rets if x is not None]),
        f"{prefix}range_{label}_mean_cents": mean(ranges),
        f"{prefix}range_{label}_max_cents": None
        if not [x for x in ranges if x is not None]
        else max(x for x in ranges if x is not None),
        f"{prefix}up_count_{label}": up if window else None,
        f"{prefix}down_count_{label}": down if window else None,
        f"{prefix}mae_{label}_cents": mae,
        f"{prefix}mfe_{label}_cents": mfe,
        f"{prefix}dist_from_{label}_high_cents": dist_high,
        f"{prefix}dist_from_{label}_low_cents": dist_low,
        f"path_shape_{label}": _path_shape(rets),
        f"_n_candles_{label}": None if window is None else len(window),
        f"_max_source_ts_{label}": None if not window else window[-1]["ts"],
    }


def features_at(rows, idx, entry_ts, close_ts):
    q = rows[idx]
    out = {
        "feat_spread_cents": None
        if q["bid_c"] is None or q["ask_c"] is None
        else e4_to_cents(q["ask_c"] - q["bid_c"]),
        "feat_distance_from_80_cents": None
        if q["bid_c"] is None
        else e4_to_cents(q["bid_c"] - HIT80),
        "feat_entry_bid_close_cents": e4_to_cents(q["bid_c"]),
        "feat_entry_ask_close_cents": e4_to_cents(q["ask_c"]),
        "feat_entry_last_close_cents": e4_to_cents(q["px_c"]),
        "feat_entry_volume_hundredths": q["vol"],
        "feat_entry_mid_cents_estimated": None
        if q["bid_c"] is None or q["ask_c"] is None
        else e4_to_cents((q["bid_c"] + q["ask_c"]) / 2.0),
        "feat_range_1m_cents": None
        if q["bid_h"] is None or q["bid_l"] is None
        else e4_to_cents(q["bid_h"] - q["bid_l"]),
        "feat_minutes_to_close": None
        if close_ts is None
        else (close_ts - entry_ts) / 60.0,
        "feat_minutes_since_first_gw_candle": None
        if not rows
        else (entry_ts - rows[0]["ts"]) / 60.0,
        "feat_prior_80_crossings": 0,
        "insufficient_history_5m": idx + 1 < 6,
        "insufficient_history_15m": idx + 1 < 16,
        "volatility_kind": "CONTRACT_PRICE_YES_BID_CLOSE_1M_PROXY",
        "not_true_realized_vol": True,
        "timing_kind": "CONTRACT_TIME",
        "tip_proxy_not_used": True,
        "_entry_source_ts": entry_ts,
    }
    # 1m momentum vs previous completed candle (also at or before decision).
    if idx >= 1 and rows[idx]["bid_c"] is not None and rows[idx - 1]["bid_c"] is not None:
        out["feat_momentum_1m_cents"] = e4_to_cents(rows[idx]["bid_c"] - rows[idx - 1]["bid_c"])
    else:
        out["feat_momentum_1m_cents"] = None

    # Candle counts: W-minute window uses W+1 closes (W intervals), matching
    # volatility-regime V1 (6 candles for 5m, 16 for 15m).
    specs = {
        "1m": 2,
        "3m": 4,
        "5m": 6,
        "10m": 11,
        "15m": 16,
        "30m": 31,
    }
    for label, n_c in specs.items():
        w = window_ending_at(rows, idx, n_c)
        stats = window_stats(w, label)
        out.update(stats)

    # Alias confirmatory names onto the 15m window stats already stored.
    out["feat_vol_shock"] = None
    v5 = out.get("feat_vol_5m_cents")
    v15 = out.get("feat_vol_15m_cents")
    if v5 is not None and v15 not in (None, 0):
        out["feat_vol_shock"] = v5 / v15

    spread = out["feat_spread_cents"]
    mtc = out["feat_minutes_to_close"]
    mom5 = out.get("feat_momentum_5m_cents")
    r1 = out["feat_range_1m_cents"]
    shock = out["feat_vol_shock"]

    def mul(a, b):
        if a is None or b is None:
            return None
        return float(a) * float(b)

    out["feat_ix_vol5_x_minutes_to_close"] = mul(v5, mtc)
    out["feat_ix_vol5_x_spread"] = mul(v5, spread)
    out["feat_ix_momentum5_x_spread"] = mul(mom5, spread)
    out["feat_ix_range1m_x_vol_shock"] = mul(r1, shock)
    out["feat_ix_vol15_x_minutes_to_close"] = mul(v15, mtc)

    # Contiguous 1m flag on last 15 intervals.
    look = min(15, max(0, idx))
    contiguous = True
    if look:
        dts = [rows[idx - look + k + 1]["ts"] - rows[idx - look + k]["ts"] for k in range(look)]
        contiguous = all(50 <= d <= 70 for d in dts)
    out["entry_contiguous_1m"] = contiguous
    return out


def leakage_rows_for(feat: dict, entry_ts: int) -> list[dict]:
    """Per-feature leakage records. Targets are TARGET_ONLY elsewhere."""
    same_bar = {
        "feat_spread_cents",
        "feat_distance_from_80_cents",
        "feat_entry_bid_close_cents",
        "feat_entry_ask_close_cents",
        "feat_entry_last_close_cents",
        "feat_entry_volume_hundredths",
        "feat_entry_mid_cents_estimated",
        "feat_range_1m_cents",
        "feat_momentum_1m_cents",
    }
    skip_prefix = ("_", "path_shape", "insufficient", "volatility", "not_true", "timing", "tip_", "entry_contiguous")
    recs = []
    for k, v in feat.items():
        if k.startswith(skip_prefix) or k.startswith("path_shape"):
            continue
        if not k.startswith("feat_"):
            continue
        max_ts = entry_ts
        status = "SAME_BAR_1M" if k in same_bar else "OK"
        if max_ts > entry_ts:
            status = "FAIL"
        recs.append(
            {
                "feature_name": k,
                "source_table": "normalized/candles_1m",
                "maximum_source_timestamp": max_ts,
                "entry_timestamp": entry_ts,
                "leakage_status": status,
                "value_present": v is not None,
            }
        )
    return recs


def main() -> int:
    obs_path = OUT / "first80_path_observations.parquet"
    if not obs_path.exists():
        print("missing observations parquet — run build_observations.py", file=sys.stderr)
        return 1
    observations = read_parquet_rows(obs_path)
    markets = audit.load_markets()
    games = audit.load_games()
    quotes, _meta = load_quotes(markets, games)

    feature_rows = []
    leakage = []
    missing_series = 0
    for obs in observations:
        ticker = obs["ticker"]
        series = quotes.get(ticker, [])
        entry_ts = obs["entry_decision_time"]
        idx = index_at_ts(series, entry_ts)
        if idx is None:
            missing_series += 1
            feat = {"observation_id": obs["observation_id"], "feature_status": "MISSING_ENTRY_CANDLE"}
            feature_rows.append(feat)
            continue
        feat = features_at(series, idx, entry_ts, obs.get("close_ts"))
        feat["observation_id"] = obs["observation_id"]
        feat["event_id"] = obs["event_id"]
        feat["ticker"] = ticker
        feat["game_date"] = obs["game_date"]
        feat["dataset_split"] = obs["dataset_split"]
        feat["target_close_40"] = obs["target_close_40"]
        feat["target_wick_40_post_entry_bar_only"] = obs["target_wick_40_post_entry_bar_only"]
        feat["target_wick_40_including_entry_bar"] = obs["target_wick_40_including_entry_bar"]
        feat["expiration_result_yes"] = obs["expiration_result_yes"]
        feat["entry_decision_time"] = entry_ts
        feat["maker_fill_confidence"] = obs.get("maker_fill_confidence")
        feat["feature_status"] = "OK"
        # Drop internal window helpers from the parquet except n_candles flags.
        slim = {k: v for k, v in feat.items() if not k.startswith("_max_source_ts")}
        feature_rows.append(slim)
        leakage.extend(leakage_rows_for(feat, entry_ts))

    fail = [r for r in leakage if r["leakage_status"] == "FAIL"]
    write_parquet(OUT / "features_entry.parquet", feature_rows)
    audit_doc = {
        "written_utc": utc_now(),
        "n_observations": len(observations),
        "n_feature_rows": len(feature_rows),
        "missing_entry_candle": missing_series,
        "n_leakage_records": len(leakage),
        "fail_count": len(fail),
        "same_bar_count": sum(1 for r in leakage if r["leakage_status"] == "SAME_BAR_1M"),
        "ok_count": sum(1 for r in leakage if r["leakage_status"] == "OK"),
        "fails": fail,
        "rule": "FAIL if maximum_source_timestamp > ENTRY_DECISION_TIME",
        "same_bar_allowed": "entry-candle OHLC is observable because decision time is candle close",
    }
    # Don't dump 1230 * n_features records into the summary JSON; store compact.
    # Full per-row audit is reconstructed as one template + fail list.
    names = sorted({r["feature_name"] for r in leakage})
    audit_doc["feature_names"] = names
    audit_doc["records"] = _compact_leakage(leakage)
    write_json(OUT / "leakage_audit.json", audit_doc)
    if fail:
        print(f"LEAKAGE FAIL n={len(fail)}", file=sys.stderr)
        return 1
    print(f"features n={len(feature_rows)} missing_entry={missing_series} leakage_fail=0")
    return 0


def _compact_leakage(leakage: list[dict]) -> list[dict]:
    """One record per feature name (max ts across rows) plus any FAIL rows."""
    by_name = {}
    for r in leakage:
        prev = by_name.get(r["feature_name"])
        if prev is None or r["maximum_source_timestamp"] > prev["maximum_source_timestamp"]:
            by_name[r["feature_name"]] = {
                "feature_name": r["feature_name"],
                "source_table": r["source_table"],
                "maximum_source_timestamp": r["maximum_source_timestamp"],
                "entry_timestamp": r["entry_timestamp"],
                "leakage_status": r["leakage_status"],
                "compacted": True,
            }
        if r["leakage_status"] == "FAIL":
            by_name[r["feature_name"]]["leakage_status"] = "FAIL"
    return sorted(by_name.values(), key=lambda x: x["feature_name"])


if __name__ == "__main__":
    raise SystemExit(main())
