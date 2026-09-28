#!/usr/bin/env python3
"""Warehouse census + Increment 1 benchmark matrix. Does not change FIRST80."""

from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from roller.config import RollerConfig
from roller.research.quality import quality
from roller.research_query.compiler import compile_draft
from roller.research_query.dataset_version import dataset_fingerprint
from roller.research_query.execute import _load_warehouse, execute_compiled
from roller.research_query.hashing import CODE_VERSION, question_hash
from roller.research_query.identity import identity_holds


def _int(v):
    if v in (None, ""):
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def census_sport(cfg: RollerConfig, sport: str, season: str) -> dict:
    from roller.admin import load_dataset

    out = {
        "sport": sport,
        "season": season,
        "games": 0,
        "markets": 0,
        "tickers": 0,
        "candle_rows": 0,
        "tradable_candles": 0,
        "untradable_candles": 0,
        "missing_internal_game_id": 0,
        "missing_settlement": 0,
        "pbp_games": 0,
        "candle_games": 0,
        "pbp_minus_candle_games": 0,
        "candle_minus_pbp_games": 0,
    }
    try:
        games = load_dataset(cfg, sport, season, "games")
        out["games"] = 0 if games is None or games.empty else int(len(games))
    except (FileNotFoundError, KeyError):
        games = None
    try:
        markets = load_dataset(cfg, sport, season, "kalshi_markets")
    except (FileNotFoundError, KeyError):
        markets = None
    try:
        candles = load_dataset(cfg, sport, season, "kalshi_candles")
    except (FileNotFoundError, KeyError):
        candles = None
    try:
        pbp = load_dataset(cfg, sport, season, "pbp")
    except (FileNotFoundError, KeyError):
        pbp = None

    if markets is not None and not markets.empty:
        out["markets"] = int(len(markets))
        missing = 0
        for rec in markets.to_dict("records"):
            result = str(rec.get("result") or rec.get("kalshi_result") or "").lower()
            sv = rec.get("settlement_value_e4")
            if result not in ("yes", "no") and sv not in (0, 10000, "0", "10000"):
                missing += 1
        out["missing_settlement"] = missing

    candle_games: set[str] = set()
    tickers: set[str] = set()
    if candles is not None and not candles.empty:
        out["candle_rows"] = int(len(candles))
        had_q: dict[str, bool] = defaultdict(bool)
        for rec in candles.to_dict("records"):
            t = str(rec.get("ticker") or "")
            tickers.add(t)
            gid = str(rec.get("internal_game_id") or "")
            if not gid:
                out["missing_internal_game_id"] += 1
            else:
                candle_games.add(gid)
            bid = _int(rec.get("yes_bid_close"))
            ask = _int(rec.get("yes_ask_close"))
            vol = _int(rec.get("volume"))
            valid = rec.get("is_valid")
            if valid in (False, 0, "0", "false", "False"):
                out["untradable_candles"] += 1
                continue
            if quality(bid, ask, vol, had_q[t]) and bid is not None and ask is not None:
                out["tradable_candles"] += 1
                had_q[t] = True
            else:
                out["untradable_candles"] += 1
    out["tickers"] = len(tickers)
    out["candle_games"] = len(candle_games)

    pbp_games: set[str] = set()
    if pbp is not None and not pbp.empty:
        for rec in pbp.to_dict("records"):
            gid = str(rec.get("internal_game_id") or "")
            if gid:
                pbp_games.add(gid)
    out["pbp_games"] = len(pbp_games)
    out["pbp_minus_candle_games"] = len(pbp_games - candle_games)
    out["candle_minus_pbp_games"] = len(candle_games - pbp_games)
    return out


def _nba_universe() -> dict:
    return {
        "sports": ["basketball"],
        "leagues": ["NBA"],
        "seasons": ["2025-26"],
        "markets": ["kalshi"],
        "marketData": ["candles"],
        "dataSources": ["nba_api"],
    }


def matrix_drafts() -> list[tuple[str, dict, bool]]:
    u = _nba_universe()
    return [
        (
            "FIRST80_frozen",
            {
                "universe": u,
                "entryConditions": [
                    {"id": "e1", "family": "first_touch", "priceCents": 80, "period": "Q3"}
                ],
                "exitConditions": [
                    {"id": "p1", "kind": "path", "family": "reach", "priceCents": 40},
                    {"id": "t", "kind": "terminal", "family": "both"},
                ],
            },
            True,
        ),
        (
            "second_touch_80",
            {
                "universe": u,
                "entryConditions": [
                    {"id": "e1", "family": "second_touch", "priceCents": 80}
                ],
                "exitConditions": [{"id": "t", "kind": "terminal", "family": "both"}],
            },
            False,
        ),
        (
            "first_60_q2",
            {
                "universe": u,
                "entryConditions": [
                    {"id": "e1", "family": "first_touch", "priceCents": 60, "period": "Q2"}
                ],
                "exitConditions": [{"id": "t", "kind": "terminal", "family": "both"}],
            },
            False,
        ),
        (
            "sequential_40_recover_80",
            {
                "universe": u,
                "entryConditions": [
                    {"id": "e1", "family": "first_touch", "priceCents": 80}
                ],
                "exitConditions": [
                    {"id": "p1", "kind": "path", "family": "reach", "priceCents": 40, "sequential": True},
                    {"id": "p2", "kind": "path", "family": "recover", "priceCents": 80, "sequential": True},
                    {"id": "t", "kind": "terminal", "family": "both"},
                ],
            },
            False,
        ),
        (
            "layered_and",
            {
                "universe": u,
                "entryConditions": [
                    {"id": "e1", "family": "first_touch", "priceCents": 80, "period": "Q3"},
                    {"id": "e2", "family": "first_touch", "priceCents": 60},
                ],
                "exitConditions": [{"id": "t", "kind": "terminal", "family": "both"}],
            },
            False,
        ),
    ]


def summarize_query(name: str, compiled, out: dict, elapsed_ms: int) -> dict:
    ident = out.get("identity") or {}
    part = out.get("empirical_partition") or {}
    cells = {c.get("key"): c.get("n") for c in (part.get("cells") or []) if isinstance(c, dict)}
    diag = (out.get("provenance") or {}).get("diagnostics") or {}
    return {
        "query_id": name,
        "status": out.get("execution_status"),
        "execution_path": (out.get("compile") or {}).get("execution_path"),
        "reference_match": (out.get("compile") or {}).get("reference_match"),
        "question_hash": question_hash(compiled.question),
        "code_version": CODE_VERSION,
        "dataset_version": out.get("dataset_version"),
        "population_n": (out.get("summary") or {}).get("population_n"),
        "funnel": (out.get("population") or {}).get("funnel") or [],
        "identity": ident,
        "identity_holds": identity_holds(ident) if ident else None,
        "partition": cells,
        "n_joint_available": part.get("n_joint_available"),
        "terminal_missing": part.get("n_missing"),
        "diagnostics": {
            "skipped_untradable": diag.get("skipped_untradable"),
            "crossings_found": diag.get("crossings_found"),
            "aligned": diag.get("aligned"),
            "unaligned": diag.get("unaligned"),
            "ambiguous": diag.get("ambiguous"),
            "modeled": diag.get("modeled"),
            "tie_same_minute_excluded": diag.get("tie_same_minute_excluded"),
        },
        "performance": out.get("performance") or {"total_ms": elapsed_ms},
        "stages": out.get("stages") or [],
        "hashes": out.get("hashes") or {},
    }


def main() -> int:
    cfg = RollerConfig()
    t0 = time.perf_counter()
    census = [
        census_sport(cfg, "NBA", "2025-2026"),
        census_sport(cfg, "NCAAB", "2025-2026"),
    ]
    print("CENSUS", json.dumps(census, indent=2))

    goldens: list[dict] = []
    # Load NBA warehouse once for generic queries.
    probe = compile_draft(matrix_drafts()[1][1])
    load_t = time.perf_counter()
    payloads = _load_warehouse(cfg, probe.question)
    load_ms = int(round((time.perf_counter() - load_t) * 1000))
    print(f"WAREHOUSE_LOAD_MS {load_ms} tickers={len(payloads[0])}")

    for name, draft, frozen in matrix_drafts():
        compiled = compile_draft(draft)
        started = time.perf_counter()
        if frozen:
            out = execute_compiled(compiled, cfg=cfg)
        else:
            out = execute_compiled(
                compiled,
                cfg=cfg,
                ticker_payloads=payloads[0],
                pbp_by_game=payloads[1],
                markets_by_ticker=payloads[2],
                games=payloads[3],
            )
        elapsed = int(round((time.perf_counter() - started) * 1000))
        if not frozen:
            out.setdefault("performance", {})
            out["performance"].setdefault("dataset_load_ms", 0)
            # Shared load is reported separately; keep per-query scan time honest.
        row = summarize_query(name, compiled, out, elapsed)
        row["wall_ms"] = elapsed
        row["shared_warehouse_load_ms"] = None if frozen else load_ms
        row["dataset_version"] = row["dataset_version"] or dataset_fingerprint(
            compiled.question, cfg=cfg
        )
        goldens.append(row)
        print(f"QUERY {name} n={row['population_n']} path={row['execution_path']} ms={elapsed}")

    out_dir = ROOT / "reports" / "research_query"
    out_dir.mkdir(parents=True, exist_ok=True)
    golden_path = ROOT / "tests" / "fixtures" / "research_query_increment1_goldens.json"
    golden_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "code_version": CODE_VERSION,
        "census": census,
        "shared_warehouse_load_ms": load_ms,
        "queries": goldens,
    }
    golden_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Warehouse adversarial audit",
        "",
        "Generated by `scripts/research_query_warehouse_audit.py`.",
        "Semantics unchanged. FIRST80 frozen executor not modified.",
        "",
        f"Code version: `{CODE_VERSION}`",
        f"Shared NBA warehouse load: **{load_ms} ms**",
        "",
        "## Census",
        "",
        "| Sport | Season | Games | Markets | Tickers | Tradable candles | Untradable | Missing settlement | PBP games | Candle games | PBP\\\\candle | Candle\\\\PBP |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for c in census:
        lines.append(
            f"| {c['sport']} | {c['season']} | {c['games']} | {c['markets']} | {c['tickers']} | "
            f"{c['tradable_candles']} | {c['untradable_candles']} | {c['missing_settlement']} | "
            f"{c['pbp_games']} | {c['candle_games']} | {c['pbp_minus_candle_games']} | "
            f"{c['candle_minus_pbp_games']} |"
        )
    lines += [
        "",
        "## Benchmark matrix",
        "",
        "| Query | Path | N | Entry eligible | Ties | Unaligned | Terminal missing | Load ms | Entry ms | Path ms | Total ms | Identity |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for q in goldens:
        ident = q.get("identity") or {}
        ex = ident.get("exclusions") or {}
        perf = q.get("performance") or {}
        lines.append(
            f"| {q['query_id']} | {q['execution_path']} | {q['population_n']} | "
            f"{ident.get('entry_eligible')} | {ex.get('tie_same_minute')} | "
            f"{(q.get('diagnostics') or {}).get('unaligned')} | {q.get('terminal_missing')} | "
            f"{perf.get('dataset_load_ms')} | {perf.get('entry_scan_ms')} | "
            f"{perf.get('path_measurement_ms')} | {perf.get('total_ms', q.get('wall_ms'))} | "
            f"{q.get('identity_holds')} |"
        )
    lines += [
        "",
        "## Structural notes",
        "",
        "- Generic queries reuse one NBA warehouse load in this script; per-query",
        "  `dataset_load_ms` is 0 when payloads are injected. Interactive RUN still loads every time.",
        "- `and_intersection_drop` is the first-condition set minus ticker intersection.",
        "- Terminal YES/NO is a measurement filter; entry N is disclosed in `identity`.",
        "",
        f"Goldens written to `{golden_path.relative_to(ROOT)}`.",
        f"Elapsed wall: {int(round((time.perf_counter() - t0) * 1000))} ms.",
        "",
    ]
    report = out_dir / "WAREHOUSE_ADVERSARIAL_AUDIT.md"
    report.write_text("\n".join(lines), encoding="utf-8")
    print(f"WROTE {report}")
    print(f"WROTE {golden_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
