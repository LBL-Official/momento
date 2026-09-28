"""Frozen identity and observation view. No fit/train/calibrate methods."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


REQUIRED_VIEW_FIELDS = (
    "observation_id",
    "game_id",
    "league",
    "season",
    "prediction_timestamp",
    "feature_as_of_timestamp",
    "raw_probability",
    "calibrated_probability",
    "model_version",
    "dataset_version",
    "feature_set_version",
    "code_version",
    "artifact_manifest_hash",
    "prediction_available",
    "availability_status",
    "coverage_status",
    "feature_availability_status",
    "data_quality_flags",
)


@dataclass(frozen=True)
class FrozenIdentity:
    league: str
    season: str
    dataset_version: str
    feature_set_version: str
    model_version: str
    code_version: str
    artifact_manifest_hash: str | None = None

    def key(self) -> tuple[str, ...]:
        return (
            self.league.upper(),
            self.season,
            self.dataset_version,
            self.feature_set_version,
            self.model_version,
            self.code_version,
        )

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FrozenObservation:
    observation_id: str
    game_id: str
    league: str
    season: str
    prediction_timestamp: str
    feature_as_of_timestamp: str
    raw_probability: float | None
    calibrated_probability: float | None
    model_version: str
    dataset_version: str
    feature_set_version: str
    code_version: str
    artifact_manifest_hash: str
    prediction_available: bool
    availability_status: str
    coverage_status: str
    feature_availability_status: str
    data_quality_flags: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def unavailable_observation(
    *,
    game_id: str,
    identity: FrozenIdentity,
    reason: str,
) -> FrozenObservation:
    return FrozenObservation(
        observation_id="",
        game_id=game_id,
        league=identity.league,
        season=identity.season,
        prediction_timestamp="",
        feature_as_of_timestamp="",
        raw_probability=None,
        calibrated_probability=None,
        model_version=identity.model_version,
        dataset_version=identity.dataset_version,
        feature_set_version=identity.feature_set_version,
        code_version=identity.code_version,
        artifact_manifest_hash=identity.artifact_manifest_hash or "",
        prediction_available=False,
        availability_status="UNAVAILABLE",
        coverage_status=reason,
        feature_availability_status="UNAVAILABLE",
        data_quality_flags=reason,
    )
