"""Bernoulli stop failures. Outcomes are not an input to the draw."""

from __future__ import annotations

import random


def fails(instance_id: str, seed: int, probability: float) -> bool:
    rng = random.Random(f"{seed}:{instance_id}")
    return rng.random() < float(probability)


def apply_failures(candidates: list[dict], *, probability: float, seed: int) -> list[dict]:
    out = []
    for cand in candidates:
        nxt = dict(cand)
        if cand.get("exit_reason") == "STOP" and fails(str(cand["game_id"]), seed, probability):
            nxt["stop_failed"] = True
            result = cand.get("terminal_result")
            settlement = cand.get("settlement_ts")
            action = int(cand.get("action_ts") or cand["signal_ts"])
            if result in {"yes", "no"} and settlement is not None and int(settlement) >= action:
                nxt["exit_reason"] = "WIN_SETTLEMENT" if result == "yes" else "LOSS_SETTLEMENT"
                nxt["exit_ts"] = int(settlement)
                nxt["cash_ts"] = int(settlement)
            else:
                nxt["exit_reason"] = "UNRESOLVED"
                nxt["exit_ts"] = None
                nxt["cash_ts"] = None
        else:
            nxt["stop_failed"] = False
        out.append(nxt)
    return out


def enumerate_four(probability: float) -> dict:
    """All 16 failure patterns on four independent stops."""
    patterns = []
    any_fail = 0.0
    for mask in range(16):
        bits = [(mask >> i) & 1 for i in range(4)]
        k = sum(bits)
        prob = (probability ** k) * ((1 - probability) ** (4 - k))
        patterns.append({"mask": bits, "probability": prob})
        if k:
            any_fail += prob
    return {
        "pattern_count": len(patterns),
        "probability_sum": sum(row["probability"] for row in patterns),
        "p_any_failure": any_fail,
        "closed_form": 1 - (1 - probability) ** 4,
    }
