"""Forward responses Y_{t→t+h}. Explicit future-information objects only."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import pandas as pd

from roller.admin import load_dataset
from roller.config import RollerConfig
from roller.measurement.integers import parse_e4
from roller.state.clock import elapsed_game_seconds
from roller.state.observation_id import parse_observation_id
from roller.timeutil import apply_as_of, now_utc_iso, parse_utc, resolve_cutoff, series_to_utc, to_iso

MEASUREMENT_VERSION = "v1"
DEFAULT_HORIZONS = {"1m": 60, "5m": 300, "10m": 600}


def horizon_seconds(cfg: RollerConfig | None, horizon: str) -> int:
    if cfg and cfg.response_horizons:
        for row in cfg.response_horizons.get("horizons") or []:
            if row.get("name") == horizon:
                return int(row["seconds"])
    if horizon in DEFAULT_HORIZONS:
        return DEFAULT_HORIZONS[horizon]
    raise KeyError(f"unknown horizon {horizon!r}")


def _home_candles(candles: pd.DataFrame) -> pd.DataFrame:
    if candles is None or candles.empty:
        return pd.DataFrame()
    if "team_side" in candles.columns:
        home = candles[candles["team_side"].astype(str) == "home"]
        if not home.empty:
            candles = home
    ts = series_to_utc(candles["available_at"])
    return candles.assign(_t=ts).dropna(subset=["_t"]).sort_values("_t")


def _k_before(candles: pd.DataFrame, cutoff: datetime) -> tuple[int | None, datetime | None]:
    vis = apply_as_of(_home_candles(candles).drop(columns=["_t"], errors="ignore"), cutoff)
    if vis.empty:
        return None, None
    ts = series_to_utc(vis["available_at"])
    last = vis.loc[ts.idxmax()]
    return parse_e4(last.get("yes_bid_close")), parse_utc(last.get("available_at"))


def _candles_in_window(candles: pd.DataFrame, start: datetime, end: datetime) -> pd.DataFrame:
    """Candles with start < available_at <= end. Window-end equality is included for Y, not for O_t."""
    frame = _home_candles(candles)
    if frame.empty:
        return frame
    mask = (frame["_t"] > start) & (frame["_t"] <= end)
    return frame.loc[mask]


def _score_before(pbp: pd.DataFrame, cutoff: datetime) -> tuple[int | None, datetime | None, int | None]:
    if pbp is None or pbp.empty or "available_at" not in pbp.columns:
        return None, None, None
    vis = apply_as_of(pbp, cutoff)
    if vis.empty:
        return None, None, None
    ts = series_to_utc(vis["available_at"])
    last = vis.loc[ts.idxmax()]
    score = parse_e4(last.get("home_score"))
    elapsed = elapsed_game_seconds(last.get("period"), last.get("clock"))
    return score, parse_utc(last.get("available_at")), elapsed


def _score_in_window(pbp: pd.DataFrame, start: datetime, end: datetime) -> tuple[int | None, datetime | None, int | None]:
    if pbp is None or pbp.empty:
        return None, None, None
    frame = pbp.copy()
    frame["_t"] = series_to_utc(frame["available_at"])
    sub = frame.dropna(subset=["_t"])
    sub = sub[(sub["_t"] > start) & (sub["_t"] <= end)]
    if sub.empty:
        return None, None, None
    last = sub.loc[sub["_t"].idxmax()]
    return parse_e4(last.get("home_score")), parse_utc(last.get("available_at")), elapsed_game_seconds(
        last.get("period"), last.get("clock")
    )


def _response_shell(
    *,
    observation_id: str,
    observation_time: datetime,
    horizon: str,
    seconds: int,
    measurement_name: str,
    source_resolution: str,
    path_information_status: str,
) -> dict[str, Any]:
    end = observation_time + timedelta(seconds=seconds)
    return {
        "observation_id": observation_id,
        "observation_time": to_iso(observation_time),
        "response_start_time": to_iso(observation_time),
        "response_end_time": to_iso(end),
        "measurement_time": to_iso(observation_time),
        "horizon": horizon,
        "horizon_seconds": seconds,
        "source_resolution": source_resolution,
        "measurement_name": measurement_name,
        "measurement_version": MEASUREMENT_VERSION,
        "contains_future_information": True,
        "information_boundary": "forward",
        "path_information_status": path_information_status,
        "calculated_at": now_utc_iso(),
        "k_field": "yes_bid_close",
    }


def build_response(
    cfg: RollerConfig,
    *,
    observation_id: str,
    measurement: str,
    horizon: str,
    candles: pd.DataFrame,
    pbp: pd.DataFrame | None = None,
) -> dict[str, Any]:
    _gid, obs_time, _ver = parse_observation_id(observation_id)
    seconds = horizon_seconds(cfg, horizon)
    end = obs_time + timedelta(seconds=seconds)

    if measurement.startswith("market_response"):
        expected = f"market_response_{horizon}"
        if measurement != expected:
            raise ValueError(f"measurement {measurement} does not match horizon {horizon}")
        row = _response_shell(
            observation_id=observation_id,
            observation_time=obs_time,
            horizon=horizon,
            seconds=seconds,
            measurement_name=measurement,
            source_resolution="1m",
            path_information_status="UNORDERED_SUMMARY",
        )
        k0, _ = _k_before(candles, obs_time)
        window = _candles_in_window(candles, obs_time, end)
        if k0 is None or window.empty:
            row.update({"value": None, "status": "insufficient_history", "response_available_at": to_iso(end)})
            return row
        last = window.loc[window["_t"].idxmax()]
        k1 = parse_e4(last.get("yes_bid_close"))
        avail = parse_utc(last.get("available_at"))
        row["response_available_at"] = to_iso(avail) if avail else to_iso(end)
        if k1 is None:
            row.update({"value": None, "status": "source_missing"})
            return row
        row.update({"value": k1 - k0, "status": "valid", "k_start": k0, "k_end": k1})
        return row

    if measurement == "future_realized_range":
        row = _response_shell(
            observation_id=observation_id,
            observation_time=obs_time,
            horizon=horizon,
            seconds=seconds,
            measurement_name=measurement,
            source_resolution="1m",
            path_information_status="UNORDERED_SUMMARY",
        )
        window = _candles_in_window(candles, obs_time, end)
        closes = [parse_e4(v) for v in window["yes_bid_close"].tolist()] if not window.empty else []
        known = [c for c in closes if c is not None]
        avail = parse_utc(window.loc[window["_t"].idxmax()]["available_at"]) if not window.empty else end
        row["response_available_at"] = to_iso(avail) if isinstance(avail, datetime) else to_iso(end)
        if len(known) < 1:
            row.update({"value": None, "status": "insufficient_history"})
            return row
        row.update({"value": max(known) - min(known), "status": "valid"})
        return row

    if measurement == "future_realized_volatility":
        row = _response_shell(
            observation_id=observation_id,
            observation_time=obs_time,
            horizon=horizon,
            seconds=seconds,
            measurement_name=measurement,
            source_resolution="1m",
            path_information_status="UNORDERED_SUMMARY",
        )
        k0, _ = _k_before(candles, obs_time)
        window = _candles_in_window(candles, obs_time, end)
        closes = ([k0] if k0 is not None else []) + [
            parse_e4(v) for v in (window["yes_bid_close"].tolist() if not window.empty else [])
        ]
        known = [c for c in closes if c is not None]
        avail = parse_utc(window.loc[window["_t"].idxmax()]["available_at"]) if not window.empty else end
        row["response_available_at"] = to_iso(avail) if isinstance(avail, datetime) else to_iso(end)
        if len(known) < 2:
            row.update({"value": None, "status": "insufficient_history"})
            return row
        diffs = [abs(known[i] - known[i - 1]) for i in range(1, len(known))]
        row.update({"value": int(sum(diffs)), "status": "valid", "n_changes": len(diffs)})
        return row

    if measurement == "score_response":
        row = _response_shell(
            observation_id=observation_id,
            observation_time=obs_time,
            horizon=horizon,
            seconds=seconds,
            measurement_name=measurement,
            source_resolution="event",
            path_information_status="ORDERED",
        )
        s0, _, _ = _score_before(pbp if pbp is not None else pd.DataFrame(), obs_time)
        s1, avail, _ = _score_in_window(pbp if pbp is not None else pd.DataFrame(), obs_time, end)
        row["response_available_at"] = to_iso(avail) if avail else to_iso(end)
        if s0 is None or s1 is None:
            row.update({"value": None, "status": "insufficient_history"})
            return row
        row.update({"value": s1 - s0, "status": "valid"})
        return row

    if measurement == "clock_response":
        row = _response_shell(
            observation_id=observation_id,
            observation_time=obs_time,
            horizon=horizon,
            seconds=seconds,
            measurement_name=measurement,
            source_resolution="event",
            path_information_status="NOT_SUPPORTED",
        )
        _s0, _, e0 = _score_before(pbp if pbp is not None else pd.DataFrame(), obs_time)
        _s1, avail, e1 = _score_in_window(pbp if pbp is not None else pd.DataFrame(), obs_time, end)
        row["response_available_at"] = to_iso(avail) if avail else to_iso(end)
        row["pure_clock_isolation"] = "PARTIAL"
        if e0 is None or e1 is None:
            row.update({"value": None, "status": "insufficient_history"})
            return row
        row.update({"value": e1 - e0, "status": "valid"})
        return row

    raise KeyError(f"unknown forward measurement {measurement!r}")


def load_game_tables(cfg: RollerConfig, internal_game_id: str) -> tuple[str, str, pd.DataFrame, pd.DataFrame]:
    from roller.admin import load_identity

    ident = load_identity(cfg)
    hit = ident[ident["internal_game_id"] == internal_game_id]
    if hit.empty:
        raise KeyError(internal_game_id)
    sport, season = hit.iloc[0]["sport"], hit.iloc[0]["season"]
    try:
        candles = load_dataset(cfg, sport, season, "kalshi_candles")
    except FileNotFoundError:
        candles = pd.DataFrame()
    try:
        pbp = load_dataset(cfg, sport, season, "pbp")
    except FileNotFoundError:
        pbp = pd.DataFrame()
    if not candles.empty:
        candles = candles[candles["internal_game_id"] == internal_game_id]
    if not pbp.empty:
        pbp = pbp[pbp["internal_game_id"] == internal_game_id]
    return sport, season, candles, pbp
