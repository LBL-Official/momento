"""Validate freeze identity, schema, coverage, and universe. Read-only."""

from __future__ import annotations

from terminal_efficiency.consumption.errors import (
    ConsumptionForbidden,
    FrozenUnavailable,
    ProvenanceRequired,
    VersionMismatch,
)
from terminal_efficiency.consumption.models import REQUIRED_VIEW_FIELDS, FrozenIdentity

FORBIDDEN_SEASONS_FOR_EVAL = frozenset({"2025-2026", "2025-26"})
KNOWN_FORBIDDEN_METHODS = ("fit", "train", "calibrate", "select_model", "evaluate_oos")


def reject_oos_season(season: str) -> None:
    if str(season) in FORBIDDEN_SEASONS_FOR_EVAL or str(season).startswith("2025-26"):
        raise ConsumptionForbidden(
            "PHASE 7 OOS EVALUATION = NOT AUTHORIZED (loader is not a backdoor)"
        )


def reject_kalshi_join(request: dict) -> None:
    keys = {str(k).lower() for k in request}
    banned = {
        "kalshi",
        "residual",
        "yes_bid",
        "market_edge",
        "k_t",
        "join_candles",
        "evaluate_oos",
    }
    hit = keys & banned
    if hit:
        raise ConsumptionForbidden(f"loader must not join market or compute residuals: {sorted(hit)}")


def match_identity(requested: FrozenIdentity, published: FrozenIdentity) -> None:
    if requested.league.upper() != published.league.upper():
        raise VersionMismatch(f"league {requested.league} != {published.league}")
    if requested.season != published.season:
        raise VersionMismatch(f"season {requested.season} != {published.season}")
    if requested.dataset_version != published.dataset_version:
        raise VersionMismatch("dataset_version mismatch — UNAVAILABLE, no fallback")
    if requested.feature_set_version != published.feature_set_version:
        raise VersionMismatch("feature_set_version mismatch — UNAVAILABLE, no fallback")
    if requested.model_version != published.model_version:
        raise VersionMismatch(f"model_version {requested.model_version} UNAVAILABLE")
    if requested.code_version != published.code_version:
        raise VersionMismatch("code_version mismatch — UNAVAILABLE, no fallback")
    if requested.artifact_manifest_hash and requested.artifact_manifest_hash != published.artifact_manifest_hash:
        raise VersionMismatch("artifact_manifest_hash mismatch — UNAVAILABLE, no fallback")


def require_view_columns(columns: list[str]) -> None:
    missing = [c for c in REQUIRED_VIEW_FIELDS if c not in columns]
    if missing:
        raise FrozenUnavailable(f"view missing required provenance fields: {missing}")


def reject_probabilities_only(columns: list[str] | None) -> None:
    if columns is None:
        return
    want = {c.lower() for c in columns}
    if want <= {"game_id", "calibrated_probability", "probability", "xib_home_win_probability"}:
        raise ProvenanceRequired(
            "probabilities-only projection is forbidden; it strips coverage and provenance"
        )
    if "calibrated_probability" in want or "raw_probability" in want:
        for req in (
            "availability_status",
            "data_quality_flags",
            "model_version",
            "prediction_timestamp",
            "feature_as_of_timestamp",
        ):
            if req not in want:
                raise ProvenanceRequired(
                    f"requesting probabilities without {req} is a quality strip"
                )


def assert_no_training_api(obj: object) -> None:
    owned = type(obj).__dict__
    for name in KNOWN_FORBIDDEN_METHODS:
        if name in owned and callable(owned[name]):
            raise ConsumptionForbidden(f"consumption object must not expose {name}()")
