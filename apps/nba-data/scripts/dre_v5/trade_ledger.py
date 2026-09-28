"""Workstream 1a — 1230 × buy@80 × Q=100 trade cards."""

from __future__ import annotations

import pandas as pd

from . import config as C
from .frozen_universe import unresolved as load_unresolved


def build_trade_ledger(trades: list[dict], panel: pd.DataFrame) -> pd.DataFrame:
    unr = load_unresolved()
    unr_tickers = {r.get("ticker") for r in (unr.get("unresolved") or []) if r.get("ticker")}
    first = (
        panel.sort_values(["trade_id", "possession_index"])
        .groupby("trade_id", as_index=False)
        .first()
        if len(panel)
        else pd.DataFrame()
    )
    first_map = {r["trade_id"]: r for r in first.to_dict("records")} if len(first) else {}

    rows = []
    for t in trades:
        tid = t["ticker"]
        p0 = first_map.get(tid)
        y = t.get("expiration_result_yes")
        unresolved = tid in unr_tickers or p0 is None
        rows.append(
            {
                "trade_id": tid,
                "event_id": t.get("event_id"),
                "market_ticker": tid,
                "opponent_ticker": t.get("opponent_ticker"),
                "nba_game_id": t.get("nba_game_id") if t.get("nba_game_id") else (None if p0 is None else p0.get("nba_game_id")),
                "dataset_split": t.get("dataset_split"),
                "game_date": t.get("game_date"),
                "first_80_timestamp": t.get("first_80_timestamp"),
                "A1_team": t.get("a1_team"),
                "A2_team": t.get("a2_team"),
                "home_team": t.get("home_team"),
                "away_team": t.get("away_team"),
                "entry_price_cents": C.ENTRY_PRICE_CENTS,
                "contracts_research": C.CONTRACTS_RESEARCH,
                "V_mtm_entry_cents": C.V_MTM_ENTRY_CENTS,
                "delta_inv": C.DELTA_INV,
                "fill_status": "CANDLE_PATH_PROXY_NOT_PROVEN_FILL",
                "disclaimer": "OBSERVED CANDLE PATH — NOT FILL HISTORY",
                "unresolved": bool(unresolved),
                "y_settle_yes": None if y is None else int(bool(y)),
                "pi_terminal": None if y is None else (100 * int(bool(y)) - 80),
                "stopped_candle_path": bool(t.get("stop_close_triggered")),
                "first_possession_index": None if p0 is None else p0.get("possession_index"),
                "first_possessions_since_entry": None if p0 is None else p0.get("possessions_since_entry"),
                "first_score_differential_from_A1": None if p0 is None else p0.get("score_differential_from_A1"),
                "first_elapsed_game_seconds": None if p0 is None else p0.get("elapsed_game_seconds"),
                "first_game_seconds_remaining": None if p0 is None else p0.get("game_seconds_remaining"),
                "first_game_clock": None if p0 is None else p0.get("game_clock"),
                "first_A1_yes_bid_cents": None if p0 is None else p0.get("A1_yes_bid"),
                "first_A2_yes_bid_cents": None if p0 is None else p0.get("A2_yes_bid"),
                "V_mtm_formula": "100 * P_A1_cents",
                "first_market_observation_timestamp": None if p0 is None else p0.get("market_observation_timestamp"),
                "first_alignment_confidence": None if p0 is None else p0.get("alignment_confidence"),
                "panel_matched": p0 is not None,
            }
        )
    df = pd.DataFrame(rows)
    if len(df) != C.UNIVERSE_N:
        raise RuntimeError(f"trade ledger {len(df)} != {C.UNIVERSE_N}")
    return df
