#!/usr/bin/env python3
"""P(¬T40 | W, FIRST75) on requested clock slices.

FIRST75 = first tradable yes_bid_close ≥ 75¢ after a prior tradable close
< 75¢, uncrossed spread ≤ 10¢, one per event; same-minute ties excluded.
Same rule as FIRST80, threshold 75. T40 = later tradable yes_bid_close ≤ 40¢.

Slices:
  NBA / WNBA: ESPN/NBA-aligned Q2 and Q3 at the FIRST75 timestamp
  NCAAB: P5 vs P5, 1H second 10 and 2H first 10 at the FIRST75 timestamp

Research only. Candle path, not fills. Does not change live FIRST01.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

NBA_SCRIPTS = Path(__file__).resolve().parent
WNBA_SCRIPTS = Path("/Users/user/Desktop/Momento/apps/wnba-data/scripts")
NCAAB_SCRIPTS = Path("/Users/user/Desktop/Momento/apps/ncaab-data/scripts")
if str(NBA_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(NBA_SCRIPTS))

import nba_80_40_execution_audit as A  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

HIT75 = 7500
HIT80 = 8000
HIT40 = 4000
QUOTE_COLS = [
    "end_period_ts",
    "yes_bid_close_e4",
    "yes_ask_close_e4",
    "volume_hundredths",
    "is_valid",
]

REPO = Path("/Users/user/Desktop/Momento")
REPORTS = REPO / "research" / "first75_slice_not40_given_w"
DOCS = REPO / "docs" / "research" / "first75_slice_not40_given_w"
DECOMP_REPORTS = REPO / "research" / "first75_terminal_path_decomp"
DECOMP_DOCS = REPO / "docs" / "research" / "first75_terminal_path_decomp"
WH_OUT = (
    REPO
    / "Backtesting Suite"
    / "Data"
    / "NBA"
    / "2025-2026"
    / "warehouse"
    / "derived"
    / "nba"
    / "first75_slice_not40_given_w"
)

# Frozen NBA FIRST75 from alpha-decomp Module B (2026-09-04). Identity gate.
NBA_F75_N = 1176
NBA_F75_W = 915
NBA_F75_NOT40_GIVEN_W = 781

NBA_F80 = {"n": 1230, "W": 1019, "T40": 320, "W_not_T40": 910}
WNBA_F80 = {"n": 589, "W": 492, "T40": 153, "W_not_T40": 436}
NCAAB_P5_F80 = {"n": 721, "W": 601, "T40": 188, "W_not_T40": 533}

NBA_F80_Q2 = 314
NBA_F80_Q3 = 290
WNBA_F80_Q2 = 127
WNBA_F80_Q3 = 119
NCAAB_F80_H12 = 193
NCAAB_F80_H21 = 139


class IdentityHalt(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def first_tradable_reach(rows: list[dict], hit_e4: int):
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


def first_close_le_after(rows: list[dict], tau: int, hit_e4: int = HIT40):
    for q in rows:
        if q["ts"] <= tau:
            continue
        if not A.quality(q["bid_c"], q["ask_c"], q["vol"], True):
            continue
        if q["bid_c"] is not None and q["bid_c"] <= hit_e4:
            return q
    return None


def quote_meta_nba_style(markets, games) -> dict[str, tuple]:
    games_by_event = {g["event_id"]: g for g in games}
    meta = {}
    for m in markets:
        g = games_by_event.get(m["event_id"], {})
        start = g.get("game_window_start")
        end = m.get("close_ts")
        gw_end = g.get("game_window_end")
        if end is None:
            end = gw_end
        elif gw_end is not None:
            end = min(end, gw_end)
        meta[m["ticker"]] = (start, end)
    return meta


def quote_meta_wnba(markets, games) -> dict[str, tuple]:
    games_by_event = {g["event_id"]: g for g in games}
    meta = {}
    for m in markets:
        g = games_by_event.get(m["event_id"], {})
        start = m.get("open_ts")
        if start is None:
            start = g.get("game_window_start")
        end = m.get("close_ts")
        if end is None:
            end = g.get("game_window_end")
        meta[m["ticker"]] = (start, end)
    return meta


def load_quotes(candles_dir: Path, meta: dict[str, tuple]) -> dict[str, list]:
    tickers = set(meta)
    files = [p for p in candles_dir.rglob("*.parquet") if p.stem in tickers]
    quotes: dict[str, list] = {t: [] for t in tickers}
    print(f"  candle files {len(files)} / tickers {len(tickers)}", flush=True)
    for i, path in enumerate(files, 1):
        table = pq.read_table(path, columns=QUOTE_COLS)
        ticker = path.stem
        start, end = meta.get(ticker, (None, None))
        get = {c: table.column(c) for c in QUOTE_COLS}
        rows = quotes[ticker]
        for j in range(table.num_rows):
            if not get["is_valid"][j].as_py():
                continue
            t = int(get["end_period_ts"][j].as_py())
            if start is not None and t < start:
                continue
            if end is not None and t > end:
                continue
            rows.append(
                {
                    "ts": t,
                    "bid_c": A._opt_int(get["yes_bid_close_e4"][j].as_py()),
                    "ask_c": A._opt_int(get["yes_ask_close_e4"][j].as_py()),
                    "vol": A._opt_int(get["volume_hundredths"][j].as_py()),
                }
            )
        if i == 1 or i == len(files) or i % 400 == 0:
            print(f"  quotes {i}/{len(files)}", flush=True)
    for rows in quotes.values():
        rows.sort(key=lambda r: r["ts"])
    return quotes


def build_first_reach(markets, games, quotes, hit_e4: int, status_ok: str) -> list[dict]:
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
            "status": "NO_REACH",
            "ticker": None,
            "team": None,
            "reach_ts": None,
            "first_80_timestamp": None,
            "W": None,
            "T40": None,
            "t40_ts": None,
            "expiration_result_yes": None,
            "stop_close_triggered": None,
        }
        if not hits:
            rows.append(rec)
            continue
        ts, ticker, m0, q = hits[0]
        if len([h for h in hits if h[0] == ts]) > 1:
            rec["status"] = "TIE_SAME_MINUTE"
            rows.append(rec)
            continue
        won = A.settled_yes(m0)
        t40 = first_close_le_after(quotes.get(ticker, []), ts)
        rec.update(
            {
                "status": status_ok,
                "ticker": ticker,
                "team": m0.get("team"),
                "reach_ts": ts,
                "first_80_timestamp": ts,
                "W": won,
                "T40": None if won is None else t40 is not None,
                "t40_ts": None if t40 is None else t40["ts"],
                "expiration_result_yes": won,
                "stop_close_triggered": t40 is not None,
            }
        )
        rows.append(rec)
    return rows


def settled(rows: list[dict], status: str) -> list[dict]:
    return [r for r in rows if r.get("status") == status and r.get("W") is not None]


def joints(rows: list[dict]) -> dict:
    n = len(rows)
    w = sum(1 for r in rows if r.get("W") is True)
    t40 = sum(1 for r in rows if r.get("T40") is True)
    w_not = sum(1 for r in rows if r.get("W") is True and not r.get("T40"))
    l_not = sum(1 for r in rows if r.get("W") is False and not r.get("T40"))
    return {"n": n, "W": w, "T40": t40, "W_not_T40": w_not, "L_not_T40": l_not}


def halt_joints(got: dict, exp: dict, label: str) -> None:
    keys = ("n", "W", "T40", "W_not_T40")
    a = {k: got[k] for k in keys}
    b = {k: exp[k] for k in keys}
    if a != b:
        raise IdentityHalt(f"HALT {label} {a} expected {b}")


NULL_P_W_75 = 0.75
# The six asked rows only (unions are derived, not added again).
ASKED_SIX = (
    ("wnba", "Q2", "2Q"),
    ("wnba", "Q3", "3Q"),
    ("nba", "Q2", "2Q"),
    ("nba", "Q3", "3Q"),
    ("ncaab_p5", "H1_2", "1H second 10"),
    ("ncaab_p5", "H2_1", "2H first 10"),
)


def p_w_given_first75(n_wins: int, n_total: int) -> dict:
    """ˆp_W,75 = N_W,75 / N_75 and α_75 = ˆp − 0.75.

    Wilson interval is on P(W|FIRST75). The α interval is that interval minus 0.75.
    Observed residual ≠ proven market inefficiency.
    """
    pct, lo, hi = A.wilson(n_wins, n_total)
    p = None if n_total == 0 else n_wins / n_total
    return {
        "N75": n_total,
        "N_W75": n_wins,
        "p_W": p,
        "pct": pct,
        "wilson_ci95": [lo, hi],
        "alpha_75_terminal": None if p is None else p - NULL_P_W_75,
        "alpha_75_pct_points": None if pct is None else round(pct - 75.0, 4),
        "alpha_wilson_ci95": None if lo is None else [round(lo - 75.0, 4), round(hi - 75.0, 4)],
        "ci_excludes_75": None if lo is None else bool(lo > 75.0 or hi < 75.0),
        "null_p": NULL_P_W_75,
        "object": "P(W | FIRST75)",
    }


def attach_terminal_calibration(summary: dict) -> dict:
    rows = []
    n75 = 0
    nw = 0
    for sport, sl, label in ASKED_SIX:
        rec = summary["sports"][sport]["slices"][sl]["FIRST75"]
        cal = p_w_given_first75(rec["n_wins"], rec["n_total"])
        cal["sport"] = sport
        cal["slice"] = sl
        cal["slice_label"] = label
        rows.append(cal)
        n75 += rec["n_total"]
        nw += rec["n_wins"]
    pooled = p_w_given_first75(nw, n75)
    pooled["sport"] = "pooled_six"
    pooled["slice"] = "ASKED_SIX"
    pooled["slice_label"] = "six asked rows"
    summary["terminal_calibration_first75"] = {
        "null_p": NULL_P_W_75,
        "definition": "alpha_75_terminal = P(W|FIRST75) - 0.75. K=0.75 is the quote, not a fill.",
        "slices": rows,
        "pooled_six_asked_rows": pooled,
        "weighting": "ONE_OBSERVATION_PER_FIRST75_EVENT",
        "note": "Pooled is sum N_W / sum N_75, not the unweighted mean of six rates.",
    }
    return summary


def attach_pooled_decomp(summary: dict) -> dict:
    d75 = None
    d80 = None
    for sport, sl, _label in ASKED_SIX:
        rec = summary["sports"][sport]["slices"][sl]
        d75 = rec["decomp_FIRST75"] if d75 is None else add_counts(d75, rec["decomp_FIRST75"])
        d80 = rec["decomp_FIRST80"] if d80 is None else add_counts(d80, rec["decomp_FIRST80"])
    summary["pooled_six_decomp"] = {
        "FIRST75": d75,
        "FIRST80": d80,
        "weighting": "ONE_OBSERVATION_PER_EVENT",
        "note": "Sum of the six asked rows only. Unions not double-counted.",
    }
    return summary


def _clopper_pearson(k: int, n: int, alpha: float = 0.05) -> tuple[float | None, float | None]:
    from scipy.stats import beta

    if n <= 0:
        return None, None
    lo = 0.0 if k == 0 else float(beta.ppf(alpha / 2.0, k, n - k + 1))
    hi = 1.0 if k == n else float(beta.ppf(1.0 - alpha / 2.0, k + 1, n - k))
    return lo, hi


def _exact_binomial(k: int, n: int, p0: float) -> dict:
    from scipy.stats import binomtest

    if n <= 0:
        return {"n": n, "k": k, "p0": p0, "p_one_sided_greater": None, "p_one_sided_less": None, "p_two_sided": None}
    greater = binomtest(k, n, p0, alternative="greater")
    less = binomtest(k, n, p0, alternative="less")
    two = binomtest(k, n, p0, alternative="two-sided")
    return {
        "n": int(n),
        "k": int(k),
        "p0": p0,
        "p_hat": k / n,
        "p_one_sided_greater": float(greater.pvalue),
        "p_one_sided_less": float(less.pvalue),
        "p_two_sided": float(two.pvalue),
        "method": "scipy.stats.binomtest",
    }


def _pct_pair(lo: float | None, hi: float | None) -> list:
    if lo is None or hi is None:
        return [None, None]
    return [round(lo * 100.0, 4), round(hi * 100.0, 4)]


def cond_rate(k: int, n: int, object_name: str) -> dict:
    pct, lo, hi = A.wilson(k, n)
    cp_lo, cp_hi = _clopper_pearson(k, n)
    return {
        "n": n,
        "k": k,
        "estimate": None if n <= 0 else k / n,
        "pct": pct,
        "wilson_ci95": [lo, hi],
        "clopper_pearson_ci95": _pct_pair(cp_lo, cp_hi),
        "object": object_name,
    }


def four_cell_counts(rows: list[dict]) -> tuple[int, int, int, int, int]:
    win_no = sum(1 for r in rows if r.get("W") is True and not r.get("T40"))
    win_t40 = sum(1 for r in rows if r.get("W") is True and r.get("T40"))
    lose_no = sum(1 for r in rows if r.get("W") is False and not r.get("T40"))
    lose_t40 = sum(1 for r in rows if r.get("W") is False and r.get("T40"))
    n = len(rows)
    if win_no + win_t40 + lose_no + lose_t40 != n:
        raise IdentityHalt(
            f"HALT four-cell {win_no}+{win_t40}+{lose_no}+{lose_t40} != {n}"
        )
    return n, win_no, win_t40, lose_no, lose_t40


def decomp_from_counts(
    n: int,
    win_no: int,
    win_t40: int,
    lose_no: int,
    lose_t40: int,
    quote_k: float,
    label: str,
) -> dict:
    """Terminal × path × four-cell joint. Counts are the authority; products must match."""
    if win_no + win_t40 + lose_no + lose_t40 != n:
        raise IdentityHalt("HALT decomp counts")
    w = win_no + win_t40
    lose = lose_no + lose_t40
    if w + lose != n:
        raise IdentityHalt("HALT W+L")
    p = None if n == 0 else w / n
    s_w = None if w == 0 else win_no / w
    s_l = None if lose == 0 else lose_no / lose
    joint = None if n == 0 else win_no / n
    s_uncond = None if n == 0 else (win_no + lose_no) / n
    product = None if p is None or s_w is None else p * s_w
    if product is not None and joint is not None and abs(product - joint) > 1e-12:
        raise IdentityHalt(f"HALT p*s_W {product} != joint {joint}")
    s_recon = None
    if p is not None and s_w is not None:
        s_recon = p * s_w + (0.0 if s_l is None else (1.0 - p) * s_l)
    if s_recon is not None and s_uncond is not None and abs(s_recon - s_uncond) > 1e-12:
        raise IdentityHalt(f"HALT S recon {s_recon} != {s_uncond}")
    term = cond_rate(w, n, f"P(W | {label})")
    vs = _exact_binomial(w, n, quote_k) if n else None
    w_lo, w_hi = term["wilson_ci95"]
    k_pct = quote_k * 100.0
    return {
        "label": label,
        "quote_k": quote_k,
        "n": n,
        "N_W": w,
        "N_L": lose,
        "cells": {
            "W_and_not_T40": win_no,
            "W_and_T40": win_t40,
            "L_and_not_T40": lose_no,
            "L_and_T40": lose_t40,
        },
        "cell_probs": None
        if n == 0
        else {
            "W_and_not_T40": win_no / n,
            "W_and_T40": win_t40 / n,
            "L_and_not_T40": lose_no / n,
            "L_and_T40": lose_t40 / n,
        },
        "terminal": {
            **term,
            "alpha_terminal": None if p is None else p - quote_k,
            "alpha_pct_points": None if term["pct"] is None else round(term["pct"] - k_pct, 4),
            "alpha_wilson_ci95": None
            if w_lo is None
            else [round(w_lo - k_pct, 4), round(w_hi - k_pct, 4)],
            "wilson_excludes_k": None if w_lo is None else bool(w_lo > k_pct or w_hi < k_pct),
            "vs_null": vs,
        },
        "winner_path": cond_rate(win_no, w, f"P(¬T40 | W, {label})"),
        "loser_path": cond_rate(lose_no, lose, f"P(¬T40 | L, {label})"),
        "unconditional_barrier": cond_rate(win_no + lose_no, n, f"P(¬T40 | {label})"),
        "joint_win_survive": cond_rate(win_no, n, f"P(W ∩ ¬T40 | {label})"),
        "reconstruction": {
            "p": p,
            "s_W": s_w,
            "s_L": s_l,
            "p_times_s_W": product,
            "S": s_recon,
            "identity_p_times_s_W_equals_joint": True,
            "identity_four_cells_sum_to_n": True,
        },
        "counterfactual_p_at_quote": {
            "held_s_W": s_w,
            "joint_if_p_equals_k": None if s_w is None else quote_k * s_w,
            "delta_vs_observed_joint": None
            if s_w is None or joint is None
            else quote_k * s_w - joint,
            "note": "Not a forecast. Holds winner-path, sets P(W) to K.",
        },
    }


def decomp_of_rows(rows: list[dict], quote_k: float, label: str) -> dict:
    n, win_no, win_t40, lose_no, lose_t40 = four_cell_counts(rows)
    return decomp_from_counts(n, win_no, win_t40, lose_no, lose_t40, quote_k, label)


def add_counts(a: dict, b: dict) -> dict:
    ca, cb = a["cells"], b["cells"]
    return decomp_from_counts(
        a["n"] + b["n"],
        ca["W_and_not_T40"] + cb["W_and_not_T40"],
        ca["W_and_T40"] + cb["W_and_T40"],
        ca["L_and_not_T40"] + cb["L_and_not_T40"],
        ca["L_and_T40"] + cb["L_and_T40"],
        a["quote_k"],
        a["label"],
    )


def p_not_t40_given_w(rows: list[dict], label: str = "FIRST75") -> dict:
    wins = [r for r in rows if r.get("W") is True]
    n = len(wins)
    k = sum(1 for r in wins if not r.get("T40"))
    pct, lo, hi = A.wilson(k, n)
    return {
        "n_total": len(rows),
        "n_wins": n,
        "k_not_t40": k,
        "estimate": None if n == 0 else k / n,
        "pct": pct,
        "wilson_ci95": [lo, hi],
        "object": f"P(¬T40 | W, {label})",
    }


def slice_rows(rows: list[dict], buckets: tuple[str, ...] | str) -> list[dict]:
    want = (buckets,) if isinstance(buckets, str) else buckets
    return [r for r in rows if r.get("entry_bucket") in want]


def split_of(game_date: str | None, research_end: str, val_end: str) -> str:
    if not game_date:
        return "UNSPLIT"
    if game_date <= research_end:
        return "IN_SAMPLE"
    if game_date <= val_end:
        return "VALIDATION"
    return "OOS"


def by_split(rows: list[dict], research_end: str, val_end: str) -> dict:
    out = {}
    for name in ("IN_SAMPLE", "VALIDATION", "OOS"):
        sub = [
            r
            for r in rows
            if split_of(r.get("game_date"), research_end, val_end) == name
        ]
        out[name] = p_not_t40_given_w(sub, "FIRST75")
    return out


def align_with(rows: list[dict], align_fn, xwalk, cache, bucket_key: str) -> list[dict]:
    for r in rows:
        if r.get("first_80_timestamp") is None:
            r["entry_bucket"] = "UNALIGNED"
            r["alignment_confidence"] = "UNUSABLE"
            continue
        align = align_fn(r, xwalk, cache)
        r["entry_bucket"] = align[bucket_key]
        r["alignment_confidence"] = align.get("alignment_confidence")
        r["alignment_reason"] = align.get("alignment_reason")
    return rows


def frozen_first80(path: Path) -> list[dict]:
    cands = json.loads(path.read_text())
    return [
        dict(c)
        for c in cands
        if c.get("status") == "FIRST_80" and c.get("expiration_result_yes") is not None
    ]


def as_first80_rows(cands: list[dict]) -> list[dict]:
    out = []
    for c in cands:
        won = bool(c["expiration_result_yes"])
        t40 = bool(c.get("stop_close_triggered"))
        rec = dict(c)
        rec["W"] = won
        rec["T40"] = t40
        rec["reach_ts"] = c.get("first_80_timestamp")
        rec["status"] = "FIRST_80"
        out.append(rec)
    return out


def sport_block(
    *,
    sport: str,
    label: str,
    f75: list[dict],
    f80: list[dict],
    slices: dict[str, tuple[str, ...] | str],
    expected_f80_slices: dict[str, int] | None,
    research_end: str,
    val_end: str,
    extra_identity: dict | None = None,
) -> dict:
    part75 = dict(Counter(r.get("entry_bucket") for r in f75))
    part80 = dict(Counter(r.get("entry_bucket") for r in f80))
    if expected_f80_slices:
        for name, n_exp in expected_f80_slices.items():
            got = len(slice_rows(f80, slices[name]))
            if got != n_exp:
                raise IdentityHalt(f"HALT {sport} FIRST80 {name} n={got} expected {n_exp}")
    slice_out = {}
    for name, buckets in slices.items():
        s75 = slice_rows(f75, buckets)
        s80 = slice_rows(f80, buckets)
        slice_out[name] = {
            "FIRST75": p_not_t40_given_w(s75, "FIRST75"),
            "FIRST80": p_not_t40_given_w(s80, "FIRST80"),
            "decomp_FIRST75": decomp_of_rows(s75, 0.75, "FIRST75"),
            "decomp_FIRST80": decomp_of_rows(s80, 0.80, "FIRST80"),
            "FIRST75_splits": by_split(s75, research_end, val_end),
            "partition_note": f"clock at FIRST75/FIRST80 timestamp; UNALIGNED excluded from {name}",
        }
    block = {
        "sport": sport,
        "label": label,
        "FIRST75_full": p_not_t40_given_w(f75, "FIRST75"),
        "FIRST80_full": p_not_t40_given_w(f80, "FIRST80"),
        "decomp_FIRST75_full": decomp_of_rows(f75, 0.75, "FIRST75"),
        "decomp_FIRST80_full": decomp_of_rows(f80, 0.80, "FIRST80"),
        "FIRST75_partition": part75,
        "FIRST80_partition": part80,
        "slices": slice_out,
    }
    if extra_identity:
        block["identity"] = extra_identity
    return block


def run_nba(nba_qbs):
    print("NBA quotes", flush=True)
    markets = A.load_markets()
    games = A.load_games()
    candles = A.NORM / "candles_1m"
    quotes = load_quotes(candles, quote_meta_nba_style(markets, games))
    raw75 = build_first_reach(markets, games, quotes, HIT75, "FIRST_75")
    raw80 = build_first_reach(markets, games, quotes, HIT80, "FIRST_80")
    f75 = settled(raw75, "FIRST_75")
    f80_rec = settled(raw80, "FIRST_80")
    halt_joints(joints(f80_rec), NBA_F80, "NBA reconstructed FIRST80")
    f75j = joints(f75)
    if f75j["n"] != NBA_F75_N or f75j["W"] != NBA_F75_W or f75j["W_not_T40"] != NBA_F75_NOT40_GIVEN_W:
        raise IdentityHalt(f"HALT NBA FIRST75 {f75j}")
    xwalk = nba_qbs.load_crosswalk()
    cache: dict = {}
    align_with(f75, nba_qbs.align_entry, xwalk, cache, "entry_quarter_bucket")
    f80 = as_first80_rows(
        frozen_first80(
            A.ROOT / "derived" / "nba" / "first80_execution_audit" / "candidates.json"
        )
    )
    halt_joints(joints(f80), NBA_F80, "NBA frozen FIRST80")
    cache80: dict = {}
    align_with(f80, nba_qbs.align_entry, xwalk, cache80, "entry_quarter_bucket")
    return sport_block(
        sport="nba",
        label="KXNBAGAME 2025-26",
        f75=f75,
        f80=f80,
        slices={"Q2": "Q2", "Q3": "Q3", "Q2∪Q3": ("Q2", "Q3")},
        expected_f80_slices={"Q2": NBA_F80_Q2, "Q3": NBA_F80_Q3},
        research_end="2025-12-31",
        val_end="2026-03-15",
        extra_identity={
            "FIRST75_full": {"n": NBA_F75_N, "W": NBA_F75_W, "k_not_t40": NBA_F75_NOT40_GIVEN_W}
        },
    )


def run_wnba(wnba_audit, wnba_qbs):
    print("WNBA quotes", flush=True)
    saved = (A.SPLIT_RESEARCH_END, A.SPLIT_VAL_END)
    A.SPLIT_RESEARCH_END = "2025-10-31"
    A.SPLIT_VAL_END = "2026-07-15"
    try:
        markets = wnba_audit.load_markets()
        games = wnba_audit.load_games()
        candles = wnba_audit.NORM / "candles_1m"
        quotes = load_quotes(candles, quote_meta_wnba(markets, games))
        raw75 = build_first_reach(markets, games, quotes, HIT75, "FIRST_75")
        raw80 = build_first_reach(markets, games, quotes, HIT80, "FIRST_80")
        f75 = settled(raw75, "FIRST_75")
        f80_rec = settled(raw80, "FIRST_80")
        halt_joints(joints(f80_rec), WNBA_F80, "WNBA reconstructed FIRST80")
        xwalk = wnba_qbs.P.load_crosswalk() if hasattr(wnba_qbs, "P") else None
        if xwalk is None:
            import sys as _sys

            if str(WNBA_SCRIPTS) not in _sys.path:
                _sys.path.insert(0, str(WNBA_SCRIPTS))
            import wnba_pbp_align as WP  # noqa: E402

            xwalk = WP.load_crosswalk()
        cache: dict = {}
        align_with(f75, wnba_qbs.align_entry, xwalk, cache, "entry_quarter_bucket")
        f80 = as_first80_rows(
            frozen_first80(
                wnba_audit.ROOT
                / "derived"
                / "wnba"
                / "first80_execution_audit"
                / "candidates.json"
            )
        )
        halt_joints(joints(f80), WNBA_F80, "WNBA frozen FIRST80")
        cache80: dict = {}
        align_with(f80, wnba_qbs.align_entry, xwalk, cache80, "entry_quarter_bucket")
        return sport_block(
            sport="wnba",
            label="KXWNBAGAME warehouse",
            f75=f75,
            f80=f80,
            slices={"Q2": "Q2", "Q3": "Q3", "Q2∪Q3": ("Q2", "Q3")},
            expected_f80_slices={"Q2": WNBA_F80_Q2, "Q3": WNBA_F80_Q3},
            research_end="2025-10-31",
            val_end="2026-07-15",
        )
    finally:
        A.SPLIT_RESEARCH_END, A.SPLIT_VAL_END = saved


def run_ncaab(ncaab_audit, ncaab_hbs):
    print("NCAAB P5 quotes", flush=True)
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
    candles = ncaab_audit.NORM / "candles_1m"
    quotes = load_quotes(candles, quote_meta_nba_style(markets, p5_games))
    raw75 = build_first_reach(markets, p5_games, quotes, HIT75, "FIRST_75")
    raw80 = build_first_reach(markets, p5_games, quotes, HIT80, "FIRST_80")
    f75 = settled(raw75, "FIRST_75")
    f80_rec = settled(raw80, "FIRST_80")
    halt_joints(joints(f80_rec), NCAAB_P5_F80, "NCAAB P5 reconstructed FIRST80")
    xwalk = ncaab_hbs.P.load_crosswalk()
    cache: dict = {}
    align_with(f75, ncaab_hbs.align_entry, xwalk, cache, "entry_half_bucket")
    frozen = ncaab_hbs.load_frozen_p5_first80()
    f80 = as_first80_rows(frozen)
    halt_joints(joints(f80), NCAAB_P5_F80, "NCAAB P5 frozen FIRST80")
    cache80: dict = {}
    align_with(f80, ncaab_hbs.align_entry, xwalk, cache80, "entry_half_bucket")
    return sport_block(
        sport="ncaab_p5",
        label="KXNCAAMBGAME P5 vs P5 2025-26",
        f75=f75,
        f80=f80,
        slices={
            "H1_2": "H1_2",
            "H2_1": "H2_1",
            "H1_2∪H2_1": ("H1_2", "H2_1"),
        },
        expected_f80_slices={"H1_2": NCAAB_F80_H12, "H2_1": NCAAB_F80_H21},
        research_end="2025-12-31",
        val_end="2026-03-15",
    )


def _fmt_p(block: dict) -> str:
    if not block["n_wins"]:
        return "n/a"
    ci = block["wilson_ci95"]
    return (
        f"{block['k_not_t40']}/{block['n_wins']} = **{block['pct']}%** "
        f"(CI {ci[0]}–{ci[1]})"
    )


def write_report(summary: dict) -> None:
    lines = [
        "# P(¬T40 | W, FIRST75) on requested clock slices",
        "",
        "Research only. Same tradable-cross rule as FIRST80, threshold **75¢**.",
        "T40 is a later tradable `yes_bid_close ≤ 40¢`. Clock is snapped at the",
        "FIRST75 timestamp, not the FIRST80 timestamp.",
        "",
        "```",
        "LIVE EXECUTION = FALSE",
        "CANDLE PATH ≠ ACTUAL FILL",
        "OBSERVED CALIBRATION DEVIATION ≠ PROVEN MARKET INEFFICIENCY",
        "```",
        "",
        "NCAAB uses the established **P5 vs P5** universe (same as the H1_2 / H2_1",
        "FIRST80 half-bin work). UNALIGNED prints are not in these slices.",
        "",
    ]
    order = [
        ("wnba", "WNBA", (("Q2", "2Q"), ("Q3", "3Q"), ("Q2∪Q3", "2Q ∪ 3Q"))),
        ("nba", "NBA", (("Q2", "2Q"), ("Q3", "3Q"), ("Q2∪Q3", "2Q ∪ 3Q"))),
        (
            "ncaab_p5",
            "NCAAB P5",
            (
                ("H1_2", "1H second 10"),
                ("H2_1", "2H first 10"),
                ("H1_2∪H2_1", "1H-2nd-10 ∪ 2H-1st-10"),
            ),
        ),
    ]
    lines.extend(
        [
            "## Asked quantity",
            "",
            "| Sport | Slice | W | ¬T40 ∩ W | P(¬T40 \\| W, FIRST75) | 95% Wilson |",
            "|---|---|---:|---:|---:|---|",
        ]
    )
    for key, sport_name, slices in order:
        block = summary["sports"][key]
        for sk, slabel in slices:
            p = block["slices"][sk]["FIRST75"]
            ci = p["wilson_ci95"]
            ci_s = "—" if ci[0] is None else f"{ci[0]}–{ci[1]}"
            pct = "—" if p["pct"] is None else f"{p['pct']}%"
            lines.append(
                f"| {sport_name} | {slabel} | {p['n_wins']} | {p['k_not_t40']} | **{pct}** | {ci_s} |"
            )
    cal = summary.get("terminal_calibration_first75") or {}
    if cal:
        lines.extend(
            [
                "",
                "## P(W | FIRST75) and terminal residual α₇₅ = P(W|FIRST75) − 0.75",
                "",
                "K = 0.75 is the triggering quote, not a fill.",
                "α₇₅ is an observed residual, not a proven inefficiency.",
                "",
                "| Sport | Slice | N₇₅ | N_W,₇₅ | P(W \\| FIRST75) | 95% Wilson | α₇₅ (pp) | α₇₅ Wilson | CI vs 75% |",
                "|---|---|---:|---:|---:|---|---:|---|---|",
            ]
        )
        for row in cal["slices"]:
            ci = row["wilson_ci95"]
            aci = row["alpha_wilson_ci95"]
            excl = "excludes 75%" if row["ci_excludes_75"] else "includes 75%"
            lines.append(
                f"| {row['sport']} | {row['slice_label']} | {row['N75']} | {row['N_W75']} | "
                f"**{row['pct']}%** | {ci[0]}–{ci[1]} | "
                f"{row['alpha_75_pct_points']:+.4f} | {aci[0]:+.4f}–{aci[1]:+.4f} | {excl} |"
            )
        pooled = cal["pooled_six_asked_rows"]
        pci = pooled["wilson_ci95"]
        paci = pooled["alpha_wilson_ci95"]
        pexcl = "excludes 75%" if pooled["ci_excludes_75"] else "includes 75%"
        lines.extend(
            [
                f"| **pooled six** | asked rows | **{pooled['N75']}** | **{pooled['N_W75']}** | "
                f"**{pooled['pct']}%** | {pci[0]}–{pci[1]} | "
                f"**{pooled['alpha_75_pct_points']:+.4f}** | {paci[0]:+.4f}–{paci[1]:+.4f} | {pexcl} |",
                "",
                "Pooled weighting: one observation per FIRST75 event "
                f"({pooled['N_W75']}/{pooled['N75']}), not the unweighted mean of six rates.",
            ]
        )
    lines.extend(
        [
            "",
            "## FIRST80 on the same clock slices (control, not retuned)",
            "",
            "| Sport | Slice | P(¬T40 \\| W, FIRST80) | P(¬T40 \\| W, FIRST75) |",
            "|---|---|---|---|",
        ]
    )
    for key, sport_name, slices in order:
        block = summary["sports"][key]
        for sk, slabel in slices:
            a = block["slices"][sk]["FIRST80"]
            b = block["slices"][sk]["FIRST75"]
            lines.append(
                f"| {sport_name} | {slabel} | {_fmt_p(a)} | {_fmt_p(b)} |"
            )
    lines.extend(
        [
            "",
            "## Full-tape FIRST75 (identity / context)",
            "",
        ]
    )
    for key, sport_name, _ in order:
        block = summary["sports"][key]
        p = block["FIRST75_full"]
        lines.append(f"- **{sport_name}**: {_fmt_p(p)}; settled FIRST75 n={p['n_total']}")
    lines.extend(
        [
            "",
            "NBA full-tape FIRST75 is gated to the 2026-09-04 alpha-decomp count",
            "(1176 settled / 915 winners / 781 never-T40).",
            "",
            "## What this is not",
            "",
            "- Not a live order, fill, or realized P&L.",
            "- Not proof that FIRST80 has an independent path edge vs FIRST75.",
            "- α₇₅ ≠ executable edge. Observed calibration residual ≠ proven inefficiency.",
            "- Not MLB FIRST01.",
            "",
            "**LIVE DEPLOYMENT: NOT AUTHORIZED**",
            "",
        ]
    )
    text = "\n".join(lines) + "\n"
    for dest in (REPORTS, DOCS, WH_OUT):
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "REPORT.md").write_text(text)


def analyze() -> dict:
    nba_qbs = load_module(
        "nba_qbs_align_f75", NBA_SCRIPTS / "first80_quarter_barrier_survival.py"
    )
    wnba_audit = load_module(
        "wnba_8040_f75", WNBA_SCRIPTS / "wnba_80_40_execution_audit.py"
    )
    wnba_qbs = load_module(
        "wnba_qbs_align_f75", WNBA_SCRIPTS / "first80_quarter_barrier_survival.py"
    )
    ncaab_audit = load_module(
        "ncaab_8040_f75", NCAAB_SCRIPTS / "ncaab_80_40_execution_audit.py"
    )
    ncaab_hbs = load_module(
        "ncaab_hbs_align_f75", NCAAB_SCRIPTS / "first80_p5_half_barrier_survival.py"
    )
    sports = {
        "wnba": run_wnba(wnba_audit, wnba_qbs),
        "nba": run_nba(nba_qbs),
        "ncaab_p5": run_ncaab(ncaab_audit, ncaab_hbs),
    }
    return {
        "written_utc": utc_now(),
        "research_only": True,
        "candle_path_not_fill": True,
        "live_execution_changed": False,
        "definition": (
            "FIRST75 = first tradable yes_bid_close >= 75 after prior tradable "
            "close < 75, uncrossed spread <= 10c, one per event, same-minute ties excluded. "
            "T40 = later tradable yes_bid_close <= 40. Clock snapped at FIRST75 timestamp."
        ),
        "sports": sports,
    }


def _pct(x) -> str:
    if x is None:
        return "—"
    return f"{x}%"


def _ci(pair) -> str:
    if not pair or pair[0] is None:
        return "—"
    return f"{pair[0]}–{pair[1]}"


def _pp(x) -> str:
    if x is None:
        return "—"
    return f"{x:+.4f}"


def write_decomp_report(summary: dict) -> None:
    asked = [
        ("wnba", "WNBA", "Q2", "2Q"),
        ("wnba", "WNBA", "Q3", "3Q"),
        ("nba", "NBA", "Q2", "2Q"),
        ("nba", "NBA", "Q3", "3Q"),
        ("ncaab_p5", "NCAAB P5", "H1_2", "1H second 10"),
        ("ncaab_p5", "NCAAB P5", "H2_1", "2H first 10"),
    ]
    lines = [
        "# FIRST75 terminal × path efficiency",
        "",
        "Same frozen FIRST75 / FIRST80 / T40 definitions. Clock snapped at the",
        "threshold timestamp. Candle path, not fills. Does not retune either rule.",
        "",
        "```",
        "LIVE EXECUTION = FALSE",
        "CANDLE PATH ≠ ACTUAL FILL",
        "OBSERVED CALIBRATION DEVIATION ≠ PROVEN MARKET INEFFICIENCY",
        "```",
        "",
        "Model:",
        "",
        "`P(W ∩ ¬T40 | FIRST_q) = P(W | FIRST_q) × P(¬T40 | W, FIRST_q)`",
        "",
        "`S = P(¬T40 | FIRST_q) = p · s_W + (1 − p) · s_L`",
        "",
        "K is the triggering quote (0.75 or 0.80), not a fill.",
        "α = P(W|FIRST_q) − K. Tests are exact binomial vs K",
        "(scipy `binomtest`; one-sided greater / one-sided less / two-sided).",
        "",
        "## 1. Terminal calibration  P(W | FIRST75)",
        "",
        "| Sport | Slice | N | W | P(W) | Wilson | Clopper–Pearson | α₇₅ (pp) | two-sided p | CI vs 75% |",
        "|---|---|---:|---:|---:|---|---|---:|---:|---|",
    ]
    for sport, sname, sl, slabel in asked:
        d = summary["sports"][sport]["slices"][sl]["decomp_FIRST75"]
        t = d["terminal"]
        vs = t.get("vs_null") or {}
        excl = "excludes K" if t["wilson_excludes_k"] else "includes K"
        p2 = vs.get("p_two_sided")
        p2s = "—" if p2 is None else f"{p2:.4g}"
        lines.append(
            f"| {sname} | {slabel} | {d['n']} | {d['N_W']} | **{_pct(t['pct'])}** | "
            f"{_ci(t['wilson_ci95'])} | {_ci(t['clopper_pearson_ci95'])} | "
            f"{_pp(t['alpha_pct_points'])} | {p2s} | {excl} |"
        )
    p75 = summary["pooled_six_decomp"]["FIRST75"]
    t = p75["terminal"]
    vs = t.get("vs_null") or {}
    lines.append(
        f"| **pooled six** | asked rows | **{p75['n']}** | **{p75['N_W']}** | "
        f"**{_pct(t['pct'])}** | {_ci(t['wilson_ci95'])} | {_ci(t['clopper_pearson_ci95'])} | "
        f"**{_pp(t['alpha_pct_points'])}** | {vs.get('p_two_sided', 0):.4g} | "
        f"{'excludes K' if t['wilson_excludes_k'] else 'includes K'} |"
    )
    lines.extend(
        [
            "",
            "One-sided tests (pooled FIRST75 vs 0.75): "
            f"greater p={vs.get('p_one_sided_greater'):.4g}, "
            f"less p={vs.get('p_one_sided_less'):.4g}.",
            "",
            "## 2. Winner path  P(¬T40 | W)  and loser path  P(¬T40 | L)",
            "",
            "| Sport | Slice | W | W∩¬T40 | s_W | L | L∩¬T40 | s_L |",
            "|---|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for sport, sname, sl, slabel in asked:
        d = summary["sports"][sport]["slices"][sl]["decomp_FIRST75"]
        lines.append(
            f"| {sname} | {slabel} | {d['N_W']} | {d['winner_path']['k']} | "
            f"**{_pct(d['winner_path']['pct'])}** | {d['N_L']} | {d['loser_path']['k']} | "
            f"**{_pct(d['loser_path']['pct'])}** |"
        )
    lines.append(
        f"| **pooled six** | asked rows | **{p75['N_W']}** | **{p75['winner_path']['k']}** | "
        f"**{_pct(p75['winner_path']['pct'])}** | **{p75['N_L']}** | **{p75['loser_path']['k']}** | "
        f"**{_pct(p75['loser_path']['pct'])}** |"
    )
    lines.extend(
        [
            "",
            "s_L Wilson (pooled): "
            f"{_ci(p75['loser_path']['wilson_ci95'])}. "
            "A 0 here means every measured loser later close-touched 40 "
            "(minute-close measurement, not a continuity proof).",
            "",
            "## 3. Four-cell joint  (W, L) × (¬T40, T40)",
            "",
            "| Sport | Slice | W∩¬T40 | W∩T40 | L∩¬T40 | L∩T40 | sum |",
            "|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    for sport, sname, sl, slabel in asked:
        c = summary["sports"][sport]["slices"][sl]["decomp_FIRST75"]["cells"]
        n = sum(c.values())
        lines.append(
            f"| {sname} | {slabel} | {c['W_and_not_T40']} | {c['W_and_T40']} | "
            f"{c['L_and_not_T40']} | {c['L_and_T40']} | {n} |"
        )
    c = p75["cells"]
    lines.append(
        f"| **pooled six** | asked rows | **{c['W_and_not_T40']}** | **{c['W_and_T40']}** | "
        f"**{c['L_and_not_T40']}** | **{c['L_and_T40']}** | **{p75['n']}** |"
    )
    lines.extend(
        [
            "",
            "## 4. Unconditional objects and the product identity",
            "",
            "| Sport | Slice | p | s_W | p·s_W = P(W∩¬T40) | S = P(¬T40) |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for sport, sname, sl, slabel in asked:
        d = summary["sports"][sport]["slices"][sl]["decomp_FIRST75"]
        r = d["reconstruction"]
        lines.append(
            f"| {sname} | {slabel} | {d['terminal']['pct']}% | {d['winner_path']['pct']}% | "
            f"**{_pct(d['joint_win_survive']['pct'])}** | **{_pct(d['unconditional_barrier']['pct'])}** |"
        )
    lines.append(
        f"| **pooled six** | asked rows | {p75['terminal']['pct']}% | {p75['winner_path']['pct']}% | "
        f"**{_pct(p75['joint_win_survive']['pct'])}** | **{_pct(p75['unconditional_barrier']['pct'])}** |"
    )
    cf = p75["counterfactual_p_at_quote"]
    lines.extend(
        [
            "",
            f"Pooled reconstruction: p·s_W = {p75['reconstruction']['p_times_s_W']:.6f} "
            f"= observed joint {p75['cell_probs']['W_and_not_T40']:.6f}. "
            f"S = {p75['reconstruction']['S']:.6f}.",
            "",
            f"If p were set to K=0.75 and s_W held: joint → {cf['joint_if_p_equals_k']:.4f} "
            f"(delta {cf['delta_vs_observed_joint']:+.4f}). **Not a forecast.**",
            "",
            "## 5. FIRST75 vs FIRST80 on the same clock slices (not retuned)",
            "",
            "| Sport | Slice | p₇₅ | s_W,₇₅ | joint₇₅ | p₈₀ | s_W,₈₀ | joint₈₀ |",
            "|---|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for sport, sname, sl, slabel in asked:
        a = summary["sports"][sport]["slices"][sl]["decomp_FIRST75"]
        b = summary["sports"][sport]["slices"][sl]["decomp_FIRST80"]
        lines.append(
            f"| {sname} | {slabel} | {_pct(a['terminal']['pct'])} | {_pct(a['winner_path']['pct'])} | "
            f"**{_pct(a['joint_win_survive']['pct'])}** | {_pct(b['terminal']['pct'])} | "
            f"{_pct(b['winner_path']['pct'])} | **{_pct(b['joint_win_survive']['pct'])}** |"
        )
    p80 = summary["pooled_six_decomp"]["FIRST80"]
    lines.append(
        f"| **pooled six** | asked rows | {_pct(p75['terminal']['pct'])} | {_pct(p75['winner_path']['pct'])} | "
        f"**{_pct(p75['joint_win_survive']['pct'])}** | {_pct(p80['terminal']['pct'])} | "
        f"{_pct(p80['winner_path']['pct'])} | **{_pct(p80['joint_win_survive']['pct'])}** |"
    )
    lines.extend(
        [
            "",
            "FIRST80 null for α is K=0.80, not 0.75.",
            f"Pooled FIRST80 four-cell: W∩¬T40={p80['cells']['W_and_not_T40']}, "
            f"W∩T40={p80['cells']['W_and_T40']}, "
            f"L∩¬T40={p80['cells']['L_and_not_T40']}, "
            f"L∩T40={p80['cells']['L_and_T40']}.",
            "",
            "## 6. What this is not",
            "",
            "- Not a live order, fill, or realized P&L.",
            "- Not proof of a tradable inefficiency.",
            "- A high s_W is not an independent FIRST80 path edge.",
            "- L∩¬T40 = 0 is a minute-close measurement, not proof losers cannot skip 40.",
            "- If 2026–27 terminal p moves toward K, s_W and s_L can move separately.",
            "- Not MLB FIRST01.",
            "",
            "**LIVE DEPLOYMENT: NOT AUTHORIZED**",
            "",
        ]
    )
    text = "\n".join(lines) + "\n"
    for dest in (DECOMP_REPORTS, DECOMP_DOCS, WH_OUT):
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "TERMINAL_PATH_REPORT.md").write_text(text)
    DECOMP_REPORTS.mkdir(parents=True, exist_ok=True)
    (DECOMP_REPORTS / "REPORT.md").write_text(text)


def write_outputs(summary: dict) -> None:
    attach_terminal_calibration(summary)
    attach_pooled_decomp(summary)
    for dest in (REPORTS, DOCS, WH_OUT, DECOMP_REPORTS, DECOMP_DOCS):
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    write_report(summary)
    write_decomp_report(summary)
    brief = {}
    for sport, block in summary["sports"].items():
        brief[sport] = {
            name: {
                "FIRST75": {
                    "n_wins": v["FIRST75"]["n_wins"],
                    "k_not_t40": v["FIRST75"]["k_not_t40"],
                    "pct": v["FIRST75"]["pct"],
                }
            }
            for name, v in block["slices"].items()
        }
    print(json.dumps(brief, indent=2))


def main() -> int:
    write_outputs(analyze())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
