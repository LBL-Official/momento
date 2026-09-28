"""ROLLER — point-in-time sports research database.

The warehouse knows what data exists. ROLLER knows what could have been
known at a particular time.
"""

from __future__ import annotations

PIPELINE_VERSION = "4.0.0-C"
DATABASE_VERSION = "4.0.0-C"
STATE_SCHEMA_VERSION = "2.0.0"
MEASUREMENT_SCHEMA_VERSION = "3.0.0"
FUNDAMENTAL_SCHEMA_VERSION = "4.0.0-A"
GREEK_SCHEMA_VERSION = "4.0.0-B"
GREEK_ARCHITECTURE_VERSION = "4.0.0-C"

from roller.point_in_time.filters import AsOfRequiredError, FutureInformationError
from roller.point_in_time.query import InformationSet, ResearchNotImplementedError, Roller

__all__ = [
    "DATABASE_VERSION",
    "PIPELINE_VERSION",
    "STATE_SCHEMA_VERSION",
    "MEASUREMENT_SCHEMA_VERSION",
    "FUNDAMENTAL_SCHEMA_VERSION",
    "GREEK_SCHEMA_VERSION",
    "GREEK_ARCHITECTURE_VERSION",
    "AsOfRequiredError",
    "FutureInformationError",
    "InformationSet",
    "ResearchNotImplementedError",
    "Roller",
]
