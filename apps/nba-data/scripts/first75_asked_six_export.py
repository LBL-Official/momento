#!/usr/bin/env python3
"""Asked-six FIRST75 ledger for Choosin Texas (75).

Same τ definition as first75_slice_not40_given_w.py. Same clock slices as
the FIRST80 asked-six export. One row per FIRST75 event.

Research only. Candle path ≠ fill. Does not change live FIRST01.
Does not invent L2. Halts unless TABLES.md FIRST75 asked-six N matches.
"""

from __future__ import annotations

import csv
import importlib.util
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import first75_slice_not40_given_w as F  # noqa: E402
import first80_asked_six_chatgpt_export as E  # noqa: E402
import nba_80_40_execution_audit as A  # noqa: E402

REPO = Path("/Users/user/Desktop/Momento")
OUT = REPO / "research" / "first75_asked_six_chatgpt_export"
HIT75_E4 = 7500
HIT40_E4 = 4000

EXPECTED = {
    ("NBA", "Q2"): 318,
    ("NBA", "Q3"): 258,
    ("WNBA", "Q2"): 128,
    ("WNBA", "Q3"): 85,
    ("NCAAB", "H1_2"): 204,
    ("NCAAB", "H2_1"): 133,
}
EXPECTED_TOTAL = 1126
EXPECTED_FOUR = 913

CSV_COLUMNS = list(E.CSV_COLUMNS)


class IdentityHalt(RuntimeError):
    pass


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def quote_at(quotes: list[dict], ts: int | None) -> dict | None:
    if ts is None:
        return None
    for q in quotes:
        if int(q["ts"]) == int(ts):
            return q
    return None


def path_after(quotes: list[dict], t0: int) -> dict:
    min_bid = None
    min_ts = None
    last_bid = None
    last_ts = None
    t40_ts = None
    for q in quotes:
        ts = int(q["ts"])
        if ts <= int(t0):
            continue
        if not A.quality(q.get("bid_c"), q.get("ask_c"), q.get("vol"), True):
            continue
        bid = q.get("bid_c")
        if bid is None:
            continue
        last_bid, last_ts = bid, ts
        if min_bid is None or bid < min_bid:
            min_bid, min_ts = bid, ts
        if t40_ts is None and bid <= HIT40_E4:
            t40_ts = ts
    return {
        "min_bid_e4": min_bid,
        "min_ts": min_ts,
        "last_bid_e4": last_bid,
        "last_ts": last_ts,
        "t40_ts": t40_ts,
    }


def enrich_row(
    rec: dict,
    *,
    sport: str,
    quotes: dict[str, list],
    games: dict[str, dict],
    align_mod,
    pbp_cache: dict,
    xwalk: dict,
) -> dict:
    ticker = rec["ticker"]
    t0 = int(rec["reach_ts"] or rec["first_80_timestamp"])
    qrows = quotes.get(ticker) or []
    entry_q = quote_at(qrows, t0)
    if entry_q is None or entry_q.get("bid_c") is None:
        raise IdentityHalt(f"missing FIRST75 entry quote {sport} {ticker}")
    if int(entry_q["bid_c"]) < HIT75_E4:
        raise IdentityHalt(f"{ticker}: FIRST75 entry bid {entry_q['bid_c']} < 75")
    path = path_after(qrows, t0)
    if path["min_bid_e4"] is None:
        raise IdentityHalt(f"{ticker}: no post-entry tradable close")
    won = bool(rec["W"])
    t40 = bool(rec["T40"])
    path_t40 = path["t40_ts"] is not None
    if t40 != path_t40:
        raise IdentityHalt(f"{ticker}: T40={t40} but path min/t40 {path['min_bid_e4']}/{path['t40_ts']}")
    if (path["min_bid_e4"] <= HIT40_E4) != t40:
        raise IdentityHalt(f"{ticker}: T40={t40} but post_entry_min={path['min_bid_e4']}")

    game = games.get(rec["event_id"]) or {}
    align = align_mod.align_entry(rec, xwalk, pbp_cache)
    bucket = rec.get("entry_bucket") or align.get("entry_quarter_bucket") or align.get("entry_half_bucket")
    bought = rec.get("team")
    side = E.side_of(ticker, game, bought)

    sh = sa = fh = fa = None
    exit_play = None
    last = None
    if sport == "NBA":
        nba_id = align.get("nba_game_id")
        packed = align_mod._pbp_pack(nba_id, pbp_cache) if nba_id else None
        actions = packed[0] if packed else []
        box_final = E.nba_box_final(nba_id)
        entry_play = E.play_at(actions, t0)
        last = E.last_play(actions)
        t40_ts = path["t40_ts"] or rec.get("t40_ts")
        exit_play = E.play_at(actions, t40_ts) if t40 else last
        sh = E._as_int((entry_play or {}).get("score_home"))
        sa = E._as_int((entry_play or {}).get("score_away"))
        fh = box_final["final_home"]
        fa = box_final["final_away"]
        if fh is None:
            fh = E._as_int((last or {}).get("score_home"))
        if fa is None:
            fa = E._as_int((last or {}).get("score_away"))
    else:
        entry_play = None
        box_final = {"final_home": None, "final_away": None}

    if sh is not None and sa is not None and side == "home":
        bought_m = sh - sa
        score_diff = sh - sa
    elif sh is not None and sa is not None and side == "away":
        bought_m = sa - sh
        score_diff = sh - sa
    else:
        bought_m = None
        score_diff = None if sh is None or sa is None else sh - sa

    home_name = game.get("home_team") or game.get("home_team_code")
    away_name = game.get("away_team") or game.get("away_team_code")
    if won:
        final_winner = bought
    elif side == "home":
        final_winner = away_name
    elif side == "away":
        final_winner = home_name
    else:
        final_winner = None

    if t40:
        exit_kind = "T40_CLOSE"
        exit_px = 40
        exit_ts = path["t40_ts"] or rec.get("t40_ts")
    elif won:
        exit_kind = "SETTLEMENT_YES"
        exit_px = 100
        exit_ts = rec.get("close_ts")
    else:
        exit_kind = "SETTLEMENT_NO"
        exit_px = 0
        exit_ts = rec.get("close_ts")

    gd = rec.get("game_date") or game.get("game_date")
    return {
        "sport": sport,
        "slice": bucket,
        "slice_label": E.SLICE_LABEL[bucket],
        "game_id": rec.get("game_id") or game.get("game_id"),
        "event_id": rec.get("event_id"),
        "ticker": ticker,
        "game_date": gd,
        "calendar_month": None if not gd else str(gd)[:7],
        "dataset_split": rec.get("dataset_split") or A.dataset_split(gd),
        "season_phase": rec.get("season_phase") or game.get("season_phase"),
        "timestamp": t0,
        "timestamp_utc": E.iso(t0),
        "period": align.get("entry_period"),
        "game_clock": E.format_clock(align.get("entry_period_remaining_s")),
        "period_remaining_s": align.get("entry_period_remaining_s"),
        "game_seconds_remaining": align.get("entry_game_seconds_remaining"),
        "entry_phase": align.get("entry_phase"),
        "alignment_confidence": align.get("alignment_confidence") or rec.get("alignment_confidence"),
        "home_team": home_name,
        "away_team": away_name,
        "home_team_code": game.get("home_team_code"),
        "away_team_code": game.get("away_team_code"),
        "bought_team": bought,
        "side": side,
        "opponent_team": away_name if side == "home" else home_name if side == "away" else None,
        "score_home": sh,
        "score_away": sa,
        "score_diff": score_diff,
        "bought_team_margin": bought_m,
        "possession_team": "",
        "possession_id": "",
        "possession_status": "UNAVAILABLE",
        "pregame_home_win_prob": "",
        "pregame_away_win_prob": "",
        "pregame_source": "UNAVAILABLE",
        "market_yes_bid": E.e4_to_cents(entry_q["bid_c"]),
        "market_yes_ask": E.e4_to_cents(entry_q.get("ask_c")),
        "market_last_price": "",
        "market_volume": E.e4_to_cents(entry_q.get("vol")),
        "market_volume_note": "ENTRY_CANDLE_VOLUME_HUNDREDTHS/100_NOT_CUMULATIVE",
        "market_trades": "",
        "market_trades_status": "UNAVAILABLE",
        "entry_implied_prob": E.e4_to_prob(entry_q["bid_c"]),
        "first80_rule_implied_prob": 0.75,
        "home_fouls": "",
        "away_fouls": "",
        "home_timeouts": "",
        "away_timeouts": "",
        "fouls_timeouts_status": "UNAVAILABLE",
        "event_type": None if not entry_play else entry_play.get("actionType"),
        "event_description": None if not entry_play else entry_play.get("description"),
        "rule_80_40": "BUY75_STOP40",
        "win_80_40": (not t40) and won,
        "stopped_40": t40,
        "terminal_yes": won,
        "W": won,
        "T40": t40,
        "T40_wick": "",
        "final_winner": final_winner,
        "final_score_home": fh,
        "final_score_away": fa,
        "final_score": None if fh is None or fa is None else f"{fh}-{fa}",
        "would_have_exited_at_40": t40,
        "held_to_expiration": not t40,
        "exit_kind": exit_kind,
        "exit_price_cents": exit_px,
        "exit_timestamp": None if exit_ts is None else int(exit_ts),
        "exit_timestamp_utc": E.iso(None if exit_ts is None else int(exit_ts)),
        "exit_period": None if not exit_play else exit_play.get("period"),
        "exit_game_clock": E.format_clock(None if not exit_play else exit_play.get("remaining_s")),
        "exit_score_home": E._as_int(None if not exit_play else exit_play.get("score_home")),
        "exit_score_away": E._as_int(None if not exit_play else exit_play.get("score_away")),
        "post_entry_min_yes_bid_cents": E.e4_to_cents(path["min_bid_e4"]),
        "post_entry_min_yes_bid_timestamp": path["min_ts"],
        "last_tradable_yes_bid_cents": E.e4_to_cents(path["last_bid_e4"]),
        "last_tradable_timestamp": path["last_ts"],
        "outcome_80_40": "STOP_40" if t40 else ("WIN_HOLD" if won else "LOSS_HOLD"),
        "hyp_pnl_cents_80_40": (40 - 75) if t40 else ((100 - 75) if won else (0 - 75)),
        "candle_path_not_fill": True,
        "live_execution": False,
    }


def collect_sport(sport: str) -> list[dict]:
    print(f"collect FIRST75 {sport}", flush=True)
    if sport == "NBA":
        nba_qbs = _load("nba_qbs_f75_export", SCRIPTS / "first80_quarter_barrier_survival.py")
        markets = A.load_markets()
        games_list = A.load_games()
        quotes = F.load_quotes(A.NORM / "candles_1m", F.quote_meta_nba_style(markets, games_list))
        raw = F.build_first_reach(markets, games_list, quotes, HIT75_E4, "FIRST_75")
        rows = F.settled(raw, "FIRST_75")
        got = F.joints(rows)
        if got["n"] != F.NBA_F75_N or got["W"] != F.NBA_F75_W or got["W_not_T40"] != F.NBA_F75_NOT40_GIVEN_W:
            raise IdentityHalt(f"NBA FIRST75 {got}")
        xwalk = nba_qbs.load_crosswalk()
        cache: dict = {}
        F.align_with(rows, nba_qbs.align_entry, xwalk, cache, "entry_quarter_bucket")
        asked = [r for r in rows if r.get("entry_bucket") in ("Q2", "Q3")]
        games = E.load_games(A.NORM / "games" / "nba_games.parquet")
        out = [
            enrich_row(r, sport="NBA", quotes=quotes, games=games, align_mod=nba_qbs, pbp_cache=cache, xwalk=xwalk)
            for r in asked
        ]
    elif sport == "WNBA":
        wnba_audit = _load("wnba_8040_f75_export", F.WNBA_SCRIPTS / "wnba_80_40_execution_audit.py")
        wnba_qbs = _load("wnba_qbs_f75_export", F.WNBA_SCRIPTS / "first80_quarter_barrier_survival.py")
        saved = (A.SPLIT_RESEARCH_END, A.SPLIT_VAL_END)
        A.SPLIT_RESEARCH_END = "2025-10-31"
        A.SPLIT_VAL_END = "2026-07-15"
        try:
            markets = wnba_audit.load_markets()
            games_list = wnba_audit.load_games()
            quotes = F.load_quotes(wnba_audit.NORM / "candles_1m", F.quote_meta_wnba(markets, games_list))
            raw = F.build_first_reach(markets, games_list, quotes, HIT75_E4, "FIRST_75")
            rows = F.settled(raw, "FIRST_75")
            xwalk = wnba_qbs.P.load_crosswalk()
            cache = {}
            F.align_with(rows, wnba_qbs.align_entry, xwalk, cache, "entry_quarter_bucket")
            asked = [r for r in rows if r.get("entry_bucket") in ("Q2", "Q3")]
            games = E.load_games(wnba_audit.NORM / "games" / "wnba_games.parquet")
            out = [
                enrich_row(r, sport="WNBA", quotes=quotes, games=games, align_mod=wnba_qbs, pbp_cache=cache, xwalk=xwalk)
                for r in asked
            ]
        finally:
            A.SPLIT_RESEARCH_END, A.SPLIT_VAL_END = saved
    elif sport == "NCAAB":
        ncaab_audit = _load("ncaab_8040_f75_export", F.NCAAB_SCRIPTS / "ncaab_80_40_execution_audit.py")
        ncaab_hbs = _load("ncaab_hbs_f75_export", F.NCAAB_SCRIPTS / "first80_p5_half_barrier_survival.py")
        P5 = ncaab_hbs.P5_CODES
        markets_all = ncaab_audit.load_markets()
        games_all = ncaab_audit.load_games()
        p5_games = [
            g
            for g in games_all
            if g.get("home_team_code") in P5 and g.get("away_team_code") in P5
        ]
        ev = {g["event_id"] for g in p5_games}
        markets = [m for m in markets_all if m["event_id"] in ev]
        quotes = F.load_quotes(ncaab_audit.NORM / "candles_1m", F.quote_meta_nba_style(markets, p5_games))
        raw = F.build_first_reach(markets, p5_games, quotes, HIT75_E4, "FIRST_75")
        rows = F.settled(raw, "FIRST_75")
        xwalk = ncaab_hbs.P.load_crosswalk()
        cache = {}
        F.align_with(rows, ncaab_hbs.align_entry, xwalk, cache, "entry_half_bucket")
        asked = [r for r in rows if r.get("entry_bucket") in ("H1_2", "H2_1")]
        games = E.load_games(ncaab_hbs.GAMES_PATH)
        out = [
            enrich_row(r, sport="NCAAB", quotes=quotes, games=games, align_mod=ncaab_hbs, pbp_cache=cache, xwalk=xwalk)
            for r in asked
        ]
    else:
        raise IdentityHalt(sport)

    counts: dict[tuple[str, str], int] = {}
    for row in out:
        key = (row["sport"], row["slice"])
        counts[key] = counts.get(key, 0) + 1
    for key, n_exp in EXPECTED.items():
        if key[0] != sport:
            continue
        got = counts.get(key, 0)
        if got != n_exp:
            raise IdentityHalt(f"{key} n={got} expected {n_exp}")
    print(f"  n={len(out)}", flush=True)
    return out


def collect() -> list[dict]:
    rows: list[dict] = []
    for sport in ("NBA", "WNBA", "NCAAB"):
        rows.extend(collect_sport(sport))
    if len(rows) != EXPECTED_TOTAL:
        raise IdentityHalt(f"asked-six FIRST75 {len(rows)} != {EXPECTED_TOTAL}")
    four = [r for r in rows if r["sport"] in {"NBA", "NCAAB"}]
    if len(four) != EXPECTED_FOUR:
        raise IdentityHalt(f"derived four FIRST75 {len(four)} != {EXPECTED_FOUR}")
    rows.sort(key=lambda r: (r["game_date"] or "", r["timestamp"] or 0, r["ticker"] or ""))
    return rows


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: "" if row.get(k) is None else row[k] for k in CSV_COLUMNS})


def main() -> None:
    rows = collect()
    dest = OUT / "first75_asked_six.csv"
    write_csv(dest, rows)
    readme = OUT / "README.md"
    readme.write_text(
        "# Asked-six FIRST75 ledger\n\n"
        "Research only. Candle path ≠ fill. LIVE EXECUTION = FALSE.\n\n"
        "Same four + WNBA clock slices as the FIRST80 asked-six export. "
        "τ is FIRST75. Integers must match `docs/research/lebronner/TABLES.md` §2.\n"
        "N asked-six = 1126. Derived four = 913.\n"
    )
    print("csv", dest, "n", len(rows), flush=True)


if __name__ == "__main__":
    main()
