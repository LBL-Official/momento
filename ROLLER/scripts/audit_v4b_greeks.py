#!/usr/bin/env python3
"""Sample V4B measurement coverage. Not a trading report. Not a CI unit test."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from roller.admin import load_dataset, load_identity
from roller.config import RollerConfig
from roller.io_csv import write_json
from roller.v4b.candles import interval_matches, interval_seconds, visible_home_candles
from roller.v4b.definitions import OBSERVED_FAMILIES, expected_interval_seconds


def _md_table(rows: list[dict], keys: list[str]) -> str:
    header = "| " + " | ".join(keys) + " |"
    sep = "| " + " | ".join("---" for _ in keys) + " |"
    body = []
    for row in rows:
        body.append("| " + " | ".join(str(row.get(k, "")) for k in keys) + " |")
    return "\n".join([header, sep, *body])


def run_audit(cfg: RollerConfig, sport: str = "NBA", season: str = "2025-2026", max_games: int = 8) -> dict:
    expected = expected_interval_seconds(cfg)
    out: dict = {
        "sport": sport,
        "season": season,
        "expected_interval_seconds": expected,
        "families": list(OBSERVED_FAMILIES),
        "note": "Coverage of constructibility only. Δ/Γ/Θ/B/R ≠ EDGE. Not a trading recommendation.",
        "status": "NOT_SUPPORTED",
        "games_scanned": 0,
        "visible_pairs": 0,
        "interval_ok_pairs": 0,
        "interval_gap_pairs": 0,
        "status_counts": {},
    }
    try:
        games = load_dataset(cfg, sport, season, "games")
        candles = load_dataset(cfg, sport, season, "kalshi_candles")
        ident = load_identity(cfg)
    except (FileNotFoundError, KeyError) as exc:
        out["reason"] = str(exc)
        return out
    if games.empty or candles.empty:
        out["reason"] = "missing games or candles"
        return out

    pair_ok = 0
    pair_gap = 0
    pair_n = 0
    scanned = 0
    for rec in games.to_dict("records"):
        if scanned >= max_games:
            break
        gid = rec.get("internal_game_id")
        if not gid:
            continue
        gc = candles[candles["internal_game_id"] == gid] if "internal_game_id" in candles.columns else candles.iloc[0:0]
        if gc.empty:
            continue
        cutoff = rec.get("result_available_at") or rec.get("available_at")
        if not cutoff:
            continue
        vis = visible_home_candles(gc, cutoff)
        scanned += 1
        for i in range(1, len(vis)):
            pair_n += 1
            sec = interval_seconds(vis[i], vis[i - 1])
            if interval_matches(sec, expected):
                pair_ok += 1
            else:
                pair_gap += 1

    out.update(
        {
            "status": "OBSERVED",
            "games_scanned": scanned,
            "identity_rows": int(len(ident)) if ident is not None else None,
            "visible_pairs": pair_n,
            "interval_ok_pairs": pair_ok,
            "interval_gap_pairs": pair_gap,
            "interval_ok_rate": None if pair_n == 0 else pair_ok / pair_n,
            "status_counts": dict(Counter({"TIME_GAP": pair_gap, "INTERVAL_OK": pair_ok})),
        }
    )
    return out


def write_report(cfg: RollerConfig, report: dict) -> Path:
    dest = cfg.root / "reports" / "ROLLER_V4B_GREEK_COVERAGE.md"
    families = [{"family": n, "layer": "observed"} for n in report.get("families") or []]
    families.append({"family": "v4b_baseline", "layer": "baseline"})
    families.append({"family": "v4b_residual", "layer": "residual"})
    md = [
        "# ROLLER V4B Greek coverage",
        "",
        "Constructibility of query-time measurements. **Not a trading report.**",
        "",
        "```text",
        "Δ ≠ EDGE    Γ ≠ EDGE    Θ ≠ EDGE    BASIS ≠ EDGE    RESIDUAL ≠ EDGE",
        "PURE THETA ≠ NO-EVENT THETA",
        "```",
        "",
        f"- Sport/season: `{report.get('sport')}` / `{report.get('season')}`",
        f"- Status: `{report.get('status')}`",
        f"- Games scanned: `{report.get('games_scanned')}`",
        f"- Visible adjacent pairs: `{report.get('visible_pairs')}`",
        f"- Configured 60s pairs: `{report.get('interval_ok_pairs')}`",
        f"- Non-60s pairs (`TIME_GAP`): `{report.get('interval_gap_pairs')}`",
        f"- Interval-ok rate: `{report.get('interval_ok_rate')}`",
        "",
        "Warehouse pair scan does not estimate edge, fill probability, or PnL.",
        "Baselines remain `E[M | core_v1]` with `measurement_available_at_i < t` and current-game exclusion.",
        "",
        "## Families",
        "",
        _md_table(families, ["family", "layer"]),
        "",
        "## Machine summary",
        "",
        "```json",
        json.dumps({k: v for k, v in report.items() if k != "families"}, indent=2, default=str),
        "```",
        "",
    ]
    dest.write_text("\n".join(md), encoding="utf-8")
    write_json(cfg.root / "reports" / "integrity" / "v4b_coverage.json", report)
    return dest


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    p.add_argument("--sport", default="NBA")
    p.add_argument("--season", default="2025-2026")
    p.add_argument("--max-games", type=int, default=8)
    args = p.parse_args()
    cfg = RollerConfig(Path(args.root))
    report = run_audit(cfg, sport=args.sport, season=args.season, max_games=args.max_games)
    path = write_report(cfg, report)
    print(json.dumps({"status": report["status"], "report": str(path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
