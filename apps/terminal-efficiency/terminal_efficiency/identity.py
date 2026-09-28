"""Documented Kalshi ticker parse for alignment only. AMBIGUOUS if not unique."""

from __future__ import annotations

from datetime import datetime

_MONTHS = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}


def parse_kxnbagame_ticker(ticker: str) -> dict | None:
    """KXNBAGAME-25APR20MIACLE-CLE → date + two 3-letter codes if parseable."""
    t = str(ticker or "")
    if "KXNBAGAME-" not in t:
        return None
    rest = t.split("KXNBAGAME-", 1)[1]
    event = rest.split("-")[0]
    if len(event) < 13:
        return None
    yy, mon, dd = event[:2], event[2:5], event[5:7]
    teams = event[7:]
    if mon not in _MONTHS or len(teams) != 6:
        return None
    try:
        year = 2000 + int(yy)
        day = int(dd)
        game_date = datetime(year, _MONTHS[mon], day).date().isoformat()
    except ValueError:
        return None
    return {"game_date": game_date, "team_a": teams[:3], "team_b": teams[3:6]}


def build_game_key_map(games) -> dict[tuple[str, frozenset], str]:
    mp: dict[tuple[str, frozenset], list[str]] = {}
    for g in games.to_dict("records"):
        key = (str(g.get("game_date"))[:10], frozenset({str(g.get("home_team_id")), str(g.get("away_team_id"))}))
        mp.setdefault(key, []).append(str(g["game_id"]))
    out = {}
    for k, ids in mp.items():
        if len(ids) == 1:
            out[k] = ids[0]
    return out


def ticker_to_game_id(ticker: str, key_map: dict[tuple[str, frozenset], str]) -> str | None:
    parsed = parse_kxnbagame_ticker(ticker)
    if not parsed:
        return None
    key = (parsed["game_date"], frozenset({parsed["team_a"], parsed["team_b"]}))
    return key_map.get(key)
