"""Day-cluster inference, account Sharpe, and the one-minute mark."""

from __future__ import annotations

import math
import random
from collections import defaultdict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from first78.stats import max_drawdown, sharpe

LA = ZoneInfo("America/Los_Angeles")


def per_contract(trades: list[dict]) -> float | None:
    vals = []
    for trade in trades:
        contracts = int(trade["contracts"])
        if contracts <= 0:
            continue
        vals.append(int(trade["net_pnl_cents"]) / contracts)
    if not vals:
        return None
    return sum(vals) / len(vals)


def studentized_cluster_p(trades: list[dict], *, draws: int, seed: int, min_days: int) -> dict:
    by_day: dict[str, list[float]] = defaultdict(list)
    for trade in trades:
        contracts = int(trade["contracts"])
        if contracts <= 0:
            continue
        by_day[str(trade["local_day"])].append(int(trade["net_pnl_cents"]) / contracts)
    days = sorted(by_day)
    if len(days) < min_days:
        return {
            "status": "P_VALUE_NOT_ESTIMABLE",
            "reason": "FEWER_THAN_10_INDEPENDENT_DAYS",
            "n_days": len(days),
            "n_trades": len(trades),
        }
    observed_vals = [v for day in days for v in by_day[day]]
    observed = sum(observed_vals) / len(observed_vals)

    def stat(sample_days: list[str]) -> tuple[float, float]:
        vals = [v for day in sample_days for v in by_day[day]]
        mean = sum(vals) / len(vals)
        # cluster SE of the mean, days as the unit
        day_means = []
        for day in sample_days:
            xs = by_day[day]
            day_means.append(sum(xs) / len(xs))
        if len(day_means) < 2:
            return mean, 0.0
        m = sum(day_means) / len(day_means)
        var = sum((x - m) ** 2 for x in day_means) / (len(day_means) - 1)
        se = math.sqrt(var / len(day_means))
        return mean, se

    t_obs_mean, se_obs = stat(days)
    if se_obs == 0:
        return {"status": "P_VALUE_NOT_ESTIMABLE", "reason": "ZERO_CLUSTER_SE", "n_days": len(days), "observed": observed}
    t_obs = t_obs_mean / se_obs
    rng = random.Random(seed)
    extreme = 0
    boots = []
    for _ in range(draws):
        picked = [days[rng.randrange(len(days))] for _ in days]
        mean, se = stat(picked)
        if se == 0:
            continue
        t_star = (mean - observed) / se
        boots.append(t_star)
        if t_star >= t_obs:
            extreme += 1
    if not boots:
        return {"status": "P_VALUE_NOT_ESTIMABLE", "reason": "NO_FINITE_BOOTSTRAP_SE", "n_days": len(days)}
    return {
        "status": "ESTIMATED",
        "n_days": len(days),
        "n_trades": len(trades),
        "observed_mean_cents_per_contract": observed,
        "studentized_observed": t_obs,
        "draws_used": len(boots),
        "one_sided_p": (1 + extreme) / (len(boots) + 1),
        "note": "Centered studentized cluster bootstrap. Not the share of uncentered means <= 0.",
    }


def holm(items: list[tuple[str, float]]) -> list[dict]:
    ordered = sorted(items, key=lambda item: item[1])
    m = len(ordered)
    running = 0.0
    rows = []
    for i, (name, pval) in enumerate(ordered):
        running = max(running, min(1.0, (m - i) * pval))
        rows.append({"endpoint": name, "raw_p": pval, "holm_p": running})
    return rows


def account_sharpe(equity_by_day: list[float]) -> dict:
    if len(equity_by_day) < 2:
        return {"status": "N_LT_2", "sharpe_unannualized": None}
    returns = []
    for prev, cur in zip(equity_by_day, equity_by_day[1:]):
        if prev == 0:
            return {"status": "ZERO_PRIOR_EQUITY", "sharpe_unannualized": None}
        returns.append(cur / prev - 1)
    out = sharpe(returns, 365)
    out["zero_activity_days_retained"] = True
    out["definition"] = "E_day_end / E_previous_day_end - 1"
    out["annualization"] = "sqrt(365) is descriptive on a short window"
    return out


def minute_marks(
    trades: list[dict],
    events: list[dict],
    paths: dict[str, list[tuple[int, int]]],
    start_ts: int,
    end_ts: int,
) -> list[dict]:
    """One row per minute. Missing bids stay missing and are not filled with zero."""
    if end_ts < start_ts:
        return []
    event_rows = sorted(events, key=lambda e: int(e["ts"]))
    cursor = 0
    cash = int(event_rows[0]["cash_cents"]) if event_rows else 2_000_000
    receivable = int(event_rows[0]["receivable_cents"]) if event_rows else 0
    # before the first event the account is the starting cash; events begin at the first entry
    if event_rows:
        cash = 2_000_000
        receivable = 0
    rows = []
    ts = int(start_ts)
    while ts <= int(end_ts):
        while cursor < len(event_rows) and int(event_rows[cursor]["ts"]) <= ts:
            cash = int(event_rows[cursor]["cash_cents"])
            receivable = int(event_rows[cursor]["receivable_cents"])
            cursor += 1
        gross = 0
        missing = False
        oldest = 0
        for trade in trades:
            entry = int(trade["entry_ts"])
            exit_ts = int(trade["exit_ts"])
            if entry > ts or exit_ts <= ts:
                continue
            series = paths.get(trade["contract_id"]) or []
            bid = None
            bid_ts = None
            for stamp, px in series:
                if stamp <= ts:
                    bid = px
                    bid_ts = stamp
                else:
                    break
            if bid is None or bid_ts is None:
                missing = True
                break
            oldest = max(oldest, ts - bid_ts)
            gross += int(trade["contracts"]) * int(bid)
        realized = None
        # realized accounting at this minute is the last event equity, carried forward
        rows.append(
            {
                "ts": ts,
                "cash_cents": cash,
                "receivable_cents": receivable,
                "mark_status": "MISSING" if missing else "BID_CLOSE",
                "mark_age_seconds": None if missing else oldest,
                "bid_marked_gross_equity_cents": None if missing else cash + receivable + gross,
            }
        )
        ts += 60
    return rows


def marked_drawdown(rows: list[dict]) -> dict:
    series = []
    missing = 0
    for row in rows:
        if row["bid_marked_gross_equity_cents"] is None:
            missing += 1
            continue
        series.append(int(row["bid_marked_gross_equity_cents"]))
    out = max_drawdown(series)
    out["minutes_with_mark"] = len(series)
    out["minutes_missing"] = missing
    out["grid"] = "ONE_MINUTE"
    return out


def day_ends(start_ts: int, end_ts: int) -> list[int]:
    start = datetime.fromtimestamp(int(start_ts), tz=LA)
    end = datetime.fromtimestamp(int(end_ts), tz=LA)
    day = start.date()
    last = end.date()
    stamps = []
    while day <= last:
        nxt = datetime(day.year, day.month, day.day, tzinfo=LA) + timedelta(days=1)
        stamps.append(int(nxt.timestamp()) - 1)
        day = nxt.date()
    return stamps
