"""Gate 2: fundamental registry flags and versioning."""

from __future__ import annotations

from pathlib import Path

from roller.config import RollerConfig
from roller.fundamental.registry import REQUIRED_FIELDS, get_fundamental, load_fundamental_registry


SRC = Path(__file__).resolve().parents[1]


def test_registry_prior_only_empirical_definition():
    cfg = RollerConfig(SRC)
    body = load_fundamental_registry(cfg)
    row = get_fundamental(cfg, "fundamental_win_probability_empirical_v1")
    assert body["schema_version"] == "4.0.0-A"
    assert cfg.fundamental_schema_version == "4.0.0-A"
    assert "true probability" not in row["definition"].lower()
    assert "prior-only" in row["definition"].lower()
    assert "empirical" in row["definition"].lower()
    assert "state-conditioned" in row["definition"].lower()
    assert "terminal win probability" in row["definition"].lower()
    assert row["information_regime"] == "prior_only"
    assert row["contains_future_information"] is True
    assert row["conditioning_schema_version"] == "core_v1"
    for field in REQUIRED_FIELDS:
        assert field in row
    cond = cfg.fundamental_conditioning
    assert cond["default_schema"] == "core_v1"
    names = [d["name"] for d in cond["schemas"]["core_v1"]["dimensions"]]
    assert names == ["period", "clock_bucket", "score_margin_bucket"]
    assert "market_probability" in cond["optional_dimensions_not_in_default"]
    assert cond["support"]["minimum_unique_seasons"] == 1
    assert cond["support"]["effective_n_status"] == "NOT_IMPLEMENTED"
