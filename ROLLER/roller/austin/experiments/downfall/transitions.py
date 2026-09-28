"""Adjacent valid PRIMARY transitions. No interpolation. No hazard language."""

from __future__ import annotations

from collections import Counter
from typing import Any

from roller.austin.experiments.downfall.economics import _status, summarize_entries
from roller.austin.experiments.downfall.ids import (
    BOOTSTRAP_B,
    BOOTSTRAP_SEED,
    CORE_STATES,
    PERSISTENCE_2,
    PERSISTENCE_3PLUS,
    RECOVERING,
    REQUIRED_TRANSITIONS,
    UNRESOLVED,
    WATCH_NEGATIVE,
)
from roller.austin.experiments.statistics import clustered_mean_diff
from roller.austin.experiments.persistence.util import as_float, clock_minutes_between


def adjacent_transitions(timeline: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for left, right in zip(timeline, timeline[1:]):
        if left["core_state"] == UNRESOLVED or right["core_state"] == UNRESOLVED:
            continue
        if as_float(left.get("EV")) is None or as_float(right.get("EV")) is None:
            continue
        if int(right["state_sequence_number"]) != int(left["state_sequence_number"]) + 1:
            continue
        src = left.get("_row") or {}
        dst = right.get("_row") or {}
        out.append(
            {
                "trade_id": left["trade_id"],
                "internal_game_id": left.get("internal_game_id"),
                "source_experiment_id": left.get("source_experiment_id"),
                "from_state": left["core_state"],
                "to_state": right["core_state"],
                "from_timestamp": left.get("timestamp"),
                "to_timestamp": right.get("timestamp"),
                "game_clock_minutes_elapsed": clock_minutes_between(src, dst),
                "EV_before": left.get("EV"),
                "EV_after": right.get("EV"),
                "price_before": left.get("current_price"),
                "price_after": right.get("current_price"),
                "score_diff_before": left.get("score_diff"),
                "score_diff_after": right.get("score_diff"),
            }
        )
    return out


def first_transition_entries(
    transitions: list[dict[str, Any]],
    entry_by_trade_state: dict[tuple[str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    out = []
    for row in transitions:
        key = (row["trade_id"], row["from_state"], row["to_state"])
        if key in seen:
            continue
        pair = (row["from_state"], row["to_state"])
        if pair not in REQUIRED_TRANSITIONS:
            continue
        seen.add(key)
        dest = entry_by_trade_state.get((row["trade_id"], row["to_state"]))
        item = dict(row)
        if dest:
            for k in (
                "OUTCOME_pnl_hold_after_state",
                "OUTCOME_future_T40",
                "OUTCOME_future_MAE",
                "OUTCOME_future_MFE",
                "OUTCOME_recover_ge_80",
                "won",
            ):
                item[k] = dest.get(k)
        out.append(item)
    return out


def transition_matrix(transitions: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    counts: Counter[tuple[str, str]] = Counter((r["from_state"], r["to_state"]) for r in transitions)
    from_tot: Counter[str] = Counter()
    for (frm, _to), n in counts.items():
        from_tot[frm] += n
    count_rows = []
    rate_rows = []
    for frm in CORE_STATES:
        for to in CORE_STATES:
            n = counts.get((frm, to), 0)
            tot = from_tot.get(frm, 0)
            count_rows.append({"from_state": frm, "to_state": to, "count": n})
            rate_rows.append(
                {
                    "from_state": frm,
                    "to_state": to,
                    "count": n,
                    "conditional_frequency": None if not tot else n / tot,
                }
            )
    return count_rows, rate_rows


def transition_economics(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for frm, to in REQUIRED_TRANSITIONS:
        group = [e for e in entries if e.get("from_state") == frm and e.get("to_state") == to]
        mapped = []
        for row in group:
            mapped.append(
                {
                    "won": row.get("won"),
                    "OUTCOME_pnl_hold_after_state": row.get("OUTCOME_pnl_hold_after_state"),
                    "OUTCOME_future_T40": row.get("OUTCOME_future_T40"),
                    "OUTCOME_future_MAE": row.get("OUTCOME_future_MAE"),
                    "OUTCOME_future_MFE": row.get("OUTCOME_future_MFE"),
                    "OUTCOME_recover_ge_80": row.get("OUTCOME_recover_ge_80"),
                    "OUTCOME_recover_ge_50": None,
                    "OUTCOME_recover_ge_60": None,
                    "OUTCOME_recover_ge_70": None,
                    "current_price": None,
                    "price_travel": None,
                    "OUTCOME_minutes_to_worst_price": None,
                    "OUTCOME_minutes_to_settlement": None,
                }
            )
        row = summarize_entries(mapped)
        row["from_state"] = frm
        row["to_state"] = to
        row["transition"] = f"{frm} → {to}"
        out.append(row)
    return out


BRANCH_PAIRS = (
    ((WATCH_NEGATIVE, RECOVERING), (WATCH_NEGATIVE, PERSISTENCE_2)),
    ((PERSISTENCE_2, RECOVERING), (PERSISTENCE_2, PERSISTENCE_3PLUS)),
)


def transition_branch_contrasts(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for recovery, deeper in BRANCH_PAIRS:
        rows = [
            e
            for e in entries
            if (e.get("from_state"), e.get("to_state")) in {recovery, deeper}
        ]
        labeled = []
        for row in rows:
            item = dict(row)
            item["_loss"] = 0.0 if row.get("won") else 1.0
            labeled.append(item)
        for key, name in (("OUTCOME_pnl_hold_after_state", "pnl"), ("_loss", "loss_rate")):
            ci = clustered_mean_diff(
                labeled,
                value_key=key,
                positive_pred=lambda r, p=recovery: (r.get("from_state"), r.get("to_state")) == p,
                negative_pred=lambda r, p=deeper: (r.get("from_state"), r.get("to_state")) == p,
                seed=BOOTSTRAP_SEED,
                draws=BOOTSTRAP_B,
            )
            n_left = sum(1 for r in rows if (r.get("from_state"), r.get("to_state")) == recovery)
            n_right = sum(1 for r in rows if (r.get("from_state"), r.get("to_state")) == deeper)
            out.append(
                {
                    "contrast": f"{recovery[0]} → {recovery[1]} vs {deeper[0]} → {deeper[1]}",
                    "left_transition": f"{recovery[0]} → {recovery[1]}",
                    "right_transition": f"{deeper[0]} → {deeper[1]}",
                    "metric": name,
                    "n_left": n_left,
                    "n_right": n_right,
                    "observed_delta": ci.get("observed_delta"),
                    "ci": ci.get("ci"),
                    "classification": _status(ci, n_a=n_left, n_b=n_right),
                }
            )
    return out


TRANSITION_FIELDS = [
    "trade_id",
    "internal_game_id",
    "source_experiment_id",
    "from_state",
    "to_state",
    "from_timestamp",
    "to_timestamp",
    "game_clock_minutes_elapsed",
    "EV_before",
    "EV_after",
    "price_before",
    "price_after",
    "score_diff_before",
    "score_diff_after",
]
COUNT_FIELDS = ["source_experiment_id", "from_state", "to_state", "count"]
RATE_FIELDS = ["source_experiment_id", "from_state", "to_state", "count", "conditional_frequency"]
TENTRY_FIELDS = TRANSITION_FIELDS + [
    "OUTCOME_pnl_hold_after_state",
    "OUTCOME_future_T40",
    "OUTCOME_future_MAE",
    "OUTCOME_future_MFE",
    "OUTCOME_recover_ge_80",
]
TECON_FIELDS = [
    "source_experiment_id",
    "transition",
    "from_state",
    "to_state",
    "N_trades",
    "loss_rate",
    "mean_pnl_hold_after_state",
    "mean_future_MAE",
    "mean_future_MFE",
    "recover_ge_80",
    "T40_rate",
]
BRANCH_FIELDS = [
    "source_experiment_id",
    "contrast",
    "left_transition",
    "right_transition",
    "metric",
    "n_left",
    "n_right",
    "observed_delta",
    "ci_lo",
    "ci_hi",
    "classification",
]


def flatten_branch(experiment_id: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
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
