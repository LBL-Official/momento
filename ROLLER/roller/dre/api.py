"""DRE HTTP handlers. Adapter only: Choosin Texas + Austin.

Missing upstream is UNAVAILABLE. Never $0. No query. No submit.
Phase 3 is not an execution policy.
"""

from __future__ import annotations

from typing import Any

LIVE_EXECUTION = False
PRODUCT = "DRE"
OBJECTIVE = {
    "id": "DRE_PORTFOLIO_OBJECTIVE_V1",
    "memo_date": "2026-09-02",
    "status": "RESEARCH_MEMO",
    "calculus": "NOT_IMPLEMENTED",
    "preserve_alpha_first": True,
    "first_form": "ΔP → 0 | αP > 0",
    "eventual_form": "ΔP → ΔP*(Xt)",
    "ssot": "research/dre/PORTFOLIO_OBJECTIVE_V1.md",
    "library": "research/dre/",
    "forward_feed": ["trade_breakdown", "position_stratification"],
    "note": (
        "Preserve αP > 0, then move exposure toward ΔP*(Xt). "
        "Do not invent Λα. Phase 3 is not an execution policy."
    ),
}


def _unavailable(source: str, detail: str) -> dict[str, Any]:
    return {
        "status": "UNAVAILABLE",
        "source": source,
        "detail": detail,
        "live_execution": LIVE_EXECUTION,
    }


def _probe_choosin() -> dict[str, Any]:
    from roller.choosin_texas.api import handle_health

    return handle_health()


def _probe_austin() -> dict[str, Any]:
    from roller.austin.api import handle_health

    return handle_health()


def handle_health() -> dict[str, Any]:
    choosin: dict[str, Any]
    austin: dict[str, Any]
    try:
        choosin = _probe_choosin()
    except Exception as exc:  # noqa: BLE001 — fail closed to UNAVAILABLE
        choosin = _unavailable("choosin_texas", f"{type(exc).__name__}: {exc}")
    try:
        austin = _probe_austin()
    except Exception as exc:  # noqa: BLE001 — fail closed to UNAVAILABLE
        austin = _unavailable("austin", f"{type(exc).__name__}: {exc}")
    return {
        "ok": True,
        "product": PRODUCT,
        "product_canonical": "Drevo",
        "role": "dynamic_risk_engine",
        "live_execution": LIVE_EXECUTION,
        "submits": False,
        "phase3_is_execution_policy": False,
        "live_feed": "UNAVAILABLE",
        "note": (
            "Hold-reason research desk. Reads Choosin Texas and Austin only. "
            "V1 objective: preserve αP > 0, then ΔP → ΔP*(Xt). "
            "Not crates/risk. Phase 3 is not an execution policy. "
            "Do not invent Λα."
        ),
        "objective": OBJECTIVE,
        "upstream": {
            "trade_breakdown": choosin,
            "position_stratification": austin,
        },
    }


def handle_trade_breakdown() -> dict[str, Any]:
    from roller.choosin_texas.api import handle_universe

    body = handle_universe()
    pool = body.get("pool") if isinstance(body.get("pool"), dict) else {}
    trade = pool.get("trade_80_40") if isinstance(pool.get("trade_80_40"), dict) else {}
    return {
        "status": body.get("status") or "UNAVAILABLE",
        "source": "choosin_texas",
        "product": "Choosin Texas",
        "live_execution": LIVE_EXECUTION,
        "submits": False,
        "rule": body.get("rule"),
        "n": pool.get("n"),
        "W": pool.get("W"),
        "L": pool.get("L"),
        "S_display": trade.get("S_display"),
        "universe": "derived_four_936",
        "note": "Texas ledger N=936. Not Austin 604. Candle path ≠ fill.",
        "pool": pool,
        "verification": body.get("verification"),
        "disclaimers": body.get("disclaimers"),
    }


def handle_stratum() -> dict[str, Any]:
    from roller.austin.api import handle_dataset, handle_health

    health = handle_health()
    dataset = handle_dataset()
    coverage = dataset.get("coverage") if isinstance(dataset.get("coverage"), dict) else {}
    return {
        "status": dataset.get("status") or "UNAVAILABLE",
        "source": "austin",
        "product": "Austin",
        "live_execution": LIVE_EXECUTION,
        "submits": False,
        "live_feed": health.get("live_feed") or dataset.get("live_feed") or "UNAVAILABLE",
        "book_n": 604,
        "universe": "nba_2q_3q_604",
        "model_universe": dataset.get("model_universe") or health.get("model_universe"),
        "dataset_version": dataset.get("dataset_version"),
        "coverage": coverage,
        "artifacts": health.get("artifacts"),
        "note": "Position Stratification. N=604 only. Never BUY/SKIP. Live feed UNAVAILABLE.",
    }


def handle_experiments() -> dict[str, Any]:
    from roller.austin.api import handle_experiments

    body = handle_experiments()
    return {
        **body,
        "source": "austin",
        "live_execution": LIVE_EXECUTION,
        "submits": False,
        "phase3_is_execution_policy": False,
    }


def handle_experiment(experiment_id: str) -> dict[str, Any]:
    from roller.austin.api import handle_experiment

    body = handle_experiment(experiment_id)
    if isinstance(body, dict):
        return {
            **body,
            "source": "austin",
            "live_execution": LIVE_EXECUTION,
            "submits": False,
            "phase3_is_execution_policy": False,
        }
    return body


def handle_positions(
    slice_name: str | None = None,
    q: str | None = None,
    dataset_split: str | None = None,
) -> dict[str, Any]:
    from roller.dre.composer import list_positions

    return list_positions(slice_name=slice_name, q=q, dataset_split=dataset_split)


def handle_position(position_id: str, as_of: str | None = None) -> dict[str, Any]:
    from roller.dre.composer import compose_position

    return compose_position(position_id, as_of=as_of, mode="HISTORICAL")


def handle_replay_position(trade_id: str, as_of: str | None = None) -> dict[str, Any]:
    from roller.dre.composer import compose_position

    return compose_position(trade_id, as_of=as_of, mode="REPLAY")


def handle_desk() -> dict[str, Any]:
    trade: dict[str, Any]
    stratum: dict[str, Any]
    experiments: dict[str, Any]
    try:
        trade = handle_trade_breakdown()
    except Exception as exc:  # noqa: BLE001 — fail closed to UNAVAILABLE
        trade = _unavailable("choosin_texas", f"{type(exc).__name__}: {exc}")
    try:
        stratum = handle_stratum()
    except Exception as exc:  # noqa: BLE001 — fail closed to UNAVAILABLE
        stratum = _unavailable("austin", f"{type(exc).__name__}: {exc}")
    try:
        experiments = handle_experiments()
    except Exception as exc:  # noqa: BLE001 — fail closed to UNAVAILABLE
        experiments = _unavailable("austin", f"{type(exc).__name__}: {exc}")
    return {
        "product": PRODUCT,
        "product_canonical": "Drevo",
        "role": "dynamic_risk_engine",
        "live_execution": LIVE_EXECUTION,
        "submits": False,
        "phase3_is_execution_policy": False,
        "live_feed": "UNAVAILABLE",
        "hold_reason_intact": "UNKNOWN",
        "note": (
            "Hold-reason research. Upstream integers only. Not a fill and not crates/risk. "
            "V1 objective: preserve αP > 0, then ΔP → ΔP*(Xt)."
        ),
        "objective": OBJECTIVE,
        "trade_breakdown": trade,
        "stratum": stratum,
        "experiments": experiments,
    }


def handle_decision(trade_id: str, as_of: str | None = None) -> dict[str, Any]:
    from roller.dre.decision import decide_for_trade

    return decide_for_trade(trade_id, as_of, record=True)
