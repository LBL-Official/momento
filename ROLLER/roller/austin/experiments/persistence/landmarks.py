"""Predetermined t0/t1/t2/t3 landmarks. Missing later states are not persistence."""

from __future__ import annotations

from typing import Any

from roller.austin.experiments.persistence.ids import (
    LANDMARK_T0,
    LANDMARK_T0_ONLY,
    LANDMARK_T0_T1,
    LANDMARK_T0_T1_T2,
    LANDMARK_T0_T1_T2_T3,
)
from roller.austin.experiments.persistence.util import as_float


def valid_steps(event: dict[str, Any]) -> list[dict[str, Any]]:
    return [event["_first"], *event["_later_valid"]]


def landmark_states(event: dict[str, Any]) -> dict[str, dict[str, Any] | None]:
    steps = valid_steps(event)
    return {
        "t0": steps[0] if steps else None,
        "t1": steps[1] if len(steps) > 1 else None,
        "t2": steps[2] if len(steps) > 2 else None,
        "t3": steps[3] if len(steps) > 3 else None,
    }


def _neg(row: dict[str, Any] | None) -> bool | None:
    if row is None:
        return None
    ev = as_float(row.get("conditional_ev_cents"))
    if ev is None:
        return None
    return ev < 0


def assign_landmarks(event: dict[str, Any]) -> dict[str, bool]:
    states = landmark_states(event)
    t0, t1, t2, t3 = states["t0"], states["t1"], states["t2"], states["t3"]
    return {
        LANDMARK_T0: bool(_neg(t0)),
        LANDMARK_T0_ONLY: bool(_neg(t0) and t1 is not None and _neg(t1) is False),
        LANDMARK_T0_T1: bool(_neg(t0) and t1 is not None and _neg(t1)),
        LANDMARK_T0_T1_T2: bool(_neg(t0) and t1 is not None and t2 is not None and _neg(t1) and _neg(t2)),
        LANDMARK_T0_T1_T2_T3: bool(
            _neg(t0) and t1 is not None and t2 is not None and t3 is not None and _neg(t1) and _neg(t2) and _neg(t3)
        ),
    }


def summarize_group(events: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(events)
    wins = sum(1 for e in events if e.get("won"))
    losses = n - wins
    holds = [float(e["pnl_hold_after_first_negative"]) for e in events if e.get("pnl_hold_after_first_negative") is not None]
    maes = [float(e["future_MAE"]) for e in events if e.get("future_MAE") is not None]
    mfes = [float(e["future_MFE"]) for e in events if e.get("future_MFE") is not None]

    def _rate(key: str) -> float | None:
        known = [e for e in events if e.get(key) is not None]
        if not known:
            return None
        return sum(1 for e in known if e.get(key)) / len(known)

    return {
        "N_trades": n,
        "N_wins": wins,
        "N_losses": losses,
        "win_rate": None if not n else wins / n,
        "loss_rate": None if not n else losses / n,
        "mean_pnl_hold_after_t0": None if not holds else sum(holds) / len(holds),
        "median_pnl_hold_after_t0": None if not holds else float(sorted(holds)[len(holds) // 2] if len(holds) % 2 else (sorted(holds)[len(holds) // 2 - 1] + sorted(holds)[len(holds) // 2]) / 2),
        "T40_rate": _rate("future_T40"),
        "mean_future_MAE": None if not maes else sum(maes) / len(maes),
        "median_future_MAE": None if not maes else float(sorted(maes)[len(maes) // 2]),
        "mean_future_MFE": None if not mfes else sum(mfes) / len(mfes),
        "median_future_MFE": None if not mfes else float(sorted(mfes)[len(mfes) // 2]),
        "recover_ge_50": _rate("future_recover_ge_50"),
        "recover_ge_60": _rate("future_recover_ge_60"),
        "recover_ge_70": _rate("future_recover_ge_70"),
        "recover_ge_80": _rate("future_recover_ge_80"),
    }


def landmark_tables(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    labeled = [(e, assign_landmarks(e)) for e in events]
    n_t0 = sum(1 for e in events if landmark_states(e)["t0"] is not None)
    n_t1 = sum(1 for e in events if landmark_states(e)["t1"] is not None)
    n_t2 = sum(1 for e in events if landmark_states(e)["t2"] is not None)
    n_t3 = sum(1 for e in events if landmark_states(e)["t3"] is not None)
    rows = []
    for name in (LANDMARK_T0, LANDMARK_T0_T1, LANDMARK_T0_T1_T2, LANDMARK_T0_T1_T2_T3):
        group = [e for e, flags in labeled if flags[name]]
        row = summarize_group(group)
        row["landmark"] = name
        row["note"] = "descriptive nested group; not a partition; not a policy"
        rows.append(row)
    return [
        {
            "availability": {"N_with_t0": n_t0, "N_with_t1": n_t1, "N_with_t2": n_t2, "N_with_t3": n_t3},
            "groups": rows,
        }
    ]


LANDMARK_FIELDS = [
    "source_experiment_id",
    "landmark",
    "N_trades",
    "N_wins",
    "N_losses",
    "win_rate",
    "loss_rate",
    "mean_pnl_hold_after_t0",
    "median_pnl_hold_after_t0",
    "T40_rate",
    "mean_future_MAE",
    "median_future_MAE",
    "mean_future_MFE",
    "median_future_MFE",
    "recover_ge_50",
    "recover_ge_60",
    "recover_ge_70",
    "recover_ge_80",
    "note",
]


def flatten_landmarks(experiment_id: str, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    payload = landmark_tables(events)[0]
    out = []
    for row in payload["groups"]:
        out.append({"source_experiment_id": experiment_id, **row})
    return out
