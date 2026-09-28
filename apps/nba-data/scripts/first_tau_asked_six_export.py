#!/usr/bin/env python3
"""Asked-six FIRST{τ} ledger collector.

Same clock slices and path-min columns as first77_asked_six_export.py.
TABLES.md has no FIRST81 / FIRST83. The CSV is the measured book.

Research only. Candle path ≠ fill. Does not change live FIRST01.
Does not invent L2. Does not relabel FIRST75 / FIRST77 / FIRST80 rows.
"""

from __future__ import annotations

import csv
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
HIT40_E4 = 4000
CSV_COLUMNS = list(E.CSV_COLUMNS)


class IdentityHalt(RuntimeError):
    pass


def _load(name: str, path: Path):
    return F75._load(name, path)


def enrich_row(
    rec: dict,
    *,
    sport: str,
    tau: int,
    quotes: dict[str, list],
    games: dict[str, dict],
    align_mod,
    pbp_cache: dict,
    xwalk: dict,
) -> dict:
    hit_e4 = int(tau) * 100
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
        raise IdentityHalt(f"missing FIRST{tau} entry quote {sport} {ticker}")
    bid_e4 = int(entry_q["bid_c"])
    if bid_e4 < hit_e4:
        raise IdentityHalt(f"{ticker}: FIRST{tau} entry bid {bid_e4} < {tau}")
    won = bool(rec["W"])
    t40 = bool(rec["T40"])
    row["first80_rule_implied_prob"] = float(tau) / 100.0
    row["rule_80_40"] = f"BUY{tau}_STOP40"
    row["hyp_pnl_cents_80_40"] = (40 - int(tau)) if t40 else (
        (100 - int(tau)) if won else (0 - int(tau))
    )
    return row


def collect_sport(sport: str, *, tau: int) -> list[dict]:
    hit_e4 = int(tau) * 100
    status = f"FIRST_{int(tau)}"
    print(f"collect FIRST{tau} {sport}", flush=True)
    if sport == "NBA":
        nba_qbs = _load(f"nba_qbs_f{tau}_export", SCRIPTS / "first80_quarter_barrier_survival.py")
        markets = A.load_markets()
        games_list = A.load_games()
        quotes = F.load_quotes(A.NORM / "candles_1m", F.quote_meta_nba_style(markets, games_list))
        raw = F.build_first_reach(markets, games_list, quotes, hit_e4, status)
        rows = F.settled(raw, status)
        xwalk = nba_qbs.load_crosswalk()
        cache: dict = {}
        F.align_with(rows, nba_qbs.align_entry, xwalk, cache, "entry_quarter_bucket")
        asked = [r for r in rows if r.get("entry_bucket") in ("Q2", "Q3")]
        games = E.load_games(A.NORM / "games" / "nba_games.parquet")
        out = [
            enrich_row(
                r,
                sport="NBA",
                tau=tau,
                quotes=quotes,
                games=games,
                align_mod=nba_qbs,
                pbp_cache=cache,
                xwalk=xwalk,
            )
            for r in asked
        ]
    elif sport == "WNBA":
        wnba_audit = _load(f"wnba_8040_f{tau}_export", F.WNBA_SCRIPTS / "wnba_80_40_execution_audit.py")
        wnba_qbs = _load(f"wnba_qbs_f{tau}_export", F.WNBA_SCRIPTS / "first80_quarter_barrier_survival.py")
        saved = (A.SPLIT_RESEARCH_END, A.SPLIT_VAL_END)
        A.SPLIT_RESEARCH_END = "2025-10-31"
        A.SPLIT_VAL_END = "2026-07-15"
        try:
            markets = wnba_audit.load_markets()
            games_list = wnba_audit.load_games()
            quotes = F.load_quotes(wnba_audit.NORM / "candles_1m", F.quote_meta_wnba(markets, games_list))
            raw = F.build_first_reach(markets, games_list, quotes, hit_e4, status)
            rows = F.settled(raw, status)
            xwalk = wnba_qbs.P.load_crosswalk()
            cache = {}
            F.align_with(rows, wnba_qbs.align_entry, xwalk, cache, "entry_quarter_bucket")
            asked = [r for r in rows if r.get("entry_bucket") in ("Q2", "Q3")]
            games = E.load_games(wnba_audit.NORM / "games" / "wnba_games.parquet")
            out = [
                enrich_row(
                    r,
                    sport="WNBA",
                    tau=tau,
                    quotes=quotes,
                    games=games,
                    align_mod=wnba_qbs,
                    pbp_cache=cache,
                    xwalk=xwalk,
                )
                for r in asked
            ]
        finally:
            A.SPLIT_RESEARCH_END, A.SPLIT_VAL_END = saved
    elif sport == "NCAAB":
        ncaab_audit = _load(f"ncaab_8040_f{tau}_export", F.NCAAB_SCRIPTS / "ncaab_80_40_execution_audit.py")
        ncaab_hbs = _load(f"ncaab_hbs_f{tau}_export", F.NCAAB_SCRIPTS / "first80_p5_half_barrier_survival.py")
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
        raw = F.build_first_reach(markets, p5_games, quotes, hit_e4, status)
        rows = F.settled(raw, status)
        xwalk = ncaab_hbs.P.load_crosswalk()
        cache = {}
        F.align_with(rows, ncaab_hbs.align_entry, xwalk, cache, "entry_half_bucket")
        asked = [r for r in rows if r.get("entry_bucket") in ("H1_2", "H2_1")]
        games = E.load_games(ncaab_hbs.GAMES_PATH)
        out = [
            enrich_row(
                r,
                sport="NCAAB",
                tau=tau,
                quotes=quotes,
                games=games,
                align_mod=ncaab_hbs,
                pbp_cache=cache,
                xwalk=xwalk,
            )
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


def collect(tau: int) -> list[dict]:
    rows: list[dict] = []
    for sport in ("NBA", "WNBA", "NCAAB"):
        rows.extend(collect_sport(sport, tau=tau))
    four = [r for r in rows if r["sport"] in {"NBA", "NCAAB"}]
    if not rows:
        raise IdentityHalt(f"asked-six FIRST{tau} is empty")
    if not four:
        raise IdentityHalt(f"derived four FIRST{tau} is empty")
    rows.sort(key=lambda r: (r["game_date"] or "", r["timestamp"] or 0, r["ticker"] or ""))
    return rows


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: "" if row.get(k) is None else row[k] for k in CSV_COLUMNS})


def export_tau(tau: int) -> Path:
    rows = collect(tau)
    out = REPO / "research" / f"first{tau}_asked_six_chatgpt_export"
    dest = out / f"first{tau}_asked_six.csv"
    write_csv(dest, rows)
    four = sum(1 for r in rows if r["sport"] in {"NBA", "NCAAB"})
    wnba = sum(1 for r in rows if r["sport"] == "WNBA")
    cap = int(tau) + 6
    (out / "README.md").write_text(
        f"# Asked-six FIRST{tau} ledger\n\n"
        "Research only. Candle path ≠ fill. LIVE EXECUTION = FALSE.\n\n"
        "Same four + WNBA clock slices as the FIRST80 / FIRST75 / FIRST77 "
        f"asked-six exports. τ is FIRST{tau}. TABLES.md has no FIRST{tau}; "
        "this CSV is the measured book.\n"
        f"N asked-six = {len(rows)}. Derived four = {four}. WNBA complement = {wnba}.\n"
        f"Collector: `apps/nba-data/scripts/first{tau}_asked_six_export.py`.\n"
        "Columns match the FIRST80 asked-six export. "
        f"`rule_80_40` is `BUY{tau}_STOP40`. "
        f"`first80_rule_implied_prob` is 0.{tau}. "
        "Path min is `post_entry_min_yes_bid_cents`. "
        f"{tau}/55 uses entry yes_bid < {cap}.\n"
        "Do not reuse first80 / first75 / first77 CSVs for this book.\n"
    )
    print("csv", dest, "n", len(rows), "four", four, "wnba", wnba, flush=True)
    return dest
