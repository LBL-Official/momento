"""Entry-time associations. Lead time from actual start is descriptive only."""

from __future__ import annotations

from typing import Any

from roller.choosin_texas.sugarland.constants import ENTRY_FEATURES


def design_entry(row: dict[str, Any]) -> dict[str, float]:
    """Features known from the anchor quote. No actual-start lead time."""
    sport = str(row.get("sport") or "")
    volume = row.get("p0_volume")
    spread = row.get("p0_spread_e4")
    bid = row.get("p0_bid_e4")
    return {
        "anchor_bid_pp": 0.0 if bid is None else float(bid) / 100.0,
        "spread_cents": 0.0 if spread is None else float(spread) / 100.0,
        "volume": 0.0 if volume is None else float(volume),
        "is_nba": 1.0 if sport == "NBA" else 0.0,
        "is_ncaab": 1.0 if sport == "NCAAB" else 0.0,
        "is_wnba": 1.0 if sport == "WNBA" else 0.0,
        "is_mlb": 1.0 if sport == "MLB" else 0.0,
    }


def design_descriptive(row: dict[str, Any]) -> dict[str, float]:
    features = design_entry(row)
    lead = row.get("lead_hours_descriptive")
    features["lead_hours_actual_start"] = 0.0 if lead is None else float(lead)
    return features


def fit_association(rows: list[dict[str, Any]], *, descriptive: bool = False) -> dict[str, Any]:
    usable = [row for row in rows if row.get("dpp") is not None and row.get("in_a")]
    role = "DESCRIPTIVE_NOT_A_FORECAST" if descriptive else "ENTRY_TIME_ASSOCIATION"
    names = list(ENTRY_FEATURES) + (["lead_hours_actual_start"] if descriptive else [])
    if "lead_hours_actual_start" in ENTRY_FEATURES:
        raise RuntimeError("entry-time features must not include actual-start lead time")
    if len(usable) < max(30, len(names) * 10):
        return {"role": role, "status": "INSUFFICIENT_N", "n": len(usable), "features": names}
    columns = [design_descriptive(row) if descriptive else design_entry(row) for row in usable]
    y = [float(row["dpp"]) for row in usable]
    design = [[1.0] + [float(col[name]) for name in names] for col in columns]
    beta = _ols(design, y)
    if beta is None:
        return {"role": role, "status": "SINGULAR", "n": len(usable), "features": ["intercept", *names]}
    return {
        "role": role,
        "status": "OBSERVED",
        "n": len(usable),
        "features": ["intercept", *names],
        "coefficients_dpp": beta,
        "note": "association only; not a trading forecast",
    }


def _ols(design: list[list[float]], y: list[float]) -> list[float] | None:
    # Normal equations via Gaussian elimination. p is small.
    p = len(design[0])
    n = len(y)
    xtx = [[0.0 for _ in range(p)] for _ in range(p)]
    xty = [0.0 for _ in range(p)]
    for i in range(n):
        row = design[i]
        for a in range(p):
            xty[a] += row[a] * y[i]
            for b in range(p):
                xtx[a][b] += row[a] * row[b]
    matrix = [xtx[a] + [xty[a]] for a in range(p)]
    for col in range(p):
        pivot = max(range(col, p), key=lambda r: abs(matrix[r][col]))
        if abs(matrix[pivot][col]) < 1e-12:
            return None
        matrix[col], matrix[pivot] = matrix[pivot], matrix[col]
        scale = matrix[col][col]
        for j in range(col, p + 1):
            matrix[col][j] /= scale
        for r in range(p):
            if r == col:
                continue
            factor = matrix[r][col]
            for j in range(col, p + 1):
                matrix[r][j] -= factor * matrix[col][j]
    return [matrix[i][p] for i in range(p)]
