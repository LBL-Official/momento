#!/usr/bin/env python3
"""Asked-six FIRST80 trade ledger for external research (ChatGPT CSV).

Universe (frozen barrier-survival windows, not a new filter):
  NBA  Q2 ∪ Q3
  WNBA Q2 ∪ Q3
  NCAAB P5 vs P5  H1_2 (1H second 10) ∪ H2_1 (2H first 10)

One row per FIRST80 trade. Candle path, not a fill. Does not change
live FIRST01. Does not invent possession, fouls, timeouts, L2, or trades.

```
RESEARCH ONLY
CANDLE PATH ≠ ACTUAL FILL
LIVE EXECUTION = FALSE
POSSESSION = UNAVAILABLE
```
"""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pyarrow.parquet as pq

SCRIPTS = Path(__file__).resolve().parent
NBA_SCRIPTS = SCRIPTS
WNBA_SCRIPTS = Path("/Users/user/Desktop/Momento/apps/wnba-data/scripts")
NCAAB_SCRIPTS = Path("/Users/user/Desktop/Momento/apps/ncaab-data/scripts")
for p in (NBA_SCRIPTS, NCAAB_SCRIPTS):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import nba_80_40_execution_audit as A  # noqa: E402


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


NBA_Q = _load_module(
    "nba_first80_q_barrier_chatgpt_export",
    NBA_SCRIPTS / "first80_quarter_barrier_survival.py",
)
WNBA_Q = _load_module(
    "wnba_first80_q_barrier_chatgpt_export",
    WNBA_SCRIPTS / "first80_quarter_barrier_survival.py",
)
NCAAB_Q = _load_module(
    "ncaab_first80_half_barrier_chatgpt_export",
    NCAAB_SCRIPTS / "first80_p5_half_barrier_survival.py",
)

REPO = Path("/Users/user/Desktop/Momento")
OUT = REPO / "research" / "first80_asked_six_chatgpt_export"
WH_OUT = (
    REPO
    / "Backtesting Suite"
    / "Data"
    / "NBA"
    / "2025-2026"
    / "warehouse"
    / "derived"
    / "nba"
    / "first80_asked_six_chatgpt_export"
)

EXPECTED_ASKED = {"NBA": 604, "WNBA": 246, "NCAAB": 332}
EXPECTED_TOTAL = 1182
HIT80_E4 = 8000
HIT40_E4 = 4000
ENTRY_CENTS = 80
STOP_CENTS = 40
SETTLE_YES_CENTS = 100
SETTLE_NO_CENTS = 0
UNAVAILABLE = "UNAVAILABLE"

SLICE_LABEL = {
    "Q2": "2Q",
    "Q3": "3Q",
    "H1_2": "1H second 10",
    "H2_1": "2H first 10",
}

CSV_COLUMNS = [
    "sport",
    "slice",
    "slice_label",
    "game_id",
    "event_id",
    "ticker",
    "game_date",
    "calendar_month",
    "dataset_split",
    "season_phase",
    "timestamp",
    "timestamp_utc",
    "period",
    "game_clock",
    "period_remaining_s",
    "game_seconds_remaining",
    "entry_phase",
    "alignment_confidence",
    "home_team",
    "away_team",
    "home_team_code",
    "away_team_code",
    "bought_team",
    "side",
    "opponent_team",
    "score_home",
    "score_away",
    "score_diff",
    "bought_team_margin",
    "possession_team",
    "possession_id",
    "possession_status",
    "pregame_home_win_prob",
    "pregame_away_win_prob",
    "pregame_source",
    "market_yes_bid",
    "market_yes_ask",
    "market_last_price",
    "market_volume",
    "market_volume_note",
    "market_trades",
    "market_trades_status",
    "entry_implied_prob",
    "first80_rule_implied_prob",
    "home_fouls",
    "away_fouls",
    "home_timeouts",
    "away_timeouts",
    "fouls_timeouts_status",
    "event_type",
    "event_description",
    "rule_80_40",
    "win_80_40",
    "stopped_40",
    "terminal_yes",
    "W",
    "T40",
    "T40_wick",
    "final_winner",
    "final_score_home",
    "final_score_away",
    "final_score",
    "would_have_exited_at_40",
    "held_to_expiration",
    "exit_kind",
    "exit_price_cents",
    "exit_timestamp",
    "exit_timestamp_utc",
    "exit_period",
    "exit_game_clock",
    "exit_score_home",
    "exit_score_away",
    "post_entry_min_yes_bid_cents",
    "post_entry_min_yes_bid_timestamp",
    "last_tradable_yes_bid_cents",
    "last_tradable_timestamp",
    "outcome_80_40",
    "hyp_pnl_cents_80_40",
    "candle_path_not_fill",
    "live_execution",
]


class IdentityHalt(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def iso(ts: int | None) -> str | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()


def e4_to_cents(v) -> float | None:
    if v is None:
        return None
    return int(v) / 100.0


def e4_to_prob(v) -> float | None:
    c = e4_to_cents(v)
    if c is None:
        return None
    return round(c / 100.0, 4)


def format_clock(seconds) -> str | None:
    return NBA_Q.format_clock(seconds)


def outcome_80_40(won: bool, t40: bool) -> tuple[str, int]:
    """Gross candle 80→40 / hold-to-settlement. Not a fill. Zero fee."""
    if t40:
        return "STOP_40", STOP_CENTS - ENTRY_CENTS
    if won:
        return "WIN_HOLD", SETTLE_YES_CENTS - ENTRY_CENTS
    return "LOSS_HOLD", SETTLE_NO_CENTS - ENTRY_CENTS


def flags_80_40(won: bool, t40: bool) -> dict:
    """Per-trade 80/40 result. win_80_40 is not terminal W."""
    outcome, pnl = outcome_80_40(won, t40)
    return {
        "rule_80_40": "BUY80_STOP40",
        "win_80_40": outcome == "WIN_HOLD",
        "stopped_40": outcome == "STOP_40",
        "terminal_yes": bool(won),
        "outcome_80_40": outcome,
        "hyp_pnl_cents_80_40": pnl,
    }


def _norm(s) -> str:
    return "".join(ch for ch in str(s).upper() if ch.isalnum())


def side_of(ticker: str | None, game: dict, bought_team: str | None = None) -> str | None:
    if ticker:
        home_t = game.get("home_market_ticker")
        away_t = game.get("away_market_ticker")
        if home_t and ticker == home_t:
            return "home"
        if away_t and ticker == away_t:
            return "away"
        suf = _norm(ticker.rsplit("-", 1)[-1])
        home_c = _norm(game.get("home_team_code") or "")
        away_c = _norm(game.get("away_team_code") or "")
        if suf and home_c and (suf == home_c or suf in home_c or home_c in suf):
            return "home"
        if suf and away_c and (suf == away_c or suf in away_c or away_c in suf):
            return "away"
    bought = _norm(bought_team or "")
    if bought:
        if bought == _norm(game.get("home_team") or "") or bought == _norm(
            game.get("home_team_code") or ""
        ):
            return "home"
        if bought == _norm(game.get("away_team") or "") or bought == _norm(
            game.get("away_team_code") or ""
        ):
            return "away"
    return None


def load_games(path: Path) -> dict[str, dict]:
    t = pq.read_table(path)
    names = t.column_names
    out = {}
    for i in range(t.num_rows):
        row = {n: t.column(n)[i].as_py() for n in names}
        out[row["event_id"]] = row
    return out


def index_candles(candles_dir: Path) -> dict[str, Path]:
    return {p.stem: p for p in candles_dir.rglob("*.parquet")}


def load_ticker_quotes(path: Path) -> list[dict]:
    cols = [
        "end_period_ts",
        "yes_bid_close_e4",
        "yes_ask_close_e4",
        "yes_bid_low_e4",
        "price_close_e4",
        "volume_hundredths",
        "is_valid",
    ]
    table = pq.read_table(path, columns=cols)
    get = {c: table.column(c) for c in cols}
    rows = []
    for i in range(table.num_rows):
        if not get["is_valid"][i].as_py():
            continue
        rows.append(
            {
                "ts": int(get["end_period_ts"][i].as_py()),
                "bid_c": A._opt_int(get["yes_bid_close_e4"][i].as_py()),
                "ask_c": A._opt_int(get["yes_ask_close_e4"][i].as_py()),
                "bid_l": A._opt_int(get["yes_bid_low_e4"][i].as_py()),
                "last_c": A._opt_int(get["price_close_e4"][i].as_py()),
                "vol": A._opt_int(get["volume_hundredths"][i].as_py()),
            }
        )
    rows.sort(key=lambda r: r["ts"])
    return rows


def quality_ok(q: dict, had_q: bool) -> bool:
    return A.quality(q.get("bid_c"), q.get("ask_c"), q.get("vol"), had_q)


def pregame_yes_bid(quotes: list[dict], tip_ts: int | None) -> int | None:
    """Last tradable yes_bid_close strictly before tip. Not a model."""
    if tip_ts is None:
        return None
    had_q = True
    last = None
    for q in quotes:
        if int(q["ts"]) >= int(tip_ts):
            break
        if not quality_ok(q, had_q):
            continue
        had_q = True
        last = q["bid_c"]
    return last


def path_after_entry(quotes: list[dict], t0: int, scan_end: int | None) -> dict:
    had_q = True
    t40_ts = None
    min_bid = None
    min_ts = None
    last_bid = None
    last_ts = None
    for q in quotes:
        ts = int(q["ts"])
        if ts <= t0:
            continue
        if scan_end is not None and ts > scan_end:
            continue
        if not quality_ok(q, had_q):
            continue
        had_q = True
        bid = q["bid_c"]
        if bid is None:
            continue
        last_bid, last_ts = bid, ts
        if min_bid is None or bid < min_bid:
            min_bid, min_ts = bid, ts
        if t40_ts is None and bid <= HIT40_E4:
            t40_ts = ts
    return {
        "t40_ts": t40_ts,
        "min_bid_e4": min_bid,
        "min_ts": min_ts,
        "last_bid_e4": last_bid,
        "last_ts": last_ts,
    }


def quote_at(quotes: list[dict], ts: int | None) -> dict | None:
    if ts is None:
        return None
    for q in quotes:
        if int(q["ts"]) == int(ts):
            return q
    return None


def tip_ts_from_actions(actions: list[dict] | None) -> int | None:
    if not actions:
        return None
    for r in actions:
        typ = (r.get("actionType") or "").lower()
        sub = (r.get("subType") or "").lower()
        if r.get("period") == 1 and (
            (typ == "period" and sub == "start") or sub == "start"
        ):
            wall = r.get("knot_wall_ts") or r.get("modeled_wall_ts")
            if wall is not None:
                return int(wall)
    walls = [r.get("modeled_wall_ts") for r in actions if r.get("modeled_wall_ts")]
    return int(min(walls)) if walls else None


def play_at(actions: list[dict] | None, ts: int | None) -> dict | None:
    if not actions or ts is None:
        return None
    cands = [
        r
        for r in actions
        if r.get("modeled_wall_ts") is not None and int(r["modeled_wall_ts"]) <= int(ts)
    ]
    return cands[-1] if cands else None


def last_play(actions: list[dict] | None) -> dict | None:
    if not actions:
        return None
    for r in reversed(actions):
        if r.get("score_home") is not None and r.get("score_away") is not None:
            return r
    return actions[-1] if actions else None


def _as_int(v):
    if v is None or v == "":
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def nba_box_final(nba_id: str | None) -> dict:
    out = {
        "final_home": None,
        "final_away": None,
        "final_home_to": None,
        "final_away_to": None,
    }
    if not nba_id:
        return out
    box = NBA_Q.load_box(nba_id)
    hdr = NBA_Q.box_header(box)
    home = hdr.get("homeTeam") or {}
    away = hdr.get("awayTeam") or {}
    out["final_home"] = _as_int(home.get("score"))
    out["final_away"] = _as_int(away.get("score"))
    out["final_home_to"] = _as_int(home.get("timeoutsRemaining"))
    out["final_away_to"] = _as_int(away.get("timeoutsRemaining"))
    return out


def scheduled_tip(game: dict) -> int | None:
    raw = game.get("scheduled_start")
    if not raw:
        return None
    return A.parse_ts(raw) if hasattr(A, "parse_ts") else None


def collect_sport(sport: str) -> list[dict]:
    if sport == "NBA":
        mod, slices, bucket_key = NBA_Q, ("Q2", "Q3"), "entry_quarter_bucket"
        games = load_games(A.NORM / "games" / "nba_games.parquet")
        xwalk = NBA_Q.load_crosswalk()
        trades = NBA_Q.load_frozen_first80()
        NBA_Q.halt_unless_identity(trades)
        candles_dir = NBA_Q.CANDLES_DIR
    elif sport == "WNBA":
        mod, slices, bucket_key = WNBA_Q, ("Q2", "Q3"), "entry_quarter_bucket"
        games = load_games(WNBA_Q.NORM / "games" / "wnba_games.parquet")
        xwalk = WNBA_Q.P.load_crosswalk()
        trades = WNBA_Q.load_frozen_first80()
        WNBA_Q.halt_unless_identity(trades)
        candles_dir = WNBA_Q.CANDLES_DIR
    elif sport == "NCAAB":
        mod, slices, bucket_key = NCAAB_Q, ("H1_2", "H2_1"), "entry_half_bucket"
        games = load_games(NCAAB_Q.GAMES_PATH)
        xwalk = NCAAB_Q.P.load_crosswalk()
        trades = NCAAB_Q.load_frozen_p5_first80()
        NCAAB_Q.halt_unless_identity(trades)
        candles_dir = NCAAB_Q.CANDLES_DIR
    else:
        raise IdentityHalt(sport)

    pbp_cache: dict = {}
    candle_idx = index_candles(candles_dir)
    quotes_cache: dict[str, list] = {}

    def quotes_for(ticker: str | None) -> list[dict]:
        if not ticker:
            return []
        if ticker not in quotes_cache:
            path = candle_idx.get(ticker)
            quotes_cache[ticker] = load_ticker_quotes(path) if path else []
        return quotes_cache[ticker]

    rows = []
    t40_mismatch = []
    for rec in trades:
        align = mod.align_entry(rec, xwalk, pbp_cache)
        bucket = align.get(bucket_key)
        if bucket not in slices:
            continue
        game = games.get(rec["event_id"]) or {}
        t0 = int(rec["first_80_timestamp"])
        ticker = rec["ticker"]
        quotes = quotes_for(ticker)
        if not quotes:
            raise IdentityHalt(f"HALT missing candles {sport} {ticker}")
        path = path_after_entry(quotes, t0, mod.scan_window_end(rec))
        frozen_t40 = bool(rec.get("stop_close_triggered"))
        rescanned = path["t40_ts"] is not None
        if frozen_t40 != rescanned:
            t40_mismatch.append(ticker)
            continue

        if sport == "NBA":
            packed = None
            nba_id = align.get("nba_game_id")
            if nba_id:
                packed = NBA_Q._pbp_pack(nba_id, pbp_cache)
            actions = packed[0] if packed else []
            box_final = nba_box_final(nba_id)
        else:
            espn_id = align.get("espn_game_id")
            actions = mod._pbp_pack(espn_id, pbp_cache) if espn_id else []
            actions = actions or []
            box_final = {
                "final_home": None,
                "final_away": None,
                "final_home_to": None,
                "final_away_to": None,
            }

        tip = tip_ts_from_actions(actions) or scheduled_tip(game)
        home_tkr = game.get("home_market_ticker")
        away_tkr = game.get("away_market_ticker")
        if not home_tkr or not away_tkr:
            codes = (game.get("market_tickers") or "").split(",")
            if len(codes) == 2:
                home_tkr = home_tkr or next(
                    (
                        t
                        for t in codes
                        if t.endswith("-" + str(game.get("home_team_code") or ""))
                    ),
                    None,
                )
                away_tkr = away_tkr or next(
                    (
                        t
                        for t in codes
                        if t.endswith("-" + str(game.get("away_team_code") or ""))
                    ),
                    None,
                )
        pre_h = pregame_yes_bid(quotes_for(home_tkr), tip)
        pre_a = pregame_yes_bid(quotes_for(away_tkr), tip)

        entry_play = play_at(actions, t0)
        last = last_play(actions)
        won = bool(rec["expiration_result_yes"])
        t40 = frozen_t40
        t40_ts = path["t40_ts"] or rec.get("first_40_close_ts")
        exit_play = play_at(actions, t40_ts) if t40 else last
        flags = flags_80_40(won, t40)
        outcome, pnl = flags["outcome_80_40"], flags["hyp_pnl_cents_80_40"]
        if t40:
            exit_kind = "T40_CLOSE"
            exit_px = STOP_CENTS
            exit_ts = t40_ts
        elif won:
            exit_kind = "SETTLEMENT_YES"
            exit_px = SETTLE_YES_CENTS
            exit_ts = rec.get("close_ts") or (last or {}).get("modeled_wall_ts")
        else:
            exit_kind = "SETTLEMENT_NO"
            exit_px = SETTLE_NO_CENTS
            exit_ts = rec.get("close_ts") or (last or {}).get("modeled_wall_ts")

        home_name = game.get("home_team") or game.get("home_team_code")
        away_name = game.get("away_team") or game.get("away_team_code")
        bought = rec.get("team")
        side = side_of(ticker, game, bought)
        if side == "home":
            opp = away_name
        elif side == "away":
            opp = home_name
        else:
            opp = None
        sh = _as_int((entry_play or {}).get("score_home"))
        sa = _as_int((entry_play or {}).get("score_away"))
        fh = box_final["final_home"]
        fa = box_final["final_away"]
        if fh is None:
            fh = _as_int((last or {}).get("score_home"))
        if fa is None:
            fa = _as_int((last or {}).get("score_away"))
        if won:
            final_winner = bought
        elif side == "home":
            final_winner = away_name
        elif side == "away":
            final_winner = home_name
        else:
            final_winner = None
        if sh is not None and sa is not None:
            score_diff = sh - sa
            if side == "home":
                bought_m = sh - sa
            elif side == "away":
                bought_m = sa - sh
            else:
                bought_m = None
        else:
            score_diff = None
            bought_m = None
        gd = rec.get("game_date") or game.get("game_date")
        rows.append(
            {
                "sport": sport,
                "slice": bucket,
                "slice_label": SLICE_LABEL[bucket],
                "game_id": rec.get("game_id") or game.get("game_id"),
                "event_id": rec.get("event_id"),
                "ticker": ticker,
                "game_date": gd,
                "calendar_month": None if not gd else str(gd)[:7],
                "dataset_split": rec.get("dataset_split") or A.dataset_split(gd),
                "season_phase": rec.get("season_phase") or game.get("season_phase"),
                "timestamp": t0,
                "timestamp_utc": rec.get("first_80_utc") or iso(t0),
                "period": align.get("entry_period"),
                "game_clock": format_clock(align.get("entry_period_remaining_s")),
                "period_remaining_s": align.get("entry_period_remaining_s"),
                "game_seconds_remaining": align.get("entry_game_seconds_remaining"),
                "entry_phase": align.get("entry_phase"),
                "alignment_confidence": align.get("alignment_confidence"),
                "home_team": home_name,
                "away_team": away_name,
                "home_team_code": game.get("home_team_code"),
                "away_team_code": game.get("away_team_code"),
                "bought_team": bought,
                "side": side,
                "opponent_team": opp,
                "score_home": sh,
                "score_away": sa,
                "score_diff": score_diff,
                "bought_team_margin": bought_m,
                "possession_team": "",
                "possession_id": "",
                "possession_status": UNAVAILABLE,
                "pregame_home_win_prob": e4_to_prob(pre_h),
                "pregame_away_win_prob": e4_to_prob(pre_a),
                "pregame_source": (
                    "KALSHI_LAST_PRE_TIP_YES_BID"
                    if pre_h is not None or pre_a is not None
                    else UNAVAILABLE
                ),
                "market_yes_bid": e4_to_cents(rec.get("entry_bid_close_e4")),
                "market_yes_ask": e4_to_cents(rec.get("entry_ask_close_e4")),
                "market_last_price": e4_to_cents(rec.get("entry_last_close_e4")),
                "market_volume": e4_to_cents(rec.get("entry_volume_hundredths")),
                "market_volume_note": "ENTRY_CANDLE_VOLUME_HUNDREDTHS/100_NOT_CUMULATIVE",
                "market_trades": "",
                "market_trades_status": UNAVAILABLE,
                "entry_implied_prob": e4_to_prob(rec.get("entry_bid_close_e4")),
                "first80_rule_implied_prob": 0.80,
                "home_fouls": "",
                "away_fouls": "",
                "home_timeouts": "",
                "away_timeouts": "",
                "fouls_timeouts_status": UNAVAILABLE,
                "event_type": None if not entry_play else entry_play.get("actionType"),
                "event_description": None
                if not entry_play
                else entry_play.get("description"),
                "rule_80_40": flags["rule_80_40"],
                "win_80_40": flags["win_80_40"],
                "stopped_40": flags["stopped_40"],
                "terminal_yes": flags["terminal_yes"],
                "W": won,
                "T40": t40,
                "T40_wick": bool(rec.get("stop_low_triggered")),
                "final_winner": final_winner,
                "final_score_home": fh,
                "final_score_away": fa,
                "final_score": None if fh is None or fa is None else f"{fh}-{fa}",
                "would_have_exited_at_40": t40,
                "held_to_expiration": not t40,
                "exit_kind": exit_kind,
                "exit_price_cents": exit_px,
                "exit_timestamp": None if exit_ts is None else int(exit_ts),
                "exit_timestamp_utc": iso(None if exit_ts is None else int(exit_ts)),
                "exit_period": None if not exit_play else exit_play.get("period"),
                "exit_game_clock": format_clock(
                    None if not exit_play else exit_play.get("remaining_s")
                ),
                "exit_score_home": _as_int(
                    None if not exit_play else exit_play.get("score_home")
                ),
                "exit_score_away": _as_int(
                    None if not exit_play else exit_play.get("score_away")
                ),
                "post_entry_min_yes_bid_cents": e4_to_cents(path["min_bid_e4"]),
                "post_entry_min_yes_bid_timestamp": path["min_ts"],
                "last_tradable_yes_bid_cents": e4_to_cents(path["last_bid_e4"]),
                "last_tradable_timestamp": path["last_ts"],
                "outcome_80_40": outcome,
                "hyp_pnl_cents_80_40": pnl,
                "candle_path_not_fill": True,
                "live_execution": False,
                "_nba_final_home_timeouts_remaining_end_of_game": box_final[
                    "final_home_to"
                ],
                "_nba_final_away_timeouts_remaining_end_of_game": box_final[
                    "final_away_to"
                ],
            }
        )

    if t40_mismatch:
        raise IdentityHalt(
            f"HALT {sport} T40 rescan mismatch n={len(t40_mismatch)} sample={t40_mismatch[:5]}"
        )
    if len(rows) != EXPECTED_ASKED[sport]:
        raise IdentityHalt(
            f"HALT {sport} asked-six n={len(rows)} expected {EXPECTED_ASKED[sport]}"
        )
    return rows


def collect() -> list[dict]:
    rows = []
    for sport in ("NBA", "WNBA", "NCAAB"):
        print(f"collect {sport}", flush=True)
        part = collect_sport(sport)
        print(f"  n={len(part)}", flush=True)
        rows.extend(part)
    if len(rows) != EXPECTED_TOTAL:
        raise IdentityHalt(f"HALT total {len(rows)} expected {EXPECTED_TOTAL}")
    rows.sort(key=lambda r: (r["game_date"] or "", r["timestamp"] or 0, r["ticker"] or ""))
    return rows


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: "" if r.get(k) is None else r[k] for k in CSV_COLUMNS})


def write_readme() -> str:
    return """# Asked-six FIRST80 ledger (ChatGPT export)

Research only. **Not a fill. Not live. Not a strategy authorization.**

```
LIVE EXECUTION = FALSE
CANDLE PATH ≠ ACTUAL FILL
POSSESSION / FOULS / TIMEOUTS / TRADE COUNTS = UNAVAILABLE
```

## Universe

Frozen FIRST80, then the published asked-six mid-game windows only:

| Sport | Window | Expected N |
|---|---|---:|
| NBA | 2Q ∪ 3Q | 604 |
| WNBA | 2Q ∪ 3Q | 246 |
| NCAAB P5 vs P5 | 1H second 10 ∪ 2H first 10 | 332 |
| **Total** | | **1182** |

This is **not** 3,000 games. Do not invent extra rows.

**All 1,182 rows use the 80/40 stop rule.** Do not report `W` / `terminal_yes` as the strategy win rate.

| Headline | Column | Count | Rate |
|---|---|---:|---:|
| **80/40 win** | `win_80_40=True` | 883 | **74.70%** |
| 80/40 stop | `stopped_40=True` | 299 | 25.30% |
| Terminal YES (ignore stop) | `W` / `terminal_yes` | 991 | 83.84% |

`W` includes 108 trades that hit the 40 close and later settled YES. Those are **stops**, not 80/40 wins.

FIRST80 = first tradable `yes_bid_close ≥ 80¢` after a prior tradable close `< 80`, uncrossed spread ≤ 10¢, one per event. Same-minute ties excluded.

## Exit when the tape never printed 40

`would_have_exited_at_40` is the close-path T40 (`yes_bid_close ≤ 40` after entry).

| `exit_kind` | meaning | `exit_price_cents` | `hyp_pnl_cents_80_40` |
|---|---|---:|---:|
| `T40_CLOSE` | first later tradable close ≤ 40 | 40 | −40 |
| `SETTLEMENT_YES` | never T40, YES expires | 100 | +20 |
| `SETTLEMENT_NO` | never T40, NO expires | 0 | −80 |

If T40 never printed, use `exit_kind`, `exit_price_cents`, `exit_timestamp`, `exit_period`, `exit_game_clock`, `exit_score_*`, plus `post_entry_min_yes_bid_cents` (closest close-path bid after entry) and `T40_wick` (wick touched 40 even if close did not).

Wick-only 40 is **not** an exit. Close-path is the frozen rule.

## Do not treat these as observed strategy inputs

| Column | Status |
|---|---|
| `possession_team`, `possession_id` | UNAVAILABLE — not invented |
| `home_fouls`, `away_fouls`, `home_timeouts`, `away_timeouts` | UNAVAILABLE at entry |
| `market_trades` | UNAVAILABLE (`trade_count_available=false`) |
| `pregame_*_win_prob` | Kalshi last tradable yes bid **before tip**, not a model. Missing → blank, `pregame_source=UNAVAILABLE` |
| `market_volume` | volume on the **entry candle only**, not cumulative tape |
| `hyp_pnl_cents_80_40` | gross candle-path 80/40 / hold. Zero fee. Not a fill |

`first80_rule_implied_prob` is always 0.80. `entry_implied_prob` is the actual entry bid / 100 (can be > 0.80).

## Splits (frozen, do not retune)

`dataset_split`: IN_SAMPLE `game_date ≤ 2025-12-31`; VALIDATION `≤ 2026-03-15`; else OOS.

NCAAB OOS is small (conference tournament / March). Do not use the full 1,182 rows both to “prove” a win rate and to fit a risk model. Split first.

## What ChatGPT should not do

- Do not treat this as executable edge.
- Do not hunt a profitable subset and promote it.
- Do not assume a 40 exit was fillable.
- Do not fill UNAVAILABLE columns from box-score intuition.
- Do not change live FIRST01 / 80/81/83/89.
- Do not use `W` as the 80/40 win rate.

## Next object (do not reshape this ledger into O_t)

KEEP / REMOVE / ADD for a ROLLER observation layer is in
`ROLLER_LAYER_SCHEMA.md` and `column_layer_map.json`. FIRST80 stays off `O_t`.
"""


def summary_of(rows: list[dict]) -> dict:
    by = Counter(r["sport"] for r in rows)
    exits = Counter(r["exit_kind"] for r in rows)
    return {
        "written_utc": utc_now(),
        "research_only": True,
        "live_execution": False,
        "candle_path_not_fill": True,
        "n": len(rows),
        "by_sport": dict(by),
        "by_slice": dict(Counter(f"{r['sport']}:{r['slice']}" for r in rows)),
        "by_exit_kind": dict(exits),
        "headline": "win_80_40_not_terminal_W",
        "n_win_80_40": sum(1 for r in rows if _as_bool(r.get("win_80_40"))),
        "n_stopped_40": sum(1 for r in rows if _as_bool(r.get("stopped_40"))),
        "pct_win_80_40": None
        if not rows
        else round(
            100.0 * sum(1 for r in rows if _as_bool(r.get("win_80_40"))) / len(rows), 4
        ),
        "n_W": sum(1 for r in rows if _as_bool(r.get("W"))),
        "n_T40": sum(1 for r in rows if _as_bool(r.get("T40"))),
        "n_held_to_expiration": sum(
            1 for r in rows if _as_bool(r.get("held_to_expiration"))
        ),
        "n_loss_hold": sum(1 for r in rows if r.get("outcome_80_40") == "LOSS_HOLD"),
        "possession": UNAVAILABLE,
        "fouls_timeouts": UNAVAILABLE,
        "market_trades": UNAVAILABLE,
        "expected": EXPECTED_ASKED,
        "csv": "first80_asked_six.csv",
    }


def _as_bool(v) -> bool:
    return str(v).strip() in {"True", "true", "1"}


def attach_80_40_to_existing(rows: list[dict]) -> list[dict]:
    """Add 80/40 headline flags. Does not drop rows. Does not rescan candles."""
    out = []
    for r in rows:
        won = _as_bool(r.get("W"))
        t40 = _as_bool(r.get("T40"))
        flags = flags_80_40(won, t40)
        merged = {**r, **flags, "W": won, "T40": t40}
        out.append(merged)
    if len(out) != EXPECTED_TOTAL:
        raise IdentityHalt(f"HALT rewrite n={len(out)} expected {EXPECTED_TOTAL}")
    n_win = sum(1 for r in out if r["win_80_40"])
    n_stop = sum(1 for r in out if r["stopped_40"])
    if n_win + n_stop != EXPECTED_TOTAL:
        raise IdentityHalt(f"HALT 80/40 coverage win={n_win} stop={n_stop}")
    return out


def load_existing_csv(path: Path | None = None) -> list[dict]:
    src = path or (OUT / "first80_asked_six.csv")
    with src.open(newline="") as f:
        return list(csv.DictReader(f))


def write_outputs(rows: list[dict]) -> None:
    readme = write_readme()
    summ = json.dumps(summary_of(rows), indent=2) + "\n"
    for dest in (OUT, WH_OUT):
        dest.mkdir(parents=True, exist_ok=True)
        write_csv(dest / "first80_asked_six.csv", rows)
        (dest / "README.md").write_text(readme)
        (dest / "summary.json").write_text(summ)


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--from-csv":
        rows = attach_80_40_to_existing(load_existing_csv())
    else:
        rows = collect()
    write_outputs(rows)
    print(json.dumps(summary_of(rows), indent=2))
    print("csv", OUT / "first80_asked_six.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
