"""Vital Phase 3 — MLB 001 fingerprints. No crate move."""

from __future__ import annotations

from pathlib import Path

from roller.vital.fingerprints import build_fingerprints, record_ownership
from roller.vital.store import events_path, fingerprints_path, list_events, seed_mlb_001
from roller.vital.versions import BOT_ID, ENGINE_POINTER, STRATEGY_POINTER


def test_fingerprints_record_pointers_not_copies(tmp_path):
    seed_mlb_001(root=tmp_path)
    prints = record_ownership(root=tmp_path)
    assert prints["moved"] is False
    paths = {row["path"] for row in prints["targets"]}
    assert ENGINE_POINTER in paths
    assert STRATEGY_POINTER in paths
    assert "config/live.toml" in paths
    assert "deploy/momento-live.service" in paths
    assert all(row["exists"] for row in prints["targets"])
    repo = Path(__file__).resolve().parents[2]
    assert (repo / ENGINE_POINTER).is_dir()
    assert (repo / STRATEGY_POINTER).is_dir()
    assert not (tmp_path / "bots" / BOT_ID / "source" / "apps").exists()


def test_fingerprints_stable_across_reread(tmp_path):
    seed_mlb_001(root=tmp_path)
    first = record_ownership(root=tmp_path)
    second = build_fingerprints()
    assert first["targets"] == second["targets"]
    on_disk = fingerprints_path(BOT_ID, root=tmp_path)
    assert on_disk.is_file()


def test_events_are_append_only(tmp_path):
    seed_mlb_001(root=tmp_path)
    record_ownership(root=tmp_path)
    kinds = [row.get("kind") for row in list_events(BOT_ID, root=tmp_path)]
    assert "seeded" in kinds
    assert "fingerprint_recorded" in kinds
    path = events_path(BOT_ID, root=tmp_path)
    before = path.read_text(encoding="utf-8")
    record_ownership(root=tmp_path)
    after = path.read_text(encoding="utf-8")
    assert after.startswith(before) or before in after


def test_bot_json_has_no_secret_material(tmp_path):
    from roller.vital.store import metadata_path

    seed_mlb_001(root=tmp_path)
    record_ownership(root=tmp_path)
    text = metadata_path(BOT_ID, root=tmp_path).read_text(encoding="utf-8")
    for token in ("KALSHI_API_KEY", "PRIVATE_KEY", "momento/kalshi/production", "api_key="):
        assert token not in text
    identity = (tmp_path / "bots" / BOT_ID / "config" / "identity.json").read_text(encoding="utf-8")
    assert "ENABLE_LIVE_TRADING" in identity
    assert "secret" not in identity.lower() or "secret_fetch" in identity
