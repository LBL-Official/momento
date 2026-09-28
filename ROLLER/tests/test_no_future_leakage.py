from __future__ import annotations

from pathlib import Path

from roller import Roller
from roller.admin import load_dataset
from roller.canonical.align import align_candles_to_pbp, assert_no_future_pbp
from roller.config import RollerConfig
from roller.maintenance.update import update_sport
from roller.validation.leakage import correct_wins_pre, leaky_wins_pre, synthetic_leak_example


def test_synthetic_sequence():
    spec = synthetic_leak_example()
    results = [r == "W" for r in spec["sequence"]]
    assert correct_wins_pre(results)[2] == spec["before_game_3"]["wins_pre"]
    assert leaky_wins_pre(results)[2] == spec["leaky_before_game_3"]["wins_pre"]
    assert leaky_wins_pre(results)[2] != correct_wins_pre(results)[2]


def test_alignment_backward_only(roller_env: Path):
    cfg = RollerConfig(roller_env)
    update_sport(cfg, "NBA", "2025-2026", include_pbp=True, include_candles=True)
    pbp = load_dataset(cfg, "NBA", "2025-2026", "pbp")
    candles = load_dataset(cfg, "NBA", "2025-2026", "kalshi_candles")
    g3_pbp = pbp[pbp["internal_game_id"] == "NBA_20251220_LAL_BOS"]
    g3_c = candles[candles["internal_game_id"] == "NBA_20251220_LAL_BOS"]
    aligned = align_candles_to_pbp(g3_c, g3_pbp)
    assert aligned is not None
    errs = assert_no_future_pbp(aligned)
    assert errs == []
    first = aligned.sort_values("available_at").iloc[0]
    assert str(first.get("home_score")) == "10"
    assert str(first.get("away_score")) == "8"


def test_future_pbp_and_candles_hidden(roller_env: Path):
    cfg = RollerConfig(roller_env)
    update_sport(cfg, "NBA", "2025-2026", include_pbp=True, include_candles=True)
    db = Roller(roller_env)
    st = db.game_state("NBA_20251220_LAL_BOS", as_of="2025-12-20T20:13:30Z")
    assert str(st["score"]["home"]) == "10"
    assert str(st["period"]) == "3"
    later = db.game_state("NBA_20251220_LAL_BOS", as_of="2025-12-20T20:14:30Z")
    assert str(later["score"]["home"]) == "12"
    early = db.dataset("NBA", "2025-2026", "kalshi_candles", as_of="2025-12-20T20:13:00Z")
    g3 = early[early["internal_game_id"] == "NBA_20251220_LAL_BOS"] if not early.empty else early
    assert g3.empty
