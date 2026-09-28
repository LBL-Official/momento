"""Counting stats and labeled estimates. Missing advanced fields stay unavailable."""

from __future__ import annotations

from decimal import Decimal

COUNTS = ("FGM", "FGA", "FG3M", "FG3A", "FTM", "FTA", "OREB", "DREB", "REB", "AST", "TOV", "PTS")
ADVANCED = ("pace", "off_rating", "def_rating", "net_rating", "oreb_pct", "dreb_pct", "tov_pct")


def _number(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def aggregate(rows: list[dict]) -> dict:
    sums: dict[str, Decimal | None] = {}
    missing = []
    for field in COUNTS:
        values = [_number(row.get(field)) for row in rows]
        if not rows or any(item is None for item in values):
            sums[field] = None
            missing.append(field)
        else:
            sums[field] = sum(values, Decimal(0))
    for field in ADVANCED:
        if not rows or any(_number(row.get(field)) is None for row in rows):
            missing.append(field)
    derived = []
    fga = sums.get("FGA")
    fgm = sums.get("FGM")
    fg3m = sums.get("FG3M")
    fta = sums.get("FTA")
    pts = sums.get("PTS")
    if fga not in {None, 0} and fgm is not None and fg3m is not None:
        derived.append(
            {
                "name": "efg",
                "value": format((fgm + Decimal("0.5") * fg3m) / fga, "f"),
                "formula": "(FGM + 0.5*FG3M) / FGA",
                "label": "ESTIMATE",
            }
        )
    if fga is not None and fta is not None and pts is not None:
        denominator = 2 * (fga + Decimal("0.44") * fta)
        if denominator != 0:
            derived.append(
                {
                    "name": "true_shooting",
                    "value": format(pts / denominator, "f"),
                    "formula": "PTS / (2 * (FGA + 0.44*FTA))",
                    "label": "ESTIMATE",
                }
            )
    if fga not in {None, 0} and fta is not None:
        derived.append(
            {
                "name": "free_throw_rate",
                "value": format(fta / fga, "f"),
                "formula": "FTA / FGA",
                "label": "ESTIMATE",
            }
        )
    return {
        "games": len(rows),
        "sums": {key: None if value is None else format(value, "f") for key, value in sums.items()},
        "derived": derived,
        "missing": missing,
        "status": "FEATURE_UNAVAILABLE" if missing else "OK",
        "model_input": False,
    }
