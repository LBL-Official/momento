"""Level 2: observable opportunity and occupancy. Not a fill."""

from __future__ import annotations

import math

from .enums import (
    AMBIGUOUS_SEQUENCE,
    BAND_OBSERVATION,
    EXACT_OBSERVATION,
    GAP_THROUGH,
    INVALID_OBSERVATION,
    L2,
    NO_OBSERVATION,
    OCC_AMBIG,
    OCC_BAND,
    OCC_EXACT,
    OCC_INFERRED,
    OCC_NOT,
    THRESHOLD_REACHED,
)


def _finite(x) -> float | None:
    if x is None:
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    if math.isnan(v) or math.isinf(v):
        return None
    return v


def classify_l2(
    opportunity_close: bool,
    opportunity_high: bool,
    obs_close,
    jump_10c: bool,
    threshold: int,
    band_lo: int,
    band_hi: int,
) -> dict:
    """Classify the first post-entry close ≥ threshold (V3 already next-bar).

    THRESHOLD_CROSSING can be true while EXACT_OBSERVATION is false.
    GAP_THROUGH never becomes occupancy confirmed.
    """
    obs = _finite(obs_close)
    if not opportunity_close:
        if opportunity_high:
            return {
                "opportunity_class": AMBIGUOUS_SEQUENCE,
                "market_occupancy_status": OCC_AMBIG,
                "threshold_reached": False,
                "threshold_crossing": False,
                "gap_through": False,
                "observed_price": None,
                "evidence_level": L2,
                "evidence_confidence": "WICK_ONLY",
                "note": "High touched region; close did not. Not occupancy.",
            }
        return {
            "opportunity_class": NO_OBSERVATION,
            "market_occupancy_status": OCC_NOT,
            "threshold_reached": False,
            "threshold_crossing": False,
            "gap_through": False,
            "observed_price": None,
            "evidence_level": L2,
            "evidence_confidence": "NONE",
            "note": "No post-entry close ≥ threshold.",
        }
    if obs is None:
        return {
            "opportunity_class": INVALID_OBSERVATION,
            "market_occupancy_status": OCC_AMBIG,
            "threshold_reached": True,
            "threshold_crossing": True,
            "gap_through": False,
            "observed_price": None,
            "evidence_level": L2,
            "evidence_confidence": "MISSING_CLOSE",
            "note": "Close flag set without a finite close.",
        }

    crossing = obs >= threshold
    jumped = bool(jump_10c) or obs > band_hi
    in_band = band_lo <= obs <= band_hi

    if jumped or not in_band:
        return {
            "opportunity_class": GAP_THROUGH,
            "market_occupancy_status": OCC_INFERRED,
            "threshold_reached": crossing,
            "threshold_crossing": crossing,
            "gap_through": True,
            "observed_price": obs,
            "evidence_level": L2,
            "evidence_confidence": "CROSSING_WITHOUT_OCCUPANCY",
            "note": "Market ended above the band or jumped ≥10¢. Occupancy of H is not observed.",
        }
    if abs(obs - threshold) < 1e-9:
        cls = EXACT_OBSERVATION
        occ = OCC_EXACT
        extra = THRESHOLD_REACHED
    else:
        cls = BAND_OBSERVATION
        occ = OCC_BAND
        extra = THRESHOLD_REACHED
    return {
        "opportunity_class": cls,
        "secondary_class": extra,
        "market_occupancy_status": occ,
        "threshold_reached": True,
        "threshold_crossing": True,
        "gap_through": False,
        "observed_price": obs,
        "evidence_level": L2,
        "evidence_confidence": "CLOSE_IN_BAND",
        "note": "Observed close occupies the band. Still not a fill.",
    }
