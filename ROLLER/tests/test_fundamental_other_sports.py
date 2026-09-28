"""WNBA / NCAAB F_t use the same estimator. Never invent 0.50."""

from __future__ import annotations

from pathlib import Path

from roller.config import RollerConfig
from roller.fundamental.estimator import estimate_fundamental
from tests.helpers_v4a import fake_observation, stamped_row


SRC = Path(__file__).resolve().parents[1]


def test_wnba_and_ncaab_are_not_hard_gated():
    cfg = RollerConfig(SRC)
    for sport in ("WNBA", "NCAAB"):
        obs = fake_observation(sport=sport, gid=f"{sport}_CUR")
        prior = stamped_row(
            cfg,
            gid="G1",
            state_at="2025-12-10T20:00:00Z",
            result_at="2025-12-10T22:00:00Z",
            home_win="1",
        )
        prior["sport"] = sport
        out = estimate_fundamental(cfg, observation=obs, corpus=[prior])
        assert out["status"] != "NOT_SUPPORTED"
        assert out["value"] is None
        assert out["status"] == "INSUFFICIENT_SUPPORT"
