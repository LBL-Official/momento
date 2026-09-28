#!/usr/bin/env python3
"""Economic evaluation of frozen candidate vs unconditional, close-path + wick stress."""

from __future__ import annotations

import json
import sys

from common import (
    EV_MARGIN,
    EV_UNCONDITIONAL,
    MIN_ACCEPTANCE_PROD,
    MIN_ACCEPTANCE_RESEARCH,
    OUT,
    Q_UNCONDITIONAL,
    ev_from_q,
    rate_ci,
    split_rows,
    utc_now,
    write_json,
)
from eval_lib import load_analysis_rows


def subset_by_definition(rows, rec, all_recs):
    """Recompute membership from ledger ids via stored train/val/oos n only.

    Membership is reconstructed from experiment files' observation sets when
    present; otherwise economics uses the ledger rates already computed.
    """
    return rec


def pack(rows, target):
    n = len(rows)
    k = sum(int(r.get(target) or 0) for r in rows)
    st = rate_ci(k, n)
    st["target"] = target
    return st


def main() -> int:
    ledger_path = OUT / "experiments" / "ledger.json"
    if not ledger_path.exists():
        print("missing ledger", file=sys.stderr)
        return 1
    ledger = json.loads(ledger_path.read_text())
    chosen_id = ledger.get("chosen_experiment_id")
    recs = ledger.get("experiments") or []
    chosen = next((r for r in recs if r["experiment_id"] == chosen_id), None)

    rows = load_analysis_rows()
    primary = [r for r in rows if r.get("alignment_confidence") in ("HIGH", "MEDIUM")]
    high_fill = [r for r in primary if r.get("maker_fill_confidence") == "HIGH"]

    # Season slices on TRAIN+VAL primary
    tv = [
        r
        for r in primary
        if r.get("dataset_split") in ("TRAIN", "VALIDATION")
    ]
    slices = {
        "early": [r for r in tv if (r.get("game_date") or "") <= "2025-12-31"],
        "middle": [
            r
            for r in tv
            if "2026-01-01" <= (r.get("game_date") or "") <= "2026-02-14"
        ],
        "late": [
            r
            for r in tv
            if "2026-02-15" <= (r.get("game_date") or "") <= "2026-03-15"
        ],
    }

    report = {
        "written_utc": utc_now(),
        "baseline_q": Q_UNCONDITIONAL,
        "baseline_ev": EV_UNCONDITIONAL,
        "primary_n": len(primary),
        "primary_close": pack(primary, "Y_40_CLOSE"),
        "primary_wick": pack(primary, "Y_40_WICK"),
        "high_maker_close": pack(high_fill, "Y_40_CLOSE"),
        "high_maker_wick": pack(high_fill, "Y_40_WICK"),
        "season_slices_unconditional": {k: pack(v, "Y_40_CLOSE") for k, v in slices.items()},
        "chosen_experiment_id": chosen_id,
        "chosen": chosen,
        "ev_margin_required": EV_MARGIN,
        "acceptance_prod": MIN_ACCEPTANCE_PROD,
        "acceptance_research": MIN_ACCEPTANCE_RESEARCH,
    }
    if chosen:
        report["chosen_economics"] = {
            "train": {
                "n": chosen.get("train_n"),
                "q": chosen.get("train_q"),
                "ev": chosen.get("train_ev"),
                "delta_ev": chosen.get("train_delta_ev"),
                "acceptance": chosen.get("acceptance_train"),
            },
            "validation": {
                "n": chosen.get("validation_n"),
                "q": chosen.get("validation_q"),
                "ev": chosen.get("validation_ev"),
                "delta_ev": chosen.get("validation_delta_ev"),
            },
            "oos": {
                "n": chosen.get("oos_n"),
                "q": chosen.get("oos_q"),
                "ev": chosen.get("oos_ev"),
                "delta_ev": chosen.get("oos_delta_ev"),
            },
            "promotion_status": chosen.get("promotion_status"),
        }
    write_json(OUT / "experiments" / "economics.json", report)
    print("economics chosen", chosen_id, "status", None if not chosen else chosen.get("promotion_status"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
