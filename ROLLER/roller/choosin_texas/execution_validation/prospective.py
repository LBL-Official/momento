"""Read-only prospective observation for the paired candle-close signal.

This collector stores quotes and clocks. It does not submit orders, does
not assume a latency, and does not turn an observation into a fill or a
portfolio return.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from roller.choosin_texas.models import ChoosinTexasError
from roller.choosin_texas.sources import repo_root

SUBMISSION_ACTIONS = frozenset(
    {"place_order", "submit_order", "create_order", "cancel_order", "decrease_order"}
)

OBSERVATION_SPEC_ID = "PAIRED_CANDLE_CLOSE_OBSERVATION_V1"
LIVE_QUOTE_SPEC_ID = "LIVE_QUOTE_TRIGGER"
TRIGGER = "CANDLE_CLOSE"


def prospective_dir() -> Path:
    return repo_root() / "research" / "choosin_texas" / "execution_validation" / "prospective"


def spec_path() -> Path:
    return prospective_dir() / "observation_spec.json"


def observation_policy() -> dict[str, Any]:
    """What this research signal is, and which order choices are still open.

    Rest duration, cancel time, and exit priority are unresolved on purpose.
    Assigning them would be a new economic rule and another return.
    """
    return {
        "observation_spec_id": OBSERVATION_SPEC_ID,
        "live_execution": "LIVE_EXECUTION_DISABLED",
        "live_authorized": False,
        "historical_signal": "The candle-path results remain the reference. They are not an achievable portfolio return.",
        "achievable_portfolio_return": "UNKNOWN",
        "return_calculation": "BLOCKED",
        "trigger": TRIGGER,
        "trigger_definition": (
            "Entry is the first tradable minute whose yes bid close is at or above 80 cents "
            "after a prior tradable close below 80. A stop is a later tradable minute whose "
            "yes bid close is at or below 40 or 65."
        ),
        "live_quote_trigger": "NOT_THIS_SPECIFICATION",
        "live_quote_spec_id": LIVE_QUOTE_SPEC_ID,
        "live_quote_note": (
            "Reacting to a quote inside the minute is a different implementation. "
            "Minute candles cannot reproduce it. This collector rejects that trigger."
        ),
        "latency": "UNASSUMED",
        "latency_note": (
            "No delay after the close is assumed. Each observation keeps the exchange "
            "timestamp and the local receive timestamp. An order is not eligible before "
            "that close has been received."
        ),
        "hypothetical_order_intent": (
            "After the qualifying minute close is received, record a hypothetical post-only "
            "buy YES at 80 cents. That record is not an order and is not sent."
        ),
        "entry_order": "Post-only buy YES at 80 cents. Hypothetical only.",
        "entry_rest": "POLICY_UNRESOLVED",
        "entry_cancel": "POLICY_UNRESOLVED",
        "entry_note": (
            "How long the 80 cent bid may rest, and what cancels its unfilled remainder, "
            "are still unresolved. No numeric lifetime is added here."
        ),
        "exit_priority": "POLICY_UNRESOLVED",
        "exit_fallback": "NOT_SELECTED",
        "exit_note": (
            "Whether a stop waits for a maker exit or attempts prompt reduction is unresolved. "
            "Pricing and fallback rules are not selected. A stop close is only a detection."
        ),
        "simulated_fills": "BLOCKED",
        "market_data": (
            "Record quotes, depth, public trades, candle closes, and exchange and receive "
            "timestamps. Do not score a fill or a return from those records."
        ),
        "submits": False,
    }


def install_observation_spec(dest: Path | None = None) -> dict[str, Any]:
    """Freeze the observation contract once. Later calls keep the original timestamp."""
    root = dest or prospective_dir()
    root.mkdir(parents=True, exist_ok=True)
    path = root / "observation_spec.json"
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    frozen_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    body = observation_policy()
    body["spec_frozen_at"] = frozen_at
    body["observations_collected_at_freeze"] = 0
    path.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
    (root / "STATUS.txt").write_text(
        "\n".join(
            [
                "CONFIGURED",
                "trigger=CANDLE_CLOSE",
                "live_quote_trigger=NOT_THIS_SPECIFICATION",
                "hypothetical_order_intent=RECORDED_NOT_SENT",
                "entry_rest=POLICY_UNRESOLVED",
                "entry_cancel=POLICY_UNRESOLVED",
                "exit_priority=POLICY_UNRESOLVED",
                "latency=UNASSUMED",
                "simulated_fills=BLOCKED",
                "return_calculation=BLOCKED",
                "submits=false",
                "credentials_read=false",
                "websocket=NOT_STARTED",
                "observations_collected=0",
                f"spec_frozen_at={frozen_at}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (root / "observations").mkdir(exist_ok=True)
    return body


def _record_count(root: Path) -> int:
    total = 0
    for name in ("observations", "market_data"):
        folder = root / name
        if not folder.is_dir():
            continue
        for path in folder.glob("*.jsonl"):
            with path.open(encoding="utf-8") as handle:
                total += sum(1 for line in handle if line.strip())
    return total


def collector_health(dest: Path | None = None) -> dict[str, Any]:
    root = dest or prospective_dir()
    spec = install_observation_spec(root)
    state_path = root / "collector_state.json"
    state: dict[str, Any] = {}
    if state_path.is_file():
        state = json.loads(state_path.read_text(encoding="utf-8"))
    last = state.get("last_poll_received_ts")
    fresh = False
    if last:
        age = (datetime.now(timezone.utc) - _parse_ts(last, label="last_poll")).total_seconds()
        fresh = age <= 180
    if fresh:
        status = "COLLECTING"
        feed = state.get("feed") or "REST_PUBLIC"
    elif state:
        status = "STALE"
        feed = state.get("feed") or "REST_PUBLIC"
    else:
        status = "CONFIGURED"
        feed = "NOT_STARTED"
    return {
        "status": status,
        "feed": feed,
        "observation_spec_id": OBSERVATION_SPEC_ID,
        "trigger": TRIGGER,
        "submits": False,
        "credentials_read": False,
        "websocket": "NOT_STARTED",
        "simulated_fills": "BLOCKED",
        "observations_collected": _record_count(root),
        "markets_seen": state.get("markets_seen"),
        "spec_frozen_at": spec["spec_frozen_at"],
        "return_calculation": "BLOCKED",
        "hypothetical_order_intent": "RECORDED_NOT_SENT",
        "entry_rest": "POLICY_UNRESOLVED",
        "entry_cancel": "POLICY_UNRESOLVED",
        "exit_priority": "POLICY_UNRESOLVED",
        "latency": "UNASSUMED",
        "last_poll_received_ts": last,
        "note": (
            "Public market data may be collected before the entry lifetime and the stop "
            "response are chosen. A hypothetical 80 cent intent is a record, not an order. "
            "Fills and returns stay blocked."
        ),
    }


def accept_observation(record: dict[str, Any], *, dest: Path | None = None) -> dict[str, Any]:
    """Store one read-only market observation. A quote is not a fill."""
    action = record.get("action")
    if action in SUBMISSION_ACTIONS:
        raise ChoosinTexasError("LOCK_MISMATCH", "execution validation cannot submit orders")
    trigger = record.get("trigger")
    if trigger == "LIVE_QUOTE":
        raise ChoosinTexasError(
            "LOCK_MISMATCH",
            "a live-quote trigger is a different specification and is not collected here",
        )
    if trigger != TRIGGER:
        raise ChoosinTexasError("LOCK_MISMATCH", "observation trigger must be CANDLE_CLOSE")
    for field in ("instrument", "signal", "exchange_ts", "received_ts"):
        if record.get(field) in (None, ""):
            raise ChoosinTexasError("DATA_REQUIRED", f"observation missing {field}")
    exchange_ts = _parse_ts(record["exchange_ts"], label="exchange_ts")
    received_ts = _parse_ts(record["received_ts"], label="received_ts")
    eligible = received_ts >= exchange_ts
    stored = {
        "observation_spec_id": OBSERVATION_SPEC_ID,
        "instrument": record["instrument"],
        "signal": record["signal"],
        "trigger": TRIGGER,
        "exchange_ts": exchange_ts.isoformat(),
        "received_ts": received_ts.isoformat(),
        "yes_bid_cents": record.get("yes_bid_cents"),
        "yes_ask_cents": record.get("yes_ask_cents"),
        "depth_contracts": record.get("depth_contracts"),
        "sequence": record.get("sequence"),
        "record_kind": "HYPOTHETICAL_ORDER_INTENT",
        "sent": False,
        "intent_eligible": eligible,
        "evidence_level": "OBSERVED_MARKET_DATA",
        "fill_label": None,
        "modeled_filled_contracts": None,
        "portfolio_pnl": "NOT_REPORTED",
    }
    if not eligible:
        stored["clock_status"] = "RECEIVED_BEFORE_EXCHANGE"
    root = dest or prospective_dir()
    install_observation_spec(root)
    folder = root / "observations"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{record['instrument']}.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(stored) + "\n")
    return stored


def _parse_ts(value: Any, *, label: str) -> datetime:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(int(value), tz=timezone.utc)
    text = str(value)
    if text.isdigit():
        return datetime.fromtimestamp(int(text), tz=timezone.utc)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ChoosinTexasError("DATA_REQUIRED", f"{label} is not a timestamp") from exc
    if parsed.tzinfo is None:
        raise ChoosinTexasError("DATA_REQUIRED", f"{label} needs a timezone")
    return parsed.astimezone(timezone.utc)
