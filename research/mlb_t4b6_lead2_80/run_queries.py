#!/usr/bin/env python3
"""Execute the two T4–B6 lead≥2 MLB 80-trade drafts.

Generic Confirm & Run only. Does not edit first80.py, compiler, execute, or
load_dataset. Candle path is not a fill. Settlement is Kalshi result.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DRAFTS = (
    "draft_80_40.json",
    "draft_80_55_hold.json",
)


def _measurement(env: dict, name: str) -> dict:
    for row in env.get("measurements") or []:
        if row.get("name") == name:
            return row
    return {}


def compact(env: dict, draft_id: str, elapsed_s: float) -> dict:
    ident = env.get("identity") or {}
    te_scope = ident.get("te_scope") or {}
    funnel = []
    for step in env.get("population") or {} if False else (env.get("population") or {}).get("funnel") or []:
        if isinstance(step, dict):
            funnel.append(step)
        else:
            funnel.append(
                {
                    "condition_id": getattr(step, "condition_id", None),
                    "label": getattr(step, "label", None),
                    "qualifying": getattr(step, "qualifying", None),
                    "population_before": getattr(step, "population_before", None),
                }
            )
    partition = env.get("empirical_partition") or {}
    cells = {}
    for cell in partition.get("cells") or []:
        if isinstance(cell, dict) and cell.get("key"):
            cells[cell["key"]] = cell.get("n")
    return {
        "id": draft_id,
        "execution_status": env.get("execution_status"),
        "observation_basis": env.get("observation_basis"),
        "reference_match": (env.get("compile") or {}).get("reference_match"),
        "execution_path": (env.get("compile") or {}).get("execution_path"),
        "population_n": (env.get("summary") or {}).get("population_n"),
        "te_scope": te_scope,
        "funnel": funnel,
        "path_rate": _measurement(env, "path_rate"),
        "kalshi_yes_rate": _measurement(env, "kalshi_yes_rate"),
        "win_on_n": _measurement(env, "win_on_n"),
        "loss_on_n": _measurement(env, "loss_on_n"),
        "win_exit_rate": _measurement(env, "win_exit_rate"),
        "loss_exit_rate": _measurement(env, "loss_exit_rate"),
        "model_a_8040_ev_cents": _measurement(env, "model_a_8040_ev_cents"),
        "observed_hyp_ev_cents": _measurement(env, "observed_hyp_ev_cents"),
        "empirical_partition": {
            "status": partition.get("status"),
            "n_population": partition.get("n_population"),
            "n_joint_available": partition.get("n_joint_available"),
            "n_missing": partition.get("n_missing"),
            "path_margin": partition.get("path_margin"),
            "cells": cells,
        },
        "base_terminal_efficiency": env.get("base_terminal_efficiency"),
        "hashes": env.get("hashes"),
        "dataset_version": env.get("dataset_version"),
        "provenance": env.get("provenance"),
        "caveats": env.get("caveats"),
        "mlb": env.get("mlb"),
        "elapsed_s": round(elapsed_s, 3),
        "note": "CANDLE PATH ≠ FILL. Settlement is Kalshi result, never box score.",
    }


def main() -> int:
    from roller.research_query.execute import execute_question

    reports = []
    for name in DRAFTS:
        payload = json.loads((ROOT / name).read_text(encoding="utf-8"))
        draft_id = str(payload.get("id") or name)
        t0 = time.perf_counter()
        env = execute_question(payload)
        elapsed = time.perf_counter() - t0
        slim = dict(env)
        pop = dict(slim.get("population") or {})
        trades = pop.get("trades") or []
        pop["trade_count"] = len(trades)
        pop["trades"] = trades[:20]
        pop["rows"] = (pop.get("rows") or [])[:20]
        slim["population"] = pop
        (ROOT / f"result_{Path(name).stem}.json").write_text(
            json.dumps(slim, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        report = compact(env, draft_id, elapsed)
        (ROOT / f"report_{Path(name).stem}.json").write_text(
            json.dumps(report, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        reports.append(report)
        print(json.dumps(report, indent=2, default=str), flush=True)
    (ROOT / "reports.json").write_text(
        json.dumps(reports, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    return 0 if all(r.get("execution_status") == "COMPLETE" for r in reports) else 1


if __name__ == "__main__":
    sys.exit(main())
