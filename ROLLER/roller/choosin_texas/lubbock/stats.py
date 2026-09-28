"""Predeclared Lubbock intervals. Payoff contrasts use integer microcents."""

from __future__ import annotations

import math
import random
import zlib
from typing import Iterable

SCALE = 1_000_000
B = 2000
Z_95 = 1.959963984540054
SEED = 604

INTERPRETATION = (
    "Terminal calibration, terminal win rate, and path survival are separate outcomes. "
    "A higher late-season win rate does not necessarily indicate better calibration. "
    "Define entry-price bands and the adjustment estimator before inspecting outcomes. "
    "Compare late and earlier observations over common entry-price/period support, "
    "report unsupported or sparse strata, and show both raw and standardized differences "
    "with uncertainty. Do not extrapolate across empty strata. Classify results from "
    "effect estimates and intervals—not the sign of a point estimate alone. A positive "
    "but imprecise estimate is inconclusive; “contradicted in this sample” requires "
    "evidence of an effect in the opposite direction."
)


def rng_for(name: str) -> random.Random:
    salt = zlib.crc32(name.encode("utf-8")) & 0xFFFFFFFF
    return random.Random(SEED ^ salt)


def scaled_mean(total: int, n: int) -> int:
    if n <= 0:
        raise ValueError("scaled mean requires n > 0")
    num = int(total) * SCALE
    half = n // 2
    if num >= 0:
        return (num + half) // n
    return -(((-num) + half) // n)


def render_micro(value: int) -> str:
    sign = "-" if value < 0 else ""
    whole, frac = divmod(abs(int(value)), SCALE)
    return f"{sign}{whole}.{frac:06d}"


def wilson(k: int, n: int) -> dict[str, str] | None:
    if n <= 0:
        return None
    p = k / n
    den = 1 + (Z_95 * Z_95) / n
    center = (p + (Z_95 * Z_95) / (2 * n)) / den
    margin = Z_95 * math.sqrt(p * (1 - p) / n + (Z_95 * Z_95) / (4 * n * n)) / den
    lo = max(0.0, center - margin)
    hi = min(1.0, center + margin)
    return {"lo": f"{lo:.6f}", "hi": f"{hi:.6f}"}


def equal_count_bounds(count: int, buckets: int) -> list[tuple[int, int, int]]:
    """Return (bucket, rank_lo, rank_hi) with extras on the earliest buckets."""
    if count < 0 or buckets <= 0:
        raise ValueError("bounds require a non-negative count and positive buckets")
    base, extra = divmod(count, buckets)
    out: list[tuple[int, int, int]] = []
    start = 1
    for index in range(buckets):
        size = base + (1 if index < extra else 0)
        if size <= 0:
            continue
        out.append((index, start, start + size - 1))
        start += size
    return out


def progress(rank: int, total: int) -> str:
    if rank < 1 or rank > total or total <= 0:
        raise ValueError("progress rank is outside 1..G")
    # (rank - 0.5) / G at micro-unit scale, rendered as a decimal.
    return render_micro(scaled_mean(2 * rank - 1, 2 * total))


def holm_at_most_5_percent(numer: int, denom: int) -> bool:
    return denom > 0 and numer * 20 <= denom


def classify_holm(*, estimate: int, lo: int, hi: int, holm_numer: int, holm_denom: int) -> str:
    """Supported or contradicted only when the interval and the Holm p-value agree."""
    rejects = holm_at_most_5_percent(holm_numer, holm_denom)
    if estimate > 0 and lo > 0 and hi > 0 and rejects:
        return "supported_in_this_sample"
    if estimate < 0 and lo < 0 and hi < 0 and rejects:
        return "contradicted_in_this_sample"
    return "inconclusive"


def percentile_interval(samples: list[int]) -> tuple[int, int]:
    if len(samples) != B:
        raise ValueError(f"percentile interval requires B={B}")
    ordered = sorted(samples)
    return ordered[49], ordered[1949]


def recentered_p(samples: list[int], observed: int) -> str:
    if len(samples) != B:
        raise ValueError(f"p-value requires B={B}")
    threshold = abs(observed)
    count = sum(1 for draw in samples if abs(draw - observed) >= threshold)
    numer = 1 + count
    denom = B + 1
    return f"{numer}/{denom}"


def holm(p_values: list[tuple[str, int, int]]) -> list[dict[str, str]]:
    """p_values are (label, numer, denom) with denom = B+1."""
    if not p_values:
        return []
    family = len(p_values)
    order = sorted(range(family), key=lambda i: p_values[i][1] / p_values[i][2])
    adjusted: list[tuple[int, int]] = [(0, 1)] * family
    running_num = 0
    running_den = 1
    for rank, index in enumerate(order):
        numer, denom = p_values[index][1], p_values[index][2]
        # (family - rank) * p, then enforce monotonicity in the sorted order.
        scaled_num = (family - rank) * numer
        scaled_den = denom
        if running_num * scaled_den >= scaled_num * running_den:
            scaled_num, scaled_den = running_num, running_den
        if scaled_num >= scaled_den:
            scaled_num, scaled_den = 1, 1
        running_num, running_den = scaled_num, scaled_den
        adjusted[index] = (scaled_num, scaled_den)
    rows = []
    for (label, numer, denom), (adj_n, adj_d) in zip(p_values, adjusted):
        rows.append(
            {
                "label": label,
                "p": f"{numer}/{denom}",
                "holm_p": f"{adj_n}/{adj_d}",
            }
        )
    return rows


def sample_blocks(dates: list[str], block: int, rng: random.Random) -> list[str] | None:
    ordered = list(dates)
    count = len(ordered)
    if count == 0 or block > count or block < 1:
        return None
    n_blocks = math.ceil(count / block)
    starts = [rng.randrange(count - block + 1) for _ in range(n_blocks)]
    chosen: list[str] = []
    for start in starts:
        chosen.extend(ordered[start : start + block])
    return chosen[:count]


def bootstrap_contrast(
    late: dict[str, tuple[int, int]],
    early: dict[str, tuple[int, int]],
    *,
    block: int,
    stream: str,
) -> dict[str, str] | None:
    """Date packs are date -> (total, n), already restricted to the metric."""
    late_dates = sorted(late)
    early_dates = sorted(early)
    if sample_blocks(late_dates, block, random.Random(0)) is None:
        return None
    if sample_blocks(early_dates, block, random.Random(0)) is None:
        return None
    observed = _contrast(late, early, late_dates, early_dates)
    if observed is None:
        return None
    rng = rng_for(stream)
    draws: list[int] = []
    attempts = 0
    while len(draws) < B and attempts < B * 2:
        attempts += 1
        late_pick = sample_blocks(late_dates, block, rng)
        early_pick = sample_blocks(early_dates, block, rng)
        if late_pick is None or early_pick is None:
            return None
        value = _contrast(late, early, late_pick, early_pick)
        if value is None:
            continue
        draws.append(value)
    if len(draws) != B:
        return None
    lo, hi = percentile_interval(draws)
    return {
        "estimate": render_micro(observed),
        "lo": render_micro(lo),
        "hi": render_micro(hi),
        "p": recentered_p(draws, observed),
        "p_numer": str(_p_numer(draws, observed)),
        "p_denom": str(B + 1),
        "n_dates_late": str(len(late_dates)),
        "n_dates_early": str(len(early_dates)),
        "empty_replicates": str(attempts - B),
        "block": str(block),
        "B": str(B),
        "lo_micro": str(lo),
        "hi_micro": str(hi),
        "estimate_micro": str(observed),
    }


def _p_numer(samples: list[int], observed: int) -> int:
    threshold = abs(observed)
    return 1 + sum(1 for draw in samples if abs(draw - observed) >= threshold)


def _contrast(
    late: dict[str, tuple[int, int]],
    early: dict[str, tuple[int, int]],
    late_dates: Iterable[str],
    early_dates: Iterable[str],
) -> int | None:
    late_total, late_n = _accumulate(late, late_dates)
    early_total, early_n = _accumulate(early, early_dates)
    if late_n <= 0 or early_n <= 0:
        return None
    return scaled_mean(late_total, late_n) - scaled_mean(early_total, early_n)


def _accumulate(packs: dict[str, tuple[int, int]], dates: Iterable[str]) -> tuple[int, int]:
    total = 0
    count = 0
    for date in dates:
        part, n = packs[date]
        total += part
        count += n
    return total, count


def bootstrap_mean(
    packs: dict[str, tuple[int, int]],
    *,
    block: int,
    stream: str,
) -> dict[str, str] | None:
    dates = sorted(packs)
    if sample_blocks(dates, block, random.Random(0)) is None:
        return None
    observed_total, observed_n = _accumulate(packs, dates)
    if observed_n <= 0:
        return None
    observed = scaled_mean(observed_total, observed_n)
    rng = rng_for(stream)
    draws: list[int] = []
    attempts = 0
    while len(draws) < B and attempts < B * 2:
        attempts += 1
        picked = sample_blocks(dates, block, rng)
        if picked is None:
            return None
        total, count = _accumulate(packs, picked)
        if count <= 0:
            continue
        draws.append(scaled_mean(total, count))
    if len(draws) != B:
        return None
    lo, hi = percentile_interval(draws)
    return {
        "estimate": render_micro(observed),
        "lo": render_micro(lo),
        "hi": render_micro(hi),
        "n_dates": str(len(dates)),
        "n": str(observed_n),
        "empty_replicates": str(attempts - B),
    }


def entry_band(cents: int | None, *, nominal: bool) -> str:
    if nominal:
        return "80"
    if cents is None:
        return "UNAVAILABLE"
    if cents < 80:
        return "BELOW_80"
    if cents == 80:
        return "80"
    if cents <= 83:
        return "81-83"
    return "84+"


def explicit_payoff(*, t40: bool, yes: bool | None) -> int | None:
    if t40:
        return -40
    if yes is None:
        return None
    return 20 if yes else -80


def hold_payoff(yes: bool | None) -> int | None:
    if yes is None:
        return None
    return 20 if yes else -80


def shorthand_cents(no_t40: int, n: int, loss_no: int) -> str:
    if n <= 0:
        return "UNAVAILABLE"
    if loss_no != 0:
        return "NOT_APPLICABLE"
    # 60*P(no T40) - 40, in microcents.
    value = scaled_mean(60 * no_t40, n) - 40 * SCALE
    return render_micro(value)


def _div_round(numer: int, denom: int) -> int:
    if denom <= 0:
        raise ValueError("division requires denom > 0")
    if numer >= 0:
        return (numer + denom // 2) // denom
    return -(((-numer) + denom // 2) // denom)


def _share(part: int, whole: int) -> str:
    if whole <= 0:
        return "UNAVAILABLE"
    return render_micro(scaled_mean(part, whole))


def retained_support(
    late: dict[tuple[str, str], tuple[int, int]],
    early: dict[tuple[str, str], tuple[int, int]],
) -> tuple[list[tuple[str, str]], list[dict[str, str]], dict[str, str]]:
    """Drop empty strata, then keep both means on the late group's renormalized weights."""
    strata: list[dict[str, str]] = []
    support: list[tuple[str, str]] = []
    late_all = sum(count for _total, count in late.values())
    early_all = sum(count for _total, count in early.values())
    late_retained = 0
    early_retained = 0
    late_unsupported = 0
    early_unsupported = 0
    for key in sorted(set(late) | set(early)):
        late_sum, late_n = late.get(key, (0, 0))
        early_sum, early_n = early.get(key, (0, 0))
        if late_n <= 0 or early_n <= 0:
            status = "UNSUPPORTED_STRATUM"
            late_unsupported += late_n
            early_unsupported += early_n
        elif late_n < 5 or early_n < 5:
            status = "SPARSE_STRATUM"
            support.append(key)
            late_retained += late_n
            early_retained += early_n
        else:
            status = "COMMON_SUPPORT"
            support.append(key)
            late_retained += late_n
            early_retained += early_n
        strata.append(
            {
                "band": key[0],
                "period": key[1],
                "late_n": str(late_n),
                "early_n": str(early_n),
                "late_sum": str(late_sum),
                "early_sum": str(early_sum),
                "status": status,
            }
        )
    shares = {
        "late_retained_share": _share(late_retained, late_all),
        "early_retained_share": _share(early_retained, early_all),
        "late_retained_rows": str(late_retained),
        "early_retained_rows": str(early_retained),
        "late_rows": str(late_all),
        "early_rows": str(early_all),
        "unsupported_late_rows": str(late_unsupported),
        "unsupported_early_rows": str(early_unsupported),
    }
    return support, strata, shares


def contrast_on_support(
    late: dict[tuple[str, str], tuple[int, int]],
    early: dict[tuple[str, str], tuple[int, int]],
    support: list[tuple[str, str]],
) -> tuple[int, int, int] | None:
    """Both means use renormalized late weights. None when a retained stratum is empty."""
    if not support:
        return None
    weighted_early = 0
    late_total = 0
    late_n = 0
    for key in support:
        late_sum, late_count = late.get(key, (0, 0))
        early_sum, early_count = early.get(key, (0, 0))
        if late_count <= 0 or early_count <= 0:
            return None
        late_total += late_sum
        late_n += late_count
        weighted_early += late_count * scaled_mean(early_sum, early_count)
    late_mean = scaled_mean(late_total, late_n)
    early_mean = _div_round(weighted_early, late_n)
    return late_mean - early_mean, late_mean, early_mean


def bootstrap_standardized(
    late: dict[str, dict[tuple[str, str], tuple[int, int]]],
    early: dict[str, dict[tuple[str, str], tuple[int, int]]],
    *,
    stream: str,
) -> dict[str, object] | None:
    late_dates = sorted(late)
    early_dates = sorted(early)
    if sample_blocks(late_dates, 1, random.Random(0)) is None:
        return None
    if sample_blocks(early_dates, 1, random.Random(0)) is None:
        return None
    observed_late = _merge_cells(late, late_dates)
    observed_early = _merge_cells(early, early_dates)
    support, strata, shares = retained_support(observed_late, observed_early)
    observed = contrast_on_support(observed_late, observed_early, support)
    if observed is None:
        return {
            "estimate": "UNAVAILABLE",
            "lo": "UNAVAILABLE",
            "hi": "UNAVAILABLE",
            "p": "UNAVAILABLE",
            "classification": "exploratory",
            "invalid_replicates": "0",
            "strata": strata,
            **shares,
        }
    estimate, late_mean, early_mean = observed
    rng = rng_for(stream)
    draws: list[int] = []
    invalid = 0
    attempts = 0
    attempt_cap = B * 5
    while len(draws) < B and attempts < attempt_cap:
        attempts += 1
        late_pick = sample_blocks(late_dates, 1, rng)
        early_pick = sample_blocks(early_dates, 1, rng)
        if late_pick is None or early_pick is None:
            return None
        value = contrast_on_support(_merge_cells(late, late_pick), _merge_cells(early, early_pick), support)
        if value is None:
            invalid += 1
            continue
        draws.append(value[0])
    payload: dict[str, object] = {
        "estimate": render_micro(estimate),
        "late_mean_on_support": render_micro(late_mean),
        "early_mean_on_support": render_micro(early_mean),
        "classification": "exploratory",
        "invalid_replicates": str(invalid),
        "attempts": str(attempts),
        "n_dates_late": str(len(late_dates)),
        "n_dates_early": str(len(early_dates)),
        "strata": strata,
        "estimate_micro": str(estimate),
        **shares,
    }
    if len(draws) != B:
        payload.update({"lo": "UNAVAILABLE", "hi": "UNAVAILABLE", "p": "UNAVAILABLE"})
        return payload
    lo, hi = percentile_interval(draws)
    payload.update(
        {
            "lo": render_micro(lo),
            "hi": render_micro(hi),
            "p": recentered_p(draws, estimate),
            "lo_micro": str(lo),
            "hi_micro": str(hi),
        }
    )
    return payload


def _merge_cells(
    packs: dict[str, dict[tuple[str, str], tuple[int, int]]],
    dates: Iterable[str],
) -> dict[tuple[str, str], tuple[int, int]]:
    merged: dict[tuple[str, str], list[int]] = {}
    for date in dates:
        for key, (total, count) in packs.get(date, {}).items():
            slot = merged.setdefault(key, [0, 0])
            slot[0] += total
            slot[1] += count
    return {key: (total, count) for key, (total, count) in merged.items()}
