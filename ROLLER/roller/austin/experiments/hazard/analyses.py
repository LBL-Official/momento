"""Descriptive Phase 4 tables. No composite score. No policy."""

from __future__ import annotations

from typing import Any

import numpy as np

from roller.austin.experiments.downfall.ids import HEALTHY, HEALTHY_AFTER_RECOVERY, RECOVERING
from roller.austin.experiments.hazard.beta import jeffreys_estimate
from roller.austin.experiments.hazard.ids import (
    CI_CROSSES_ZERO,
    CI_NEGATIVE,
    NEGATIVE_STATES,
    NOT_APPLICABLE,
    PERSISTENCE_2,
    PERSISTENCE_3PLUS,
    REQUIRED_TRANSITIONS,
    WATCH_NEGATIVE,
)
from roller.austin.experiments.hazard.metrics import clustered_spearman, probability_contrast
from roller.austin.experiments.persistence.util import as_float


def _mean(vals: list[Any]) -> float | None:
    nums = [float(v) for v in vals if v is not None]
    return None if not nums else float(np.mean(nums))


def _full_cell(rows: list[dict[str, Any]], target: str) -> dict[str, Any]:
    eligible = [r for r in rows if r.get(target) not in (None, NOT_APPLICABLE)]
    y = sum(int(r[target]) for r in eligible)
    return jeffreys_estimate(y, len(eligible))


def by_state(rows: list[dict[str, Any]], experiment_id: str) -> list[dict[str, Any]]:
    out = []
    for state in (HEALTHY, *NEGATIVE_STATES, RECOVERING, HEALTHY_AFTER_RECOVERY):
        group = [r for r in rows if r.get("core_state") == state]
        loss = _full_cell(group, "TARGET_terminal_loss")
        rec = {k: _full_cell(group, k) if state in NEGATIVE_STATES else {"p_hat": None, "support_n": 0, "status": "N/A"} for k in ("TARGET_recovery_t1", "TARGET_recovery_by_t2", "TARGET_recovery_by_t3")}
        out.append(
            {
                "source_experiment_id": experiment_id,
                "core_state": state,
                "N": len(group),
                "terminal_losses": sum(int(r.get("TARGET_terminal_loss") or 0) for r in group),
                "p_terminal_loss_H1": loss["p_hat"],
                "p_terminal_loss_lo": loss["posterior_lower"],
                "p_terminal_loss_hi": loss["posterior_upper"],
                "support_n_loss": loss["support_n"],
                "p_recovery_t1_H1": rec["TARGET_recovery_t1"]["p_hat"],
                "p_recovery_by_t2_H1": rec["TARGET_recovery_by_t2"]["p_hat"],
                "p_recovery_by_t3_H1": rec["TARGET_recovery_by_t3"]["p_hat"],
                "mean_pnl_hold_after_state": _mean([r.get("OUTCOME_pnl_hold_after_state") for r in group]),
            }
        )
    return out


def by_state_ci(rows: list[dict[str, Any]], experiment_id: str) -> list[dict[str, Any]]:
    out = []
    for state in NEGATIVE_STATES:
        for ci in (CI_NEGATIVE, CI_CROSSES_ZERO):
            group = [r for r in rows if r.get("core_state") == state and r.get("CI_state") == ci]
            loss = _full_cell(group, "TARGET_terminal_loss")
            out.append(
                {
                    "source_experiment_id": experiment_id,
                    "core_state": state,
                    "CI_state": ci,
                    "N": len(group),
                    "losses": sum(int(r.get("TARGET_terminal_loss") or 0) for r in group),
                    "p_terminal_loss_H2": loss["p_hat"],
                    "posterior_lower": loss["posterior_lower"],
                    "posterior_upper": loss["posterior_upper"],
                    "label": "LOW_SAMPLE" if len(group) < 10 else "OBSERVED",
                }
            )
    return out


def missingness(rows: list[dict[str, Any]], experiment_id: str) -> list[dict[str, Any]]:
    out = []
    for target in ("TARGET_recovery_t1", "TARGET_recovery_by_t2", "TARGET_recovery_by_t3", "TARGET_deeper_distress_next"):
        neg = [r for r in rows if r.get("core_state") in NEGATIVE_STATES]
        out.append(
            {
                "source_experiment_id": experiment_id,
                "target": target,
                "eligible": sum(1 for r in neg if r.get(target) in (0, 1)),
                "positive": sum(1 for r in neg if r.get(target) == 1),
                "negative": sum(1 for r in neg if r.get(target) == 0),
                "unavailable": sum(1 for r in neg if r.get(target) is None),
                "not_applicable": sum(1 for r in rows if r.get(target) == NOT_APPLICABLE),
            }
        )
    return out


def trajectories(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_trade: dict[tuple, list[dict[str, Any]]] = {}
    for row in rows:
        if row.get("core_state") not in NEGATIVE_STATES:
            continue
        key = (row.get("source_experiment_id"), row.get("trade_id"))
        by_trade.setdefault(key, []).append(row)
    out = []
    for (_eid, trade_id), group in by_trade.items():
        group = sorted(group, key=lambda r: int(r.get("state_sequence_number") or 0))
        prev = None
        for row in group:
            item = {
                "source_experiment_id": row.get("source_experiment_id"),
                "trade_id": trade_id,
                "internal_game_id": row.get("internal_game_id"),
                "core_state": row.get("core_state"),
                "state_sequence_number": row.get("state_sequence_number"),
                "p_terminal_loss_H1": row.get("p_terminal_loss_H1"),
                "p_recovery_t1_H1": row.get("p_recovery_t1_H1"),
                "delta_p_loss_H1": None
                if prev is None or row.get("p_terminal_loss_H1") is None or prev.get("p_terminal_loss_H1") is None
                else float(row["p_terminal_loss_H1"]) - float(prev["p_terminal_loss_H1"]),
                "delta_p_recovery_t1_H1": None
                if prev is None or row.get("p_recovery_t1_H1") is None or prev.get("p_recovery_t1_H1") is None
                else float(row["p_recovery_t1_H1"]) - float(prev["p_recovery_t1_H1"]),
            }
            out.append(item)
            prev = row
    return out


def transition_risk(rows: list[dict[str, Any]], transitions: list[dict[str, Any]], experiment_id: str) -> list[dict[str, Any]]:
    by_trade_state = {(r.get("trade_id"), r.get("core_state")): r for r in rows if r.get("source_experiment_id") == experiment_id}
    seen: set[tuple] = set()
    first = []
    for row in transitions:
        if row.get("source_experiment_id") != experiment_id:
            continue
        pair = (row.get("from_state"), row.get("to_state"))
        if pair not in REQUIRED_TRANSITIONS:
            continue
        key = (row.get("trade_id"), pair[0], pair[1])
        if key in seen:
            continue
        seen.add(key)
        src = by_trade_state.get((row.get("trade_id"), pair[0]))
        if not src:
            continue
        item = dict(row)
        for k in ("p_terminal_loss_H1", "p_recovery_t1_H1", "p_recovery_by_t2_H1", "p_recovery_by_t3_H1", "p_terminal_loss_H2", "p_recovery_t1_H2"):
            item[k] = src.get(k)
        item["branch"] = "RECOVERY" if pair[1] == RECOVERING else "DEEPER"
        first.append(item)
    return first


def support_rows(rows: list[dict[str, Any]], experiment_id: str) -> list[dict[str, Any]]:
    out = []
    for state in (*NEGATIVE_STATES, HEALTHY):
        group = [r for r in rows if r.get("core_state") == state]
        low_cell = sum(1 for r in group if (r.get("support_n_terminal_loss_H1") or 0) < 10)
        out.append(
            {
                "source_experiment_id": experiment_id,
                "core_state": state,
                "N": len(group),
                "mean_ESS": _mean([r.get("ESS") for r in group]),
                "mean_median_distance": _mean([r.get("median_distance") for r in group]),
                "mean_feature_coverage": _mean([r.get("feature_coverage") for r in group]),
                "low_cell_support_N": low_cell,
            }
        )
    return out


def timing_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        if row.get("core_state") not in NEGATIVE_STATES:
            continue
        out.append(
            {
                "source_experiment_id": row.get("source_experiment_id"),
                "trade_id": row.get("trade_id"),
                "internal_game_id": row.get("internal_game_id"),
                "core_state": row.get("core_state"),
                "price": row.get("current_price"),
                "price_travel": row.get("price_travel"),
                "future_min_price": row.get("OUTCOME_future_min_price"),
                "adverse_cents_remaining": row.get("adverse_cents_remaining"),
                "minutes_to_worst_price": row.get("OUTCOME_minutes_to_worst_price"),
                "minutes_to_settlement": row.get("OUTCOME_minutes_to_settlement"),
                "p_terminal_loss_H1": row.get("p_terminal_loss_H1"),
                "p_recovery_t1_H1": row.get("p_recovery_t1_H1"),
                "p_recovery_by_t2_H1": row.get("p_recovery_by_t2_H1"),
                "p_recovery_by_t3_H1": row.get("p_recovery_by_t3_H1"),
            }
        )
    return out


def ev_vs_hazard(rows: list[dict[str, Any]], experiment_id: str) -> list[dict[str, Any]]:
    out = []
    for y_key, name in (("p_terminal_loss_H1", "p_loss"), ("p_recovery_t1_H1", "p_recovery_t1")):
        usable = []
        for r in rows:
            ev = as_float(r.get("EV"))
            if ev is None or r.get(y_key) is None:
                continue
            item = dict(r)
            item["_ev"] = ev
            usable.append(item)
        sp = clustered_spearman(usable, x_key="_ev", y_key=y_key)
        out.append(
            {
                "source_experiment_id": experiment_id,
                "contrast": f"EV vs {name}",
                "n": sp["n"],
                "spearman": sp["observed"],
                "ci_lo": None if not sp["ci"] else sp["ci"][0],
                "ci_hi": None if not sp["ci"] else sp["ci"][1],
            }
        )
    return out


def t40_rows(rows: list[dict[str, Any]], experiment_id: str) -> list[dict[str, Any]]:
    neg = [r for r in rows if r.get("core_state") in NEGATIVE_STATES]
    known = [r for r in neg if r.get("TARGET_T40_before_recovery") in (0, 1)]
    return [
        {
            "source_experiment_id": experiment_id,
            "N_negative_entries": len(neg),
            "N_not_applicable": sum(1 for r in neg if r.get("TARGET_T40_before_recovery") == NOT_APPLICABLE),
            "N_unavailable": sum(1 for r in neg if r.get("TARGET_T40_before_recovery") is None),
            "N_observable": len(known),
            "n_T40_before_recovery": sum(1 for r in known if r.get("TARGET_T40_before_recovery") == 1),
        }
    ]


def predeclared_contrasts(rows: list[dict[str, Any]], experiment_id: str) -> list[dict[str, Any]]:
    out = []
    for left, right in (( "WATCH_NEGATIVE", "HEALTHY"), ("PERSISTENCE_2", "WATCH_NEGATIVE"), ("PERSISTENCE_3PLUS", "PERSISTENCE_2")):
        ci = probability_contrast(rows, left=left, right=right, p_key="p_terminal_loss_H1")
        out.append({"source_experiment_id": experiment_id, "contrast": f"{left} vs {right} p_loss", "metric": "p_terminal_loss_H1", **_flat(ci)})
    for left, right, key in (
        ("WATCH_NEGATIVE", "PERSISTENCE_2", "p_recovery_t1_H1"),
        ("WATCH_NEGATIVE", "PERSISTENCE_2", "p_recovery_by_t2_H1"),
    ):
        ci = probability_contrast(rows, left=left, right=right, p_key=key)
        out.append({"source_experiment_id": experiment_id, "contrast": f"{left} vs {right} {key}", "metric": key, **_flat(ci)})
    neg = [r for r in rows if r.get("core_state") in NEGATIVE_STATES and r.get("CI_state") in {CI_NEGATIVE, CI_CROSSES_ZERO}]
    ci = probability_contrast(
        [{**r, "core_state": r.get("CI_state")} for r in neg],
        left=CI_NEGATIVE,
        right=CI_CROSSES_ZERO,
        p_key="p_terminal_loss_H2",
    )
    out.append({"source_experiment_id": experiment_id, "contrast": "CI_NEGATIVE vs CI_CROSSES_ZERO p_loss", "metric": "p_terminal_loss_H2", **_flat(ci)})
    return out


def _flat(ci: dict[str, Any]) -> dict[str, Any]:
    band = ci.get("ci") or [None, None]
    return {
        "n_left": ci.get("n_positive"),
        "n_right": ci.get("n_negative"),
        "observed_delta": ci.get("observed_delta"),
        "ci_lo": band[0],
        "ci_hi": band[1],
        "classification": "INSUFFICIENT_SAMPLE"
        if ci.get("observed_delta") is None or (ci.get("n_positive") or 0) < 2 or (ci.get("n_negative") or 0) < 2
        else ("SUPPORTED" if ci.get("excludes_zero") else "MIXED"),
    }


def dynamic_updates(rows: list[dict[str, Any]], experiment_id: str) -> list[dict[str, Any]]:
    by_trade: dict[str, dict[str, dict[str, Any]]] = {}
    for row in rows:
        if row.get("source_experiment_id") != experiment_id:
            continue
        by_trade.setdefault(str(row.get("trade_id")), {})[str(row.get("core_state"))] = row
    pairs = (
        (WATCH_NEGATIVE, PERSISTENCE_2),
        (PERSISTENCE_2, PERSISTENCE_3PLUS),
        (PERSISTENCE_2, RECOVERING),
    )
    out = []
    for src, dst in pairs:
        deltas_loss = []
        deltas_rec = []
        n = 0
        for states in by_trade.values():
            a = states.get(src)
            b = states.get(dst)
            if not a or not b:
                continue
            n += 1
            if a.get("p_terminal_loss_H1") is not None and b.get("p_terminal_loss_H1") is not None:
                deltas_loss.append(float(b["p_terminal_loss_H1"]) - float(a["p_terminal_loss_H1"]))
            if a.get("p_recovery_t1_H1") is not None and b.get("p_recovery_t1_H1") is not None:
                deltas_rec.append(float(b["p_recovery_t1_H1"]) - float(a["p_recovery_t1_H1"]))
        out.append(
            {
                "source_experiment_id": experiment_id,
                "from_state": src,
                "to_state": dst,
                "N_trades": n,
                "mean_delta_p_loss_H1": None if not deltas_loss else float(np.mean(deltas_loss)),
                "mean_delta_p_recovery_t1_H1": None if not deltas_rec else float(np.mean(deltas_rec)),
            }
        )
    return out


H1_FIELDS = ["p_terminal_loss_H1", "p_recovery_t1_H1"]
H2_FIELDS = ["p_terminal_loss_H2"]
