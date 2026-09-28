"""E[M | core_v1] over other games. measurement_available_at_i < t."""

from __future__ import annotations

from datetime import datetime
from fractions import Fraction
from typing import Any

from roller.config import RollerConfig
from roller.io_csv import read_csv_optional
from roller.paths import derived_dir
from roller.timeutil import parse_utc, to_iso
from roller.v4b.definitions import v4b_support_floors
from roller.v4b.types import ExactRational, MeasurementPoint

CORPUS_NAME = "v4b_greek_observations.csv"


def parse_measurement_value(value: Any) -> Fraction | None:
    if value is None or value == "":
        return None
    if isinstance(value, ExactRational):
        return value.fraction()
    if isinstance(value, Fraction):
        return value
    if isinstance(value, dict) and value.get("denominator") not in (None, "", 0):
        try:
            return Fraction(int(value["numerator"]), int(value["denominator"]))
        except (TypeError, ValueError, ZeroDivisionError):
            return None
    try:
        return Fraction(int(value), 1)
    except (TypeError, ValueError):
        return None


def measurement_eligible(
    row: dict[str, Any],
    *,
    target_cutoff,
    target_game: str,
    condition_id: str | None,
) -> bool:
    if str(row.get("internal_game_id") or "") == str(target_game):
        return False
    if condition_id and row.get("condition_id") != condition_id:
        return False
    ts = parse_utc(row.get("measurement_available_at"))
    cut = target_cutoff if isinstance(target_cutoff, datetime) else parse_utc(target_cutoff)
    if ts is None or cut is None:
        return False
    return ts < cut


def _support(rows: list[dict[str, Any]], floors: dict[str, int]) -> dict[str, Any]:
    games = {str(r.get("internal_game_id") or "") for r in rows}
    games.discard("")
    dates: set[str] = set()
    seasons: set[str] = set()
    times: list[datetime] = []
    for r in rows:
        ts = parse_utc(r.get("measurement_available_at"))
        if ts is not None:
            times.append(ts)
            dates.add(ts.date().isoformat())
        if r.get("game_date"):
            dates.add(str(r["game_date"])[:10])
        if r.get("season"):
            seasons.add(str(r["season"]))
    times_sorted = sorted(times)
    sufficient = (
        len(rows) >= floors["minimum_observations"]
        and len(games) >= floors["minimum_unique_games"]
        and len(dates) >= floors["minimum_unique_dates"]
        and len(seasons) >= floors["minimum_unique_seasons"]
    )
    return {
        "n_observations": len(rows),
        "n_unique_games": len(games),
        "n_unique_dates": len(dates),
        "n_unique_seasons": len(seasons),
        "first_measurement_available_at": to_iso(times_sorted[0]) if times_sorted else None,
        "last_measurement_available_at": to_iso(times_sorted[-1]) if times_sorted else None,
        "sufficient": sufficient,
        "effective_n": None,
        "effective_n_status": "NOT_IMPLEMENTED",
        "repeated_observation_warning": len(rows) > len(games),
    }


def exact_mean(values: list[Fraction]) -> Fraction | None:
    if not values:
        return None
    return sum(values, Fraction(0, 1)) / len(values)


def exact_mad(values: list[Fraction], mean: Fraction) -> Fraction:
    if not values:
        return Fraction(0, 1)
    return sum((abs(v - mean) for v in values), Fraction(0, 1)) / len(values)


def compute_baseline(
    cfg: RollerConfig,
    *,
    measurement_name: str,
    target_game: str,
    target_cutoff,
    condition_id: str | None,
    corpus: list[dict[str, Any]],
) -> dict[str, Any]:
    floors = v4b_support_floors(cfg)
    eligible: list[dict[str, Any]] = []
    values: list[Fraction] = []
    for row in corpus:
        if row.get("measurement_name") != measurement_name:
            continue
        if row.get("status") not in (None, "", "valid"):
            continue
        if not measurement_eligible(
            row, target_cutoff=target_cutoff, target_game=target_game, condition_id=condition_id
        ):
            continue
        parsed = parse_measurement_value(row.get("value"))
        if parsed is None:
            continue
        eligible.append(row)
        values.append(parsed)
    support = _support(eligible, floors)
    out: dict[str, Any] = {
        "measurement_name": measurement_name,
        "conditioning_schema_version": "core_v1",
        "condition_id": condition_id,
        "contains_future_information": True,
        "expected": None,
        "dispersion": None,
        "support": support,
        "status": "INSUFFICIENT_SUPPORT",
        "effective_n": None,
    }
    if not support["sufficient"] or not values:
        return out
    mean = exact_mean(values)
    assert mean is not None
    mad = exact_mad(values, mean)
    units = "e4"
    first = eligible[0].get("value")
    if isinstance(first, dict) and first.get("units"):
        units = str(first["units"])
    out["expected"] = ExactRational.from_fraction(mean, units).public()
    out["dispersion"] = {
        "kind": "mean_absolute_deviation",
        **ExactRational.from_fraction(mad, units).public(),
    }
    out["status"] = "valid"
    return out


def load_v4b_corpus(cfg: RollerConfig, sport: str, season: str) -> list[dict[str, Any]]:
    """Optional derived file. Not a public PIT dataset. Always re-filter at query time."""
    try:
        path_key = cfg.season_meta(sport, season).get("path_key") or season
    except KeyError:
        return []
    path = derived_dir(cfg.root, sport, path_key) / CORPUS_NAME
    df = read_csv_optional(path)
    if df is None or df.empty:
        return []
    return df.to_dict("records")


def baseline_available_at(target_cutoff) -> str | None:
    cut = target_cutoff if isinstance(target_cutoff, datetime) else parse_utc(target_cutoff)
    return to_iso(cut) if cut is not None else None


def observed_as_corpus_value(point: MeasurementPoint) -> dict[str, Any] | None:
    if point.value is None:
        return None
    return point.value.public()
