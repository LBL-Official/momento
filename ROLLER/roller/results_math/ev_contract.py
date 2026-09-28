"""Results EV data-contract. PATH WIN is never settlement YES."""

from __future__ import annotations

from typing import Any

from roller.results_math.models import DERIVED, HYPOTHETICAL, OBSERVED, UNAVAILABLE

INVARIANTS = (
    "PATH WIN ≠ SETTLEMENT YES",
    "PATH LOSS ≠ SETTLEMENT NO",
    "OBSERVED PATH EV ≠ BOOK-PRICE EV ≠ SETTLEMENT EV",
    "Missing terminal is not NO and is not path WIN",
)


def ev_contract() -> dict[str, Any]:
    """Permanent definitions. UI copy must not invent a fourth EV object."""
    return {
        "status": OBSERVED,
        "invariants": list(INVARIANTS),
        "objects": {
            "observed_path_ev": {
                "label": "OBSERVED PATH EV",
                "provenance": OBSERVED,
                "formula": "E[exit_close − entry_close]",
                "unit": "cents / contract",
                "not": ["fill", "book_price_ev", "settlement_ev", "profit"],
            },
            "book_price_ev": {
                "label": "BOOK-PRICE EV",
                "provenance": HYPOTHETICAL,
                "formula": "P(WIN)×(WIN_price − entry) + P(LOSS)×(LOSS_price − entry)",
                "unit": "cents / contract",
                "not": ["observed_path_ev", "settlement_ev", "profit"],
            },
            "settlement_ev": {
                "label": "SETTLEMENT EV",
                "provenance": DERIVED,
                "formula": "P(YES)×(100¢ − entry) + P(NO)×(0¢ − entry)",
                "unit": "cents / contract",
                "unavailable_when": "measured Kalshi YES/NO absent",
                "unavailable_status": UNAVAILABLE,
                "not": ["path_win", "path_loss", "invented_zero"],
            },
        },
        "note": "Three objects. Path classification is not terminal settlement.",
    }


def settlement_uses_path_rates(settlement: dict[str, Any] | None, path_true: int, path_available: int) -> bool:
    """True if settlement EV was illegally substituted from path rates.

    Official YES/NO counts may equal path-true / path-available by chance —
    a one-trade query that path-wins and settles YES is legitimate, not a
    substitution. Detect provenance, not numeric coincidence.
    ``path_true`` / ``path_available`` stay in the signature for callers.
    """
    del path_true, path_available
    if not settlement or settlement.get("status") == UNAVAILABLE:
        return False
    source = str(settlement.get("source") or settlement.get("provenance") or "")
    if source in {"path_rates", "path", "path_true"}:
        return True
    return settlement.get("substituted_from_path") is True
