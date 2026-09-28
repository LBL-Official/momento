#!/usr/bin/env python3
"""STEP 4 / 19 — Empty append-only live episode ledger. Do not fabricate rows."""

from __future__ import annotations

import shutil

from common import (
    DIR_LEDGER,
    EPISODES,
    OUT,
    SCHEMA_DIR,
    empty_parquet,
    ensure_dirs,
    provenance,
    write_json,
)

LEDGER_COLUMNS = [
    "episode_id",
    "strategy_version",
    "market_ticker",
    "game_date",
    "team",
    "side",
    "signal_timestamp",
    "signal_price",
    "signal_bid",
    "signal_ask",
    "entry_order_timestamp",
    "entry_order_price",
    "entry_order_size",
    "entry_status",
    "entry_fill_timestamp",
    "entry_fill_price",
    "entry_fill_quantity",
    "remaining_quantity",
    "stop_trigger_timestamp",
    "stop_trigger_price",
    "stop_order_timestamp",
    "stop_order_type",
    "stop_order_price",
    "stop_fill_timestamp",
    "stop_fill_price",
    "stop_fill_quantity",
    "settlement_price",
    "gross_pnl",
    "fees",
    "slippage",
    "net_pnl",
    "max_favorable_price",
    "max_adverse_price",
    "episode_status",
    "data_confidence",
    "gross_pnl_status",
    "fees_status",
    "slippage_status",
    "net_pnl_status",
    "entry_fill_status",
    "stop_fill_status",
    "program_version",
    "source_dataset_version",
    "created_at",
    "assumptions_version",
]


def main() -> int:
    ensure_dirs()
    schema_out = OUT / "schema"
    schema_out.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SCHEMA_DIR / "episode.schema.json", schema_out / "episode.schema.json")
    shutil.copyfile(SCHEMA_DIR / "episode.schema.json", DIR_LEDGER / "episode.schema.json")
    shutil.copyfile(SCHEMA_DIR / "episode_template.json", schema_out / "episode_template.json")
    shutil.copyfile(SCHEMA_DIR / "episode_template.json", DIR_LEDGER / "episode_template.json")
    dest = EPISODES / "_template.json"
    shutil.copyfile(SCHEMA_DIR / "episode_template.json", dest)

    empty_parquet(DIR_LEDGER / "live_episode_ledger.parquet", LEDGER_COLUMNS)
    empty_parquet(OUT / "live_episode_ledger.parquet", LEDGER_COLUMNS)

    write_json(
        DIR_LEDGER / "summary.json",
        {
            **provenance(),
            "n_episodes": 0,
            "n_observed_fills": 0,
            "n_observed_stop_fills": 0,
            "n_observed_fees": 0,
            "waterfall": {
                "signals": {"n": 0, "status": "UNAVAILABLE"},
                "orders_attempted": {"n": 0, "status": "UNAVAILABLE"},
                "orders_filled": {"n": 0, "status": "UNAVAILABLE"},
                "partial_fills": {"n": 0, "status": "UNAVAILABLE"},
                "full_positions": {"n": 0, "status": "UNAVAILABLE"},
                "stop_events": {"n": 0, "status": "UNAVAILABLE"},
                "stop_fills": {"n": 0, "status": "UNAVAILABLE"},
                "settlements": {"n": 0, "status": "UNAVAILABLE"},
            },
            "fabricated": False,
            "live_armed": False,
            "note": "Ledger is empty until a later authorized capture mode records episodes.",
        },
    )
    print("live ledger empty n=0 fabricated=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
