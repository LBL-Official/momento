"""78/67 Austin fit stays off the 604 artifact tree."""

from __future__ import annotations

import hashlib
from pathlib import Path

from roller.austin.paths import repo_root
from roller.austin.raw_state import RawState
from roller.austin_first78.config import CFG, distance_from_78
from roller.austin_first78.query import public_mode, query_from_body

MANIFEST_SHA256 = "432b014fd672f41791ef595536c6dcd7d96332c9283e4cd9a73885a07b62bd38"
SUMMARY_SHA256 = "63a6a18072925a90c076584fbb80efc951fd6eae6a1b764e06273e61470f545c"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_distance_from_78_is_entry_minus_78():
    assert distance_from_78(78) == 0
    assert distance_from_78(80) == 2
    assert distance_from_78(None) is None
    assert "distance_from_78" in CFG.default_knn
    assert "distance_from_80" not in CFG.default_knn
    assert CFG.entry_cents == 78
    assert CFG.stop_cents == 67
    assert CFG.dataset_version != "choosin_nba_2q3q_604"


def test_pre_78_has_no_entry_for_the_knn():
    raw = query_from_body({"side": "home", "query_mode": "PRE_78", "current_price_cents": 70})
    assert isinstance(raw, RawState)
    assert raw.query_mode == "PRE_80"
    assert raw.entry_price_cents is None
    assert public_mode(raw.query_mode) == "PRE_78"


def test_604_manifest_and_summary_are_unchanged():
    root = repo_root()
    manifest = root / "research/austin/experiments/_model/MODEL_MANIFEST.json"
    summary = root / "research/austin/artifacts/summary.json"
    assert _sha(manifest) == MANIFEST_SHA256
    assert _sha(summary) == SUMMARY_SHA256
