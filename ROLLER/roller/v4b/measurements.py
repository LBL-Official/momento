"""Observed V4B measurements from shared X_t. Do not rediscover candles or F."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from fractions import Fraction
from typing import Any

import pandas as pd

from roller.config import RollerConfig
from roller.fundamental.conditioning import condition_observation, observation_state_fields
from dataclasses import replace

from roller.timeutil import parse_utc, resolve_cutoff, to_iso
from roller.v4b.candles import interval_matches, interval_seconds, visible_home_candles
from roller.v4b.definitions import expected_interval_seconds, realized_vol_window_closes
from roller.v4b.fundamentals import fundamental_at_cutoff, fundamental_at_observation
from roller.v4b.provenance import candle_pair_prov, fundamental_pair_prov, latest_iso, ohlc_prov
from roller.v4b.types import (
    ExactRational,
    MeasurementPoint,
    SharedXt,
    as_int,
)

PATH_STATUS = "UNORDERED_SUMMARY"
RECONCILE_NAMES = ("market_delta_1m", "fundamental_delta", "response_delta", "basis_delta")


def _point(
    name: str,
    value: ExactRational | None,
    status: str,
    available_at: str | None,
    provenance: dict[str, Any],
    *,
    path: str | None = None,
    extra: dict[str, Any] | None = None,
) -> MeasurementPoint:
    return MeasurementPoint(
        name=name,
        value=value,
        status=status,
        measurement_available_at=available_at,
        provenance=provenance,
        path_information_status=path,
        extra=extra or {},
    )


def _null(
    name: str,
    status: str,
    available_at: str | None,
    provenance: dict[str, Any],
    *,
    path: str | None = None,
    extra: dict[str, Any] | None = None,
) -> MeasurementPoint:
    return _point(name, None, status, available_at, provenance, path=path, extra=extra)


def _same_period(a: Any, b: Any) -> bool:
    ia, ib = as_int(a), as_int(b)
    if ia is not None and ib is not None:
        return ia == ib
    if a in (None, "") or b in (None, ""):
        return False
    return str(a) == str(b)


def _state_from_obs(observation: dict[str, Any] | None) -> dict[str, Any]:
    if not observation:
        return {
            "period": None,
            "elapsed_game_seconds": None,
            "score_differential_home": None,
            "home_score": None,
            "away_score": None,
            "latest_available_at": None,
        }
    fields = observation_state_fields(observation)
    gs = (observation.get("GAME_STATE") or {}).get("data") or {}
    s = as_int(fields.get("score_differential_home"))
    if s is None:
        home = as_int(fields.get("home_score"))
        away = as_int(fields.get("away_score"))
        if home is not None and away is not None:
            s = home - away
    fields["score_differential_home"] = s
    fields["elapsed_game_seconds"] = as_int(fields.get("elapsed_game_seconds"))
    fields["latest_available_at"] = gs.get("latest_available_at")
    return fields


def assemble_shared_xt(
    cfg: RollerConfig,
    *,
    observation: dict[str, Any],
    candles: pd.DataFrame,
    fundamental_fn: Callable[[str], dict[str, Any]],
    previous_observation: dict[str, Any] | None = None,
    previous2_observation: dict[str, Any] | None = None,
    load_observation: Callable[[str, datetime], dict[str, Any]] | None = None,
) -> SharedXt:
    """One shared X_t. Measurements must not rebuild candles or F."""
    cutoff = parse_utc(observation.get("observation_time")) or resolve_cutoff(observation["observation_time"])
    views = visible_home_candles(candles, cutoff)
    current = views[-1] if views else None
    previous = views[-2] if len(views) >= 2 else None
    previous2 = views[-3] if len(views) >= 3 else None
    expected = expected_interval_seconds(cfg)
    sec = interval_seconds(current, previous)
    sec_prev = interval_seconds(previous, previous2)
    gid = str(observation.get("internal_game_id") or "")
    oid = str(observation.get("observation_id") or "")
    f_t = fundamental_at_observation(fundamental_fn, oid)
    f_prev = None
    f_prev2 = None
    if previous is not None:
        f_prev = fundamental_at_cutoff(
            cfg, internal_game_id=gid, cutoff=previous.available_at_dt, fundamental_fn=fundamental_fn
        )
    if previous2 is not None:
        f_prev2 = fundamental_at_cutoff(
            cfg, internal_game_id=gid, cutoff=previous2.available_at_dt, fundamental_fn=fundamental_fn
        )

    if previous_observation is None and previous is not None and load_observation is not None:
        previous_observation = load_observation(gid, previous.available_at_dt)
    if previous2_observation is None and previous2 is not None and load_observation is not None:
        previous2_observation = load_observation(gid, previous2.available_at_dt)

    now_state = _state_from_obs(observation)
    prev_state = _state_from_obs(previous_observation)
    cond = condition_observation(cfg, observation)
    closes = [(c.available_at, c.yes_bid_close) for c in views if c.yes_bid_close is not None]
    return SharedXt(
        observation_id=oid,
        internal_game_id=gid,
        sport=str(observation.get("sport") or ""),
        season=str(observation.get("season") or ""),
        cutoff=cutoff,
        cutoff_iso=to_iso(cutoff),
        expected_interval_seconds=expected,
        vol_window_closes=realized_vol_window_closes(cfg),
        current=current,
        previous=previous,
        previous2=previous2,
        interval_seconds=sec,
        interval_seconds_prev=sec_prev,
        interval_ok=interval_matches(sec, expected),
        interval_prev_ok=interval_matches(sec_prev, expected),
        f_t=f_t,
        f_prev=f_prev,
        f_prev2=f_prev2,
        s_t=now_state.get("score_differential_home"),
        s_prev=prev_state.get("score_differential_home"),
        period_t=now_state.get("period"),
        period_prev=prev_state.get("period"),
        elapsed_t=now_state.get("elapsed_game_seconds"),
        elapsed_prev=prev_state.get("elapsed_game_seconds"),
        visible_closes=closes,
        condition_id=cond.get("condition_id"),
        state_available_at=now_state.get("latest_available_at"),
    )


def _market_delta(xt: SharedXt) -> MeasurementPoint:
    prov = candle_pair_prov(xt)
    if xt.current is None:
        return _null("market_delta_1m", "MISSING_K", None, prov, path=PATH_STATUS)
    if xt.previous is None:
        return _null("market_delta_1m", "NO_PRIOR_CANDLE", xt.current.available_at, prov, path=PATH_STATUS)
    if xt.current.yes_bid_close is None or xt.previous.yes_bid_close is None:
        return _null("market_delta_1m", "MISSING_K", xt.current.available_at, prov, path=PATH_STATUS)
    if not xt.interval_ok:
        reason = "TIME_GAP" if xt.interval_seconds is not None else "PERIOD_OR_SEQUENCE_GAP"
        return _null("market_delta_1m", reason, xt.current.available_at, prov, path=PATH_STATUS)
    delta = xt.current.yes_bid_close - xt.previous.yes_bid_close
    return _point(
        "market_delta_1m",
        ExactRational.from_int(delta),
        "valid",
        xt.current.available_at,
        prov,
        path=PATH_STATUS,
    )


def _fundamental_delta(xt: SharedXt, *, name: str = "fundamental_delta") -> MeasurementPoint:
    prov = fundamental_pair_prov(xt.f_t, xt.f_prev)
    maa = None if xt.f_t is None else xt.f_t.available_at
    if xt.f_t is None or not xt.f_t.ok:
        return _null(name, "MISSING_F", maa, prov)
    if xt.f_prev is None or not xt.f_prev.ok:
        return _null(name, "NO_PRIOR_F", maa, prov)
    cur = xt.f_t.f_e4()
    prev = xt.f_prev.f_e4()
    if cur is None or prev is None:
        return _null(name, "MISSING_F", maa, prov)
    return _point(name, ExactRational.from_fraction(cur - prev), "valid", maa, prov)


def _prior_fundamental_delta(xt: SharedXt) -> MeasurementPoint:
    """ΔF_{t-1} = F_{t-1} - F_{t-2} for discrete_gamma only."""
    dummy = replace(xt, f_t=xt.f_prev, f_prev=xt.f_prev2)
    return _fundamental_delta(dummy, name="fundamental_delta_prev")


def _response_delta(xt: SharedXt, market: MeasurementPoint, fund: MeasurementPoint) -> MeasurementPoint:
    prov = {**market.provenance, **fund.provenance}
    maa = latest_iso(market.measurement_available_at, fund.measurement_available_at)
    if market.value is None:
        return _null("response_delta", market.status if market.status != "valid" else "MISSING_K", maa, prov)
    if fund.value is None:
        return _null("response_delta", fund.status if fund.status != "valid" else "MISSING_F", maa, prov)
    return _point("response_delta", market.value - fund.value, "valid", maa, prov)


def _basis(xt: SharedXt, *, current: bool) -> MeasurementPoint:
    name = "market_fundamental_basis" if current else "market_fundamental_basis_prev"
    candle = xt.current if current else xt.previous
    fund = xt.f_t if current else xt.f_prev
    k = None if candle is None else candle.yes_bid_close
    prov = {
        **ohlc_prov(candle),
        **fundamental_pair_prov(fund, None),
    }
    maa = latest_iso(
        None if candle is None else candle.available_at,
        None if fund is None else fund.available_at,
    )
    if k is None:
        return _null(name, "MISSING_K", maa, prov)
    if fund is None or not fund.ok:
        return _null(name, "MISSING_F", maa, prov)
    b = fund.basis(k)
    if b is None:
        return _null(name, "MISSING_F", maa, prov)
    return _point(name, ExactRational.from_fraction(b), "valid", maa, prov)


def _basis_delta(xt: SharedXt, b_t: MeasurementPoint, b_prev: MeasurementPoint) -> MeasurementPoint:
    prov = {**b_t.provenance, **b_prev.provenance, **candle_pair_prov(xt)}
    maa = latest_iso(b_t.measurement_available_at, b_prev.measurement_available_at)
    if b_t.value is None:
        return _null("basis_delta", b_t.status if b_t.status != "valid" else "MISSING_F", maa, prov)
    if b_prev.value is None:
        return _null("basis_delta", b_prev.status if b_prev.status != "valid" else "MISSING_F", maa, prov)
    return _point("basis_delta", b_t.value - b_prev.value, "valid", maa, prov)


def _score_delta(xt: SharedXt, fund: MeasurementPoint) -> MeasurementPoint:
    prov = {
        **fund.provenance,
        "S_t": xt.s_t,
        "S_{t-1}": xt.s_prev,
        "score_convention": "home_score - away_score",
    }
    maa = latest_iso(fund.measurement_available_at, xt.state_available_at, xt.cutoff_iso)
    if fund.value is None:
        return _null("score_delta", fund.status if fund.status != "valid" else "MISSING_F", maa, prov)
    if xt.s_t is None or xt.s_prev is None:
        return _null("score_delta", "MISSING_REQUIRED_INPUT", maa, prov)
    ds = xt.s_t - xt.s_prev
    if ds == 0:
        return _null("score_delta", "ZERO_SCORE_DELTA", maa, prov)
    val = ExactRational.from_fraction(fund.value.fraction() / ds, "e4_per_score_point")
    return _point("score_delta", val, "valid", maa, prov, extra={"delta_s": ds})


def _discrete_gamma(xt: SharedXt, d1: MeasurementPoint, d0: MeasurementPoint) -> MeasurementPoint:
    prov = {**d1.provenance, **d0.provenance, "kind": "temporal_second_difference"}
    maa = latest_iso(d1.measurement_available_at, d0.measurement_available_at)
    if not xt.interval_ok or not xt.interval_prev_ok:
        return _null("discrete_gamma", "PERIOD_OR_SEQUENCE_GAP", maa, prov)
    if d1.value is None:
        return _null("discrete_gamma", d1.status if d1.status != "valid" else "MISSING_F", maa, prov)
    if d0.value is None:
        return _null("discrete_gamma", d0.status if d0.status != "valid" else "NO_PRIOR_F", maa, prov)
    return _point("discrete_gamma", d1.value - d0.value, "valid", maa, prov)


def _theta_observed(xt: SharedXt, fund: MeasurementPoint) -> MeasurementPoint:
    prov = {**fund.provenance, "elapsed_t": xt.elapsed_t, "elapsed_{t-1}": xt.elapsed_prev}
    maa = latest_iso(fund.measurement_available_at, xt.state_available_at, xt.cutoff_iso)
    if fund.value is None:
        return _null("theta_observed", fund.status if fund.status != "valid" else "MISSING_F", maa, prov)
    if xt.elapsed_t is None or xt.elapsed_prev is None:
        return _null("theta_observed", "MISSING_REQUIRED_INPUT", maa, prov)
    de = xt.elapsed_t - xt.elapsed_prev
    if de == 0:
        return _null("theta_observed", "ZERO_ELAPSED", maa, prov)
    val = ExactRational.from_fraction(fund.value.fraction() / de, "e4_per_elapsed_second")
    return _point("theta_observed", val, "valid", maa, prov, extra={"delta_elapsed_seconds": de})


def _pure_theta(xt: SharedXt, theta: MeasurementPoint) -> MeasurementPoint:
    prov = {
        **theta.provenance,
        "period_t": xt.period_t,
        "period_{t-1}": xt.period_prev,
        "S_t": xt.s_t,
        "S_{t-1}": xt.s_prev,
        "interpretation": "PARTIAL",
        "not": "NO-EVENT THETA",
    }
    maa = theta.measurement_available_at
    if not _same_period(xt.period_t, xt.period_prev) or xt.s_t is None or xt.s_t != xt.s_prev:
        return _null("pure_theta", "MIXED_INTERVAL", maa, prov)
    if theta.value is None:
        return _null("pure_theta", theta.status if theta.status != "valid" else "MISSING_F", maa, prov)
    return _point("pure_theta", theta.value, "valid", maa, prov)


def _candle_range(xt: SharedXt) -> MeasurementPoint:
    prov = ohlc_prov(xt.current)
    if xt.current is None:
        return _null("candle_range", "MISSING_K", None, prov, path=PATH_STATUS)
    h, lo = xt.current.yes_bid_high, xt.current.yes_bid_low
    if h is None or lo is None:
        return _null("candle_range", "MISSING_K", xt.current.available_at, prov, path=PATH_STATUS)
    return _point(
        "candle_range",
        ExactRational.from_int(h - lo),
        "valid",
        xt.current.available_at,
        prov,
        path=PATH_STATUS,
    )


def _absolute_return(xt: SharedXt, market: MeasurementPoint) -> MeasurementPoint:
    prov = dict(market.provenance)
    if market.value is None:
        return _null("absolute_return", market.status, market.measurement_available_at, prov)
    return _point("absolute_return", abs(market.value), "valid", market.measurement_available_at, prov)


def _realized_vol(xt: SharedXt) -> MeasurementPoint:
    window = xt.visible_closes[-xt.vol_window_closes :] if xt.vol_window_closes > 0 else xt.visible_closes
    prov = {
        "window_closes": xt.vol_window_closes,
        "n_closes_used": len(window),
        "definition": "sum_abs_close_to_close",
        "not": ["implied_volatility", "standard_deviation", "sqrt_sum_squared_returns"],
        "target_cutoff": xt.cutoff_iso,
    }
    if len(window) < 2:
        last = window[-1][0] if window else None
        return _null("realized_market_volatility", "INSUFFICIENT_HISTORY", last, prov, path=PATH_STATUS)
    total = 0
    for i in range(1, len(window)):
        total += abs(window[i][1] - window[i - 1][1])
    return _point(
        "realized_market_volatility",
        ExactRational.from_int(total),
        "valid",
        window[-1][0],
        prov,
        path=PATH_STATUS,
        extra={"n_changes": len(window) - 1, "abs_change_sum": total},
    )


def _directional_efficiency(xt: SharedXt) -> MeasurementPoint:
    prov = ohlc_prov(xt.current)
    if xt.current is None:
        return _null("directional_efficiency", "MISSING_K", None, prov, path=PATH_STATUS)
    o, h, lo, c = (
        xt.current.yes_bid_open,
        xt.current.yes_bid_high,
        xt.current.yes_bid_low,
        xt.current.yes_bid_close,
    )
    maa = xt.current.available_at
    if None in (o, h, lo, c):
        return _null("directional_efficiency", "MISSING_K", maa, prov, path=PATH_STATUS)
    den = h - lo
    if den == 0:
        return _null("directional_efficiency", "ZERO_RANGE", maa, prov, path=PATH_STATUS)
    num = abs(c - o)
    return _point(
        "directional_efficiency",
        ExactRational.from_fraction(Fraction(num, den), "ratio"),
        "valid",
        maa,
        prov,
        path=PATH_STATUS,
        extra={"numerator_e4": num, "denominator_e4": den},
    )


def _reconcile(observed: dict[str, MeasurementPoint]) -> None:
    needed = [observed.get(n) for n in RECONCILE_NAMES]
    if any(p is None or p.value is None or p.status != "valid" for p in needed):
        return
    market, fund, response, basis = needed
    expected = market.value - fund.value
    if response.value == expected and basis.value == expected:
        return
    for name in ("response_delta", "basis_delta"):
        point = observed[name]
        observed[name] = _null(
            name,
            "RECONCILIATION_FAILED",
            point.measurement_available_at,
            point.provenance,
        )


def compute_observed(xt: SharedXt) -> dict[str, MeasurementPoint]:
    market = _market_delta(xt)
    fund = _fundamental_delta(xt)
    response = _response_delta(xt, market, fund)
    b_t = _basis(xt, current=True)
    b_prev = _basis(xt, current=False)
    basis_d = _basis_delta(xt, b_t, b_prev)
    score = _score_delta(xt, fund)
    d0 = _prior_fundamental_delta(xt)
    gamma = _discrete_gamma(xt, fund, d0)
    theta = _theta_observed(xt, fund)
    pure = _pure_theta(xt, theta)
    rng = _candle_range(xt)
    abs_ret = _absolute_return(xt, market)
    vol = _realized_vol(xt)
    eff = _directional_efficiency(xt)
    observed = {
        "market_delta_1m": market,
        "fundamental_delta": fund,
        "response_delta": response,
        "market_fundamental_basis": b_t,
        "basis_delta": basis_d,
        "score_delta": score,
        "discrete_gamma": gamma,
        "theta_observed": theta,
        "pure_theta": pure,
        "candle_range": rng,
        "absolute_return": abs_ret,
        "realized_market_volatility": vol,
        "directional_efficiency": eff,
    }
    _reconcile(observed)
    return observed


def public_observed(observed: dict[str, MeasurementPoint]) -> dict[str, Any]:
    return {name: point.public() for name, point in observed.items()}


def build_greeks_payload(
    cfg: RollerConfig,
    xt: SharedXt,
    observed: dict[str, MeasurementPoint],
    corpus: list[dict[str, Any]],
) -> dict[str, Any]:
    from roller.v4b.baseline import baseline_available_at, compute_baseline
    from roller.v4b.residual import compute_residual

    baselines: dict[str, Any] = {}
    residuals: dict[str, Any] = {}
    for name, point in observed.items():
        base = compute_baseline(
            cfg,
            measurement_name=name,
            target_game=xt.internal_game_id,
            target_cutoff=xt.cutoff,
            condition_id=xt.condition_id,
            corpus=corpus,
        )
        baselines[name] = base
        residuals[name] = compute_residual(point, base)

    market = None
    if xt.current is not None and xt.current.yes_bid_close is not None:
        market = {
            "yes_bid_close": xt.current.yes_bid_close,
            "available_at": xt.current.available_at,
            "interval_seconds": xt.interval_seconds,
            "interval_ok": xt.interval_ok,
        }
    fundamental = None
    if xt.f_t is not None:
        fundamental = {
            "status": xt.f_t.status,
            "value": None
            if not xt.f_t.ok
            else {"numerator": xt.f_t.wins, "denominator": xt.f_t.n},
            "available_at": xt.f_t.available_at,
            "observation_id": xt.f_t.observation_id,
        }

    maas = [p.measurement_available_at for p in observed.values() if p.measurement_available_at]
    statuses = {p.status for p in observed.values()}
    if "RECONCILIATION_FAILED" in statuses:
        status = "RECONCILIATION_FAILED"
    elif any(p.status == "valid" for p in observed.values()):
        status = "IMPLEMENTED"
    else:
        status = "PARTIAL"

    payload: dict[str, Any] = {
        "identity": {
            "observation_id": xt.observation_id,
            "internal_game_id": xt.internal_game_id,
            "sport": xt.sport,
            "season": xt.season,
        },
        "versions": {
            "version": cfg.pipeline_version,
            "pipeline_version": cfg.pipeline_version,
            "state_schema_version": cfg.state_schema_version,
            "measurement_schema_version": cfg.measurement_schema_version,
            "fundamental_schema_version": cfg.fundamental_schema_version,
            "greek_schema_version": cfg.greek_schema_version,
        },
        "observed": public_observed(observed),
        "availability": {
            "state_available_at": xt.state_available_at,
            "measurement_available_at": max(maas) if maas else None,
            "baseline_available_at": baseline_available_at(xt.cutoff),
        },
        "support": next((b.get("support") for b in baselines.values() if b.get("support")), None),
        "status": status,
        "contains_future_information": True,
    }
    if fundamental is not None:
        payload["fundamental"] = fundamental
    if market is not None:
        payload["market"] = market
    if baselines:
        payload["baseline"] = baselines
    if residuals:
        payload["residual"] = residuals
    return payload
