#!/usr/bin/env python3
"""STEP 5 / 9 — Historical-versus-executable separation and EV surface."""

from __future__ import annotations

from common import (
    DIR_EXEC,
    FILL_GRID,
    OUT,
    PARTIAL_GRID,
    STOP_CENTS_GRID,
    SURVIVAL_GRID,
    ensure_dirs,
    provenance,
    write_json,
    write_parquet,
)
from economics import surface_row

FEE_GRID = [
    "ZERO_FEE_MODEL",
    "PUBLISHED_SCHEDULE_ESTIMATE",
    "CUSTOM_STRESS_MODEL",
]


def main() -> int:
    ensure_dirs()
    catalog = [
        {
            "scenario_id": "E0",
            "family": "ENTRY",
            "name": "Idealized fill at 80",
            "status": "SIMULATED",
            "note": "Reproduces historical path economics only. Not a fill.",
        },
        {
            "scenario_id": "E1",
            "family": "ENTRY",
            "name": "Parameterized P_fill",
            "status": "SIMULATED",
            "note": "P_fill in {1.0,0.9,0.8,0.7,0.6,0.5}. No 'correct' value.",
        },
        {
            "scenario_id": "E2",
            "family": "ENTRY",
            "name": "Partial fills",
            "status": "SIMULATED",
            "note": "alpha in {0.25,0.50,0.75,1.00}. Capacity uses filled qty.",
        },
        {
            "scenario_id": "E3",
            "family": "ENTRY",
            "name": "Missed signals",
            "status": "SIMULATED",
            "note": "N_fillable = N_signals * P_fill. Not deployable capital.",
        },
        {
            "scenario_id": "S0",
            "family": "STOP",
            "name": "Historical close-path",
            "status": "OBSERVED",
            "note": "yes_bid_close <= 40. Historical label only.",
        },
        {
            "scenario_id": "S1",
            "family": "STOP",
            "name": "Immediate touch / wick",
            "status": "ESTIMATED",
            "note": "yes_bid_low <= 40. Not an executable 40.00 fill.",
        },
        {
            "scenario_id": "S2",
            "family": "STOP",
            "name": "Executable stop simulation",
            "status": "SIMULATED",
            "note": "Stop prints {40,39,38,35,30}. SIMULATED_EXECUTION_SCENARIO.",
        },
    ]

    rows = []
    for p in SURVIVAL_GRID:
        for pf in FILL_GRID:
            for alpha in PARTIAL_GRID:
                for stop in STOP_CENTS_GRID:
                    for fee in FEE_GRID:
                        row = surface_row(p, pf, alpha, stop, fee)
                        row.update(provenance())
                        rows.append(row)

    unavailable = surface_row(0.7398, 1.0, 1.0, 40, "OBSERVED_PRODUCTION_MODEL")
    unavailable.update(provenance())
    unavailable["note"] = "Fee model UNAVAILABLE; EV not computed as observed."
    rows.append(unavailable)

    n_a = sum(1 for r in rows if r.get("region") == "REGION_A_ROBUSTLY_PROFITABLE")
    n_b = sum(1 for r in rows if r.get("region") == "REGION_B_EXECUTION_SENSITIVE")
    n_c = sum(1 for r in rows if r.get("region") == "REGION_C_UNPROFITABLE")

    write_parquet(DIR_EXEC / "execution_scenario_matrix.parquet", rows)
    write_parquet(OUT / "execution_scenario_matrix.parquet", rows)
    write_json(
        DIR_EXEC / "catalog.json",
        {
            **provenance(),
            "catalog": catalog,
            "n_rows": len(rows),
            "region_counts": {
                "A_robust": n_a,
                "B_sensitive": n_b,
                "C_unprofitable": n_c,
            },
            "grids": {
                "survival": SURVIVAL_GRID,
                "fill": FILL_GRID,
                "partial": PARTIAL_GRID,
                "stop_cents": STOP_CENTS_GRID,
                "fee": FEE_GRID + ["OBSERVED_PRODUCTION_MODEL"],
            },
            "label": "SIMULATED_EXECUTION_SCENARIO",
            "is_forecast": False,
        },
    )
    print(f"execution surface rows={len(rows)} A={n_a} B={n_b} C={n_c}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
