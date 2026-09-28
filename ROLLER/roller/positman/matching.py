"""Identity / time match. Exact fields only. Never invent IDs."""

from __future__ import annotations

from typing import Any

from roller.systimo.transitions.identity import extract_identity, match_identities


def match_siblings(ballhog: dict[str, Any], tk_ultra: dict[str, Any]) -> dict[str, Any]:
    left = extract_identity(ballhog.get("intent") if isinstance(ballhog.get("intent"), dict) else ballhog)
    right_src = tk_ultra.get("assessment") if isinstance(tk_ultra.get("assessment"), dict) else tk_ultra
    right = extract_identity(right_src)
    return match_identities(left, right)
