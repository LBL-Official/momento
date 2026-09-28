"""One-shot first-touch scan for 65/60/55 on the derived four. Research only."""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path

SCRIPTS = Path("/Users/user/Desktop/Momento/apps/nba-data/scripts")
sys.path.insert(0, str(SCRIPTS))

import first80_asked_six_chatgpt_export as E  # noqa: E402
import first80_asked_six_80_40_liquidation as L  # noqa: E402

LEDGER = Path("/Users/user/Desktop/Momento/research/first80_asked_six_chatgpt_export/first80_asked_six.csv")
OUT = Path("/Users/user/Desktop/Momento/research/choosin_texas/t60_band/touches.json")
LEVELS = (65, 60, 55, 40)
LEVEL_E4 = {65: 6500, 60: 6000, 55: 5500, 40: 4000}
HALT_LEVELS = (65, 60, 55)
WANTED = {("NBA", "Q2"), ("NBA", "Q3"), ("NCAAB", "H1_2"), ("NCAAB", "H2_1")}
PERIOD_ORDER = ("Q2", "Q3", "Q4", "OT")
CLOCK_BINS = ("12:00-9:01", "9:00-6:01", "6:00-3:01", "3:00-0:00")


def clock_bin(remaining_s: int) -> str:
    if remaining_s > 9 * 60:
        return "12:00-9:01"
    if remaining_s > 6 * 60:
        return "9:00-6:01"
    if remaining_s > 3 * 60:
        return "6:00-3:01"
    return "3:00-0:00"


def period_label(period: int) -> str:
    if period >= 5:
        return "OT"
    if period in (2, 3, 4):
        return f"Q{period}"
    raise RuntimeError(f"unexpected period {period}")


def first_touches(quotes: list[dict], t0: int) -> dict:
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
    return found_ts, found_px


def main() -> None:
    caches: dict[str, dict[str, Path]] = {}
    pbp_cache: dict = {}
    xwalk = E.NBA_Q.load_crosswalk()
    rows = []
    missing_clock = []
    with LEDGER.open(newline="", encoding="utf-8") as fh:
        for rec in csv.DictReader(fh):
            key = (rec["sport"].strip(), rec["slice"].strip())
            if key not in WANTED:
                continue
            sport = key[0]
            if sport not in caches:
                caches[sport] = E.index_candles(L.sport_mod(sport).CANDLES_DIR)
            path = caches[sport].get(rec["ticker"])
            if path is None:
                raise SystemExit(f"HALT no candle {rec['ticker']}")
            quotes = E.load_ticker_quotes(path)
            found_ts, found_px = first_touches(quotes, int(float(rec["timestamp"])))
            post_min = int(round(float(rec["post_entry_min_yes_bid_cents"])))
            touched = {c: found_ts[c] is not None for c in LEVELS}
            for cents in HALT_LEVELS:
                if touched[cents] != (post_min <= cents):
                    raise SystemExit(
                        f"HALT {rec['ticker']} T{cents} scan={touched[cents]} min={post_min}"
                    )
            if touched[40] != (post_min <= 40):
                raise SystemExit(
                    f"HALT {rec['ticker']} T40 scan={touched[40]} min={post_min}"
                )
            entry_ts = int(float(rec["timestamp"]))
            exit_ts_raw = rec.get("exit_timestamp")
            if exit_ts_raw in (None, ""):
                raise SystemExit(f"HALT {rec['ticker']} missing exit_timestamp")
            ledger_exit_ts = int(float(exit_ts_raw))
            exit_kind = str(rec.get("exit_kind") or "")
            if exit_kind == "T40_CLOSE":
                if found_ts[40] is None or int(found_ts[40]) != ledger_exit_ts:
                    raise SystemExit(
                        f"HALT {rec['ticker']} t40_ts {found_ts[40]} != ledger {ledger_exit_ts}"
                    )
            elif found_ts[40] is not None:
                raise SystemExit(f"HALT {rec['ticker']} t40_ts set without T40_CLOSE")
            if touched[65] and (found_ts[65] is None or int(found_ts[65]) <= entry_ts):
                raise SystemExit(f"HALT {rec['ticker']} t65_ts {found_ts[65]}")
            if touched[65] and touched[40] and int(found_ts[65]) > int(found_ts[40]):
                raise SystemExit(
                    f"HALT {rec['ticker']} t65_ts {found_ts[65]} after t40_ts {found_ts[40]}"
                )
            item = {
                "ticker": rec["ticker"],
                "sport": sport,
                "slice": key[1],
                "post_min": post_min,
                "t65_close": found_px[65],
                "t65_ts": found_ts[65],
                "t60_close": found_px[60],
                "t55_close": found_px[55],
                "t40_ts": found_ts[40],
                "t65_separate": bool(found_px[65] is not None and 61 <= int(found_px[65]) <= 65),
                "t60_separate": bool(found_px[60] is not None and 56 <= int(found_px[60]) <= 60),
                "t60_already_le55": bool(found_px[60] is not None and int(found_px[60]) <= 55),
            }
            if sport == "NBA" and touched[60]:
                cw = xwalk.get(rec["event_id"]) or {}
                nba_id = cw.get("nba_game_id")
                packed = E.NBA_Q._pbp_pack(nba_id, pbp_cache) if nba_id else None
                actions = packed[0] if packed else []
                play = E.play_at(actions, found_ts[60])
                if not play or play.get("period") is None or play.get("remaining_s") is None:
                    missing_clock.append(rec["ticker"])
                else:
                    period = period_label(int(play["period"]))
                    remaining = int(round(float(play["remaining_s"])))
                    item["exit_period"] = period
                    item["exit_remaining_s"] = remaining
                    item["clock_bin"] = clock_bin(remaining)
            rows.append(item)
            if len(rows) % 100 == 0:
                print(f"scanned {len(rows)}", flush=True)
    if missing_clock:
        raise SystemExit(f"HALT missing T60 clock n={len(missing_clock)} sample={missing_clock[:8]}")
    nba_t60 = [r for r in rows if r["sport"] == "NBA" and r["t60_close"] is not None]
    period_mix = {
        slice_id: Counter(r["exit_period"] for r in nba_t60 if r["slice"] == slice_id)
        for slice_id in ("Q2", "Q3")
    }
    bins = {
        slice_id: Counter((r["exit_period"], r["clock_bin"]) for r in nba_t60 if r["slice"] == slice_id)
        for slice_id in ("Q2", "Q3")
    }
    t65 = [r for r in rows if r["t65_close"] is not None]
    t60 = [r for r in rows if r["t60_close"] is not None]
    summary = {
        "n": len(rows),
        "t65_n": len(t65),
        "t65_ts_n": sum(1 for r in rows if r.get("t65_ts") is not None),
        "t40_ts_n": sum(1 for r in rows if r.get("t40_ts") is not None),
        "t65_separate_61_65": sum(1 for r in t65 if r["t65_separate"]),
        "t65_first_already_le60": sum(1 for r in t65 if not r["t65_separate"]),
        "t65_separate_then_t60": sum(1 for r in t65 if r["t65_separate"] and r["t60_close"] is not None),
        "t65_separate_survive_60": sum(1 for r in t65 if r["t65_separate"] and r["t60_close"] is None),
        "t60_n": len(t60),
        "t60_separate_56_60": sum(1 for r in t60 if r["t60_separate"]),
        "t60_first_already_le55": sum(1 for r in t60 if r["t60_already_le55"]),
        "nba_t60_n": len(nba_t60),
        "period_mix": {k: dict(v) for k, v in period_mix.items()},
        "bins": {k: {f"{a}|{b}": n for (a, b), n in v.items()} for k, v in bins.items()},
        "mean_remaining": {},
    }
    for slice_id in ("Q2", "Q3"):
        by_period: dict[str, list[int]] = {p: [] for p in PERIOD_ORDER}
        for r in nba_t60:
            if r["slice"] == slice_id:
                by_period[r["exit_period"]].append(int(r["exit_remaining_s"]))
        summary["mean_remaining"][slice_id] = {
            p: {"n": len(vals), "sum_s": sum(vals)} for p, vals in by_period.items() if vals
        }
    OUT.write_text(json.dumps({"summary": summary, "rows": rows}, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
