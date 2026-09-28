"""Candle quote load and first-reach using the frozen audit quality rule.

Does not change FIRST80. Reconstructs first-reach at other thresholds with the
same tradable-cross rule. HALT if reconstructed FIRST80 disagrees with frozen candidates.
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

NBA_SCRIPTS = Path("/Users/user/Desktop/Momento/apps/nba-data/scripts")
if str(NBA_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(NBA_SCRIPTS))
import nba_80_40_execution_audit as A  # noqa: E402
import pyarrow.parquet as pq

import config as C


def load_quotes() -> dict[str, list[dict]]:
    """Same windowed 1-minute yes_bid load as the frozen audit scan()."""
    markets = A.load_markets()
    games = A.load_games()
    games_by_event = {g["event_id"]: g for g in games}
    meta = {}
    for m in markets:
        g = games_by_event.get(m["event_id"], {})
        start = g.get("game_window_start")
        end = m["close_ts"]
        gw_end = g.get("game_window_end")
        if end is None:
            end = gw_end
        elif gw_end is not None:
            end = min(end, gw_end)
        meta[m["ticker"]] = (start, end, m["close_ts"], m)
    files = sorted(C.CANDLES.rglob("*.parquet"))
    quotes: dict[str, list] = defaultdict(list)
    cols = [
        "ticker",
        "end_period_ts",
        "yes_bid_open_e4",
        "yes_bid_high_e4",
        "yes_bid_low_e4",
        "yes_bid_close_e4",
        "yes_ask_close_e4",
        "volume_hundredths",
        "is_valid",
    ]
    C.log(f"loading {len(files)} candle files")
    for path in files:
        table = pq.read_table(path, columns=cols)
        get = {c: table.column(c) for c in cols}
        n = table.num_rows
        for i in range(n):
            if not get["is_valid"][i].as_py():
                continue
            ticker = get["ticker"][i].as_py()
            t = int(get["end_period_ts"][i].as_py())
            start, end, _, _ = meta.get(ticker, (None, None, None, None))
            if start is not None and t < start:
                continue
            if end is not None and t > end:
                continue
            quotes[ticker].append(
                {
                    "ts": t,
                    "bid_c": A._opt_int(get["yes_bid_close_e4"][i].as_py()),
                    "bid_h": A._opt_int(get["yes_bid_high_e4"][i].as_py()),
                    "bid_l": A._opt_int(get["yes_bid_low_e4"][i].as_py()),
                    "ask_c": A._opt_int(get["yes_ask_close_e4"][i].as_py()),
                    "vol": A._opt_int(get["volume_hundredths"][i].as_py()),
                }
            )
    for ticker, rows in quotes.items():
        rows.sort(key=lambda r: r["ts"])
    return dict(quotes), markets, games, meta


def first_tradable_reach(rows: list[dict], hit_e4: int):
    """Frozen audit rule, parameterized by threshold."""
    had_q = False
    seen_below = False
    for q in rows:
        if not A.quality(q["bid_c"], q["ask_c"], q["vol"], had_q):
            continue
        had_q = True
        if q["bid_c"] < hit_e4:
            seen_below = True
        if seen_below and q["bid_c"] >= hit_e4:
            return q
    return None


def first_close_le_after(rows: list[dict], tau: int, hit_e4: int = C.HIT40_E4):
    for q in rows:
        if q["ts"] <= tau:
            continue
        if not A.quality(q["bid_c"], q["ask_c"], q["vol"], True):
            continue
        if q["bid_c"] is not None and q["bid_c"] <= hit_e4:
            return q
    return None


def min_close_after(rows: list[dict], tau: int) -> int | None:
    vals = []
    for q in rows:
        if q["ts"] <= tau:
            continue
        if not A.quality(q["bid_c"], q["ask_c"], q["vol"], True):
            continue
        if q["bid_c"] is not None:
            vals.append(q["bid_c"])
    return None if not vals else int(min(vals))


def max_close_after(rows: list[dict], tau: int) -> int | None:
    vals = []
    for q in rows:
        if q["ts"] <= tau:
            continue
        if not A.quality(q["bid_c"], q["ask_c"], q["vol"], True):
            continue
        if q["bid_c"] is not None:
            vals.append(q["bid_c"])
    return None if not vals else int(max(vals))


def first_team_at_threshold(markets, games, quotes, hit_e4: int) -> pd.DataFrame:
    """Game-level first team to reach q using the same ordering as FIRST80."""
    from collections import defaultdict

    by_event = defaultdict(list)
    for m in markets:
        by_event[m["event_id"]].append(m)
    games_by_event = {g["event_id"]: g for g in games}
    rows = []
    for event_id, ms in by_event.items():
        g = games_by_event.get(event_id, {})
        hits = []
        for m in ms:
            q = first_tradable_reach(quotes.get(m["ticker"], []), hit_e4)
            if q:
                hits.append((q["ts"], m["ticker"], m, q))
        hits.sort(key=lambda x: (x[0], x[1]))
        rec = {
            "event_id": event_id,
            "game_date": g.get("game_date"),
            "dataset_split": C.canon_split(A.dataset_split(g.get("game_date"))),
            "regime": A.season_regime(g.get("game_date")),
            "threshold_cents": hit_e4 / 100.0,
            "status": "NO_REACH",
            "ticker": None,
            "team": None,
            "reach_ts": None,
            "W": None,
            "T40": None,
            "tie_same_minute": False,
        }
        if not hits:
            rows.append(rec)
            continue
        ts, ticker, m0, q = hits[0]
        if len([h for h in hits if h[0] == ts]) > 1:
            rec["status"] = "TIE_SAME_MINUTE"
            rec["tie_same_minute"] = True
            rows.append(rec)
            continue
        won = A.settled_yes(m0)
        t40 = first_close_le_after(quotes.get(ticker, []), ts, C.HIT40_E4)
        rec.update(
            {
                "status": "FIRST_REACH",
                "ticker": ticker,
                "team": m0["team"],
                "reach_ts": ts,
                "entry_bid_close_e4": q["bid_c"],
                "W": won,
                "T40": t40 is not None,
                "t40_ts": None if t40 is None else t40["ts"],
                "n_other_reaches_same_event": len(hits) - 1,
            }
        )
        rows.append(rec)
    return pd.DataFrame(rows)
