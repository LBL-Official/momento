"""Momento 19-system architecture freeze (15 tournament + 4 infrastructure).

Ownership map + /momento façade. Does not execute trades.

LIVE EXECUTION = FALSE
NO NBA SUBMISSION IMPLEMENTATION
"""

from __future__ import annotations

from roller.momento.bracket import BRACKET_EDGES, INFRA_EDGES, assert_acyclic
from roller.momento.registry import (
    CANONICAL_IDS,
    LIVE_EXECUTION,
    REGISTRY_SCHEMA,
    SYSTEM_COUNT,
    SystemRecord,
    load_registry,
)

__all__ = (
    "BRACKET_EDGES",
    "CANONICAL_IDS",
    "INFRA_EDGES",
    "LIVE_EXECUTION",
    "REGISTRY_SCHEMA",
    "SYSTEM_COUNT",
    "SystemRecord",
    "assert_acyclic",
    "load_registry",
)
