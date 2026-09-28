"""Assemble T_i at ENTRY_DECISION_TIME. Causal: possessions with wall_start ≤ entry only."""

from __future__ import annotations

from feature_store.game_dynamics import game_dynamics_features
from feature_store.game_market_coupling import coupling_features
from feature_store.game_state import game_state_at_possession
from feature_store.market_path import market_path_features
from feature_store.market_state import market_state_features
from feature_store.possession_path import possession_path_features


def assemble_trade_state(
    obs: dict,
    snap: dict,
    pre_poss: list[dict],
    overlay_row: dict | None,
    pre_overlays: list[dict],
) -> dict:
    last = pre_poss[-1] if pre_poss else None
    gs = game_state_at_possession(
        last,
        team_code=obs.get("team_code"),
        n_poss_pre=len(pre_poss),
        total_poss_est=None,
    )
    pp = possession_path_features(pre_poss, obs.get("team_code"))
    gd = game_dynamics_features(pre_poss)
    ms = market_state_features(obs, overlay_row)
    mp = market_path_features(pre_overlays)
    cp = coupling_features(pre_poss, pre_overlays)
    rec = {
        "observation_id": obs["observation_id"],
        "event_id": obs["event_id"],
        "ticker": obs["ticker"],
        "team_code": obs.get("team_code"),
        "game_date": obs.get("game_date"),
        "dataset_split": obs["dataset_split"],
        "entry_decision_time": obs["entry_decision_time"],
        "Y_40_CLOSE": obs["Y_40_CLOSE"],
        "SURVIVE_40": obs["SURVIVE_40"],
        "Y_40_WICK": obs.get("Y_40_WICK"),
        "expiration_result_yes": obs.get("expiration_result_yes"),
        "alignment_confidence": snap.get("alignment_confidence"),
        "alignment_reason": snap.get("alignment_reason"),
        "game_phase": snap.get("game_phase"),
        "possession_id": snap.get("possession_id"),
        "maker_fill_confidence": obs.get("maker_fill_confidence"),
        "time_to_40_minutes": None
        if not obs.get("first_40_close_ts")
        else (obs["first_40_close_ts"] - obs["entry_decision_time"]) / 60.0,
        "primary_set": snap.get("alignment_confidence") in ("HIGH", "MEDIUM"),
    }
    rec.update(gs)
    rec.update(pp)
    rec.update(gd)
    rec.update(ms)
    rec.update(mp)
    rec.update(cp)
    rec["z_uses_future_possession"] = False
    rec["l2_invented"] = False
    rec["wall_clock_claimed_observed"] = False
    return rec
