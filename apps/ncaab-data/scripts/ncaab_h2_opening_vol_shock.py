#!/usr/bin/env python3
"""NCAAB P5 H2 opening adverse-delta normalization — event study.

Completely separate from FIRST75 / FIRST80 / Lebronner. P5 vs P5 only.

ARCHIVED REJECTED MECHANISM. Do not hunt a profitable subset.

Constructs the full H2-open (20:00→15:00 remaining) bar population, stores
continuous H1-relative shock measures, and reports recovery vs controls.
Does not optimize an entry rule. Does not change live FIRST01.

```
RESEARCH ONLY
VOLATILITY SPIKE ≠ MISPRICING
PRICE DECLINE ≠ TEMPORARY DISLOCATION
VOLATILITY NORMALIZATION ≠ PRICE RECOVERY
OBSERVED RECOVERY ≠ EXECUTABLE EDGE
LIVE EXECUTION = FALSE
```
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

NCAAB_SCRIPTS = Path(__file__).resolve().parent
NBA_SCRIPTS = Path("/Users/user/Desktop/Momento/apps/nba-data/scripts")
for p in (NCAAB_SCRIPTS, NBA_SCRIPTS):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import first75_slice_not40_given_w as F  # noqa: E402
import first80_p5_half_barrier_survival as HBS  # noqa: E402
import nba_80_40_execution_audit as A  # noqa: E402
import ncaab_80_40_execution_audit as AUDIT  # noqa: E402
import ncaab_pbp_align as NP  # noqa: E402
import ncaab_pbp_espn_ingest as ING  # noqa: E402

REPO = Path("/Users/user/Desktop/Momento")
REPORTS = REPO / "research" / "ncaab_h2_opening_vol_shock"
DOCS = REPO / "docs" / "research" / "ncaab_h2_opening_vol_shock"
WH_OUT = (
    REPO
    / "Backtesting Suite"
    / "Data"
    / "NCAAB"
    / "2025-2026"
    / "warehouse"
    / "derived"
    / "ncaab"
    / "h2_opening_vol_shock"
)

P5_GAMES_EXPECTED = 849
H1_MIN_DIFFS = 8
PAIR_GAP_MAX_S = 90
H2_OPEN_REM_LO = 900.0
H2_OPEN_REM_HI = 1200.0
LOOKAHEADS = (1, 2, 3, 5, 10)
POST_VOL_S = 300
PATH_S = 600
LOOKAHEAD_SLACK_S = 90
CLOSE_BANDS = (5, 7, 10, 12)
PRIMARY_P = 0.80
BOUNDED_DM = (1.0, 4.0)
PROP_BAND = (0.25, 0.50)
MIN_MARGIN_FOR_PCT = 4.0
SPLIT_RESEARCH_END = "2025-12-31"
SPLIT_VAL_END = "2026-03-15"

VERDICT = {
    "status": "NEGATIVE",
    "title": "VOLATILITY NORMALIZATION FAILS AS A RECOVERY MECHANISM",
    "short_title": "QUIET DOES NOT MEAN REVERSION",
    "interpretation": "QUIET TAPE = NEW PRICE ACCEPTANCE",
    "close_5": "DESCRIPTIVE_OBSERVATION",
    "further_optimization_authorized": False,
    "entry_rule_authorized": False,
    "fade_rule_authorized": False,
    "normalization_buy_authorized": False,
    "live_execution": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def halt_if(cond: bool, msg: str) -> None:
    if cond:
        raise RuntimeError(msg)


def pctile(xs: list[float], p: float) -> float | None:
    ys = sorted(float(x) for x in xs)
    if not ys:
        return None
    k = (len(ys) - 1) * p
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return ys[int(k)]
    return ys[f] * (c - k) + ys[c] * (k - f)


def summarize(xs: list[float]) -> dict:
    ys = [float(x) for x in xs if x is not None]
    if not ys:
        return {"n": 0, "mean": None, "median": None, "sd": None}
    return {
        "n": len(ys),
        "mean": statistics.mean(ys),
        "median": statistics.median(ys),
        "sd": statistics.stdev(ys) if len(ys) >= 2 else 0.0,
    }


def h1_baseline(diffs: list[float]) -> dict | None:
    if len(diffs) < H1_MIN_DIFFS:
        return None
    absx = [abs(d) for d in diffs]
    return {
        "n": len(diffs),
        "mean_abs": statistics.mean(absx),
        "median_abs": statistics.median(absx),
        "sigma_signed": statistics.stdev(diffs),
        "sigma_abs": statistics.stdev(absx),
        "p80_abs": pctile(absx, 0.80),
        "p85_abs": pctile(absx, 0.85),
        "p90_abs": pctile(absx, 0.90),
        "p95_abs": pctile(absx, 0.95),
    }


def z_vol(abs_dp: float, baseline: dict | None) -> dict:
    if not baseline:
        return {"z_abs": None, "z_signed_scale": None, "r_shock": None}
    mu = baseline["mean_abs"]
    sig_abs = baseline["sigma_abs"]
    sig_s = baseline["sigma_signed"]
    p80 = baseline["p80_abs"]
    return {
        "z_abs": None if not sig_abs else (abs_dp - mu) / sig_abs,
        "z_signed_scale": None if not sig_s else (abs_dp - mu) / sig_s,
        "r_shock": None if not p80 else abs_dp / p80,
    }


def in_h2_open(period, remaining_s, phase: str | None) -> bool:
    if phase != "IN_PERIOD" or period != 2 or remaining_s is None:
        return False
    rem = float(remaining_s)
    return H2_OPEN_REM_LO < rem <= H2_OPEN_REM_HI


def in_h1_baseline(period, phase: str | None) -> bool:
    return phase == "IN_PERIOD" and period == 1


def score_tags(m_pre: float | None, m_post: float | None) -> dict:
    if m_pre is None or m_post is None:
        return {
            "abs_dm": None,
            "pct_abs_dm": None,
            "bounded_info": False,
            "prop_band": False,
            "deterioration": False,
            **{f"close_{c}": False for c in CLOSE_BANDS},
        }
    dm = float(m_post) - float(m_pre)
    abs_dm = abs(dm)
    pct = None
    if abs(float(m_pre)) >= MIN_MARGIN_FOR_PCT:
        pct = abs_dm / abs(float(m_pre))
    return {
        "abs_dm": abs_dm,
        "pct_abs_dm": pct,
        "bounded_info": BOUNDED_DM[0] <= abs_dm <= BOUNDED_DM[1],
        "prop_band": pct is not None and PROP_BAND[0] <= pct <= PROP_BAND[1],
        "deterioration": dm < 0,
        **{f"close_{c}": abs(float(m_pre)) <= c for c in CLOSE_BANDS},
    }


def pick_adverse(dps: dict[str, float | None]) -> tuple[str | None, bool]:
    avail = {k: v for k, v in dps.items() if v is not None}
    if not avail:
        return None, False
    if len(avail) == 2 and avail["home"] == avail["away"]:
        return None, True
    return min(avail, key=avail.get), False


def vol_normalized(post_mean_abs: float | None, h1_mean_abs: float | None) -> bool | None:
    if post_mean_abs is None or h1_mean_abs is None:
        return None
    return post_mean_abs <= h1_mean_abs


def quality_rows(quotes: list[dict]) -> list[dict]:
    had = True
    out = []
    for q in quotes:
        if not A.quality(q.get("bid_c"), q.get("ask_c"), q.get("vol"), had):
            continue
        had = True
        if q.get("bid_c") is None:
            continue
        out.append(q)
    return out


def quality_pairs(quotes: list[dict], max_gap_s: int = PAIR_GAP_MAX_S) -> list[dict]:
    qs = quality_rows(quotes)
    out = []
    for i in range(1, len(qs)):
        prev, cur = qs[i - 1], qs[i]
        gap = int(cur["ts"]) - int(prev["ts"])
        if gap <= 0 or gap > max_gap_s:
            continue
        out.append(
            {
                "prev_ts": int(prev["ts"]),
                "ts": int(cur["ts"]),
                "prev_bid_c": prev["bid_c"],
                "bid_c": cur["bid_c"],
                "dp_cents": (cur["bid_c"] - prev["bid_c"]) / 100.0,
            }
        )
    return out


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


def phase_at(ts: int, row: dict | None, bounds: dict, first_start, last_end) -> str:
    if row is None:
        if first_start is not None and ts < first_start:
            return "GAME_NOT_STARTED"
        return "UNALIGNED"
    if last_end is not None and ts > last_end + 30:
        return "GAME_ENDED"
    if first_start is not None and ts < first_start:
        return "GAME_NOT_STARTED"
    period = row.get("period")
    if period is None:
        return "UNALIGNED"
    nxt = bounds.get(int(period) + 1, {}).get("start")
    ended = bounds.get(int(period), {}).get("end")
    if ended is not None and nxt is not None and ended < ts < nxt:
        return "INTERMISSION"
    return "IN_PERIOD"


def build_snapper(actions: list[dict]):
    import bisect

    bounds = NP.period_bounds(actions)
    usable = [a for a in actions if a.get("modeled_wall_ts") is not None]
    usable.sort(key=lambda a: (int(a["modeled_wall_ts"]), a.get("idx") or 0))
    walls = [int(a["modeled_wall_ts"]) for a in usable]
    carried = []
    last = None
    for a in usable:
        last = carry_score(a, last)
        carried.append(last)
    first_start = None if 1 not in bounds else bounds[1].get("start")
    last_end = None
    for p in sorted(bounds):
        if bounds[p].get("end") is not None:
            last_end = bounds[p]["end"]
    cache: dict[int, dict] = {}

    def at(ts: int) -> dict:
        key = int(ts)
        if key in cache:
            return cache[key]
        i = bisect.bisect_right(walls, key) - 1
        row = usable[i] if i >= 0 else None
        period = None if row is None else row.get("period")
        rem = None if row is None else row.get("remaining_s")
        rec = {
            "phase": phase_at(key, row, bounds, first_start, last_end),
            "period": period,
            "remaining_s": rem,
            "score": None if i < 0 else carried[i],
        }
        cache[key] = rec
        return rec

    return at


def match_side(team: str | None, game: dict) -> str | None:
    if not team:
        return None
    homes = {game.get("home_team"), game.get("home_team_code")}
    aways = {game.get("away_team"), game.get("away_team_code")}
    homes.discard(None)
    aways.discard(None)
    if team in homes:
        return "home"
    if team in aways:
        return "away"
    tl = str(team).lower()
    for h in homes:
        if str(h).lower() == tl:
            return "home"
    for a in aways:
        if str(a).lower() == tl:
            return "away"
    return None


def split_of(game_date: str | None) -> str:
    if not game_date:
        return "UNSPLIT"
    if game_date <= SPLIT_RESEARCH_END:
        return "IN_SAMPLE"
    if game_date <= SPLIT_VAL_END:
        return "VALIDATION"
    return "OOS"


def bid_after(quotes: list[dict], t0: int, horizon_s: int, slack_s: int) -> float | None:
    target = t0 + horizon_s
    best = None
    for q in quotes:
        ts = int(q["ts"])
        if ts < target:
            continue
        if ts > target + slack_s:
            break
        if q.get("bid_c") is None:
            continue
        if not A.quality(q.get("bid_c"), q.get("ask_c"), q.get("vol"), True):
            continue
        best = q["bid_c"] / 100.0
        break
    return best


def path_excursions(quotes: list[dict], t0: int, entry_cents: float, window_s: int) -> dict:
    bids = []
    for q in quotes:
        ts = int(q["ts"])
        if ts <= t0:
            continue
        if ts > t0 + window_s:
            break
        if q.get("bid_c") is None:
            continue
        if not A.quality(q.get("bid_c"), q.get("ask_c"), q.get("vol"), True):
            continue
        bids.append(q["bid_c"] / 100.0)
    if not bids:
        return {"mae_down": None, "mfe_up": None, "n_bars": 0}
    downs = [entry_cents - b for b in bids]
    ups = [b - entry_cents for b in bids]
    return {"mae_down": max(downs), "mfe_up": max(ups), "n_bars": len(bids)}


def post_abs_diffs(quotes: list[dict], t0: int, window_s: int) -> list[float]:
    qs = [q for q in quality_rows(quotes) if t0 < int(q["ts"]) <= t0 + window_s]
    out = []
    for i in range(1, len(qs)):
        gap = int(qs[i]["ts"]) - int(qs[i - 1]["ts"])
        if 0 < gap <= PAIR_GAP_MAX_S:
            out.append(abs(qs[i]["bid_c"] - qs[i - 1]["bid_c"]) / 100.0)
    return out


def annotate_pairs(pairs: list[dict], snap_fn, want_h1: bool, want_h2: bool) -> list[dict]:
    out = []
    for p in pairs:
        cur = snap_fn(p["ts"])
        prev = snap_fn(p["prev_ts"])
        h1 = in_h1_baseline(prev["period"], prev["phase"]) and in_h1_baseline(
            cur["period"], cur["phase"]
        )
        h2 = in_h2_open(cur["period"], cur["remaining_s"], cur["phase"])
        if want_h1 and not h1:
            continue
        if want_h2 and not h2:
            continue
        rec = dict(p)
        rec["cur_snap"] = cur
        rec["prev_snap"] = prev
        out.append(rec)
    return out


def game_events(game: dict, sides: dict, actions: list[dict]) -> list[dict]:
    snap_fn = build_snapper(actions)
    per = {}
    pooled_diffs = []
    for side, rec in sides.items():
        qs = rec["quotes"]
        pairs = quality_pairs(qs)
        h1_pairs = annotate_pairs(pairs, snap_fn, True, False)
        h2_pairs = annotate_pairs(pairs, snap_fn, False, True)
        pooled_diffs.extend(p["dp_cents"] for p in h1_pairs)
        per[side] = {
            "quotes": qs,
            "market": rec["market"],
            "h1": h1_baseline([p["dp_cents"] for p in h1_pairs]),
            "h2": {p["ts"]: p for p in h2_pairs},
            "W": A.settled_yes(rec["market"]),
        }
    if per["home"]["h1"] is None and per["away"]["h1"] is None:
        return []
    game_h1 = h1_baseline(pooled_diffs)

    ts_set = set(per["home"]["h2"]) | set(per["away"]["h2"])
    events = []
    for ts in sorted(ts_set):
        dps = {
            "home": None if ts not in per["home"]["h2"] else per["home"]["h2"][ts]["dp_cents"],
            "away": None if ts not in per["away"]["h2"] else per["away"]["h2"][ts]["dp_cents"],
        }
        i_star, tie = pick_adverse(dps)
        if i_star is None:
            continue
        star = per[i_star]["h2"][ts]
        base = per[i_star]["h1"]
        abs_dp = abs(star["dp_cents"])
        zv = z_vol(abs_dp, base)
        m_pre = margin_of(star["prev_snap"]["score"], i_star == "home")
        m_post = margin_of(star["cur_snap"]["score"], i_star == "home")
        tags = score_tags(m_pre, m_post)
        entry = star["bid_c"] / 100.0
        qs = per[i_star]["quotes"]
        rets = {}
        for h in LOOKAHEADS:
            nxt = bid_after(qs, ts, h * 60, LOOKAHEAD_SLACK_S)
            rets[f"r_{h}"] = None if nxt is None else nxt - entry
            rets[f"p_{h}"] = nxt
        post = post_abs_diffs(qs, ts, POST_VOL_S)
        post_mean = None if len(post) < 2 else statistics.mean(post)
        exc = path_excursions(qs, ts, entry, PATH_S)
        p80 = None if not base else base["p80_abs"]
        shock = bool(
            base
            and p80 is not None
            and abs_dp > p80
            and star["dp_cents"] < 0
        )
        events.append(
            {
                "event_id": game["event_id"],
                "game_date": game.get("game_date"),
                "split": split_of(game.get("game_date")),
                "team": per[i_star]["market"].get("team"),
                "side": i_star,
                "opposing_team": per["away" if i_star == "home" else "home"]["market"].get(
                    "team"
                ),
                "ticker": per[i_star]["market"].get("ticker"),
                "entry_ts": ts,
                "entry_clock_remaining_s": star["cur_snap"]["remaining_s"],
                "entry_price_cents": entry,
                "shock_delta": star["dp_cents"],
                "abs_shock": abs_dp,
                "tie_delta": tie,
                "h1_n": None if not base else base["n"],
                "h1_mean_abs": None if not base else base["mean_abs"],
                "h1_median_abs": None if not base else base["median_abs"],
                "h1_sigma": None if not base else base["sigma_signed"],
                "h1_p80_abs": p80,
                "h1_p90_abs": None if not base else base["p90_abs"],
                "h1_p95_abs": None if not base else base["p95_abs"],
                "game_h1_p80_abs": None if not game_h1 else game_h1["p80_abs"],
                "z_abs": zv["z_abs"],
                "r_shock": zv["r_shock"],
                "above_p80": bool(base and p80 is not None and abs_dp > p80),
                "above_p90": bool(base and base["p90_abs"] is not None and abs_dp > base["p90_abs"]),
                "above_p95": bool(base and base["p95_abs"] is not None and abs_dp > base["p95_abs"]),
                "primary_shock": shock,
                "pre_shock_margin": m_pre,
                "post_shock_margin": m_post,
                **tags,
                **rets,
                "post_vol_mean_abs": post_mean,
                "vol_norm": vol_normalized(post_mean, None if not base else base["mean_abs"]),
                "mae_down": exc["mae_down"],
                "mfe_up": exc["mfe_up"],
                "W": per[i_star]["W"],
            }
        )
    shocks_seen = 0
    for ev in events:
        if ev["primary_shock"]:
            shocks_seen += 1
            ev["first_shock_in_game"] = shocks_seen == 1
        else:
            ev["first_shock_in_game"] = False
    return events


def load_universe():
    games = [
        g
        for g in AUDIT.load_games()
        if g.get("home_team_code") in ING.P5_CODES and g.get("away_team_code") in ING.P5_CODES
    ]
    halt_if(len(games) != P5_GAMES_EXPECTED, f"HALT P5 games {len(games)}")
    ev = {g["event_id"] for g in games}
    markets = [m for m in AUDIT.load_markets() if m["event_id"] in ev]
    print("load candles", flush=True)
    quotes = F.load_quotes(
        AUDIT.NORM / "candles_1m", F.quote_meta_nba_style(markets, games)
    )
    xwalk = HBS.P.load_crosswalk()
    cache: dict = {}
    games_by = {g["event_id"]: g for g in games}
    by_event = defaultdict(list)
    for m in markets:
        by_event[m["event_id"]].append(m)
    return games_by, by_event, quotes, xwalk, cache


def collect() -> dict:
    games_by, by_event, quotes, xwalk, cache = load_universe()
    events = []
    n_pbp = 0
    n_usable = 0
    n_two_sides = 0
    for event_id, ms in by_event.items():
        game = games_by[event_id]
        sides = {}
        for m in ms:
            side = match_side(m.get("team"), game)
            if side is None:
                continue
            sides[side] = {"market": m, "quotes": quotes.get(m["ticker"], [])}
        if set(sides) != {"home", "away"}:
            continue
        n_two_sides += 1
        cw = xwalk.get(event_id) or {}
        espn_id = cw.get("espn_game_id")
        if cw.get("match_status") != "MATCHED" or not espn_id:
            continue
        actions = HBS._pbp_pack(espn_id, cache)
        if not actions:
            continue
        n_pbp += 1
        evs = game_events(game, sides, actions)
        if evs:
            n_usable += 1
        events.extend(evs)

    halt_if(not events, "HALT no H2-open events")
    return {
        "written_utc": utc_now(),
        "research_only": True,
        "live_execution_changed": False,
        "separate_from_first75": True,
        "universe": "KXNCAAMBGAME 2025-26 P5 vs P5",
        "p5_games": P5_GAMES_EXPECTED,
        "n_two_sided": n_two_sides,
        "n_matched_pbp": n_pbp,
        "n_games_with_h2_bars": n_usable,
        "n_events": len(events),
        "events": events,
    }


def subset(events: list[dict], pred) -> list[dict]:
    return [e for e in events if pred(e)]


def block(events: list[dict], label: str) -> dict:
    rs = {h: summarize([e.get(f"r_{h}") for e in events]) for h in LOOKAHEADS}
    return {
        "label": label,
        "n": len(events),
        "n_games": len({e["event_id"] for e in events}),
        "mean_shock": summarize([e["shock_delta"] for e in events]),
        "mean_abs_shock": summarize([e["abs_shock"] for e in events]),
        "mean_r_shock": summarize([e["r_shock"] for e in events if e.get("r_shock") is not None]),
        "returns": rs,
        "p_r5_pos": None
        if not any(e.get("r_5") is not None for e in events)
        else sum(1 for e in events if e.get("r_5") is not None and e["r_5"] > 0)
        / sum(1 for e in events if e.get("r_5") is not None),
        "mae": summarize([e["mae_down"] for e in events]),
        "mfe": summarize([e["mfe_up"] for e in events]),
        "p_vol_norm": None
        if not any(e.get("vol_norm") is not None for e in events)
        else sum(1 for e in events if e.get("vol_norm") is True)
        / sum(1 for e in events if e.get("vol_norm") is not None),
        "p_w": None
        if not any(e.get("W") is not None for e in events)
        else sum(1 for e in events if e.get("W") is True)
        / sum(1 for e in events if e.get("W") is not None),
    }


def object_c(events: list[dict]) -> dict:
    norm = [e for e in events if e.get("vol_norm") is True]
    none = [e for e in events if e.get("vol_norm") is False]
    return {
        "shock_and_norm": block(norm, "shock ∧ vol_norm"),
        "shock_and_no_norm": block(none, "shock ∧ ¬vol_norm"),
    }


def analyze(doc: dict) -> dict:
    ev = doc["events"]
    shock = subset(ev, lambda e: e["primary_shock"])
    ordinary = subset(ev, lambda e: e["shock_delta"] < 0 and not e["above_p80"])
    shock_b = subset(shock, lambda e: e["bounded_info"] and e["deterioration"])
    shock_bp = subset(shock_b, lambda e: e["prop_band"])
    ordinary_b = subset(ordinary, lambda e: e["bounded_info"] and e["deterioration"])
    close_blocks = {}
    for c in CLOSE_BANDS:
        key = f"close_{c}"
        close_blocks[key] = {
            "shock": block(subset(shock, lambda e, k=key: e[k]), f"shock ∩ {key}"),
            "ordinary": block(
                subset(ordinary, lambda e, k=key: e[k]), f"ordinary ∩ {key}"
            ),
            "shock_bounded": block(
                subset(shock_b, lambda e, k=key: e[k]), f"shock ∩ bounded ∩ {key}"
            ),
        }
    splits = {}
    for name in ("IN_SAMPLE", "VALIDATION", "OOS"):
        splits[name] = {
            "shock": block(subset(shock, lambda e, n=name: e["split"] == n), f"{name} shock"),
            "ordinary": block(
                subset(ordinary, lambda e, n=name: e["split"] == n), f"{name} ordinary"
            ),
        }
    first_only = subset(shock, lambda e: e["first_shock_in_game"])
    return {
        "all_h2_open": block(ev, "all H2-open bars with unique i*"),
        "primary_shock": block(shock, "primary: |ΔP|>H1 p80 and ΔP<0"),
        "ordinary_adverse": block(ordinary, "control: ΔP<0 and |ΔP|≤H1 p80"),
        "shock_bounded": block(shock_b, "shock ∩ |ΔM|∈[1,4] ∩ deterioration"),
        "shock_bounded_prop": block(
            shock_bp, "shock ∩ bounded ∩ prop 25–50% ∩ |M_pre|≥4"
        ),
        "ordinary_bounded": block(ordinary_b, "ordinary ∩ |ΔM|∈[1,4] ∩ deterioration"),
        "close_bands": close_blocks,
        "object_c_primary": object_c(shock),
        "object_c_bounded": object_c(shock_b),
        "first_shock_only": block(first_only, "first primary shock per game"),
        "splits": splits,
    }


def _f(x, d=3):
    if x is None:
        return "—"
    return f"{x:.{d}f}"


def _row(b: dict) -> str:
    r = b["returns"]
    return (
        f"| {b['label']} | {b['n']} | {b['n_games']} | "
        f"{_f(b['mean_shock']['mean'])} | {_f((r[5] or {}).get('mean'))} | "
        f"{_f((r[10] or {}).get('mean'))} | {_f(100.0 * b['p_r5_pos'] if b['p_r5_pos'] is not None else None, 1)} | "
        f"{_f(100.0 * b['p_vol_norm'] if b['p_vol_norm'] is not None else None, 1)} | "
        f"{_f(100.0 * b['p_w'] if b['p_w'] is not None else None, 1)} |"
    )


def write_outputs(raw: dict, stats: dict) -> None:
    slim = {k: v for k, v in raw.items() if k != "events"}
    slim["analysis"] = stats
    slim["verdict"] = VERDICT
    slim["rejected_mechanism"] = True
    slim["further_optimization_authorized"] = False
    payload = json.dumps(slim, indent=2) + "\n"
    events_txt = "\n".join(json.dumps(e) for e in raw["events"]) + "\n"
    spec = SPEC_TEXT
    report = write_report_text(raw, stats)
    for dest in (REPORTS, DOCS, WH_OUT):
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "SPEC.md").write_text(spec)
        (dest / "CONCLUSION.md").write_text(CONCLUSION_TEXT)
        (dest / "REPORT.md").write_text(report)
        (dest / "summary.json").write_text(payload)
        (dest / "events.jsonl").write_text(events_txt)


SPEC_TEXT = """# H2 OPENING ADVERSE DELTA NORMALIZATION — frozen object

```
RESULT: NEGATIVE
REJECTED MECHANISM
DO NOT OPTIMIZE A PROFITABLE SUBSET
CLOSE_5 = DESCRIPTIVE OBSERVATION
LIVE EXECUTION = FALSE
```

Title: **VOLATILITY NORMALIZATION FAILS AS A RECOVERY MECHANISM**
Short: **QUIET DOES NOT MEAN REVERSION**
Interpretation: **QUIET TAPE = NEW PRICE ACCEPTANCE**

Completely separate from FIRST75 / FIRST80 / Lebronner.
Does not change live FIRST01. P5 vs P5 `KXNCAAMBGAME` 2025-26 only.
Formal freeze: `CONCLUSION.md`.

## One sentence

Within the first five minutes of H2, does an unusually large, bounded
adverse price delta — relative to that game's H1 volatility regime —
subsequently recover when volatility normalizes?

## Universe

- Sport: NCAAB men's
- Filter: both teams in Power-5 codes
- Identity: 849 P5 vs P5 games (warehouse gate)
- Requires: both yes contracts, MATCHED ESPN PBP
- Price: quality `yes_bid_close` (uncrossed, spread ≤ 10¢). Candle path ≠ fill.

## Clock

Regulation 2 × 20:00. ESPN observed wallclock snap.

- t0 conceptual: 20:00 remaining (H2 start)
- H1 baseline: period = 1, phase = IN_PERIOD (halftime INTERMISSION excluded)
- H2 shock window: period = 2, phase = IN_PERIOD, `900 < remaining ≤ 1200`
- Consecutive quality minutes only if wall gap ≤ 90s (halts HT jumps)

## Baseline (stored, not collapsed)

Per damaged contract, and game-pooled:

- n, mean |ΔP|, median |ΔP|, σ(ΔP), σ(|ΔP|)
- p80 / p85 / p90 / p95 of |ΔP|
- Thin H1 (n < 8 diffs) cannot be a primary shock

Continuous shock measures (always stored):

- Z_abs = (|ΔP| − mean_abs) / σ(|ΔP|)
- R_shock = |ΔP| / Q_0.80

Primary *flag* (not the only rows): |ΔP| > H1 p80 and ΔP < 0.

## Score tags (not optimized)

- |ΔM| stored continuously
- bounded_info: |ΔM| ∈ [1, 4]
- pct = |ΔM| / |M_pre| only if |M_pre| ≥ 4 (avoids 2→1 as “50%”)
- prop_band: pct ∈ [25%, 50%]
- CLOSE_5 / 7 / 10 / 12 on |M_pre|
- All bands reported. None selected on recovery.

## Entry object

i* = argmin_i ΔP_i among the two yes contracts that have a quality
ΔP on that minute. Ties discarded.

## Hypothesis

H0: E[R_post | shock] ≤ E[R_post | ordinary adverse control]
H1: E[R_post | shock] > E[R_post | ordinary adverse control]

Control = H2-open minutes with ΔP < 0 and |ΔP| ≤ that contract's H1 p80.

## Objects (tested separately)

- A: does post-entry mean |ΔP| over 5 minutes return to ≤ H1 mean |ΔP|?
- B: R at +1 / +2 / +3 / +5 / +10 minutes (bid close − entry close)
- C: E[R | shock ∧ vol_norm] vs E[R | shock ∧ ¬vol_norm]

## Splits (calendar, frozen before this object)

IN_SAMPLE: game_date ≤ 2025-12-31
VALIDATION: 2026-01-01 … 2026-03-15
OOS: game_date > 2026-03-15

Descriptive only. Close bands are not selected on VAL.

## Archive rule

This object is **closed**. Do not add score bands, close thresholds,
or shock percentiles to rescue R5. CLOSE_5 stays a descriptive
observation and requires independent replication before it can even
be a *hypothesis*, not a condition.

## What this is not

- Not FIRST75 / FIRST80 / T40 / Lebronner
- Not a live fade or other-side rule
- Not L2, mid, fees, or fills
- Not W9
"""


CONCLUSION_TEXT = """# VOLATILITY NORMALIZATION FAILS AS A RECOVERY MECHANISM

**QUIET DOES NOT MEAN REVERSION**

```
H2 OPENING ADVERSE-DELTA NORMALIZATION

RESULT: NEGATIVE

An adverse price movement exceeding a contract's
own first-half volatility regime does not demonstrate
a systematic temporary component.

Volatility normalization does not predict price recovery.
The contract frequently remains at its newly repriced level.

Restricting the event to bounded score deterioration,
proportional margin changes, or the first qualifying
shock does not rescue the hypothesis.

The apparent unconditional +0.14¢ R5 is economically
small, dispersion-heavy, and reverses OOS.

NO ENTRY RULE AUTHORIZED
NO FADE RULE AUTHORIZED
NO NORMALIZATION-BUY RULE AUTHORIZED

CLOSE_5 = DESCRIPTIVE OBSERVATION
CLOSE_5 ≠ AUTHORIZED CONDITION
CLOSE_5 → REQUIRES INDEPENDENT REPLICATION

DO NOT HUNT A PROFITABLE SUBSET

LIVE EXECUTION = FALSE
```

This is a clean negative. It answers the hypothesis rather than
failing to find a profitable threshold.

## Rejected causal chain

```
abnormal adverse price shock
  → temporary dislocation
  → volatility normalization
  → price recovery
```

Broken at multiple points (candle path, not fills):

1. Vol does not preferentially normalize after the shock
   (45.6% < 53.6% ordinary adverse).
2. Unconditional R5 +0.14¢ vs control +0.00¢ is trivial
   (sd 8.5¢, median 0) and reverses OOS.
3. Object C is the wrong sign:
   vol_norm R5 = −0.50¢; elevated-vol R5 = +0.69¢.
   The mechanism predicted the reverse.

## Frozen interpretation

**QUIET TAPE = NEW PRICE ACCEPTANCE**

The abnormal adverse delta appears to incorporate information.
When subsequent volatility subsides, the market does not
mechanically return toward the pre-shock price; it appears to
stabilize around the newly repriced probability.

Continued movement ≠ reversion. The positive R5 in the
still-volatile group is continued path dynamics, not
normalization bounce.

Score filters make the result stronger, not weaker:

```
ALL PRIMARY SHOCKS                  +0.14¢ R5
1–4 PT DETERIORATION                −0.06¢ R5
+ 25–50% PROPORTIONAL DETERIORATION −0.49¢ R5
FIRST SHOCK IN GAME                 −0.45¢ R5
```

The more specifically the original theoretical event is
approximated, the less evidence there is for recovery.

Tables: `REPORT.md`. Object definition: `SPEC.md`.
"""


def write_report_text(raw: dict, stats: dict) -> str:
    lines = [
        "# VOLATILITY NORMALIZATION FAILS AS A RECOVERY MECHANISM",
        "",
        "**QUIET DOES NOT MEAN REVERSION** — H2 opening adverse-delta",
        "normalization. Archived rejected mechanism.",
        "",
        "```",
        "RESULT: NEGATIVE",
        "QUIET TAPE = NEW PRICE ACCEPTANCE",
        "VOLATILITY NORMALIZATION ≠ PRICE RECOVERY",
        "CLOSE_5 = DESCRIPTIVE OBSERVATION",
        "DO NOT HUNT A PROFITABLE SUBSET",
        "LIVE EXECUTION = FALSE",
        "```",
        "",
        "Completely separate from FIRST75. Does not change live FIRST01.",
        "Candle path ≠ fill. P5 vs P5 only.",
        "",
        "Freeze: `CONCLUSION.md`. Object: `SPEC.md`.",
        "",
        "## Universe",
        "",
        f"- P5 vs P5 games (gate): **{raw['p5_games']}**",
        f"- Two-sided markets: {raw['n_two_sided']}",
        f"- MATCHED ESPN PBP: {raw['n_matched_pbp']}",
        f"- Games with ≥1 H2-open i* bar: **{raw['n_games_with_h2_bars']}**",
        f"- H2-open bar events: **{raw['n_events']}**",
        "",
        "## 1. Event population (no rule selected)",
        "",
        "Every quality H2-open minute with a unique adverse contract i*.",
        "Primary shock is a *flag*, not the universe.",
        "",
        "| Slice | N bars | N games | mean ΔP ¢ | R5 ¢ | R10 ¢ | P(R5>0)% | P(vol_norm)% | P(W)% |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        _row(stats["all_h2_open"]),
        _row(stats["primary_shock"]),
        _row(stats["ordinary_adverse"]),
        _row(stats["shock_bounded"]),
        _row(stats["shock_bounded_prop"]),
        _row(stats["ordinary_bounded"]),
        _row(stats["first_shock_only"]),
        "",
        "## 2. Object B — price after the bar",
        "",
        "R_h = later quality yes_bid_close minus the shock-minute close.",
        "Not a fill. Comparable control is ordinary adverse (ΔP<0, not above p80).",
        "",
    ]
    shock = stats["primary_shock"]
    ctrl = stats["ordinary_adverse"]
    lines.append("| Horizon | Shock mean ¢ | Control mean ¢ | Shock − control |")
    lines.append("|---|---:|---:|---:|")
    for h in LOOKAHEADS:
        sm = shock["returns"][h]["mean"]
        cm = ctrl["returns"][h]["mean"]
        diff = None if sm is None or cm is None else sm - cm
        lines.append(f"| +{h}m | {_f(sm)} | {_f(cm)} | {_f(diff)} |")
    lines.extend(
        [
            "",
            "H1 is descriptively favored if Shock − control > 0 (better subsequent",
            "bid path after an abnormal adverse bar than after an ordinary one).",
            "That is not proof of a temporary component, and not a trade.",
            "",
            "## 3. Object A — does volatility normalize?",
            "",
            f"- P(vol_norm | primary shock) = {_f(None if shock['p_vol_norm'] is None else 100.0 * shock['p_vol_norm'], 1)}%",
            f"- P(vol_norm | ordinary adverse) = {_f(None if ctrl['p_vol_norm'] is None else 100.0 * ctrl['p_vol_norm'], 1)}%",
            "",
            "vol_norm := mean |ΔP| over the next 5 minutes ≤ that contract's H1 mean |ΔP|.",
            "",
            "## 4. Object C — recovery only when vol normalizes?",
            "",
        ]
    )
    c = stats["object_c_primary"]
    lines.append("| Condition | N | R5 ¢ | R10 ¢ | P(R5>0)% |")
    lines.append("|---|---:|---:|---:|---:|")
    for key in ("shock_and_norm", "shock_and_no_norm"):
        b = c[key]
        lines.append(
            f"| {b['label']} | {b['n']} | {_f(b['returns'][5]['mean'])} | "
            f"{_f(b['returns'][10]['mean'])} | "
            f"{_f(None if b['p_r5_pos'] is None else 100.0 * b['p_r5_pos'], 1)} |"
        )
    lines.extend(
        [
            "",
            "If R | (shock ∧ ¬norm) ≥ R | (shock ∧ norm), volatility quieting is",
            "*not* the mechanism of recovery (the market may have finished",
            "repricing and then gone quiet at the new level).",
            "",
            "## 5. Close bands (all frozen; none selected)",
            "",
            "| Band | Shock N | Shock R5 | Ordinary N | Ordinary R5 | Δ R5 |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for cband in CLOSE_BANDS:
        blk = stats["close_bands"][f"close_{cband}"]
        s5 = blk["shock"]["returns"][5]["mean"]
        o5 = blk["ordinary"]["returns"][5]["mean"]
        d = None if s5 is None or o5 is None else s5 - o5
        lines.append(
            f"| CLOSE_{cband} | {blk['shock']['n']} | {_f(s5)} | "
            f"{blk['ordinary']['n']} | {_f(o5)} | {_f(d)} |"
        )
    lines.extend(
        [
            "",
            "Do not promote the largest Δ R5 to a structural close threshold.",
            "",
            "## 6. Calendar splits (descriptive; no selection)",
            "",
            f"IN_SAMPLE ≤ {SPLIT_RESEARCH_END}; VALIDATION ≤ {SPLIT_VAL_END}; else OOS.",
            "",
            "| Split | Shock N | Shock R5 | Ordinary N | Ordinary R5 | Δ R5 |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for name in ("IN_SAMPLE", "VALIDATION", "OOS"):
        s = stats["splits"][name]["shock"]
        o = stats["splits"][name]["ordinary"]
        s5 = s["returns"][5]["mean"]
        o5 = o["returns"][5]["mean"]
        d = None if s5 is None or o5 is None else s5 - o5
        lines.append(
            f"| {name} | {s['n']} | {_f(s5)} | {o['n']} | {_f(o5)} | {_f(d)} |"
        )
    sb = stats["shock_bounded"]
    sbp = stats["shock_bounded_prop"]
    first = stats["first_shock_only"]
    cprim = stats["object_c_primary"]
    lines.extend(
        [
            "",
            "## 7. Reading (descriptive; not a rule)",
            "",
            "Primary shocks are large: mean ΔP "
            f"**{_f(shock['mean_shock']['mean'])}¢** (median "
            f"{_f(shock['mean_shock']['median'])}). Subsequent R5 is "
            f"**{_f(shock['returns'][5]['mean'])}¢** versus "
            f"{_f(ctrl['returns'][5]['mean'])}¢ for ordinary adverse "
            f"(Δ ≈ {_f((shock['returns'][5]['mean'] or 0) - (ctrl['returns'][5]['mean'] or 0))}¢). "
            f"R5 sd is {_f(shock['returns'][5]['sd'])}¢. Median R5 is 0. "
            "That is not a recoverable temporary component.",
            "",
            "The tighter, intended information filter is *worse* for the bounce:",
            f"- shock ∩ bounded deterioration: R5 {_f(sb['returns'][5]['mean'])}¢ "
            f"(n={sb['n']})",
            f"- plus prop 25–50% and |M_pre|≥4: R5 {_f(sbp['returns'][5]['mean'])}¢ "
            f"(n={sbp['n']})",
            f"- first primary shock in the game: R5 {_f(first['returns'][5]['mean'])}¢ "
            f"(n={first['n']})",
            "",
            "Object A: vol is *less* likely to return to the H1 mean after a",
            "primary shock than after an ordinary adverse bar "
            f"({_f(None if shock['p_vol_norm'] is None else 100.0 * shock['p_vol_norm'], 1)}% vs "
            f"{_f(None if ctrl['p_vol_norm'] is None else 100.0 * ctrl['p_vol_norm'], 1)}%).",
            "",
            "Object C rejects the causal chain. After a primary shock:",
            f"- vol_norm: R5 {_f(cprim['shock_and_norm']['returns'][5]['mean'])}¢ "
            f"(n={cprim['shock_and_norm']['n']})",
            f"- ¬vol_norm: R5 {_f(cprim['shock_and_no_norm']['returns'][5]['mean'])}¢ "
            f"(n={cprim['shock_and_no_norm']['n']})",
            "",
            "When the tape quiets, the damaged contract does **not** reclaim",
            "the shock. Quiet looks like a finished reprice. Continued vol",
            "is where the small positive mean lives — not a normalization bounce.",
            "",
            "CLOSE_5 has the largest Δ R5 among frozen close bands. That is",
            "**not** selected. OOS primary Δ R5 is negative. Do not promote",
            "a close threshold from this table.",
            "",
            "## 8. What this is not",
            "",
            "- Not FIRST75, FIRST80, T40, or Lebronner.",
            "- Not an authorized entry rule or fade.",
            "- Not evidence that vol normalization *causes* price recovery.",
            "- Not a fill, fee, or live P&L.",
            "- Not MLB FIRST01. Not W9.",
            "",
            "**LIVE DEPLOYMENT: NOT AUTHORIZED**",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def load_raw_from_events(path: Path | None = None) -> dict:
    src = path or (REPORTS / "events.jsonl")
    header = json.loads((REPORTS / "summary.json").read_text())
    events = [json.loads(line) for line in src.read_text().splitlines() if line]
    header["events"] = events
    header["n_events"] = len(events)
    return header


def main() -> int:
    if "--from-events" in sys.argv:
        raw = load_raw_from_events()
    else:
        raw = collect()
    stats = analyze(raw)
    write_outputs(raw, stats)
    print(
        json.dumps(
            {
                "p5_games": raw["p5_games"],
                "n_events": raw["n_events"],
                "n_shock": stats["primary_shock"]["n"],
                "shock_r5": stats["primary_shock"]["returns"][5]["mean"],
                "ordinary_r5": stats["ordinary_adverse"]["returns"][5]["mean"],
                "out": str(REPORTS),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
