"""Architectural types. Identity is a hard firewall, not a display label."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class GreekIdentity:
    measurement_name: str
    definition_version: str | None
    information_regime: str
    resolution: str | None
    measurement_class: str | None = None
    conditioning_schema: str | None = None
    canonical_identity: str | None = None
    informal_family: str | None = None
    identity_kind: str | None = None

    def key(self) -> tuple[Any, ...]:
        return (
            self.measurement_name,
            self.measurement_class,
            self.definition_version,
            self.information_regime,
            self.resolution,
            self.conditioning_schema,
        )

    def public(self) -> dict[str, Any]:
        return {
            "measurement_name": self.measurement_name,
            "canonical_identity": self.canonical_identity or self.measurement_name,
            "measurement_class": self.measurement_class,
            "definition_version": self.definition_version,
            "information_regime": self.information_regime,
            "resolution": self.resolution,
            "conditioning_schema": self.conditioning_schema,
            "informal_family": self.informal_family,
            "identity_kind": self.identity_kind,
        }


@dataclass(frozen=True)
class MeasurementContract:
    measurement_name: str
    definition_version: str | None
    information_regime: str
    resolution: str | None
    requires: tuple[str, ...]
    information_boundary: str
    edge_claim: bool = False
    status: str = ""
    measurement_class: str | None = None
    conditioning_schema: str | None = None

    def public(self) -> dict[str, Any]:
        return {
            "measurement_name": self.measurement_name,
            "measurement_class": self.measurement_class,
            "definition_version": self.definition_version,
            "information_regime": self.information_regime,
            "resolution": self.resolution,
            "conditioning_schema": self.conditioning_schema,
            "requires": list(self.requires),
            "information_boundary": self.information_boundary,
            "edge_claim": self.edge_claim,
            "status": self.status,
        }


@dataclass(frozen=True)
class GreekProvenance:
    source: str
    source_schema_version: str
    source_measurement_name: str
    source_identity: dict[str, Any]
    transformation: str
    source_status: str | None = None

    def public(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "source_schema_version": self.source_schema_version,
            "source_measurement_name": self.source_measurement_name,
            "source_identity": dict(self.source_identity),
            "transformation": self.transformation,
            "source_status": self.source_status,
        }


def identity_from_row(row: dict[str, Any]) -> GreekIdentity:
    from roller.v4c.information_regimes import regime_of
    from roller.v4c.measurement_classes import CANONICAL_IDENTITY, INFORMAL_FAMILY

    name = str(row["measurement_name"])
    return GreekIdentity(
        measurement_name=name,
        definition_version=row.get("definition_version"),
        information_regime=regime_of(row),
        resolution=row.get("resolution"),
        measurement_class=row.get("measurement_class"),
        conditioning_schema=row.get("conditioning_schema"),
        canonical_identity=row.get("canonical_identity") or CANONICAL_IDENTITY.get(name) or name,
        informal_family=row.get("informal_family") or INFORMAL_FAMILY.get(name),
        identity_kind=row.get("identity_kind"),
    )


def contract_from_row(row: dict[str, Any]) -> MeasurementContract:
    from roller.v4c.information_regimes import regime_of

    req = row.get("requires") or []
    return MeasurementContract(
        measurement_name=str(row["measurement_name"]),
        definition_version=row.get("definition_version"),
        information_regime=regime_of(row),
        resolution=row.get("resolution"),
        requires=tuple(str(x) for x in req),
        information_boundary=str(row.get("information_boundary") or ""),
        edge_claim=bool(row.get("edge_claim")),
        status=str(row.get("status") or ""),
        measurement_class=row.get("measurement_class"),
        conditioning_schema=row.get("conditioning_schema"),
    )
