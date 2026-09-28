"""As-of join: latest game state with event time <= candle end_period_ts.

Never uses a future event. Never synthesizes missing candles.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pandas as pd

from terminal_efficiency.clocks import parse_utc, to_iso
from terminal_efficiency.paths import warehouse
from terminal_efficiency.provenance import data_gap


def _iter_raw_candles(league: str, season: str):
    sport = "nba" if league.upper() == "NBA" else "ncaab"
    root = warehouse(league, season) / "raw" / "kalshi" / sport / "candlesticks"
    if not root.exists():
        return
    for d in sorted(root.iterdir()):
        if not d.is_dir():
            continue
        f = d / "candles.jsonl.gz"
        if not f.exists():
            continue
        ticker = d.name.replace("ticker=", "")
        with gzip.open(f, "rt") as fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                row["_ticker"] = ticker
                yield row


def load_raw_candles_frame(league: str, season: str, *, max_rows: int | None = None) -> pd.DataFrame:
    rows = []
    for i, c in enumerate(_iter_raw_candles(league, season)):
        sticks = []
        if isinstance(c.get("payload"), dict) and c["payload"].get("candlesticks"):
            sticks = c["payload"]["candlesticks"]
        elif c.get("end_period_ts") is not None:
            sticks = [c]
        elif isinstance(c.get("candlesticks"), list):
            sticks = c["candlesticks"]
        ticker = c.get("ticker") or c.get("_ticker")
        for bar in sticks:
            end_ts = bar.get("end_period_ts")
            if end_ts is None:
                continue
            yes = bar.get("yes_bid") if isinstance(bar.get("yes_bid"), dict) else {}
            rows.append(
                {
                    "ticker": ticker,
                    "end_period_ts": int(end_ts),
                    "market_timestamp": to_iso(pd.Timestamp(int(end_ts), unit="s", tz="UTC").to_pydatetime()),
                    "yes_bid_close": yes.get("close_dollars") or yes.get("close"),
                }
            )
        if max_rows is not None and len(rows) >= max_rows:
            break
    return pd.DataFrame(rows)


def align_states_to_candles(
    observations: pd.DataFrame,
    candles: pd.DataFrame,
    *,
    game_id_from_ticker,
) -> tuple[pd.DataFrame, dict]:
    """game_id_from_ticker(ticker) -> game_id or None."""
    if candles.empty:
        return pd.DataFrame(), {
            "status": "DATA_GAP",
            "data_gap": data_gap(
                source="Kalshi candlesticks",
                required_field="end_period_ts",
                why="no candles loaded",
                future_source="warehouse download-all",
                impact="Dataset C empty; training unaffected",
            ),
            "total_candles": 0,
            "aligned": 0,
            "unaligned": 0,
            "ambiguous": 0,
            "modeled": 0,
        }

    obs = observations.copy()
    obs["_event_ts"] = obs["game_event_timestamp"].map(parse_utc)
    by_game = {gid: g.sort_values("game_event_timestamp") for gid, g in obs.groupby("game_id")}

    aligned_rows = []
    unaligned = 0
    ambiguous = 0
    modeled = 0
    for c in candles.to_dict("records"):
        gid = game_id_from_ticker(c.get("ticker") or "")
        if not gid or gid not in by_game:
            unaligned += 1
            continue
        mkt = parse_utc(c.get("market_timestamp"))
        if mkt is None:
            unaligned += 1
            continue
        g = by_game[gid]
        times = g["_event_ts"]
        eligible = g[times.notna() & (times <= mkt)]
        if eligible.empty:
            unaligned += 1
            continue
        last = eligible.iloc[-1].to_dict()
        last["market_timestamp"] = c.get("market_timestamp")
        last["market_id"] = c.get("ticker")
        last["kalshi_yes_price_raw"] = c.get("yes_bid_close")  # stored for residual research, not a feature
        last["alignment_status"] = "ALIGNED"
        tq = str(last.get("timestamp_quality") or "")
        if tq == "MODELED":
            last["alignment_quality"] = "MODELED"
            last["alignment_status"] = "ALIGNED_MODELED"
            modeled += 1
        elif tq == "OBSERVED":
            last["alignment_quality"] = "OBSERVED"
        else:
            last["alignment_quality"] = "AMBIGUOUS"
            ambiguous += 1
        aligned_rows.append(last)

    coverage = {
        "status": "PARTIAL" if aligned_rows else "MISSING",
        "total_candles": int(len(candles)),
        "aligned": int(len(aligned_rows)),
        "unaligned": int(unaligned),
        "ambiguous": int(ambiguous),
        "modeled": int(modeled),
    }
    return pd.DataFrame(aligned_rows), coverage


def nba_ticker_to_guess_date_teams(ticker: str) -> tuple[str, str, str] | None:
    """KXNBAGAME-25APR20MIACLE-CLE → (2025-04-20, MIA, CLE) best-effort parse. Not a silent match."""
    # ticker may be event-team; we only parse tokens, caller must confirm against games
    core = ticker.replace("KXNBAGAME-", "").split("-")[0]
    # 25APR20MIACLE
    if len(core) < 9:
        return None
    return None  # require explicit crosswalk; do not guess
