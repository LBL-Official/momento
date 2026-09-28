"""Fee-inclusive path PnL.

Synthetic runs may use ESTIMATED_PLACEHOLDER.
Warehouse / real runs require production KalshiFeeModel — which is not
implemented in-repo (crates/risk still has ZeroFeeModel only). Fail closed.
"""

from __future__ import annotations

from roller.nba_path_fe.config import DEFAULT, PathFeConfig

GROSS_WIN_CENTS = 20
GROSS_BAIL_CENTS = -40
PLACEHOLDER_ID = "ESTIMATED_PLACEHOLDER_CENTS_PER_SIDE"
UNRESOLVED_ID = "KALSHI_FEE_MODEL_UNRESOLVED"


def resolve_fee_model(source: str) -> dict[str, str]:
    if source == "SYNTHETIC_E2E":
        return {
            "id": PLACEHOLDER_ID,
            "status": "ESTIMATED",
            "note": "Synthetic only. Not production KalshiFeeModel.",
        }
    return {
        "id": UNRESOLVED_ID,
        "status": "UNAVAILABLE",
        "note": (
            "Production KalshiFeeModel is UNRESOLVED in crates/risk "
            "(ZeroFeeModel only). Do not treat placeholder cents as venue fees."
        ),
    }


def fee_roundtrip_cents(cfg: PathFeConfig = DEFAULT) -> int | None:
    if cfg.source_tag != "SYNTHETIC_E2E":
        return None
    return int(cfg.fee_cents_per_side_est) * 2


def ev_cents(p: float, cfg: PathFeConfig = DEFAULT) -> float:
    fee = fee_roundtrip_cents(cfg)
    if fee is None:
        return float("nan")
    return float(p * (GROSS_WIN_CENTS - fee) + (1.0 - p) * (GROSS_BAIL_CENTS - fee))


def episode_pnl_cents(y: int, cfg: PathFeConfig = DEFAULT) -> int | None:
    fee = fee_roundtrip_cents(cfg)
    if fee is None:
        return None
    if int(y) == 1:
        return GROSS_WIN_CENTS - fee
    return GROSS_BAIL_CENTS - fee
