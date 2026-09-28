"""Leave-one-game-out Jeffreys predictions. Same-game never enters the training table."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from roller.austin.errors import AustinError
from roller.austin.experiments.hazard.beta import jeffreys_estimate
from roller.austin.experiments.hazard.ids import H0, H1, H2, NOT_APPLICABLE, TARGETS

PREFIX = {
    "TARGET_terminal_loss": "terminal_loss",
    "TARGET_recovery_t1": "recovery_t1",
    "TARGET_recovery_by_t2": "recovery_by_t2",
    "TARGET_recovery_by_t3": "recovery_by_t3",
    "TARGET_deeper_distress_next": "deeper_distress_next",
}


def _key(row: dict[str, Any], family: str) -> tuple:
    if family == H0:
        return (row.get("source_experiment_id"),)
    if family == H1:
        return (row.get("source_experiment_id"), row.get("core_state"))
    if family == H2:
        return (row.get("source_experiment_id"), row.get("core_state"), row.get("CI_state"))
    raise AustinError("LOCK_MISMATCH", f"unknown family {family}")


def _game_id(row: dict[str, Any]) -> str:
    return str(row.get("internal_game_id") or row.get("trade_id"))


def _counts_by_game(rows: list[dict[str, Any]], target: str, family: str) -> dict[str, dict[tuple, list[int]]]:
    by_game: dict[str, dict[tuple, list[int]]] = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for row in rows:
        val = row.get(target)
        if val in (None, NOT_APPLICABLE):
            continue
        key = _key(row, family)
        cell = by_game[_game_id(row)][key]
        cell[0] += int(val)
        cell[1] += 1
    return by_game


def _total(by_game: dict[str, dict[tuple, list[int]]]) -> dict[tuple, list[int]]:
    total: dict[tuple, list[int]] = defaultdict(lambda: [0, 0])
    for cells in by_game.values():
        for key, (y, n) in cells.items():
            total[key][0] += y
            total[key][1] += n
    return total


def predict_family(
    rows: list[dict[str, Any]],
    *,
    family: str,
    target: str,
) -> list[dict[str, Any]]:
    by_game = _counts_by_game(rows, target, family)
    total = _total(by_game)
    games = {_game_id(r) for r in rows}
    out = []
    for row in rows:
        gid = _game_id(row)
        held = by_game.get(gid) or {}
        val = row.get(target)
        key = _key(row, family)
        if val in (None, NOT_APPLICABLE):
            est = jeffreys_estimate(0, 0)
            est["p_hat"] = None
            est["status"] = "UNAVAILABLE" if val is None else NOT_APPLICABLE
        else:
            y, n = total.get(key, [0, 0])
            hy, hn = held.get(key, [0, 0])
            est = jeffreys_estimate(y - hy, n - hn)
        prefix = PREFIX[target]
        out.append(
            {
                "trade_id": row["trade_id"],
                "internal_game_id": row.get("internal_game_id"),
                "source_experiment_id": row.get("source_experiment_id"),
                "core_state": row.get("core_state"),
                "CI_state": row.get("CI_state"),
                "family": family,
                "target": target,
                "scoring_internal_game_id": gid,
                "training_game_count": len(games) - (1 if gid in games else 0),
                "same_game_present_in_training": False,
                "conditioning_key": str(key),
                "p_hat": est["p_hat"],
                "support_n": est["support_n"],
                "event_n": est["event_n"],
                "posterior_lower": est["posterior_lower"],
                "posterior_upper": est["posterior_upper"],
                "status": est["status"],
                f"p_{prefix}_{family}": est["p_hat"],
                f"support_n_{prefix}_{family}": est["support_n"],
                f"event_n_{prefix}_{family}": est["event_n"],
                f"posterior_lower_{prefix}_{family}": est["posterior_lower"],
                f"posterior_upper_{prefix}_{family}": est["posterior_upper"],
            }
        )
    if any(r.get("same_game_present_in_training") for r in out):
        raise AustinError("LOCK_MISMATCH", "LOGO same_game_present_in_training")
    return out


def attach_predictions(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    attached = [dict(r) for r in rows]
    index = {(r["trade_id"], r["core_state"], r.get("source_experiment_id")): r for r in attached}
    if len(index) != len(attached):
        raise AustinError("LOCK_MISMATCH", "first trade x core_state entries are not unique")
    for family in (H0, H1, H2):
        for target in TARGETS:
            for pred in predict_family(rows, family=family, target=target):
                dest = index[(pred["trade_id"], pred["core_state"], pred.get("source_experiment_id"))]
                dest.update(
                    {
                        k: v
                        for k, v in pred.items()
                        if k.startswith("p_")
                        or k.startswith("support_n_")
                        or k.startswith("event_n_")
                        or k.startswith("posterior_")
                    }
                )
    return attached


def crossfit_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for family in (H0, H1, H2):
        for target in TARGETS:
            out.extend(predict_family(rows, family=family, target=target))
    return out
