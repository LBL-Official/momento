"""SuperASI ITI home. Jump /jump/iti/* remains an alias. Not a live signal."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

from roller.superasi.iti.catalog import SLOT_SPEC
from roller.superasi.iti.versions import ITI_HOME, SLOT_COUNT


def test_catalog_still_25():
    assert SLOT_COUNT == 25
    assert len(SLOT_SPEC) == 25
    assert ITI_HOME == "superasi"


def test_superasi_and_jump_iti_routes_exist():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import terminal_api

    client = TestClient(terminal_api.app)
    caps = client.get("/health").json()["capabilities"]
    assert "superasi_iti" in caps
    empty = client.get("/superasi/iti").json()
    alias = client.get("/jump/iti").json()
    assert "results" in empty
    assert "results" in alias
