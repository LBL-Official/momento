"""Official Kalshi W overlay for generic queries that select a terminal.

Does not invent settlement from PBP, box score, path WIN, last trade, or candles.
Uses FIRST80 candidates.expiration_result_yes (same official W frozen locks use)
and the complementary side of a binary event ticker.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable

from roller.research_query.models import ResearchQuestion, TerminalOutcome

OFFICIAL_W_TAG = "official_w_v1"
_REPO = Path(__file__).resolve().parents[3]
_CACHE: dict[str, Any] | None = None

_SPORT_DIRS = ("NBA", "NCAAB", "WNBA", "NHL")


def needs_official_settlement(question: ResearchQuestion) -> bool:
    if question.win_hold or question.loss_hold:
        return True
    return question.terminal in (TerminalOutcome.YES, TerminalOutcome.NO)


def official_settlement_health() -> dict[str, Any]:
    sources = _source_paths()
    existing = [str(p.relative_to(_REPO)) for p in sources if p.is_file()]
    return {
        "status": "AVAILABLE" if existing else "ABSENT",
        "canonical_kalshi_markets": "ABSENT",
        "sources": existing,
        "terminal_source": "official_first80_expiration_result_yes",
        "complement": "binary_event_ticker",
        "note": (
            "Kalshi expiration_result_yes from FIRST80 candidates, plus the other "
            "side of the same event ticker. Not box-score win. Not path WIN."
        ),
    }


def load_official_settlement() -> dict[str, dict[str, Any]]:
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    overlay: dict[str, dict[str, Any]] = {}
    for path in _source_paths():
        if not path.is_file():
            continue
        if path.suffix == ".json":
            _ingest_candidates(overlay, path)
        elif path.suffix == ".csv":
            _ingest_asked_six(overlay, path)
    _CACHE = overlay
    return overlay


def merge_official_settlement(
    markets_by_ticker: dict[str, dict[str, Any]] | None,
    tickers: Iterable[str] | None = None,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Fill missing result from official W. Existing kalshi_markets result wins."""
    overlay = load_official_settlement()
    out = {k: dict(v) for k, v in (markets_by_ticker or {}).items()}
    wanted = list(tickers) if tickers is not None else list(overlay)
    n_direct = 0
    n_complement = 0
    n_kept = 0
    for ticker in wanted:
        if not ticker:
            continue
        existing = out.get(ticker)
        if _has_result(existing):
            n_kept += 1
            continue
        rec = _lookup_official(ticker, overlay)
        if rec is None:
            continue
        if rec.get("source", "").startswith("official_complement"):
            n_complement += 1
        else:
            n_direct += 1
        merged = dict(existing or {})
        merged.update(rec)
        merged.setdefault("ticker", ticker)
        out[ticker] = merged
    status = official_settlement_health()
    overlay_n = n_direct + n_complement
    if overlay_n and n_kept:
        terminal_source = "kalshi_markets.result+official_first80_expiration_result_yes"
        note = (
            "Existing kalshi_markets.result wins. FIRST80 expiration_result_yes "
            "fills only tickers that still have no result. Not box-score win. Not path WIN."
        )
        canonical = "USED"
    elif overlay_n:
        terminal_source = "official_first80_expiration_result_yes"
        note = (
            "Kalshi expiration_result_yes from FIRST80 candidates, plus the other "
            "side of the same event ticker. Not box-score win. Not path WIN."
        )
        canonical = "ABSENT"
    elif n_kept:
        terminal_source = "kalshi_markets.result"
        note = (
            "Kalshi warehouse kalshi_markets.result. FIRST80 official W overlay "
            "matched 0 tickers. Missing result stays missing. Not box-score win. "
            "Not path WIN."
        )
        canonical = "USED"
    else:
        terminal_source = "UNAVAILABLE"
        note = (
            "No kalshi_markets.result and no official FIRST80 W join. "
            "Terminal is missing. Not invented from path or box score."
        )
        canonical = "ABSENT"
    status.update(
        {
            "n_kept_canonical": n_kept,
            "n_direct": n_direct,
            "n_complement": n_complement,
            "n_overlay_tickers": len(overlay),
            "overlay_applied": bool(overlay_n),
            "canonical_kalshi_markets": canonical,
            "terminal_source": terminal_source,
            "note": note,
        }
    )
    return out, status


def _source_paths() -> list[Path]:
    paths: list[Path] = []
    for sport in _SPORT_DIRS:
        paths.append(
            _REPO
            / "Backtesting Suite"
            / "Data"
            / sport
            / "2025-2026"
            / "warehouse"
            / "derived"
            / sport.lower()
            / "first80_execution_audit"
            / "candidates.json"
        )
    paths.append(
        _REPO / "research" / "first80_asked_six_chatgpt_export" / "first80_asked_six.csv"
    )
    return paths


def _ingest_candidates(overlay: dict[str, dict[str, Any]], path: Path) -> None:
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(rows, list):
        return
    src = f"candidates:{path.parent.parent.name}"
    for row in rows:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "")
        if not ticker or ticker in overlay:
            continue
        rec = _from_flag(row.get("expiration_result_yes"), src)
        if rec is None:
            rec = _from_flag(row.get("W"), src)
        if rec is not None:
            overlay[ticker] = rec


def _ingest_asked_six(overlay: dict[str, dict[str, Any]], path: Path) -> None:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                ticker = str(row.get("ticker") or "")
                if not ticker or ticker in overlay:
                    continue
                rec = _from_flag(row.get("W"), "asked_six_csv")
                if rec is None:
                    rec = _from_flag(row.get("terminal_yes"), "asked_six_csv")
                if rec is not None:
                    overlay[ticker] = rec
    except OSError:
        return


def _from_flag(value: Any, source: str) -> dict[str, Any] | None:
    if value in (True, 1, "1", "true", "True", "yes", "YES"):
        return {"result": "yes", "source": source}
    if value in (False, 0, "0", "false", "False", "no", "NO"):
        return {"result": "no", "source": source}
    return None


def _has_result(market: dict[str, Any] | None) -> bool:
    if not market:
        return False
    result = str(market.get("result") or market.get("kalshi_result") or "").lower()
    if result in {"yes", "no"}:
        return True
    sv = market.get("settlement_value_e4")
    try:
        return int(sv) in (0, 10000)
    except (TypeError, ValueError):
        return False


def _bare_ticker(ticker: str) -> str:
    """League-union may prefix `NBA:KX…`. Official W is keyed by the Kalshi ticker."""
    if ":" in ticker and not ticker.startswith("KX"):
        return ticker.split(":", 1)[1]
    return ticker


def _lookup_official(ticker: str, overlay: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    for key in (ticker, _bare_ticker(ticker)):
        if key in overlay:
            return overlay[key]
        rec = _complement(key, overlay)
        if rec is not None:
            return rec
    return None


def _complement(ticker: str, overlay: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    if "-" not in ticker:
        return None
    prefix = ticker.rsplit("-", 1)[0]
    siblings = [
        (other, rec)
        for other, rec in overlay.items()
        if other.startswith(prefix + "-") and other != ticker and rec.get("result") in {"yes", "no"}
    ]
    if len(siblings) != 1:
        return None
    other_t, rec = siblings[0]
    inv = "no" if rec["result"] == "yes" else "yes"
    return {
        "result": inv,
        "source": f"official_complement:{rec.get('source')}:{other_t}",
    }
