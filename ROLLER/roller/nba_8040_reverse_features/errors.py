"""Fail-closed errors. Research only."""

from __future__ import annotations


class ReverseFeaturesError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")

    def as_dict(self) -> dict[str, str]:
        return {"status": self.code, "code": self.code, "message": self.message}
