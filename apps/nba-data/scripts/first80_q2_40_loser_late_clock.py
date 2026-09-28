#!/usr/bin/env python3
"""FIRST80→40 losers: when the 40 close-path printed in the last 6:00.

NBA slices: 2Q and 3Q FIRST80. Clock is 4Q remaining at first
yes_bid_close ≤ 40. OT (period ≥ 5) is separate.

Research only. Does not change live FIRST01. Uses the existing quarter
barrier T40 clock. Does not invent a fill.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import first80_quarter_barrier_survival as Q  # noqa: E402

OUT = Q.OUT.parent / "first80_q2_40_loser_late_clock"
LAST_MINUTES = (6, 5, 4, 3, 2, 1)
BIN_ORDER = (
    "BEFORE_LAST_6",
    "5:01–6:00",
    "4:01–5:00",
    "3:01–4:00",
    "2:01–3:00",
    "1:01–2:00",
    "0:00–1:00",
    "OT",
    "NO_CLOCK",
)

NBA_CLOSING_PERIOD = 4
NBA_OT_MIN_PERIOD = 5
NBA_SLICES = {
    "Q2": {"n": 314, "losers": 47, "t40": 75, "label": "2Q"},
    "Q3": {"n": 290, "losers": 52, "t40": 79, "label": "3Q"},
}


class IdentityHalt(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def closing_remaining_s(
    period: int | None,
    remaining_s: float | None,
    closing_period: int,
) -> float | None:
    """Remaining on the closing regulation period. None if not in that period."""
    if period is None or remaining_s is None:
        return None
    if int(period) != int(closing_period):
        return None
    return float(remaining_s)


def is_ot(period: int | None, ot_min_period: int) -> bool:
    return period is not None and int(period) >= int(ot_min_period)


def hit_with_at_most_k_min(
    period: int | None,
    remaining_s: float | None,
    k_min: int,
    closing_period: int = NBA_CLOSING_PERIOD,
    ot_min_period: int = NBA_OT_MIN_PERIOD,
) -> bool:
    """True iff first T40 is in the closing period with remaining ≤ k minutes.

    OT is not that period.
    """
    rem = closing_remaining_s(period, remaining_s, closing_period)
    if rem is None:
        return False
    if is_ot(period, ot_min_period):
        return False
    return rem <= float(k_min) * 60.0


def discrete_last6_bin(
    period: int | None,
    remaining_s: float | None,
    closing_period: int = NBA_CLOSING_PERIOD,
    ot_min_period: int = NBA_OT_MIN_PERIOD,
) -> str:
    if period is None or remaining_s is None:
        return "NO_CLOCK"
    if is_ot(period, ot_min_period):
        return "OT"
    rem = closing_remaining_s(period, remaining_s, closing_period)
    if rem is None:
        return "BEFORE_LAST_6"
    if rem > 360.0:
        return "BEFORE_LAST_6"
    if rem > 300.0:
        return "5:01–6:00"
    if rem > 240.0:
        return "4:01–5:00"
    if rem > 180.0:
        return "3:01–4:00"
    if rem > 120.0:
        return "2:01–3:00"
    if rem > 60.0:
        return "1:01–2:00"
    return "0:00–1:00"


def rate(k: int, n: int) -> float | None:
    if n <= 0:
        return None
    return round(100.0 * k / n, 2)


def format_period_clock(seconds: float | None) -> str | None:
    return Q.format_clock(seconds)


def analyze_slice(
    rows: list[dict],
    *,
    entry_field: str,
    bucket: str,
    expected_n: int | None,
    expected_losers: int | None,
    expected_t40: int | None,
    closing_period: int,
    ot_min_period: int,
    closing_label: str,
    label: str,
) -> dict:
    sub = [r for r in rows if r.get(entry_field) == bucket]
    if expected_n is not None and len(sub) != expected_n:
        raise IdentityHalt(f"HALT {bucket} n={len(sub)} expected {expected_n}")
    losers = [r for r in sub if not r.get("W")]
    t40 = [r for r in sub if r.get("T40")]
    if expected_losers is not None and len(losers) != expected_losers:
        raise IdentityHalt(f"HALT {bucket} losers n={len(losers)} expected {expected_losers}")
    if expected_t40 is not None and len(t40) != expected_t40:
        raise IdentityHalt(f"HALT {bucket} T40 n={len(t40)} expected {expected_t40}")
    leak = [r for r in losers if not r.get("T40")]
    if leak:
        raise IdentityHalt(f"HALT {bucket} loser without T40 n={len(leak)}")

    n_lose = len(losers)
    missing = [
        r.get("ticker")
        for r in losers
        if r.get("t40_period") is None or r.get("t40_period_remaining_s") is None
    ]
    if missing:
        raise IdentityHalt(f"HALT {bucket} loser T40 clock missing {missing[:5]}")

    cumulative = []
    for k in LAST_MINUTES:
        hit = [
            r
            for r in losers
            if hit_with_at_most_k_min(
                r.get("t40_period"),
                r.get("t40_period_remaining_s"),
                k,
                closing_period,
                ot_min_period,
            )
        ]
        cumulative.append(
            {
                "at_most_min": k,
                "label": f"≤{k}:00 {closing_label} remaining",
                "n": len(hit),
                "pct_of_losers": rate(len(hit), n_lose),
                "pct_of_t40": rate(len(hit), len(t40)),
                "pct_of_slice": rate(len(hit), len(sub)),
            }
        )

    discrete_n = {b: 0 for b in BIN_ORDER}
    games = []
    for r in losers:
        b = discrete_last6_bin(
            r.get("t40_period"),
            r.get("t40_period_remaining_s"),
            closing_period,
            ot_min_period,
        )
        discrete_n[b] += 1
        rem = r.get("t40_period_remaining_s")
        games.append(
            {
                "ticker": r.get("ticker"),
                "event_id": r.get("event_id"),
                "game_date": r.get("game_date"),
                "team": r.get("team"),
                "t40_period": r.get("t40_period"),
                "t40_period_remaining_s": rem,
                "t40_remaining_clock": r.get("t40_remaining_clock"),
                "t40_closing_clock": format_period_clock(rem)
                if r.get("t40_period") == closing_period
                else None,
                "bin": b,
                "in_last_6": b not in ("BEFORE_LAST_6", "NO_CLOCK"),
            }
        )
    games.sort(
        key=lambda g: (
            0 if g["in_last_6"] else 1,
            g.get("t40_period") or 99,
            g.get("t40_period_remaining_s") if g.get("t40_period_remaining_s") is not None else 10**9,
        )
    )

    n_last6 = sum(discrete_n[b] for b in BIN_ORDER if b not in ("BEFORE_LAST_6", "NO_CLOCK"))
    n_last6_reg = n_last6 - discrete_n["OT"]
    n_before = discrete_n["BEFORE_LAST_6"]
    late_games = [g for g in games if g["in_last_6"]]

    return {
        "bucket": bucket,
        "label": label,
        "n": len(sub),
        "n_winners": sum(1 for r in sub if r.get("W")),
        "n_losers": n_lose,
        "n_t40": len(t40),
        "n_t40_before_last_6": n_before,
        "n_t40_last_6_or_ot": n_last6,
        "n_t40_last_6_regulation": n_last6_reg,
        "pct_losers_last_6_or_ot": rate(n_last6, n_lose),
        "pct_losers_before_last_6": rate(n_before, n_lose),
        "cumulative_at_most_k_min": cumulative,
        "discrete_bins": [
            {"bin": b, "n": discrete_n[b], "pct_of_losers": rate(discrete_n[b], n_lose)}
            for b in BIN_ORDER
            if discrete_n[b] or b != "NO_CLOCK"
        ],
        "late_games": late_games,
        "games": games,
    }


def analyze(rows: list[dict] | None = None) -> dict:
    """Q2-only (kept for existing tests)."""
    rows = rows if rows is not None else Q._pq().read_table(Q.OUT / "trades.parquet").to_pylist()
    spec = NBA_SLICES["Q2"]
    slice_ = analyze_slice(
        rows,
        entry_field="entry_quarter_bucket",
        bucket="Q2",
        expected_n=spec["n"],
        expected_losers=spec["losers"],
        expected_t40=spec["t40"],
        closing_period=NBA_CLOSING_PERIOD,
        ot_min_period=NBA_OT_MIN_PERIOD,
        closing_label="4Q",
        label=spec["label"],
    )
    return {
        "written_utc": utc_now(),
        "research_only": True,
        "candle_path_not_fill": True,
        "universe": "KXNBAGAME 2025-26 FIRST80 entry Q2, losers (all close-touch 40)",
        "clock": "4Q remaining at first tradable yes_bid_close <= 40. OT separate. Future OT not invented.",
        "identity": {
            "q2": slice_["n"],
            "losers": slice_["n_losers"],
            "t40": slice_["n_t40"],
            "loser_without_t40": 0,
        },
        **{k: slice_[k] for k in slice_ if k not in ("bucket", "label")},
    }


def analyze_nba_quarters(rows: list[dict] | None = None) -> dict:
    rows = rows if rows is not None else Q._pq().read_table(Q.OUT / "trades.parquet").to_pylist()
    slices = []
    for bucket, spec in NBA_SLICES.items():
        slices.append(
            analyze_slice(
                rows,
                entry_field="entry_quarter_bucket",
                bucket=bucket,
                expected_n=spec["n"],
                expected_losers=spec["losers"],
                expected_t40=spec["t40"],
                closing_period=NBA_CLOSING_PERIOD,
                ot_min_period=NBA_OT_MIN_PERIOD,
                closing_label="4Q",
                label=spec["label"],
            )
        )
    return {
        "written_utc": utc_now(),
        "research_only": True,
        "candle_path_not_fill": True,
        "universe": "KXNBAGAME 2025-26 FIRST80 entry Q2 and Q3, losers (all close-touch 40)",
        "clock": "4Q remaining at first tradable yes_bid_close <= 40. OT separate. Future OT not invented.",
        "slices": slices,
    }


def write_outputs(summary: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print("wrote", OUT / "summary.json")
    blocks = summary["slices"] if "slices" in summary else [summary]
    for block in blocks:
        name = block.get("bucket") or block.get("label") or "slice"
        print(
            name,
            "losers",
            block["n_losers"],
            "before last 6",
            block["n_t40_before_last_6"],
            f"({block['pct_losers_before_last_6']}%)",
            "last 6 or OT",
            block["n_t40_last_6_or_ot"],
            f"({block['pct_losers_last_6_or_ot']}%)",
        )
        for row in block["cumulative_at_most_k_min"]:
            print(" ", row["label"], row["n"], f"{row['pct_of_losers']}% of losers")
        for row in block["discrete_bins"]:
            print("   ", row["bin"], row["n"], f"{row['pct_of_losers']}%")


def main() -> int:
    write_outputs(analyze_nba_quarters())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
