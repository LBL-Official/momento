"""Official Polymarket Gamma + CLOB readers.

Events: GET https://gamma-api.polymarket.com/events
Prices: GET https://clob.polymarket.com/prices-history
        (last-trade samples {t, p}, fidelity minutes). Not bid/ask OHLC.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from roller.config import RollerConfig
from roller.ingest.games import load_sport_games
from roller.paths import warehouse_dir
from roller.timeutil import UTC, parse_utc, to_iso

HttpGet = Callable[[str], Any]

DEFAULT_HEADERS = {"User-Agent": "MomentoROLLER/1.0 (research ingest; read-only)"}


def polymarket_cfg(cfg: RollerConfig) -> dict[str, Any]:
    return dict(cfg.polymarket or {})


def warehouse_polymarket_raw(warehouse: Path, sport: str) -> Path:
    return warehouse / "raw" / "polymarket" / sport.lower()


def warehouse_polymarket_events(warehouse: Path, sport: str) -> Path:
    return warehouse_polymarket_raw(warehouse, sport) / "events"


def warehouse_polymarket_prices(warehouse: Path, sport: str, token_id: str) -> Path:
    return warehouse_polymarket_raw(warehouse, sport) / "prices_history" / f"token={token_id}"


def warehouse_polymarket_candles(warehouse: Path, sport: str) -> Path:
    return warehouse / "normalized" / sport.lower() / "polymarket_candles_1m"


def warehouse_polymarket_crosswalk(warehouse: Path, sport: str) -> Path:
    return warehouse / "normalized" / sport.lower() / "polymarket_crosswalk.json"


def warehouse_for(cfg: RollerConfig, sport: str, season: str) -> Path:
    meta = cfg.season_meta(sport, season)
    return warehouse_dir(cfg.warehouse_root, meta["warehouse_sport"], meta["warehouse_season"])


def json_list(value: Any) -> list[Any]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return json.loads(value)
    return []


def default_http_get(url: str, *, timeout: float = 45.0, retries: int = 5) -> Any:
    last: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=DEFAULT_HEADERS)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code == 429 or exc.code >= 500:
                time.sleep(min(30.0, 1.5**attempt))
                continue
            raise
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last = exc
            time.sleep(min(30.0, 1.5**attempt))
    if last is not None:
        raise last
    raise RuntimeError(f"GET failed: {url}")


def list_events(
    cfg: RollerConfig,
    sport: str,
    season: str,
    *,
    http_get: HttpGet | None = None,
    max_events: int | None = None,
    pause_s: float = 0.12,
) -> list[dict[str, Any]]:
    pm = polymarket_cfg(cfg)
    league = (pm.get("leagues") or {}).get(sport) or {}
    window = ((pm.get("season_windows") or {}).get(sport) or {}).get(season) or {}
    date_from = str(window.get("event_date_from") or "")
    date_to = str(window.get("event_date_to") or "")
    series_ids = [str(s) for s in (league.get("series_ids") or [])]
    getter = http_get or default_http_get
    base = str(pm.get("gamma_base") or "https://gamma-api.polymarket.com").rstrip("/")
    path = str(pm.get("events_path") or "/events")
    tag_id = pm.get("game_tag_id")
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for series_id in series_ids:
        offset = 0
        use_tag = tag_id is not None
        while True:
            params: dict[str, Any] = {
                "series_id": series_id,
                "limit": 100,
                "offset": offset,
                "order": "startTime",
                "ascending": "true",
            }
            if use_tag:
                params["tag_id"] = str(tag_id)
            url = f"{base}{path}?{urllib.parse.urlencode(params)}"
            try:
                payload = getter(url)
            except Exception:
                if use_tag:
                    use_tag = False
                    continue
                raise
            if not isinstance(payload, list):
                break
            if not payload:
                break
            for ev in payload:
                eid = str(ev.get("id") or "")
                if not eid or eid in seen:
                    continue
                event_date = str(ev.get("eventDate") or "")[:10]
                if date_from and event_date and event_date < date_from:
                    continue
                if date_to and event_date and event_date > date_to:
                    continue
                if not event_date:
                    start = parse_utc(ev.get("startTime") or ev.get("endDate"))
                    if start is None:
                        continue
                    event_date = to_iso(start)[:10]
                    if date_from and event_date < date_from:
                        continue
                    if date_to and event_date > date_to:
                        continue
                seen.add(eid)
                out.append(ev)
                if max_events is not None and len(out) >= max_events:
                    return out
            offset += len(payload)
            if len(payload) < 100:
                break
            if pause_s:
                time.sleep(pause_s)
    return out


def write_raw_events(warehouse: Path, sport: str, events: list[dict[str, Any]]) -> list[Path]:
    dest = warehouse_polymarket_events(warehouse, sport)
    dest.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for ev in events:
        eid = str(ev.get("id") or "")
        if not eid:
            continue
        path = dest / f"{eid}.json"
        path.write_text(json.dumps(ev, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
        paths.append(path)
    return paths


def load_raw_events(warehouse: Path, sport: str) -> list[dict[str, Any]]:
    dest = warehouse_polymarket_events(warehouse, sport)
    if not dest.is_dir():
        return []
    events = []
    for path in sorted(dest.glob("*.json")):
        events.append(json.loads(path.read_text(encoding="utf-8")))
    return events


def moneyline_market(event: dict[str, Any], moneyline_type: str = "moneyline") -> dict[str, Any] | None:
    for raw in event.get("markets") or []:
        if str(raw.get("sportsMarketType") or "") == moneyline_type:
            return raw
    return None


def fetch_prices_history(
    token_id: str,
    start: datetime,
    end: datetime,
    *,
    cfg: RollerConfig,
    http_get: HttpGet | None = None,
    pause_s: float = 0.12,
) -> list[dict[str, Any]]:
    pm = polymarket_cfg(cfg)
    hist_cfg = pm.get("price_history") or {}
    fidelity = int(hist_cfg.get("fidelity_minutes") or 1)
    chunk_days = int(hist_cfg.get("chunk_days") or 10)
    getter = http_get or default_http_get
    base = str(pm.get("clob_base") or "https://clob.polymarket.com").rstrip("/")
    path = str(pm.get("prices_history_path") or "/prices-history")
    points: list[dict[str, Any]] = []
    seen: set[int] = set()
    cursor = start
    while cursor < end:
        chunk_end = min(cursor + timedelta(days=chunk_days), end)
        params = {
            "market": token_id,
            "startTs": int(cursor.timestamp()),
            "endTs": int(chunk_end.timestamp()),
            "fidelity": fidelity,
        }
        url = f"{base}{path}?{urllib.parse.urlencode(params)}"
        payload = getter(url)
        history = payload.get("history") if isinstance(payload, dict) else payload
        if isinstance(history, list):
            for row in history:
                t = row.get("t")
                p = row.get("p")
                if t is None or p is None:
                    continue
                ti = int(t)
                if ti in seen:
                    continue
                seen.add(ti)
                points.append({"t": ti, "p": p})
        cursor = chunk_end
        if pause_s:
            time.sleep(pause_s)
    points.sort(key=lambda r: int(r["t"]))
    return points


def sample_window(start_time: datetime, *, cfg: RollerConfig) -> tuple[datetime, datetime]:
    hist = (polymarket_cfg(cfg).get("price_history") or {})
    pre = int(hist.get("pre_start_hours") or 12)
    post = int(hist.get("post_start_hours") or 8)
    return start_time - timedelta(hours=pre), start_time + timedelta(hours=post)


def write_raw_prices(warehouse: Path, sport: str, token_id: str, points: list[dict[str, Any]]) -> Path:
    dest = warehouse_polymarket_prices(warehouse, sport, token_id)
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / "history.json"
    path.write_text(json.dumps({"token_id": token_id, "history": points}, indent=2) + "\n", encoding="utf-8")
    return path


def load_raw_prices(warehouse: Path, sport: str, token_id: str) -> list[dict[str, Any]]:
    path = warehouse_polymarket_prices(warehouse, sport, token_id) / "history.json"
    if not path.is_file():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    hist = payload.get("history") if isinstance(payload, dict) else payload
    return hist if isinstance(hist, list) else []


def price_to_e4(value: Any) -> str:
    if value in (None, ""):
        return ""
    return str(int(round(float(value) * 10000)))


def sample_iso(unix_ts: int) -> str:
    return to_iso(datetime.fromtimestamp(int(unix_ts), tz=UTC))


SLUG_PREFIX = {"NBA": "nba", "WNBA": "wnba", "NCAAB": "cbb"}

# Official Gamma slugs use these abbreviations. Only listed alternates.
SLUG_CODE_ALTERNATES = {
    "NBA": {"GSW": ["gsw", "gs"], "NOP": ["nop", "no"], "BKN": ["bkn", "bk"], "WAS": ["was", "wsh"]},
    "WNBA": {
        "CONN": ["conn"],
        "WSH": ["wsh", "was"],
        "NY": ["ny", "nyl"],
        "LV": ["lv", "lva"],
        "GS": ["gs", "gsv"],
        "LA": ["la", "las"],
        "PDX": ["pdx", "por"],
    },
    "NCAAB": {"CONN": ["uconn", "conn"]},
}


def slug_codes(sport: str, team_id: str) -> list[str]:
    tid = str(team_id or "").strip()
    alts = (SLUG_CODE_ALTERNATES.get(sport) or {}).get(tid.upper())
    if alts:
        return list(alts)
    return [tid.lower()]


def identity_slugs(sport: str, game_date: str, away_id: str, home_id: str) -> list[str]:
    prefix = SLUG_PREFIX[sport]
    date = str(game_date)[:10]
    slugs = []
    for away in slug_codes(sport, away_id):
        for home in slug_codes(sport, home_id):
            slugs.append(f"{prefix}-{away}-{home}-{date}")
    return slugs


def events_by_slugs(
    slugs: list[str],
    *,
    cfg: RollerConfig,
    http_get: HttpGet | None = None,
) -> list[dict[str, Any]]:
    if not slugs:
        return []
    pm = polymarket_cfg(cfg)
    getter = http_get or default_http_get
    base = str(pm.get("gamma_base") or "https://gamma-api.polymarket.com").rstrip("/")
    path = str(pm.get("events_path") or "/events")
    params = [("slug", s) for s in slugs]
    url = f"{base}{path}?{urllib.parse.urlencode(params)}"
    payload = getter(url)
    return payload if isinstance(payload, list) else []


def load_sport_warehouse(cfg: RollerConfig, sport: str, season: str) -> Path:
    _, _, wh = load_sport_games(cfg, sport, season)
    return wh
