"""Choose the observation dataset for a compiled question.

TRADABLE_YES_BID → kalshi_candles (genuine yes_bid only)
LAST_TRADE_PRINT + polymarket → polymarket_candles
LAST_TRADE_PRINT + kalshi → kalshi_last_trade

Never derive yes_bid from a print. Never treat last trade as a fill.
"""

from __future__ import annotations

import json
from pathlib import Path

from roller.config import RollerConfig
from roller.research_query.availability import LeagueScope, _dataset_exists
from roller.research_query.models import (
    BASIS_LAST_TRADE,
    BASIS_TRADABLE,
    ResearchQuestion,
    Universe,
)
from roller.research_query.sport_family import is_baseball


def universe_observation_basis(universe: Universe) -> str | None:
    """Venue + explicit market-data choice. None when bases conflict."""
    from roller.research_query.models import MARKET_BASIS

    markets = tuple(universe.markets)
    if not markets:
        return BASIS_TRADABLE
    bases = {MARKET_BASIS[m] for m in markets if m in MARKET_BASIS}
    if len(bases) > 1:
        return None
    md = {str(x) for x in universe.market_data}
    if "last_trade" in md:
        return BASIS_LAST_TRADE
    if "polymarket" in markets:
        return BASIS_LAST_TRADE
    baseball = is_baseball_universe(universe)
    if baseball:
        if "candles" in md and "last_trade" not in md:
            return BASIS_TRADABLE
        return BASIS_LAST_TRADE
    if bases:
        return next(iter(bases))
    return BASIS_TRADABLE


def is_baseball_universe(universe: Universe) -> bool:
    return any(is_baseball(x) for x in (*universe.sports, *universe.leagues))


def candle_dataset_name(question: ResearchQuestion) -> str:
    if "polymarket" in question.universe.markets:
        return "polymarket_candles"
    if question.basis() == BASIS_LAST_TRADE:
        return "kalshi_last_trade"
    return "kalshi_candles"


def required_market_dataset(question: ResearchQuestion, scope: LeagueScope) -> str | None:
    if "polymarket" in question.universe.markets:
        return "polymarket_candles"
    if "kalshi" not in question.universe.markets:
        return None
    md = {str(x) for x in question.universe.market_data}
    if "last_trade" in md or (
        is_baseball(scope.sport) and "candles" not in md
    ):
        return "kalshi_last_trade"
    if "candles" in md or not md:
        return "kalshi_candles"
    return "kalshi_last_trade" if is_baseball(scope.sport) else "kalshi_candles"


def genuine_yes_bid_available(
    cfg: RollerConfig,
    sport: str,
    season: str,
) -> bool:
    if not _dataset_exists(cfg, sport, season, "kalshi_candles"):
        return False
    path = cfg.dataset_path(sport, season, "kalshi_candles")
    p = Path(path)
    if p.is_file():
        return p.stat().st_size > 0
    return any(child.is_file() and child.stat().st_size > 0 for child in p.rglob("*"))


def candles_quality_ready(cfg: RollerConfig, sport: str, season: str) -> bool:
    """True only when some candle can pass frozen quality() (volume > 0).

    Does not invent volume. Does not weaken quality().
    """
    if not genuine_yes_bid_available(cfg, sport, season):
        return False
    if not is_baseball(sport):
        return True
    path = cfg.dataset_path(sport, season, "kalshi_candles")
    manifest = Path(path).parent / "dataset_version.json"
    if manifest.is_file():
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        if "candles_quality_ready" in data:
            return bool(data["candles_quality_ready"])
    return _sample_candle_volume_positive(Path(path))


def _sample_candle_volume_positive(path: Path) -> bool:
    import csv

    files = [path] if path.is_file() else sorted(path.rglob("*.csv"))[:3]
    for f in files:
        if not f.is_file():
            continue
        try:
            with f.open("r", encoding="utf-8", newline="") as fh:
                reader = csv.DictReader(fh)
                for i, rec in enumerate(reader):
                    if i >= 200:
                        break
                    raw = rec.get("volume")
                    if raw in (None, ""):
                        continue
                    try:
                        if int(float(raw)) > 0:
                            return True
                    except (TypeError, ValueError):
                        continue
        except OSError:
            continue
    return False
