"""Consecutive tradable transitions. Representation A. Facts, not answers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from roller.research_query.facts import TradableIndex

TRANSITIONS_NAME = "transitions.parquet"


def rows_from_index(index: TradableIndex) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for ticker, bars in index.bars.items():
        skipped = int(index.skipped.get(ticker, 0))
        if len(bars) < 2:
            continue
        prior = bars[0]
        for bar in bars[1:]:
            rows.append(
                {
                    "ticker": ticker,
                    "game_id": bar.game_id,
                    "ts": bar.ts.isoformat().replace("+00:00", "Z"),
                    "prior_e4": int(prior.bid),
                    "current_e4": int(bar.bid),
                    "skipped_untradable": skipped,
                }
            )
            prior = bar
    return rows


def write_transitions(path: Path, index: TradableIndex) -> int:
    rows = rows_from_index(index)
    pd.DataFrame(rows).to_parquet(path, index=False)
    return len(rows)


def read_transitions(path: Path) -> list[dict[str, Any]]:
    df = pd.read_parquet(path)
    return df.to_dict("records") if not df.empty else []
