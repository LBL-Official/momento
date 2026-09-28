"""Machine-tested leakage invariant. Not a comment."""

from __future__ import annotations

import re
from typing import Iterable

from roller.nba_8040_reverse_features.catalog import (
    FORBIDDEN_NAMES,
    FORBIDDEN_TIMING,
    PREDICTIVE_TIMING,
    spec_by_name,
)
from roller.nba_8040_reverse_features.errors import ReverseFeaturesError

_FUTURE_HINT = re.compile(
    r"(after|t40|^s$|terminal|post_entry|time_to_40|hit_90|min_after|max_after|next_close)",
    re.I,
)


def assert_predictive_columns(columns: Iterable[str]) -> None:
    specs = spec_by_name()
    seen: list[str] = []
    for raw in columns:
        name = str(raw)
        key = name.lower()
        if key in FORBIDDEN_NAMES or _FUTURE_HINT.search(key):
            raise ReverseFeaturesError(
                "LEAKAGE", f"forbidden column {name!r} entered PREDICTIVE_FEATURE_MATRIX"
            )
        spec = specs.get(name)
        if spec is None:
            raise ReverseFeaturesError("LEAKAGE", f"unregistered matrix column {name!r}")
        if spec.timing in FORBIDDEN_TIMING or spec.timing not in PREDICTIVE_TIMING:
            raise ReverseFeaturesError(
                "LEAKAGE", f"{name} timing {spec.timing} is not allowed in the predictive matrix"
            )
        if not spec.include_in_matrix:
            raise ReverseFeaturesError("LEAKAGE", f"{name} is not a matrix feature")
        seen.append(name)
    if not seen:
        raise ReverseFeaturesError("LEAKAGE", "predictive matrix is empty")
