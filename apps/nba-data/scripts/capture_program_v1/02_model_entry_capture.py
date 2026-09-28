#!/usr/bin/env python3
"""STEP 6 — Entry capture scenarios E0–E3. No invented 'correct' fill rate."""

from __future__ import annotations

from common import (
    DIR_FILL,
    FILL_GRID,
    FROZEN_N,
    FROZEN_P,
    OUT,
    PARTIAL_GRID,
    SIGNAL_CAPACITY,
    ensure_dirs,
    provenance,
    write_json,
    write_parquet,
)
from economics import n_required, surface_row


def main() -> int:
    ensure_dirs()
    rows = []
    for pf in FILL_GRID:
        for alpha in PARTIAL_GRID:
            ev = surface_row(FROZEN_P, pf, alpha, 40, "ZERO_FEE_MODEL")
            n_sig = FROZEN_N
            n_fillable = n_sig * pf
            rows.append(
                {
                    **provenance(),
                    **ev,
                    "scenario": "E1_E2",
                    "n_signals": n_sig,
                    "n_fillable": n_fillable,
                    "n_filled_qty_units": n_fillable * alpha,
                    "observation_status": "SIMULATED",
                    "maker_fill_observed": False,
                }
            )

    e0 = surface_row(FROZEN_P, 1.0, 1.0, 40, "ZERO_FEE_MODEL")
    e0.update(
        {
            **provenance(),
            "scenario": "E0_IDEALIZED",
            "n_signals": FROZEN_N,
            "n_fillable": float(FROZEN_N),
            "observation_status": "SIMULATED",
            "note": "Idealized: every FIRST-80 fills at 80. Reproduces path EV only.",
        }
    )
    rows.append(e0)

    e3 = []
    for cap_name, cap in SIGNAL_CAPACITY.items():
        for pf in FILL_GRID:
            accepted = cap["accepted"]
            fillable = accepted * pf
            ev = surface_row(FROZEN_P, pf, 1.0, 40, "ZERO_FEE_MODEL")
            e3.append(
                {
                    **provenance(),
                    **ev,
                    "scenario": "E3_MISSED_AND_CAPACITY",
                    "signal_cap": cap_name,
                    "n_signals_accepted": accepted,
                    "n_signals_skipped": cap["skipped"],
                    "n_fillable": fillable,
                    "max_open_observed": cap["max_open_observed"],
                    "observation_status": "SIMULATED",
                    "capacity_kind": "SIGNAL_CAPACITY_THEN_P_FILL",
                    "not_executable_capital": True,
                }
            )

    write_parquet(DIR_FILL / "fill_assumption_matrix.parquet", rows)
    write_parquet(OUT / "fill_assumption_matrix.parquet", rows)
    write_parquet(DIR_FILL / "missed_signal_matrix.parquet", e3)
    write_json(
        DIR_FILL / "summary.json",
        {
            **provenance(),
            "e0_ev_realized_R": e0["ev_realized_R"],
            "e0_matches_path_ev": abs((e0["ev_realized_R"] or 0) - (3 * FROZEN_P - 2)) < 1e-9,
            "p_fill_grid": FILL_GRID,
            "alpha_grid": PARTIAL_GRID,
            "n_fillable_formula": "N_signals * P_fill",
            "observed_maker_fill_rate": None,
            "observed_maker_fill_status": "UNAVAILABLE",
            "n_required_2pct_at_e0_f5": n_required(0.02, e0["ev_bankroll_frac_at_f"]),
            "label": "SIMULATED_EXECUTION_SCENARIO",
        },
    )
    print(f"entry capture E0 EV_R={e0['ev_realized_R']:.4f} rows={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
