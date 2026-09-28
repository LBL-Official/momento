"""Temporary vs persistent contrasts. Trade-level. A and B stay separate."""

from __future__ import annotations

from typing import Any

import numpy as np

from roller.austin.experiments.persistence.ids import (
    BOOTSTRAP_B,
    BOOTSTRAP_SEED,
    PERSISTENT_NEGATIVE_EV,
    PIT_KEYS,
    TEMPORARY_NEGATIVE_EV,
    UNRESOLVED_NO_LATER_VALID_EV,
)
from roller.austin.experiments.persistence.landmarks import landmark_states, summarize_group
from roller.austin.experiments.persistence.util import as_float
from roller.austin.experiments.statistics import clustered_mean_diff


def _cohens_d(a: list[float], b: list[float]) -> float | None:
    if len(a) < 2 or len(b) < 2:
        return None
    va = float(np.var(a, ddof=1))
    vb = float(np.var(b, ddof=1))
    pooled = ((len(a) - 1) * va + (len(b) - 1) * vb) / (len(a) + len(b) - 2)
    if pooled <= 0:
        return None
    return (float(np.mean(b)) - float(np.mean(a))) / float(np.sqrt(pooled))


def _status(ci: dict[str, Any], *, n_a: int, n_b: int) -> str:
    if n_a < 2 or n_b < 2:
        return "INSUFFICIENT_SAMPLE"
    if ci.get("observed_delta") is None:
        return "INSUFFICIENT_SAMPLE"
    if ci.get("excludes_zero"):
        return "SUPPORTED"
    return "MIXED"


def class_split(events: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    return {
        TEMPORARY_NEGATIVE_EV: [e for e in events if e["negative_ev_class"] == TEMPORARY_NEGATIVE_EV],
        PERSISTENT_NEGATIVE_EV: [e for e in events if e["negative_ev_class"] == PERSISTENT_NEGATIVE_EV],
        UNRESOLVED_NO_LATER_VALID_EV: [e for e in events if e["negative_ev_class"] == UNRESOLVED_NO_LATER_VALID_EV],
    }


def _mean(values: list[float]) -> float | None:
    return None if not values else float(np.mean(values))


def _median(values: list[float]) -> float | None:
    return None if not values else float(np.median(values))


def economics_block(events: list[dict[str, Any]]) -> dict[str, Any]:
    split = class_split(events)
    temp = split[TEMPORARY_NEGATIVE_EV]
    pers = split[PERSISTENT_NEGATIVE_EV]
    rows = temp + pers
    for row in rows:
        row["_loss"] = 0.0 if row.get("won") else 1.0
        row["_t40"] = 1.0 if row.get("future_T40") else 0.0
    contrasts = {}
    for key, name in (
        ("pnl_hold_after_first_negative", "pnl"),
        ("_loss", "loss_rate"),
        ("_t40", "t40"),
        ("future_MAE", "mae"),
        ("future_MFE", "mfe"),
    ):
        ci = clustered_mean_diff(
            rows,
            value_key=key,
            positive_pred=lambda r, k=PERSISTENT_NEGATIVE_EV: r["negative_ev_class"] == k,
            negative_pred=lambda r, k=TEMPORARY_NEGATIVE_EV: r["negative_ev_class"] == k,
            seed=BOOTSTRAP_SEED,
            draws=BOOTSTRAP_B,
        )
        contrasts[name] = {
            **ci,
            "contrast": "PERSISTENT - TEMPORARY",
            "classification": _status(ci, n_a=len(temp), n_b=len(pers)),
        }
    return {
        "n_first_negative": len(events),
        "n_temporary": len(temp),
        "n_persistent": len(pers),
        "n_unresolved": len(split[UNRESOLVED_NO_LATER_VALID_EV]),
        "temporary": summarize_group(temp),
        "persistent": summarize_group(pers),
        "unresolved": summarize_group(split[UNRESOLVED_NO_LATER_VALID_EV]),
        "persistent_minus_temporary": contrasts,
        "temporary_means": _class_means(temp),
        "persistent_means": _class_means(pers),
    }


def _class_means(events: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "mean_first_negative_EV": _mean([float(e["first_negative_EV"]) for e in events if e.get("first_negative_EV") is not None]),
        "median_first_negative_EV": _median([float(e["first_negative_EV"]) for e in events if e.get("first_negative_EV") is not None]),
        "mean_EV_deterioration_from_entry": _mean(
            [float(e["EV_change_from_entry"]) for e in events if e.get("EV_change_from_entry") is not None]
        ),
        "median_EV_deterioration_from_entry": _median(
            [float(e["EV_change_from_entry"]) for e in events if e.get("EV_change_from_entry") is not None]
        ),
        "mean_price_at_first_negative": _mean(
            [float(e["first_negative_price"]) for e in events if e.get("first_negative_price") is not None]
        ),
        "median_price_at_first_negative": _median(
            [float(e["first_negative_price"]) for e in events if e.get("first_negative_price") is not None]
        ),
        "mean_price_travel": _mean([float(e["price_travel"]) for e in events if e.get("price_travel") is not None]),
        "mean_game_time_remaining": _mean(
            [float(e["game_time_remaining"]) for e in events if e.get("game_time_remaining") is not None]
        ),
        "mean_ESS": _mean([float(e["ESS"]) for e in events if e.get("ESS") is not None]),
        "mean_median_distance": _mean(
            [float(e["median_distance"]) for e in events if e.get("median_distance") is not None]
        ),
    }


def pit_feature_comparison(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    temp = [e for e in events if e["negative_ev_class"] == TEMPORARY_NEGATIVE_EV]
    pers = [e for e in events if e["negative_ev_class"] == PERSISTENT_NEGATIVE_EV]
    keys = list(PIT_KEYS) + ["CI_ENTIRELY_NEGATIVE"]
    rows = []
    for key in keys:
        def values(group: list[dict[str, Any]]) -> list[float]:
            out = []
            for event in group:
                pit = event.get("pit") or {}
                val = pit.get(key)
                if isinstance(val, bool):
                    out.append(1.0 if val else 0.0)
                elif val is not None:
                    out.append(float(val))
            return out

        tv = values(temp)
        pv = values(pers)
        labeled = []
        for event in temp + pers:
            pit = event.get("pit") or {}
            val = pit.get(key)
            if val is None:
                continue
            num = 1.0 if isinstance(val, bool) and val else (0.0 if isinstance(val, bool) else float(val))
            labeled.append(
                {
                    "internal_game_id": event.get("internal_game_id"),
                    "negative_ev_class": event["negative_ev_class"],
                    "value": num,
                }
            )
        ci = clustered_mean_diff(
            labeled,
            value_key="value",
            positive_pred=lambda r: r["negative_ev_class"] == PERSISTENT_NEGATIVE_EV,
            negative_pred=lambda r: r["negative_ev_class"] == TEMPORARY_NEGATIVE_EV,
            seed=BOOTSTRAP_SEED,
            draws=BOOTSTRAP_B,
        )
        rows.append(
            {
                "feature": key,
                "temporary_n": len(tv),
                "persistent_n": len(pv),
                "temporary_mean": _mean(tv),
                "temporary_median": _median(tv),
                "persistent_mean": _mean(pv),
                "persistent_median": _median(pv),
                "difference": None if not tv or not pv else _mean(pv) - _mean(tv),
                "ci": ci.get("ci"),
                "effect_size": _cohens_d(tv, pv),
                "classification": _status(ci, n_a=len(tv), n_b=len(pv)),
                "contrast": "PERSISTENT - TEMPORARY",
            }
        )
    return rows


def _state_value(row: dict[str, Any] | None, key: str) -> float | None:
    if row is None:
        return None
    if key == "EV":
        return as_float(row.get("conditional_ev_cents"))
    if key == "CI_lower":
        return as_float(row.get("ci_lower_cents"))
    if key == "CI_upper":
        return as_float(row.get("ci_upper_cents"))
    if key == "price":
        px = row.get("current_price_cents")
        return None if px is None else float(px)
    return None


def trajectory_feature_comparison(events: list[dict[str, Any]], step: str) -> list[dict[str, Any]]:
    temp = [e for e in events if e["negative_ev_class"] == TEMPORARY_NEGATIVE_EV]
    pers = [e for e in events if e["negative_ev_class"] == PERSISTENT_NEGATIVE_EV]
    features = (
        "EV",
        "EV_change_from_t0",
        "EV_velocity",
        "CI_lower",
        "CI_upper",
        "CI_width",
        "price",
        "price_change_from_t0",
        "score_diff",
        "score_diff_change_from_t0",
        "ESS",
        "median_distance",
    )
    out = []
    for key in features:
        labeled = []
        for event in temp + pers:
            states = landmark_states(event)
            now = states.get(step)
            t0 = states.get("t0")
            if now is None:
                continue
            if key == "EV_change_from_t0":
                a = _state_value(now, "EV")
                b = _state_value(t0, "EV")
                val = None if a is None or b is None else a - b
            elif key == "EV_velocity":
                val = event.get("EV_velocity_t0_to_t1") if step == "t1" else event.get("EV_velocity_t1_to_t2")
            elif key == "CI_width":
                lo = _state_value(now, "CI_lower")
                hi = _state_value(now, "CI_upper")
                val = None if lo is None or hi is None else hi - lo
            elif key == "price_change_from_t0":
                a = _state_value(now, "price")
                b = _state_value(t0, "price")
                val = None if a is None or b is None else a - b
            elif key == "score_diff":
                val = event.get("score_diff_t1") if step == "t1" else None
                if now.get("home_score") is not None and now.get("away_score") is not None:
                    val = float(int(now["home_score"]) - int(now["away_score"]))
            elif key == "score_diff_change_from_t0":
                if (
                    now.get("home_score") is not None
                    and now.get("away_score") is not None
                    and t0 is not None
                    and t0.get("home_score") is not None
                    and t0.get("away_score") is not None
                ):
                    val = float(
                        (int(now["home_score"]) - int(now["away_score"]))
                        - (int(t0["home_score"]) - int(t0["away_score"]))
                    )
                else:
                    val = None
            elif key == "ESS":
                val = as_float(now.get("effective_sample_size"))
            elif key == "median_distance":
                val = as_float(now.get("median_distance"))
            else:
                val = _state_value(now, key)
            if val is None:
                continue
            labeled.append(
                {
                    "internal_game_id": event.get("internal_game_id"),
                    "negative_ev_class": event["negative_ev_class"],
                    "value": float(val),
                }
            )
        tv = [r["value"] for r in labeled if r["negative_ev_class"] == TEMPORARY_NEGATIVE_EV]
        pv = [r["value"] for r in labeled if r["negative_ev_class"] == PERSISTENT_NEGATIVE_EV]
        ci = clustered_mean_diff(
            labeled,
            value_key="value",
            positive_pred=lambda r: r["negative_ev_class"] == PERSISTENT_NEGATIVE_EV,
            negative_pred=lambda r: r["negative_ev_class"] == TEMPORARY_NEGATIVE_EV,
            seed=BOOTSTRAP_SEED,
            draws=BOOTSTRAP_B,
        )
        out.append(
            {
                "step": step,
                "feature": key,
                "temporary_n": len(tv),
                "persistent_n": len(pv),
                "temporary_mean": _mean(tv),
                "temporary_median": _median(tv),
                "persistent_mean": _mean(pv),
                "persistent_median": _median(pv),
                "difference": None if not tv or not pv else _mean(pv) - _mean(tv),
                "ci": ci.get("ci"),
                "effect_size": _cohens_d(tv, pv),
                "classification": _status(ci, n_a=len(tv), n_b=len(pv)),
            }
        )
    return out


PIT_COMPARE_FIELDS = [
    "source_experiment_id",
    "feature",
    "temporary_n",
    "persistent_n",
    "temporary_mean",
    "temporary_median",
    "persistent_mean",
    "persistent_median",
    "difference",
    "ci_lo",
    "ci_hi",
    "effect_size",
    "classification",
]

TRAJ_COMPARE_FIELDS = [
    "source_experiment_id",
    "step",
    "feature",
    "temporary_n",
    "persistent_n",
    "temporary_mean",
    "temporary_median",
    "persistent_mean",
    "persistent_median",
    "difference",
    "ci_lo",
    "ci_hi",
    "effect_size",
    "classification",
]


def flatten_pit(experiment_id: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        ci = row.get("ci") or [None, None]
        out.append(
            {
                "source_experiment_id": experiment_id,
                **row,
                "ci_lo": None if not ci else ci[0],
                "ci_hi": None if not ci else ci[1],
            }
        )
    return out
