"""TK Ultra desk. Relative Value Hedging frontend. Not live."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from roller.momento.registry import LIVE_EXECUTION
from roller.momento.relative_value import evaluate, parse_price
from roller.paths import find_root, momento_root

SCHEMA = "tk_ultra_desk_v1"
SYSTEM_ID = "relative_value_hedging"
METHOD = "tk_relative_value_v1"

NQ_ES_EXAMPLE = {
    "label": "TK letter NQ vs ES",
    "wing_name": "Nasdaq futures",
    "base_name": "ES futures",
    "wing_price": "14033",
    "base_price": "4382.50",
    "beta": "1.325",
    "beta_note": "NQ vol 28.5 / ES vol 21.5",
    "wing_anchor": "13954.8",
    "base_anchor": "4349.46",
    "ticks_per_handle": 4,
    "published": {
        "multiplier": "4.2427",
        "expected_move": "140.1788",
        "residual": "-61.979",
        "rv_ticks": "-247.92",
        "note": "Letter rounded 4.2427 as an intermediate. Engine ticks still print -247.92.",
    },
}


class TkUltraError(ValueError):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def _repo() -> Path:
    return momento_root(find_root())


def source_letter_path() -> Path:
    return _repo() / "research" / "tk_ultra" / "SOURCE_LETTER.md"


def _letter() -> dict[str, str]:
    path = source_letter_path()
    if not path.is_file():
        raise TkUltraError("SOURCE_LETTER_MISSING", "TK Ultra source letter is missing", 500)
    return {
        "from_name": "Louie Weinhaus",
        "from_email": "louiexfinance@gmail.com",
        "date": "Aug 27, 2026, 4:24 AM",
        "to": "me",
        "subject": "Relative Value",
        "path": "research/tk_ultra/SOURCE_LETTER.md",
        "body": path.read_text(encoding="utf-8"),
    }


def _nq_es_engine() -> dict[str, Any]:
    result = evaluate(
        wing_price=parse_price(NQ_ES_EXAMPLE["wing_price"], field="wing_price"),
        base_price=parse_price(NQ_ES_EXAMPLE["base_price"], field="base_price"),
        beta=parse_price(NQ_ES_EXAMPLE["beta"], field="beta"),
        wing_anchor=parse_price(NQ_ES_EXAMPLE["wing_anchor"], field="wing_anchor"),
        base_anchor=parse_price(NQ_ES_EXAMPLE["base_anchor"], field="base_anchor"),
        ticks_per_handle=int(NQ_ES_EXAMPLE["ticks_per_handle"]),
    )
    return result.payload()


def handle_desk() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "live_execution": LIVE_EXECUTION,
        "system_id": SYSTEM_ID,
        "title": "TK Ultra",
        "subtitle": "Relative value hedging · tk_relative_value_v1",
        "product": "TK Ultra",
        "named_for": "TK",
        "candle_path_not_fill": True,
        "binary_formula_is_truth": False,
        "model_mode_generic": "GENERIC_RV",
        "model_mode_first80": "BINARY_COMPLEMENT_V0",
        "hash": "#/tk-ultra",
        "note": (
            "TK Ultra is the Relative Value Hedging frontend. Not an 18th system. "
            "The formula compiles a relationship into one signed tick number. "
            "It is not market truth, not a fill, and not permission to submit."
        ),
        "source_letter": _letter(),
        "formula": {
            "method": METHOD,
            "steps": [
                "(wing_price / base_price) * beta = relationship_multiplier",
                "(base_price - base_anchor) * multiplier = expected_wing_move",
                "wing_price - (expected_wing_move + wing_anchor) = residual",
                "residual * ticks_per_handle = rv_ticks",
            ],
            "reading": {
                "WING_CHEAP": "residual < 0. Wing is cheap vs the base move. Prefer buying the wing as the hedge.",
                "WING_RICH": "residual > 0. Wing is rich vs the base move. Prefer reducing the base directly.",
                "FAIR_LINE": "residual = 0. Relationship is on this formula's line. Richness does not choose the leg.",
            },
        },
        "worked_example": {
            **NQ_ES_EXAMPLE,
            "engine": _nq_es_engine(),
        },
        "corridor": {
            "owner_when": "hedging_analysis",
            "owner_rich_cheap": "relative_value_hedging",
            "bdr_route": "#/bdr/liquidation-corridor",
            "windows": [
                {
                    "cents": 80,
                    "role": "entry_hold",
                    "bdr": "Position is open. Watch. Do not invent a hedge.",
                    "tk": "Store anchors: base_anchor = A at fill, wing_anchor = B at the same as-of.",
                },
                {
                    "cents": 45,
                    "role": "start_hedge",
                    "bdr": "Start working the hedge. Maker-first. This is not a fill.",
                    "tk": "Run tk_relative_value_v1 on observed A now vs observed B now. Missing B = SOURCE_UNAVAILABLE.",
                },
                {
                    "cents": 35,
                    "role": "finish_hedge",
                    "bdr": "Finish the hedge / exit window. Still not a live rule.",
                    "tk": "Re-run on the 35 print. Same reading: cheap wing → buy B; rich wing → sell A.",
                },
            ],
            "pair": {
                "base": "A = favorite YES already owned (entry ~80).",
                "wing": "B = opponent YES (or NO of A) that would be bought as the hedge.",
                "beta_same_direction": "vol(wing) / vol(base). TK letter: 28.5 / 21.5 = 1.325.",
                "beta_inverse": "Negative of that ratio when the products move opposite (A YES vs B YES of the same game).",
                "ticks_per_handle": "Kalshi cents: 1. Nasdaq quarter-ticks: 4.",
            },
            "implementation": [
                "BDR answers WHEN exposure should change (45 start, 35 finish).",
                "TK Ultra answers WHETHER B is cheap or rich vs A's move from the entry anchors.",
                "Observe B. Do not invent B from 100 − A. Complement identity is not tk_relative_value_v1.",
                "beta is a measured vol ratio, not a live signal. Unmeasured beta = SOURCE_UNAVAILABLE.",
                "rv_ticks < 0 → WING_CHEAP → prefer BUY B (hedge instead of a stop on A).",
                "rv_ticks > 0 → WING_RICH → prefer SELL A (direct reduction). Buying B is the expensive leg.",
                "The number is a research residual. Candle path ≠ fill. Does not submit. Does not change FIRST01 / 80/81/83/89.",
            ],
            "missing_wing": "SOURCE_UNAVAILABLE",
        },
        "limitations": [
            "LIVE EXECUTION = FALSE",
            "CANDLE PATH ≠ FILL",
            "GENERIC_RV = tk_relative_value_v1 futures ratio. BINARY_COMPLEMENT_V0 = FIRST80 A/B YES.",
            "Do not run (wing/base)*beta on A/B YES.",
            "tk_relative_value_v1 is a formula, not market truth.",
            "Do not invent a wing price, residual, L2, or fill.",
            "YES + NO ≈ 100 is a quote identity. It is not GENERIC_RV.",
            "BUY NO as taker is not implemented. This desk does not route orders.",
            "Hedging Analysis is an optional sibling. It is not model input.",
            "Position Management is NOT_IMPLEMENTED.",
        ],
    }


def handle_assess(
    *,
    wing_price: str | None,
    base_price: str | None,
    beta: str | None,
    wing_anchor: str | None,
    base_anchor: str | None,
    ticks_per_handle: str | None,
    pair: str | None = None,
    corridor_cents: str | None = None,
) -> dict[str, Any]:
    fields = {
        "wing_price": wing_price,
        "base_price": base_price,
        "beta": beta,
        "wing_anchor": wing_anchor,
        "base_anchor": base_anchor,
    }
    missing = [name for name, value in fields.items() if not str(value or "").strip()]
    if missing:
        return {
            "schema": SCHEMA,
            "live_execution": LIVE_EXECUTION,
            "system_id": SYSTEM_ID,
            "method": METHOD,
            "model_mode": "GENERIC_RV",
            "status": "SOURCE_UNAVAILABLE",
            "binary_formula_is_truth": False,
            "missing": missing,
            "detail": "Missing input. Do not invent a wing, beta, or residual.",
            "pair": pair,
            "corridor_cents": corridor_cents,
        }
    try:
        ticks = int(str(ticks_per_handle or "1").strip())
    except ValueError as exc:
        raise TkUltraError("INVALID_INPUT", "ticks_per_handle must be an integer") from exc
    try:
        result = evaluate(
            wing_price=parse_price(str(wing_price), field="wing_price"),
            base_price=parse_price(str(base_price), field="base_price"),
            beta=parse_price(str(beta), field="beta"),
            wing_anchor=parse_price(str(wing_anchor), field="wing_anchor"),
            base_anchor=parse_price(str(base_anchor), field="base_anchor"),
            ticks_per_handle=ticks,
        )
    except ValueError as exc:
        raise TkUltraError("INVALID_INPUT", str(exc)) from exc
    body = result.payload()
    body.update(
        {
            "schema": SCHEMA,
            "system_id": SYSTEM_ID,
            "model_mode": "GENERIC_RV",
            "pair": pair,
            "corridor_cents": corridor_cents,
        }
    )
    if corridor_cents:
        try:
            cents = int(str(corridor_cents).strip())
        except ValueError as exc:
            raise TkUltraError("INVALID_INPUT", "corridor_cents must be an integer") from exc
        if cents == 45:
            body["corridor_note"] = (
                "45 is BDR start-hedge. Negative ticks → prefer BUY B. "
                "Positive ticks → prefer SELL A. Not a fill."
            )
        elif cents == 35:
            body["corridor_note"] = (
                "35 is BDR finish-hedge. Re-read richness. Still not a live rule."
            )
        elif cents == 80:
            body["corridor_note"] = "80 is entry/hold. Anchors belong here. Do not hedge from this print alone."
        else:
            body["corridor_note"] = "corridor_cents is annotation only. Not a live barrier."
    return body
