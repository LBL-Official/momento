"""Pre-80 feature store for all 604 instances. No outcome selection."""

from __future__ import annotations

from datetime import datetime, timedelta
from statistics import pstdev
from typing import Any

import pandas as pd

from roller.nba_8040_reverse_features.bars import _parse_utc, load_ticker_bars, split_pre_post
from roller.nba_8040_reverse_features.catalog import WINDOWS, spec_by_name
from roller.nba_8040_reverse_features.errors import ReverseFeaturesError
from roller.nba_8040_reverse_features.instances import load_instances
from roller.nba_8040_reverse_features.locks import NBA_Q2Q3_N, features_path

STATUS_OK = "OBSERVED"
STATUS_MISSING = "OBSERVATION_UNAVAILABLE"
STATUS_SOURCE = "SOURCE_UNAVAILABLE"
STATUS_OP = "OPERATION_REQUIRED"
QUARTER_S = 720.0
REGULATION_S = 2880.0


def _status_col(name: str) -> str:
    return f"{name}__status"


def _window(pre: list[tuple[datetime, float]], entry: datetime, minutes: int) -> list[float]:
    start = entry - timedelta(minutes=minutes)
    return [close for stamp, close in pre if start <= stamp < entry]


def _direction_changes(closes: list[float]) -> float | None:
    if len(closes) < 3:
        return None
    signs: list[int] = []
    for left, right in zip(closes, closes[1:]):
        if right > left:
            signs.append(1)
        elif right < left:
            signs.append(-1)
        else:
            signs.append(0)
    flips = 0
    last = 0
    for sign in signs:
        if sign == 0:
            continue
        if last != 0 and sign != last:
            flips += 1
        last = sign
    return float(flips)


def _put(row: dict[str, Any], name: str, value: Any, status: str) -> None:
    row[name] = value
    row[_status_col(name)] = status


def _optional_float(value: Any) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _csv_state(instance: dict[str, Any]) -> dict[str, Any]:
    entry = int(instance["entry_bid_cents"])
    ask = instance["entry_ask_cents"]
    pregame = int(instance["pregame_cents"])
    margin = int(instance["bought_margin"])
    remaining = float(instance["period_remaining_s"])
    game_left = float(instance["game_seconds_remaining"])
    overtime = bool(game_left < 0 or remaining > QUARTER_S + 1.0 or game_left > REGULATION_S)
    volume = _optional_float(instance.get("entry_volume"))
    row: dict[str, Any] = {
        "instance_id": instance["instance_id"],
        "event_id": instance["event_id"],
        "game_id": instance["game_id"],
        "ticker": instance["ticker"],
        "period": instance["period"],
        "side": instance["side"],
        "home_team": instance["home_team"],
        "away_team": instance["away_team"],
        "bought_team": instance["bought_team"],
        "season_phase": instance["season_phase"],
        "dataset_split": instance["dataset_split"],
        "game_date": instance["game_date"],
        "timestamp_utc": instance["timestamp_utc"],
        "alignment_confidence": instance["alignment_confidence"],
        "score_change_1m": None,
        "possession_team": None,
        "score_change_1m__status": STATUS_OP,
        "possession_team__status": STATUS_SOURCE,
    }
    _put(row, "entry_bid_cents", float(entry), STATUS_OK)
    _put(row, "entry_ask_cents", float(ask) if ask is not None else None, STATUS_OK if ask is not None else STATUS_MISSING)
    _put(
        row,
        "spread_cents",
        float(ask - entry) if ask is not None else None,
        STATUS_OK if ask is not None else STATUS_MISSING,
    )
    last = instance["entry_last_cents"]
    _put(row, "entry_last_cents", float(last) if last is not None else None, STATUS_OK if last is not None else STATUS_MISSING)
    _put(row, "entry_volume", volume, STATUS_OK if volume is not None else STATUS_MISSING)
    _put(row, "pregame_cents", float(pregame), STATUS_OK)
    _put(row, "distance_from_open", float(entry - pregame), STATUS_OK)
    _put(row, "bought_margin", float(margin), STATUS_OK)
    _put(row, "abs_margin", float(abs(margin)), STATUS_OK)
    _put(row, "score_home", float(instance["score_home"]), STATUS_OK)
    _put(row, "score_away", float(instance["score_away"]), STATUS_OK)
    _put(row, "leading", 1.0 if margin > 0 else 0.0, STATUS_OK)
    _put(row, "tie", 1.0 if margin == 0 else 0.0, STATUS_OK)
    _put(row, "favorite_leading", 1.0 if pregame >= 50 and margin > 0 else 0.0, STATUS_OK)
    _put(row, "period_remaining_s", remaining, STATUS_OK)
    _put(row, "game_seconds_remaining", game_left, STATUS_OK)
    _put(row, "frac_period_remaining", remaining / QUARTER_S, STATUS_OK)
    _put(row, "frac_game_elapsed", 1.0 - (game_left / REGULATION_S), STATUS_OK)
    _put(row, "regular_season", 1.0 if instance["regular_season"] else 0.0, STATUS_OK)
    _put(row, "jump_through_80", 1.0 if entry > 80 else 0.0, STATUS_OK)
    _put(row, "exact_80", 1.0 if entry == 80 else 0.0, STATUS_OK)
    _put(row, "period_q2", 1.0 if instance["period"] == "Q2" else 0.0, STATUS_OK)
    _put(row, "period_q3", 1.0 if instance["period"] == "Q3" else 0.0, STATUS_OK)
    _put(row, "overtime_flag", 1.0 if overtime else 0.0, STATUS_OK)
    return row


def _path_state(
    row: dict[str, Any],
    instance: dict[str, Any],
    pre: list[tuple[datetime, float]],
) -> None:
    entry_bid = float(instance["entry_bid_cents"])
    n_pre = len(pre)
    _put(row, "bars_before_n", float(n_pre), STATUS_OK)
    if not pre:
        _put(row, "prior_close_cents", None, STATUS_MISSING)
        _put(row, "came_from_below", None, STATUS_MISSING)
    else:
        prior = pre[-1][1]
        _put(row, "prior_close_cents", float(prior), STATUS_OK)
        _put(row, "came_from_below", 1.0 if prior < 80 else 0.0, STATUS_OK)
    entry_ts = _parse_utc(instance["timestamp_utc"])
    if entry_ts is None:
        raise ReverseFeaturesError("DATA_REQUIRED", f"bad timestamp {instance['ticker']}")
    for w in WINDOWS:
        closes = _window(pre, entry_ts, w)
        n = len(closes)
        _put(row, f"n_bars_{w}m", float(n), STATUS_OK)
        if n == 0:
            for name in (
                f"close_{w}m_before",
                f"delta_{w}m",
                f"velocity_{w}m",
                f"accel_{w}m",
                f"min_{w}m",
                f"max_{w}m",
                f"range_{w}m",
                f"std_{w}m",
                f"direction_changes_{w}m",
            ):
                _put(row, name, None, STATUS_MISSING)
            continue
        close_w = closes[0]
        delta = entry_bid - close_w
        _put(row, f"close_{w}m_before", float(close_w), STATUS_OK)
        _put(row, f"delta_{w}m", float(delta), STATUS_OK)
        _put(row, f"velocity_{w}m", float(delta / w), STATUS_OK)
        _put(row, f"min_{w}m", float(min(closes)), STATUS_OK)
        _put(row, f"max_{w}m", float(max(closes)), STATUS_OK)
        _put(row, f"range_{w}m", float(max(closes) - min(closes)), STATUS_OK)
        if n >= 4:
            mid = n // 2
            first = closes[:mid]
            second = closes[mid:]
            v1 = (first[-1] - first[0]) / max(len(first) - 1, 1)
            v2 = (second[-1] - second[0]) / max(len(second) - 1, 1)
            _put(row, f"accel_{w}m", float(v2 - v1), STATUS_OK)
        else:
            _put(row, f"accel_{w}m", None, STATUS_MISSING)
        if n >= 3:
            _put(row, f"std_{w}m", float(pstdev(closes)), STATUS_OK)
            _put(row, f"direction_changes_{w}m", _direction_changes(closes), STATUS_OK)
        else:
            _put(row, f"std_{w}m", None, STATUS_MISSING)
            _put(row, f"direction_changes_{w}m", None, STATUS_MISSING)


def build_features(
    instances: list[dict[str, Any]] | None = None,
    bars: dict | None = None,
) -> pd.DataFrame:
    rows = instances if instances is not None else load_instances()
    if len(rows) != NBA_Q2Q3_N:
        raise ReverseFeaturesError("LOCK_MISMATCH", f"feature store N {len(rows)} != {NBA_Q2Q3_N}")
    if bars is None:
        bars = load_ticker_bars({row["ticker"] for row in rows})
    out: list[dict[str, Any]] = []
    for instance in rows:
        entry_ts = _parse_utc(instance["timestamp_utc"])
        if entry_ts is None:
            raise ReverseFeaturesError("DATA_REQUIRED", f"bad timestamp {instance['ticker']}")
        series = bars.get(instance["ticker"], [])
        pre, _post = split_pre_post(series, entry_ts)
        item = _csv_state(instance)
        _path_state(item, instance, pre)
        out.append(item)
    frame = pd.DataFrame(out)
    if len(frame) != NBA_Q2Q3_N:
        raise ReverseFeaturesError("LOCK_MISMATCH", "feature frame N mismatch")
    if frame["instance_id"].nunique() != NBA_Q2Q3_N:
        raise ReverseFeaturesError("LOCK_MISMATCH", "feature instance_id not unique")
    for spec in spec_by_name().values():
        if spec.name not in frame.columns:
            raise ReverseFeaturesError("LOCK_MISMATCH", f"missing feature {spec.name}")
    return frame


def write_features(frame: pd.DataFrame) -> None:
    path = features_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)
