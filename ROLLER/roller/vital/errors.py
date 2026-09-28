"""Vital errors. Control plane only. No order submission."""

from __future__ import annotations

from typing import Any


class VitalError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")

    def as_dict(self) -> dict[str, Any]:
        return {"status": self.code, "code": self.code, "message": self.message}
