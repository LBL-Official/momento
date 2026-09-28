"""78/67 TK Ultra handlers. Anchors 78 and 22. Sibling is the 78/67 Ballhog intent."""

from __future__ import annotations

from typing import Any

from roller.ballhog_first78.context import choosin_prior
from roller.ballhog_first78.compose import austin_n
from roller.momento.tk_ultra import handle_assess, handle_desk
from roller.tk_ultra.assessment import assess_binary, attach_sibling
from roller.tk_ultra.models import LIVE_EXECUTION, MODEL_BINARY, UNAVAILABLE


def _desk() -> dict[str, Any]:
    body = handle_desk()
    body["book"] = "FIRST78_67"
    body["hash"] = "#/tk-ultra"
    body["model_mode_first78"] = MODEL_BINARY
    body["model_mode_generic"] = "GENERIC_RV"
    body["subtitle"] = "Relative value hedging · FIRST78→67"
    body["binary_anchors"] = {"a": 78, "b": 22}
    body["context"] = {
        "austin": {
            "universe": "choosin_nba_2q3q_first78_67",
            "n": austin_n(),
            "role": "shown beside the quote",
            "model_input": False,
        },
        "choosin_texas": choosin_prior(),
    }
    body["corridor"] = {
        "owner_when": "hedging_analysis",
        "owner_rich_cheap": "relative_value_hedging",
        "bdr_route": "#/bdr/liquidation-corridor",
        "windows": [
            {"cents": 78, "role": "entry_hold", "bdr": "Position is open at the 78¢ entry. Do not invent a hedge.", "tk": "Store anchors. Complementary pair is 78 and 22."},
            {"cents": 69, "role": "start_hedge", "bdr": "Counterfactual start toward the 67 stop. Not a fill.", "tk": "Run GENERIC_RV on observed prices. Missing wing stays SOURCE_UNAVAILABLE."},
            {"cents": 67, "role": "finish_hedge", "bdr": "The 67¢ stop window. Still not a live rule.", "tk": "Re-read richness. The number is not a residual input from Austin or Choosin."},
        ],
        "pair": {
            "base": "A = favorite YES already owned (entry 78).",
            "wing": "B = opponent YES. Complement anchor is 22.",
            "beta_same_direction": "vol(wing) / vol(base). Unmeasured beta stays SOURCE_UNAVAILABLE.",
            "beta_inverse": "Negative of that ratio when the products move opposite.",
            "ticks_per_handle": "Kalshi cents: 1. Nasdaq quarter-ticks: 4.",
        },
        "implementation": [
            "Ballhog 78/67 answers WHEN on the 62–72 grid.",
            "TK Ultra answers WHETHER the wing is cheap or rich.",
            "Austin conditional value and the Choosin 78/67 prior are displayed beside the quote.",
            "Those two numbers are not inputs to the residual.",
            "78 + 22 = 100. Any other complementary pair is ANCHOR_INVALID.",
            "Candle path is not a fill. This desk does not submit.",
        ],
        "missing_wing": "SOURCE_UNAVAILABLE",
    }
    body["limitations"] = [
        "LIVE EXECUTION = FALSE",
        "CANDLE PATH ≠ FILL",
        "GENERIC_RV is the futures calculator.",
        "BINARY_COMPLEMENT_V0 defaults are anchors 78 and 22.",
        "Austin and Choosin context are not model inputs.",
        "Do not invent a wing price, residual, L2, or fill.",
    ]
    body["note"] = (
        "TK Ultra 78/67. The futures calculator is GENERIC_RV. "
        "The binary pair is 78 and 22. Sibling intent is Ballhog 78/67."
    )
    return body


def handle_health() -> dict[str, Any]:
    prior = choosin_prior()
    return {
        "ok": True,
        "product": "TK Ultra",
        "book": "FIRST78_67",
        "live_execution": LIVE_EXECUTION,
        "execution_enabled": False,
        "submits": False,
        "feed_mode": "HISTORICAL",
        "live_feed": "UNAVAILABLE",
        "model_modes": ["GENERIC_RV", MODEL_BINARY],
        "austin": {
            "universe": "choosin_nba_2q3q_first78_67",
            "n": austin_n(),
            "availability": "OBSERVED" if austin_n() else UNAVAILABLE,
            "adapter": "roller.austin_first78",
        },
        "choosin_texas": {
            "universe": "DERIVED_FOUR_FIRST78",
            "n": prior.get("n"),
            "availability": prior.get("availability"),
            "historical_ev": prior.get("historical_ev"),
            "adapter": "derived-four FIRST78_67",
            "pit_kind": "STATIC",
        },
        "ballhog": {"availability": "OBSERVED", "role": "optional_sibling", "adapter": "roller.ballhog_first78.api.handle_intent"},
        "position_management": "NOT_IMPLEMENTED",
    }


def handle_sources() -> dict[str, Any]:
    return handle_health()


def handle_generic_assess(**kwargs: Any) -> dict[str, Any]:
    body = handle_assess(**kwargs)
    cents = str(kwargs.get("corridor_cents") or "").strip()
    notes = {
        "78": "78 is the FIRST78 entry. Anchors belong here. Do not hedge from this print alone.",
        "69": "69 is a counterfactual start toward the 67 stop. Not a fill.",
        "67": "67 is the FIRST78 stop window. Re-read richness. Still not a live rule.",
    }
    if cents in notes:
        body["corridor_note"] = notes[cents]
    return body


def _sibling(trade_id: str, as_of: str | None) -> dict[str, Any]:
    from roller.ballhog.errors import BallhogError
    from roller.ballhog_first78.api import handle_intent

    try:
        intent = handle_intent(trade_id, as_of=as_of)
    except BallhogError as exc:
        return {"availability": UNAVAILABLE, "detail": exc.message, "code": exc.code}
    return {"availability": "OBSERVED", "intent": intent, "book": "FIRST78_67"}


def handle_assess_v0(body: dict[str, Any] | None) -> dict[str, Any]:
    payload = body if isinstance(body, dict) else {}
    assessment = assess_binary(payload, feed_mode=str(payload.get("feed_mode") or "MANUAL_INPUT"))
    trade_id = str(payload.get("trade_id") or "").strip()
    sibling = _sibling(trade_id, payload.get("as_of")) if trade_id and payload.get("include_sibling") else None
    assessment = attach_sibling(assessment, sibling)
    assessment["book"] = "FIRST78_67"
    assessment["context_not_model_input"] = handle_health()
    return assessment


def handle_ballhog_context(trade_id: str, as_of: str | None = None) -> dict[str, Any]:
    return _sibling(trade_id, as_of)


def handle_positions() -> dict[str, Any]:
    from roller.ballhog_first78.api import handle_positions as positions

    return positions()


def handle_state(trade_id: str, as_of: str | None = None, include_sibling: bool = False) -> dict[str, Any]:
    from roller.ballhog_first78.api import handle_state as state

    body = state(trade_id, as_of)
    if include_sibling:
        body["sibling"] = _sibling(trade_id, as_of)
    return body
