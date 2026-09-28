"""NBA Bot 001 desk. The worker is observed read-only over SSM. No submit."""

from __future__ import annotations

import json
from pathlib import Path

from roller.momento.contracts import (
    ExecutionIntent,
    ExecutionReport,
    Fill,
    OrderIntent,
    PositionReconciliation,
    TargetExposure,
)

NBA_BOT_ID = "nba-first80-001"
NBA_CANONICAL_ID = "nba-001"
SUBMITS = False
_BOT_ROOT = Path(__file__).resolve().parents[3] / "research" / "vital" / "bots" / "nba-001"
_NBA_DOCS = {
    "strategy": _BOT_ROOT / "strategy" / "NBA_001_STRATEGY_SPEC.md",
    "policy": _BOT_ROOT / "strategy" / "policy_v1.json",
    "policy_v0": _BOT_ROOT / "strategy" / "policy.json",
    "contract": _BOT_ROOT / "strategy" / "execution_contract.json",
    "field_to_code": _BOT_ROOT / "strategy" / "FIELD_TO_CODE.md",
    "funding": _BOT_ROOT / "FUNDING_ROUTING.md",
    "status": _BOT_ROOT / "IMPLEMENTATION_STATUS.md",
    "evidence": _BOT_ROOT / "analysis" / "EVIDENCE_REPORT.md",
    "testing": _BOT_ROOT / "testing" / "OCTOBER_3_PROTOCOL.md",
}
_JSON_DOCS = {"policy", "policy_v0", "contract"}

HOOKS: dict[str, bool] = {
    "capital_limit": True,
    "max_position": True,
    "kill_switch": True,
    "stale_data_guard": True,
    "duplicate_order_guard": True,
    "reconciliation_guard": True,
    "enabled": False,
}


def dry_run_intent(target: TargetExposure) -> ExecutionIntent:
    return ExecutionIntent(
        generated_at=target.generated_at,
        as_of=target.as_of,
        source_system="algorithmic_execution",
        game_id=target.game_id,
        event_id=target.event_id,
        provenance={"hooks": dict(HOOKS), "reference_only": "MLB 001"},
        bot_id=NBA_BOT_ID,
        submits=SUBMITS,
        mode="disabled",
        target_exposure_bps=target.target_exposure_bps,
        status="NOT_IMPLEMENTED",
    )


def disabled_order(intent: ExecutionIntent, *, side: str, quantity: int) -> OrderIntent:
    return OrderIntent(
        generated_at=intent.generated_at,
        as_of=intent.as_of,
        source_system="algorithmic_execution",
        game_id=intent.game_id,
        bot_id=NBA_BOT_ID,
        side=side,
        quantity=quantity,
        submits=False,
        status="NOT_IMPLEMENTED",
    )


def empty_report(intent: ExecutionIntent) -> ExecutionReport:
    return ExecutionReport(
        generated_at=intent.generated_at,
        as_of=intent.as_of,
        source_system="algorithmic_execution",
        game_id=intent.game_id,
        bot_id=NBA_BOT_ID,
        submits=False,
        accepted=False,
        status="NOT_IMPLEMENTED",
    )


def no_fill(intent: ExecutionIntent) -> Fill:
    return Fill(
        generated_at=intent.generated_at,
        as_of=intent.as_of,
        source_system="algorithmic_execution",
        game_id=intent.game_id,
        quantity=0,
        observed=False,
        status="NOT_IMPLEMENTED",
    )


def empty_reconciliation(intent: ExecutionIntent) -> PositionReconciliation:
    return PositionReconciliation(
        generated_at=intent.generated_at,
        as_of=intent.as_of,
        source_system="trade_reconciliation",
        game_id=intent.game_id,
        yes_quantity=0,
        no_quantity=0,
        matched=True,
        note="No NBA fills. Dry-run only.",
        status="NOT_IMPLEMENTED",
    )


def handle_nba_document(kind: str, session_id: str | None, *, store=None) -> dict:
    """Read the quad-1 review desk from disk. Does not submit. Does not serve MLB files."""
    from roller.momento.api import MomentoApiError
    from roller.systimo.errors import SystimoError
    from roller.systimo.scope import get_session

    if not session_id:
        raise MomentoApiError("SCOPE_REQUIRED", "NBA execution routes require an NBA session", 401)
    try:
        session = get_session(session_id, store)
    except SystimoError as exc:
        raise MomentoApiError(exc.code, str(exc), exc.status_code) from exc
    if session.get("sport") != "NBA" or session.get("quadrant_id") != "quad-1":
        raise MomentoApiError("SCOPE_DENIED", "NBA execution routes require a quad-1 NBA session", 403)
    token = str(kind or "")
    if "mlb" in token.lower():
        raise MomentoApiError("NOT_FOUND", "NBA session cannot retrieve MLB artifacts", 404)
    if token == "runtime":
        from roller.stryke.artifact import load_signal

        try:
            sheet = load_signal()
            signal = {
                "source": "stryke",
                "system_id": "signal_generation",
                "label": sheet.get("label"),
                "rows": sheet.get("rows"),
                "status": "OBSERVED",
            }
        except (OSError, ValueError):
            signal = {"source": "stryke", "status": "UNAVAILABLE"}
        from roller.momento.nba_001_runtime import observe

        worker = observe()
        status = worker.get("status") if isinstance(worker.get("status"), dict) else {}
        return {
            "bot_id": NBA_CANONICAL_ID,
            "alias": NBA_BOT_ID,
            "runtime": worker["runtime"],
            "execution_authorized": False,
            "submits": SUBMITS,
            "live_execution": False,
            "listens_to": "signal_generation",
            "signal": signal,
            "heartbeat": worker.get("heartbeat", "UNAVAILABLE"),
            "running": worker.get("running"),
            "healthy": worker.get("healthy"),
            "executing": False,
            "mode": status.get("mode", "UNAVAILABLE"),
            "worker": worker,
            "fills": "UNAVAILABLE",
            "pnl": "UNAVAILABLE",
        }
    path = _NBA_DOCS.get(token)
    if path is None or not path.is_file():
        raise MomentoApiError("NOT_FOUND", f"unknown NBA document {kind}", 404)
    if token in _JSON_DOCS:
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["submits"] = False
        payload["execution_authorized"] = False
        return payload
    return {
        "bot_id": NBA_CANONICAL_ID,
        "alias": NBA_BOT_ID,
        "kind": token,
        "markdown": path.read_text(encoding="utf-8"),
        "submits": False,
    }
