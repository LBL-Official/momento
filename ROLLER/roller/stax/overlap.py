"""Observation overlap. Independent definitions ≠ independent outcomes."""

from __future__ import annotations

from typing import Any


INDEPENDENCE_NOTE = (
    "Independent strategies are independently defined research objects. "
    "They are not statistically independent observations. "
    "Do not treat sum of strategy N as an independent population."
)


def _population(envelope: dict[str, Any]) -> dict[str, Any]:
    pop = envelope.get("population")
    return pop if isinstance(pop, dict) else {}


def _count(envelope: dict[str, Any]) -> int | None:
    pop = _population(envelope)
    if pop.get("count") is not None:
        return int(pop["count"])
    summary = envelope.get("summary") if isinstance(envelope.get("summary"), dict) else {}
    if summary.get("population_n") is not None:
        return int(summary["population_n"])
    return None


def game_ids_from_envelope(envelope: dict[str, Any]) -> tuple[set[str] | None, str]:
    """Return game ids only from a full population.

    Never treat the 200-row preview as N.
    """
    pop = _population(envelope)
    trades = pop.get("trades")
    n = _count(envelope)
    if isinstance(trades, list) and trades:
        if n is not None and len(trades) != n:
            return None, "UNAVAILABLE"
        ids = {
            str(row.get("internal_game_id"))
            for row in trades
            if isinstance(row, dict) and row.get("internal_game_id")
        }
        if not ids:
            return None, "UNAVAILABLE"
        return ids, "INTERNAL_GAME_ID"
    rows = pop.get("rows")
    if isinstance(rows, list) and rows:
        if pop.get("rows_truncated") or (n is not None and len(rows) != n):
            return None, "UNAVAILABLE"
        ids = {
            str(row.get("internal_game_id"))
            for row in rows
            if isinstance(row, dict) and row.get("internal_game_id")
        }
        if not ids:
            return None, "UNAVAILABLE"
        return ids, "INTERNAL_GAME_ID"
    return None, "UNAVAILABLE"


def compute_overlap(results: list[dict[str, Any]]) -> dict[str, Any]:
    per_member: dict[str, set[str]] = {}
    method = "INTERNAL_GAME_ID"
    available = True
    for row in results:
        mid = str(row.get("member_id") or "")
        env = row.get("envelope") if isinstance(row.get("envelope"), dict) else row
        ids, how = game_ids_from_envelope(env)
        if ids is None:
            available = False
            method = how
            continue
        per_member[mid] = ids
    if not available or len(per_member) < 2:
        return {
            "overlap_method": "UNAVAILABLE" if not available else method,
            "shared_game_count": None,
            "pairwise": [],
            "independence_claim": False,
            "note": INDEPENDENCE_NOTE,
        }
    ids_list = list(per_member.items())
    shared: set[str] | None = None
    for _mid, ids in ids_list:
        shared = ids if shared is None else shared & ids
    pairwise = []
    for i, (a_id, a_set) in enumerate(ids_list):
        for b_id, b_set in ids_list[i + 1 :]:
            inter = a_set & b_set
            union = a_set | b_set
            pairwise.append(
                {
                    "a": a_id,
                    "b": b_id,
                    "shared_game_count": len(inter),
                    "overlap_pct": (len(inter) / len(union)) if union else 0.0,
                    "a_n_games": len(a_set),
                    "b_n_games": len(b_set),
                }
            )
    return {
        "overlap_method": method,
        "shared_game_count": len(shared or ()),
        "pairwise": pairwise,
        "independence_claim": False,
        "note": INDEPENDENCE_NOTE,
    }
