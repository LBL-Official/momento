"""Family G — game–market coupling (robust to near-zero denominators)."""

from __future__ import annotations

from common import mean


def _safe_ratio(num, den, eps=0.25):
    if num is None or den is None:
        return None
    if abs(den) < eps:
        return None
    return float(num) / float(den)


def coupling_features(pre_poss: list[dict], pre_ov: list[dict]) -> dict:
    pairs = []
    n = min(len(pre_poss), len(pre_ov))
    for p, o in zip(pre_poss[-n:], pre_ov[-n:] if pre_ov else []):
        d0, d1 = p.get("score_differential_start"), p.get("score_differential_end")
        gd = None if d0 is None or d1 is None else d1 - d0
        md = o.get("market_change_during_cents")
        to = p.get("turnover")
        lc = p.get("lead_change")
        pairs.append((gd, md, to, lc, o.get("alignment_quality")))
    w = pairs[-10:]
    ratios = [_safe_ratio(md, gd) for gd, md, *_ in w]
    after_to = [md for gd, md, to, lc, q in w if to and md is not None]
    after_lc = [md for gd, md, to, lc, q in w if lc and md is not None]
    game_move = [gd for gd, md, *_ in w if gd is not None]
    mkt_move = [md for gd, md, *_ in w if md is not None]
    # Regime
    gm = mean([abs(x) for x in game_move]) if game_move else None
    mm = mean([abs(x) for x in mkt_move]) if mkt_move else None
    regime = "UNAVAILABLE"
    if gm is not None and mm is not None:
        if gm >= 0.5 and mm >= 1.0:
            regime = "GAME_MOVES_MARKET_RESPONDS"
        elif gm >= 0.5 and mm < 0.5:
            regime = "GAME_MOVES_MARKET_QUIET"
        elif gm < 0.35 and mm >= 1.5:
            regime = "SMALL_GAME_LARGE_MARKET"
        elif gm < 0.35 and mm < 0.5:
            regime = "BOTH_STABLE"
        else:
            regime = "MIXED"
    cons = None
    rs = [r for r in ratios if r is not None]
    if len(rs) >= 3:
        cons = 1.0 - (max(rs) - min(rs)) / (abs(mean(rs)) + 1.0)
    return {
        "coupling_response_per_score_10p": mean(ratios),
        "coupling_mkt_after_turnover_10p": mean(after_to),
        "coupling_mkt_after_lead_change_10p": mean(after_lc),
        "coupling_consistency_10p": cons,
        "coupling_regime": regime,
        "coupling_observed_or_derived": "DERIVED_PROXY",
        "coupling_not_causal_proof": True,
    }
