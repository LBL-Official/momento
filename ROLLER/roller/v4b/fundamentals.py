"""Adapt V4A db.fundamental() into exact rationals. Never mutate V4A."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from roller.config import RollerConfig
from roller.state.observation_id import make_observation_id
from roller.timeutil import parse_utc, to_iso
from roller.v4b.types import FundamentalView, as_int


def adapt_fundamental(row: dict[str, Any] | None) -> FundamentalView:
    row = row or {}
    value = row.get("value") if isinstance(row.get("value"), dict) else {}
    wins = as_int(row.get("probability_wins"))
    n = as_int(row.get("probability_n"))
    if wins is None:
        wins = as_int((value or {}).get("numerator"))
    if n is None:
        n = as_int((value or {}).get("denominator"))
    cutoff = row.get("information_cutoff") or row.get("observation_cutoff") or row.get("available_at")
    return FundamentalView(
        observation_id=row.get("observation_id"),
        cutoff=cutoff,
        available_at=row.get("available_at") or cutoff,
        status=str(row.get("status") or "INSUFFICIENT_SUPPORT"),
        wins=wins,
        n=n,
        condition_id=row.get("condition_id"),
    )


def observation_id_at(cfg: RollerConfig, internal_game_id: str, cutoff) -> str:
    cut = cutoff if isinstance(cutoff, datetime) else parse_utc(cutoff) or cutoff
    return make_observation_id(internal_game_id, cut, cfg.state_schema_version)


def fundamental_at_observation(
    fundamental_fn: Callable[[str], dict[str, Any]],
    observation_id: str,
) -> FundamentalView:
    return adapt_fundamental(fundamental_fn(observation_id))


def fundamental_at_cutoff(
    cfg: RollerConfig,
    *,
    internal_game_id: str,
    cutoff,
    fundamental_fn: Callable[[str], dict[str, Any]],
) -> FundamentalView:
    """New observation_id at this cutoff. Never reuse F_t under a new label."""
    oid = observation_id_at(cfg, internal_game_id, cutoff)
    view = fundamental_at_observation(fundamental_fn, oid)
    if view.cutoff is None:
        ts = cutoff if isinstance(cutoff, datetime) else parse_utc(cutoff)
        iso = to_iso(ts) if ts is not None else None
        view.cutoff = iso
        view.available_at = view.available_at or iso
    if view.observation_id is None:
        view.observation_id = oid
    return view
