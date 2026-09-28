#!/usr/bin/env python3
"""Join candle-proxy path (secondary) + TARGET_ONLY labels. No L2. No leakage into Z."""

from __future__ import annotations

from collections import defaultdict

from common import HIT40, OUT, ROOT, e4_to_cents, read_parquet_rows, utc_now, write_json, write_parquet

V1_FEAT = ROOT / "derived" / "nba" / "momento_path_engine_v1" / "features_entry.parquet"
V1_OBS = ROOT / "derived" / "nba" / "momento_path_engine_v1" / "first80_path_observations.parquet"

CANDLE_KEEP = [
    "feat_spread_cents",
    "feat_entry_last_close_cents",
    "feat_entry_volume_hundredths",
    "feat_range_1m_cents",
    "feat_momentum_1m_cents",
    "feat_prior_80_crossings",
    "feat_vol_5m_cents",
    "feat_momentum_5m_cents",
    "feat_mae_15m_cents",
    "feat_mfe_15m_cents",
    "feat_dist_from_15m_high_cents",
    "feat_dist_from_15m_low_cents",
    "feat_up_count_15m",
    "feat_down_count_15m",
    "feat_vol_shock",
]


def main() -> int:
    feats = read_parquet_rows(OUT / "features.parquet")
    v1 = {r["observation_id"]: r for r in read_parquet_rows(V1_FEAT)} if V1_FEAT.exists() else {}
    v1o = {r["observation_id"]: r for r in read_parquet_rows(V1_OBS)} if V1_OBS.exists() else {}
    snaps = {r["observation_id"]: r for r in read_parquet_rows(OUT / "entry_snaps.parquet")}
    poss = read_parquet_rows(OUT / "possessions.parquet")
    mkt = {r["possession_id"]: r for r in read_parquet_rows(OUT / "possession_market.parquet")}
    by_nba = defaultdict(list)
    for p in poss:
        by_nba[p["nba_game_id"]].append(p)
    for lst in by_nba.values():
        lst.sort(key=lambda x: x["possession_sequence"])

    out = []
    for r in feats:
        rec = dict(r)
        oid = r["observation_id"]
        vf = v1.get(oid) or {}
        vo = v1o.get(oid) or {}
        rec["Y_survive_40"] = int(r.get("SURVIVE_40") or 0)
        rec["Y_hit_40"] = int(r.get("Y_40_CLOSE") or 0)
        rec["Y_settle_yes"] = 1 if r.get("expiration_result_yes") else 0
        rec["Y_40_WICK"] = r.get("Y_40_WICK")
        # Candle proxies — secondary, not the primary coordinate system.
        for k in CANDLE_KEEP:
            rec[f"candle_{k}"] = vf.get(k)
        rec["candle_derived_microstructure_proxy"] = True
        rec["candle_not_l2"] = True
        rec["pregame_win_probability"] = None
        rec["team_strength_difference"] = None
        rec["lineup_state"] = None
        rec["order_book_imbalance"] = None
        rec["true_l2_depth"] = None
        rec["availability_pregame"] = "UNAVAILABLE"
        rec["availability_l2"] = "UNAVAILABLE"
        rec["availability_lineup"] = "UNAVAILABLE"
        rec["entry_bid_high_cents"] = e4_to_cents(vo.get("entry_bid_high_e4"))
        rec["entry_bid_low_cents"] = e4_to_cents(vo.get("entry_bid_low_e4"))
        rec["entry_last_close_cents"] = e4_to_cents(vo.get("entry_last_close_e4"))
        rec["entry_volume_hundredths"] = vo.get("entry_volume_hundredths")
        # TARGET_ONLY path-risk from post-entry possessions (not a predictor).
        s = snaps.get(oid) or {}
        entry = int(r["entry_decision_time"])
        plist = by_nba.get(s.get("nba_game_id"), [])
        after = [p for p in plist if p.get("wall_start_ts") is not None and p["wall_start_ts"] > entry]
        bids = []
        stop_i = None
        for i, p in enumerate(after, 1):
            ov = mkt.get(p["possession_id"]) or {}
            b = ov.get("market_bid_after_e4")
            if b is None:
                b = ov.get("market_bid_before_e4")
            if b is not None:
                bids.append(b)
                if stop_i is None and b <= HIT40:
                    stop_i = i
        entry_bid = r.get("mkt_yes_bid_cents")
        min_after = None if not bids else e4_to_cents(min(bids))
        rec["mae_after_entry_cents"] = None if min_after is None or entry_bid is None else min_after - entry_bid
        rec["mae_after_entry_role"] = "TARGET_ONLY"
        rec["possessions_until_stop"] = stop_i
        rec["possessions_until_stop_role"] = "TARGET_ONLY"
        rec["minutes_until_stop"] = r.get("time_to_40_minutes")
        rec["minutes_until_stop_role"] = "TARGET_ONLY"
        rec["minutes_until_stop_resolution"] = "1m_candle"
        out.append(rec)

    write_parquet(OUT / "features_v2.parquet", out)
    avail = [
        {"name": "possession sequence", "status": "OBSERVED"},
        {"name": "period / official clock", "status": "OBSERVED"},
        {"name": "score path", "status": "OBSERVED"},
        {"name": "modeled wall start/end", "status": "DERIVED", "note": "PERIOD_BOUNDED_LINEAR_GAME_CLOCK"},
        {"name": "per-play timeActual", "status": "UNAVAILABLE"},
        {"name": "Kalshi 1m TOB OHLC", "status": "OBSERVED"},
        {"name": "possession-normalized market overlay", "status": "APPROXIMATED", "note": "MULTI_POSSESSION_CANDLE dominant"},
        {"name": "L2 imbalance / queue / depth", "status": "UNAVAILABLE"},
        {"name": "pregame win probability", "status": "UNAVAILABLE"},
        {"name": "lineup state", "status": "UNAVAILABLE"},
        {"name": "maker fill", "status": "UNAVAILABLE", "note": "not a verified fill"},
        {"name": "mae_after_entry / possessions_until_stop", "status": "OBSERVED", "role": "TARGET_ONLY"},
        {"name": "1/5/15m candle windows", "status": "OBSERVED", "role": "SECONDARY_MARKET_SAMPLING_ARTIFACT"},
    ]
    write_json(
        OUT / "feature_availability.json",
        {"written_utc": utc_now(), "n": len(out), "matrix": avail},
    )
    print(f"enriched n={len(out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
