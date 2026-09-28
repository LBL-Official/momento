"""SuperASI API surface. No credentials."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from roller.superasi import api as sapi


def test_handlers_exist():
    assert callable(sapi.handle_import)
    assert callable(sapi.handle_list)
    assert callable(sapi.handle_get)
    assert callable(sapi.handle_decompose)
    assert callable(sapi.handle_seed)


def test_no_new_credential_paths():
    root = Path(__file__).resolve().parents[1] / "roller" / "superasi"
    banned = ("KALSHI_API_KEY", "PRIVATE_KEY", "secret_key", "api_key=")
    for path in root.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token in banned:
            assert token not in text, f"{path} contains {token}"


def test_health_lists_superasi():
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import terminal_api

    client = TestClient(terminal_api.app)
    body = client.get("/health").json()
    assert "superasi_import" in body["capabilities"]
    assert "superasi_library" in body["capabilities"]
    assert "superasi_decompose" in body["capabilities"]
    assert "superasi_seed_asked_six" in body["capabilities"]


def test_list_and_get_isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERASI_LIBRARY_ROOT", str(tmp_path))
    assert sapi.handle_list()["n"] == 0
    with pytest.raises(Exception) as ei:
        sapi.handle_get("missing")
    assert getattr(ei.value, "code", None) == "PACKAGE_SCHEMA_INVALID"
