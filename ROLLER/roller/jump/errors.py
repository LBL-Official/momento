"""Jump errors. Research only. No order submission."""

from __future__ import annotations

from typing import Any


class JumpError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")

    def as_dict(self) -> dict[str, Any]:
        return {"status": self.code, "code": self.code, "message": self.message}
