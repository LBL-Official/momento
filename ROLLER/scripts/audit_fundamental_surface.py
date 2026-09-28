"""Warehouse scan of the V4A fundamental surface. Not a CI unit test."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from roller.admin import load_dataset
from roller.config import RollerConfig
from roller.fundamental.corpus import build_state_rows
from roller.fundamental.eligibility import fundamental_eligible
from roller.fundamental.surface import classify_surface
from roller.fundamental.support import fundamental_support
from roller.timeutil import parse_utc, to_iso


def _breakdown(rows: list[dict], key_fn, cutoff, floors: dict) -> dict:
    cells: dict[str, list] = defaultdict(list)
    for row in rows:
        if not fundamental_eligible(row, current_game_id="", cutoff=cutoff):
            continue
        cells[str(key_fn(row))].append(row)
    supported = 0
    unique_games = []
    unique_obs = []
    for cell_rows in cells.values():
        supp = fundamental_support(cell_rows, floors=floors)
        unique_games.append(supp["n_unique_games"])
        unique_obs.append(supp["n_observations"])
        if supp["sufficient"]:
            supported += 1
    n = len(cells)
    med_g = sorted(unique_games)[len(unique_games) // 2] if unique_games else None
    return {
        "n_cells": n,
        "supported_cells": supported,
        "unsupported_cells": n - supported,
        "null_rate": None if n == 0 else (n - supported) / n,
        "median_n_unique_games": med_g,
        "min_n_unique_games": min(unique_games) if unique_games else None,
        "max_n_unique_games": max(unique_games) if unique_games else None,
        "median_n_observations": sorted(unique_obs)[len(unique_obs) // 2] if unique_obs else None,
    }


def run_audit(cfg: RollerConfig, sport: str = "NBA", season: str = "2025-2026") -> dict:
    floors = {
        "minimum_observations": int((cfg.fundamental_conditioning or {}).get("support", {}).get("minimum_observations") or 3),
        "minimum_unique_games": int((cfg.fundamental_conditioning or {}).get("support", {}).get("minimum_unique_games") or 2),
        "minimum_unique_dates": int((cfg.fundamental_conditioning or {}).get("support", {}).get("minimum_unique_dates") or 1),
        "minimum_unique_seasons": int((cfg.fundamental_conditioning or {}).get("support", {}).get("minimum_unique_seasons") or 1),
    }
    games = load_dataset(cfg, sport, season, "games")
    pbp = load_dataset(cfg, sport, season, "pbp")
    rows = build_state_rows(cfg, games=games, pbp=pbp, sport=sport, season=season)
    times = [parse_utc(r.get("result_available_at")) for r in rows]
    times = [t for t in times if t is not None]
    cutoff = max(times) if times else None
    if cutoff is None:
        return {"status": "NOT_SUPPORTED", "reason": "no corpus rows"}
    # Late cutoff so outcome clock is visible for completed games; still half-open.
    from datetime import timedelta

    late = cutoff + timedelta(seconds=1)
    period = _breakdown(rows, lambda r: r.get("period"), late, floors)
    period_clock = _breakdown(rows, lambda r: f"{r.get('period')}|{r.get('clock_bucket')}", late, floors)
    full = _breakdown(rows, lambda r: r.get("condition_id"), late, floors)
    by_period = _breakdown(rows, lambda r: f"period={r.get('period')}", late, floors)
    summary = {
        "total_observations_in_corpus": len(rows),
        "total_estimates_requested": full["n_cells"],
        "supported_estimates": full["supported_cells"],
        "unsupported_estimates": full["unsupported_cells"],
        "null_rate": full["null_rate"],
        "median_n_unique_games": full["median_n_unique_games"],
        "median_n_observations": full["median_n_observations"],
        "fragmentation": {
            "period": period,
            "period_clock": period_clock,
            "period_clock_score": full,
        },
        "support_by_period": by_period,
        "cutoff": to_iso(late),
        "floors": floors,
        "n_games_in_corpus": len({r.get("internal_game_id") for r in rows}),
    }
    summary["classification"] = classify_surface(summary)
    return summary


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    cfg = RollerConfig(root)
    summary = run_audit(cfg)
    out = root / "reports" / "integrity" / "fundamental_surface.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"classification": summary.get("classification"), "null_rate": summary.get("null_rate")}, indent=2))


if __name__ == "__main__":
    main()
