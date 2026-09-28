"""Trajectory Γ_t is backward-only. Lookahead is false."""

from __future__ import annotations

import json
from pathlib import Path

from roller.state.trajectory import trajectory_features


SRC = Path(__file__).resolve().parents[1]


def test_feature_registry_lookahead_false():
    body = json.loads((SRC / "meta" / "feature_registry.json").read_text())
    for fam in body["families"]:
        assert fam["lookahead"] is False


def test_trajectory_ignores_future_events():
    events = [
        {
            "available_at": "2025-12-20T20:00:00Z",
            "event_type": "shot",
            "home_score": 2,
            "away_score": 0,
            "score_differential_home": 2,
        },
        {
            "available_at": "2025-12-20T20:05:00Z",
            "event_type": "shot",
            "home_score": 4,
            "away_score": 3,
            "score_differential_home": 1,
        },
        {
            "available_at": "2025-12-20T20:10:00Z",
            "event_type": "shot",
            "home_score": 10,
            "away_score": 3,
            "score_differential_home": 7,
        },
    ]
    feat = trajectory_features(events, as_of="2025-12-20T20:06:00Z")
    assert feat["status"] == "REAL"
    assert feat["data"]["n_events"] == 2
    assert feat["data"]["score_margin"] == 1
    assert 7 not in feat["data"]["margin_path"]
