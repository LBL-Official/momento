"""Family B — rolling possession-path windows (configurable)."""

from __future__ import annotations

from common import POS_WINDOWS, mean, stdev


def _window(pre: list[dict], k: int) -> list[dict]:
    if k <= 0:
        return []
    return pre[-k:] if len(pre) >= 1 else []


def possession_path_features(pre: list[dict], team_code: str | None) -> dict:
    out = {}
    for k in POS_WINDOWS:
        w = _window(pre, k)
        n = len(w)
        pts = [p.get("points_scored") or 0 for p in w]
        to = [p.get("turnover") or 0 for p in w]
        oreb = [p.get("offensive_rebound") or 0 for p in w]
        fta = [p.get("free_throw_attempts") or 0 for p in w]
        lc = [p.get("lead_change") or 0 for p in w]
        timeouts = [p.get("timeout") or 0 for p in w]
        diffs = []
        for p in w:
            d0 = p.get("score_differential_start")
            d1 = p.get("score_differential_end")
            if d0 is not None and d1 is not None:
                diffs.append(d1 - d0)
        net = sum(diffs) if diffs else None
        abs_chg = sum(abs(x) for x in diffs) if diffs else None
        signs = [1 if x > 0 else (-1 if x < 0 else 0) for x in diffs]
        reversals = 0
        for a, b in zip(signs, signs[1:]):
            if a and b and a != b:
                reversals += 1
        persist = 0
        for a, b in zip(signs, signs[1:]):
            if a and a == b:
                persist += 1
        out[f"pts_for_{k}p"] = sum(pts) if n else None
        out[f"net_homeaway_{k}p"] = net
        out[f"abs_score_change_{k}p"] = abs_chg
        out[f"turnovers_{k}p"] = sum(to) if n else None
        out[f"oreb_{k}p"] = sum(oreb) if n else None
        out[f"fta_{k}p"] = sum(fta) if n else None
        out[f"lead_changes_{k}p"] = sum(lc) if n else None
        out[f"timeouts_{k}p"] = sum(timeouts) if n else None
        out[f"scoring_var_{k}p"] = stdev([float(x) for x in pts]) if n >= 3 else None
        out[f"directional_reversals_{k}p"] = reversals if n else None
        out[f"directional_persist_{k}p"] = persist if n else None
        out[f"n_window_{k}p"] = n
        out[f"off_eff_{k}p"] = (sum(pts) / n) if n else None
    return out
