"""Auto Roller lock, missed-schedule, verify --fast. Does not change detectors."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from roller.auto_roller.history import list_runs
from roller.auto_roller.ingest import run_ingest
from roller.auto_roller.locking import job_lock
from roller.auto_roller.verify import run_verify
from roller.config import RollerConfig


def test_lock_blocks_second_holder(tmp_path: Path, monkeypatch):
    cfg = RollerConfig()
    monkeypatch.setattr(
        "roller.auto_roller.locking.lock_path",
        lambda cfg=None: tmp_path / "auto_roller.lock",
    )
    with job_lock(cfg):
        with pytest.raises(RuntimeError, match="lock held"):
            with job_lock(cfg):
                pass


def test_verify_fast_and_missed_schedule():
    rec = run_verify(semantic=False, checksums=False, missed_schedule=True)
    assert rec["job_type"] == "verify"
    assert rec["display"] == "AUTO ROLLER VERIFY"
    assert "MISSED_SCHEDULE" in rec["warnings"]
    assert rec["sentinels"] == []
    assert rec["status"] in {"COMPLETE", "FAILED"}
    assert rec["indexes"]
    assert any(c.get("leaf", "").startswith("NBA") for c in rec["indexes"])


def test_ingest_skip_indexes_records_history():
    rec = run_ingest(rebuild_indexes=False, missed_schedule=True)
    assert rec["job_type"] == "ingest"
    assert rec["display"] == "AUTO ROLLER INGEST"
    assert rec["status"] != "FAILED"
    assert "MISSED_SCHEDULE" in rec["warnings"]
    hist = list_runs(limit=5)
    assert any(h["run_id"] == rec["run_id"] for h in hist)
    report = Path(rec["report_path"])
    assert report.is_file()
    json.loads(report.read_text())


def test_planted_hash_mismatch_fails_without_mutating(tmp_path: Path):
    """Guardian: bad manifest hash → FAILED. Warehouse bytes stay put."""
    from roller.research_query.indexes.manifest import MANIFEST_NAME
    from roller.research_query.indexes.reader import IndexUnavailable, verify_index_checksums
    from roller.research_query.models import BASIS_TRADABLE

    payload = b"planted-index-bytes-do-not-change"
    bars = tmp_path / "bars.parquet"
    bars.write_bytes(payload)
    (tmp_path / MANIFEST_NAME).write_text(
        json.dumps(
            {
                "index_version": "rq_index_v1.0.0",
                "dataset_version": "planted",
                "code_version": "planted",
                "operation_semantics_version": "planted",
                "league": "NBA",
                "season": "2025-2026",
                "sport": "NBA",
                "built_at_utc": "2026-09-12T00:00:00Z",
                "git_sha": None,
                "source_paths": [],
                "files": {"bars.parquet": "0" * 64},
                "ticker_count": 0,
                "game_count": 0,
                "bar_rows": 0,
                "transition_rows": 0,
                "settlement_rows": 0,
                "coverage": {},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    nba_manifest = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "nba"
        / "2025_2026"
        / "derived"
        / "research_query"
        / "indexes"
        / "rq_index_v1.0.0"
        / "NBA"
        / "tradable"
        / "manifest.json"
    )
    before = nba_manifest.read_bytes() if nba_manifest.is_file() else None
    with pytest.raises(IndexUnavailable, match="checksum mismatch"):
        verify_index_checksums(tmp_path)
    rec = run_verify(
        semantic=False,
        checksums=True,
        leaves=(("NBA", "2025-2026", BASIS_TRADABLE),),
        root_for=lambda sport, season, basis: tmp_path,
    )
    assert rec["status"] == "FAILED"
    assert any("checksum mismatch" in str(c.get("reason")) for c in rec["indexes"])
    assert bars.read_bytes() == payload
    if before is not None:
        assert nba_manifest.read_bytes() == before
