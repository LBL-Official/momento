"""Model-assumed finite-sample power diagnostic. Not an approval threshold."""

from __future__ import annotations

import math
from typing import Any

from roller.results_math.models import MODEL_ASSUMED, UNAVAILABLE
from roller.results_math.versions import WILSON_Z

# Inverse normal for 80% power (one-sided shift under two-sided α = 0.05).
Z_POWER_80 = 0.841621233572914


def minimum_detectable_ev(
    *,
    n: int,
    sample_std_cents: float | None,
    alpha: float = 0.05,
    power: float = 0.80,
) -> dict[str, Any]:
    if n < 2 or sample_std_cents is None or sample_std_cents <= 0:
        return {
            "status": UNAVAILABLE,
            "reason": "Need N >= 2 and positive sample standard deviation.",
        }
    if alpha != 0.05 or power != 0.80:
        return {
            "status": UNAVAILABLE,
            "reason": "Only the default α=0.05 / power=0.80 diagnostic is implemented.",
        }
    mde = (WILSON_Z + Z_POWER_80) * float(sample_std_cents) / math.sqrt(n)
    return {
        "status": MODEL_ASSUMED,
        "label": "MODEL-ASSUMED STATISTICAL POWER DIAGNOSTIC",
        "n": n,
        "alpha": alpha,
        "power": power,
        "sample_std_cents": float(sample_std_cents),
        "minimum_detectable_ev_cents": mde,
        "note": "Approximate two-sided normal MDE. Not an approval threshold. Independence is not assumed.",
    }
