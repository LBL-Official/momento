#!/usr/bin/env python3
"""±5 one-minute candles around each asked-six T40 print.

Universe: asked-six FIRST80 (NBA/WNBA Q2∪Q3, NCAAB H1_2∪H2_1).
Rows: the 299 STOP_40 trades. Window is the T40 bar and the five
valid 1m candles before and after it.

```
RESEARCH ONLY
CANDLE PATH ≠ ACTUAL FILL
LIVE EXECUTION = FALSE
DO NOT CHANGE LIVE FIRST01
40 STOP UNCHANGED
This window does not prove a 40¢ bid was liftable.
```
"""

from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import first80_asked_six_chatgpt_export as E  # noqa: E402
import first80_asked_six_80_40_liquidation as L  # noqa: E402
import first80_asked_six_80_40_quant_paths as Q  # noqa: E402

REPO = Path("/Users/user/Desktop/Momento")
LEDGER = E.OUT / "first80_asked_six.csv"
OUT = REPO / "research" / "first80_asked_six_t40_surround_candles"
WH_OUT = E.WH_OUT.parent / "first80_asked_six_t40_surround_candles"

EXPECTED_STOP = 299
WINDOW = 5
CSV_NAME = "t40_surround_pm5.csv"


class IdentityHalt(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def iso(ts: int | None) -> str | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()


def mark_tradable(quotes: list[dict]) -> list[dict]:
    """Copy quotes and set tradable from the FIRST80 quality walk."""
    had_q = True
    out = []
    for q in quotes:
        ok = E.quality_ok(q, had_q)
        if ok:
            had_q = True
        row = dict(q)
        row["tradable"] = bool(ok and q.get("bid_c") is not None)
        out.append(row)
    return out


def find_t40_index(quotes: list[dict], t40_ts: int) -> int | None:
    for i, q in enumerate(quotes):
        if int(q["ts"]) == int(t40_ts):
            return i
    return None


def surround(quotes: list[dict], t40_index: int, window: int = WINDOW) -> list[dict]:
    """Return candles with offset_min in [-window, +window]."""
    out = []
    for off in range(-window, window + 1):
        j = t40_index + off
        if j < 0 or j >= len(quotes):
            continue
        q = quotes[j]
        out.append({**q, "offset_min": off, "is_t40_bar": off == 0})
    return out


def cents(v):
    return L.e4_to_cents(v)


def load_stops() -> list[dict]:
    rows = [r for r in csv.DictReader(LEDGER.open()) if Q.as_bool(r["stopped_40"])]
    if len(rows) != EXPECTED_STOP:
        raise IdentityHalt(f"HALT stops {len(rows)}")
    return rows


CSV_FIELDS = [
    "sport",
    "slice",
    "event_id",
    "ticker",
    "game_date",
    "dataset_split",
    "bought_team",
    "entry_ts",
    "entry_ts_utc",
    "t40_ts",
    "t40_ts_utc",
    "t40_close_cents",
    "offset_min",
    "is_t40_bar",
    "candle_ts",
    "candle_ts_utc",
    "yes_bid_close_cents",
    "yes_ask_close_cents",
    "yes_bid_low_cents",
    "last_cents",
    "spread_cents",
    "volume_hundredths",
    "tradable",
    "close_le40",
    "close_le35",
    "low_le40",
    "n_bars_in_window",
    "label",
    "live_execution",
]


def emit_trade(rec: dict, quotes: list[dict], t40_ts: int, t40_close: int) -> list[dict]:
    marked = mark_tradable(quotes)
    idx = find_t40_index(marked, t40_ts)
    if idx is None:
        return []
    win = surround(marked, idx, WINDOW)
    n = len(win)
    out = []
    for q in win:
        bid = cents(q.get("bid_c"))
        ask = cents(q.get("ask_c"))
        low = cents(q.get("bid_l"))
        last = cents(q.get("last_c"))
        spread = None if bid is None or ask is None else ask - bid
        out.append(
            {
                "sport": rec["sport"],
                "slice": rec["slice"],
                "event_id": rec["event_id"],
                "ticker": rec["ticker"],
                "game_date": rec["game_date"],
                "dataset_split": rec["dataset_split"],
                "bought_team": rec.get("bought_team"),
                "entry_ts": int(float(rec["timestamp"])),
                "entry_ts_utc": rec.get("timestamp_utc"),
                "t40_ts": t40_ts,
                "t40_ts_utc": iso(t40_ts),
                "t40_close_cents": t40_close,
                "offset_min": q["offset_min"],
                "is_t40_bar": q["is_t40_bar"],
                "candle_ts": int(q["ts"]),
                "candle_ts_utc": iso(int(q["ts"])),
                "yes_bid_close_cents": bid,
                "yes_ask_close_cents": ask,
                "yes_bid_low_cents": low,
                "last_cents": last,
                "spread_cents": spread,
                "volume_hundredths": q.get("vol"),
                "tradable": q["tradable"],
                "close_le40": bid is not None and bid <= 40,
                "close_le35": bid is not None and bid <= 35,
                "low_le40": low is not None and low <= 40,
                "n_bars_in_window": n,
                "label": "CANDLE_PATH_NOT_FILL",
                "live_execution": False,
            }
        )
    return out


def main() -> int:
    stops = load_stops()
    caches: dict[str, dict[str, Path]] = {}
    rows: list[dict] = []
    n_found = 0
    n_missing = 0
    print(f"scanning {EXPECTED_STOP} STOP_40 tickers for ±{WINDOW}m around T40…", flush=True)
    for rec in stops:
        sport = rec["sport"]
        if sport not in caches:
            caches[sport] = E.index_candles(L.sport_mod(sport).CANDLES_DIR)
        path = caches[sport].get(rec["ticker"])
        if path is None:
            n_missing += 1
            continue
        quotes = E.load_ticker_quotes(path)
        entry_ts = int(float(rec["timestamp"]))
        ledger_t40 = (
            int(float(rec["exit_timestamp"]))
            if rec.get("exit_timestamp") not in (None, "")
            else None
        )
        win = L.post_t40_window(quotes, entry_ts, ledger_t40)
        if not win.get("found"):
            n_missing += 1
            continue
        emitted = emit_trade(rec, quotes, int(win["t40_ts"]), int(win["t40_close"]))
        if not emitted:
            n_missing += 1
            continue
        n_found += 1
        rows.extend(emitted)
    if n_found != EXPECTED_STOP:
        raise IdentityHalt(f"HALT found {n_found} missing {n_missing}")
    OUT.mkdir(parents=True, exist_ok=True)
    WH_OUT.mkdir(parents=True, exist_ok=True)
    csv_path = OUT / CSV_NAME
    with csv_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        w.writerows(rows)
    offsets = {}
    for r in rows:
        offsets[r["offset_min"]] = offsets.get(r["offset_min"], 0) + 1
    t40_bars = [r for r in rows if r["is_t40_bar"]]
    n_exact40 = sum(1 for r in t40_bars if r["t40_close_cents"] == 40)
    n_le35 = sum(1 for r in t40_bars if r["t40_close_cents"] <= 35)
    summary = {
        "generated_at": utc_now(),
        "identity": {"stopped_40": EXPECTED_STOP, "trades_with_window": n_found},
        "window": WINDOW,
        "n_candle_rows": len(rows),
        "rows_per_offset": {str(k): offsets[k] for k in sorted(offsets)},
        "t40_exact_40": n_exact40,
        "t40_le35": n_le35,
        "csv": str(csv_path),
        "constraints": [
            "RESEARCH ONLY",
            "CANDLE PATH ≠ ACTUAL FILL",
            "LIVE EXECUTION = FALSE",
            "DO NOT CHANGE LIVE FIRST01",
            "40 STOP UNCHANGED",
        ],
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    readme = "\n".join(
        [
            "# Asked-six T40 ±5 candle window",
            "",
            "```",
            "RESEARCH ONLY",
            "CANDLE PATH ≠ ACTUAL FILL",
            "LIVE EXECUTION = FALSE",
            "DO NOT CHANGE LIVE FIRST01",
            "```",
            "",
            f"- Universe: asked-six FIRST80 (NBA/WNBA Q2∪Q3, NCAAB H1_2∪H2_1).",
            f"- Trades: **{EXPECTED_STOP}** STOP_40.",
            f"- File: `{CSV_NAME}` — one row per candle.",
            f"- Window: offset_min **-5 … +5** around the first tradable close ≤40.",
            "- `is_t40_bar` is the stop print. Prices are cents. `tradable` is the FIRST80 quality filter.",
            "- This does **not** prove a 40¢ bid was liftable.",
            "",
        ]
    )
    (OUT / "README.md").write_text(readme)
    for fn in (CSV_NAME, "summary.json", "README.md"):
        (WH_OUT / fn).write_text((OUT / fn).read_text())
    print(f"trades={n_found} rows={len(rows)} wrote {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
