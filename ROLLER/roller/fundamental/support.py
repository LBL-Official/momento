"""First-class support. Unique games ≠ observation count."""

from __future__ import annotations

from typing import Any

from roller.config import RollerConfig
from roller.fundamental.conditioning import support_floors
from roller.measurement.support import support_object


def fundamental_support(
    rows: list[dict[str, Any]],
    *,
    floors: dict[str, int] | None = None,
    cfg: RollerConfig | None = None,
) -> dict[str, Any]:
    req = floors or (support_floors(cfg) if cfg is not None else {
        "minimum_observations": 3,
        "minimum_unique_games": 2,
        "minimum_unique_dates": 1,
        "minimum_unique_seasons": 1,
    })
    base = support_object(
        rows,
        min_unique_games=int(req["minimum_unique_games"]),
        min_observations=int(req["minimum_observations"]),
    )
    sufficient = (
        bool(base["sufficient"])
        and int(base["n_unique_dates"]) >= int(req["minimum_unique_dates"])
        and int(base["n_unique_seasons"]) >= int(req["minimum_unique_seasons"])
    )
    base["sufficient"] = sufficient
    base["min_unique_dates"] = int(req["minimum_unique_dates"])
    base["min_unique_seasons"] = int(req["minimum_unique_seasons"])
    return base
