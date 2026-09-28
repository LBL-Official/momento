from __future__ import annotations

from pathlib import Path

import pandas as pd

from roller.config import RollerConfig
from roller.state.observation_id import make_observation_id, parse_observation_id
from roller.timeutil import parse_utc
from roller.v4b.measurements import assemble_shared_xt
from tests.helpers_v4a import fake_observation
from tests.helpers_v4b import recording_fundamental_fn

SRC = Path(__file__).resolve().parents[1]


def test_f_prev_uses_previous_visible_candle_cutoff_not_current():
    cfg = RollerConfig(SRC)
    cutoff = "2025-12-20T20:15:00Z"
    obs = fake_observation(t=cutoff)
    obs["observation_id"] = make_observation_id("NBA_CUR", cutoff, cfg.state_schema_version)
    candles = pd.DataFrame(
        [
            {"available_at": "2025-12-20T20:13:00Z", "yes_bid_close": 7400, "team_side": "home"},
            {"available_at": "2025-12-20T20:14:00Z", "yes_bid_close": 7500, "team_side": "home"},
        ]
    )
    table = {
        "2025-12-20T20:15:00Z": {
            "status": "IMPLEMENTED",
            "probability_wins": 3,
            "probability_n": 4,
            "value": {"numerator": 3, "denominator": 4},
            "available_at": "2025-12-20T20:15:00Z",
            "information_cutoff": "2025-12-20T20:15:00Z",
        },
        "2025-12-20T20:13:00Z": {
            "status": "IMPLEMENTED",
            "probability_wins": 1,
            "probability_n": 2,
            "value": {"numerator": 1, "denominator": 2},
            "available_at": "2025-12-20T20:13:00Z",
            "information_cutoff": "2025-12-20T20:13:00Z",
        },
    }
    fn = recording_fundamental_fn(table)
    xt = assemble_shared_xt(cfg, observation=obs, candles=candles, fundamental_fn=fn)
    times = {parse_observation_id(oid)[1] for oid in fn.calls}
    assert parse_utc(cutoff) in times
    assert parse_utc("2025-12-20T20:13:00Z") in times
    assert parse_utc("2025-12-20T20:14:00Z") not in times or xt.previous.available_at == "2025-12-20T20:13:00Z"
    assert xt.f_t.wins == 3 and xt.f_t.n == 4
    assert xt.f_prev.wins == 1 and xt.f_prev.n == 2
    assert xt.f_t.cutoff != xt.f_prev.cutoff
    assert xt.f_prev.observation_id != xt.f_t.observation_id
    assert xt.f_prev.observation_id != obs["observation_id"]
