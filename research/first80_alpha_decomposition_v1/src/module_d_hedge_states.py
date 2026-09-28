"""MODULE D — theoretical opposite-side hedge states from candles. Not fills."""

from __future__ import annotations

import pandas as pd

import config as C
import quotes as Q


def opponent_ticker(games_by_event, rec) -> str | None:
    g = games_by_event.get(rec["event_id"]) or {}
    home = g.get("home_market_ticker")
    away = g.get("away_market_ticker")
    held = rec["ticker"]
    if home and away:
        if held == home:
            return away
        if held == away:
            return home
    return None


def scan_one(held_rows, opp_rows, tau: int, h_e4: int) -> dict:
    hit = Q.first_close_le_after(opp_rows, tau, h_e4)
    mae_adv = Q.max_close_after(held_rows, tau)
    mae_fav_opp = Q.min_close_after(opp_rows, tau)
    # complement at first post-tau tradable pair
    complement = None
    ka_at = None
    kb_at = None
    if hit is not None:
        kb_at = hit["bid_c"]
        for q in held_rows:
            if q["ts"] == hit["ts"] and q["bid_c"] is not None:
                ka_at = q["bid_c"]
                break
        if ka_at is not None and kb_at is not None:
            complement = ka_at + kb_at
    return {
        "reached": hit is not None,
        "ts": None if hit is None else hit["ts"],
        "delay_s": None if hit is None else int(hit["ts"] - tau),
        "opp_bid_e4": None if hit is None else hit["bid_c"],
        "held_bid_at_hit_e4": ka_at,
        "complement_e4": complement,
        "theoretical_lock_if_EA_80": None if hit is None else (hit["bid_c"] / 100.0) < (100 - C.ENTRY_CENTS),
        "max_held_bid_after_e4": mae_adv,
        "min_opp_bid_after_e4": mae_fav_opp,
    }


def run(df80: pd.DataFrame, quotes, games) -> dict:
    games_by_event = {g["event_id"]: g for g in games}
    events = []
    missing_opp = 0
    for rec in df80.to_dict("records"):
        opp = opponent_ticker(games_by_event, rec)
        tau = int(rec["first_80_timestamp"])
        held_rows = quotes.get(rec["ticker"], [])
        if not opp or opp not in quotes:
            missing_opp += 1
            continue
        opp_rows = quotes[opp]
        row = {
            "event_id": rec["event_id"],
            "ticker": rec["ticker"],
            "opponent_ticker": opp,
            "dataset_split": rec["dataset_split"],
            "W": bool(rec["W"]),
            "T40": bool(rec["T40"]),
            "tau": tau,
        }
        for h in C.HEDGE_THRESHOLDS_CENTS:
            s = scan_one(held_rows, opp_rows, tau, int(h * 100))
            for k, v in s.items():
                row[f"h{h}_{k}"] = v
        events.append(row)
    ev = pd.DataFrame(events)
    C.write_parquet(C.DATA / "hedge_state_events.parquet", ev)
    summary_rows = []
    by_h = {}
    for h in C.HEDGE_THRESHOLDS_CENTS:
        col = f"h{h}_reached"
        recs = {}
        for split, g in [("FULL", ev)] + [(s, ev[ev["dataset_split"] == s]) for s in ("TRAIN", "VALIDATION", "OOS")]:
            n = int(len(g))
            k = int(g[col].sum()) if n and col in g else 0
            delays = g.loc[g[col] == True, f"h{h}_delay_s"] if n and col in g else []
            recs[split] = {
                "n": n,
                "k": k,
                "p": None if n == 0 else k / n,
                "median_delay_s": None if not len(delays) else float(pd.Series(delays).median()),
                "p_given_W": None if n == 0 else float(g.loc[g["W"] == True, col].mean()) if int(g["W"].sum()) else None,
                "p_given_not_W": None if n == 0 else float(g.loc[g["W"] == False, col].mean()) if int((~g["W"]).sum()) else None,
                "p_given_T40": None if n == 0 else float(g.loc[g["T40"] == True, col].mean()) if int(g["T40"].sum()) else None,
                "mean_complement_e4": None
                if n == 0
                else float(g.loc[g[col] == True, f"h{h}_complement_e4"].dropna().mean())
                if int(g[col].sum())
                else None,
            }
            summary_rows.append({"threshold_cents": h, "split": split, **recs[split]})
        by_h[h] = recs
    C.write_csv(C.RESULTS / "hedge_state_summary.csv", pd.DataFrame(summary_rows))
    C.write_csv(C.RESULTS / "hedge_threshold_surface.csv", pd.DataFrame(summary_rows))
    C.write_json(
        C.RESULTS / "hedge_state.json",
        {
            "n_events": int(len(ev)),
            "missing_opponent": missing_opp,
            "by_threshold": by_h,
            "evidence_level": "THEORETICAL_HEDGE_STATE / OBSERVED_QUOTED_HEDGE_OPPORTUNITY",
            "not": "EXECUTABLE_HEDGE",
            "note": (
                "Candle yes_bid_close on the opponent ticker is not a fill. "
                "Complementary prices are measured, not assumed to sum to 1.00. "
                "Fees, spread, slippage, and queue are omitted."
            ),
        },
    )
    return {"events": ev, "by_threshold": by_h, "missing_opponent": missing_opp}
