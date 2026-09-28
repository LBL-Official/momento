"""Covered-time slope. Stale gaps have weight zero."""

from __future__ import annotations

from roller.choosin_texas.sugarland.constants import (
    GRID_SEC,
    SLOPE_AGE_SEC,
    SLOPE_MIN_COVERAGE,
    SLOPE_MIN_SPAN_H,
    SLOPE_MIN_WEIGHTS,
)


def path_from_grid(
    grid: dict[int, tuple[int, int]],
    anchor_ts: int,
    anchor_bid: int,
    t_end: int,
    *,
    max_age: int = SLOPE_AGE_SEC,
    step: int = GRID_SEC,
) -> dict[str, object]:
    """grid maps grid timestamp -> (quote_ts, bid_e4), already freshness-filtered."""
    times = [anchor_ts]
    first_aligned = ((anchor_ts // step) + 1) * step
    t = first_aligned
    while t <= t_end:
        times.append(t)
        t += step

    kept: list[tuple[int, int, int]] = []
    quote = (anchor_ts, anchor_bid)
    if anchor_ts <= t_end and 0 <= (anchor_ts - quote[0]) <= max_age:
        kept.append((anchor_ts, quote[0], quote[1]))
    for grid_t in times[1:]:
        rec = grid.get(grid_t)
        if rec is None:
            continue
        quote_ts, bid = rec
        if quote_ts <= grid_t and grid_t - quote_ts <= max_age:
            kept.append((grid_t, quote_ts, bid))

    weights = [0.0] * len(kept)
    for i in range(len(kept) - 1):
        gap = kept[i + 1][0] - kept[i][0]
        quote_ts = kept[i][1]
        next_grid = kept[i + 1][0]
        if gap > 0 and gap <= max_age and next_grid - quote_ts <= max_age:
            weights[i] = gap / 3600.0

    covered = sum(weights)
    elapsed = max(0.0, (t_end - anchor_ts) / 3600.0)
    positive = [(kept[i], weights[i]) for i in range(len(kept)) if weights[i] > 0]
    if positive:
        span_start = positive[0][0][0]
        span_end = positive[-1][0][0] + int(round(positive[-1][1] * 3600))
        span = max(0.0, (span_end - span_start) / 3600.0)
    else:
        span = 0.0
    fraction = (covered / elapsed) if elapsed > 0 else 0.0

    above = below = unchanged = 0.0
    for (grid_t, quote_ts, bid), weight in positive:
        del grid_t, quote_ts
        if bid > anchor_bid:
            above += weight
        elif bid < anchor_bid:
            below += weight
        else:
            unchanged += weight

    bids = [bid for _g, _q, bid in kept]
    max_up = max(((b - anchor_bid) / 100.0) for b in bids) if bids else None
    max_down = min(((b - anchor_bid) / 100.0) for b in bids) if bids else None
    peak = bids[0] if bids else anchor_bid
    trough = 0
    for bid in bids:
        if bid > peak:
            peak = bid
        drop = peak - bid
        if drop > trough:
            trough = drop

    status = "OK"
    beta_pp = None
    if (
        len(positive) < SLOPE_MIN_WEIGHTS
        or span < SLOPE_MIN_SPAN_H
        or fraction < SLOPE_MIN_COVERAGE
    ):
        status = "INSUFFICIENT_COVERAGE"
    else:
        beta_pp = _weighted_slope_pp(positive, anchor_ts)
        if beta_pp is None:
            status = "INSUFFICIENT_VARIATION"

    share_den = covered if covered > 0 else None
    return {
        "status": status,
        "beta_pp_per_hour": beta_pp,
        "n_kept": len(kept),
        "n_positive_weights": len(positive),
        "covered_hours": covered,
        "uncovered_hours": max(0.0, elapsed - covered),
        "elapsed_hours": elapsed,
        "coverage_fraction": fraction,
        "span_hours": span,
        "share_above": (above / share_den) if share_den else None,
        "share_below": (below / share_den) if share_den else None,
        "share_unchanged": (unchanged / share_den) if share_den else None,
        "max_appreciation_pp": max_up,
        "max_drawdown_pp": max_down,
        "peak_to_trough_pp": trough / 100.0,
    }


def _weighted_slope_pp(
    positive: list[tuple[tuple[int, int, int], float]],
    anchor_ts: int,
) -> float | None:
    sw = sx = sy = sxx = sxy = 0.0
    for (grid_t, _quote_ts, bid), weight in positive:
        x = (grid_t - anchor_ts) / 3600.0
        y = bid / 10000.0
        sw += weight
        sx += weight * x
        sy += weight * y
        sxx += weight * x * x
        sxy += weight * x * y
    den = sw * sxx - sx * sx
    if den == 0:
        return None
    beta = (sw * sxy - sx * sy) / den
    return 100.0 * beta
