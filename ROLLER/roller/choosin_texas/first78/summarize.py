"""Turn a shared FIRST78 cohort into the three stop views."""

from __future__ import annotations

from collections import Counter
from fractions import Fraction
from typing import Any

from roller.choosin_texas.first78.desk import clock_samples
from roller.choosin_texas.first78.outcomes import cell_name, gross_threshold_cents
from roller.choosin_texas.first78.portfolio_replay import replay_variant

SLICES = ("Q2", "Q3", "H1_2", "H2_1")


def _money(numer: int, denom: int) -> str | None:
    if denom <= 0:
        return None
    return format(Fraction(int(numer), int(denom)), "f")


def score_row(row: dict[str, Any], stop_cents: int) -> dict[str, Any]:
    stop = (row.get("stops") or {}).get(str(stop_cents)) or (row.get("stops") or {}).get(int(stop_cents)) or {}
    stopped = stop.get("stop_ts") is not None
    terminal = row.get("terminal")
    cell = cell_name(terminal=terminal, stopped=stopped)
    gross = gross_threshold_cents(terminal=terminal, stopped=stopped, stop_cents=stop_cents)
    exit_ts = stop.get("stop_ts") if stopped else row.get("settlement_ts")
    if cell == "UNRESOLVED":
        exit_ts = None
        gross = None
    return {
        "game_id": row["game_id"],
        "contract_id": row["contract_id"],
        "sport": row.get("sport"),
        "slice": row.get("slice"),
        "signal_ts": row.get("signal_ts"),
        "observed_entry_close_cents": row.get("observed_entry_close_cents"),
        "terminal": terminal,
        "stopped": stopped,
        "cell": cell,
        "gross_cents": gross,
        "exit_ts": exit_ts,
        "stop_ts": stop.get("stop_ts"),
        "stop_close_cents": stop.get("stop_close_cents"),
        "intrabar_ambiguity": bool(stop.get("intrabar_ambiguity")),
        "clock_reason": row.get("clock_reason"),
        "entry_period": row.get("entry_period"),
        "entry_remaining_s": row.get("entry_remaining_s"),
        "stop_period": stop.get("period"),
        "stop_remaining_s": stop.get("period_remaining_s"),
    }


def _variant_block(rows: list[dict], spec: dict) -> dict[str, Any]:
    stop = int(spec["stop_cents"])
    scored = [score_row(row, stop) for row in rows]
    cells = Counter(row["cell"] for row in scored)
    resolved = [row for row in scored if row["gross_cents"] is not None]
    gross_sum = sum(int(row["gross_cents"]) for row in resolved)
    stops = sum(1 for row in scored if row["stopped"])
    slices = []
    for name in SLICES:
        group = [row for row in scored if row.get("slice") == name]
        group_resolved = [row for row in group if row["gross_cents"] is not None]
        slices.append(
            {
                "slice": name,
                "n": len(group),
                "resolved": len(group_resolved),
                "unresolved": sum(1 for row in group if row["cell"] == "UNRESOLVED"),
                "stops": sum(1 for row in group if row["stopped"]),
                "gross_sum_cents": sum(int(row["gross_cents"]) for row in group_resolved),
                "gross_ev_per_contract": _money(
                    sum(int(row["gross_cents"]) for row in group_resolved),
                    len(group_resolved),
                ),
                "cells": dict(Counter(row["cell"] for row in group)),
            }
        )
    funded_rows = []
    for row in scored:
        funded_rows.append(row)
    return {
        "strategy_id": spec["strategy_id"],
        "role": spec["role"],
        "entry_cents": 78,
        "stop_cents": stop,
        "n_entries": len(scored),
        "resolved": len(resolved),
        "unresolved": cells.get("UNRESOLVED", 0),
        "cells": {key: cells.get(key, 0) for key in ("YES_NO_STOP", "YES_STOP", "NO_NO_STOP", "NO_STOP", "UNRESOLVED")},
        "stop_count": stops,
        "stop_rate": _money(stops, len(scored)),
        "gross_sum_cents": gross_sum,
        "gross_ev_per_contract": _money(gross_sum, len(resolved)),
        "gross_ev_denominator": "resolved contracts with a terminal yes or no",
        "gross_is_net": False,
        "gross_is_executable": False,
        "slices": slices,
        "funded": replay_variant(scored, stop),
        "scored": scored,
    }


def assemble(candidates: list[dict], *, strategy: dict, coverage: dict, exclusions: dict, run_id: str, strategy_sha256: str) -> dict[str, Any]:
    variants = [_variant_block(candidates, spec) for spec in strategy["variants"]]
    by_game: dict[str, dict] = {}
    for block in variants:
        for row in block["scored"]:
            slot = by_game.setdefault(
                row["game_id"],
                {"game_id": row["game_id"], "contract_id": row["contract_id"], "slice": row.get("slice"), "stops": {}},
            )
            slot["stops"][str(block["stop_cents"])] = {
                "cell": row["cell"],
                "gross_cents": row["gross_cents"],
                "stopped": row["stopped"],
            }
    paired = []
    for game_id, slot in sorted(by_game.items()):
        base = slot["stops"].get("67", {})
        paired.append(
            {
                **slot,
                "gross_65_minus_67": _diff(slot["stops"].get("65"), base),
                "gross_60_minus_67": _diff(slot["stops"].get("60"), base),
            }
        )
    official = next(block for block in variants if int(block["stop_cents"]) == 67)
    samples = clock_samples(official["scored"])
    public_variants = []
    for block in variants:
        copied = dict(block)
        copied.pop("scored", None)
        public_variants.append(copied)
    explorer = []
    for row in candidates[:200]:
        scored67 = score_row(row, 67)
        explorer.append(
            {
                "game_id": row["game_id"],
                "contract_id": row["contract_id"],
                "sport": row.get("sport"),
                "slice": row.get("slice"),
                "signal_ts": row.get("signal_ts"),
                "observed_entry_close_cents": row.get("observed_entry_close_cents"),
                "scenario_entry_cents": 78,
                "terminal": row.get("terminal"),
                "cell_67": scored67["cell"],
                "stop_ts_67": scored67["stop_ts"],
                "stop_close_cents_67": scored67["stop_close_cents"],
                "intrabar_ambiguity_67": scored67["intrabar_ambiguity"],
                "clock_reason": row.get("clock_reason"),
            }
        )
    return {
        "schema_version": "first78_active_artifact_v1",
        "status": "OBSERVED",
        "run_id": run_id,
        "strategy_version": strategy["strategy_version"],
        "strategy_sha256": strategy_sha256,
        "official_strategy_id": "FIRST78_67",
        "population_id": "PRIMARY_EX_ANTE_FIRST78",
        "live_execution": False,
        "submits": False,
        "candle_path_is_not_a_fill": True,
        "fee_applicability": "FEE_APPLICABILITY_UNVERIFIED",
        "window": strategy["development_window"],
        "separate_windows_not_pooled": strategy["separate_windows_not_pooled"],
        "coverage": coverage,
        "exclusions": exclusions,
        "n_entries": len(candidates),
        "variants": public_variants,
        "paired": paired,
        "clock_samples": samples,
        "candidates": explorer,
        "candidate_rows_truncated": len(candidates) > 200,
        "clock_availability": "MODELED_AVAILABILITY",
        "migration": _migration(),
        "variables": {
            "rule": "FIRST78",
            "entry_cents": 78,
            "official_stop_cents": 67,
            "comparison_stops_cents": [65, 60],
            "gross_win_cents": 22,
            "entry_cap_cents": None,
            "slices": ["nba_q2", "nba_q3", "ncaab_h1_2", "ncaab_h2_1"],
            "recompute": "ARTIFACT",
        },
    }


def _diff(other: dict | None, base: dict) -> int | None:
    if not other or not base:
        return None
    if other.get("gross_cents") is None or base.get("gross_cents") is None:
        return None
    return int(other["gross_cents"]) - int(base["gross_cents"])


def _migration() -> list[dict[str, str]]:
    historical = [
        ("#/first80", "FIRST80 path ladder", "Historical. Locked 80/40 reconstruction."),
        ("#/texas-60", "80/60", "Historical FIRST80 stop. Not 78/60."),
        ("#/paired", "Paired 80/40 vs 80/65", "Historical. Not a FIRST78 comparison."),
        ("#/texas-75", "FIRST75", "Historical."),
        ("#/texas-77", "FIRST77", "Historical."),
        ("#/asked-six", "Asked-six", "Historical. Distinct from this population."),
        ("#/dallas", "Dallas", "Historical FIRST80 snapshots."),
        ("#/lubbock", "Lubbock", "Historical season progression."),
        ("#/book", "80/40 baseline", "Historical registered research book."),
    ]
    rows = [{"route": route, "name": name, "applicability": note, "class": "HISTORICAL"} for route, name, note in historical]
    rows.append({"route": "#/austin", "name": "Austin", "applicability": "Unvalidated for FIRST78. N=604 model is unchanged.", "class": "UNVALIDATED"})
    rows.append({"route": "#/fort-worth", "name": "Fort Worth", "applicability": "Unvalidated for FIRST78.", "class": "UNVALIDATED"})
    rows.append({"route": "#/sugarland", "name": "Sugarland", "applicability": "Pregame quotes. Not FIRST78 alpha.", "class": "STRATEGY_INDEPENDENT"})
    rows.append({"route": "#/katy", "name": "Katy", "applicability": "Experiment index. Not a FIRST78 recompute.", "class": "STRATEGY_INDEPENDENT"})
    return rows
