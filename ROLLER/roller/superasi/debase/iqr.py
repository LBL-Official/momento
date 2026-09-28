"""IQR 1 (Q1) of a strategy's win-rate evidence. Generic — not one lab."""

from __future__ import annotations

from typing import Any

from roller.risk.formulas import RiskConfigError, wilson_interval, wilson_interval_from_p
from roller.superasi.base.versions import WILSON_Z
from roller.superasi.debase.versions import P_WORKING_BASIS, WILSON_Z_IQR1
from roller.superasi.models import SuperasiError


def iqr_hinges(*, wins: int, decided: int) -> dict[str, float]:
    """Wilson IQR box on decided trade rows. IQR 1 = Q1, the lowest hinge."""
    try:
        p_hat, q1, q3 = wilson_interval(int(wins), int(decided), z=WILSON_Z_IQR1)
    except RiskConfigError as exc:
        raise SuperasiError("PAYOFF_REQUIRED", "IQR 1 requires decided trade rows") from exc
    return {
        "p_hat": float(p_hat),
        "p_iqr1": float(q1),
        "p_iqr3": float(q3),
        "iqr": float(q3) - float(q1),
        "z": WILSON_Z_IQR1,
        "basis": P_WORKING_BASIS,
    }


def working_p_from_observed(observed: dict[str, Any]) -> dict[str, float]:
    wins = int(observed.get("wins") or 0)
    decided = int(observed.get("decided") or 0)
    if decided <= 0:
        raise SuperasiError("PAYOFF_REQUIRED", "IQR 1 requires decided trade rows")
    hinges = iqr_hinges(wins=wins, decided=decided)
    try:
        _, lo_w, hi_w = wilson_interval_from_p(hinges["p_iqr1"], decided, z=WILSON_Z)
    except RiskConfigError as exc:
        raise SuperasiError("PAYOFF_REQUIRED", "Wilson interval around IQR 1 is required") from exc
    return {
        **hinges,
        "p_working": hinges["p_iqr1"],
        "wilson_lower_at_iqr1": float(lo_w),
        "wilson_upper_at_iqr1": float(hi_w),
        "wilson_width_at_iqr1": float(hi_w) - float(lo_w),
    }
