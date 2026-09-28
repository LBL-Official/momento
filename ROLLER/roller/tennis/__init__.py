"""Tennis research adapter. Observation only. Not a trading system.

This package parses tennis play-by-play into a canonical, point-in-time-honest
shape and builds a deterministic crosswalk between charted matches and Kalshi
tennis events. Nothing here submits orders, prices contracts, or touches
FIRST01 / FIRST80 / Risk / W9 / SuperASI.

SOURCE AND LICENSE
------------------
The only PBP source wired up today is the Match Charting Project (MCP) by
Jeff Sackmann (https://github.com/JeffSackmann/tennis_MatchChartingProject),
licensed **CC BY-NC-SA 4.0**.

    NonCommercial: COMMERCIAL USE IS PROHIBITED.

Momento Systems LLC is building a commercial B2B/D2C product, so this source
is **research-only and must be replaced or separately licensed** before any
commercial use. Attribution to Jeff Sackmann is required, and ShareAlike
applies to derivatives. Every manifest written by this package must carry the
license fields; see ``roller.tennis.pbp.LICENSE_FIELDS``.

POINT-IN-TIME STATUS
--------------------
MCP point rows carry **no wall-clock timestamp**. They are ordered only by the
point ordinal ``Pt``. Therefore every MCP row is emitted with
``pbp_basis = "SEQUENCE_ONLY"``, ``pit_joinable = False`` and
``event_timestamp = None``. The matches-index ``Time`` column is an
inconsistent, mostly-empty match start time and MUST NOT be used to synthesize
point timestamps.
"""

from __future__ import annotations

__all__ = ["crosswalk", "names", "observability", "pbp", "snap", "state", "windows"]
