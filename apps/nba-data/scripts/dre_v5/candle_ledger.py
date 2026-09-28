"""Workstream 1b — post-entry 1-minute candle ledger with anti-lookahead PBP join."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from . import config as C


def _asof_idx(ts_sorted: np.ndarray, t: float) -> int:
    """Largest index with ts_sorted[i] <= t, or -1."""
    if len(ts_sorted) == 0:
        return -1
    i = int(np.searchsorted(ts_sorted, t, side="right") - 1)
    return i


def _load_quotes(ticker: str) -> list[dict]:
    path = C.CANDLES_DIR / f"{ticker}.parquet"
    if not path.exists():
        hits = list(C.CANDLES_DIR.rglob(f"{ticker}.parquet"))
        if not hits:
            return []
        path = hits[0]
    cols = [
        "end_period_ts",
        "yes_bid_open_e4",
        "yes_bid_high_e4",
        "yes_bid_low_e4",
        "yes_bid_close_e4",
        "yes_ask_close_e4",
        "is_valid",
    ]
    table = pq.read_table(path, columns=cols)
    get = {c: table.column(c) for c in cols}
    rows = []
    for i in range(table.num_rows):
        if not get["is_valid"][i].as_py():
            continue
        ts = get["end_period_ts"][i].as_py()
        if ts is None:
            continue
        rows.append(
            {
                "ts": int(ts),
                "bid_o": get["yes_bid_open_e4"][i].as_py(),
                "bid_h": get["yes_bid_high_e4"][i].as_py(),
                "bid_l": get["yes_bid_low_e4"][i].as_py(),
                "bid_c": get["yes_bid_close_e4"][i].as_py(),
                "ask_c": get["yes_ask_close_e4"][i].as_py(),
            }
        )
    rows.sort(key=lambda r: r["ts"])
    return rows


def _poss_index(poss: pd.DataFrame) -> dict[str, tuple[np.ndarray, pd.DataFrame]]:
    out = {}
    if poss.empty:
        return out
    for gid, g in poss.groupby("nba_game_id", sort=False):
        g = g.sort_values("wall_start_ts")
        ts = pd.to_numeric(g["wall_start_ts"], errors="coerce").to_numpy(float)
        out[str(gid)] = (ts, g.reset_index(drop=True))
    return out


def build_candle_ledger(trades: list[dict], poss: pd.DataFrame, priors: pd.DataFrame | None) -> pd.DataFrame:
    """One row per in-game post-entry A1 candle. Latest PBP wall_start_ts <= candle ts."""
    pidx = _poss_index(poss)
    rx_map = {}
    if priors is not None and len(priors):
        rx_map = {str(r["nba_game_id"]): r for r in priors.to_dict("records")}

    out_rows = []
    missing_candles = 0
    for t in trades:
        tid = t["ticker"]
        gid = t.get("nba_game_id")
        entry = t.get("first_80_timestamp")
        if entry is None:
            continue
        entry = float(entry)
        quotes = _load_quotes(tid)
        a2q = _load_quotes(t["opponent_ticker"]) if t.get("opponent_ticker") else []
        a2_ts = np.array([q["ts"] for q in a2q], dtype=float) if a2q else np.array([], dtype=float)
        if not quotes:
            missing_candles += 1
            continue
        end_ts = None
        if gid and str(gid) in pidx:
            walls = pidx[str(gid)][0]
            if len(walls) and np.isfinite(walls).any():
                end_ts = float(np.nanmax(walls))
        prior = rx_map.get(str(gid)) if gid else None
        rx = None if prior is None else prior.get("r_x_prior")

        for q in quotes:
            ts = float(q["ts"])
            if ts + 1e-9 < entry:
                continue
            if end_ts is not None and ts > end_ts + 60:
                continue
            a1 = C.e4_to_cents(q["bid_c"])
            a1_o = C.e4_to_cents(q["bid_o"])
            a1_h = C.e4_to_cents(q["bid_h"])
            a1_l = C.e4_to_cents(q["bid_l"])
            a1_ask = C.e4_to_cents(q["ask_c"])
            a2 = None
            if len(a2_ts):
                j = _asof_idx(a2_ts, ts)
                if j >= 0:
                    a2 = C.e4_to_cents(a2q[j]["bid_c"])
            pbp = None
            if gid and str(gid) in pidx:
                ts_arr, g = pidx[str(gid)]
                k = _asof_idx(ts_arr, ts)
                if k >= 0:
                    pbp = g.iloc[k]
            pidx_n = None if pbp is None else pbp.get("possession_index")
            n_hat = None
            if rx is not None and pidx_n is not None and pd.notna(pidx_n):
                n_hat = max(0.0, float(rx) - float(pidx_n))
            out_rows.append(
                {
                    "trade_id": tid,
                    "event_id": t.get("event_id"),
                    "nba_game_id": gid,
                    "dataset_split": t.get("dataset_split"),
                    "candle_ts": ts,
                    "minutes_since_entry": (ts - entry) / 60.0,
                    "A1_yes_bid_cents": a1,
                    "A1_yes_open_cents": a1_o,
                    "A1_yes_high_cents": a1_h,
                    "A1_yes_low_cents": a1_l,
                    "A1_yes_ask_cents": a1_ask,
                    "A2_yes_bid_cents": a2,
                    "current_price_cents": a1,
                    "V_mtm_cents": None if a1 is None else C.CONTRACTS_RESEARCH * float(a1),
                    "V_mtm_formula": "100 * P_A1_cents",
                    "delta_inv": C.DELTA_INV,
                    "possession_index": None if pbp is None else pbp.get("possession_index"),
                    "period": None if pbp is None else pbp.get("period"),
                    "game_clock": None if pbp is None else pbp.get("game_clock_start"),
                    "elapsed_game_seconds": None if pbp is None else pbp.get("elapsed_game_seconds_start"),
                    "game_seconds_remaining": None if pbp is None else pbp.get("game_seconds_remaining_start"),
                    "offensive_team": None if pbp is None else pbp.get("offensive_team"),
                    "score_home": None if pbp is None else pbp.get("score_home_start"),
                    "score_away": None if pbp is None else pbp.get("score_away_start"),
                    "pbp_wall_start_ts": None if pbp is None else pbp.get("wall_start_ts"),
                    "n_hat_remaining_prior": n_hat,
                    "join_rule": "latest_possession_wall_start_ts_le_candle_end_period_ts",
                    "fill_status": "CANDLE_PATH_PROXY_NOT_PROVEN_FILL",
                    "disclaimer": "OBSERVED CANDLE PATH — NOT FILL HISTORY",
                }
            )
    df = pd.DataFrame(out_rows)
    df.attrs["missing_candle_tickers"] = missing_candles
    return df
