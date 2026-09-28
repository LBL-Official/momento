"""Empirical baseline label and a small snapshot diagnostic. Not an entry rule."""

from __future__ import annotations

import math
import random


def empirical_baseline_label() -> dict:
    return {
        "name": "ENTRY_CELL_OUTCOME_FREQUENCY",
        "role": "empirical baseline",
        "not": "predictive alpha or a regime-switching simulator",
        "changes_entries": False,
    }


def snapshot_rows(candidates: list[dict]) -> list[dict]:
    rows = []
    for cand in candidates:
        bars = cand.get("bars") or []
        action = int(cand["action_ts"])
        end = cand.get("exit_ts")
        if end is None:
            continue
        window = [bar for bar in bars if action <= int(bar["ts"]) <= int(end)]
        if len(window) < 2:
            continue
        bids = [int(bar["bid"]) / 100 for bar in window]
        trailing = bids[-5:]
        mean = sum(trailing) / len(trailing)
        var = sum((x - mean) ** 2 for x in trailing) / len(trailing)
        rows.append(
            {
                "game_id": cand["game_id"],
                "local_day": cand["local_day"],
                "price_cents": bids[-1],
                "distance_to_stop_cents": bids[-1] - 67,
                "trailing_vol": math.sqrt(var),
                "duration_seconds": int(end) - action,
                "event": cand["exit_reason"],
                "clock_availability": "MODELED_AVAILABILITY",
            }
        )
    return rows


def validate_snapshots(candidates: list[dict], *, resamples: int = 20, seed: int = 1) -> dict:
    rows = snapshot_rows(candidates)
    if len(rows) < 8:
        return {"status": "BLOCKED_DATA", "reason": "fewer than 8 snapshot rows", "rows": len(rows), "changes_entries": False}
    games = []
    seen = set()
    for row in sorted(rows, key=lambda item: (item["local_day"], item["game_id"])):
        if row["game_id"] not in seen:
            seen.add(row["game_id"])
            games.append(row["game_id"])
    cut = max(1, int(len(games) * 0.7))
    train_ids = set(games[:cut])
    test_ids = set(games[cut:])
    if not test_ids:
        return {"status": "BLOCKED_DATA", "reason": "no time-separated games", "rows": len(rows), "changes_entries": False}
    train = [row for row in rows if row["game_id"] in train_ids]
    test = [row for row in rows if row["game_id"] in test_ids]
    base = sum(1 for row in train if row["event"] == "STOP") / len(train)

    def brier(sample, rate):
        return sum((rate - (1 if row["event"] == "STOP" else 0)) ** 2 for row in sample) / len(sample)

    rng = random.Random(seed)
    nested = []
    train_games = sorted(train_ids)
    for _ in range(resamples):
        picked = [train_games[rng.randrange(len(train_games))] for _ in train_games]
        sample = [row for row in train if row["game_id"] in set(picked)] or train
        rate = sum(1 for row in sample if row["event"] == "STOP") / len(sample)
        nested.append(brier(test, rate))
    return {
        "status": "BACKWARD_OR_WITHIN_WINDOW_DIAGNOSTIC",
        "changes_entries": False,
        "rows": len(rows),
        "train_games": len(train_ids),
        "test_games": len(test_ids),
        "training_stop_rate": base,
        "test_brier_training_rate": brier(test, base),
        "test_brier_half": brier(test, 0.5),
        "nested_refits": resamples,
        "nested_test_brier_mean": sum(nested) / len(nested),
        "duration": "exit timestamp minus action timestamp",
        "resolution_jumps": "volatility uses bids at or before the exit and does not append a settlement print",
    }
