#!/usr/bin/env python3
"""STEP 7 — Stop capture S0–S2. Close-40 and wick-40 stay separate."""

from __future__ import annotations

from common import (
    AUDIT,
    DIR_STOP,
    FROZEN_N,
    FROZEN_P,
    FROZEN_STOPS_CLOSE,
    FROZEN_SURVIVORS,
    OUT,
    STOP_CENTS_GRID,
    ensure_dirs,
    load_json,
    p_break_even,
    provenance,
    write_json,
    write_parquet,
)
from economics import payoff, surface_row


def main() -> int:
    ensure_dirs()
    audit = load_json(AUDIT / "summary.json")
    baseline = audit.get("baseline") or {}
    wick_n = ((baseline.get("p_eventual_win_given_40_low") or {}).get("n_80_to_40")) or 381
    wick_survive = FROZEN_N - wick_n
    wick_p = wick_survive / FROZEN_N

    rows = []
    # S0 historical close-path
    s0 = surface_row(FROZEN_P, 1.0, 1.0, 40, "ZERO_FEE_MODEL")
    s0.update(
        {
            **provenance(),
            "stop_model": "S0_HISTORICAL_CLOSE_PATH",
            "observation_status": "OBSERVED",
            "observation_kind": "OBSERVED_CANDLE_PATH",
            "n": FROZEN_N,
            "survivors": FROZEN_SURVIVORS,
            "stops": FROZEN_STOPS_CLOSE,
            "p_survive_used": FROZEN_P,
            "executable_claim": False,
        }
    )
    rows.append(s0)

    # S1 wick / immediate touch — frozen audit count, still not a fill
    s1 = surface_row(wick_p, 1.0, 1.0, 40, "ZERO_FEE_MODEL")
    s1.update(
        {
            **provenance(),
            "stop_model": "S1_IMMEDIATE_TOUCH_WICK",
            "observation_status": "ESTIMATED",
            "observation_kind": "CANDLE_BID_LOW_PROXY",
            "n": FROZEN_N,
            "survivors": wick_survive,
            "stops": wick_n,
            "p_survive_used": wick_p,
            "executable_claim": False,
        }
    )
    rows.append(s1)

    # S2 simulated stop prints
    for stop in STOP_CENTS_GRID:
        for p_sf in (1.0, 0.9, 0.8, 0.7):
            for fee in (
                "ZERO_FEE_MODEL",
                "PUBLISHED_SCHEDULE_ESTIMATE",
                "CUSTOM_STRESS_MODEL",
            ):
                row = surface_row(FROZEN_P, 1.0, 1.0, stop, fee, p_stop_fill=p_sf)
                pay = payoff(stop, fee)
                row.update(
                    {
                        **provenance(),
                        "stop_model": "S2_EXECUTABLE_STOP_SIMULATION",
                        "observation_status": "SIMULATED",
                        "observation_kind": "SIMULATED_EXECUTION_SCENARIO",
                        "p_be_zero_fee_at_stop": p_break_even(20.0, float(80 - stop)),
                        "w_cents_net": pay.w_cents,
                        "l_cents_net": pay.l_abs_cents,
                        "executable_claim": False,
                    }
                )
                rows.append(row)

    write_parquet(DIR_STOP / "stop_execution_matrix.parquet", rows)
    write_parquet(OUT / "stop_execution_matrix.parquet", rows)
    write_json(
        DIR_STOP / "summary.json",
        {
            **provenance(),
            "s0_close_path": {
                "n": FROZEN_N,
                "survivors": FROZEN_SURVIVORS,
                "stops": FROZEN_STOPS_CLOSE,
                "p": FROZEN_P,
                "status": "OBSERVED_CANDLE_PATH",
            },
            "s1_wick": {
                "n": FROZEN_N,
                "stops_bid_low": wick_n,
                "survivors": wick_survive,
                "p": wick_p,
                "status": "ESTIMATED_CANDLE_PROXY",
            },
            "s2": {
                "stop_cents": STOP_CENTS_GRID,
                "status": "SIMULATED_EXECUTION_SCENARIO",
                "executable_claim": False,
            },
            "observed_stop_fill_price_distribution": None,
            "observed_stop_fill_status": "UNAVAILABLE",
        },
    )
    print(f"stop models S0 p={FROZEN_P:.4f} S1 p={wick_p:.4f} rows={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
