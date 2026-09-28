"""Versioned Results analysis contract. Bump semantics when a reported number changes."""

from __future__ import annotations

SEMANTICS_VERSION = "2.0.0"
SCHEMA_VERSION = "2.0.0"
CODE_VERSION = "results_math_v2.0.0"

MIN_CLUSTER_UNITS = 2

WILSON_Z = 1.959963984540054
BOOTSTRAP_ITERATIONS = 10_000
BOOTSTRAP_SEED = 20260909
CONFIDENCE_LEVEL = 0.95
