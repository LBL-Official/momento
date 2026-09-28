from __future__ import annotations

from pathlib import Path

from roller.config import RollerConfig
from roller.v4b.baseline import compute_baseline, measurement_eligible
from tests.helpers_v4b import corpus_row

SRC = Path(__file__).resolve().parents[1]


def _cfg() -> RollerConfig:
    return RollerConfig(SRC)


def test_baseline_mean_is_exact_rational_and_excludes_current_game():
    cfg = _cfg()
    cid = "C_CORE"
    corpus = [
        corpus_row(name="market_delta_1m", gid="G1", available_at="2025-12-19T20:00:00Z", numerator=100, denominator=1, condition_id=cid),
        corpus_row(name="market_delta_1m", gid="G2", available_at="2025-12-18T20:00:00Z", numerator=200, denominator=1, condition_id=cid),
        corpus_row(name="market_delta_1m", gid="G3", available_at="2025-12-17T20:00:00Z", numerator=300, denominator=1, condition_id=cid),
        corpus_row(name="market_delta_1m", gid="CUR", available_at="2025-12-16T20:00:00Z", numerator=9999, denominator=1, condition_id=cid),
    ]
    base = compute_baseline(
        cfg,
        measurement_name="market_delta_1m",
        target_game="CUR",
        target_cutoff="2025-12-20T20:15:00Z",
        condition_id=cid,
        corpus=corpus,
    )
    assert base["status"] == "valid"
    assert base["expected"] == {"numerator": 200, "denominator": 1, "units": "e4"}
    assert base["dispersion"]["kind"] == "mean_absolute_deviation"
    # |100-200| + |200-200| + |300-200| = 200 / 3
    assert base["dispersion"]["numerator"] == 200
    assert base["dispersion"]["denominator"] == 3
    assert base["support"]["effective_n"] is None
    assert base["support"]["n_unique_games"] == 3


def test_baseline_half_open_and_core_v1_only():
    row = {
        "internal_game_id": "G1",
        "measurement_available_at": "2025-12-20T10:05:00Z",
        "condition_id": "C_CORE",
    }
    assert not measurement_eligible(row, target_cutoff="2025-12-20T10:05:00Z", target_game="CUR", condition_id="C_CORE")
    assert measurement_eligible(row, target_cutoff="2025-12-20T10:06:00Z", target_game="CUR", condition_id="C_CORE")
    assert not measurement_eligible(row, target_cutoff="2025-12-20T10:06:00Z", target_game="CUR", condition_id="C_OTHER")


def test_baseline_insufficient_is_null_not_zero():
    cfg = _cfg()
    base = compute_baseline(
        cfg,
        measurement_name="market_delta_1m",
        target_game="CUR",
        target_cutoff="2025-12-20T20:15:00Z",
        condition_id="C_CORE",
        corpus=[
            corpus_row(name="market_delta_1m", gid="G1", available_at="2025-12-19T20:00:00Z", numerator=10, denominator=1, condition_id="C_CORE"),
        ],
    )
    assert base["status"] == "INSUFFICIENT_SUPPORT"
    assert base["expected"] is None
