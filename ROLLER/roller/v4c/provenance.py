"""Auditable overlay provenance. source must be V4B_CANONICAL_RESULT."""

from __future__ import annotations

from typing import Any

from roller.v4c.types import GreekIdentity, GreekProvenance

SOURCE = "V4B_CANONICAL_RESULT"
SOURCE_SCHEMA_VERSION = "4.0.0-B"
TRANSFORMATION = "LOSSLESS_METADATA_MAPPING"


def measurement_provenance(
    identity: GreekIdentity,
    *,
    source_status: str | None,
) -> GreekProvenance:
    return GreekProvenance(
        source=SOURCE,
        source_schema_version=SOURCE_SCHEMA_VERSION,
        source_measurement_name=identity.measurement_name,
        source_identity=identity.public(),
        transformation=TRANSFORMATION,
        source_status=source_status,
    )


def assert_overlay_provenance(body: dict[str, Any]) -> None:
    if body.get("source") != SOURCE:
        raise ValueError("V4C provenance source must be V4B_CANONICAL_RESULT")
    if body.get("transformation") != TRANSFORMATION:
        raise ValueError("V4C transformation must be LOSSLESS_METADATA_MAPPING")
    if body.get("source_schema_version") != SOURCE_SCHEMA_VERSION:
        raise ValueError("V4C source_schema_version must be 4.0.0-B")
