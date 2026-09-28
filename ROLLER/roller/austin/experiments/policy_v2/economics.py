"""Discovery-only first-fire hypothetical economics. Scenario ≠ fill."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import numpy as np

from roller.austin.experiments.ids import BOOTSTRAP_B, BOOTSTRAP_SEED
from roller.austin.experiments.ledgers import _hyp_pnl, _scenario_prices
from roller.austin.experiments.outcomes_ncaab import baseline_8040_cents, baseline_hold_cents
from roller.austin.experiments.policy_v2.decide import decide
from roller.austin.experiments.policy_v2.ids import (
    EXECUTION_COST_ASSUMPTION,
    EXECUTION_COST_CENTS,
    INTERVENE,
    SCENARIO_LABEL,
)
from roller.austin.experiments.statistics import max_drawdown, summarize_pnl
from roller.austin.experiments.downfall.timeline import trade_primary


def attach_t40(entries: list[dict[str, Any]], suite: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    primaries: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for eid, member in suite.items():
        for trade in member["trades"]:
            primaries[(eid, trade["trade_id"])] = trade_primary(member["queries"], trade["trade_id"])
    out = []
    for row in entries:
        item = dict(row)
        primary = primaries.get((str(row.get("source_experiment_id")), str(row.get("trade_id")))) or []
        idx = int(row.get("state_sequence_number") or 0)
        now = primary[idx] if 0 <= idx < len(primary) else {}
        already = bool(now.get("t40_already"))
        if row.get("TARGET_T40_before_recovery") == "NOT_APPLICABLE" and row.get("core_state") in {
            "WATCH_NEGATIVE",
            "PERSISTENCE_2",
            "PERSISTENCE_3PLUS",
        }:
            already = True
        item["t40_already"] = already
        out.append(item)
    return out


def first_fire(
    entries: list[dict[str, Any]],
    candidate: dict[str, Any],
) -> list[dict[str, Any]]:
    by_trade: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in entries:
        by_trade[(str(row.get("source_experiment_id")), str(row.get("trade_id")))].append(row)
    events = []
    for (eid, tid), group in by_trade.items():
        ordered = sorted(group, key=lambda r: int(r.get("state_sequence_number") or 0))
        chosen = None
        reason = "NO_TRIGGER"
        timing = None
        for row in ordered:
            verdict = decide(candidate, row)
            if verdict["action"] == INTERVENE and chosen is None:
                chosen = row
                reason = verdict["reason"]
                timing = verdict["timing_class"]
                break
        events.append(
            {
                "source_experiment_id": eid,
                "trade_id": tid,
                "candidate_id": candidate["candidate_id"],
                "action": INTERVENE if chosen else "NONE",
                "reason": reason if chosen else ("NO_TRIGGER" if reason == "NO_TRIGGER" else reason),
                "timing_class": timing,
                "entry": chosen,
            }
        )
    return events


def _later_primary(queries: list[dict[str, Any]], trade_id: str, stamp: str | None) -> list[dict[str, Any]]:
    rows = [r for r in queries if r.get("trade_id") == trade_id and r.get("primary")]
    return [r for r in rows if (r.get("timestamp_utc") or "") > (stamp or "")]


def score_events(
    events: list[dict[str, Any]],
    trades: list[dict[str, Any]],
    queries: list[dict[str, Any]],
    timing_by_key: dict[tuple[str, str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    trade_map = {t["trade_id"]: t for t in trades}
    out = []
    for event in events:
        trade = trade_map.get(event["trade_id"])
        if not trade:
            continue
        hold = baseline_hold_cents(trade)
        eight = baseline_8040_cents(trade)
        chosen = event.get("entry")
        stamp = None if not chosen else chosen.get("state_entry_timestamp")
        later = _later_primary(queries, event["trade_id"], stamp)
        raw_price = None if not chosen else chosen.get("price")
        price = None if raw_price is None else int(float(raw_price))
        price_row = {} if not chosen else {"current_price_cents": price}
        prices = _scenario_prices(price_row, later)
        won = bool(trade.get("won"))
        hyp_a = _hyp_pnl(prices["scenario_a"], won) if event["action"] == INTERVENE else hold
        hyp_b = _hyp_pnl(prices["scenario_b"], won) if event["action"] == INTERVENE else hold
        saved = 0 if (won or event["action"] != INTERVENE or hyp_b is None) else max(0, hyp_b - hold)
        sacrificed = 0 if (not won or event["action"] != INTERVENE or hyp_b is None) else max(0, hold - hyp_b)
        tkey = (event["source_experiment_id"], event["trade_id"], str((chosen or {}).get("core_state")))
        timing = timing_by_key.get(tkey) or {}
        out.append(
            {
                "source_experiment_id": event["source_experiment_id"],
                "trade_id": event["trade_id"],
                "internal_game_id": trade.get("internal_game_id"),
                "candidate_id": event["candidate_id"],
                "action": event["action"],
                "reason": event["reason"],
                "timing_class": event["timing_class"],
                "core_state": None if not chosen else chosen.get("core_state"),
                "p_terminal_loss_H1": None if not chosen else chosen.get("p_terminal_loss_H1"),
                "p_recovery_t1_H1": None if not chosen else chosen.get("p_recovery_t1_H1"),
                "won": won,
                "t40_already": None if not chosen else chosen.get("t40_already"),
                "price": None if not chosen else chosen.get("price"),
                "scenario_a_price": prices["scenario_a"],
                "scenario_b_price": prices["scenario_b"],
                "baseline_hold_pnl": hold,
                "baseline_8040_pnl": eight,
                "hypothetical_pnl_a": hyp_a,
                "hypothetical_pnl_b": hyp_b,
                "delta_vs_hold_b": None if hyp_b is None else hyp_b - hold,
                "delta_vs_8040_b": None if hyp_b is None else hyp_b - eight,
                "cents_saved": saved,
                "cents_sacrificed": sacrificed,
                "winner_abandoned": bool(event["action"] == INTERVENE and won),
                "loss_avoided": bool(event["action"] == INTERVENE and not won),
                "adverse_cents_remaining": timing.get("adverse_cents_remaining"),
                "minutes_to_worst_price": timing.get("minutes_to_worst_price"),
                "scenario_label": SCENARIO_LABEL,
            }
        )
    return out


def summarize_candidate(rows: list[dict[str, Any]], experiment_id: str, candidate_id: str) -> dict[str, Any]:
    fired = [r for r in rows if r.get("action") == INTERVENE]
    n = len(rows)
    n_int = len(fired)
    losses_int = sum(1 for r in fired if not r.get("won"))
    wins_int = sum(1 for r in fired if r.get("won"))
    saved = sum(float(r.get("cents_saved") or 0) for r in fired)
    sacr = sum(float(r.get("cents_sacrificed") or 0) for r in fired)
    value = saved - sacr - EXECUTION_COST_CENTS
    hyp = [float(r["hypothetical_pnl_b"]) for r in rows if r.get("hypothetical_pnl_b") is not None]
    hold = [float(r["baseline_hold_pnl"]) for r in rows if r.get("baseline_hold_pnl") is not None]
    summary = summarize_pnl(hyp)
    dd = max_drawdown(hyp)
    p10 = summary.get("p10")
    worst = None if not hyp else min(hyp)
    ci = _clustered_mean(rows, "delta_vs_hold_b")
    prices = [float(r["price"]) for r in fired if r.get("price") is not None]
    adv = [float(r["adverse_cents_remaining"]) for r in fired if r.get("adverse_cents_remaining") is not None]
    mins = [float(r["minutes_to_worst_price"]) for r in fired if r.get("minutes_to_worst_price") is not None]
    too_late = sum(1 for r in fired if r.get("timing_class") == "TOO_LATE")
    return {
        "source_experiment_id": experiment_id,
        "candidate_id": candidate_id,
        "n_trades": n,
        "intervention_n": n_int,
        "intervention_rate": None if not n else n_int / n,
        "losses_intervened": losses_int,
        "winners_intervened": wins_int,
        "losses_avoided": sum(1 for r in fired if r.get("loss_avoided")),
        "winners_abandoned": sum(1 for r in fired if r.get("winner_abandoned")),
        "cents_saved": saved,
        "winner_cents_sacrificed": sacr,
        "dre_value_added": value,
        "scenario_b_ev": summary.get("ev_cents"),
        "delta_vs_hold": None if not hyp or not hold else float(np.mean(hyp) - np.mean(hold)),
        "delta_vs_hold_ci_lo": ci[0],
        "delta_vs_hold_ci_hi": ci[1],
        "delta_vs_8040": _mean_delta(rows, "delta_vs_8040_b"),
        "max_drawdown": dd,
        "p10": p10,
        "worst_trade": worst,
        "median_trigger_price": None if not prices else float(np.median(prices)),
        "median_adverse_cents_remaining": None if not adv else float(np.median(adv)),
        "median_minutes_to_worst": None if not mins else float(np.median(mins)),
        "n_too_late": too_late,
        "execution_cost_cents": EXECUTION_COST_CENTS,
        "execution_cost_assumption": EXECUTION_COST_ASSUMPTION,
        "scenario_label": SCENARIO_LABEL,
    }


def _mean_delta(rows: list[dict[str, Any]], key: str) -> float | None:
    vals = [float(r[key]) for r in rows if r.get(key) is not None]
    return None if not vals else float(np.mean(vals))


def _clustered_mean(rows: list[dict[str, Any]], key: str) -> list[float | None]:
    groups: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        if row.get(key) is None:
            continue
        groups[str(row.get("internal_game_id") or row.get("trade_id"))].append(float(row[key]))
    keys = sorted(groups)
    if not keys:
        return [None, None]
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    draws = []
    for _ in range(BOOTSTRAP_B):
        pick = rng.choice(len(keys), size=len(keys), replace=True)
        sample = [v for idx in pick for v in groups[keys[int(idx)]]]
        if sample:
            draws.append(float(np.mean(sample)))
    if not draws:
        return [None, None]
    return [float(np.quantile(draws, 0.025)), float(np.quantile(draws, 0.975))]
