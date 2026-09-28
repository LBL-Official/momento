#!/usr/bin/env python3
"""Copy Question B numbers from the frozen execution audit. Do not relabel."""

from __future__ import annotations

import sys

from common import AUDIT, OUT, REP, SPEC_DIR, load_json, utc_now, write_json


def block(m):
    if not m:
        return None
    return {
        "n": m.get("trades") or m.get("sample_size"),
        "wins": m.get("wins"),
        "stops": m.get("stops"),
        "win_rate_pct": m.get("win_rate_pct"),
        "win_rate_ci95": m.get("win_rate_ci95"),
        "gross_ev_R": m.get("gross_ev_R"),
        "net_ev_R": m.get("net_ev_R"),
        "maker_fee_on": m.get("maker_fee_on"),
    }


def main() -> int:
    src = AUDIT / "summary.json"
    if not src.exists():
        print(f"missing frozen audit {src}", file=sys.stderr)
        return 1
    audit = load_json(src)
    models = audit.get("models") or {}
    splits = (audit.get("splits") or {}).get("original_baseline") or {}
    cons_splits = (audit.get("splits") or {}).get("conservative_execution") or {}
    port = (audit.get("portfolio") or {}).get("original_baseline") or {}
    board = {
        "written_utc": utc_now(),
        "program": "MOMENTO_NBA_CAPTURE_PROGRAM_V1",
        "source": str(src),
        "source_unmodified": True,
        "relabeled": False,
        "live_execution_changed": False,
        "disclaimer": "This is not a claim that the strategy makes 74%. Prints are not fills.",
        "price_interpretation": audit.get("price_interpretation"),
        "fees": audit.get("fees"),
        "baseline": audit.get("baseline"),
        "fill_confidence_counts": audit.get("fill_confidence_counts"),
        "fill_confidence_rules": audit.get("fill_confidence_rules"),
        "models": {
            "original_close_stop": block(models.get("original_baseline")),
            "high_fill_close_stop": block(models.get("high_fill_close_stop")),
            "all_fills_wick_stop": block(models.get("all_fills_bid_low_stop")),
            "conservative_high_wick": block(models.get("conservative_execution")),
            "original_maker_fee_on": block(models.get("original_baseline_maker_fee_on")),
            "conservative_maker_fee_on": block(models.get("conservative_execution_maker_fee_on")),
        },
        "splits_close_stop": {
            "IN_SAMPLE": block(splits.get("IN_SAMPLE")),
            "VALIDATION": block(splits.get("VALIDATION")),
            "OOS": block(splits.get("OOS")),
        },
        "splits_conservative": {
            "IN_SAMPLE": block(cons_splits.get("IN_SAMPLE")),
            "VALIDATION": block(cons_splits.get("VALIDATION")),
            "OOS": block(cons_splits.get("OOS")),
        },
        "degradation": audit.get("degradation"),
        "portfolio_close_stop": {
            "max_open_unlimited": (port.get("unlimited") or {}).get("max_open_observed"),
            "cap1_accepted": (port.get("1") or {}).get("accepted"),
            "cap1_skipped": (port.get("1") or {}).get("skipped_overlap"),
            "cap5_accepted": (port.get("5") or {}).get("accepted"),
            "cap5_skipped": (port.get("5") or {}).get("skipped_overlap"),
        },
        "leakage": audit.get("leakage"),
        "question_a": {
            "status": "CLOSED_ON_1M_CANDLES",
            "unconditional_q": (audit.get("baseline") or {}).get("stops_40_close"),
            "first80": (audit.get("baseline") or {}).get("first80_settled"),
            "survivors": (audit.get("baseline") or {}).get("survivors_no40"),
            "v1": "C_NO_ROBUST_OOS_FILTER",
            "v2": "C_NO_FILTER",
            "v3": "C_PROXIMITY_REDISCOVERY",
            "v4": "C_NO_ROBUST_CONDITIONAL_STRUCTURE",
            "v4_skip_high_p_val_lift_R": 0.030,
            "v4_skip_high_p_oos_lift_R": 0.008,
        },
        "question_b": {
            "status": "OPEN",
            "fill_at_80": "UNAVAILABLE_AS_OBSERVED_FILL",
            "stop_fill_at_40": "UNAVAILABLE_AS_OBSERVED_FILL",
            "kalshi_fee_model": "UNRESOLVED",
            "fillable_weekly_n": "UNAVAILABLE",
        },
        "research_5pct_scenario": {
            "label": "NOT_LIVE_SIZING",
            "not_mlb_12_5_pct": True,
            "fraction_of_current_equity": 0.05,
            "approx_ev_bankroll_pct_at_74pct": 0.275,
            "approx_ev_bankroll_pct_at_69_3pct": 0.099,
            "fills_for_2pct_week_at_74pct": 2.0 / 0.275,
            "fills_for_2pct_week_at_69_3pct": 2.0 / 0.099,
            "is_forecast": False,
        },
        "spec_docs": str(SPEC_DIR),
    }
    write_json(OUT / "scoreboard.json", board)
    write_json(REP / "scoreboard.json", board)
    print(
        "scoreboard "
        f"first80={board['baseline']['first80_settled']} "
        f"close_stop={board['models']['original_close_stop']['win_rate_pct']} "
        f"conservative={board['models']['conservative_high_wick']['win_rate_pct']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
