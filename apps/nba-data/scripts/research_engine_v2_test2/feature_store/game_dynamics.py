"""Families C, D, H — possession-space velocity, volatility, physics (DERIVED PROXY)."""

from __future__ import annotations

from common import mean, stdev


def game_dynamics_features(pre: list[dict]) -> dict:
    w5 = pre[-5:] if pre else []
    w10 = pre[-10:] if pre else []
    w20 = pre[-20:] if pre else []

    def nets(w):
        xs = []
        for p in w:
            d0, d1 = p.get("score_differential_start"), p.get("score_differential_end")
            if d0 is not None and d1 is not None:
                xs.append(d1 - d0)
        return xs

    n5, n10, n20 = nets(w5), nets(w10), nets(w20)
    v5 = mean(n5)
    v10 = mean(n10)
    accel = None if v5 is None or v10 is None else v5 - v10
    instab5 = None
    if n5:
        rev = 0
        signs = [1 if x > 0 else (-1 if x < 0 else 0) for x in n5]
        for a, b in zip(signs, signs[1:]):
            if a and b and a != b:
                rev += 1
        instab5 = rev / max(1, len(n5) - 1)
    # Entropy of points scored (coarse)
    pts = [int(p.get("points_scored") or 0) for p in w10]
    entropy = None
    if pts:
        from collections import Counter
        import math

        c = Counter(pts)
        n = len(pts)
        entropy = -sum((v / n) * math.log((v / n) + 1e-12) for v in c.values())

    regime = "STABLE"
    if instab5 is not None and instab5 >= 0.45:
        regime = "OSCILLATORY"
    elif accel is not None and accel > 0.4:
        regime = "ACCELERATING"
    elif accel is not None and accel < -0.4:
        regime = "DECELERATING"
    elif v5 is not None and abs(v5) >= 0.3:
        regime = "PERSISTENT"

    return {
        "net_score_per_poss_5p": v5,
        "net_score_per_poss_10p": v10,
        "abs_score_per_poss_10p": None if not n10 else mean([abs(x) for x in n10]),
        "score_diff_std_5p": stdev(n5),
        "score_diff_std_10p": stdev(n10),
        "score_diff_range_10p": None if not n10 else (max(n10) - min(n10)),
        "lead_reversal_freq_10p": None
        if not w10
        else sum(int(p.get("lead_change") or 0) for p in w10) / max(1, len(w10)),
        "possession_outcome_entropy_10p": entropy,
        "game_acceleration_5_vs_10": accel,
        "game_instability_5p": instab5,
        "game_momentum_5p": v5,
        "game_inertia_10p": None if v10 is None else abs(v10),
        "game_regime": regime,
        "observed_or_derived": "DERIVED_PROXY",
    }
