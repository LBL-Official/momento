#!/usr/bin/env python3
"""STEP 8 — Pluggable fee architecture. Production model stays UNAVAILABLE."""

from __future__ import annotations

from common import DIR_FEE, ENTRY_CENTS, OUT, STOP_CENTS_GRID, ensure_dirs, provenance, write_json, write_parquet
from fee_models import MODELS, e6_to_cents, get_model


def main() -> int:
    ensure_dirs()
    rows = []
    quotes = []
    for model_id in MODELS:
        model = get_model(model_id)
        for stop in STOP_CENTS_GRID:
            entry = model.calculate_entry_fee(1, ENTRY_CENTS, True)
            exit_q = model.calculate_exit_fee(1, stop, False)
            settle = model.calculate_settlement_fee(1)
            total = model.calculate_total_fee(1, ENTRY_CENTS, stop, True, False, True)
            win_total = model.calculate_total_fee(1, ENTRY_CENTS, None, True, False, True)
            rec = {
                **provenance(),
                "fee_model_id": model_id,
                "fee_model_status": model.status,
                "stop_cents": stop,
                "entry_maker_e6": entry.amount_e6,
                "entry_maker_cents": entry.amount_cents,
                "exit_taker_e6": exit_q.amount_e6,
                "exit_taker_cents": exit_q.amount_cents,
                "settlement_e6": settle.amount_e6,
                "settlement_cents": settle.amount_cents,
                "total_loser_e6": total.amount_e6,
                "total_loser_cents": total.amount_cents,
                "total_winner_e6": win_total.amount_e6,
                "total_winner_cents": win_total.amount_cents,
                "note": total.note,
            }
            rows.append(rec)
            quotes.append(
                {
                    "model_id": model_id,
                    "status": model.status,
                    "stop_cents": stop,
                    "entry": entry.note,
                    "exit": exit_q.note,
                }
            )

    # Frozen-audit checkpoint at 80/40 published schedule
    pub = get_model("PUBLISHED_SCHEDULE_ESTIMATE")
    chk = {
        "maker_entry_80_e6": pub.calculate_entry_fee(1, 80, True).amount_e6,
        "taker_entry_80_e6": pub.calculate_entry_fee(1, 80, False).amount_e6,
        "taker_stop_40_e6": pub.calculate_exit_fee(1, 40, False).amount_e6,
        "expected_maker_entry_80_e6": 2800,
        "expected_taker_entry_80_e6": 11200,
        "expected_taker_stop_40_e6": 16801,
    }
    chk["matches_frozen_audit_e6"] = (
        chk["maker_entry_80_e6"] == 2800
        and chk["taker_entry_80_e6"] == 11200
        and chk["taker_stop_40_e6"] == 16801
    )

    write_parquet(DIR_FEE / "fee_model_matrix.parquet", rows)
    write_parquet(OUT / "fee_model_matrix.parquet", rows)
    write_json(
        DIR_FEE / "summary.json",
        {
            **provenance(),
            "FEE_MODEL_STATUS": "UNRESOLVED",
            "models": {
                mid: {"status": get_model(mid).status} for mid in MODELS
            },
            "observed_production_available": False,
            "audit_checkpoint": chk,
            "e6_to_cents_maker_80": e6_to_cents(2800),
            "quotes": quotes[:8],
        },
    )
    print(
        f"FEE MODEL STATUS UNRESOLVED checkpoint={chk['matches_frozen_audit_e6']} "
        f"rows={len(rows)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
