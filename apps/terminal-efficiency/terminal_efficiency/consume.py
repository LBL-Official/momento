"""Compatibility inspect entry. Delegates to the read-only consumption loader."""

from __future__ import annotations

from terminal_efficiency.consumption.loader import FrozenObjectLoader
from terminal_efficiency.frozen_artifacts.registry import resolve_published


def inspect_frozen(league: str, season: str, *, model_version: str | None = None) -> dict:
    identity, _ = resolve_published(league=league, season=season, model_version=model_version)
    return FrozenObjectLoader().inspect(identity)
