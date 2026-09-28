"""Independent NBA warehouse evaluator.

Reconstructs a ResearchQuestion against the frozen warehouse and runs the
reference ConditionalBacktest engine.

Does not import roller.warehouse.frontend_contract.
Does not treat production JSON as expected values.
Does not reimplement CROSS / BREAK.
Does not use Confirm & Run execute.py.
"""

from __future__ import annotations

import time
from typing import Any

from roller.config import RollerConfig
from roller.research_query.models import ResearchQuestion
from roller.warehouse.conditional_backtest import run_plan
from roller.warehouse.query_context import get_research_context
from roller.warehouse.research_compiler import compile_research


def evaluate_question(question: ResearchQuestion, cfg: RollerConfig | None = None) -> dict[str, Any]:
    cfg = cfg or RollerConfig()
    t0 = time.perf_counter()
    plan = compile_research(question, cfg)
    t_compile = time.perf_counter()
    loaded = get_research_context(question, cfg, plan=plan)
    t_context = time.perf_counter()
    result = run_plan(plan, loaded.context, engine_id="reference") if loaded.context is not None else None
    t_end = time.perf_counter()
    coverage = dict(getattr(loaded, "coverage", {}) or {})
    load_stats = loaded.load_stats.to_dict() if getattr(loaded, "load_stats", None) else {}
    if result is None:
        return {
            "status": loaded.status.value if hasattr(loaded.status, "value") else str(loaded.status),
            "population": 0,
            "rows": [],
            "classification": {},
            "plan_hash": plan.plan_hash,
            "result_hash": None,
            "timings_s": {
                "compile": t_compile - t0,
                "context": t_context - t_compile,
                "backtest": 0.0,
                "evaluator": t_end - t0,
            },
            "coverage": coverage,
        }
    return {
        "status": result.status.value,
        "population": result.population,
        "rows": [r.to_dict() for r in result.rows],
        "classification": dict(result.classification_counts),
        "plan_hash": result.plan_hash,
        "result_hash": result.result_hash,
        "aggregates": {
            "W": int(result.classification_counts.get("WIN", 0)),
            "L": int(result.classification_counts.get("LOSS", 0)),
        },
        "timings_s": {
            "compile": t_compile - t0,
            "context": t_context - t_compile,
            "backtest": t_end - t_context,
            "evaluator": t_end - t0,
        },
        "coverage": coverage,
        "obs_rows": load_stats.get("observation_rows_read"),
        "pbp_rows": load_stats.get("pbp_rows_read"),
        "months": load_stats.get("observation_months"),
        "load_stats": load_stats,
        "source": "independent_reference",
    }


def compare_production(production: dict[str, Any], expected: dict[str, Any]) -> dict[str, Any]:
    prod_result = production.get("result") if isinstance(production.get("result"), dict) else {}
    contract = production.get("results_contract") if isinstance(production.get("results_contract"), dict) else {}
    prod_rows = contract.get("audit_rows") or prod_result.get("rows") or []
    exp_rows = expected.get("rows") or []

    def _key(row: dict[str, Any]) -> tuple:
        return (
            str(row.get("internal_game_id") or ""),
            str(row.get("market_id") or ""),
            str(row.get("entry_timestamp") or ""),
        )

    prod_sorted = sorted([r for r in prod_rows if isinstance(r, dict)], key=_key)
    exp_sorted = sorted([r for r in exp_rows if isinstance(r, dict)], key=_key)
    fields = (
        "internal_game_id",
        "market_id",
        "entry_timestamp",
        "entry_value",
        "entry_operation",
        "win_exit_timestamp",
        "win_exit_value",
        "loss_exit_timestamp",
        "loss_exit_value",
        "classification",
        "settlement_status",
        "settlement_value",
    )
    diffs: list[dict[str, Any]] = []
    if len(prod_sorted) != len(exp_sorted):
        diffs.append({"field": "population_len", "production": len(prod_sorted), "expected": len(exp_sorted)})
    for i, (a, b) in enumerate(zip(prod_sorted, exp_sorted)):
        for field in fields:
            if a.get(field) != b.get(field):
                diffs.append({"index": i, "field": field, "production": a.get(field), "expected": b.get(field)})
    prod_n = contract.get("population")
    if prod_n is None:
        prod_n = prod_result.get("population")
    prod_hash = (contract.get("reproducibility") or {}).get("result_hash") or prod_result.get("result_hash")
    if int(prod_n or 0) != int(expected.get("population") or 0):
        diffs.append({"field": "population", "production": prod_n, "expected": expected.get("population")})
    if prod_hash != expected.get("result_hash"):
        diffs.append({"field": "result_hash", "production": prod_hash, "expected": expected.get("result_hash")})
    prod_class = contract.get("classification") or prod_result.get("classification_counts") or {}
    if dict(prod_class) != dict(expected.get("classification") or {}):
        diffs.append({"field": "classification", "production": prod_class, "expected": expected.get("classification")})
    return {
        "difference_count": len(diffs),
        "differences": diffs,
        "exact": len(diffs) == 0,
    }
