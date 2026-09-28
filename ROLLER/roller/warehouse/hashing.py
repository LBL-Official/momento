"""Dataset and file hashes. Fail closed; do not invent content hashes."""

from __future__ import annotations

import hashlib
from pathlib import Path

from roller.io_csv import sha256_file


def file_sha256(path: Path) -> str:
    return sha256_file(path)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def partition_fingerprint(paths: list[Path]) -> str:
    h = hashlib.sha256()
    for path in sorted(paths, key=lambda p: str(p)):
        h.update(path.name.encode("utf-8"))
        h.update(b"\0")
        if path.is_file():
            h.update(file_sha256(path).encode("ascii"))
        h.update(b"\n")
    return h.hexdigest()
