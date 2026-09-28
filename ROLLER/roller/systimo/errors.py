"""Systimo fail-closed errors. Missing is UNAVAILABLE, never $0."""

from __future__ import annotations


class SystimoError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        self.code = str(code)
        self.message = str(message)
        self.status_code = int(status_code)
        super().__init__(f"{self.code}: {self.message}")

    def as_dict(self) -> dict[str, str]:
        return {"status": self.code, "code": self.code, "message": self.message}
