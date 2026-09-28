"""Synthetic V4B fixtures. Not a public API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from roller.config import RollerConfig
from roller.fundamental.conditioning import condition_state
from roller.state.observation_id import make_observation_id, parse_observation_id
from roller.timeutil import parse_utc_required, to_iso
from roller.v4b.types import CandleView, FundamentalView, SharedXt
from tests.helpers_v4a import fake_observation


def candle(
    ts: str,
    close: int,
    *,
    open_: int | None = None,
    high: int | None = None,
    low: int | None = None,
) -> CandleView:
    dt = parse_utc_required(ts)
    o = close if open_ is None else open_
    h = close if high is None else high
    lo = close if low is None else low
    return CandleView(
        available_at=ts,
        available_at_dt=dt,
        yes_bid_close=close,
        yes_bid_open=o,
        yes_bid_high=h,
        yes_bid_low=lo,
    )


def fund(
    wins: int,
    n: int,
    cutoff: str,
    *,
    oid: str | None = None,
    status: str = "IMPLEMENTED",
    gid: str = "NBA_CUR",
) -> FundamentalView:
    dt = parse_utc_required(cutoff)
    observation_id = oid or make_observation_id(gid, dt, "2.0.0")
    return FundamentalView(
        observation_id=observation_id,
        cutoff=cutoff,
        available_at=cutoff,
        status=status,
        wins=wins,
        n=n,
        condition_id="C_TEST",
    )


def make_xt(
    *,
    cutoff: str = "2025-12-20T20:15:00Z",
    gid: str = "NBA_CUR",
    current: CandleView | None = None,
    previous: CandleView | None = None,
    previous2: CandleView | None = None,
    f_t: FundamentalView | None = None,
    f_prev: FundamentalView | None = None,
    f_prev2: FundamentalView | None = None,
    s_t: int | None = -3,
    s_prev: int | None = -5,
    period_t: int | None = 2,
    period_prev: int | None = 2,
    elapsed_t: int | None = 780,
    elapsed_prev: int | None = 720,
    expected: int = 60,
    vol_window: int = 10,
    closes: list[tuple[str, int]] | None = None,
) -> SharedXt:
    cut = parse_utc_required(cutoff)
    oid = make_observation_id(gid, cut, "2.0.0")
    if current is None:
        current = candle("2025-12-20T20:14:00Z", 7500, open_=7400, high=7600, low=7300)
    if previous is None:
        previous = candle("2025-12-20T20:13:00Z", 7400, open_=7350, high=7450, low=7300)
    sec = None
    sec_prev = None
    if current is not None and previous is not None:
        sec = int((current.available_at_dt - previous.available_at_dt).total_seconds())
    if previous is not None and previous2 is not None:
        sec_prev = int((previous.available_at_dt - previous2.available_at_dt).total_seconds())
    vis = []
    for c in (previous2, previous, current):
        if c is not None and c.yes_bid_close is not None:
            vis.append((c.available_at, c.yes_bid_close))
    return SharedXt(
        observation_id=oid,
        internal_game_id=gid,
        sport="NBA",
        season="2025-2026",
        cutoff=cut,
        cutoff_iso=to_iso(cut),
        expected_interval_seconds=expected,
        vol_window_closes=vol_window,
        current=current,
        previous=previous,
        previous2=previous2,
        interval_seconds=sec,
        interval_seconds_prev=sec_prev,
        interval_ok=sec == expected,
        interval_prev_ok=sec_prev == expected,
        f_t=f_t if f_t is not None else fund(3, 4, cutoff, gid=gid),
        f_prev=f_prev if f_prev is not None else fund(2, 4, "2025-12-20T20:13:00Z", gid=gid),
        f_prev2=f_prev2,
        s_t=s_t,
        s_prev=s_prev,
        period_t=period_t,
        period_prev=period_prev,
        elapsed_t=elapsed_t,
        elapsed_prev=elapsed_prev,
        visible_closes=closes if closes is not None else vis,
        condition_id="C_TEST",
        state_available_at="2025-12-20T20:14:00Z",
    )


def recording_fundamental_fn(table: dict[str, dict[str, Any]] | None = None):
    """Map compact observation time → fundamental row. Records every observation_id."""
    calls: list[str] = []
    table = table or {}

    def _fn(observation_id: str) -> dict[str, Any]:
        calls.append(observation_id)
        gid, ts, _ver = parse_observation_id(observation_id)
        key = to_iso(ts)
        if key in table:
            row = dict(table[key])
            row.setdefault("observation_id", observation_id)
            return row
        return {
            "observation_id": observation_id,
            "status": "IMPLEMENTED",
            "value": {"numerator": 1, "denominator": 4},
            "probability_wins": 1,
            "probability_n": 4,
            "available_at": key,
            "information_cutoff": key,
            "observation_cutoff": key,
        }

    _fn.calls = calls  # type: ignore[attr-defined]
    return _fn


def condition_id_for(cfg: RollerConfig, period: int, elapsed: int, margin: int) -> str:
    return condition_state(
        cfg,
        {"period": period, "elapsed_game_seconds": elapsed, "score_differential_home": margin},
    )["condition_id"]


def corpus_row(
    *,
    name: str,
    gid: str,
    available_at: str,
    numerator: int,
    denominator: int,
    condition_id: str,
    units: str = "e4",
) -> dict[str, Any]:
    return {
        "measurement_name": name,
        "internal_game_id": gid,
        "measurement_available_at": available_at,
        "value": {"numerator": numerator, "denominator": denominator, "units": units},
        "status": "valid",
        "condition_id": condition_id,
        "season": "2025-2026",
        "game_date": available_at[:10],
    }


# re-export for observation assembly tests
fake_observation = fake_observation
