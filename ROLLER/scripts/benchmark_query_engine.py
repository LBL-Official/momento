#!/usr/bin/env python3
"""Phase 0 / Phase 5 query-engine benchmark. Do not invent timings."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from roller.research_query.compiler import compile_draft
from roller.research_query.entry_engine import crossings, tradable_sequence
from roller.research_query.execute import execute_compiled
from roller.research_query.facts import TradableIndex
from roller.research_query.indexes.bars import rows_from_index
from roller.research_query.indexes.transitions import rows_from_index as transition_rows
from roller.research_query.operations import first_cross


QUERIES = [
    ("first_touch_80_q3", [{"id": "e1", "family": "first_touch", "priceCents": 80, "period": "Q3"}], []),
    ("second_touch_80_q3", [{"id": "e1", "family": "second_touch", "priceCents": 80, "period": "Q3"}], []),
    ("first_touch_60_q2", [{"id": "e1", "family": "first_touch", "priceCents": 60, "period": "Q2"}], []),
    (
        "first_60_and_80",
        [
            {"id": "e1", "family": "first_touch", "priceCents": 60},
            {"id": "e2", "family": "first_touch", "priceCents": 80},
        ],
        [],
    ),
    (
        "first_80_reach_40",
        [{"id": "e1", "family": "first_touch", "priceCents": 80}],
        [{"id": "p1", "kind": "path", "family": "reach", "priceCents": 40}],
    ),
    (
        "first_80_reach_40_recover_80",
        [{"id": "e1", "family": "first_touch", "priceCents": 80}],
        [
            {"id": "p1", "kind": "path", "family": "reach", "priceCents": 40, "sequential": True},
            {"id": "p2", "kind": "path", "family": "recover", "priceCents": 80, "sequential": True},
        ],
    ),
    ("first_touch_80_season", [{"id": "e1", "family": "first_touch", "priceCents": 80}], []),
]


def _universe(league: str) -> dict:
    key = league.strip().upper()
    if key == "NHL":
        raise ValueError("NHL is SOURCE_UNAVAILABLE — skip, do not invent")
    if key == "MLB":
        return {
            "sports": ["baseball"],
            "leagues": ["MLB"],
            "seasons": ["2025-26"],
            "markets": ["kalshi"],
            "marketData": ["last_trade"],
        }
    if key in {"ATP", "WTA"}:
        return {
            "sports": ["tennis"],
            "leagues": [key],
            "seasons": ["2025-26"],
            "markets": ["kalshi"],
            "marketData": ["candles"],
        }
    if key == "WNBA":
        return {
            "sports": ["basketball"],
            "leagues": ["WNBA"],
            "seasons": ["2025"],
            "markets": ["kalshi"],
            "marketData": ["candles"],
        }
    sources = {"NBA": ["nba_api"]}.get(key, [])
    return {
        "sports": ["basketball"],
        "leagues": [key],
        "seasons": ["2025-26"],
        "markets": ["kalshi"],
        "marketData": ["candles"],
        "dataSources": sources,
    }


def _draft(league: str, entries: list, exits: list) -> dict:
    return {
        "universe": _universe(league),
        "entryConditions": entries,
        "exitConditions": exits + [{"id": "t", "kind": "terminal", "family": "both"}],
    }


def bakeoff() -> dict:
    """Representation bake-off. 79,80,80,80,79,80 must be one upward touch."""
    from datetime import datetime, timezone

    bids = [7900, 8000, 8000, 8000, 7900, 8000]
    candles = []
    t0 = datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc)
    for i, bid in enumerate(bids):
        ts = t0.replace(minute=i)
        candles.append(
            {
                "available_at": ts.isoformat().replace("+00:00", "Z"),
                "yes_bid_close": bid,
                "yes_ask_close": bid + 100,
                "volume": 10,
                "ticker": "T-BAKE",
                "internal_game_id": "G-BAKE",
                "is_valid": True,
            }
        )
    bars, skipped = tradable_sequence(candles)
    index = TradableIndex(bars={"T-BAKE": bars}, skipped={"T-BAKE": skipped})
    t_a = time.perf_counter()
    trans = transition_rows(index)
    a_ms = (time.perf_counter() - t_a) * 1000
    t_b = time.perf_counter()
    grid = {}
    for p in range(500, 9600, 100):
        grid[p] = [(b.ts.isoformat(), b.bid) for b in crossings(bars, p)]
    b_ms = (time.perf_counter() - t_b) * 1000
    t_c = time.perf_counter()
    compact = rows_from_index(index)
    c_ms = (time.perf_counter() - t_c) * 1000
    touches_80 = crossings(bars, 8000)
    cross_80 = first_cross(bars, 8000)
    return {
        "series": bids,
        "one_touch_test": {
            "crossings_80": len(touches_80),
            "expected": 2,
            "pass": len(touches_80) == 2,
            "note": "79,80,80,80 is one touch; 79,80 after is the second",
        },
        "A_transitions": {"rows": len(trans), "build_ms": round(a_ms, 3)},
        "B_grid_91": {"prices": len(grid), "build_ms": round(b_ms, 3), "cells": sum(len(v) for v in grid.values())},
        "C_compact_bars": {"rows": len(compact), "build_ms": round(c_ms, 3)},
        "recommendation": "A + compact bars",
        "first_cross_80_bid": None if cross_80 is None else cross_80.bid,
    }


def run_warehouse(leagues: list[str]) -> list[dict]:
    out: list[dict] = []
    for league in leagues:
        for name, entries, exits in QUERIES:
            draft = _draft(league, entries, exits)
            compiled = compile_draft(draft)
            t0 = time.perf_counter()
            env = execute_compiled(compiled)
            elapsed = (time.perf_counter() - t0) * 1000
            perf = env.get("performance") or {}
            out.append(
                {
                    "league": league,
                    "query": name,
                    "execution_status": env.get("execution_status"),
                    "execution_path": (env.get("compile") or {}).get("execution_path"),
                    "population_n": (env.get("summary") or {}).get("population_n"),
                    "total_ms": perf.get("total_ms", round(elapsed)),
                    "dataset_load_ms": perf.get("dataset_load_ms"),
                    "entry_scan_ms": perf.get("entry_scan_ms"),
                    "path_measurement_ms": perf.get("path_measurement_ms"),
                    "execution_mode": perf.get("execution_mode"),
                    "index_version": perf.get("index_version"),
                    "rows_scanned": perf.get("rows_scanned"),
                    "tickers": next(
                        (s.get("tickers") for s in env.get("stages") or [] if s.get("stage") == "universe_loaded"),
                        None,
                    ),
                }
            )
        for cents in (55, 60, 65, 70, 75, 80):
            compiled = compile_draft(
                _draft(league, [{"id": "e1", "family": "first_touch", "priceCents": cents}], [])
            )
            env = execute_compiled(compiled)
            perf = env.get("performance") or {}
            out.append(
                {
                    "league": league,
                    "query": f"price_sweep_{cents}",
                    "population_n": (env.get("summary") or {}).get("population_n"),
                    "total_ms": perf.get("total_ms"),
                    "dataset_load_ms": perf.get("dataset_load_ms"),
                    "execution_mode": perf.get("execution_mode"),
                    "rows_scanned": perf.get("rows_scanned"),
                    "cache_hit_warehouse": perf.get("cache_hit_warehouse"),
                }
            )
        for period in ("Q1", "Q2", "Q3", "Q4"):
            compiled = compile_draft(
                _draft(
                    league,
                    [{"id": "e1", "family": "first_touch", "priceCents": 80, "period": period}],
                    [],
                )
            )
            env = execute_compiled(compiled)
            perf = env.get("performance") or {}
            out.append(
                {
                    "league": league,
                    "query": f"period_sweep_{period}",
                    "population_n": (env.get("summary") or {}).get("population_n"),
                    "total_ms": perf.get("total_ms"),
                    "execution_mode": perf.get("execution_mode"),
                }
            )
        for dest in (35, 40, 45):
            compiled = compile_draft(
                _draft(
                    league,
                    [{"id": "e1", "family": "first_touch", "priceCents": 80}],
                    [{"id": "p1", "kind": "path", "family": "reach", "priceCents": dest}],
                )
            )
            env = execute_compiled(compiled)
            perf = env.get("performance") or {}
            out.append(
                {
                    "league": league,
                    "query": f"reach_{dest}",
                    "population_n": (env.get("summary") or {}).get("population_n"),
                    "total_ms": perf.get("total_ms"),
                    "execution_mode": perf.get("execution_mode"),
                }
            )
    return out


def run_compare(leagues: list[str]) -> list[dict]:
    """Indexed (current optimized) vs reference full-scan. Same draft. Do not invent."""
    from roller.research_query import cache as rq_cache
    from roller.research_query.reference_engine import execute_reference, identities

    out: list[dict] = []
    for league in leagues:
        draft = _draft(league, [{"id": "e1", "family": "first_touch", "priceCents": 80}], [])
        compiled = compile_draft(draft)
        rq_cache.clear()
        t0 = time.perf_counter()
        opt = execute_compiled(compiled)
        opt_ms = (time.perf_counter() - t0) * 1000
        rq_cache.clear()
        t1 = time.perf_counter()
        ref = execute_reference({"draft": draft}, clear_cache=False)
        ref_ms = (time.perf_counter() - t1) * 1000
        row = {
            "league": league,
            "query": "first_touch_80_season",
            "optimized_status": opt.get("execution_status"),
            "reference_status": ref.get("execution_status"),
            "optimized_mode": (opt.get("performance") or {}).get("execution_mode"),
            "reference_mode": (ref.get("performance") or {}).get("execution_mode"),
            "optimized_n": (opt.get("summary") or {}).get("population_n"),
            "reference_n": (ref.get("summary") or {}).get("population_n"),
            "identities_equal": identities(ref) == identities(opt),
            "optimized_total_ms": round((opt.get("performance") or {}).get("total_ms") or opt_ms, 3),
            "reference_total_ms": round((ref.get("performance") or {}).get("total_ms") or ref_ms, 3),
            "optimized_wall_ms": round(opt_ms, 3),
            "reference_wall_ms": round(ref_ms, 3),
            "optimized_load_ms": (opt.get("performance") or {}).get("dataset_load_ms"),
            "reference_load_ms": (ref.get("performance") or {}).get("dataset_load_ms"),
        }
        print(json.dumps(row), file=sys.stderr, flush=True)
        out.append(row)
    return out


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--bakeoff", action="store_true")
    p.add_argument("--warehouse", action="store_true")
    p.add_argument("--compare", action="store_true", help="reference vs indexed")
    p.add_argument("--leagues", default="NBA")
    args = p.parse_args()
    report: dict = {}
    if args.bakeoff or not (args.warehouse or args.compare):
        report["bakeoff"] = bakeoff()
    if args.warehouse:
        report["warehouse"] = run_warehouse([x.strip() for x in args.leagues.split(",") if x.strip()])
    if args.compare:
        report["compare"] = run_compare([x.strip() for x in args.leagues.split(",") if x.strip()])
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
