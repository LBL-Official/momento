#!/usr/bin/env python3
"""STEP 10 — Signal capacity vs executable capital capacity."""

from __future__ import annotations

from common import (
    DIR_CAP,
    FILL_GRID,
    FROZEN_N,
    FROZEN_P,
    OUT,
    SIGNAL_CAPACITY,
    WEEKLY_TARGETS,
    ensure_dirs,
    provenance,
    write_json,
    write_parquet,
)
from economics import n_required, surface_row

FRACTIONS = [0.01, 0.02, 0.03, 0.05]


def main() -> int:
    ensure_dirs()
    rows = []
    for cap_name, cap in SIGNAL_CAPACITY.items():
        for pf in FILL_GRID:
            for fee in (
                "ZERO_FEE_MODEL",
                "PUBLISHED_SCHEDULE_ESTIMATE",
                "CUSTOM_STRESS_MODEL",
            ):
                for stop in (40, 38, 35):
                    for f in FRACTIONS:
                        ev = surface_row(FROZEN_P, pf, 1.0, stop, fee, f_alloc=f)
                        n_fillable = cap["accepted"] * pf
                        for target in WEEKLY_TARGETS:
                            n_req = (
                                n_required(target, ev["ev_bankroll_frac_at_f"])
                                if ev["ev_bankroll_frac_at_f"] is not None
                                else None
                            )
                            rows.append(
                                {
                                    **provenance(),
                                    **ev,
                                    "capacity_kind": "SIGNAL_THEN_P_FILL",
                                    "signal_cap": cap_name,
                                    "signals_accepted": cap["accepted"],
                                    "signals_skipped": cap["skipped"],
                                    "max_open_observed": cap["max_open_observed"],
                                    "n_signals": FROZEN_N,
                                    "n_fillable": n_fillable,
                                    "weekly_target": target,
                                    "n_required": n_req,
                                    "fills_cover_target": (
                                        None
                                        if n_req is None
                                        else n_fillable >= n_req
                                    ),
                                    "executable_capital_status": "UNAVAILABLE",
                                    "observation_status": "SIMULATED",
                                    "not_live_fillable": True,
                                }
                            )

    # Identity table at the two headline worlds from the frozen scoreboard
    identity = []
    for label, p in (("path_73_98", FROZEN_P), ("wick_proxy_69_02", 849 / 1230)):
        for pf in FILL_GRID:
            ev = surface_row(p, pf, 1.0, 40, "ZERO_FEE_MODEL", f_alloc=0.05)
            identity.append(
                {
                    **provenance(),
                    "world": label,
                    "p_survive": p,
                    "p_fill": pf,
                    "ev_R": ev["ev_realized_R"],
                    "ev_bankroll_f5": ev["ev_bankroll_frac_at_f"],
                    "n_for_1_5pct": ev["n_for_1_5pct_week"],
                    "n_for_2pct": ev["n_for_2pct_week"],
                    "status": "SIMULATED",
                }
            )

    write_parquet(DIR_CAP / "capacity_simulation.parquet", rows)
    write_parquet(OUT / "capacity_simulation.parquet", rows)
    write_json(
        DIR_CAP / "summary.json",
        {
            **provenance(),
            "signal_capacity": SIGNAL_CAPACITY,
            "signal_vs_executable": {
                "SIGNAL_CAPACITY": "frozen overlap stats",
                "EXECUTABLE_CAPITAL_CAPACITY": "UNAVAILABLE",
            },
            "max_observed_concurrent": 8,
            "identity": identity,
            "note": "Overlap stats are not live fillable capacity.",
        },
    )
    print(f"capacity rows={len(rows)} identity={len(identity)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
