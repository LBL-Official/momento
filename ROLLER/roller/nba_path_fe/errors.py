"""Fail-closed errors. Missing is never an economic 0."""

from __future__ import annotations


class PathFeError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = str(code)
        super().__init__(f"{self.code}: {message}")
