#!/usr/bin/env python3
"""Phase 15 warehouse-path benchmark. Records measured times. Does not invent numbers."""

from __future__ import annotations

import argparse
import json
import resource
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

from roller.config import RollerConfig
from roller.research_query.models import (
    EntryCondition,
    EntryOp,
    ExitOutcome,
    PathCondition,
    PathOp,
    ResearchQuestion,
    TerminalOutcome,
    TouchOrdinal,
    Universe,
)
from roller.warehouse.conditional_backtest import (
    compare_backtest_rows,
    run_plan_optimized,
    run_plan_reference,
)
from roller.warehouse.coverage import get_catalog
from roller.warehouse.query_context import clear_context_cache, get_research_context
from roller.warehouse.research_compiler import compile_research

_ORIG_READ = pd.read_parquet
_FILES: list[str] = []


def _tracked_read(*args, **kwargs):
    path = args[0] if args else kwargs.get("path")
    _FILES.append(str(path))
    return _ORIG_READ(*args, **kwargs)


def _rss_mb() -> float:
    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # macOS reports bytes; Linux reports KiB.
    if sys.platform == "darwin":
        return usage / (1024 * 1024)
    return usage / 1024


def _question(
    *,
    date_from: str | None,
    date_to: str | None,
    period: str | None = None,
    and_second: bool = False,
    price_e4: int = 6300,
    game_data: tuple[str, ...] = (),
) -> ResearchQuestion:
    entries = [
        EntryCondition(
            id="e1",
            ordinal=TouchOrdinal.FIRST_TOUCH,
            price_e4=price_e4,
            period=period,
            operation=EntryOp.CROSS,
        )
    ]
    if and_second:
        entries.append(
            EntryCondition(
                id="e2",
                ordinal=TouchOrdinal.FIRST_TOUCH,
                price_e4=7000,
                operation=EntryOp.ABOVE,
            )
        )
    return ResearchQuestion(
        universe=Universe(
            sports=("NBA",),
            leagues=("NBA",),
            seasons=("2025-2026",),
            markets=("kalshi",),
            market_data=("candles",),
            game_data=game_data,
            date_from=date_from,
            date_to=date_to,
        ),
        entry_conditions=tuple(entries),
        path_conditions=(
            PathCondition(id="win", op=PathOp.REACH, price_e4=8700, outcome=ExitOutcome.WIN),
            PathCondition(id="loss", op=PathOp.REACH, price_e4=4100, outcome=ExitOutcome.LOSS),
        ),
        terminal=TerminalOutcome.BOTH,
        requested_dimensions=("HOLD_TO_SETTLEMENT",),
    )


QUERIES = {
    "A_season": lambda: _question(date_from="2025-10-10", date_to="2026-06-13"),
    "B_date": lambda: _question(date_from="2025-10-10", date_to="2025-10-10"),
    "C_period": lambda: _question(date_from="2025-10-10", date_to="2025-10-10", period="Q2", game_data=("pbp",)),
    "D_and": lambda: _question(date_from="2025-10-10", date_to="2025-10-10", and_second=True),
    "E_zero": lambda: _question(date_from="2025-10-10", date_to="2025-10-10", period="Q2", game_data=("pbp",)),
}


def _measure(name: str, question: ResearchQuestion, cfg: RollerConfig, *, skip_reference: bool = False) -> dict:
    _FILES.clear()
    clear_context_cache()
    t0 = time.perf_counter()
    plan = compile_research(question, cfg)
    compile_s = time.perf_counter() - t0
    t1 = time.perf_counter()
    loaded = get_research_context(question, cfg, plan=plan)
    context_s = time.perf_counter() - t1
    files = list(_FILES)
    ctx = loaded.context
    obs_n = 0 if ctx is None else len(ctx.observations)
    pbp_n = 0 if ctx is None else len(ctx.pbp_events)
    games_n = 0 if ctx is None else len(ctx.games)
    months = sorted({Path(p).name for p in files if "month=" in p})
    t2 = time.perf_counter()
    ref = None
    if ctx is not None and plan.status.value == "READY" and not skip_reference:
        ref = run_plan_reference(plan, ctx)
    ref_s = time.perf_counter() - t2
    t3 = time.perf_counter()
    opt = run_plan_optimized(plan, ctx) if ctx is not None and plan.status.value == "READY" else None
    opt_s = time.perf_counter() - t3
    diffs = 0
    if ref is not None and opt is not None:
        diffs = len(compare_backtest_rows(ref, opt))
    scored = ref if ref is not None else opt
    return {
        "query": name,
        "plan_status": plan.status.value,
        "plan_hash": plan.plan_hash,
        "context_status": loaded.status.value,
        "population": 0 if scored is None else scored.population,
        "classification_counts": {} if scored is None else dict(scored.classification_counts),
        "compile_s": round(compile_s, 6),
        "context_s": round(context_s, 6),
        "reference_s": round(ref_s, 6),
        "optimized_s": round(opt_s, 6),
        "execution_s": round(ref_s + opt_s, 6),
        "loaded_games": games_n,
        "loaded_observations": obs_n,
        "loaded_pbp": pbp_n,
        "parquet_files_opened": len(files),
        "month_files": months,
        "difference_count": diffs,
        "peak_rss_mb": round(_rss_mb(), 2),
        "result_hash": "" if scored is None else scored.result_hash,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", default="baseline")
    parser.add_argument("--queries", default="A_season,B_date,C_period,D_and,E_zero")
    parser.add_argument("--out", default="")
    parser.add_argument("--skip-reference", action="store_true")
    args = parser.parse_args()
    cfg = RollerConfig(ROOT)
    pd.read_parquet = _tracked_read  # type: ignore[assignment]
    t_cat = time.perf_counter()
    catalog = get_catalog(cfg)
    catalog_s = time.perf_counter() - t_cat
    rows = []
    for name in [q.strip() for q in args.queries.split(",") if q.strip()]:
        if name not in QUERIES:
            raise SystemExit(f"unknown query {name}")
        print(f"measuring {name}…", file=sys.stderr, flush=True)
        rows.append(_measure(name, QUERIES[name](), cfg, skip_reference=args.skip_reference))
        print(json.dumps(rows[-1], indent=2), file=sys.stderr, flush=True)
    payload = {
        "label": args.label,
        "catalog_s": round(catalog_s, 6),
        "warehouse_version": catalog.warehouse_version,
        "queries": rows,
        "peak_rss_mb": round(_rss_mb(), 2),
    }
    text = json.dumps(payload, indent=2, sort_keys=True)
    print(text)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
