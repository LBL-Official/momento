"""Sport capability matrix. Do not fabricate equivalence across sports."""

from __future__ import annotations

REAL = "REAL"
PARTIAL = "PARTIAL"
INCOMPLETE = "INCOMPLETE"
SCHEMA_ONLY = "SCHEMA_ONLY"
NOT_SUPPORTED = "NOT_SUPPORTED"

MATRIX = {
    "NBA": {
        "events": REAL,
        "player_id": REAL,
        "possessions": REAL,
        "player_state": REAL,
        "lineups": INCOMPLETE,
        "information": NOT_SUPPORTED,
        "market": REAL,
        "labels": REAL,
    },
    "WNBA": {
        "events": REAL,
        "player_id": SCHEMA_ONLY,
        "possessions": PARTIAL,
        "player_state": NOT_SUPPORTED,
        "lineups": SCHEMA_ONLY,
        "information": SCHEMA_ONLY,
        "market": REAL,
        "labels": REAL,
    },
    "NCAAB": {
        "events": REAL,
        "player_id": SCHEMA_ONLY,
        "possessions": PARTIAL,
        "player_state": NOT_SUPPORTED,
        "lineups": SCHEMA_ONLY,
        "information": SCHEMA_ONLY,
        "market": REAL,
        "labels": REAL,
    },
}


def capability(sport: str, family: str) -> str:
    return MATRIX.get(sport, {}).get(family, NOT_SUPPORTED)
