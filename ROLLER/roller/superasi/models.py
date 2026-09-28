"""SuperASI data shapes and errors. Research only. No order submission."""

from __future__ import annotations

from typing import Any


class SuperasiError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")

    def as_dict(self) -> dict[str, str]:
        return {"status": self.code, "code": self.code, "message": self.message}


def frac(numer: int, denom: int) -> dict[str, Any]:
    if denom == 0:
        raise SuperasiError("PACKAGE_SCHEMA_INVALID", "fraction denominator is 0")
    return {
        "numer": int(numer),
        "denom": int(denom),
        "status": "OBSERVED",
    }


def metric(status: str, value: Any = None, **extra: Any) -> dict[str, Any]:
    out = {"status": status, "value": value}
    out.update(extra)
    return out
