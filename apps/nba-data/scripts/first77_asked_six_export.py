#!/usr/bin/env python3
"""Asked-six FIRST77 ledger for Choosin Texas (77).

Same τ definition as first75_slice_not40_given_w.py, threshold 77.
Same clock slices as the FIRST80 / FIRST75 asked-six exports.
One row per FIRST77 event.

TABLES.md has no FIRST77. This CSV is the measured book. Do not invent
Lebronner FIRST77 rows. Do not reuse first80 or first75 CSVs.

Research only. Candle path ≠ fill. Does not change live FIRST01.
Does not invent L2.
"""

from __future__ import annotations

import csv
import importlib.util
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import first75_asked_six_export as F75  # noqa: E402
import first75_slice_not40_given_w as F  # noqa: E402
import first80_asked_six_chatgpt_export as E  # noqa: E402
import nba_80_40_execution_audit as A  # noqa: E402

REPO = Path("/Users/user/Desktop/Momento")
OUT = REPO / "research" / "first77_asked_six_chatgpt_export"
HIT77_E4 = 7700
HIT40_E4 = 4000
ENTRY_CENTS = 77

CSV_COLUMNS = list(E.CSV_COLUMNS)


class IdentityHalt(RuntimeError):
    pass


def _load(name: str, path: Path):
    return F75._load(name, path)


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
    row = F75.enrich_row(
        rec,
        sport=sport,
        quotes=quotes,
        games=games,
        align_mod=align_mod,
        pbp_cache=pbp_cache,
        xwalk=xwalk,
    )
    ticker = rec["ticker"]
    t0 = int(rec["reach_ts"] or rec["first_80_timestamp"])
    entry_q = F75.quote_at(quotes.get(ticker) or [], t0)
    if entry_q is None or entry_q.get("bid_c") is None:
        raise IdentityHalt(f"missing FIRST77 entry quote {sport} {ticker}")
    bid_e4 = int(entry_q["bid_c"])
    if bid_e4 < HIT77_E4:
        raise IdentityHalt(f"{ticker}: FIRST77 entry bid {bid_e4} < 77")
    won = bool(rec["W"])
    t40 = bool(rec["T40"])
    row["first80_rule_implied_prob"] = 0.77
    row["rule_80_40"] = "BUY77_STOP40"
    row["hyp_pnl_cents_80_40"] = (40 - ENTRY_CENTS) if t40 else (
        (100 - ENTRY_CENTS) if won else (0 - ENTRY_CENTS)
    )
    return row


def collect_sport(sport: str) -> list[dict]:
    print(f"collect FIRST77 {sport}", flush=True)
    if sport == "NBA":
        nba_qbs = _load("nba_qbs_f77_export", SCRIPTS / "first80_quarter_barrier_survival.py")
        markets = A.load_markets()
        games_list = A.load_games()
        quotes = F.load_quotes(A.NORM / "candles_1m", F.quote_meta_nba_style(markets, games_list))
        raw = F.build_first_reach(markets, games_list, quotes, HIT77_E4, "FIRST_77")
        rows = F.settled(raw, "FIRST_77")
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
        wnba_audit = _load("wnba_8040_f77_export", F.WNBA_SCRIPTS / "wnba_80_40_execution_audit.py")
        wnba_qbs = _load("wnba_qbs_f77_export", F.WNBA_SCRIPTS / "first80_quarter_barrier_survival.py")
        saved = (A.SPLIT_RESEARCH_END, A.SPLIT_VAL_END)
        A.SPLIT_RESEARCH_END = "2025-10-31"
        A.SPLIT_VAL_END = "2026-07-15"
        try:
            markets = wnba_audit.load_markets()
            games_list = wnba_audit.load_games()
            quotes = F.load_quotes(wnba_audit.NORM / "candles_1m", F.quote_meta_wnba(markets, games_list))
            raw = F.build_first_reach(markets, games_list, quotes, HIT77_E4, "FIRST_77")
            rows = F.settled(raw, "FIRST_77")
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
        ncaab_audit = _load("ncaab_8040_f77_export", F.NCAAB_SCRIPTS / "ncaab_80_40_execution_audit.py")
        ncaab_hbs = _load("ncaab_hbs_f77_export", F.NCAAB_SCRIPTS / "first80_p5_half_barrier_survival.py")
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
        raw = F.build_first_reach(markets, p5_games, quotes, HIT77_E4, "FIRST_77")
        rows = F.settled(raw, "FIRST_77")
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
    print(f"  n={len(out)} slices={counts}", flush=True)
    return out


def collect() -> list[dict]:
    rows: list[dict] = []
    for sport in ("NBA", "WNBA", "NCAAB"):
        rows.extend(collect_sport(sport))
    four = [r for r in rows if r["sport"] in {"NBA", "NCAAB"}]
    if not rows:
        raise IdentityHalt("asked-six FIRST77 is empty")
    if not four:
        raise IdentityHalt("derived four FIRST77 is empty")
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
    dest = OUT / "first77_asked_six.csv"
    write_csv(dest, rows)
    four = sum(1 for r in rows if r["sport"] in {"NBA", "NCAAB"})
    wnba = sum(1 for r in rows if r["sport"] == "WNBA")
    (OUT / "README.md").write_text(
        "# Asked-six FIRST77 ledger\n\n"
        "Research only. Candle path ≠ fill. LIVE EXECUTION = FALSE.\n\n"
        "Same four + WNBA clock slices as the FIRST80 / FIRST75 asked-six exports. "
        "τ is FIRST77. TABLES.md has no FIRST77; this CSV is the measured book.\n"
        f"N asked-six = {len(rows)}. Derived four = {four}. WNBA complement = {wnba}.\n"
        "Collector: `apps/nba-data/scripts/first77_asked_six_export.py`.\n"
        "Columns match the FIRST80 asked-six export. `rule_80_40` is `BUY77_STOP40`. "
        "`first80_rule_implied_prob` is 0.77. Path min is `post_entry_min_yes_bid_cents`. "
        "77/55 uses entry yes_bid < 83.\n"
        "Do not reuse `first80_asked_six.csv` or `first75_asked_six.csv` for this book.\n"
    )
    print("csv", dest, "n", len(rows), "four", four, "wnba", wnba, flush=True)


if __name__ == "__main__":
    main()
