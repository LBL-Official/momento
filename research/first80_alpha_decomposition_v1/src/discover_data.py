#!/usr/bin/env python3
"""Warehouse audit. Writes EXPERIMENT_DATA_AUDIT.md. Does not fit models."""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import AUDIT, BANNER, CANDLES, GPE_V2, NORM, PADE, REPO, ROOT as EXP, WAREHOUSE, write_json  # noqa: E402


def main() -> int:
    cands = json.loads((AUDIT / "candidates.json").read_text())
    first = [c for c in cands if c.get("status") == "FIRST_80" and c.get("expiration_result_yes") is not None]
    n_candles = len(list(CANDLES.rglob("*.parquet")))
    markets = pq.read_table(NORM / "markets" / "markets.parquet")
    games = pq.read_table(NORM / "games" / "nba_games.parquet")
    feat = pq.read_table(GPE_V2 / "features_entry.parquet")
    pade_ok = (PADE / "05_trade_possession_panel.parquet").exists()
    dates = sorted(c["game_date"] for c in first if c.get("game_date"))
    w = sum(1 for c in first if c["expiration_result_yes"])
    t40 = sum(1 for c in first if c.get("stop_close_triggered"))
    lines = [
        "# EXPERIMENT_DATA_AUDIT — FIRST80 alpha decomposition v1",
        "",
        f"> {BANNER}",
        "",
        "Audit completed before scientific tables. FIRST80 and TOUCH40 are **not** redefined.",
        "",
        "## Canonical definition source",
        "",
        "- Code: `apps/nba-data/scripts/nba_80_40_execution_audit.py`",
        "- Artifacts: `warehouse/derived/nba/first80_execution_audit/`",
        "- FIRST80: first tradable `yes_bid_close ≥ 80¢` after a prior tradable close < 80¢, spread ≤ 10¢, game-day window, one per event.",
        "- Primary T40: later tradable `yes_bid_close ≤ 40¢` (`stop_close_triggered`). Wick is secondary.",
        "- Sampling: 1-minute Kalshi yes_bid OHLC. `end_period_ts` is candle end. Intraminute path unknown.",
        "",
        "## Counts (frozen candidates, not recomputed here)",
        "",
        f"- Games in candidates file: {len(cands)}",
        f"- FIRST80 settled: {len(first)}",
        f"- W: {w}  T40: {t40}",
        f"- Date range: {dates[0] if dates else '—'} → {dates[-1] if dates else '—'}",
        f"- Splits: {dict(Counter(c.get('dataset_split') for c in first))}",
        "",
        "## Files",
        "",
        f"- 1m candle parquet files: {n_candles}",
        f"- markets.parquet rows: {markets.num_rows}",
        f"- nba_games.parquet rows: {games.num_rows}",
        f"- Game Path Engine V2 features_entry rows: {feat.num_rows} (causal-at-entry labels; alignment HIGH/MEDIUM/LOW/UNUSABLE)",
        f"- PADE 05 panel present: {pade_ok}",
        "",
        "## Ambiguities (not silently resolved)",
        "",
        "- ADR-0006 (MLB live) uses YES **bid sticky**. This NBA frozen study uses **candle yes_bid_close** tradable cross. They are related but not identical. This experiment uses the NBA frozen audit definition.",
        "- LOSS ∧ ¬T40 can be non-zero if the market skips 40¢ between minute closes. Frozen sample count is an observation, not a continuity proof.",
        "- Game-state features use PERIOD_BOUNDED_LINEAR_GAME_CLOCK; 69 rows lack score/clock (UNUSABLE/unaligned). Matching drops them and counts them.",
        "- PADE panel does not cover every FIRST80 game. Alpha persistence drops unmatched games.",
        "",
        "## Not used as fills",
        "",
        "Candles are not maker fills, not IOC fills, and not L2.",
        "",
        "**LIVE DEPLOYMENT: NOT AUTHORIZED**",
        "",
    ]
    text = "\n".join(lines)
    (EXP / "EXPERIMENT_DATA_AUDIT.md").write_text(text)
    (REPO / "docs" / "research" / "first80_alpha_decomposition_v1").mkdir(parents=True, exist_ok=True)
    (REPO / "docs" / "research" / "first80_alpha_decomposition_v1" / "EXPERIMENT_DATA_AUDIT.md").write_text(text)
    write_json(
        EXP / "data" / "audit_snapshot.json",
        {
            "n_cands": len(cands),
            "n_first80": len(first),
            "n_candles": n_candles,
            "n_markets": markets.num_rows,
            "n_games": games.num_rows,
        },
    )
    print(text)
    return 0


if __name__ == "__main__":
    EXP.joinpath("data").mkdir(parents=True, exist_ok=True)
    raise SystemExit(main())
