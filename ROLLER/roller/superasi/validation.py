"""Validate SuperASI packages. Do not auto-repair."""

from __future__ import annotations

from typing import Any

from roller.superasi.models import SuperasiError
from roller.superasi.package import sha256_hex
from roller.superasi.versions import PACKAGE_SCHEMA, SOURCES


def validate_package(pkg: dict[str, Any], trades: list[dict[str, Any]] | None = None) -> None:
    if not isinstance(pkg, dict):
        raise SuperasiError("PACKAGE_SCHEMA_INVALID", "package is not an object")
    if pkg.get("schema_version") != PACKAGE_SCHEMA:
        raise SuperasiError(
            "PACKAGE_SCHEMA_INVALID",
            f"schema_version {pkg.get('schema_version')!r} != {PACKAGE_SCHEMA}",
        )
    if pkg.get("source") not in SOURCES:
        raise SuperasiError("PACKAGE_SCHEMA_INVALID", f"bad source {pkg.get('source')!r}")
    if not pkg.get("package_id"):
        raise SuperasiError("PACKAGE_SCHEMA_INVALID", "package_id required")
    n = pkg.get("population_n")
    if not isinstance(n, int) or n <= 0:
        raise SuperasiError("EMPTY_POPULATION", "population_n must be a positive integer")
    if trades is not None:
        if len(trades) != n:
            raise SuperasiError(
                "POPULATION_COUNT_MISMATCH",
                f"len(trades)={len(trades)} != population_n={n}",
            )
        expected = (pkg.get("checksums") or {}).get("trades")
        if expected and sha256_hex(trades) != expected:
            raise SuperasiError("PACKAGE_SCHEMA_INVALID", "trades checksum mismatch")
        for i, t in enumerate(trades):
            if not t.get("ticker"):
                raise SuperasiError("PACKAGE_SCHEMA_INVALID", f"trade[{i}] missing ticker")
            if t.get("price_basis") == "LAST_TRADE_PRINT":
                continue


def validate_windows(windows: list[dict[str, Any]], path_loss_n: int) -> None:
    if path_loss_n < 0:
        raise SuperasiError("PACKAGE_SCHEMA_INVALID", "path_loss_n negative")
    ids = {w.get("ticker") for w in windows if w.get("offset") == 0}
    if path_loss_n and len(ids) != path_loss_n:
        # Missing offset-0 is DATA_REQUIRED, not silent pad.
        raise SuperasiError(
            "PATH_WINDOW_DATA_REQUIRED",
            f"offset-0 window trades={len(ids)} != path_loss_n={path_loss_n}",
        )
