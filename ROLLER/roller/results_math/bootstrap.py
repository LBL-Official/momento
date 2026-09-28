"""Deterministic percentile bootstrap. Observation or game-cluster. Not a forecast."""

from __future__ import annotations

import random
from typing import Any, Callable

from roller.results_math.dependence import cluster_readiness
from roller.results_math.means import mean, median, sample_std
from roller.results_math.models import DERIVED, UNAVAILABLE
from roller.results_math.path_metrics import downside_deviation, observed_path_sharpe, profit_factor
from roller.results_math.versions import BOOTSTRAP_ITERATIONS, BOOTSTRAP_SEED, CONFIDENCE_LEVEL


def _max_dd_cents(pnls: list[float]) -> float:
    peak = 0.0
    equity = 0.0
    max_dd = 0.0
    for pnl in pnls:
        equity += pnl
        if equity > peak:
            peak = equity
        dd = peak - equity
        if dd > max_dd:
            max_dd = dd
    return max_dd


def _min_cumulative(pnls: list[float]) -> float:
    equity = 0.0
    floor = 0.0
    for pnl in pnls:
        equity += pnl
        if equity < floor:
            floor = equity
    return floor


def _longest_loss_streak(pnls: list[float]) -> int:
    longest = cur = 0
    for pnl in pnls:
        if pnl < 0:
            cur += 1
            longest = max(longest, cur)
        else:
            cur = 0
    return longest


def _percentile(xs: list[float], p: float) -> float | None:
    if not xs:
        return None
    s = sorted(xs)
    idx = p * (len(s) - 1)
    lo = int(idx)
    hi = min(lo + 1, len(s) - 1)
    w = idx - lo
    return s[lo] * (1.0 - w) + s[hi] * w


def resample_observation(
    xs: list[float],
    *,
    iterations: int = BOOTSTRAP_ITERATIONS,
    seed: int = BOOTSTRAP_SEED,
    stat: Callable[[list[int]], float | None],
) -> list[float]:
    rng = random.Random(seed)
    n = len(xs)
    out: list[float] = []
    if n == 0:
        return out
    for _ in range(iterations):
        sample = [xs[rng.randrange(n)] for _ in range(n)]
        v = stat(sample)
        if v is not None:
            out.append(v)
    return out


def resample_game_cluster(
    groups: list[list[float]],
    *,
    iterations: int = BOOTSTRAP_ITERATIONS,
    seed: int = BOOTSTRAP_SEED,
    stat: Callable[[list[int]], float | None],
) -> list[float]:
    rng = random.Random(seed)
    g = len(groups)
    out: list[float] = []
    if g == 0:
        return out
    for _ in range(iterations):
        sample: list[int] = []
        for _i in range(g):
            sample.extend(groups[rng.randrange(g)])
        v = stat(sample)
        if v is not None:
            out.append(v)
    return out


def _ci(values: list[float], level: float = CONFIDENCE_LEVEL) -> dict[str, Any] | None:
    if not values:
        return None
    alpha = 1.0 - level
    return {
        "lower": _percentile(values, alpha / 2.0),
        "upper": _percentile(values, 1.0 - alpha / 2.0),
        "median": median(values),
        "n_resamples": len(values),
    }


def _joint_stats(sample: list[float]) -> tuple[float | None, float | None, float | None]:
    return mean(sample), median(sample), observed_path_sharpe(sample)


def _unit_cluster(
    groups: list[list[float]] | None,
    n_obs: int,
    *,
    unit: str,
    iterations: int,
    seed: int,
    observation_mean: dict[str, Any] | None = None,
    observation_sharpe: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ready = cluster_readiness(len(groups or []), n_obs, unit=unit)
    sizes = [len(g) for g in (groups or [])]
    if sizes:
        ready["n_clusters"] = len(sizes)
        ready["mean_observations_per_cluster"] = sum(sizes) / len(sizes)
        ready["max_observations_per_cluster"] = max(sizes)
        ready["min_observations_per_cluster"] = min(sizes)
    if ready["status"] == "COINCIDENT":
        ready["mean"] = observation_mean
        ready["sharpe"] = observation_sharpe
        return ready
    if ready["status"] != DERIVED or not groups:
        return ready
    c_means: list[float] = []
    c_sharpes: list[float] = []
    g = len(groups)
    crng = random.Random(seed)
    for _ in range(iterations):
        sample: list[float] = []
        for _i in range(g):
            sample.extend(groups[crng.randrange(g)])
        m, _md, sh = _joint_stats(sample)
        if m is not None:
            c_means.append(m)
        if sh is not None:
            c_sharpes.append(sh)
    ready["mean"] = _ci(c_means)
    ready["sharpe"] = _ci(c_sharpes)
    return ready


def bootstrap_returns(
    xs: list[float],
    *,
    groups: list[list[float]] | None = None,
    date_groups: list[list[float]] | None = None,
    iterations: int = BOOTSTRAP_ITERATIONS,
    seed: int = BOOTSTRAP_SEED,
) -> dict[str, Any]:
    if len(xs) < 2:
        return {
            "status": UNAVAILABLE,
            "reason": "Need N >= 2 observed returns.",
            "iterations": iterations,
            "seed": seed,
        }

    rng = random.Random(seed)
    n = len(xs)
    means: list[float] = []
    meds: list[float] = []
    sharpes: list[float] = []
    stds: list[float] = []
    downsides: list[float] = []
    pfs: list[float] = []
    endings: list[float] = []
    drawdowns: list[float] = []
    min_cums: list[float] = []
    loss_streaks: list[float] = []
    for _ in range(iterations):
        sample = [xs[rng.randrange(n)] for _ in range(n)]
        m, md, sh = _joint_stats(sample)
        if m is not None:
            means.append(m)
        if md is not None:
            meds.append(md)
        if sh is not None:
            sharpes.append(sh)
        s = sample_std(sample)
        if s is not None:
            stds.append(s)
        d = downside_deviation(sample)
        if d is not None:
            downsides.append(d)
        pf = profit_factor(sample)
        if pf.get("status") == DERIVED and pf.get("value") is not None:
            pfs.append(float(pf["value"]))
        endings.append(float(sum(sample)))
        drawdowns.append(float(_max_dd_cents(sample)))
        min_cums.append(_min_cumulative(sample))
        loss_streaks.append(float(_longest_loss_streak(sample)))
    n_pos = sum(1 for v in means if v > 0)
    share_pos = (n_pos / len(means)) if means else None
    mean_ci = _ci(means)
    sharpe_ci = _ci(sharpes)
    game_cluster = _unit_cluster(
        groups,
        n,
        unit="game",
        iterations=iterations,
        seed=seed + 3,
        observation_mean=mean_ci,
        observation_sharpe=sharpe_ci,
    )
    date_cluster = _unit_cluster(
        date_groups,
        n,
        unit="date",
        iterations=iterations,
        seed=seed + 5,
        observation_mean=mean_ci,
        observation_sharpe=sharpe_ci,
    )
    return {
        "status": DERIVED,
        "label": "HISTORICAL-DISTRIBUTION RESAMPLE · PERCENTILE BOOTSTRAP · NOT A FORECAST",
        "method": "percentile",
        "iterations": iterations,
        "seed": seed,
        "resampling_unit": "observation",
        "confidence_level": CONFIDENCE_LEVEL,
        "mean": mean_ci,
        "median": _ci(meds),
        "std": _ci(stds),
        "downside_deviation": _ci(downsides),
        "profit_factor": _ci(pfs),
        "sharpe": sharpe_ci,
        "ending_pnl_cents": _ci(endings),
        "min_cumulative_cents": _ci(min_cums),
        "longest_loss_streak": _ci(loss_streaks),
        "max_drawdown_cents": {
            **(_ci(drawdowns) or {}),
            "p95": _percentile(drawdowns, 0.95) if drawdowns else None,
        },
        "share_means_positive": share_pos,
        "share_means_positive_label": "DERIVED RESAMPLE FRACTION · NOT P(EV > 0) · NOT A POSTERIOR",
        "game_cluster": game_cluster,
        "date_cluster": date_cluster,
        "cluster": game_cluster if game_cluster.get("status") == DERIVED else None,
        "caveat": "Does not solve dependence. Game- and date-cluster intervals are separate from observation bootstrap. Sequence resample is not a forecast.",
    }
