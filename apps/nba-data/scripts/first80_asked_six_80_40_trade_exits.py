#!/usr/bin/env python3
"""Per-trade candle-path exits for the asked-six 80/40 book.

Every row gets an exit under each declared definition. Averages are
unweighted means of those 1,182 exits. Not fills. Does not change live
FIRST01.

```
RESEARCH ONLY
CANDLE PATH ≠ ACTUAL FILL
LIVE EXECUTION = FALSE
DO NOT CHANGE LIVE FIRST01
```

Wins: 80/40 rule exit is settlement 100¢.
Stops: labeled 40¢ is the signal, not a fill. T40 close / +1m / +5m min
are candle-path diagnostics from the frozen post-T40 scan.
last_tradable is rest-of-path, not the 80/40 exit (stop median is 0).
"""

from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import first80_asked_six_chatgpt_export as E  # noqa: E402
import first80_asked_six_80_40_liquidation as L  # noqa: E402
import first80_asked_six_80_40_quant_paths as Q  # noqa: E402

REPO = Path("/Users/user/Desktop/Momento")
LEDGER = E.OUT / "first80_asked_six.csv"
T40_JSON = L.OUT / "post_t40_5m.json"
OUT = REPO / "research" / "first80_asked_six_80_40_trade_exits"
WH_OUT = E.WH_OUT.parent / "first80_asked_six_80_40_trade_exits"

EXPECTED_N = L.EXPECTED_N
EXPECTED_WIN = L.EXPECTED_WIN
EXPECTED_STOP = L.EXPECTED_STOP
ENTRY_CENTS = 80
WIN_EXIT = 100
LABELED_STOP = 40


class IdentityHalt(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def mean_cents(xs: list[int | float] | np.ndarray) -> float | None:
    arr = np.asarray(list(xs), dtype=np.float64)
    if arr.size == 0:
        return None
    return round(float(arr.mean()), 4)


def pnl_from_exit(exit_cents: int) -> int:
    return int(exit_cents) - ENTRY_CENTS


def load_t40() -> dict[tuple[str, int], dict]:
    if not T40_JSON.is_file():
        raise IdentityHalt(f"HALT missing {T40_JSON} — run liquidation scan first")
    recs = json.loads(T40_JSON.read_text())
    out = {}
    for r in recs:
        key = (r["ticker"], int(r["entry_ts"]))
        out[key] = r
    if len(out) != EXPECTED_STOP:
        raise IdentityHalt(f"HALT t40 n={len(out)}")
    if not all(r.get("found") and r.get("t40_close") is not None for r in recs):
        raise IdentityHalt("HALT t40 close missing")
    return out


def build_rows() -> list[dict]:
    ledger = list(csv.DictReader(LEDGER.open()))
    t40_map = load_t40()
    rows = []
    n_win = n_stop = 0
    for rec in ledger:
        win = Q.as_bool(rec["win_80_40"])
        stop = Q.as_bool(rec["stopped_40"])
        if win == stop:
            raise IdentityHalt(f"HALT win/stop {rec['ticker']}")
        entry_ts = int(float(rec["timestamp"]))
        labeled = WIN_EXIT if win else LABELED_STOP
        t40_close = WIN_EXIT
        close_1m = WIN_EXIT
        close_2m = WIN_EXIT
        close_5m = WIN_EXIT
        min_5m = WIN_EXIT
        t40_rec = None
        if stop:
            n_stop += 1
            t40_rec = t40_map.get((rec["ticker"], entry_ts))
            if t40_rec is None:
                raise IdentityHalt(f"HALT no t40 {rec['ticker']}")
            t40_close = int(t40_rec["t40_close"])
            close_1m = (
                int(t40_rec["close_1m"])
                if t40_rec.get("close_1m") is not None
                else None
            )
            close_2m = (
                int(t40_rec["close_2m"])
                if t40_rec.get("close_2m") is not None
                else None
            )
            close_5m = (
                int(t40_rec["close_5m"])
                if t40_rec.get("close_5m") is not None
                else None
            )
            if t40_rec.get("min_close_5m") is not None:
                min_5m = int(t40_rec["min_close_5m"])
            else:
                min_5m = t40_close
        else:
            n_win += 1
        last = Q.as_float(rec.get("last_tradable_yes_bid_cents"))
        last_i = None if last is None else int(round(last))
        rows.append(
            {
                "sport": rec["sport"],
                "slice": rec["slice"],
                "event_id": rec["event_id"],
                "ticker": rec["ticker"],
                "game_date": rec["game_date"],
                "dataset_split": rec["dataset_split"],
                "timestamp": entry_ts,
                "win_80_40": win,
                "stopped_40": stop,
                "entry_cents": ENTRY_CENTS,
                "exit_labeled_cents": labeled,
                "exit_t40_close_cents": t40_close,
                "exit_plus_1m_cents": close_1m,
                "exit_plus_2m_cents": close_2m,
                "exit_plus_5m_cents": close_5m,
                "exit_5m_min_cents": min_5m,
                "pnl_labeled_cents": pnl_from_exit(labeled),
                "pnl_t40_close_cents": pnl_from_exit(t40_close),
                "pnl_5m_min_cents": pnl_from_exit(min_5m),
                "last_tradable_cents": last_i,
                "last_tradable_is_not_rule_exit": True,
                "t40_n_bars_5m": None if t40_rec is None else t40_rec.get("n_bars_5m"),
                "label": "CANDLE_PATH_NOT_FILL",
            }
        )
    if (len(rows), n_win, n_stop) != (EXPECTED_N, EXPECTED_WIN, EXPECTED_STOP):
        raise IdentityHalt(f"HALT identity {len(rows)}/{n_win}/{n_stop}")
    return rows


def subset(rows: list[dict], pred) -> list[dict]:
    return [r for r in rows if pred(r)]


def avg_block(rows: list[dict]) -> dict:
    def col(name: str) -> list[int]:
        return [int(r[name]) for r in rows if r.get(name) is not None]

    labeled = col("exit_labeled_cents")
    t40 = col("exit_t40_close_cents")
    m5 = col("exit_5m_min_cents")
    c1 = col("exit_plus_1m_cents")
    c2 = col("exit_plus_2m_cents")
    c5 = col("exit_plus_5m_cents")
    last = col("last_tradable_cents")
    return {
        "n": len(rows),
        "n_win": sum(1 for r in rows if r["win_80_40"]),
        "n_stop": sum(1 for r in rows if r["stopped_40"]),
        "avg_exit_labeled_cents": mean_cents(labeled),
        "avg_exit_t40_close_cents": mean_cents(t40),
        "avg_exit_plus_1m_cents": mean_cents(c1),
        "avg_exit_plus_2m_cents": mean_cents(c2),
        "avg_exit_plus_5m_cents": mean_cents(c5),
        "avg_exit_5m_min_cents": mean_cents(m5),
        "avg_last_tradable_cents": mean_cents(last),
        "avg_pnl_labeled_cents": mean_cents(col("pnl_labeled_cents")),
        "avg_pnl_t40_close_cents": mean_cents(col("pnl_t40_close_cents")),
        "avg_pnl_5m_min_cents": mean_cents(col("pnl_5m_min_cents")),
        "note": "Unweighted mean of per-trade exits. NOT a fill.",
    }


def summarize(rows: list[dict]) -> dict:
    groups = {
        "ALL": avg_block(rows),
        "WINS": avg_block(subset(rows, lambda r: r["win_80_40"])),
        "STOPS": avg_block(subset(rows, lambda r: r["stopped_40"])),
    }
    for sport in ("NBA", "WNBA", "NCAAB"):
        groups[sport] = avg_block(subset(rows, lambda r, s=sport: r["sport"] == s))
        groups[f"{sport}_STOPS"] = avg_block(
            subset(rows, lambda r, s=sport: r["sport"] == s and r["stopped_40"])
        )
    for split in ("IN_SAMPLE", "VALIDATION", "OOS"):
        groups[split] = avg_block(
            subset(rows, lambda r, s=split: r["dataset_split"] == s)
        )
    return groups


def write_report(doc: dict) -> str:
    a = doc["averages"]
    lines = [
        "# Asked-six 80/40 per-trade exits",
        "",
        "```",
        "RESEARCH ONLY",
        "CANDLE PATH ≠ ACTUAL FILL",
        "LIVE EXECUTION = FALSE",
        "DO NOT CHANGE LIVE FIRST01",
        "```",
        "",
        f"Generated: `{doc['generated_at']}`",
        "",
        "## Identity",
        "",
        f"- n = **{EXPECTED_N}**",
        f"- wins = **{EXPECTED_WIN}** — rule exit **100¢** (settlement YES)",
        f"- STOP_40 = **{EXPECTED_STOP}** — labeled **40¢** is the signal, not a fill",
        "- Entry is 80¢ on every row. P&L = exit − 80.",
        "",
        "## Average exit — all 1,182 trades",
        "",
        "Each trade has one exit under each definition. The number below is",
        "the unweighted mean of those 1,182 values.",
        "",
        "| Definition | Avg exit | Avg P&L | What it is |",
        "|---|---:|---:|---|",
        f"| Labeled 80/40 | **{a['ALL']['avg_exit_labeled_cents']:.2f}¢** | "
        f"{a['ALL']['avg_pnl_labeled_cents']:+.2f}¢ | "
        "883×100 + 299×40. Assumes every stop fills at 40. |",
        f"| T40 close | **{a['ALL']['avg_exit_t40_close_cents']:.2f}¢** | "
        f"{a['ALL']['avg_pnl_t40_close_cents']:+.2f}¢ | "
        "Wins 100. Stops = first tradable close ≤40. |",
        f"| +1m after T40 | {a['ALL']['avg_exit_plus_1m_cents']:.2f}¢ | "
        f"{a['ALL']['avg_exit_plus_1m_cents'] - ENTRY_CENTS:+.2f}¢ | "
        "Wins 100. Stops with a +1m bar only. |",
        f"| +5m min close | **{a['ALL']['avg_exit_5m_min_cents']:.2f}¢** | "
        f"{a['ALL']['avg_pnl_5m_min_cents']:+.2f}¢ | "
        "Wins 100. Stops = worst tradable close in the next 5 minutes. |",
        f"| last_tradable | {a['ALL']['avg_last_tradable_cents']:.2f}¢ | "
        f"{a['ALL']['avg_last_tradable_cents'] - ENTRY_CENTS:+.2f}¢ | "
        "**Not** the 80/40 exit. Stop median is 0 (hold-to-expiry). |",
        "",
        "## Average exit — the 299 stops only",
        "",
        "| Definition | Avg exit | Avg loss vs 80 | n |",
        "|---|---:|---:|---:|",
        f"| Labeled 40 | {a['STOPS']['avg_exit_labeled_cents']:.2f}¢ | "
        f"{a['STOPS']['avg_pnl_labeled_cents']:+.2f}¢ | {a['STOPS']['n']} |",
        f"| T40 close | **{a['STOPS']['avg_exit_t40_close_cents']:.2f}¢** | "
        f"{a['STOPS']['avg_pnl_t40_close_cents']:+.2f}¢ | {a['STOPS']['n']} |",
        f"| +1m | {a['STOPS']['avg_exit_plus_1m_cents']:.2f}¢ | "
        f"{a['STOPS']['avg_exit_plus_1m_cents'] - ENTRY_CENTS:+.2f}¢ | "
        f"{a['STOPS'].get('n_plus_1m', '—')} |",
        f"| +2m | {a['STOPS']['avg_exit_plus_2m_cents']:.2f}¢ | "
        f"{a['STOPS']['avg_exit_plus_2m_cents'] - ENTRY_CENTS:+.2f}¢ | "
        f"{a['STOPS'].get('n_plus_2m', '—')} |",
        f"| +5m close | {a['STOPS']['avg_exit_plus_5m_cents']:.2f}¢ | "
        f"{a['STOPS']['avg_exit_plus_5m_cents'] - ENTRY_CENTS:+.2f}¢ | "
        f"{a['STOPS'].get('n_plus_5m', '—')} |",
        f"| +5m min | **{a['STOPS']['avg_exit_5m_min_cents']:.2f}¢** | "
        f"{a['STOPS']['avg_pnl_5m_min_cents']:+.2f}¢ | {a['STOPS']['n']} |",
        "",
        "## Wins",
        "",
        f"- n = {a['WINS']['n']}. Rule exit = **100¢** on every winning trade.",
        f"- last_tradable mean = {a['WINS']['avg_last_tradable_cents']:.2f}¢ "
        "(almost all 99; settlement is still 100).",
        "",
        "## By sport",
        "",
        "| Book | n | labeled | T40 close | 5m min |",
        "|---|---:|---:|---:|---:|",
    ]
    for key in ("NBA", "WNBA", "NCAAB", "NBA_STOPS", "WNBA_STOPS", "NCAAB_STOPS"):
        b = a[key]
        lines.append(
            f"| {key} | {b['n']} | {b['avg_exit_labeled_cents']:.2f}¢ | "
            f"{b['avg_exit_t40_close_cents']:.2f}¢ | "
            f"{b['avg_exit_5m_min_cents']:.2f}¢ |"
        )
    lines += [
        "",
        "## By split",
        "",
        "| Split | n | labeled | T40 close | 5m min |",
        "|---|---:|---:|---:|---:|",
    ]
    for key in ("IN_SAMPLE", "VALIDATION", "OOS"):
        b = a[key]
        lines.append(
            f"| {key} | {b['n']} | {b['avg_exit_labeled_cents']:.2f}¢ | "
            f"{b['avg_exit_t40_close_cents']:.2f}¢ | "
            f"{b['avg_exit_5m_min_cents']:.2f}¢ |"
        )
    lines += [
        "",
        "## Files",
        "",
        "- `trade_exits.csv` — one row per trade, integer cents.",
        "- `summary.json` — the averages above.",
        "",
        "None of these exits is a Kalshi fill.",
        "",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    rows = build_rows()
    averages = summarize(rows)
    # Fill stop +1m n in report via summary counts
    n1 = sum(r["exit_plus_1m_cents"] is not None for r in rows if r["stopped_40"])
    n2 = sum(r["exit_plus_2m_cents"] is not None for r in rows if r["stopped_40"])
    n5 = sum(r["exit_plus_5m_cents"] is not None for r in rows if r["stopped_40"])
    averages["STOPS"]["n_plus_1m"] = n1
    averages["STOPS"]["n_plus_2m"] = n2
    averages["STOPS"]["n_plus_5m"] = n5
    doc = {
        "generated_at": utc_now(),
        "identity": {
            "n": EXPECTED_N,
            "win_80_40": EXPECTED_WIN,
            "stopped_40": EXPECTED_STOP,
            "entry_cents": ENTRY_CENTS,
        },
        "constraints": [
            "RESEARCH ONLY",
            "CANDLE PATH ≠ ACTUAL FILL",
            "LIVE EXECUTION = FALSE",
            "DO NOT CHANGE LIVE FIRST01",
        ],
        "averages": averages,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    WH_OUT.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0].keys())
    with (OUT / "trade_exits.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    (OUT / "summary.json").write_text(json.dumps(doc, indent=2) + "\n")
    (OUT / "REPORT.md").write_text(write_report(doc))
    for fn in ("trade_exits.csv", "summary.json", "REPORT.md"):
        (WH_OUT / fn).write_text((OUT / fn).read_text())
    print(
        f"ALL labeled={averages['ALL']['avg_exit_labeled_cents']} "
        f"t40={averages['ALL']['avg_exit_t40_close_cents']} "
        f"5mmin={averages['ALL']['avg_exit_5m_min_cents']}"
    )
    print(
        f"STOPS labeled={averages['STOPS']['avg_exit_labeled_cents']} "
        f"t40={averages['STOPS']['avg_exit_t40_close_cents']} "
        f"5mmin={averages['STOPS']['avg_exit_5m_min_cents']}"
    )
    print(f"wrote {OUT / 'trade_exits.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
