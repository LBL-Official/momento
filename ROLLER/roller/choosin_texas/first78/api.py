"""HTTP view for the active FIRST78 desk."""

from __future__ import annotations

from typing import Any

from roller.choosin_texas.first78.artifact import load_derived, load_strategy, variant_stop
from roller.choosin_texas.first78.desk import attach_desk


def handle_first78(variant: str = "67") -> dict[str, Any]:
    strategy = load_strategy()
    stop = variant_stop(variant, strategy)
    body = load_derived()
    if body.get("status") != "OBSERVED":
        body["requested_stop_cents"] = stop
        body["official_strategy_id"] = "FIRST78_67"
        return body
    if body.get("population_id") == "DERIVED_FOUR_FIRST78":
        payload = dict(body)
        payload["requested_stop_cents"] = stop
        payload["cache_key"] = f"{body.get('run_id')}:{body.get('strategy_sha256')}:derived:{stop}"
        payload["official_strategy_unchanged"] = True
        return attach_desk(payload)
    selected = next((row for row in body.get("variants") or [] if int(row["stop_cents"]) == stop), None)
    if selected is None:
        body = dict(body)
        body["status"] = "UNKNOWN_VARIANT"
        body["message"] = f"artifact has no stop {stop}"
        return body
    payload = dict(body)
    payload["requested_stop_cents"] = stop
    payload["selected"] = selected
    payload["cache_key"] = f"{body.get('run_id')}:{body.get('strategy_sha256')}:{stop}"
    payload["official_strategy_unchanged"] = payload.get("official_strategy_id") == "FIRST78_67"
    return attach_desk(payload)
