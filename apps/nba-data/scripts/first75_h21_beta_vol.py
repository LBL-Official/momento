#!/usr/bin/env python3
"""NCAAB H2_1 FIRST75 post-entry price vol and score-to-price β.

Compares the asked H2 first-10 FIRST75 slice to the other asked FIRST75
slices (NCAAB H1_2, NBA/WNBA Q2/Q3). Candle path, not fills.

Does not change live FIRST01. Does not retune FIRST75 / T40.
Does not authorize a fade / other-side rule.
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

NBA_SCRIPTS = Path(__file__).resolve().parent
if str(NBA_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(NBA_SCRIPTS))

import first75_slice_not40_given_w as F  # noqa: E402
import nba_80_40_execution_audit as A  # noqa: E402

REPO = Path("/Users/user/Desktop/Momento")
REPORTS = REPO / "research" / "lebronner" / "ncaab_h21_beta_vol"
DOCS = REPO / "docs" / "research" / "lebronner" / "ncaab_h21_beta_vol"
WH_OUT = (
    REPO
    / "Backtesting Suite"
    / "Data"
    / "NBA"
    / "2025-2026"
    / "warehouse"
    / "derived"
    / "nba"
    / "ncaab_h21_beta_vol"
)

ASKED = (
    ("ncaab_p5", "H2_1", "NCAAB 2H first 10"),
    ("ncaab_p5", "H1_2", "NCAAB 1H second 10"),
    ("nba", "Q2", "NBA 2Q"),
    ("nba", "Q3", "NBA 3Q"),
    ("wnba", "Q2", "WNBA 2Q"),
    ("wnba", "Q3", "WNBA 3Q"),
)
TARGET = ("ncaab_p5", "H2_1")
PAIR_LIMIT_S = 180
W600 = 600


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def halt_if(cond: bool, msg: str) -> None:
    if cond:
        raise RuntimeError(msg)


def ols_slope(xs: list[float], ys: list[float]) -> dict:
    n = len(xs)
    if n < 2 or n != len(ys):
        return {"n": n, "beta": None, "intercept": None, "r": None}
    mx = statistics.mean(xs)
    my = statistics.mean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 0:
        return {"n": n, "beta": None, "intercept": None, "r": None}
    beta = sxy / sxx
    intercept = my - beta * mx
    r = None if syy <= 0 else sxy / math.sqrt(sxx * syy)
    return {"n": n, "beta": beta, "intercept": intercept, "r": r}


def summarize(xs: list[float]) -> dict:
    ys = [float(x) for x in xs if x is not None]
    if not ys:
        return {"n": 0, "mean": None, "median": None, "sd": None, "p25": None, "p75": None}
    ys.sort()
    n = len(ys)

    def q(p: float) -> float:
        k = (n - 1) * p
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return ys[int(k)]
        return ys[f] * (c - k) + ys[c] * (k - f)

    return {
        "n": n,
        "mean": statistics.mean(ys),
        "median": statistics.median(ys),
        "sd": statistics.stdev(ys) if n >= 2 else 0.0,
        "p25": q(0.25),
        "p75": q(0.75),
    }


def quality_after(quotes: list[dict], tau: int, window_s: int | None) -> list[dict]:
    end = None if window_s is None else tau + window_s
    out = []
    had = True
    for q in quotes:
        ts = q["ts"]
        if ts <= tau:
            continue
        if end is not None and ts > end:
            break
        if not A.quality(q.get("bid_c"), q.get("ask_c"), q.get("vol"), had):
            continue
        had = True
        if q.get("bid_c") is None:
            continue
        out.append(q)
    return out


def path_vol(quotes: list[dict], tau: int, window_s: int | None) -> dict:
    qs = quality_after(quotes, tau, window_s)
    bids = [q["bid_c"] / 100.0 for q in qs]
    diffs = [bids[i] - bids[i - 1] for i in range(1, len(bids))]
    if not bids:
        return {
            "n_bars": 0,
            "sigma_d_bid_cents": None,
            "range_cents": None,
            "mae_down_cents": None,
            "max_up_cents": None,
        }
    entry = None
    for q in reversed(quotes):
        if q["ts"] <= tau and q.get("bid_c") is not None:
            if A.quality(q.get("bid_c"), q.get("ask_c"), q.get("vol"), True):
                entry = q["bid_c"] / 100.0
                break
    if entry is None:
        entry = bids[0]
    downs = [entry - b for b in bids]
    ups = [b - entry for b in bids]
    return {
        "n_bars": len(bids),
        "sigma_d_bid_cents": None if len(diffs) < 2 else statistics.stdev(diffs),
        "range_cents": max(bids) - min(bids),
        "mae_down_cents": max(downs) if downs else 0.0,
        "max_up_cents": max(ups) if ups else 0.0,
    }


def team_home(rec: dict, game: dict | None) -> bool | None:
    if not game:
        return None
    team = rec.get("team")
    if not team:
        return None
    homes = {game.get("home_team"), game.get("home_team_code")}
    aways = {game.get("away_team"), game.get("away_team_code")}
    homes.discard(None)
    aways.discard(None)
    if team in homes:
        return True
    if team in aways:
        return False
    tl = str(team).lower()
    for h in homes:
        if str(h).lower() == tl:
            return True
    for a in aways:
        if str(a).lower() == tl:
            return False
    return None


def actions_of(pack) -> list[dict] | None:
    if pack is None:
        return None
    if isinstance(pack, tuple):
        return pack[0]
    return pack


def parse_score(row: dict | None) -> tuple[int, int] | None:
    if not row:
        return None
    h, aw = row.get("score_home"), row.get("score_away")
    if h is None or aw is None:
        return None
    try:
        return int(h), int(aw)
    except (TypeError, ValueError):
        return None


def carry_score(row: dict | None, last: tuple[int, int] | None) -> tuple[int, int] | None:
    """NBA Stats often omits scoreHome; enrich stores that as 0-0.

    After a real score has been seen, treat 0-0 as missing and keep last.
    """
    parsed = parse_score(row)
    if parsed is None:
        return last
    if parsed == (0, 0) and last not in {None, (0, 0)}:
        return last
    return parsed


def margin_of(score: tuple[int, int] | None, team_is_home: bool) -> float | None:
    if score is None:
        return None
    h, aw = score
    return float(h - aw) if team_is_home else float(aw - h)


def scoring_steps(actions: list[dict], tau: int, team_is_home: bool) -> list[dict]:
    prev = None
    steps = []
    for a in actions:
        ts = a.get("modeled_wall_ts")
        h, aw = a.get("score_home"), a.get("score_away")
        if h is None or aw is None:
            continue
        margin = (h - aw) if team_is_home else (aw - h)
        if ts is None:
            prev = margin
            continue
        if ts <= tau:
            prev = margin
            continue
        if prev is None:
            prev = margin
            continue
        dm = margin - prev
        if dm != 0:
            steps.append({"ts": int(ts), "d_margin": float(dm), "margin": float(margin)})
        prev = margin
    return steps


def bid_at_or_after(quotes: list[dict], ts: int, limit_s: int) -> float | None:
    for q in quotes:
        if q["ts"] < ts:
            continue
        if q["ts"] - ts > limit_s:
            return None
        if q.get("bid_c") is None:
            continue
        if not A.quality(q.get("bid_c"), q.get("ask_c"), q.get("vol"), True):
            continue
        return q["bid_c"] / 100.0
    return None


def bar_pairs(
    quotes: list[dict],
    actions: list[dict] | None,
    tau: int,
    window_s: int | None,
    team_is_home: bool,
    snap_fn,
) -> list[tuple[float, float]]:
    """Δbid vs Δmargin on consecutive quality minutes (score snapped at the bar)."""
    if not actions or snap_fn is None:
        return []
    qs = quality_after(quotes, tau, window_s)
    pairs = []
    prev_m = None
    prev_b = None
    last_score = None
    for q in qs:
        snap = snap_fn(actions, int(q["ts"]))
        idx = snap.get("snap_idx")
        row = actions[idx] if idx is not None and 0 <= idx < len(actions) else None
        last_score = carry_score(row, last_score)
        margin = margin_of(last_score, team_is_home)
        if margin is None:
            continue
        bid = q["bid_c"] / 100.0
        if prev_m is not None and margin != prev_m and prev_b is not None:
            pairs.append((float(margin - prev_m), bid - prev_b))
        prev_m = margin
        prev_b = bid
    return pairs


def beta_pairs(quotes: list[dict], steps: list[dict], tau: int, window_s: int | None) -> list[tuple[float, float]]:
    end = None if window_s is None else tau + window_s
    pairs = []
    prev_bid = bid_at_or_after(quotes, tau, PAIR_LIMIT_S)
    for st in steps:
        if end is not None and st["ts"] > end:
            break
        b = bid_at_or_after(quotes, st["ts"], PAIR_LIMIT_S)
        if b is None or prev_bid is None:
            if b is not None:
                prev_bid = b
            continue
        pairs.append((st["d_margin"], b - prev_bid))
        prev_bid = b
    return pairs


def slice_metrics(events: list[dict]) -> dict:
    vol600 = [e["vol_w600"] for e in events]
    volfull = [e["vol_full"] for e in events]
    pairs600 = [p for e in events for p in e["pairs_w600"]]
    pairsfull = [p for e in events for p in e["pairs_full"]]
    against600 = [dp for dm, dp in pairs600 if dm < 0]
    for600 = [dp for dm, dp in pairs600 if dm > 0]
    against_abs = [abs(dm) for dm, _dp in pairs600 if dm < 0]
    return {
        "n_events": len(events),
        "n_w": sum(1 for e in events if e["W"]),
        "n_t40": sum(1 for e in events if e["T40"]),
        "p_w": None if not events else sum(1 for e in events if e["W"]) / len(events),
        "p_t40": None if not events else sum(1 for e in events if e["T40"]) / len(events),
        "vol_w600": {
            "sigma": summarize([v["sigma_d_bid_cents"] for v in vol600 if v["sigma_d_bid_cents"] is not None]),
            "range": summarize([v["range_cents"] for v in vol600 if v["range_cents"] is not None]),
            "mae_down": summarize([v["mae_down_cents"] for v in vol600 if v["mae_down_cents"] is not None]),
            "max_up": summarize([v["max_up_cents"] for v in vol600 if v["max_up_cents"] is not None]),
        },
        "vol_full": {
            "sigma": summarize([v["sigma_d_bid_cents"] for v in volfull if v["sigma_d_bid_cents"] is not None]),
            "range": summarize([v["range_cents"] for v in volfull if v["range_cents"] is not None]),
            "mae_down": summarize([v["mae_down_cents"] for v in volfull if v["mae_down_cents"] is not None]),
        },
        "beta_w600": {
            **ols_slope([p[0] for p in pairs600], [p[1] for p in pairs600]),
            "n_events_with_pairs": sum(1 for e in events if e["pairs_w600"]),
            "mean_dP_given_score_against": None if not against600 else statistics.mean(against600),
            "mean_dP_given_score_for": None if not for600 else statistics.mean(for600),
            "n_against": len(against600),
            "n_for": len(for600),
            "mean_abs_d_margin_against": None if not against_abs else statistics.mean(against_abs),
        },
        "beta_full": ols_slope([p[0] for p in pairsfull], [p[1] for p in pairsfull]),
        "entry_margin": summarize([e["entry_margin"] for e in events if e["entry_margin"] is not None]),
    }


def ratio(a: float | None, b: float | None) -> float | None:
    if a is None or b is None or b == 0:
        return None
    return a / b


def beta_usable(b: dict) -> bool:
    """Reject collapsed snap pairing (NBA 0-0 score fills → β≈0, r≈0)."""
    beta = b.get("beta")
    r = b.get("r")
    if beta is None or r is None:
        return False
    return abs(float(beta)) >= 0.3 and float(r) >= 0.4


def beta_ratio(a: dict, b: dict) -> float | None:
    if not beta_usable(a) or not beta_usable(b):
        return None
    return ratio(a.get("beta"), b.get("beta"))


def attach_paths(rows, quotes, games_by_event, pbp_loader, team_home_fn) -> list[dict]:
    out = []
    for rec in rows:
        ticker = rec.get("ticker")
        tau = rec.get("reach_ts")
        qs = quotes.get(ticker, []) if ticker else []
        game = games_by_event.get(rec.get("event_id"))
        home = team_home_fn(rec, game)
        actions = pbp_loader(rec)
        entry_margin = None
        steps = []
        if actions and home is not None:
            steps = scoring_steps(actions, int(tau), home)
            last_score = None
            for a in actions:
                ts = a.get("modeled_wall_ts")
                if ts is None or ts > tau:
                    continue
                last_score = carry_score(a, last_score)
            entry_margin = margin_of(last_score, home)
        ev = {
            "event_id": rec.get("event_id"),
            "sport": rec.get("_sport"),
            "slice": rec.get("entry_bucket"),
            "W": bool(rec.get("W")),
            "T40": bool(rec.get("T40")),
            "reach_ts": tau,
            "entry_margin": entry_margin,
            "vol_w600": path_vol(qs, int(tau), W600),
            "vol_full": path_vol(qs, int(tau), None),
            "pairs_w600": bar_pairs(
                qs, actions, int(tau), W600, home, getattr(pbp_loader, "snap", None)
            )
            if home is not None
            else [],
            "pairs_full": bar_pairs(
                qs, actions, int(tau), None, home, getattr(pbp_loader, "snap", None)
            )
            if home is not None
            else [],
            "n_score_steps": len(steps),
            "home_matched": home is not None,
        }
        out.append(ev)
    return out


class Pbp:
    def __init__(self, pack_fn, snap_fn, cache):
        self.pack_fn = pack_fn
        self.snap_fn = snap_fn
        self.cache = cache

    def __call__(self, rec: dict):
        return actions_of(self.pack_fn(rec, self.cache))

    def snap(self, actions, tau: int):
        return self.snap_fn(actions, tau)


def load_sport(name: str):
    if name == "nba":
        nba_qbs = F.load_module("nba_qbs_bv", F.NBA_SCRIPTS / "first80_quarter_barrier_survival.py")
        markets = A.load_markets()
        games = A.load_games()
        candles = A.NORM / "candles_1m"
        quotes = F.load_quotes(candles, F.quote_meta_nba_style(markets, games))
        raw = F.build_first_reach(markets, games, quotes, F.HIT75, "FIRST_75")
        f75 = F.settled(raw, "FIRST_75")
        xwalk = nba_qbs.load_crosswalk()
        cache: dict = {}
        F.align_with(f75, nba_qbs.align_entry, xwalk, cache, "entry_quarter_bucket")
        gbe = {g["event_id"]: g for g in games}

        def pack(rec, c):
            cw = xwalk.get(rec.get("event_id")) or {}
            nba_id = cw.get("nba_game_id")
            if not nba_id:
                return None
            return nba_qbs._pbp_pack(nba_id, c)

        from pbp import snap_to_entry  # noqa: E402

        return f75, quotes, gbe, Pbp(pack, snap_to_entry, cache)

    if name == "wnba":
        wnba_audit = F.load_module("wnba_8040_bv", F.WNBA_SCRIPTS / "wnba_80_40_execution_audit.py")
        wnba_qbs = F.load_module(
            "wnba_qbs_bv", F.WNBA_SCRIPTS / "first80_quarter_barrier_survival.py"
        )
        saved = (A.SPLIT_RESEARCH_END, A.SPLIT_VAL_END)
        A.SPLIT_RESEARCH_END = "2025-10-31"
        A.SPLIT_VAL_END = "2026-07-15"
        try:
            markets = wnba_audit.load_markets()
            games = wnba_audit.load_games()
            quotes = F.load_quotes(
                wnba_audit.NORM / "candles_1m", F.quote_meta_wnba(markets, games)
            )
            raw = F.build_first_reach(markets, games, quotes, F.HIT75, "FIRST_75")
            f75 = F.settled(raw, "FIRST_75")
            import sys as _sys

            if str(F.WNBA_SCRIPTS) not in _sys.path:
                _sys.path.insert(0, str(F.WNBA_SCRIPTS))
            import wnba_pbp_align as WP  # noqa: E402

            xwalk = WP.load_crosswalk()
            cache = {}
            F.align_with(f75, wnba_qbs.align_entry, xwalk, cache, "entry_quarter_bucket")
            gbe = {g["event_id"]: g for g in games}

            def pack(rec, c):
                cw = xwalk.get(rec.get("event_id")) or {}
                espn_id = cw.get("espn_game_id")
                if not espn_id:
                    return None
                return wnba_qbs._pbp_pack(espn_id, c)

            return f75, quotes, gbe, Pbp(pack, WP.snap_to_entry, cache)
        finally:
            A.SPLIT_RESEARCH_END, A.SPLIT_VAL_END = saved

    if name == "ncaab_p5":
        ncaab_audit = F.load_module("ncaab_8040_bv", F.NCAAB_SCRIPTS / "ncaab_80_40_execution_audit.py")
        ncaab_hbs = F.load_module(
            "ncaab_hbs_bv", F.NCAAB_SCRIPTS / "first80_p5_half_barrier_survival.py"
        )
        import ncaab_pbp_align as NP  # noqa: E402

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
        quotes = F.load_quotes(
            ncaab_audit.NORM / "candles_1m", F.quote_meta_nba_style(markets, p5_games)
        )
        raw = F.build_first_reach(markets, p5_games, quotes, F.HIT75, "FIRST_75")
        f75 = F.settled(raw, "FIRST_75")
        xwalk = ncaab_hbs.P.load_crosswalk()
        cache = {}
        F.align_with(f75, ncaab_hbs.align_entry, xwalk, cache, "entry_half_bucket")
        gbe = {g["event_id"]: g for g in p5_games}

        def pack(rec, c):
            cw = xwalk.get(rec.get("event_id")) or {}
            espn_id = cw.get("espn_game_id")
            if not espn_id:
                return None
            return ncaab_hbs._pbp_pack(espn_id, c)

        return f75, quotes, gbe, Pbp(pack, NP.snap_to_entry, cache)

    raise KeyError(name)


def collect() -> dict:
    by_key: dict[tuple[str, str], list] = {}
    if str(F.NCAAB_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(F.NCAAB_SCRIPTS))
    for sport in ("wnba", "nba", "ncaab_p5"):
        print(f"load {sport}", flush=True)
        rows, quotes, gbe, pbp = load_sport(sport)
        for rec in rows:
            rec["_sport"] = sport
        want = {sl for s, sl, _ in ASKED if s == sport}
        chosen = [r for r in rows if r.get("entry_bucket") in want]
        tagged = attach_paths(chosen, quotes, gbe, pbp, team_home)
        for r, ev in zip(chosen, tagged):
            by_key.setdefault((sport, r.get("entry_bucket")), []).append(ev)

    halt_if(len(by_key.get(TARGET, [])) != 133, f"HALT H2_1 n={len(by_key.get(TARGET, []))}")
    halt_if(len(by_key.get(("ncaab_p5", "H1_2"), [])) != 204, "HALT H1_2")
    halt_if(len(by_key.get(("nba", "Q2"), [])) != 318, "HALT NBA Q2")
    halt_if(len(by_key.get(("nba", "Q3"), [])) != 258, "HALT NBA Q3")
    halt_if(len(by_key.get(("wnba", "Q2"), [])) != 128, "HALT WNBA Q2")
    halt_if(len(by_key.get(("wnba", "Q3"), [])) != 85, "HALT WNBA Q3")

    slices = {}
    for sport, sl, label in ASKED:
        evs = by_key[(sport, sl)]
        slices[f"{sport}:{sl}"] = {"label": label, "sport": sport, "slice": sl, **slice_metrics(evs)}

    rest = [e for (sp, sl), evs in by_key.items() if (sp, sl) != TARGET for e in evs]
    target = by_key[TARGET]
    ncaab_h12 = by_key[("ncaab_p5", "H1_2")]
    q23 = [e for (sp, sl), evs in by_key.items() if sl in {"Q2", "Q3"} for e in evs]
    college_wnba = [
        e
        for (sp, sl), evs in by_key.items()
        if (sp, sl) != TARGET and sp in {"ncaab_p5", "wnba"}
        for e in evs
    ]

    t = slice_metrics(target)
    r = slice_metrics(rest)
    h = slice_metrics(ncaab_h12)
    q = slice_metrics(q23)
    cw = slice_metrics(college_wnba)
    return {
        "written_utc": utc_now(),
        "research_only": True,
        "live_execution_changed": False,
        "candle_path_not_fill": True,
        "definition": (
            "Post-FIRST75 quality minute-close path. β = OLS slope of "
            "Δyes_bid_cents on Δmargin_points on consecutive quality minutes "
            "whose carried snap score changed. W600 = first 600s of wall time. "
            "FULL = remaining candle path. Not a fill. Not a live fade."
        ),
        "slices": slices,
        "comparisons": {
            "h21_vs_rest_asked": {
                "sigma_w600_ratio": ratio(
                    t["vol_w600"]["sigma"]["mean"], r["vol_w600"]["sigma"]["mean"]
                ),
                "beta_w600_ratio": beta_ratio(t["beta_w600"], r["beta_w600"]),
                "beta_usable": beta_usable(r["beta_w600"]),
                "mae_w600_ratio": ratio(
                    t["vol_w600"]["mae_down"]["mean"], r["vol_w600"]["mae_down"]["mean"]
                ),
            },
            "h21_vs_h12": {
                "sigma_w600_ratio": ratio(
                    t["vol_w600"]["sigma"]["mean"], h["vol_w600"]["sigma"]["mean"]
                ),
                "beta_w600_ratio": beta_ratio(t["beta_w600"], h["beta_w600"]),
                "mae_w600_ratio": ratio(
                    t["vol_w600"]["mae_down"]["mean"], h["vol_w600"]["mae_down"]["mean"]
                ),
            },
            "h21_vs_q23": {
                "sigma_w600_ratio": ratio(
                    t["vol_w600"]["sigma"]["mean"], q["vol_w600"]["sigma"]["mean"]
                ),
                "beta_w600_ratio": beta_ratio(t["beta_w600"], q["beta_w600"]),
                "beta_usable": beta_usable(q["beta_w600"]),
            },
            "h21_vs_ncaab_wnba": {
                "sigma_w600_ratio": ratio(
                    t["vol_w600"]["sigma"]["mean"], cw["vol_w600"]["sigma"]["mean"]
                ),
                "beta_w600_ratio": beta_ratio(t["beta_w600"], cw["beta_w600"]),
                "mae_w600_ratio": ratio(
                    t["vol_w600"]["mae_down"]["mean"], cw["vol_w600"]["mae_down"]["mean"]
                ),
                "note": "Primary β comparator when NBA snap scores are unusable.",
            },
        },
        "target": t,
        "rest_asked_five": r,
        "ncaab_h12": h,
        "nba_wnba_q23": q,
        "ncaab_wnba_not_h21": cw,
    }


def _f(x, digits=3):
    if x is None:
        return "—"
    return f"{x:.{digits}f}"


def _beta_cell(b: dict) -> str:
    if not beta_usable(b):
        return "UNRELIABLE"
    return _f(b.get("beta"))


def write_report(doc: dict) -> None:
    t = doc["target"]
    r = doc["rest_asked_five"]
    h = doc["ncaab_h12"]
    q = doc["nba_wnba_q23"]
    cw = doc["ncaab_wnba_not_h21"]
    c = doc["comparisons"]
    lines = [
        "# NCAAB 2H first 10 FIRST75 — why it differs, and post-τ β / vol",
        "",
        "```",
        "LIVE EXECUTION = FALSE",
        "CANDLE PATH ≠ ACTUAL FILL",
        "OBSERVED CALIBRATION DEVIATION ≠ PROVEN MARKET INEFFICIENCY",
        "NO OTHER-SIDE RULE AUTHORIZED",
        "```",
        "",
        "Does not change live FIRST01. Does not retune FIRST75 / T40.",
        "Does not authorize fading H2_1 or buying the opposite contract.",
        "",
        "## 1. Why H2_1 looks different (locked four-cell, before this path scan)",
        "",
        "NCAAB P5 **2H first 10 FIRST75** is the only asked row whose Wilson",
        "interval on P(W) **excludes 75%**: 110/133 = **82.71%**, Wilson",
        "75.39–88.19, two-sided p = 0.045. s_W = 99/110 = **90.00%**.",
        "S = 99/133 = **74.44%**. s_L = 0/23.",
        "",
        "That is not just “NCAAB is different.” Same-sport **1H second 10**",
        "is 152/204 = **74.51%** (includes 75%), s_W = 82.89%, S = 61.76%.",
        "",
        "Selection, not a retune: FIRST75 is the *first* tradable cross of 75¢.",
        "An H2_1 FIRST75 means this yes **never first-crossed 75 in the first",
        "half**. It is a late-arriving 75¢ favorite. Q2/Q3 and H1_2 are",
        "earlier first-crosses. Those are different populations.",
        "",
        "Split caveat (FIRST75 H2_1 winners among settled): IN_SAMPLE 21/24,",
        "VALIDATION 83/103, OOS **6/6**. The 82.7% is not an OOS fact.",
        "One of six asked rows was always going to be the tail. Multiple-testing",
        "applies.",
        "",
        "## 2. What this scan measures",
        "",
        "After τ = FIRST75 timestamp, on quality minute closes:",
        "",
        "- σ = stdev of Δyes_bid (cents) in the first **600s** (W600) and on the full remaining path",
        "- range and max adverse excursion down from the entry close",
        "- β = OLS slope of Δbid_cents on Δmargin_points on consecutive quality",
        "  minutes whose snapped score changed (same snap as clock alignment)",
        "",
        "W600 is the comparable window (H2_1 is a 10-minute clock bin).",
        "FULL mixes remaining game length and is descriptive only.",
        "",
        "## 3. Slice results (W600)",
        "",
        "| Slice | N | P(W) | P(T40) | σ Δbid ¢ mean | range ¢ mean | MAE down ¢ | β ¢/pt | n pairs | mean Δbid | score against |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for _sport, sl, label in ASKED:
        s = doc["slices"][f"{_sport}:{sl}"]
        b = s["beta_w600"]
        v = s["vol_w600"]
        lines.append(
            f"| {label} | {s['n_events']} | {_f(100.0 * s['p_w'], 2)}% | "
            f"{_f(100.0 * s['p_t40'], 2)}% | {_f(v['sigma']['mean'])} | "
            f"{_f(v['range']['mean'])} | {_f(v['mae_down']['mean'])} | "
            f"{_beta_cell(b)} | {b['n']} | {_f(b['mean_dP_given_score_against'])} |"
        )
    lines.extend(
        [
            "",
            f"| **H2_1 target** | {t['n_events']} | {_f(100.0 * t['p_w'], 2)}% | "
            f"{_f(100.0 * t['p_t40'], 2)}% | {_f(t['vol_w600']['sigma']['mean'])} | "
            f"{_f(t['vol_w600']['range']['mean'])} | {_f(t['vol_w600']['mae_down']['mean'])} | "
            f"{_beta_cell(t['beta_w600'])} | {t['beta_w600']['n']} | "
            f"{_f(t['beta_w600']['mean_dP_given_score_against'])} |",
            f"| Rest of asked five (vol ok; β if NBA usable) | {r['n_events']} | {_f(100.0 * r['p_w'], 2)}% | "
            f"{_f(100.0 * r['p_t40'], 2)}% | {_f(r['vol_w600']['sigma']['mean'])} | "
            f"{_f(r['vol_w600']['range']['mean'])} | {_f(r['vol_w600']['mae_down']['mean'])} | "
            f"{_beta_cell(r['beta_w600'])} | {r['beta_w600']['n']} | "
            f"{_f(r['beta_w600']['mean_dP_given_score_against'])} |",
            f"| NCAAB H1_2 ∪ WNBA Q2∪Q3 | {cw['n_events']} | {_f(100.0 * cw['p_w'], 2)}% | "
            f"{_f(100.0 * cw['p_t40'], 2)}% | {_f(cw['vol_w600']['sigma']['mean'])} | "
            f"{_f(cw['vol_w600']['range']['mean'])} | {_f(cw['vol_w600']['mae_down']['mean'])} | "
            f"{_beta_cell(cw['beta_w600'])} | {cw['beta_w600']['n']} | "
            f"{_f(cw['beta_w600']['mean_dP_given_score_against'])} |",
            f"| NBA+WNBA Q2∪Q3 | {q['n_events']} | {_f(100.0 * q['p_w'], 2)}% | "
            f"{_f(100.0 * q['p_t40'], 2)}% | {_f(q['vol_w600']['sigma']['mean'])} | "
            f"{_f(q['vol_w600']['range']['mean'])} | {_f(q['vol_w600']['mae_down']['mean'])} | "
            f"{_beta_cell(q['beta_w600'])} | {q['beta_w600']['n']} | "
            f"{_f(q['beta_w600']['mean_dP_given_score_against'])} |",
            "",
            "## 4. How much more sensitive?",
            "",
            "Ratios are H2_1 / comparator on W600 means. **1.00 = same.**",
            "Primary β comparators exclude NBA when NBA snap β is UNRELIABLE",
            "(collapsed pairing from 0-filled scoreHome). Vol does not use PBP",
            "and remains valid on all rows.",
            "",
            "| Comparator | σ ratio | β ratio | MAE-down ratio |",
            "|---|---:|---:|---:|",
            f"| NCAAB H1_2 (same stack) | {_f(c['h21_vs_h12']['sigma_w600_ratio'])} | "
            f"{_f(c['h21_vs_h12']['beta_w600_ratio'])} | "
            f"{_f(c['h21_vs_h12']['mae_w600_ratio'])} |",
            f"| NCAAB H1_2 ∪ WNBA Q2∪Q3 | {_f(c['h21_vs_ncaab_wnba']['sigma_w600_ratio'])} | "
            f"{_f(c['h21_vs_ncaab_wnba']['beta_w600_ratio'])} | "
            f"{_f(c['h21_vs_ncaab_wnba']['mae_w600_ratio'])} |",
            f"| Rest of asked five | {_f(c['h21_vs_rest_asked']['sigma_w600_ratio'])} | "
            f"{_f(c['h21_vs_rest_asked']['beta_w600_ratio'])} | "
            f"{_f(c['h21_vs_rest_asked']['mae_w600_ratio'])} |",
            f"| NBA+WNBA Q2∪Q3 | {_f(c['h21_vs_q23']['sigma_w600_ratio'])} | "
            f"{_f(c['h21_vs_q23']['beta_w600_ratio'])} | — |",
            "",
            f"H2_1 entry margin (yes − opponent) mean {_f(t['entry_margin']['mean'])}, "
            f"median {_f(t['entry_margin']['median'])} "
            f"(n={t['entry_margin']['n']}). H1_2 mean {_f(h['entry_margin']['mean'])}.",
            "",
            "A β ratio > 1 means a point of score moved the yes close more in H2_1",
            "than in the comparator, on this candle pairing. That is not a fill,",
            "not L2, and not proof the other side is +EV.",
            "",
            "## 5. Other-side hypothesis (not a rule)",
            "",
            "If H2_1 yes overreacts to score against it, the opposite contract",
            "(~25¢ at a 75¢ yes) would be the candidate fade. The descriptive",
            "object is mean Δyes_bid on minutes where snapped margin fell, W600.",
            "Compare to usable β slices only.",
            "",
            f"H2_1: {_f(t['beta_w600']['mean_dP_given_score_against'])}¢ "
            f"(n={t['beta_w600']['n_against']}).",
            f"NCAAB H1_2: {_f(h['beta_w600']['mean_dP_given_score_against'])}¢ "
            f"(n={h['beta_w600']['n_against']}).",
            f"NCAAB H1_2 ∪ WNBA Q2∪Q3: {_f(cw['beta_w600']['mean_dP_given_score_against'])}¢ "
            f"(n={cw['beta_w600']['n_against']}).",
            "",
            "A more negative number is a larger yes drop after a bad score.",
            "H2_1 matching WNBA 3Q (another late-clock high-vol slice) is not",
            "the same as a unique H2_1 fade. That still needs OOS, fees, the",
            "other-side fill, and a locked protocol. It is **not** authorized",
            "as a trade.",
            "",
            "## 6. What this is not",
            "",
            "- Not a live order, fill, or realized P&L.",
            "- Not proof of an inefficient delta or a fade edge.",
            "- Not a retune of FIRST75.",
            "- Not MLB FIRST01.",
            "- H2_1 OOS n=6. Do not deploy on this slice.",
            "",
            "**LIVE DEPLOYMENT: NOT AUTHORIZED**",
            "",
        ]
    )
    text = "\n".join(lines) + "\n"
    payload = json.dumps(doc, indent=2) + "\n"
    for dest in (REPORTS, DOCS, WH_OUT):
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "REPORT.md").write_text(text)
        (dest / "summary.json").write_text(payload)


def main() -> int:
    doc = collect()
    write_report(doc)
    print(
        json.dumps(
            {
                "h21_n": doc["target"]["n_events"],
                "sigma_ratio_vs_rest": doc["comparisons"]["h21_vs_rest_asked"]["sigma_w600_ratio"],
                "beta_ratio_vs_h12": doc["comparisons"]["h21_vs_h12"]["beta_w600_ratio"],
                "beta_ratio_vs_ncaab_wnba": doc["comparisons"]["h21_vs_ncaab_wnba"][
                    "beta_w600_ratio"
                ],
                "out": str(REPORTS),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
