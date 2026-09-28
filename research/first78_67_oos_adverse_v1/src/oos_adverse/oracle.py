"""Oracle bounds. Baseline scenario ids must not call this module."""

from __future__ import annotations

import math
import random
from decimal import Decimal

from first78.money import fee_charged_cents, fee_raw

FEE = Decimal("0.0175")


def _one_contract_net(exit_reason: str, entry: int = 78, stop: int = 67, coef: Decimal = FEE) -> int | None:
    if exit_reason == "STOP":
        entry_fee = fee_charged_cents(fee_raw(1, entry, coef))
        stop_fee = fee_charged_cents(fee_raw(1, stop, coef))
        return (stop - entry) - entry_fee - stop_fee
    if exit_reason == "WIN_SETTLEMENT":
        entry_fee = fee_charged_cents(fee_raw(1, entry, coef))
        return (100 - entry) - entry_fee
    if exit_reason == "LOSS_SETTLEMENT":
        entry_fee = fee_charged_cents(fee_raw(1, entry, coef))
        return (0 - entry) - entry_fee
    return None


def assert_baseline(scenario_id: str) -> None:
    if str(scenario_id).startswith("ORACLE"):
        raise RuntimeError("oracle module cannot run under a baseline scenario id")


def worst_acceptance(candidates: list[dict], fraction: float) -> list[dict]:
    """Keep the worst equal-contract outcomes within each sport. Uses future exits."""
    if fraction >= 1:
        return list(candidates)
    chosen = []
    sports = sorted({c["sport"] for c in candidates})
    for sport in sports:
        group = [c for c in candidates if c["sport"] == sport]
        k = max(0, math.ceil(fraction * len(group)))
        ranked = sorted(
            group,
            key=lambda c: (
                _one_contract_net(c["exit_reason"]) if _one_contract_net(c["exit_reason"]) is not None else 0,
                str(c["contract_id"]),
            ),
        )
        chosen.extend(ranked[:k])
    return chosen


def random_acceptance(candidates: list[dict], fraction: float, seed: int) -> list[dict]:
    rng = random.Random(seed)
    chosen = []
    for sport in sorted({c["sport"] for c in candidates}):
        group = [c for c in candidates if c["sport"] == sport]
        k = len(group) if fraction >= 1 else max(0, math.ceil(fraction * len(group)))
        picks = group[:]
        rng.shuffle(picks)
        chosen.extend(picks[:k])
    return chosen


def oracle_tail_ids(stops: list[dict], rate: float = 0.05) -> list[str]:
    """Concentrate a rate-sized failure quota on contracts that later settle no."""
    losers = [s for s in stops if str(s.get("terminal_result")) == "no"]
    losers.sort(key=lambda s: str(s["contract_id"]))
    k = int(Decimal(len(stops)) * Decimal(str(rate)) + Decimal("0.5"))
    return [str(s["game_id"]) for s in losers[:k]]


def stop_fail_ids(stops: list[dict], rate: float, seed: int) -> list[str]:
    """Choose failures from ids and the seed. Outcomes are not an input."""
    rng = random.Random(seed)
    ids = [str(s["game_id"]) for s in stops]
    rng.shuffle(ids)
    k = int(Decimal(len(ids)) * Decimal(str(rate)) + Decimal("0.5"))
    return ids[:k]
