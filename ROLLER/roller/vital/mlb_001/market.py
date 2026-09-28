"""Parse a Kalshi MLB ticker into a human game label. Missing stays unavailable."""

from __future__ import annotations

from typing import Any

_MON = {
    "JAN": "01",
    "FEB": "02",
    "MAR": "03",
    "APR": "04",
    "MAY": "05",
    "JUN": "06",
    "JUL": "07",
    "AUG": "08",
    "SEP": "09",
    "OCT": "10",
    "NOV": "11",
    "DEC": "12",
}


def parse_mlb_ticker(ticker: str | None) -> dict[str, Any] | None:
    """KXMLBGAME-26AUG291915TEXMIL-MIL → TEX @ MIL YES MIL.

    Date-only or unparseable tokens return None. Does not invent teams.
    """
    text = str(ticker or "").strip().upper()
    if not text.startswith("KXMLBGAME-"):
        return None
    parts = text.split("-")
    if len(parts) < 2:
        return None
    token = parts[1]
    if len(token) < 7:
        return None
    yy, mon, dd = token[:2], token[2:5], token[5:7]
    month = _MON.get(mon)
    if month is None or not yy.isdigit() or not dd.isdigit():
        return None
    day_n = int(dd)
    if day_n < 1 or day_n > 31:
        return None
    rest = token[7:]
    away = home = None
    hhmm = None
    teams = None
    if len(rest) >= 4 and rest[:4].isdigit():
        hhmm = rest[:4]
        teams = rest[4:]
    elif rest.isalpha():
        teams = rest
    side = None
    if len(parts) >= 3 and parts[2].isalpha() and 2 <= len(parts[2]) <= 4:
        side = parts[2]
    if teams:
        if len(teams) > 2 and teams[-2] == "G" and teams[-1].isdigit():
            teams = teams[:-2]
        if not teams.isalpha():
            teams = None
    if teams:
        if len(teams) == 6:
            away, home = teams[:3], teams[3:6]
        elif side and teams.endswith(side) and 2 <= len(teams) - len(side) <= 4:
            away, home = teams[: -len(side)], side
        elif side and teams.startswith(side) and 2 <= len(teams) - len(side) <= 4:
            away, home = side, teams[len(side) :]
    if away is None or home is None:
        return None
    label = f"{away} @ {home}"
    if side:
        label = f"{label} YES {side}"
    return {
        "date": f"{2000 + int(yy)}-{month}-{dd}",
        "away": away,
        "home": home,
        "side": side,
        "hhmm": hhmm,
        "label": label,
    }


def game_label(ticker: str | None) -> str | None:
    parsed = parse_mlb_ticker(ticker)
    if parsed is None:
        return None
    return str(parsed["label"])
