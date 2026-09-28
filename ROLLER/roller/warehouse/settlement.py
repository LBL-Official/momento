"""Project NBA Kalshi settlements into warehouse_v0. Phase 6.

Authoritative source is Suite markets.parquet (kalshi_rest).
internal_game_id comes only from GameMarketLink.

Never derive YES/NO from score, PBP, candles, last trade, or price.
MISSING is not NO. scalar is INVALID.

Not used by execute / compile_draft / load_dataset / official_settlement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from roller.canonical.markets import markets_parquet
from roller.config import RollerConfig
from roller.ingest.games import load_sport_games
from roller.io_csv import sha256_file, write_json
from roller.timeutil import now_utc_iso
from roller.warehouse.entities import Settlement, SettlementResult, kalshi_result_to_settlement
from roller.warehouse.layout_v0 import (
    settlements_manifest_path,
    settlements_parquet_path,
    warehouse_v0_readme_path,
    warehouse_v0_root,
)
from roller.warehouse.market_link import load_nba_crosswalk

PHASE6_SPORT = "NBA"
SETTLEMENT_SOURCE = "kalshi_rest"

SETTLEMENT_COLUMNS = [
    "market_id",
    "ticker",
    "internal_game_id",
    "game_link_status",
    "source",
    "source_market_id",
    "source_result",
    "source_identifier",
    "settlement_status",
    "settlement_value_e4",
    "source_settled_at",
    "result_available_at",
    "settlement_time",
    "close_time",
    "expiration_time",
    "provenance",
    "sport",
    "season",
]

# Columns that must never be used as the settlement authority.
FORBIDDEN_INFERENCE_COLUMNS = (
    "home_win",
    "away_win",
    "final_home_score",
    "final_away_score",
    "yes_bid_close",
    "yes_bid_open",
    "yes_bid_high",
    "yes_bid_low",
    "last_close_e4",
    "last_price_e4",
)


class SettlementConflictError(ValueError):
    """One market_id with two different authoritative classifications."""


@dataclass
class SettlementBuild:
    settlements: pd.DataFrame
    status_counts: dict[str, int] = field(default_factory=dict)
    suite_tickers: int = 0
    crosswalk_tickers: int = 0
    duplicate_source_rows: int = 0
    unlinked_rows: int = 0
    missing_rows: int = 0
    games_with_settlement: int = 0
    input_hashes: dict[str, str] = field(default_factory=dict)
    source_path: str = ""
    date_min: str = ""
    date_max: str = ""


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _iso(value: object) -> str:
    if value in (None, ""):
        return ""
    if hasattr(value, "strftime"):
        try:
            ts = pd.Timestamp(value, tz="UTC")
            return ts.strftime("%Y-%m-%dT%H:%M:%S.%fZ").replace(".000000Z", "Z")
        except (TypeError, ValueError):
            return str(value)
    text = _text(value)
    if text.endswith("+00:00"):
        return text.replace("+00:00", "Z")
    return text


def _e4_text(value: object, *, missing: bool) -> str:
    if missing:
        return ""
    if value in (None, ""):
        return ""
    try:
        return str(int(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"malformed settlement_value_e4: {value!r}") from exc


def refuse_score_derived_settlement() -> None:
    raise ValueError("settlement must not be derived from NBA score or PBP")


def refuse_price_derived_settlement() -> None:
    raise ValueError("settlement must not be derived from market price or candles")


def assert_not_inferred_settlement_source(columns: list[str] | tuple[str, ...]) -> None:
    """Fail if the caller offers only score/price columns and no Kalshi result."""
    cols = {str(c) for c in columns}
    if "result" in cols:
        return
    forbidden = [c for c in FORBIDDEN_INFERENCE_COLUMNS if c in cols]
    if forbidden:
        if any(c in cols for c in ("home_win", "away_win", "final_home_score", "final_away_score")):
            refuse_score_derived_settlement()
        refuse_price_derived_settlement()


def suite_markets_path(cfg: RollerConfig, season: str = "2025-2026") -> Path:
    _, _, wh = load_sport_games(cfg, PHASE6_SPORT, season)
    return markets_parquet(wh, cfg.season_meta(PHASE6_SPORT, season)["warehouse_sport"])


def load_suite_markets(cfg: RollerConfig, season: str = "2025-2026") -> pd.DataFrame:
    src = suite_markets_path(cfg, season)
    if not src.is_file():
        return pd.DataFrame()
    return pd.read_parquet(src)


def _link_lookup(crosswalk: pd.DataFrame) -> dict[str, tuple[str, str]]:
    out: dict[str, tuple[str, str]] = {}
    if crosswalk.empty:
        return out
    for rec in crosswalk.to_dict("records"):
        ticker = _text(rec.get("ticker") or rec.get("market_id"))
        if not ticker:
            continue
        out[ticker] = (_text(rec.get("internal_game_id")), _text(rec.get("link_status")))
    return out


def _source_key(rec: dict[str, Any]) -> tuple[str, str, str]:
    raw = rec.get("result")
    status = kalshi_result_to_settlement(raw)
    value = _e4_text(rec.get("settlement_value_e4"), missing=status is SettlementResult.MISSING)
    return (status.value, _text(raw).lower(), value)


def project_settlement_frame(
    suite: pd.DataFrame,
    crosswalk: pd.DataFrame,
    *,
    source_path: str = "",
    source_hash: str = "",
    season: str = "2025-2026",
) -> tuple[pd.DataFrame, dict[str, int]]:
    """One row per market_id. Conflicting Suite classifications fail closed."""
    assert_not_inferred_settlement_source(list(suite.columns) if suite is not None else [])
    links = _link_lookup(crosswalk)
    by_ticker: dict[str, list[dict[str, Any]]] = {}
    if suite is not None and not suite.empty and "ticker" in suite.columns:
        for rec in suite.to_dict("records"):
            ticker = _text(rec.get("ticker"))
            if not ticker:
                raise ValueError("malformed settlement: blank ticker")
            by_ticker.setdefault(ticker, []).append(rec)

    tickers = sorted(set(by_ticker) | set(links))
    provenance = f"suite:{Path(source_path).name}:{source_hash[:16] or 'nohash'}:{SETTLEMENT_SOURCE}"
    rows: list[dict[str, str]] = []
    extras = {
        "duplicate_source_rows": 0,
        "unlinked_rows": 0,
        "missing_rows": 0,
    }

    for ticker in tickers:
        sources = by_ticker.get(ticker, [])
        gid, link_status = links.get(ticker, ("", "UNLINKED"))
        if not sources:
            extras["missing_rows"] += 1
            rows.append(
                _settlement_row(
                    ticker=ticker,
                    gid=gid if link_status == "LINKED" else "",
                    link_status=link_status or "UNLINKED",
                    status=SettlementResult.MISSING,
                    source_result="",
                    source_market_id="",
                    value="",
                    settled_at="",
                    close_time="",
                    expiration_time="",
                    provenance=provenance,
                    season=season,
                )
            )
            continue

        keys = [_source_key(rec) for rec in sources]
        if len(set(keys)) > 1:
            raise SettlementConflictError(
                f"conflicting Suite settlements for {ticker}: {sorted(set(keys))}"
            )
        if len(sources) > 1:
            extras["duplicate_source_rows"] += len(sources) - 1
        rec = sources[0]
        status = kalshi_result_to_settlement(rec.get("result"))
        # Construct the entity so Phase 1 invariants apply (MISSING cannot invent e4).
        value = _e4_text(rec.get("settlement_value_e4"), missing=status is SettlementResult.MISSING)
        Settlement(
            ticker=ticker,
            result=status,
            settlement_value_e4=None if value == "" else int(value),
            result_available_at=_iso(rec.get("settlement_time") or rec.get("close_time") or rec.get("expiration_time")),
            settlement_time=_iso(rec.get("settlement_time")),
        )
        if link_status != "LINKED":
            extras["unlinked_rows"] += 1
            gid = ""
            link_status = link_status or "UNLINKED"
        rows.append(
            _settlement_row(
                ticker=ticker,
                gid=gid,
                link_status=link_status,
                status=status,
                source_result=_text(rec.get("result")).lower(),
                source_market_id=_text(rec.get("market_id")),
                value=value,
                settled_at=_iso(rec.get("settlement_time")),
                close_time=_iso(rec.get("close_time")),
                expiration_time=_iso(rec.get("expiration_time")),
                provenance=provenance,
                season=season,
            )
        )

    frame = pd.DataFrame(rows, columns=SETTLEMENT_COLUMNS)
    if not frame.empty:
        frame = frame.sort_values(["market_id"], kind="mergesort").reset_index(drop=True)
    return frame, extras


def _settlement_row(
    *,
    ticker: str,
    gid: str,
    link_status: str,
    status: SettlementResult,
    source_result: str,
    source_market_id: str,
    value: str,
    settled_at: str,
    close_time: str,
    expiration_time: str,
    provenance: str,
    season: str,
) -> dict[str, str]:
    result_at = settled_at or close_time or expiration_time
    return {
        "market_id": ticker,
        "ticker": ticker,
        "internal_game_id": gid,
        "game_link_status": link_status,
        "source": SETTLEMENT_SOURCE,
        "source_market_id": source_market_id,
        "source_result": source_result,
        "source_identifier": source_market_id or ticker,
        "settlement_status": status.value,
        "settlement_value_e4": value,
        "source_settled_at": settled_at,
        "result_available_at": result_at,
        "settlement_time": settled_at,
        "close_time": close_time,
        "expiration_time": expiration_time,
        "provenance": provenance,
        "sport": PHASE6_SPORT,
        "season": season,
    }


def build_nba_settlements(
    cfg: RollerConfig,
    *,
    season: str = "2025-2026",
    suite: pd.DataFrame | None = None,
    crosswalk: pd.DataFrame | None = None,
) -> SettlementBuild:
    src = suite_markets_path(cfg, season)
    source_hash = sha256_file(src) if src.is_file() else ""
    if suite is None:
        suite = load_suite_markets(cfg, season)
    if crosswalk is None:
        crosswalk = load_nba_crosswalk(cfg)
        if crosswalk.empty:
            raise ValueError("NBA GameMarketLink crosswalk is empty; run Phase 3 first")
    assert_not_inferred_settlement_source(list(suite.columns) if suite is not None and not suite.empty else ["result"])
    frame, extras = project_settlement_frame(
        suite,
        crosswalk,
        source_path=str(src),
        source_hash=source_hash,
        season=season,
    )
    status_counts = {s.value: 0 for s in SettlementResult}
    if not frame.empty:
        for status in frame["settlement_status"].astype(str):
            status_counts[status] = status_counts.get(status, 0) + 1
    games = set()
    if not frame.empty:
        settled = frame[frame["settlement_status"].isin(["YES", "NO", "INVALID"])]
        games = {g for g in settled["internal_game_id"].astype(str) if g}
    times = []
    if not frame.empty:
        times = [t for t in frame["source_settled_at"].astype(str) if t]
    suite_n = 0
    if suite is not None and not suite.empty and "ticker" in suite.columns:
        suite_n = int(suite["ticker"].map(_text).astype(bool).sum())
    xwalk_n = 0 if crosswalk.empty else int(crosswalk["ticker"].map(_text).nunique())
    return SettlementBuild(
        settlements=frame,
        status_counts=status_counts,
        suite_tickers=suite_n,
        crosswalk_tickers=xwalk_n,
        duplicate_source_rows=extras["duplicate_source_rows"],
        unlinked_rows=extras["unlinked_rows"],
        missing_rows=extras["missing_rows"],
        games_with_settlement=len(games),
        input_hashes={"suite_markets": source_hash},
        source_path=str(src),
        date_min=min(times) if times else "",
        date_max=max(times) if times else "",
    )


def write_nba_settlements(cfg: RollerConfig, built: SettlementBuild) -> dict[str, Any]:
    path = settlements_parquet_path(cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    built.settlements.to_parquet(path, index=False)
    readme = warehouse_v0_readme_path(cfg)
    if not readme.is_file():
        readme.write_text(
            "Provisional NBA warehouse_v0. Not Confirm & Run. Phase 8 will relocate.\n",
            encoding="utf-8",
        )
    manifest = {
        "artifact": "nba_settlements",
        "sport": PHASE6_SPORT,
        "row_count": int(len(built.settlements)),
        "status_counts": built.status_counts,
        "suite_tickers": built.suite_tickers,
        "crosswalk_tickers": built.crosswalk_tickers,
        "duplicate_source_rows": built.duplicate_source_rows,
        "unlinked_rows": built.unlinked_rows,
        "missing_rows": built.missing_rows,
        "games_with_settlement": built.games_with_settlement,
        "date_min": built.date_min,
        "date_max": built.date_max,
        "source_path": built.source_path,
        "input_hashes": built.input_hashes,
        "sha256": sha256_file(path),
        "updated_at": now_utc_iso(),
        "provisional_layout": str(warehouse_v0_root(cfg)),
    }
    write_json(settlements_manifest_path(cfg), manifest)
    return manifest


def build_and_write_nba_settlements(cfg: RollerConfig, *, season: str = "2025-2026") -> dict[str, Any]:
    built = build_nba_settlements(cfg, season=season)
    return write_nba_settlements(cfg, built)


def coverage_report(
    settlements: pd.DataFrame,
    *,
    observation_tickers: set[str] | None = None,
    observation_games: set[str] | None = None,
) -> dict[str, int]:
    if settlements.empty:
        return {
            "markets": 0,
            "linked_markets": 0,
            "yes": 0,
            "no": 0,
            "missing": 0,
            "invalid": 0,
            "games_with_settlement": 0,
            "games_without_settlement": 0,
            "games_market_obs_settlement": 0,
            "games_market_obs_no_settlement": 0,
        }
    linked = settlements[settlements["game_link_status"] == "LINKED"]
    has_result = settlements["settlement_status"].isin(["YES", "NO", "INVALID"])
    settled_games = {g for g in settlements.loc[has_result, "internal_game_id"].astype(str) if g}
    linked_games = {g for g in linked["internal_game_id"].astype(str) if g}
    obs_t = observation_tickers or set()
    obs_g = observation_games or set()
    settled_tickers = set(settlements.loc[has_result, "ticker"].astype(str))
    games_both = obs_g & settled_games
    games_obs_only = obs_g - settled_games
    return {
        "markets": int(len(settlements)),
        "linked_markets": int(len(linked)),
        "markets_with_settlement": int(has_result.sum()),
        "markets_missing_settlement": int((settlements["settlement_status"] == "MISSING").sum()),
        "yes": int((settlements["settlement_status"] == "YES").sum()),
        "no": int((settlements["settlement_status"] == "NO").sum()),
        "missing": int((settlements["settlement_status"] == "MISSING").sum()),
        "invalid": int((settlements["settlement_status"] == "INVALID").sum()),
        "duplicate_source_rows": 0,
        "games_with_settlement": len(settled_games),
        "games_without_settlement": len(linked_games - settled_games),
        "games_market_obs_settlement": len(games_both),
        "games_market_obs_no_settlement": len(games_obs_only),
        "obs_tickers_with_settlement": len(obs_t & settled_tickers),
        "obs_tickers_without_settlement": len(obs_t - settled_tickers),
    }
