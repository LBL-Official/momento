#!/usr/bin/env python3
"""FIRST80 close-40 / wick-40 segmented by inning × FIRST80-team lead.

Research only. Frozen candidates.json (n=4303). Does not rescan candles.
Does not change live FIRST01 / 80/81/83/89. Does not invent gamePk or L2.

Snap: last completed StatsAPI play with endTime ≤ first_80_timestamp.
Score differential is the FIRST80 yes-team lead (ticker suffix vs home/away).
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
NBA_SCRIPTS = Path("/Users/user/Desktop/Momento/apps/nba-data/scripts")
sys.path.insert(0, str(NBA_SCRIPTS))

import mlb_80_40_execution_audit as mlb_audit  # noqa: E402
import mlb_pbp_statsapi_ingest as ingest  # noqa: E402
import nba_80_40_execution_audit as A  # noqa: E402

CANDIDATES = Path("/Users/user/Desktop/Momento/research/mlb_first80_80_40_v1/candidates.json")
CROSSWALK = ingest.NORM / "game_crosswalk.json"
OUT = ingest.ROOT / "derived" / "mlb" / "first80_inning_score_tensor"
REPORTS = Path("/Users/user/Desktop/Momento/research/mlb_first80_80_40_v1")

EXPECTED_N = 4303
EXPECTED_SURVIVORS = 3326
EXPECTED_CLOSE_STOPS = 977

INNING_ORDER = ("PREGAME", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10+", "POSTGAME", "UNALIGNED")
LEAD_ORDER = ("-4+", "-3", "-2", "-1", "0", "+1", "+2", "+3", "+4+", "NA")
MODELS = (
    ("close_all", "aggressive", "40_close", "all fills + close-stop"),
    ("wick_all", "aggressive", "40_low", "all fills + wick-stop"),
    ("close_high", "conservative", "40_close", "HIGH + close-stop"),
    ("wick_high", "conservative", "40_low", "HIGH + wick-stop"),
)


def parse_iso(ts: str | None) -> int | None:
    if not ts:
        return None
    t = ts.replace("Z", "+00:00")
    try:
        return int(datetime.fromisoformat(t).timestamp())
    except ValueError:
        return None


def load_feed(path: Path) -> dict:
    raw = json.loads(path.read_text())
    if isinstance(raw, dict) and "gameData" in raw:
        return raw
    payload = raw.get("payload") if isinstance(raw, dict) else None
    if isinstance(payload, dict) and "gameData" in payload:
        return payload
    return raw


def yes_code(ticker: str | None) -> str | None:
    if not ticker or "-" not in ticker:
        return None
    code = ticker.rsplit("-", 1)[-1].upper()
    return code or None


def yes_side(code: str | None, away: str, home: str) -> str | None:
    if not code:
        return None
    variants = set(ingest.abbr_variants(code))
    away_hit = bool(set(ingest.abbr_variants(away)) & variants)
    home_hit = bool(set(ingest.abbr_variants(home)) & variants)
    if away_hit and not home_hit:
        return "away"
    if home_hit and not away_hit:
        return "home"
    return None


def lead_bucket(lead: int | None) -> str:
    if lead is None:
        return "NA"
    if lead <= -4:
        return "-4+"
    if lead >= 4:
        return "+4+"
    return f"{lead:+d}" if lead != 0 else "0"


def inning_bucket(phase: str, inning: int | None) -> str:
    if phase == "PREGAME":
        return "PREGAME"
    if phase == "POSTGAME":
        return "POSTGAME"
    if phase == "UNALIGNED" or inning is None:
        return "UNALIGNED"
    if inning >= 10:
        return "10+"
    if 1 <= inning <= 9:
        return str(inning)
    return "UNALIGNED"


def completed_plays(feed: dict) -> list[dict]:
    plays = (((feed.get("liveData") or {}).get("plays") or {}).get("allPlays")) or []
    out = []
    for p in plays:
        about = p.get("about") or {}
        if not about.get("isComplete"):
            continue
        end_ts = parse_iso(about.get("endTime") or p.get("playEndTime"))
        if end_ts is None:
            continue
        result = p.get("result") or {}
        out.append(
            {
                "end_ts": end_ts,
                "start_ts": parse_iso(about.get("startTime")),
                "inning": about.get("inning"),
                "half": about.get("halfInning"),
                "is_top": about.get("isTopInning"),
                "away_score": result.get("awayScore"),
                "home_score": result.get("homeScore"),
            }
        )
    out.sort(key=lambda r: (r["end_ts"], r.get("start_ts") or 0))
    return out


def snap_first80(feed: dict, entry_ts: int, side: str | None) -> dict:
    teams = (feed.get("gameData") or {}).get("teams") or {}
    away_abbr = (teams.get("away") or {}).get("abbreviation") or ""
    home_abbr = (teams.get("home") or {}).get("abbreviation") or ""
    status = (((feed.get("gameData") or {}).get("status") or {}).get("detailedState") or "")
    first_pitch = parse_iso((((feed.get("gameData") or {}).get("datetime") or {}).get("dateTime")))
    plays = completed_plays(feed)
    first_start = plays[0]["start_ts"] if plays and plays[0]["start_ts"] is not None else first_pitch
    last = plays[-1] if plays else None

    if not plays:
        return {
            "phase": "UNALIGNED",
            "inning": None,
            "half": None,
            "away_score": None,
            "home_score": None,
            "lead": None,
            "away_abbreviation": away_abbr,
            "home_abbreviation": home_abbr,
            "reason": "NO_COMPLETED_PLAYS",
        }

    if first_start is not None and entry_ts < first_start:
        lead = 0 if side else None
        return {
            "phase": "PREGAME",
            "inning": None,
            "half": None,
            "away_score": 0,
            "home_score": 0,
            "lead": lead,
            "away_abbreviation": away_abbr,
            "home_abbreviation": home_abbr,
            "reason": "BEFORE_FIRST_PITCH",
        }

    prior = [p for p in plays if p["end_ts"] <= entry_ts]
    if not prior:
        lead = 0 if side else None
        return {
            "phase": "IN_GAME",
            "inning": plays[0]["inning"] or 1,
            "half": plays[0]["half"],
            "away_score": 0,
            "home_score": 0,
            "lead": lead,
            "away_abbreviation": away_abbr,
            "home_abbreviation": home_abbr,
            "reason": "FIRST_AB_IN_PROGRESS",
        }

    snap = prior[-1]
    away_s = snap["away_score"]
    home_s = snap["home_score"]
    lead = None
    if side == "away" and away_s is not None and home_s is not None:
        lead = int(away_s) - int(home_s)
    elif side == "home" and away_s is not None and home_s is not None:
        lead = int(home_s) - int(away_s)

    phase = "IN_GAME"
    reason = "LAST_COMPLETED_PLAY"
    if last and entry_ts > last["end_ts"] and status.lower() == "final":
        phase = "POSTGAME"
        reason = "AFTER_FINAL"

    return {
        "phase": phase,
        "inning": snap["inning"],
        "half": snap["half"],
        "away_score": away_s,
        "home_score": home_s,
        "lead": lead,
        "away_abbreviation": away_abbr,
        "home_abbreviation": home_abbr,
        "reason": reason,
        "snap_end_ts": snap["end_ts"],
    }


def load_crosswalk() -> dict[str, dict]:
    rows = json.loads(CROSSWALK.read_text())
    out = {}
    for r in rows:
        if r.get("mapping") != "MAPPED" or not r.get("event_ticker"):
            continue
        out[r["event_ticker"]] = r
    return out


def attach(rec: dict, walk: dict[str, dict], cache: dict[str, dict]) -> dict:
    row = dict(rec)
    mapped = walk.get(rec["event_ticker"])
    if not mapped or not mapped.get("has_pbp") or not mapped.get("pbp_path"):
        row.update(
            {
                "align": "UNALIGNED",
                "inning_bucket": "UNALIGNED",
                "lead_bucket": "NA",
                "lead": None,
                "phase": "UNALIGNED",
                "align_reason": "NO_MAPPED_PBP",
            }
        )
        return row
    path = Path(mapped["pbp_path"])
    if not path.exists():
        row.update(
            {
                "align": "UNALIGNED",
                "inning_bucket": "UNALIGNED",
                "lead_bucket": "NA",
                "lead": None,
                "phase": "UNALIGNED",
                "align_reason": "PBP_PATH_MISSING",
            }
        )
        return row
    pk = mapped["game_pk"]
    if pk not in cache:
        cache[pk] = load_feed(path)
    feed = cache[pk]
    teams = (feed.get("gameData") or {}).get("teams") or {}
    away = mapped.get("away_abbreviation") or (teams.get("away") or {}).get("abbreviation") or ""
    home = mapped.get("home_abbreviation") or (teams.get("home") or {}).get("abbreviation") or ""
    side = yes_side(yes_code(rec.get("ticker")), away, home)
    if side is None:
        row.update(
            {
                "align": "UNALIGNED",
                "inning_bucket": "UNALIGNED",
                "lead_bucket": "NA",
                "lead": None,
                "phase": "UNALIGNED",
                "align_reason": "YES_TEAM_NOT_HOME_OR_AWAY",
                "game_pk": pk,
            }
        )
        return row
    snap = snap_first80(feed, int(rec["first_80_timestamp"]), side)
    ib = inning_bucket(snap["phase"], snap.get("inning") if isinstance(snap.get("inning"), int) else None)
    if snap["phase"] == "IN_GAME" and not isinstance(snap.get("inning"), int):
        ib = "UNALIGNED"
    row.update(
        {
            "align": "ALIGNED" if ib != "UNALIGNED" else "UNALIGNED",
            "align_reason": snap.get("reason"),
            "game_pk": pk,
            "yes_side": side,
            "phase": snap["phase"],
            "inning": snap.get("inning"),
            "half": snap.get("half"),
            "away_score": snap.get("away_score"),
            "home_score": snap.get("home_score"),
            "lead": snap.get("lead"),
            "inning_bucket": ib,
            "lead_bucket": lead_bucket(snap.get("lead")),
            "away_abbreviation": away,
            "home_abbreviation": home,
        }
    )
    return row


def cell_key(inning_b: str, lead_b: str) -> tuple[str, str]:
    return inning_b, lead_b


def summarize_subset(rows: list[dict], mode: str, stop: str) -> dict:
    accepted, _ = A.apply_scenario(rows, mode, stop)
    return A.summarize_trades(accepted, f"{mode}:{stop}", maker_fee_on=False)


def tensor_for(rows: list[dict], mode: str, stop: str) -> dict:
    cells = {}
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    innings: dict[str, list[dict]] = defaultdict(list)
    leads: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        grouped[cell_key(r["inning_bucket"], r["lead_bucket"])].append(r)
        innings[r["inning_bucket"]].append(r)
        leads[r["lead_bucket"]].append(r)

    def pack(subset: list[dict]) -> dict:
        s = summarize_subset(subset, mode, stop)
        return {
            "n": s["trades"],
            "pct_of_first80": None
            if not rows
            else round(100.0 * s["trades"] / EXPECTED_N, 4),
            "win_rate_pct": s["win_rate_pct"],
            "win_rate_ci95": s["win_rate_ci95"],
            "gross_ev_cents": s["gross_ev_cents"],
            "gross_ev_R": s["gross_ev_R"],
            "evn_cents": s["net_ev_cents"],
            "evn_R": s["net_ev_R"],
            "wins": s["wins"],
            "stops": s["stops"],
            "loss_no_stop": s["loss_no_stop"],
        }

    for (ib, lb), subset in grouped.items():
        cells[f"{ib}|{lb}"] = {"inning": ib, "lead": lb, **pack(subset)}
    return {
        "cells": cells,
        "inning_marginal": {k: pack(v) for k, v in innings.items()},
        "lead_marginal": {k: pack(v) for k, v in leads.items()},
        "overall": pack(rows),
    }


def md_table(headers: list[str], rows: list[list[str]]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" if i == 0 else "---:" for i, _ in enumerate(headers)) + "|"]
    # first col left, rest numeric-ish
    lines[1] = "|" + "|".join("---:" if i else "---" for i in range(len(headers))) + "|"
    for r in rows:
        lines.append("| " + " | ".join(r) + " |")
    return lines


def fmt_pct(x) -> str:
    return "—" if x is None else f"{x}%"


def fmt_num(x) -> str:
    return "—" if x is None else str(x)


def write_report(identity: dict, coverage: dict, tensors: dict, aligned: list[dict]) -> str:
    close = tensors["close_all"]
    wick = tensors["wick_all"]
    close_h = tensors["close_high"]
    wick_h = tensors["wick_high"]

    def row_for(block: dict, key: str) -> list[str]:
        c = block["inning_marginal"].get(key) or block["lead_marginal"].get(key)
        if not c:
            return [key, "0", "—", "—", "—"]
        return [
            key,
            f"{c['n']:,}",
            fmt_pct(c["win_rate_pct"]),
            fmt_num(c["evn_cents"]),
            fmt_num(c["gross_ev_R"]),
        ]

    lines = [
        "# MLB FIRST80 — inning × score-differential tensor",
        "",
        "Research only. Does not change live trading. Does not invent L2 or gamePk.",
        "",
        "```",
        "LIVE EXECUTION = FALSE",
        "CANDLE PATH ≠ ACTUAL FILL",
        "```",
        "",
        "Frozen FIRST80 from `research/mlb_first80_80_40_v1/candidates.json` (n=4,303).",
        "State at entry = last completed StatsAPI play with `endTime ≤ first_80_timestamp`.",
        "Lead = FIRST80 yes-team score − opponent (ticker suffix vs home/away).",
        "Observed alias only: AZ ↔ ARI. Trailing-`2` Kalshi events are not mapped to game 1.",
        "",
        "---",
        "",
        "## 0. Identity (frozen close-stop)",
        "",
        f"- FIRST80 settled: **{identity['n']:,}** (expected {EXPECTED_N:,})",
        f"- Close-40 survivors (WIN ∧ ¬T40): **{identity['survivors']:,}**",
        f"- Close-40 stops: **{identity['close_stops']:,}**",
        f"- Close-stop win rate: **{identity['close_win_rate_pct']}%**",
        "",
        "## 1. PBP coverage",
        "",
        f"- Mapped + snapped (usable tensor): **{coverage['aligned']:,}** "
        f"({coverage['aligned_pct']}% of FIRST80)",
        f"- Unaligned (no unique gamePk, missing PBP, or yes-team side unknown): "
        f"**{coverage['unaligned']:,}**",
        f"- Pregame FIRST80: **{coverage['pregame']:,}**",
        f"- Postgame FIRST80: **{coverage['postgame']:,}**",
        f"- Crosswalk method: foundation rejoin + unique observed abbr concat for new Finals",
        "",
        "## 2. Overall (aligned only vs all FIRST80)",
        "",
        "| Universe | Model | n | Win rate | EVN ¢ | Gross EV R |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for key, label in (
        ("close_all", "all fills + close-stop"),
        ("wick_all", "all fills + wick-stop"),
        ("close_high", "HIGH + close-stop"),
        ("wick_high", "HIGH + wick-stop"),
    ):
        o = tensors[key]["overall_all"]
        a = tensors[key]["overall_aligned"]
        lines.append(
            f"| all FIRST80 | {label} | {o['n']:,} | {fmt_pct(o['win_rate_pct'])} | "
            f"{fmt_num(o['evn_cents'])} | {fmt_num(o['gross_ev_R'])} |"
        )
        lines.append(
            f"| aligned PBP | {label} | {a['n']:,} | {fmt_pct(a['win_rate_pct'])} | "
            f"{fmt_num(a['evn_cents'])} | {fmt_num(a['gross_ev_R'])} |"
        )

    lines += [
        "",
        "Wick-stop remains the MLB-specific failure: all-fills and HIGH wick-stop stay "
        "negative on the full frozen universe, unlike the basketball first80strat notebooks.",
        "",
        "## 3. Inning marginal (aligned + pregame/postgame/unaligned)",
        "",
        "Close-stop EVN vs wick-stop EVN. n is the same rows; only the stop model changes.",
        "",
        "| Inning | n | Close win | Close EVN ¢ | Wick win | Wick EVN ¢ |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for ib in INNING_ORDER:
        c = close["inning_marginal"].get(ib)
        w = wick["inning_marginal"].get(ib)
        if not c:
            continue
        lines.append(
            f"| {ib} | {c['n']:,} | {fmt_pct(c['win_rate_pct'])} | {fmt_num(c['evn_cents'])} | "
            f"{fmt_pct((w or {}).get('win_rate_pct'))} | {fmt_num((w or {}).get('evn_cents'))} |"
        )

    lines += [
        "",
        "## 4. Lead marginal (FIRST80-team run differential)",
        "",
        "| Lead | n | Close win | Close EVN ¢ | Wick win | Wick EVN ¢ |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for lb in LEAD_ORDER:
        c = close["lead_marginal"].get(lb)
        w = wick["lead_marginal"].get(lb)
        if not c:
            continue
        lines.append(
            f"| {lb} | {c['n']:,} | {fmt_pct(c['win_rate_pct'])} | {fmt_num(c['evn_cents'])} | "
            f"{fmt_pct((w or {}).get('win_rate_pct'))} | {fmt_num((w or {}).get('evn_cents'))} |"
        )

    lines += [
        "",
        "## 5. Tensor — close-stop EVN ¢ (n in parentheses)",
        "",
        "Cells with n < 20 are noisy. Do not retune live 80/81/83/89 from a sparse cell.",
        "",
    ]
    header = ["Inning \\ Lead"] + list(LEAD_ORDER[:-1])
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "|".join("---" for _ in header) + "|")
    for ib in INNING_ORDER:
        if ib == "UNALIGNED":
            continue
        row = [ib]
        empty = True
        for lb in LEAD_ORDER[:-1]:
            cell = close["cells"].get(f"{ib}|{lb}")
            if not cell:
                row.append("—")
            else:
                empty = False
                row.append(f"{cell['evn_cents']} ({cell['n']})")
        if not empty:
            lines.append("| " + " | ".join(row) + " |")

    lines += [
        "",
        "## 6. Tensor — wick-stop EVN ¢ (n in parentheses)",
        "",
    ]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "|".join("---" for _ in header) + "|")
    for ib in INNING_ORDER:
        if ib == "UNALIGNED":
            continue
        row = [ib]
        empty = True
        for lb in LEAD_ORDER[:-1]:
            cell = wick["cells"].get(f"{ib}|{lb}")
            if not cell:
                row.append("—")
            else:
                empty = False
                row.append(f"{cell['evn_cents']} ({cell['n']})")
        if not empty:
            lines.append("| " + " | ".join(row) + " |")

    # Notable cells: 2nd inning +2, and any wick-positive vs close
    example = close["cells"].get("2|+2")
    example_w = wick["cells"].get("2|+2")
    lines += ["", "## 7. Requested example — 2nd inning, +2 lead", ""]
    if example:
        lines.append(
            f"Close-stop: n={example['n']:,} ({example['pct_of_first80']}% of FIRST80) "
            f"win={fmt_pct(example['win_rate_pct'])} EVN={example['evn_cents']}¢"
        )
        if example_w:
            lines.append(
                f"Wick-stop: n={example_w['n']:,} win={fmt_pct(example_w['win_rate_pct'])} "
                f"EVN={example_w['evn_cents']}¢"
            )
    else:
        lines.append("No aligned FIRST80 snapped to 2nd inning with a 2-run lead.")

    pos_wick = [
        v
        for v in wick["cells"].values()
        if v["inning"] not in ("UNALIGNED",) and v["n"] >= 20 and (v["evn_cents"] or 0) > 0
    ]
    pos_wick.sort(key=lambda x: x["evn_cents"], reverse=True)
    lines += [
        "",
        "## 8. Wick-stop cells that stay +EV (n≥20)",
        "",
        "If this list is empty, wick-stop does not recover a tradeable MLB pocket "
        "at this resolution.",
        "",
    ]
    if not pos_wick:
        lines.append("None.")
    else:
        lines.append("| Inning | Lead | n | Wick win | Wick EVN ¢ | Close EVN ¢ |")
        lines.append("|---|---|---:|---:|---:|---:|")
        for v in pos_wick:
            c = close["cells"].get(f"{v['inning']}|{v['lead']}", {})
            lines.append(
                f"| {v['inning']} | {v['lead']} | {v['n']:,} | {fmt_pct(v['win_rate_pct'])} | "
                f"{v['evn_cents']} | {c.get('evn_cents', '—')} |"
            )

    lines += [
        "",
        "## 9. What this is not",
        "",
        "- Not a live order, fill, or realized P&L.",
        "- Not live MLB FIRST01 / 80/81/83/89.",
        "- Not W9. Candle path ≠ fill. Historical L2 is NOT AVAILABLE.",
        "- Fees: labeled KXMLBGAME quadratic M=0.5 (same as the frozen audit).",
        "",
        "**LIVE DEPLOYMENT: NOT AUTHORIZED**",
        "",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    if not CANDIDATES.exists():
        print("missing frozen candidates.json", flush=True)
        return 1
    if not CROSSWALK.exists():
        print("missing PBP crosswalk; run mlb_pbp_statsapi_ingest.py first", flush=True)
        return 1

    cands = json.loads(CANDIDATES.read_text())
    first = [
        c
        for c in cands
        if c.get("status") == "FIRST_80" and c.get("expiration_result_yes") is not None
    ]
    survivors = [c for c in first if not c["stop_close_triggered"] and c["expiration_result_yes"]]
    stops = [c for c in first if c["stop_close_triggered"]]
    if len(first) != EXPECTED_N or len(survivors) != EXPECTED_SURVIVORS or len(stops) != EXPECTED_CLOSE_STOPS:
        print(
            f"HALT frozen identity n={len(first)} survivors={len(survivors)} stops={len(stops)}",
            flush=True,
        )
        return 2

    walk = load_crosswalk()
    cache: dict[str, dict] = {}
    attached = [attach(c, walk, cache) for c in first]
    aligned = [r for r in attached if r["align"] == "ALIGNED"]
    coverage = {
        "first80": len(first),
        "aligned": len(aligned),
        "aligned_pct": round(100.0 * len(aligned) / len(first), 4),
        "unaligned": sum(1 for r in attached if r["align"] != "ALIGNED"),
        "pregame": sum(1 for r in attached if r.get("phase") == "PREGAME"),
        "postgame": sum(1 for r in attached if r.get("phase") == "POSTGAME"),
        "unaligned_reasons": dict(Counter(r.get("align_reason") for r in attached if r["align"] != "ALIGNED")),
        "mapped_events_in_crosswalk": len(walk),
        "pbp_feeds_loaded": len(cache),
    }

    tensors = {}
    for key, mode, stop, _label in MODELS:
        full = tensor_for(attached, mode, stop)
        al = tensor_for(aligned, mode, stop)
        tensors[key] = {
            **full,
            "overall_all": full["overall"],
            "overall_aligned": al["overall"],
        }

    identity = {
        "n": len(first),
        "survivors": len(survivors),
        "close_stops": len(stops),
        "close_win_rate_pct": round(100.0 * len(survivors) / len(first), 4),
        "ok": True,
    }

    OUT.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    snaps_path = OUT / "snaps.json"
    snaps_path.write_text(
        json.dumps(
            [
                {
                    "event_ticker": r["event_ticker"],
                    "ticker": r["ticker"],
                    "game_date": r.get("game_date"),
                    "first_80_timestamp": r.get("first_80_timestamp"),
                    "game_pk": r.get("game_pk"),
                    "align": r.get("align"),
                    "align_reason": r.get("align_reason"),
                    "phase": r.get("phase"),
                    "inning_bucket": r.get("inning_bucket"),
                    "lead_bucket": r.get("lead_bucket"),
                    "lead": r.get("lead"),
                    "inning": r.get("inning"),
                    "half": r.get("half"),
                    "away_score": r.get("away_score"),
                    "home_score": r.get("home_score"),
                    "yes_side": r.get("yes_side"),
                    "maker_fill_confidence": r.get("maker_fill_confidence"),
                    "stop_close_triggered": r.get("stop_close_triggered"),
                    "stop_low_triggered": r.get("stop_low_triggered"),
                    "expiration_result_yes": r.get("expiration_result_yes"),
                }
                for r in attached
            ]
        )
        + "\n"
    )
    summary = {
        "written_utc": datetime.now(timezone.utc).isoformat(),
        "identity": identity,
        "coverage": coverage,
        "models": {
            key: {
                "overall_all": tensors[key]["overall_all"],
                "overall_aligned": tensors[key]["overall_aligned"],
            }
            for key, *_ in MODELS
        },
        "tensors": {
            key: {
                "cells": tensors[key]["cells"],
                "inning_marginal": tensors[key]["inning_marginal"],
                "lead_marginal": tensors[key]["lead_marginal"],
            }
            for key, *_ in MODELS
        },
        "live_trading_changed": False,
        "candle_path_not_fill": True,
    }
    (OUT / "summary.json").write_text(json.dumps(summary) + "\n")
    report = write_report(identity, coverage, tensors, aligned)
    (OUT / "REPORT.md").write_text(report)
    (REPORTS / "INNING_SCORE_TENSOR.md").write_text(report)
    print(json.dumps({"identity": identity, "coverage": coverage}, indent=2), flush=True)
    print(f"wrote {OUT / 'REPORT.md'}", flush=True)
    return 0


def _self_test() -> None:
    assert yes_code("KXMLBGAME-25APR16ATHCWS-ATH") == "ATH"
    assert yes_side("ATH", "ATH", "CWS") == "away"
    assert yes_side("ARI", "AZ", "SD") == "away"
    assert yes_side("AZ", "SD", "AZ") == "home"
    assert lead_bucket(2) == "+2"
    assert lead_bucket(-5) == "-4+"
    assert lead_bucket(0) == "0"
    feed = {
        "gameData": {
            "datetime": {"dateTime": "2025-04-16T22:35:00Z"},
            "status": {"detailedState": "In Progress"},
            "teams": {"away": {"abbreviation": "ATH"}, "home": {"abbreviation": "CWS"}},
        },
        "liveData": {
            "plays": {
                "allPlays": [
                    {
                        "about": {
                            "inning": 2,
                            "halfInning": "top",
                            "isComplete": True,
                            "startTime": "2025-04-16T23:10:00Z",
                            "endTime": "2025-04-16T23:12:00Z",
                        },
                        "result": {"awayScore": 3, "homeScore": 1},
                    }
                ]
            }
        },
    }
    pre = snap_first80(feed, parse_iso("2025-04-16T22:00:00Z"), "away")
    assert pre["phase"] == "PREGAME" and pre["lead"] == 0
    mid = snap_first80(feed, parse_iso("2025-04-16T23:15:00Z"), "away")
    assert mid["phase"] == "IN_GAME" and mid["lead"] == 2 and mid["inning"] == 2
    assert inning_bucket(mid["phase"], mid["inning"]) == "2"


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--self-test":
        _self_test()
        print("ok")
        raise SystemExit(0)
    raise SystemExit(main())
