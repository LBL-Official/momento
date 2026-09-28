#!/usr/bin/env python3
"""Average stop loss when a 40¢ print existed vs when it blew through.

The ledger labels every STOP_40 at 40¢. This asks a narrower question:

  On the first tradable close ≤40 after entry, was 40 actually there?
  If not, what was the first available close, and how large was the
  one-bar drop into that print?

```
RESEARCH ONLY
CANDLE PATH ≠ ACTUAL FILL
LIVE EXECUTION = FALSE
DO NOT CHANGE LIVE FIRST01
A 40 CLOSE IS NOT A PROVEN FILL
```

Frozen classes (set before looking at the 299):

- PRINTED_40: first T40 close == 40. Modeled exit 40¢ if we get that print.
- NO_40_PRINT: first T40 close < 40. Modeled exit = that close.
- FAST_GAP: prior tradable close > 40 AND first T40 close < 40 AND
  one-bar drop ≥ 10¢. Price skipped through 40 on the close path.

Mild through (35–39) is reported as a slice of NO_40_PRINT, not a
separate trading rule.
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
OUT = REPO / "research" / "first80_asked_six_80_40_stop_loss"
WH_OUT = E.WH_OUT.parent / "first80_asked_six_80_40_stop_loss"

EXPECTED_STOP = 299
ENTRY_CENTS = 80
FAST_GAP_DROP = 10


class IdentityHalt(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stop_loss_cents(exit_cents: int) -> int:
    """Positive loss magnitude. Entry 80."""
    return ENTRY_CENTS - int(exit_cents)


def classify(rec: dict) -> dict:
    """Assign frozen classes. Does not invent a fill."""
    if not rec.get("found") or rec.get("t40_close") is None:
        raise IdentityHalt(f"HALT missing t40 {rec.get('ticker')}")
    t40 = int(rec["t40_close"])
    prior = rec.get("prior_close")
    prior_i = None if prior is None else int(prior)
    drop = rec.get("drop_from_prior")
    drop_i = None if drop is None else int(drop)
    printed_40 = t40 == 40
    no_40 = t40 < 40
    fast_gap = (
        no_40
        and prior_i is not None
        and prior_i > 40
        and drop_i is not None
        and drop_i >= FAST_GAP_DROP
    )
    if printed_40:
        modeled_exit = 40
        cls = "PRINTED_40"
    else:
        modeled_exit = t40
        cls = "NO_40_PRINT"
    if t40 <= 20:
        depth = "CRASH_LE20"
    elif t40 <= 34:
        depth = "FAST_LE34"
    elif t40 <= 39:
        depth = "MILD_35_39"
    else:
        depth = "AT_40"
    return {
        "class": cls,
        "depth": depth,
        "printed_40": printed_40,
        "no_40_print": no_40,
        "fast_gap": fast_gap,
        "t40_close": t40,
        "prior_close": prior_i,
        "drop_from_prior": drop_i,
        "modeled_exit_cents": modeled_exit,
        "modeled_stop_loss_cents": stop_loss_cents(modeled_exit),
        "label": "CANDLE_PATH_NOT_FILL",
    }


def mean(xs) -> float | None:
    arr = [float(x) for x in xs]
    if not arr:
        return None
    return round(float(np.mean(arr)), 4)


def block(rows: list[dict], pred=None) -> dict:
    pop = [r for r in rows if pred(r)] if pred else rows
    losses = [int(r["modeled_stop_loss_cents"]) for r in pop]
    exits = [int(r["modeled_exit_cents"]) for r in pop]
    t40 = [int(r["t40_close"]) for r in pop]
    drops = [int(r["drop_from_prior"]) for r in pop if r.get("drop_from_prior") is not None]
    priors = [int(r["prior_close"]) for r in pop if r.get("prior_close") is not None]
    m5 = [int(r["min_close_5m"]) for r in pop if r.get("min_close_5m") is not None]
    return {
        "n": len(pop),
        "pct_of_stops": round(100.0 * len(pop) / EXPECTED_STOP, 4),
        "avg_modeled_exit_cents": mean(exits),
        "avg_stop_loss_cents": mean(losses),
        "avg_t40_close": mean(t40),
        "avg_prior_close": mean(priors),
        "avg_drop_from_prior": mean(drops),
        "avg_5m_min": mean(m5),
        "p_fast_gap": round(100.0 * sum(1 for r in pop if r["fast_gap"]) / len(pop), 4) if pop else None,
    }


def write_report(doc: dict) -> str:
    a = doc["averages"]
    return "\n".join(
        [
            "# Asked-six 80/40 — average stop loss when 40 is missing",
            "",
            "```",
            "RESEARCH ONLY",
            "CANDLE PATH ≠ ACTUAL FILL",
            "LIVE EXECUTION = FALSE",
            "A 40 CLOSE IS NOT A PROVEN FILL",
            "DO NOT CHANGE LIVE FIRST01",
            "```",
            "",
            f"Generated: `{doc['generated_at']}`",
            "",
            "## Question",
            "",
            "The book assumes every loser exits at 40¢ (−40¢). What is the",
            "average stop loss if we only get 40 when the first tradable",
            "close ≤40 is actually 40, and otherwise we get that first print?",
            "",
            "## Frozen rule",
            "",
            "- **PRINTED_40** (can try 40): first T40 close == 40. Modeled loss **−40¢**.",
            "- **NO_40_PRINT** (cannot get 40 on that bar): first T40 close < 40.",
            "  Modeled loss = 80 − that close.",
            "- **FAST_GAP**: prior close > 40, first T40 close < 40, one-bar drop ≥ 10¢.",
            "",
            "This is still a candle close, not a Kalshi fill.",
            "",
            "## Average stop loss on the 299 stops",
            "",
            f"- When a 40 print existed (**{a['PRINTED_40']['n']} / 299**, "
            f"{a['PRINTED_40']['pct_of_stops']:.1f}%): "
            f"**−{a['PRINTED_40']['avg_stop_loss_cents']:.2f}¢** "
            f"(exit {a['PRINTED_40']['avg_modeled_exit_cents']:.2f}¢).",
            f"- When it did not (**{a['NO_40_PRINT']['n']} / 299**, "
            f"{a['NO_40_PRINT']['pct_of_stops']:.1f}%): "
            f"**−{a['NO_40_PRINT']['avg_stop_loss_cents']:.2f}¢** "
            f"(exit {a['NO_40_PRINT']['avg_modeled_exit_cents']:.2f}¢).",
            f"- Blended, using 40 only when it printed: "
            f"**−{a['ALL']['avg_stop_loss_cents']:.2f}¢** "
            f"(avg exit {a['ALL']['avg_modeled_exit_cents']:.2f}¢).",
            f"- FAST_GAP subset: **{a['FAST_GAP']['n']} / 299** "
            f"({a['FAST_GAP']['pct_of_stops']:.1f}%), "
            f"avg loss **−{a['FAST_GAP']['avg_stop_loss_cents']:.2f}¢**, "
            f"avg one-bar drop {a['FAST_GAP']['avg_drop_from_prior']}¢ "
            f"from prior {a['FAST_GAP']['avg_prior_close']}¢.",
            "",
            "| Class | n | % | Avg exit | Avg stop loss | Avg prior | Avg drop | 5m min |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
        + [
            (
                f"| {name} | {b['n']} | {b['pct_of_stops']:.1f}% | "
                f"{b['avg_modeled_exit_cents']:.2f}¢ | "
                f"−{b['avg_stop_loss_cents']:.2f}¢ | "
                f"{'—' if b['avg_prior_close'] is None else f'{b['avg_prior_close']:.1f}¢'} | "
                f"{'—' if b['avg_drop_from_prior'] is None else f'{b['avg_drop_from_prior']:.1f}¢'} | "
                f"{'—' if b['avg_5m_min'] is None else f'{b['avg_5m_min']:.1f}¢'} |"
            )
            for name, b in (
                ("ALL stops", a["ALL"]),
                ("PRINTED_40", a["PRINTED_40"]),
                ("NO_40_PRINT", a["NO_40_PRINT"]),
                ("  mild 35–39", a["MILD_35_39"]),
                ("  fast ≤34", a["FAST_LE34"]),
                ("  crash ≤20", a["CRASH_LE20"]),
                ("FAST_GAP (drop≥10)", a["FAST_GAP"]),
            )
        ]
        + [
            "",
            "## What this does to the book",
            "",
            "Wins stay +20¢. 883 wins, 299 stops.",
            "",
            f"- If every stop is −40: EV = +4.82¢/trade.",
            f"- If stops use this modeled loss "
            f"(−{a['ALL']['avg_stop_loss_cents']:.2f}¢): "
            f"EV = {doc['ev_at_observed_p']:+.2f}¢/trade.",
            "",
            "Breakeven average stop loss at 74.70% WR is still **59.06¢**.",
            "This blended loss (first print) is below that line. The 5-minute",
            "chase on NO_40_PRINT is closer to it.",
            "",
            "## Does not",
            "",
            "- Prove a 40 close was liftable.",
            "- Change live FIRST01.",
            "- Use rest-of-game min (hold-to-0 on losers).",
            "",
        ]
    ) + "\n"


def main() -> int:
    ledger = list(csv.DictReader(LEDGER.open()))
    stops = [r for r in ledger if Q.as_bool(r["stopped_40"])]
    if len(stops) != EXPECTED_STOP:
        raise IdentityHalt(f"HALT stops {len(stops)}")
    print("rescanning 299 STOP_40 paths for prior bar + T40 close…", flush=True)
    scanned = L.scan_post_t40(stops)
    rows = []
    for rec in scanned:
        cls = classify(rec)
        rec.update(cls)
        rows.append(rec)
    if len(rows) != EXPECTED_STOP:
        raise IdentityHalt(f"HALT n={len(rows)}")
    n_print = sum(1 for r in rows if r["printed_40"])
    n_no = sum(1 for r in rows if r["no_40_print"])
    if n_print + n_no != EXPECTED_STOP:
        raise IdentityHalt("HALT class split")
    averages = {
        "ALL": block(rows),
        "PRINTED_40": block(rows, lambda r: r["printed_40"]),
        "NO_40_PRINT": block(rows, lambda r: r["no_40_print"]),
        "MILD_35_39": block(rows, lambda r: r["depth"] == "MILD_35_39"),
        "FAST_LE34": block(rows, lambda r: r["depth"] == "FAST_LE34"),
        "CRASH_LE20": block(rows, lambda r: r["depth"] == "CRASH_LE20"),
        "FAST_GAP": block(rows, lambda r: r["fast_gap"]),
    }
    avg_loss = averages["ALL"]["avg_stop_loss_cents"]
    p = 883 / 1182
    ev = round(p * 20.0 - (1.0 - p) * float(avg_loss), 4)
    doc = {
        "generated_at": utc_now(),
        "identity": {"stopped_40": EXPECTED_STOP, "printed_40": n_print, "no_40_print": n_no},
        "constraints": [
            "RESEARCH ONLY",
            "CANDLE PATH ≠ ACTUAL FILL",
            "A 40 CLOSE IS NOT A PROVEN FILL",
            "LIVE EXECUTION = FALSE",
        ],
        "rule": {
            "printed_40": "t40_close == 40 → modeled exit 40",
            "no_40_print": "t40_close < 40 → modeled exit t40_close",
            "fast_gap": "prior>40 and t40<40 and drop>=10",
        },
        "averages": averages,
        "ev_at_observed_p": ev,
        "rows": rows,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    WH_OUT.mkdir(parents=True, exist_ok=True)
    slim = {k: v for k, v in doc.items() if k != "rows"}
    (OUT / "summary.json").write_text(json.dumps(slim, indent=2) + "\n")
    (OUT / "stop_loss_rows.json").write_text(json.dumps(rows, indent=2) + "\n")
    fields = [
        "sport",
        "ticker",
        "dataset_split",
        "class",
        "depth",
        "printed_40",
        "no_40_print",
        "fast_gap",
        "prior_close",
        "t40_close",
        "drop_from_prior",
        "modeled_exit_cents",
        "modeled_stop_loss_cents",
        "close_1m",
        "min_close_5m",
        "label",
    ]
    with (OUT / "stop_loss.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    (OUT / "REPORT.md").write_text(write_report(doc))
    for fn in ("summary.json", "REPORT.md", "stop_loss.csv", "stop_loss_rows.json"):
        (WH_OUT / fn).write_text((OUT / fn).read_text())
    print(
        f"PRINTED_40 n={n_print} loss={averages['PRINTED_40']['avg_stop_loss_cents']} "
        f"NO_40 n={n_no} loss={averages['NO_40_PRINT']['avg_stop_loss_cents']} "
        f"BLEND={averages['ALL']['avg_stop_loss_cents']} "
        f"FAST_GAP n={averages['FAST_GAP']['n']}"
    )
    print(f"wrote {OUT / 'REPORT.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
