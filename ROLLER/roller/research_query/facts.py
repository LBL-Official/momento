"""Atomic tradable-bar index. Facts, not precomputed questions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from roller.research_query.entry_engine import TradableBar, observation_sequence
from roller.research_query.models import BASIS_TRADABLE


@dataclass
class TradableIndex:
    """One quality() pass per ticker. Crossings stay query-time."""

    bars: dict[str, list[TradableBar]] = field(default_factory=dict)
    skipped: dict[str, int] = field(default_factory=dict)
    basis: str = BASIS_TRADABLE

    def precomputed(self, ticker: str) -> tuple[list[TradableBar], int]:
        return self.bars.get(ticker, []), int(self.skipped.get(ticker, 0))

    @classmethod
    def build(
        cls,
        ticker_payloads: dict[str, list[dict[str, Any]]],
        *,
        basis: str = BASIS_TRADABLE,
    ) -> TradableIndex:
        bars: dict[str, list[TradableBar]] = {}
        skipped: dict[str, int] = {}
        for ticker, candles in ticker_payloads.items():
            seq, skip = observation_sequence(candles, basis=basis)
            bars[ticker] = seq
            skipped[ticker] = skip
        return cls(bars=bars, skipped=skipped, basis=basis)
