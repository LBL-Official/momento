"""Read-only frozen-object loader. Does not import training. Does not evaluate 2025–26."""

from terminal_efficiency.consumption.errors import (
    ConsumptionForbidden,
    FrozenUnavailable,
    ProvenanceRequired,
    VersionMismatch,
)
from terminal_efficiency.consumption.models import FrozenIdentity, FrozenObservation

def __getattr__(name: str):
    if name == "FrozenObjectLoader":
        from terminal_efficiency.consumption.loader import FrozenObjectLoader

        return FrozenObjectLoader
    raise AttributeError(name)


__all__ = [
    "ConsumptionForbidden",
    "FrozenIdentity",
    "FrozenObjectLoader",
    "FrozenObservation",
    "FrozenUnavailable",
    "ProvenanceRequired",
    "VersionMismatch",
]
