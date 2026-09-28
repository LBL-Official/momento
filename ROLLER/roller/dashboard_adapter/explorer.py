"""BBALL1 Explorer — What existed at I(t)?

Uses authoritative Roller.dataset(..., \"games\", as_of=...).
Does not assemble observations in bulk. Does not invent fields.
"""

from __future__ import annotations

from typing import Any

from roller import Roller
from roller.dashboard_adapter.serialize import dataframe_records, to_jsonable
from roller.point_in_time.filters import AsOfRequiredError

BBALL1_ID = "BBALL1"
INFORMATION_MODE_PIT = "POINT_IN_TIME"

# League → season keys from ROLLER/roller.json (V1 operational scope).
BBALL1_SPORT_SEASONS: list[tuple[str, str]] = [
    ("NBA", "2025-2026"),
    ("WNBA", "2025"),
    ("WNBA", "2026"),
    ("NCAAB", "2025-2026"),
]

# Identity / schedule only — no terminal outcomes in Explorer.
_EXPLORER_COLUMNS = [
    "internal_game_id",
    "sport",
    "season",
    "game_date",
    "scheduled_start",
    "home_team_id",
    "away_team_id",
    "home_team_name",
    "away_team_name",
    "event_ticker",
]


class ExplorerError(ValueError):
    """Explicit Explorer validation / binding failure."""


def list_universe_games(
    *,
    universe: str = BBALL1_ID,
    as_of: str | None = None,
    information_mode: str = INFORMATION_MODE_PIT,
    db: Roller | None = None,
) -> dict[str, Any]:
    """Return PIT-visible games for a universe at as_of.

    as_of is required. information_mode must be POINT_IN_TIME for Phase 1.
    """
    if as_of is None or str(as_of).strip() == "":
        raise ExplorerError("as_of is required for POINT-IN-TIME exploration")
    if information_mode != INFORMATION_MODE_PIT:
        raise ExplorerError(
            f"information_mode={information_mode!r} not supported in Phase 1; "
            f"use {INFORMATION_MODE_PIT}"
        )
    if universe != BBALL1_ID:
        raise ExplorerError(f"universe={universe!r} not available; Phase 1 supports {BBALL1_ID}")

    roller = db or Roller()
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    for sport, season in BBALL1_SPORT_SEASONS:
        try:
            games = roller.dataset(sport, season, "games", as_of=as_of)
        except AsOfRequiredError as exc:
            raise ExplorerError(str(exc)) from exc
        except (FileNotFoundError, KeyError) as exc:
            errors.append({"sport": sport, "season": season, "error": str(exc)})
            continue
        except Exception as exc:  # noqa: BLE001 — surface binding failure
            errors.append({"sport": sport, "season": season, "error": f"{type(exc).__name__}: {exc}"})
            continue
        part = dataframe_records(games, _EXPLORER_COLUMNS)
        rows.extend(part)

    return to_jsonable(
        {
            "universe": universe,
            "information_mode": INFORMATION_MODE_PIT,
            "as_of": as_of,
            "n_rows": len(rows),
            "rows": rows,
            "dataset_errors": errors,
            "caveats": [
                "POINT-IN-TIME MODE",
                "MEASUREMENT ≠ EDGE",
                "CANDLE PATH ≠ FILL",
                "Explorer lists games visible under I(t); outcomes are not exploration results",
            ],
        }
    )
