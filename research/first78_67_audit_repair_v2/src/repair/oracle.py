"""Oracle bounds. Baseline scenario ids cannot import this module's runners."""

from __future__ import annotations

import math
import random

from repair.ledger import replay


def one_contract_net(cand: dict) -> int:
    entry = int(cand.get("entry_price_cents") or 78)
    if cand.get("exit_reason") == "STOP":
        stop = int(cand.get("stop_price_cents") or 67)
        return (stop - entry) - 1
    if cand.get("terminal_result") == "yes":
        return 100 - entry
    if cand.get("terminal_result") == "no":
        return -entry
    return 0


def worst_ids(candidates: list[dict], fraction: float) -> list[str]:
    by_sport: dict[str, list[dict]] = {}
    for cand in candidates:
        by_sport.setdefault(str(cand.get("sport") or "ALL"), []).append(cand)
    chosen = []
    for sport, rows in by_sport.items():
        ranked = sorted(rows, key=lambda row: (one_contract_net(row), str(row["contract_id"])))
        if fraction >= 1:
            keep = len(ranked)
        else:
            keep = math.ceil(fraction * len(ranked))
        chosen.extend(row["game_id"] for row in ranked[:keep])
    return chosen


def replay_ids(candidates: list[dict], ids: list[str], *, balance_cents: int = 2_000_000):
    chosen = {str(i) for i in ids}
    rows = [dict(row, entry_price_cents=78, stop_price_cents=67) for row in candidates if row["game_id"] in chosen]
    return replay(rows, balance_cents=balance_cents)


def oracle_tail(candidates: list[dict], *, probability: float = 0.05, seed: int = 1) -> dict:
    """Not used by baseline play(). Concentrates a Bernoulli draw only among later losers."""
    losers = [c for c in candidates if c.get("exit_reason") == "STOP" and c.get("terminal_result") == "no"]
    rng = random.Random(seed)
    failed = [c["game_id"] for c in losers if rng.random() < probability]
    return {"label": "ORACLE_TAIL_BOUND", "executable": False, "failed_ids": failed, "probability": probability}
