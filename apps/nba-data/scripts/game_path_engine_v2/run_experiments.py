#!/usr/bin/env python3
"""Consolidate experiments, freeze ≤1 candidate on VALIDATION, one OOS pass."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

from common import (
    DELTA_Q_TRAIN,
    EV_MARGIN,
    EV_UNCONDITIONAL,
    MIN_ACCEPTANCE_PROD,
    MIN_ACCEPTANCE_RESEARCH,
    MIN_BUCKET_N_TRAIN,
    OUT,
    SPEC_DIR,
    split_rows,
    utc_now,
    write_json,
)
from eval_lib import (
    apply_tree_leaf,
    attach_status,
    experiment_row,
    load_analysis_rows,
)

HYP_DIRECTION = {
    "H|H1": "LOWER",
    "H|H2": "HIGHER",
    "H|H3": "HIGHER",
    "H|H4": "HIGHER",
    "H|H5": "LOWER",
    "H|H6": "HIGHER",
}


def load_exp_file(name: str) -> list[dict]:
    path = OUT / "experiments" / name
    if not path.exists():
        return []
    return json.loads(path.read_text()).get("experiments") or []


def direction_ok(rec: dict) -> bool:
    want = HYP_DIRECTION.get(rec["experiment_id"])
    dq = rec.get("train_delta_q")
    if want is None or dq is None:
        return True
    if want == "LOWER":
        return dq < 0
    if want == "HIGHER":
        return dq > 0
    return True


def choose_candidate(recs: list[dict]) -> str | None:
    """VALIDATION chooses at most one. No OOS peeking."""
    pool = []
    for r in recs:
        if r.get("promotion_status") == "INSUFFICIENT_SAMPLE":
            continue
        if r.get("train_n", 0) < MIN_BUCKET_N_TRAIN:
            continue
        if abs(r.get("train_delta_q") or 0) < DELTA_Q_TRAIN:
            continue
        if not direction_ok(r):
            continue
        vq = r.get("validation_q")
        if vq is None or r.get("validation_n", 0) < 30:
            continue
        if abs(r.get("validation_delta_q") or 0) < 0.02:
            continue
        tsign = (r.get("train_delta_q") or 0) >= 0
        vsign = (r.get("validation_delta_q") or 0) >= 0
        if tsign != vsign:
            continue
        acc = r.get("acceptance_train") or 0
        if acc < MIN_ACCEPTANCE_RESEARCH:
            continue
        # Prefer *lower* q filters (accept this bucket) with EV lift
        if (r.get("validation_delta_ev") or 0) < EV_MARGIN:
            continue
        pool.append(r)
    if not pool:
        return None
    pool.sort(
        key=lambda r: (
            r.get("validation_ev") or -99,
            r.get("validation_n") or 0,
            r.get("acceptance_train") or 0,
        ),
        reverse=True,
    )
    return pool[0]["experiment_id"]


def main() -> int:
    rows = load_analysis_rows()
    train_u = split_rows(rows, "TRAIN", primary_only=True)
    val_u = split_rows(rows, "VALIDATION", primary_only=True)
    oos_u = split_rows(rows, "OOS", primary_only=True)

    recs = []
    recs.extend(load_exp_file("univariate.json"))
    recs.extend(load_exp_file("hypotheses.json"))
    recs.extend(load_exp_file("interactions.json"))

    tree_path = OUT / "models" / "tree_discovery.json"
    if tree_path.exists():
        tree = json.loads(tree_path.read_text())
        med = tree.get("medians") or {}
        for i, leaf in enumerate(tree.get("leaves") or []):
            pfn = leaf.get("pred_fn")
            if not pfn:
                continue

            def sel(rs, pfn=tuple(pfn), med=med):
                return [r for r in rs if apply_tree_leaf(r, pfn, med)]

            recs.append(
                experiment_row(
                    experiment_id=f"TREE|L{i}",
                    hypothesis="Depth-2 discovered leaf",
                    features_used="tree_depth2",
                    bucket_definition=leaf.get("rule") or "",
                    train=sel(train_u),
                    val=sel(val_u),
                    oos=sel(oos_u),
                    universe_train=train_u,
                )
            )

    # Choose using TRAIN+VAL fields only (oos numbers exist but must not drive choice).
    recs_for_choice = []
    for r in recs:
        c = dict(r)
        c["oos_q"] = None
        c["oos_n"] = 0
        recs_for_choice.append(c)
    chosen = choose_candidate(recs_for_choice)

    final = [attach_status(dict(r), chosen) for r in recs]
    # attach_status with oos present will VALIDATE/REJECT the chosen one.

    write_json(
        OUT / "experiments" / "ledger.json",
        {
            "written_utc": utc_now(),
            "n": len(final),
            "chosen_experiment_id": chosen,
            "choice_rule": (
                "VAL only; TRAIN |Δq|≥4pp n≥40; VAL |Δq|≥2pp same sign n≥30; "
                "VAL ΔEV≥0.03R; TRAIN acceptance≥20%. At most one candidate. "
                "OOS is a single frozen pass."
            ),
            "experiments": final,
        },
    )

    # CSV ledger
    spec_csv = SPEC_DIR / "EXPERIMENT_LEDGER.csv"
    fieldnames = [
        "experiment_id",
        "hypothesis",
        "features_used",
        "bucket_definition",
        "train_n",
        "train_q",
        "train_result",
        "validation_n",
        "validation_q",
        "validation_result",
        "oos_n",
        "oos_q",
        "oos_result",
        "effect_size",
        "confidence_interval",
        "economic_EV",
        "promotion_status",
        "notes",
    ]
    out_csv = OUT / "experiments" / "EXPERIMENT_LEDGER.csv"
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in final:
            w.writerow(r)
    spec_csv.parent.mkdir(parents=True, exist_ok=True)
    with spec_csv.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in final:
            w.writerow(r)

    print(f"experiments n={len(final)} chosen={chosen}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
