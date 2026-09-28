"""Fail-closed Austin errors. Missing is never an economic 0."""

from __future__ import annotations


class AustinError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = str(code)
        self.message = str(message)
        super().__init__(f"{self.code}: {self.message}")

    def as_dict(self) -> dict[str, str]:
        return {"status": self.code, "code": self.code, "message": self.message}
