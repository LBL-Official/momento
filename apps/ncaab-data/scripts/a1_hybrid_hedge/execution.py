"""Price event vs execution event. No fictional fills.

A close crossing H is a PRICE EVENT.
A modeled hedge requires an in-band observed close (or an explicit
lookahead persist rule). Jump-through is a miss.

persist_subsequent_min is bars AFTER the first close ≥ band_lo that
remain ≥ band_lo. That is LOOKAHEAD if used as a fill gate.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Band:
    name: str
    lo: int
    hi: int
    target_h: int | None


def band_for(name: str, h: int) -> Band:
    if name == "exact":
        return Band(name, h, h, h)
    if name == "symmetric_1":
        return Band(name, h - 1, h + 1, h)
    if name == "symmetric_2":
        return Band(name, h - 2, h + 2, h)
    if name == "band_39_41":
        return Band(name, 39, 41, 40)
    if name == "band_38_42":
        return Band(name, 38, 42, 40)
    if name == "band_37_42":
        return Band(name, 37, 42, 40)
    if name == "band_35_45":
        return Band(name, 35, 45, 40)
    if name == "focus_17_22":
        return Band(name, 17, 22, 20)
    if name == "focus_27_32":
        return Band(name, 27, 32, 30)
    if name == "focus_37_42":
        return Band(name, 37, 42, 40)
    raise ValueError(name)


SURFACE_BANDS = ("exact", "symmetric_1", "symmetric_2")
NAMED_BANDS = (
    "band_39_41",
    "band_38_42",
    "band_37_42",
    "band_35_45",
    "focus_17_22",
    "focus_27_32",
    "focus_37_42",
)


def classify_opportunity(
    opportunity_close: bool,
    obs_close: float | None,
    persist_subsequent: int | None,
    jump_10c: bool,
    band: Band,
    persist_k: int,
) -> dict:
    """Classify one trade at band_lo's first close ≥ lo.

    Returns confidence labels, never CONFIRMED FILL.
    """
    if persist_subsequent is None:
        persist = 0
    else:
        try:
            persist = int(persist_subsequent)
        except (TypeError, ValueError):
            persist = 0
        if isinstance(persist_subsequent, float) and math.isnan(persist_subsequent):
            persist = 0
    total_obs = (1 + persist) if opportunity_close else 0
    if obs_close is not None and isinstance(obs_close, float) and math.isnan(obs_close):
        obs_close = None
    if not opportunity_close or obs_close is None:
        return {
            "tier": "NONE",
            "gap": False,
            "in_band": False,
            "obs_px": None,
            "total_obs": 0,
            "lookahead_t1": False,
            "label": "NO_PRICE_OPPORTUNITY",
        }
    obs = float(obs_close)
    jumped = bool(jump_10c) or obs > band.hi
    in_band = band.lo <= obs <= band.hi
    if jumped or not in_band:
        return {
            "tier": "TIER3_GAP",
            "gap": True,
            "in_band": False,
            "obs_px": obs,
            "total_obs": total_obs,
            "lookahead_t1": False,
            "label": "GAP_NO_OBSERVABLE_FILL_EVIDENCE",
        }
    lookahead_t1 = total_obs >= persist_k
    if lookahead_t1:
        tier = "TIER1"
    else:
        tier = "TIER2"
    return {
        "tier": tier,
        "gap": False,
        "in_band": True,
        "obs_px": obs,
        "total_obs": total_obs,
        "lookahead_t1": lookahead_t1,
        "label": "OBSERVABLE_EXECUTION_CONFIDENCE",
    }
