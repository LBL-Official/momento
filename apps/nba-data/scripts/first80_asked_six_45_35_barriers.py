#!/usr/bin/env python3
"""Asked-six close-path touches at 45¢ and 35¢ (research only).

45 is above the 40 stop. 35 is below it.

- T45 = first later tradable yes_bid_close ≤ 45. Nested: T40 ⇒ T45.
  Survivors at 45 = T45 ∧ ¬T40 (dipped to 41–45, never printed 40).
  A separate 45 print exists only when the first ≤45 close is still 41–45.
  If the first ≤45 close is already ≤40, 45 and 40 printed on the same bar.

- T35 = first later tradable yes_bid_close ≤ 35. Nested: T35 ⇒ T40.
  Among losers, “survived 35” = T40 ∧ ¬T35 (hit 40, never printed 35).
  Recovery after 35 = T35 ∧ terminal YES (already a 40-stop on the 80/40 book).

```
RESEARCH ONLY
CANDLE PATH ≠ ACTUAL FILL
LIVE EXECUTION = FALSE
DO NOT CHANGE LIVE FIRST01
DO NOT RETUNE FIRST80 / T40 FROM THIS TABLE
```
"""

from __future__ import annotations

import csv
import json
import math
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
OUT = REPO / "research" / "first80_asked_six_45_35_barriers"
WH_OUT = E.WH_OUT.parent / "first80_asked_six_45_35_barriers"

EXPECTED_N = 1182
EXPECTED_WIN = 883
EXPECTED_STOP = 299
LEVELS = (45, 40, 35)
LEVEL_E4 = {45: 4500, 40: 4000, 35: 3500}


class IdentityHalt(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def wilson(k: int, n: int, z: float = 1.96):
    if n <= 0:
        return None, None, None
    p = k / n
    z2 = z * z
    den = 1.0 + z2 / n
    center = (p + z2 / (2 * n)) / den
    rad = z * math.sqrt((p * (1 - p) + z2 / (4 * n)) / n) / den
    return (
        round(p * 100, 4),
        round(max(0.0, center - rad) * 100, 4),
        round(min(1.0, center + rad) * 100, 4),
    )


def first_touches(quotes: list[dict], t0: int) -> dict:
    """First later tradable close ≤ L. Quotes are e4."""
    found_ts = {c: None for c in LEVELS}
    found_px = {c: None for c in LEVELS}
    had_q = True
    for q in quotes:
        ts = int(q["ts"])
        if ts <= int(t0):
            continue
        if not E.quality_ok(q, had_q):
            continue
        had_q = True
        bid = q.get("bid_c")
        if bid is None:
            continue
        for cents, e4 in LEVEL_E4.items():
            if found_ts[cents] is None and int(bid) <= e4:
                found_ts[cents] = ts
                found_px[cents] = L.e4_to_cents(bid)
        if all(v is not None for v in found_ts.values()):
            break
    return {
        "t45_ts": found_ts[45],
        "t45_close": found_px[45],
        "t40_ts": found_ts[40],
        "t40_close": found_px[40],
        "t35_ts": found_ts[35],
        "t35_close": found_px[35],
    }


def sport_mod(sport: str):
    return L.sport_mod(sport)


def scan_book() -> list[dict]:
    ledger = list(csv.DictReader(LEDGER.open()))
    caches: dict[str, dict[str, Path]] = {}
    rows = []
    n_win = n_stop = 0
    for rec in ledger:
        win = Q.as_bool(rec["win_80_40"])
        stop = Q.as_bool(rec["stopped_40"])
        if win == stop:
            raise IdentityHalt(rec["ticker"])
        n_win += int(win)
        n_stop += int(stop)
        sport = rec["sport"]
        if sport not in caches:
            caches[sport] = E.index_candles(sport_mod(sport).CANDLES_DIR)
        path = caches[sport].get(rec["ticker"])
        entry_ts = int(float(rec["timestamp"]))
        row = {
            "sport": sport,
            "slice": rec["slice"],
            "event_id": rec["event_id"],
            "ticker": rec["ticker"],
            "dataset_split": rec["dataset_split"],
            "timestamp": entry_ts,
            "win_80_40": win,
            "stopped_40": stop,
            "terminal_yes": Q.as_bool(rec["W"]),
            "t45": False,
            "t40": False,
            "t35": False,
            "t45_close": None,
            "t40_close": None,
            "t35_close": None,
            "t45_separate_print": False,
            "t40_already_le35": False,
            "label": "CANDLE_PATH_NOT_FILL",
        }
        if path is None:
            raise IdentityHalt(f"HALT no candle {rec['ticker']}")
        quotes = E.load_ticker_quotes(path)
        t = first_touches(quotes, entry_ts)
        row["t45"] = t["t45_ts"] is not None
        row["t40"] = t["t40_ts"] is not None
        row["t35"] = t["t35_ts"] is not None
        row["t45_close"] = t["t45_close"]
        row["t40_close"] = t["t40_close"]
        row["t35_close"] = t["t35_close"]
        row["t45_ts"] = t["t45_ts"]
        row["t40_ts"] = t["t40_ts"]
        row["t35_ts"] = t["t35_ts"]
        if row["t45"] and row["t45_close"] is not None:
            row["t45_separate_print"] = 41 <= int(row["t45_close"]) <= 45
        if row["t40"] and row["t40_close"] is not None:
            row["t40_already_le35"] = int(row["t40_close"]) <= 35
        if row["t40"] != stop:
            raise IdentityHalt(
                f"HALT T40 vs stopped_40 {rec['ticker']} scan={row['t40']} ledger={stop}"
            )
        if row["t35"] and not row["t40"]:
            raise IdentityHalt(f"HALT T35 not subset T40 {rec['ticker']}")
        if row["t40"] and not row["t45"]:
            raise IdentityHalt(f"HALT T40 not subset T45 {rec['ticker']}")
        rows.append(row)
    if (len(rows), n_win, n_stop) != (EXPECTED_N, EXPECTED_WIN, EXPECTED_STOP):
        raise IdentityHalt(f"HALT identity {len(rows)}/{n_win}/{n_stop}")
    return rows


def rate(k: int, n: int) -> dict:
    p, lo, hi = wilson(k, n)
    return {"k": k, "n": n, "pct": p, "wilson95": [lo, hi]}


def summarize(rows: list[dict]) -> dict:
    t45 = [r for r in rows if r["t45"]]
    t40 = [r for r in rows if r["t40"]]
    t35 = [r for r in rows if r["t35"]]
    t45_survive = [r for r in t45 if not r["t40"]]
    t45_lose = [r for r in t45 if r["t40"]]
    t45_sep = [r for r in t45 if r["t45_separate_print"]]
    t45_sep_surv = [r for r in t45_sep if not r["t40"]]
    t45_sep_lose = [r for r in t45_sep if r["t40"]]
    t45_same = [r for r in t45 if r["t45"] and not r["t45_separate_print"]]
    t40_not_35 = [r for r in t40 if not r["t35"]]
    t40_and_35 = [r for r in t40 if r["t35"]]
    t35_yes = [r for r in t35 if r["terminal_yes"]]
    t35_no = [r for r in t35 if not r["terminal_yes"]]
    gap_40_35 = [r for r in t40 if r["t40_already_le35"]]

    def sport_block(sport: str) -> dict:
        sub = [r for r in rows if r["sport"] == sport]
        s45 = [r for r in sub if r["t45"]]
        s40 = [r for r in sub if r["t40"]]
        s35 = [r for r in sub if r["t35"]]
        return {
            "n": len(sub),
            "T45": rate(len(s45), len(sub)),
            "P_T40_given_T45": rate(sum(1 for r in s45 if r["t40"]), len(s45)),
            "P_survive_given_T45": rate(sum(1 for r in s45 if not r["t40"]), len(s45)),
            "T40": rate(len(s40), len(sub)),
            "P_T35_given_T40": rate(sum(1 for r in s40 if r["t35"]), len(s40)),
            "P_never_35_given_T40": rate(sum(1 for r in s40 if not r["t35"]), len(s40)),
            "T35_and_terminal_yes": sum(1 for r in s35 if r["terminal_yes"]),
        }

    return {
        "n": len(rows),
        "T45": {
            "n": len(t45),
            "lose_T40": rate(len(t45_lose), len(t45)),
            "survive_not_T40": rate(len(t45_survive), len(t45)),
            "separate_print_41_45": {
                "n": len(t45_sep),
                "lose_T40": rate(len(t45_sep_lose), len(t45_sep)) if t45_sep else rate(0, 0),
                "survive_not_T40": rate(len(t45_sep_surv), len(t45_sep)) if t45_sep else rate(0, 0),
                "note": "First ≤45 close was still 41–45. A 45-area print existed before 40.",
            },
            "first_print_already_le40": {
                "n": len(t45_same),
                "note": "First ≤45 close was already ≤40. No separate 45 print.",
            },
        },
        "T40": {
            "n": len(t40),
            "continued_to_35": rate(len(t40_and_35), len(t40)),
            "never_printed_35": rate(len(t40_not_35), len(t40)),
            "same_bar_already_le35": rate(len(gap_40_35), len(t40)),
        },
        "T35": {
            "n": len(t35),
            "terminal_yes": rate(len(t35_yes), len(t35)) if t35 else rate(0, 0),
            "terminal_no": rate(len(t35_no), len(t35)) if t35 else rate(0, 0),
            "note": "T35 ⇒ T40. win_80_40 is already False. Survival here is settlement YES after 35.",
        },
        "by_sport": {s: sport_block(s) for s in ("NBA", "WNBA", "NCAAB")},
    }


def write_report(doc: dict) -> str:
    t45 = doc["T45"]
    t40 = doc["T40"]
    t35 = doc["T35"]
    sep = t45["separate_print_41_45"]
    lines = [
        "# Asked-six 45¢ / 35¢ barrier counts",
        "",
        "```",
        "RESEARCH ONLY",
        "CANDLE PATH ≠ ACTUAL FILL",
        "LIVE EXECUTION = FALSE",
        "DO NOT CHANGE LIVE FIRST01",
        "DO NOT RETUNE FIRST80 FROM THIS TABLE",
        "```",
        "",
        f"Generated: `{doc['generated_at']}`",
        "",
        "## Universe",
        "",
        f"- n = **{EXPECTED_N}** FIRST80 asked-six trades",
        f"- win_80_40 = **{EXPECTED_WIN}** (never printed 40)",
        f"- STOP_40 = **{EXPECTED_STOP}** (printed ≤40)",
        "- T45 = first later tradable close ≤45. T40 ⇒ T45.",
        "- T35 = first later tradable close ≤35. T35 ⇒ T40.",
        "",
        "## 45¢ — early level above the stop",
        "",
        f"- Touched 45: **{t45['n']}** / {EXPECTED_N}",
        f"- Of those, then lost (went to 40): **{t45['lose_T40']['k']}** "
        f"({t45['lose_T40']['pct']:.1f}%, Wilson "
        f"{t45['lose_T40']['wilson95'][0]:.1f}–{t45['lose_T40']['wilson95'][1]:.1f})",
        f"- Of those, survived (never printed 40): **{t45['survive_not_T40']['k']}** "
        f"({t45['survive_not_T40']['pct']:.1f}%, Wilson "
        f"{t45['survive_not_T40']['wilson95'][0]:.1f}–{t45['survive_not_T40']['wilson95'][1]:.1f})",
        "",
        "Every one of the 299 losers touched 45, because ≤40 is ≤45.",
        "The survivors at 45 are winners who dipped into 41–45 and came back.",
        "",
        "### Did a 45 print exist before 40?",
        "",
        f"- First ≤45 close was still **41–45**: **{sep['n']}**. "
        f"Then lost: **{sep['lose_T40']['k']}** ({sep['lose_T40']['pct']:.1f}%). "
        f"Then survived: **{sep['survive_not_T40']['k']}** "
        f"({sep['survive_not_T40']['pct']:.1f}%).",
        f"- First ≤45 close was already **≤40**: **{t45['first_print_already_le40']['n']}**. "
        "No separate 45 print — 45 and 40 arrived on the same bar.",
        "",
        "If you flatten at a *separate* 45 print, you exit some trades that",
        "would have survived, and you also get out before some 40s. You do",
        "not get a 45 print on the same-bar blow-throughs.",
        "",
        "## 35¢ — continuation below the stop",
        "",
        f"- Touched 35: **{t35['n']}** (all of these already printed 40)",
        f"- Of the 299 losers, continued to 35: **{t40['continued_to_35']['k']}** "
        f"({t40['continued_to_35']['pct']:.1f}%)",
        f"- Of the 299 losers, never printed 35: **{t40['never_printed_35']['k']}** "
        f"({t40['never_printed_35']['pct']:.1f}%) — this is “survived 35”",
        f"- Of the 299, first 40-print was already ≤35: "
        f"**{t40['same_bar_already_le35']['k']}** "
        f"({t40['same_bar_already_le35']['pct']:.1f}%) — blew through 40 and 35 together",
        "",
        f"Among the {t35['n']} who printed 35:",
        f"- Later settled YES: **{t35['terminal_yes']['k']}** "
        f"({t35['terminal_yes']['pct']:.1f}%) — recovered after 35; still a 40-stop on 80/40",
        f"- Settled NO: **{t35['terminal_no']['k']}** ({t35['terminal_no']['pct']:.1f}%)",
        "",
        "## By sport",
        "",
        "| Sport | n | T45 | P(T40\\|T45) | P(survive\\|T45) | P(T35\\|T40) | P(never 35\\|T40) |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for sport, b in doc["by_sport"].items():
        lines.append(
            f"| {sport} | {b['n']} | {b['T45']['k']} | "
            f"{b['P_T40_given_T45']['pct']:.1f}% | "
            f"{b['P_survive_given_T45']['pct']:.1f}% | "
            f"{b['P_T35_given_T40']['pct']:.1f}% | "
            f"{b['P_never_35_given_T40']['pct']:.1f}% |"
        )
    lines += [
        "",
        "## Exit reading (not a retune)",
        "",
        "- **45** is a pre-stop warning. P(go to 40 | touch 45) is the cost of",
        "  staying. P(survive | touch 45) is the winners you would sell early.",
        "- **35** is a post-stop chase level. Most 40s that blow through get here.",
        "  Never-35 is the group where a 40-area print was the path low-ish close.",
        "- None of this is a fill. Do not change live FIRST01.",
        "",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    print("scanning 1,182 asked-six tickers for T45 / T40 / T35…", flush=True)
    rows = scan_book()
    summary = summarize(rows)
    doc = {
        "generated_at": utc_now(),
        "identity": {
            "n": EXPECTED_N,
            "win_80_40": EXPECTED_WIN,
            "stopped_40": EXPECTED_STOP,
        },
        "constraints": [
            "RESEARCH ONLY",
            "CANDLE PATH ≠ ACTUAL FILL",
            "LIVE EXECUTION = FALSE",
            "DO NOT CHANGE LIVE FIRST01",
            "DO NOT RETUNE FIRST80 FROM THIS TABLE",
        ],
        **summary,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    WH_OUT.mkdir(parents=True, exist_ok=True)
    fields = [
        "sport",
        "slice",
        "event_id",
        "ticker",
        "dataset_split",
        "timestamp",
        "win_80_40",
        "stopped_40",
        "terminal_yes",
        "t45",
        "t40",
        "t35",
        "t45_close",
        "t40_close",
        "t35_close",
        "t45_separate_print",
        "t40_already_le35",
        "label",
    ]
    with (OUT / "touches.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    (OUT / "summary.json").write_text(json.dumps(doc, indent=2) + "\n")
    (OUT / "REPORT.md").write_text(write_report(doc))
    for fn in ("touches.csv", "summary.json", "REPORT.md"):
        (WH_OUT / fn).write_text((OUT / fn).read_text())
    print(
        f"T45={summary['T45']['n']} "
        f"lose={summary['T45']['lose_T40']['k']} "
        f"surv={summary['T45']['survive_not_T40']['k']} "
        f"sep45={summary['T45']['separate_print_41_45']['n']} "
        f"T35={summary['T35']['n']} "
        f"T40_never35={summary['T40']['never_printed_35']['k']}"
    )
    print(f"wrote {OUT / 'REPORT.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
