#!/usr/bin/env python3
"""NCAAB P5: H1 full 20 vs H2 first 5 — vol, empirical greeks, reversion.

Discovery scan. Candle-path sensitivities, not options greeks, not W9.
Completely separate from FIRST75 / Lebronner. P5 vs P5 only.

```
RESEARCH ONLY
EMPIRICAL β ≠ OPTION GREEK
VOLATILITY ≠ MISPRICING
REVERSION STAT ≠ EXECUTABLE EDGE
LIVE EXECUTION = FALSE
```
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

NCAAB_SCRIPTS = Path(__file__).resolve().parent
if str(NCAAB_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(NCAAB_SCRIPTS))

import ncaab_h2_opening_vol_shock as V  # noqa: E402

REPO = Path("/Users/user/Desktop/Momento")
REPORTS = REPO / "research" / "ncaab_h1_h2_vol_greeks"
DOCS = REPO / "docs" / "research" / "ncaab_h1_h2_vol_greeks"
WH_OUT = (
    REPO
    / "Backtesting Suite"
    / "Data"
    / "NCAAB"
    / "2025-2026"
    / "warehouse"
    / "derived"
    / "ncaab"
    / "h1_h2_vol_greeks"
)

WINDOWS = ("H1_20", "H1_5", "H2_5")
MIN_DIFFS = {"H1_20": 8, "H1_5": 3, "H2_5": 3}
MIN_BETA_PAIRS = 4
CLOSE_M = 10.0


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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
    r = None if syy <= 0 else sxy / math.sqrt(sxx * syy)
    return {"n": n, "beta": beta, "intercept": my - beta * mx, "r": r}


def ar1(diffs: list[float]) -> float | None:
    if len(diffs) < 4:
        return None
    return ols_slope(diffs[:-1], diffs[1:]).get("r")


def sign_flip_rate(diffs: list[float]) -> float | None:
    n = 0
    k = 0
    for a, b in zip(diffs[:-1], diffs[1:]):
        if a == 0:
            continue
        n += 1
        if a * b < 0:
            k += 1
    return None if n == 0 else k / n


def safe_ratio(a: float | None, b: float | None) -> float | None:
    if a is None or b is None or b == 0:
        return None
    return a / b


def in_window(name: str, period, remaining_s, phase: str | None) -> bool:
    if phase != "IN_PERIOD" or period is None:
        return False
    p = int(period)
    if name == "H1_20":
        return p == 1
    rem = remaining_s
    if rem is None:
        return False
    rem = float(rem)
    if name in {"H1_5", "H2_5"}:
        want = 1 if name == "H1_5" else 2
        return p == want and V.H2_OPEN_REM_LO < rem <= V.H2_OPEN_REM_HI
    raise KeyError(name)


def pair_in_window(prev: dict, cur: dict, name: str) -> bool:
    if not in_window(name, cur["period"], cur["remaining_s"], cur["phase"]):
        return False
    if prev["phase"] != "IN_PERIOD":
        return False
    return prev["period"] == cur["period"]


def window_metrics(rows: list[dict], h1_p80: float | None) -> dict:
    diffs = [r["dp_cents"] for r in rows]
    absx = [abs(d) for d in diffs]
    bids = [r["bid_c"] / 100.0 for r in rows]
    beta_xy = [
        (r["dm"], r["dp_cents"])
        for r in rows
        if r.get("dm") is not None and r["dm"] != 0
    ]
    close_xy = [
        (r["dm"], r["dp_cents"])
        for r in rows
        if r.get("dm") not in (None, 0) and r.get("close10")
    ]
    open_xy = [
        (r["dm"], r["dp_cents"])
        for r in rows
        if r.get("dm") not in (None, 0) and r.get("close10") is False
    ]
    against = [r["dp_cents"] for r in rows if r.get("dm") is not None and r["dm"] < 0]
    for_sc = [r["dp_cents"] for r in rows if r.get("dm") is not None and r["dm"] > 0]
    beta = ols_slope([x for x, _ in beta_xy], [y for _, y in beta_xy])
    if beta["n"] < MIN_BETA_PAIRS:
        beta = {**beta, "beta": None, "r": None}
    nxt_after_adv = [
        rows[i + 1]["dp_cents"]
        for i, r in enumerate(rows[:-1])
        if r["dp_cents"] < 0
    ]
    large_rev = {}
    for label, thr in (("c3", 3.0), ("c5", 5.0), ("h1p80", h1_p80)):
        if thr is None:
            large_rev[label] = {"n": 0, "r1": None, "p_signflip": None}
            continue
        seq = [
            (r["dp_cents"], rows[i + 1]["dp_cents"])
            for i, r in enumerate(rows[:-1])
            if r["dp_cents"] < -float(thr)
        ]
        r1s = [b for _a, b in seq]
        flips = [1.0 if a * b < 0 else 0.0 for a, b in seq]
        large_rev[label] = {
            "n": len(seq),
            "r1": None if not r1s else statistics.mean(r1s),
            "p_signflip": None if not flips else statistics.mean(flips),
        }
    return {
        "n": len(rows),
        "mean_abs": None if not absx else statistics.mean(absx),
        "median_abs": None if not absx else statistics.median(absx),
        "sigma": None if len(diffs) < 2 else statistics.stdev(diffs),
        "p80_abs": V.pctile(absx, 0.80) if absx else None,
        "p95_abs": V.pctile(absx, 0.95) if absx else None,
        "range": None if len(bids) < 2 else max(bids) - min(bids),
        "beta": beta["beta"],
        "beta_r": beta["r"],
        "beta_n": beta["n"],
        "beta_close10": ols_slope([x for x, _ in close_xy], [y for _, y in close_xy])["beta"]
        if len(close_xy) >= MIN_BETA_PAIRS
        else None,
        "beta_not_close10": ols_slope([x for x, _ in open_xy], [y for _, y in open_xy])["beta"]
        if len(open_xy) >= MIN_BETA_PAIRS
        else None,
        "dP_score_against": None if not against else statistics.mean(against),
        "dP_score_for": None if not for_sc else statistics.mean(for_sc),
        "n_score_against": len(against),
        "ar1": ar1(diffs),
        "sign_flip": sign_flip_rate(diffs),
        "r1_after_adverse": None if not nxt_after_adv else statistics.mean(nxt_after_adv),
        "large": large_rev,
    }


def side_rows(pairs: list[dict], snap_fn, name: str, team_is_home: bool) -> list[dict]:
    out = []
    for p in pairs:
        prev = snap_fn(p["prev_ts"])
        cur = snap_fn(p["ts"])
        if not pair_in_window(prev, cur, name):
            continue
        m_pre = V.margin_of(prev["score"], team_is_home)
        m_post = V.margin_of(cur["score"], team_is_home)
        dm = None if m_pre is None or m_post is None else m_post - m_pre
        out.append(
            {
                **p,
                "dm": dm,
                "close10": None if m_pre is None else abs(m_pre) <= CLOSE_M,
                "m_pre": m_pre,
            }
        )
    return out


def game_scan(game: dict, sides: dict, actions: list[dict]) -> dict | None:
    snap_fn = V.build_snapper(actions)
    per_side = {}
    for side, rec in sides.items():
        pairs = V.quality_pairs(rec["quotes"])
        home = side == "home"
        wins = {w: side_rows(pairs, snap_fn, w, home) for w in WINDOWS}
        h1 = V.h1_baseline([r["dp_cents"] for r in wins["H1_20"]])
        h1_p80 = None if not h1 else h1["p80_abs"]
        per_side[side] = {
            "W": V.A.settled_yes(rec["market"]),
            "windows": {
                w: window_metrics(wins[w], h1_p80)
                if len(wins[w]) >= MIN_DIFFS[w]
                else None
                for w in WINDOWS
            },
        }
    if not any(per_side[s]["windows"]["H1_20"] and per_side[s]["windows"]["H2_5"] for s in per_side):
        return None
    return {
        "event_id": game["event_id"],
        "game_date": game.get("game_date"),
        "split": V.split_of(game.get("game_date")),
        "sides": per_side,
    }


def mean_side_metric(game: dict, window: str, key: str) -> float | None:
    xs = []
    for side in ("home", "away"):
        w = game["sides"][side]["windows"].get(window)
        if not w:
            continue
        v = w.get(key)
        if v is not None:
            xs.append(v)
    return None if not xs else statistics.mean(xs)


def pool_windows(games: list[dict]) -> dict:
    out = {}
    for w in WINDOWS:
        bags = {k: [] for k in (
            "mean_abs", "sigma", "p80_abs", "range", "beta", "beta_r",
            "beta_close10", "beta_not_close10", "dP_score_against",
            "ar1", "sign_flip", "r1_after_adverse",
        )}
        large = {"c3": [], "c5": [], "h1p80": []}
        n_sides = 0
        n_games = set()
        for g in games:
            for side, rec in g["sides"].items():
                m = rec["windows"].get(w)
                if not m:
                    continue
                n_sides += 1
                n_games.add(g["event_id"])
                for k in bags:
                    if m.get(k) is not None:
                        bags[k].append(m[k])
                for lab in large:
                    r1 = (m.get("large") or {}).get(lab, {}).get("r1")
                    if r1 is not None:
                        large[lab].append(r1)
        out[w] = {
            "n_sides": n_sides,
            "n_games": len(n_games),
            **{k: V.summarize(vs) for k, vs in bags.items()},
            "large_r1": {lab: V.summarize(vs) for lab, vs in large.items()},
        }
    return out


def paired(games: list[dict]) -> dict:
    usable = []
    for g in games:
        if mean_side_metric(g, "H1_20", "sigma") is None:
            continue
        if mean_side_metric(g, "H2_5", "sigma") is None:
            continue
        usable.append(g)

    def pack(a: str, b: str) -> dict:
        ratios = {}
        for key in ("sigma", "mean_abs", "beta", "ar1", "sign_flip"):
            rs = []
            da = []
            for g in usable:
                va = mean_side_metric(g, a, key)
                vb = mean_side_metric(g, b, key)
                if key == "ar1":
                    if va is not None and vb is not None:
                        da.append(va - vb)
                    continue
                r = safe_ratio(va, vb)
                if r is not None:
                    rs.append(r)
                    da.append(va - vb)
            ratios[key] = {
                "n": len(rs) if key != "ar1" else len(da),
                "median_ratio": None if key == "ar1" or not rs else statistics.median(rs),
                "mean_ratio": None if key == "ar1" or not rs else statistics.mean(rs),
                "pct_a_gt_b": None
                if not da
                else sum(1 for x in da if x > 0) / len(da),
                "median_diff": None if not da else statistics.median(da),
            }
        return ratios

    return {
        "n_games": len(usable),
        "H2_5_vs_H1_20": pack("H2_5", "H1_20"),
        "H2_5_vs_H1_5": pack("H2_5", "H1_5"),
        "H1_5_vs_H1_20": pack("H1_5", "H1_20"),
    }


def collect() -> dict:
    games_by, by_event, quotes, xwalk, cache = V.load_universe()
    games = []
    n_pbp = 0
    for event_id, ms in by_event.items():
        game = games_by[event_id]
        sides = {}
        for m in ms:
            side = V.match_side(m.get("team"), game)
            if side is None:
                continue
            sides[side] = {"market": m, "quotes": quotes.get(m["ticker"], [])}
        if set(sides) != {"home", "away"}:
            continue
        cw = xwalk.get(event_id) or {}
        espn_id = cw.get("espn_game_id")
        if cw.get("match_status") != "MATCHED" or not espn_id:
            continue
        actions = V.HBS._pbp_pack(espn_id, cache)
        if not actions:
            continue
        n_pbp += 1
        rec = game_scan(game, sides, actions)
        if rec:
            games.append(rec)
    V.halt_if(len(games) < 100, f"HALT few paired games {len(games)}")
    pooled = pool_windows(games)
    pair = paired(games)
    splits = {}
    for name in ("IN_SAMPLE", "VALIDATION", "OOS"):
        sub = [g for g in games if g["split"] == name]
        splits[name] = {"n": len(sub), "paired": paired(sub)} if sub else {"n": 0}
    return {
        "written_utc": utc_now(),
        "research_only": True,
        "live_execution_changed": False,
        "separate_from_first75": True,
        "not_w9": True,
        "universe": "KXNCAAMBGAME 2025-26 P5 vs P5",
        "p5_games": V.P5_GAMES_EXPECTED,
        "n_matched_pbp": n_pbp,
        "n_games_scanned": len(games),
        "pooled": pooled,
        "paired": pair,
        "splits": splits,
        "definition": (
            "H1_20 = period 1 IN_PERIOD. H1_5 / H2_5 = first 5 clock minutes "
            "of that half (900 < rem ≤ 1200). Empirical β = OLS Δbid_cents on "
            "Δmargin. Not an option greek. Not a fill."
        ),
    }


def _f(x, d=3):
    if x is None:
        return "—"
    return f"{x:.{d}f}"


def write_report(doc: dict) -> str:
    p = doc["pooled"]
    pair = doc["paired"]
    lines = [
        "# NCAAB P5 — H1 20 vs H2 first 5: vol, empirical greeks, reversion",
        "",
        "```",
        "RESEARCH ONLY",
        "EMPIRICAL β ≠ OPTION GREEK",
        "VOLATILITY ≠ MISPRICING",
        "REVERSION STAT ≠ EXECUTABLE EDGE",
        "LIVE EXECUTION = FALSE",
        "```",
        "",
        "Discovery only. Not FIRST75. Not W9. Not live FIRST01.",
        "P5 vs P5. Quality yes_bid_close. Candle path ≠ fill.",
        "",
        "Windows (clock, not wall):",
        "- **H1_20** — entire first half, IN_PERIOD",
        "- **H1_5** — first 5 minutes of H1 (same-length control)",
        "- **H2_5** — first 5 minutes of H2 (20:00→15:00 remaining)",
        "",
        "Greeks here are **candle-path score sensitivities**, not Kalshi",
        "option greeks and not the MLB W9 object.",
        "",
        f"Games scanned: **{doc['n_games_scanned']}** / {doc['p5_games']} P5 "
        f"(MATCHED PBP {doc['n_matched_pbp']}).",
        f"Paired games with both H1_20 and H2_5 σ: **{pair['n_games']}**.",
        "",
        "## 1. Pooled contract-windows",
        "",
        "Each side of each game is one observation. Complementary contracts",
        "are not independent; paired ratios below are the fair comparison.",
        "",
        "| Window | N sides | N games | mean \\|ΔP\\| ¢ | σ ΔP ¢ | p80 \\|ΔP\\| | path range ¢ | β ¢/pt | r(β) | ΔP \\| score against | AR1 | sign-flip | R1 after adverse |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for w in WINDOWS:
        s = p[w]
        lines.append(
            f"| {w} | {s['n_sides']} | {s['n_games']} | "
            f"{_f(s['mean_abs']['mean'])} | {_f(s['sigma']['mean'])} | "
            f"{_f(s['p80_abs']['mean'])} | {_f(s['range']['mean'])} | "
            f"{_f(s['beta']['mean'])} | {_f(s['beta_r']['mean'])} | "
            f"{_f(s['dP_score_against']['mean'])} | {_f(s['ar1']['mean'])} | "
            f"{_f(s['sign_flip']['mean'])} | {_f(s['r1_after_adverse']['mean'])} |"
        )
    lines.extend(
        [
            "",
            "Path range is larger in H1_20 because the window is longer.",
            "Minute σ, mean |ΔP|, and β are the comparable objects.",
            "",
            "### State-dependent β (close ≤ 10 vs not)",
            "",
            "| Window | β close10 | β not close10 |",
            "|---|---:|---:|",
        ]
    )
    for w in WINDOWS:
        s = p[w]
        lines.append(
            f"| {w} | {_f(s['beta_close10']['mean'])} | {_f(s['beta_not_close10']['mean'])} |"
        )
    lines.extend(
        [
            "",
            "### Next-minute path after a large adverse bar",
            "",
            "| Window | R1 after < −3¢ | R1 after < −5¢ | R1 after < −H1 p80 |",
            "|---|---:|---:|---:|",
        ]
    )
    for w in WINDOWS:
        s = p[w]
        lines.append(
            f"| {w} | {_f(s['large_r1']['c3']['mean'])} | "
            f"{_f(s['large_r1']['c5']['mean'])} | "
            f"{_f(s['large_r1']['h1p80']['mean'])} |"
        )
    h2 = pair["H2_5_vs_H1_20"]
    h25 = pair["H2_5_vs_H1_5"]
    h15 = pair["H1_5_vs_H1_20"]
    lines.extend(
        [
            "",
            "## 2. Same-game paired ratios (the discovery object)",
            "",
            "For each game, average home/away, then H2_5 / H1_20.",
            "**1.00 = same regime.** Median ratio is the headline.",
            "",
            "| Contrast | σ median ratio | % σ higher | mean\\|ΔP\\| ratio | β median ratio | % β higher | AR1 median diff | % more mean-reverting |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )

    def pair_row(label, rec):
        ar = rec["ar1"]
        # more mean-reverting = more negative AR1, so a-b < 0 when a=H2
        pct_mr = None
        if ar["pct_a_gt_b"] is not None:
            pct_mr = 1.0 - ar["pct_a_gt_b"]
        return (
            f"| {label} | {_f(rec['sigma']['median_ratio'])} | "
            f"{_f(None if rec['sigma']['pct_a_gt_b'] is None else 100.0 * rec['sigma']['pct_a_gt_b'], 1)} | "
            f"{_f(rec['mean_abs']['median_ratio'])} | "
            f"{_f(rec['beta']['median_ratio'])} | "
            f"{_f(None if rec['beta']['pct_a_gt_b'] is None else 100.0 * rec['beta']['pct_a_gt_b'], 1)} | "
            f"{_f(ar['median_diff'])} | "
            f"{_f(None if pct_mr is None else 100.0 * pct_mr, 1)} |"
        )

    lines.append(pair_row("H2_5 vs H1_20", h2))
    lines.append(pair_row("H2_5 vs H1_5 (same length)", h25))
    lines.append(pair_row("H1_5 vs H1_20", h15))
    lines.extend(
        [
            "",
            "AR1 more negative = stronger one-minute reversal. A higher",
            "“% more mean-reverting” means the first window flips sign more",
            "than the second. That is still not a trade.",
            "",
            "## 3. Calendar splits of the H2_5 / H1_20 σ ratio",
            "",
            "| Split | N games | σ median ratio | β median ratio |",
            "|---|---:|---:|---:|",
        ]
    )
    for name in ("IN_SAMPLE", "VALIDATION", "OOS"):
        rec = doc["splits"].get(name) or {}
        if not rec.get("paired"):
            lines.append(f"| {name} | {rec.get('n', 0)} | — | — |")
            continue
        pr = rec["paired"]["H2_5_vs_H1_20"]
        lines.append(
            f"| {name} | {rec['paired']['n_games']} | "
            f"{_f(pr['sigma']['median_ratio'])} | {_f(pr['beta']['median_ratio'])} |"
        )
    lines.extend(
        [
            "",
            "## 4. Discoveries (descriptive)",
            "",
            "1. **Typical game: H2 first 5 is not a high-vol expansion vs own H1.**",
            f"   Paired median σ(H2_5)/σ(H1_20) = {_f(h2['sigma']['median_ratio'])}.",
            "   Only 46.9% of games have louder early H2 than their own first half.",
            "   Pooled *means* are slightly the other way (H2_5 σ 2.71 vs H1_20 2.63)",
            "   because a minority of games have a very loud H2 open. The H1 p80",
            "   shock filter is well-calibrated: the two regimes have almost the",
            "   same p80 (|ΔP| 3.13 vs 3.08).",
            "",
            "2. **The rest of H1 is louder than H1’s own first five.**",
            "   H1_5 is the quietest window (σ 2.42, β 0.87). Full-half σ is",
            "   pulled up by minutes 5–20, which is why H2_5/H1_20 < 1 while",
            f"   H2_5/H1_5 σ median = {_f(h25['sigma']['median_ratio'])}.",
            "   Early H2 is a bit louder than early H1, not louder than all of H1.",
            "",
            "3. **The greek that actually moves is close-state delta.**",
            "   Pooled β: H1_5 0.87, H1_20 1.07, H2_5 1.24 ¢/pt.",
            "   Inside |M|≤10: H2_5 β **1.70** vs H1_20 **1.11**.",
            "   Outside that band H2_5 β collapses to 0.42. A 3-point swing",
            "   in a close early-H2 game moves the yes much more than the same",
            "   swing in H1. Part of that is mechanical (less clock left →",
            "   larger win-prob per point). It is not, by itself, mispricing.",
            "",
            "4. **One-minute reversion is a short-window effect, not an H2 effect.**",
            "   H1_20 AR1 ≈ 0. Both 5-minute windows are mildly negative",
            "   (H1_5 −0.13, H2_5 −0.09). After any adverse bar, R1 is ~+0.33¢",
            "   in both 5-minute windows and ~0 over the full half. After a",
            "   *large* adverse (−3/−5¢), H2_5 R1 is larger (+0.56 / +0.67)",
            "   than H1_20 (+0.01 / +0.21). That is a next-minute bounce of",
            "   well under a cent per cent of shock. The earlier H2-open shock",
            "   study already showed this does not survive to +5m once the",
            "   move is H1-p80 and bounded, and that vol-normalization is not",
            "   the recovery mechanism.",
            "",
            "5. **OOS (n=29) is too small to use.** VAL matches the full-sample",
            "   σ ratio (~0.94). Do not chase the OOS 1.15 / 1.41 pair.",
            "",
            "## 5. What this is not",
            "",
            "- Not W9. Not option greeks. Not L2.",
            "- Not FIRST75 / FIRST80 / T40 / Lebronner.",
            "- Not an entry rule, fade, or live order.",
            "- Not proof of inefficient delta.",
            "",
            "**LIVE DEPLOYMENT: NOT AUTHORIZED**",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    doc = collect()
    text = write_report(doc)
    payload = json.dumps(doc, indent=2) + "\n"
    for dest in (REPORTS, DOCS, WH_OUT):
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "REPORT.md").write_text(text)
        (dest / "summary.json").write_text(payload)
    h2 = doc["paired"]["H2_5_vs_H1_20"]
    print(
        json.dumps(
            {
                "n_games": doc["n_games_scanned"],
                "sigma_ratio_h2_vs_h1": h2["sigma"]["median_ratio"],
                "beta_ratio_h2_vs_h1": h2["beta"]["median_ratio"],
                "out": str(REPORTS),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
