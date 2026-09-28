#!/usr/bin/env python3
"""STEP 2 — Reproduce 1,230 / 910 / 320 without modifying source research."""

from __future__ import annotations

import sys

from common import (
    AUDIT,
    DIR_BASELINE,
    FROZEN_GROSS_EV_R,
    FROZEN_N,
    FROZEN_P,
    FROZEN_P_BE_GROSS,
    FROZEN_SHA256,
    FROZEN_STOPS_CLOSE,
    FROZEN_SURVIVORS,
    OUT,
    ensure_dirs,
    ev_gross_R,
    load_frozen_ledger,
    load_json,
    provenance,
    reproduce_counts,
    sha256_file,
    write_json,
    write_parquet,
)


def main() -> int:
    ensure_dirs()
    hashes = {
        "summary.json": sha256_file(AUDIT / "summary.json"),
        "ledger_baseline.json": sha256_file(AUDIT / "ledger_baseline.json"),
    }
    for name, expected in (
        ("summary.json", FROZEN_SHA256["summary.json"]),
        ("ledger_baseline.json", FROZEN_SHA256["ledger_baseline.json"]),
    ):
        if hashes[name] != expected:
            print(f"FROZEN HASH MISMATCH {name}", file=sys.stderr)
            return 1

    ledger = load_frozen_ledger()
    counts = reproduce_counts(ledger)
    if not counts["matches_frozen"]:
        print(f"COUNT MISMATCH {counts}", file=sys.stderr)
        return 1

    audit = load_json(AUDIT / "summary.json")
    baseline = audit.get("baseline") or {}
    if (
        baseline.get("first80_settled") != FROZEN_N
        or baseline.get("survivors_no40") != FROZEN_SURVIVORS
        or baseline.get("stops_40_close") != FROZEN_STOPS_CLOSE
    ):
        print("summary.json counts drifted from freeze", file=sys.stderr)
        return 1

    rows = []
    for i, r in enumerate(ledger):
        win = r.get("winner_or_stop") == "WIN"
        rows.append(
            {
                **provenance(),
                "row_index": i,
                "game_id": r.get("game_id"),
                "market_id": r.get("market_id"),
                "market_ticker": r.get("event_ticker"),
                "team": r.get("team"),
                "game_date": r.get("game_date"),
                "dataset_split": r.get("dataset_split"),
                "regime": r.get("regime"),
                "first_80_timestamp": r.get("first_80_timestamp"),
                "path_survivor": bool(win),
                "path_stop_close": bool(r.get("stop_triggered")),
                "path_label_R": 1.0 if win else -2.0,
                "path_label_status": "OBSERVED",
                "path_label_kind": "OBSERVED_CANDLE_PATH",
                "maker_fill_at_80": None,
                "maker_fill_status": "UNAVAILABLE",
                "stop_fill_at_40": None,
                "stop_fill_status": "UNAVAILABLE",
                "gross_pnl_cents_path": 20 if win else -40,
                "entry_price_assumed": r.get("entry_price"),
                "entry_confidence_candle": r.get("entry_confidence"),
                "scenario_source": r.get("scenario"),
            }
        )

    write_parquet(DIR_BASELINE / "historical_path_baseline.parquet", rows)
    write_parquet(OUT / "historical_path_baseline.parquet", rows)

    summary = {
        **provenance(),
        "reproduced": True,
        "source_unmodified": True,
        "source_hashes": hashes,
        "universe": FROZEN_N,
        "survivors": FROZEN_SURVIVORS,
        "close_path_40": FROZEN_STOPS_CLOSE,
        "p_survive": FROZEN_P,
        "p_survive_pct": round(100.0 * FROZEN_P, 4),
        "ev_gross_R": FROZEN_GROSS_EV_R,
        "ev_gross_R_formula": "3p-2",
        "p_be_gross": FROZEN_P_BE_GROSS,
        "check_ev": ev_gross_R(FROZEN_P),
        "interpretation": "HISTORICAL PATH — NOT EXECUTED FILLS",
        "splits_from_audit": (audit.get("splits") or {}).get("original_baseline"),
        "counts": counts,
    }
    write_json(DIR_BASELINE / "summary.json", summary)
    write_json(OUT / "historical_path_baseline.json", summary)
    print(
        f"reproduced {FROZEN_N}/{FROZEN_SURVIVORS}/{FROZEN_STOPS_CLOSE} "
        f"p={100.0 * FROZEN_P:.4f}% EV={FROZEN_GROSS_EV_R:.4f}R"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
