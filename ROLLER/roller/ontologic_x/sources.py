"""Fixture book and credential-gated William Hill transports."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path

WILLIAM_HILL_ODDS_API_KEY = "williamhill"
CAESARS_ODDS_API_KEY = "williamhill_us"
OPTIC_SPORTSBOOK = "william_hill"
ODDS_API_INTERVAL_SECONDS = 60
OPTIC_INTERVAL_SECONDS = 30


class PollGate:
    """Bounded exponential backoff for the lease owner."""

    def __init__(self) -> None:
        self.failures = 0
        self.blocked_until: datetime | None = None

    def allowed(self, now: datetime) -> bool:
        return self.blocked_until is None or now >= self.blocked_until

    def failure(self, now: datetime) -> int:
        self.failures += 1
        delay = min(60, 2**self.failures)
        self.blocked_until = now + timedelta(seconds=delay)
        return delay

    def success(self) -> None:
        self.failures = 0
        self.blocked_until = None


def redact(text: str) -> str:
    cleaned = text
    for name in ("ONTOLOGIC_ODDS_API_KEY", "ONTOLOGIC_OPTICODDS_KEY"):
        secret = os.environ.get(name)
        if secret:
            cleaned = cleaned.replace(secret, "REDACTED")
    return cleaned


def load_local_secrets(path: Path | None = None) -> None:
    """Load server-side Ontologic keys when the process environment does not already have them."""
    file = path or (Path(__file__).resolve().parents[3] / ".env.ontologic")
    if not file.is_file():
        return
    for line in file.read_text().splitlines():
        text = line.strip()
        if not text or text.startswith("#") or "=" not in text:
            continue
        name, value = text.split("=", 1)
        name = name.strip()
        if name.startswith("ONTOLOGIC_") and not os.environ.get(name):
            os.environ[name] = value.strip().strip('"').strip("'")


def provider_mode() -> str:
    book = (os.environ.get("ONTOLOGIC_BOOK") or "").strip().lower()
    if book == "betonline":
        return "BETONLINE"
    if os.environ.get("ONTOLOGIC_OPTICODDS_KEY"):
        return "OPTICODDS"
    if os.environ.get("ONTOLOGIC_ODDS_API_KEY"):
        return "ODDS_API"
    return "FIXTURE"


def cadence_for(mode: str) -> tuple[int, str]:
    if mode == "BETONLINE":
        raw = os.environ.get("ONTOLOGIC_BETONLINE_INTERVAL_SECONDS") or "120"
        try:
            seconds = max(30, int(raw))
        except ValueError:
            seconds = 120
        return seconds, "PROVIDER_CADENCE_NOT_5S"
    override = os.environ.get("ONTOLOGIC_PROVIDER_INTERVAL_SECONDS")
    if override:
        seconds = max(5, int(override))
        label = "ENTITLED_5S" if seconds == 5 else "PROVIDER_CADENCE_NOT_5S"
        return seconds, label
    if mode == "ODDS_API":
        return ODDS_API_INTERVAL_SECONDS, "PROVIDER_CADENCE_NOT_5S"
    if mode == "OPTICODDS":
        return OPTIC_INTERVAL_SECONDS, "PROVIDER_CADENCE_NOT_5S"
    return 5, "FIXTURE"


def load_fixture_document(path: Path) -> dict:
    document = json.loads(path.read_text())
    document.pop("secret_sentinel_do_not_emit", None)
    return document


class FixtureSource:
    def __init__(self, document: dict):
        self.document = document
        self.calls = 0

    def __call__(self, revision: int) -> dict:
        return self.fetch(revision)

    def fetch(self, revision: int) -> dict:
        self.calls += 1
        quotes = deepcopy(self.document.get("quotes") or [])
        if revision >= 1:
            for quote in quotes:
                patch = (self.document.get("revision_patch") or {}).get(quote.get("provider_event_id"))
                if not patch:
                    continue
                if (
                    quote.get("market_family") == patch.get("market_family")
                    and quote.get("side") == patch.get("side")
                    and str(quote.get("line")) == str(patch.get("line"))
                ):
                    quote["american"] = patch.get("american")
                    if "source_updated_at" in patch:
                        quote["source_updated_at"] = patch.get("source_updated_at")
                    if patch.get("status"):
                        quote["status"] = patch["status"]
        return {
            "mode": "FIXTURE",
            "label": "FIXTURE",
            "quotes": quotes,
            "nba_games": deepcopy(self.document.get("nba_games") or []),
            "canonical_games": deepcopy(self.document.get("canonical_games") or []),
            "cadence_label": "FIXTURE",
            "error": None,
        }


def _get_json(url: str, headers: dict[str, str] | None = None, timeout: int = 10) -> object:
    request = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(redact(f"HTTP {exc.code}: {detail[:240]}")) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(redact(str(exc.reason))) from exc
    return json.loads(payload, parse_int=str, parse_float=str)


def DecimalAmerican(value: object) -> str:
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text


def parse_odds_api(payload: object) -> tuple[list[dict], list[str]]:
    quotes: list[dict] = []
    rejected: list[str] = []
    if not isinstance(payload, list):
        return quotes, ["ODDS_API_SHAPE"]
    for event in payload:
        if not isinstance(event, dict):
            continue
        home_name = event.get("home_team")
        away_name = event.get("away_team")
        for book in event.get("bookmakers") or []:
            key = str(book.get("key") or "")
            if key == CAESARS_ODDS_API_KEY:
                rejected.append("BOOK_KEY_IS_CAESARS")
                continue
            if key != WILLIAM_HILL_ODDS_API_KEY:
                rejected.append("NOT_WILLIAM_HILL")
                continue
            for market in book.get("markets") or []:
                market_key = str(market.get("key") or "")
                family, period = _odds_api_market(market_key)
                if family is None:
                    continue
                source_time = market.get("last_update") or book.get("last_update")
                for outcome in market.get("outcomes") or []:
                    side = _odds_api_side(outcome.get("name"), home_name, away_name, family)
                    if side is None:
                        continue
                    quotes.append(
                        {
                            "provider": "the_odds_api",
                            "bookmaker": "williamhill",
                            "provider_event_id": event.get("id"),
                            "home_name": home_name,
                            "away_name": away_name,
                            "start_utc": event.get("commence_time"),
                            "market_family": family,
                            "period": period,
                            "main": True,
                            "side": side,
                            "line": outcome.get("point"),
                            "american": DecimalAmerican(outcome.get("price")) if outcome.get("price") is not None else None,
                            "status": "open",
                            "phase": "pregame",
                            "settlement": "UNKNOWN",
                            "source_updated_at": source_time,
                            "home_team_id": None,
                            "away_team_id": None,
                        }
                    )
    return quotes, rejected


def _odds_api_market(key: str) -> tuple[str | None, str]:
    if key == "h2h":
        return "moneyline", "game"
    if key == "spreads":
        return "spread", "game"
    if key == "totals":
        return "total", "game"
    if key.endswith("_q1"):
        return _odds_api_market(key[:-3])[0], "Q1"
    if key.endswith("_q2"):
        return _odds_api_market(key[:-3])[0], "Q2"
    if key.endswith("_q3"):
        return _odds_api_market(key[:-3])[0], "Q3"
    if key.endswith("_q4"):
        return _odds_api_market(key[:-3])[0], "Q4"
    return None, "game"


def _odds_api_side(name: object, home: object, away: object, family: str) -> str | None:
    if family == "total":
        text = str(name or "").lower()
        if text == "over":
            return "over"
        if text == "under":
            return "under"
        return None
    if name == home:
        return "home"
    if name == away:
        return "away"
    return None


def fetch_odds_api() -> dict:
    key = os.environ.get("ONTOLOGIC_ODDS_API_KEY")
    if not key:
        raise RuntimeError("ODDS_API_KEY_MISSING")
    query = urllib.parse.urlencode(
        {
            "markets": "h2h,spreads,totals",
            "bookmakers": WILLIAM_HILL_ODDS_API_KEY,
            "oddsFormat": "american",
            "apiKey": key,
        }
    )
    quotes: list[dict] = []
    rejected: list[str] = []
    for sport in ("basketball_nba_preseason", "basketball_nba"):
        url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/?{query}"
        payload = _get_json(url)
        sport_quotes, sport_rejected = parse_odds_api(payload)
        quotes.extend(sport_quotes)
        rejected.extend(sport_rejected)
    return {
        "mode": "ODDS_API",
        "label": "williamhill" if quotes else "SOURCE_UNAVAILABLE",
        "quotes": quotes,
        "rejected": rejected,
        "error": None,
    }


def parse_optic(payload: object) -> tuple[list[dict], list[str]]:
    quotes: list[dict] = []
    rejected: list[str] = []
    rows = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return quotes, ["OPTIC_SHAPE"]
    for fixture in rows:
        if not isinstance(fixture, dict):
            continue
        home = (fixture.get("home_competitors") or [{}])[0]
        away = (fixture.get("away_competitors") or [{}])[0]
        for odd in fixture.get("odds") or []:
            book = str(odd.get("sportsbook") or "")
            if book.replace(" ", "").replace("_", "").lower() not in {"williamhill"}:
                rejected.append("NOT_WILLIAM_HILL")
                continue
            market = str(odd.get("market_id") or odd.get("market") or "").lower()
            family, period = _optic_market(market)
            if family is None:
                continue
            side = _optic_side(odd, home, away, family)
            if side is None:
                continue
            quotes.append(
                {
                    "provider": "opticodds",
                    "bookmaker": "williamhill",
                    "provider_event_id": fixture.get("id"),
                    "home_team_id": None,
                    "away_team_id": None,
                    "home_name": home.get("name") or fixture.get("home_team_display"),
                    "away_name": away.get("name") or fixture.get("away_team_display"),
                    "start_utc": fixture.get("start_date"),
                    "market_family": family,
                    "period": period,
                    "main": bool(odd.get("is_main")),
                    "side": side,
                    "line": odd.get("points"),
                    "american": DecimalAmerican(odd.get("price")) if odd.get("price") is not None else None,
                    "status": "open",
                    "phase": "live" if fixture.get("is_live") else "pregame",
                    "settlement": "UNKNOWN",
                    "source_updated_at": None if odd.get("timestamp") is None else str(odd.get("timestamp")),
                }
            )
    return quotes, rejected


def _optic_market(market: str) -> tuple[str | None, str]:
    period = "game"
    for label, code in (("1st quarter", "Q1"), ("2nd quarter", "Q2"), ("3rd quarter", "Q3"), ("4th quarter", "Q4")):
        if label in market:
            period = code
    if "moneyline" in market:
        return "moneyline", period
    if "spread" in market or "point spread" in market:
        return "spread", period
    if "total" in market:
        return "total", period
    return None, period


def _optic_side(odd: dict, home: dict, away: dict, family: str) -> str | None:
    if family == "total":
        text = str(odd.get("selection_line") or odd.get("name") or "").lower()
        if "over" in text:
            return "over"
        if "under" in text:
            return "under"
        return None
    team_id = odd.get("team_id")
    if team_id and team_id == home.get("id"):
        return "home"
    if team_id and team_id == away.get("id"):
        return "away"
    return None


def fetch_opticodds(fixture_ids: list[str]) -> dict:
    key = os.environ.get("ONTOLOGIC_OPTICODDS_KEY")
    if not key:
        raise RuntimeError("OPTICODDS_KEY_MISSING")
    if not fixture_ids:
        active = _get_json(
            "https://api.opticodds.com/api/v3/fixtures/active?sport=basketball&league=NBA",
            headers={"X-Api-Key": key},
        )
        rows = active.get("data") if isinstance(active, dict) else None
        fixture_ids = [str(row.get("id")) for row in (rows or []) if isinstance(row, dict) and row.get("id")][:5]
    if not fixture_ids:
        return {
            "mode": "OPTICODDS",
            "label": "SOURCE_UNAVAILABLE",
            "quotes": [],
            "rejected": ["NO_FIXTURES"],
            "error": "SOURCE_UNAVAILABLE",
        }
    query = [("sportsbook", OPTIC_SPORTSBOOK), ("odds_format", "AMERICAN")]
    for fixture_id in fixture_ids[:5]:
        query.append(("fixture_id", fixture_id))
    url = "https://api.opticodds.com/api/v3/fixtures/odds?" + urllib.parse.urlencode(query)
    payload = _get_json(url, headers={"X-Api-Key": key})
    quotes, rejected = parse_optic(payload)
    if not quotes:
        return {
            "mode": "OPTICODDS",
            "label": "SOURCE_UNAVAILABLE",
            "quotes": [],
            "rejected": rejected or ["WILLIAM_HILL_ABSENT"],
            "error": "SOURCE_UNAVAILABLE",
        }
    return {
        "mode": "OPTICODDS",
        "label": "williamhill",
        "quotes": quotes,
        "rejected": rejected,
        "error": None,
    }
