"""Phase 4 empirical research executor — orchestrator only.

Selects authoritative frozen artifacts / loaders. Does not reimplement FIRST80,
path math, EV, fees, or portfolio logic.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from roller.dashboard_adapter.bindings import (
    BINDING_BARRIER_SURVIVAL_V1,
    BINDING_NCAAB_FIRST80_P5,
    BINDING_ROLLER_FIRST80,
    BINDING_WAREHOUSE_FROZEN_V1,
    ENTRY_HALF_ARTIFACT_FIELD,
    ENTRY_SLICE_ARTIFACT_FIELD,
    NCAAB_FIRST80_P5_ARTIFACT_LABEL,
    POPULATION_ROWS_SERIALIZE_CAP,
    warehouse_barrier_trades_path,
    warehouse_first80_candidates_path,
    warehouse_ncaab_first80_p5_trades_path,
)
from roller.dashboard_adapter.measurement_registry import resolve_measurement_request
from roller.dashboard_adapter.research_object_ops import validate_for_api
from roller.dashboard_adapter.serialize import to_jsonable

_BASE_CAVEATS = (
    "MEASUREMENT ≠ EDGE",
    "CANDLE PATH ≠ FILL",
    "SURVIVE ≠ TERMINAL_YES",
)

# Optional hook for tests: spy on candidates path resolution.
_candidates_path_hook: Callable[[], Path] | None = None

# Optional hook for tests: spy on NCAAB P5 parquet path resolution.
_ncaab_p5_path_hook: Callable[[], Path] | None = None


def _candidates_path() -> Path:
    if _candidates_path_hook is not None:
        return _candidates_path_hook()
    return warehouse_first80_candidates_path()


def _ncaab_p5_path() -> Path:
    if _ncaab_p5_path_hook is not None:
        return _ncaab_p5_path_hook()
    return warehouse_ncaab_first80_p5_trades_path()


def _empty_result(
    *,
    research_object_id: str | None,
    execution_status: str,
    validation: dict[str, Any],
    caveats: list[str] | None = None,
    bindings: dict[str, Any] | None = None,
    message: str | None = None,
    measurements: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    notes = list(_BASE_CAVEATS)
    if caveats:
        notes.extend(caveats)
    if message:
        notes.append(message)
    return to_jsonable(
        {
            "research_object_id": research_object_id,
            "execution_status": execution_status,
            "validation": {
                "valid": validation.get("valid"),
                "runnable": validation.get("runnable"),
                "status": validation.get("status"),
                "errors": validation.get("errors") or [],
                "unresolved": validation.get("unresolved") or [],
            },
            "summary": {
                "population_n": None,
                "population_description": None,
            },
            "bindings": bindings or {},
            "population": {
                "status": "ABSENT",
                "count": 0,
                "rows": [],
                "rows_truncated": False,
            },
            "path_conditions": {"status": "ABSENT", "results": []},
            "terminal_conditions": {"status": "ABSENT", "results": []},
            "measurements": measurements or [],
            "provenance": {
                "definition_versions": {},
                "dataset_versions": {},
                "source_artifacts": [],
            },
            "empirical_partition": _unavailable_partition(0),
            "caveats": notes,
        }
    )


def _proportion(true_n: int, available_n: int) -> float | None:
    if available_n <= 0:
        return None
    return true_n / available_n


def _boolish(value: Any) -> bool | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        low = value.strip().lower()
        if low in ("true", "1", "yes"):
            return True
        if low in ("false", "0", "no"):
            return False
    return None


def _requested_slices(spec: dict[str, Any]) -> list[str]:
    pop = spec.get("population_binding") if isinstance(spec.get("population_binding"), dict) else {}
    slices = list(pop.get("default_structural_slices") or [])
    filters = spec.get("state_filters") if isinstance(spec.get("state_filters"), dict) else {}
    for arg in filters.get("args") or []:
        if not isinstance(arg, dict):
            continue
        if arg.get("op") != "ATOM":
            continue
        field = arg.get("field")
        if field in ("entry_slice", ENTRY_SLICE_ARTIFACT_FIELD, "period"):
            if arg.get("operator") == "eq" and arg.get("value") is not None:
                val = arg["value"]
                if isinstance(val, list):
                    slices.extend(str(v) for v in val)
                else:
                    slices.append(str(val))
    out: list[str] = []
    for s in slices:
        if s not in out:
            out.append(s)
    return out


def _unavailable_partition(n: int, reason: str | None = None) -> dict[str, Any]:
    return {
        "status": "UNAVAILABLE",
        "reason": reason
        or (
            "JOINT PARTITION NOT CURRENTLY MEASURED. "
            "The current result artifact does not provide an authoritative "
            "exhaustive joint partition. Marginal measurements may still be available."
        ),
        "axes": [],
        "cells": [],
        "n_population": n,
        "n_joint_available": 0,
        "n_missing": n,
    }


def _empirical_partition(
    rows: list[dict[str, Any]],
    *,
    path_field: str = "T40",
    terminal_field: str = "W",
) -> dict[str, Any]:
    """Additive serialization of a path × terminal joint on the full population.

    Not a new measurement. Uses the same _boolish rules as marginal aggregates.
    null ≠ false. Does not infer joints from marginal rates.
    """
    n = len(rows)
    if n == 0:
        return _unavailable_partition(0)
    has_path = any(path_field in row for row in rows)
    has_term = any(terminal_field in row for row in rows)
    if not has_path or not has_term:
        return _unavailable_partition(
            n,
            "JOINT PARTITION NOT CURRENTLY MEASURED. "
            f"Authoritative fields {path_field!r} and {terminal_field!r} "
            "are not both present on the population.",
        )

    tt = tf = ft = ff = missing = 0
    for row in rows:
        path_v = _boolish(row.get(path_field))
        term_v = _boolish(row.get(terminal_field))
        if path_v is None or term_v is None:
            missing += 1
            continue
        if path_v and term_v:
            tt += 1
        elif path_v and not term_v:
            tf += 1
        elif not path_v and term_v:
            ft += 1
        else:
            ff += 1

    cells = [
        {"key": "T_AND_W", "path_true": True, "terminal_true": True, "n": tt},
        {"key": "T_AND_NOT_W", "path_true": True, "terminal_true": False, "n": tf},
        {"key": "NOT_T_AND_W", "path_true": False, "terminal_true": True, "n": ft},
        {"key": "NOT_T_AND_NOT_W", "path_true": False, "terminal_true": False, "n": ff},
    ]
    joint_n = tt + tf + ft + ff
    if joint_n + missing != n:
        return _unavailable_partition(
            n,
            "JOINT PARTITION NOT CURRENTLY MEASURED. "
            "Cell sum plus missing does not equal population N.",
        )

    return {
        "status": "COMPLETE",
        "reason": None,
        "axes": [
            {
                "id": "path",
                "field": path_field,
                "true_label": "PATH TRUE",
                "false_label": "PATH FALSE",
            },
            {
                "id": "terminal",
                "field": terminal_field,
                "true_label": "TERMINAL YES",
                "false_label": "TERMINAL NO",
            },
        ],
        "cells": cells,
        "n_population": n,
        "n_joint_available": joint_n,
        "n_missing": missing,
    }


def _serialize_population_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], bool]:
    truncated = len(rows) > POPULATION_ROWS_SERIALIZE_CAP
    preview = rows[:POPULATION_ROWS_SERIALIZE_CAP]
    return to_jsonable(preview), truncated


def _full_population_trades(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Uncapped export for SuperASI. Does not change the Results 200-row preview."""
    return to_jsonable(list(rows))


def _path_aggregate(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    available = 0
    true_n = 0
    false_n = 0
    missing_n = 0
    for row in rows:
        b = _boolish(row.get(field))
        if b is None:
            missing_n += 1
            continue
        available += 1
        if b:
            true_n += 1
        else:
            false_n += 1
    return {
        "field": field,
        "count_true": true_n,
        "count_false": false_n,
        "count_available": available,
        "count_missing": missing_n,
        "proportion_true": _proportion(true_n, available),
    }


def _population_context_first80(population: list[dict[str, Any]]) -> dict[str, Any]:
    available: set[str] = set()
    for row in population:
        for k, v in row.items():
            if v is not None:
                available.add(k)
    return {
        "definition_family": "FIRST80",
        "available_fields": sorted(available),
    }


def _population_context_ncaab_first80_p5(population: list[dict[str, Any]]) -> dict[str, Any]:
    available: set[str] = set()
    for row in population:
        for k, v in row.items():
            if v is not None:
                available.add(k)
    return {
        "definition_family": "NCAAB_FIRST80_P5",
        "available_fields": sorted(available),
    }


def _route_measurements(
    spec: dict[str, Any],
    *,
    population: list[dict[str, Any]],
    population_context: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Resolve each measurement_request through the registry, then execute explicit handlers."""
    defs = spec.get("definition_versions") if isinstance(spec.get("definition_versions"), dict) else {}
    out: list[dict[str, Any]] = []
    for req in spec.get("measurement_requests") or []:
        if not isinstance(req, dict):
            continue
        route = resolve_measurement_request(
            req,
            definition_versions=defs,
            population_context=population_context,
        )
        name = route.get("name")
        if route.get("route_status") != "IMPLEMENTED":
            out.append(
                {
                    "name": name,
                    "status": route.get("route_status"),
                    "value": None,
                    "definition_version": route.get("definition_version"),
                    "source": None,
                    "caveat": route.get("caveat") or route.get("reason"),
                }
            )
            continue

        handler = route.get("handler_key")
        family = (population_context or {}).get("definition_family")
        if family == "NCAAB_FIRST80_P5":
            artifact_label = NCAAB_FIRST80_P5_ARTIFACT_LABEL
        else:
            artifact_label = "first80_quarter_barrier_survival/trades.parquet"
        if handler == "t40_rate":
            agg = _path_aggregate(population, "T40")
            out.append(
                {
                    "name": "t40_rate",
                    "status": "COMPLETE",
                    "value": agg["proportion_true"],
                    "definition_version": route.get("definition_version")
                    or BINDING_BARRIER_SURVIVAL_V1,
                    "detail": agg,
                    "source": {
                        "artifact": artifact_label,
                        "field": "T40",
                    },
                    "caveat": route.get("caveat")
                    or "Proportion of available rows with T40 == True. MEASUREMENT ≠ EDGE.",
                }
            )
        elif handler == "kalshi_yes_rate":
            agg_w = _path_aggregate(population, "W")
            if agg_w["count_available"] > 0:
                out.append(
                    {
                        "name": "kalshi_yes_rate",
                        "status": "COMPLETE",
                        "value": agg_w["proportion_true"],
                        "definition_version": route.get("definition_version")
                        or BINDING_WAREHOUSE_FROZEN_V1,
                        "detail": {"field": "W", **agg_w},
                        "source": {
                            "artifact": artifact_label,
                            "field": "W",
                        },
                        "caveat": route.get("caveat")
                        or (
                            "Proportion of available rows with W == True (Kalshi settlement). "
                            "Not box-score win."
                        ),
                    }
                )
            else:
                agg_y = _path_aggregate(population, "expiration_result_yes")
                out.append(
                    {
                        "name": "kalshi_yes_rate",
                        "status": "COMPLETE" if agg_y["count_available"] else "ABSENT",
                        "value": agg_y["proportion_true"],
                        "definition_version": route.get("definition_version")
                        or BINDING_WAREHOUSE_FROZEN_V1,
                        "detail": {"field": "expiration_result_yes", **agg_y},
                        "source": {
                            "artifact": "first80_execution_audit/candidates.json",
                            "field": "expiration_result_yes",
                        },
                        "caveat": "Used expiration_result_yes from candidates. Not box-score win.",
                    }
                )
        else:
            out.append(
                {
                    "name": name,
                    "status": "ABSENT",
                    "value": None,
                    "definition_version": route.get("definition_version"),
                    "source": None,
                    "caveat": f"Registry marked IMPLEMENTED but no executor handler for {handler!r}",
                }
            )
    return out


def _load_candidates() -> list[dict[str, Any]]:
    path = _candidates_path()
    return json.loads(path.read_text(encoding="utf-8"))


def _load_barrier_trades() -> pd.DataFrame:
    return pd.read_parquet(warehouse_barrier_trades_path())


def _execute_warehouse_first80(spec: dict[str, Any], validation: dict[str, Any]) -> dict[str, Any]:
    rid = validation.get("research_object_id")
    caveats = list(_BASE_CAVEATS)
    source_artifacts: list[str] = []
    requested = BINDING_WAREHOUSE_FROZEN_V1

    cand_path = _candidates_path()
    if not cand_path.is_file():
        return _empty_result(
            research_object_id=rid,
            execution_status="ABSENT",
            validation=validation,
            bindings={
                "FIRST80": {
                    "requested_definition_version": requested,
                    "actual_definition_version": None,
                    "status": "ABSENT",
                    "reason": f"candidates artifact missing: {cand_path}",
                }
            },
            message="warehouse_frozen_v1 candidates.json not available",
        )

    barrier_path = warehouse_barrier_trades_path()
    if not barrier_path.is_file():
        return _empty_result(
            research_object_id=rid,
            execution_status="ABSENT",
            validation=validation,
            bindings={
                "FIRST80": {
                    "requested_definition_version": requested,
                    "actual_definition_version": None,
                    "status": "ABSENT",
                    "reason": f"barrier trades artifact missing: {barrier_path}",
                }
            },
            message="barrier_survival_v1 trades.parquet not available",
        )

    candidates = _load_candidates()
    source_artifacts.append(str(cand_path))
    first80 = [r for r in candidates if r.get("status") == "FIRST_80"]
    trades = _load_barrier_trades()
    source_artifacts.append(str(barrier_path))

    if "ticker" not in trades.columns:
        return _empty_result(
            research_object_id=rid,
            execution_status="ABSENT",
            validation=validation,
            bindings={
                "FIRST80": {
                    "requested_definition_version": requested,
                    "actual_definition_version": None,
                    "status": "ABSENT",
                    "reason": "barrier trades missing ticker column",
                }
            },
            message="barrier trades.parquet schema unexpected",
        )

    trade_by_ticker = trades.drop_duplicates(subset=["ticker"], keep="first").set_index("ticker")

    joined: list[dict[str, Any]] = []
    unmatched = 0
    for row in first80:
        ticker = row.get("ticker")
        base: dict[str, Any] = {
            "ticker": ticker,
            "event_ticker": row.get("event_ticker") or row.get("event_id"),
            "game_date": row.get("game_date"),
            "team": row.get("team") or row.get("home_team"),
            "status": row.get("status"),
            "first_80_timestamp": row.get("first_80_timestamp"),
            "entry_price_e4": row.get("entry_price_e4"),
            "expiration_result_yes": row.get("expiration_result_yes"),
            "dataset_split": row.get("dataset_split"),
        }
        if ticker is None or ticker not in trade_by_ticker.index:
            unmatched += 1
            base["barrier_join"] = "UNMATCHED"
            base["entry_quarter_bucket"] = None
            base["T40"] = None
            base["W"] = None
            joined.append(base)
            continue
        trow = trade_by_ticker.loc[ticker]
        base["barrier_join"] = "MATCHED"
        base["entry_quarter_bucket"] = to_jsonable(trow.get(ENTRY_SLICE_ARTIFACT_FIELD))
        base["T40"] = to_jsonable(trow.get("T40"))
        base["W"] = to_jsonable(trow.get("W"))
        base["alignment_confidence"] = to_jsonable(trow.get("alignment_confidence"))
        joined.append(base)

    if unmatched:
        caveats.append(
            f"{unmatched} FIRST_80 candidate row(s) unmatched to barrier trades on ticker "
            "(T40/W left null — not invented as False)"
        )

    caveats.append(
        f"Phase 4 adapter binding: schema entry_slice ↔ artifact {ENTRY_SLICE_ARTIFACT_FIELD}"
    )

    slices = _requested_slices(spec)
    population = joined
    filter_notes: list[str] = []
    if slices:
        supported = {"Q1", "Q2", "Q3", "Q4", "OT", "UNALIGNED"}
        unsupported = [s for s in slices if s not in supported]
        usable = [s for s in slices if s in supported]
        if unsupported:
            filter_notes.append(
                f"Unsupported structural slices for Phase 4 warehouse path: {unsupported}"
            )
        if usable:
            population = [r for r in population if r.get("entry_quarter_bucket") in usable]
            filter_notes.append(
                f"Filtered entry_quarter_bucket in {usable} (schema entry_slice binding)"
            )
        elif unsupported and not usable:
            return _empty_result(
                research_object_id=rid,
                execution_status="PARTIAL",
                validation=validation,
                bindings={
                    "FIRST80": {
                        "requested_definition_version": requested,
                        "actual_definition_version": requested,
                        "status": "PARTIAL",
                        "reason": "structural slices unsupported",
                    }
                },
                caveats=filter_notes,
                message="Requested structural slices are not executable in Phase 4 warehouse path",
            )

    path_results: list[dict[str, Any]] = []
    path_status = "ABSENT"
    for cond in spec.get("path_conditions") or []:
        if not isinstance(cond, dict):
            continue
        kind = cond.get("kind")
        binding = cond.get("binding")
        price_e4 = cond.get("price_e4")
        if (
            kind == "EVER_CLOSE_LE"
            and price_e4 == 4000
            and binding in (BINDING_BARRIER_SURVIVAL_V1, None, "barrier_survival_v1")
        ):
            agg = _path_aggregate(population, "T40")
            path_results.append(
                {
                    "kind": kind,
                    "price_e4": price_e4,
                    "binding": BINDING_BARRIER_SURVIVAL_V1,
                    "label": "T40 path proportion (proportion of population with T40 == True)",
                    **agg,
                }
            )
            path_status = "COMPLETE"
        else:
            path_results.append(
                {
                    "kind": kind,
                    "binding": binding,
                    "status": "ABSENT",
                    "reason": "Phase 4 has no authoritative binding for this path condition",
                }
            )
            if path_status != "COMPLETE":
                path_status = "PARTIAL"

    terminal_results: list[dict[str, Any]] = []
    terminal_status = "ABSENT"
    for cond in spec.get("terminal_conditions") or []:
        if not isinstance(cond, dict):
            continue
        kind = cond.get("kind")
        if kind in ("KALSHI_YES", "UNRESTRICTED"):
            agg = _path_aggregate(population, "W")
            yes_agg = _path_aggregate(population, "expiration_result_yes")
            terminal_results.append(
                {
                    "kind": kind,
                    "binding": cond.get("binding"),
                    "label": "terminal YES proportion (artifact field W)",
                    "W": agg,
                    "expiration_result_yes": yes_agg,
                }
            )
            terminal_status = "COMPLETE"
        else:
            terminal_results.append(
                {
                    "kind": kind,
                    "status": "ABSENT",
                    "reason": "Phase 4 has no authoritative binding for this terminal condition",
                }
            )
            if terminal_status != "COMPLETE":
                terminal_status = "PARTIAL"

    measurements: list[dict[str, Any]] = _route_measurements(
        spec,
        population=population,
        population_context=_population_context_first80(population),
    )

    partition = _empirical_partition(population)
    rows_out, truncated = _serialize_population_rows(population)
    if truncated:
        caveats.append(
            f"population.rows truncated to {POPULATION_ROWS_SERIALIZE_CAP} for transport; "
            f"population.count={len(population)} is full"
        )
    caveats.extend(filter_notes)

    desc_parts = ["NBA warehouse FIRST_80 candidates"]
    if slices:
        desc_parts.append(f"structural slices {slices} via {ENTRY_SLICE_ARTIFACT_FIELD}")
    description = " · ".join(desc_parts)

    return to_jsonable(
        {
            "research_object_id": rid,
            "execution_status": "COMPLETE",
            "validation": {
                "valid": validation.get("valid"),
                "runnable": validation.get("runnable"),
                "status": validation.get("status"),
                "errors": validation.get("errors") or [],
                "unresolved": validation.get("unresolved") or [],
            },
            "summary": {
                "population_n": len(population),
                "population_description": description,
            },
            "bindings": {
                "FIRST80": {
                    "requested_definition_version": requested,
                    "actual_definition_version": requested,
                    "status": "COMPLETE",
                },
                "T40": {
                    "requested_definition_version": (spec.get("definition_versions") or {}).get(
                        "T40"
                    ),
                    "actual_definition_version": BINDING_BARRIER_SURVIVAL_V1,
                    "status": "COMPLETE",
                },
            },
            "population": {
                "status": "COMPLETE",
                "count": len(population),
                "rows": rows_out,
                "rows_truncated": truncated,
                "trades": _full_population_trades(population),
            },
            "path_conditions": {"status": path_status, "results": path_results},
            "terminal_conditions": {"status": terminal_status, "results": terminal_results},
            "measurements": measurements,
            "provenance": {
                "definition_versions": dict(spec.get("definition_versions") or {}),
                "dataset_versions": dict(spec.get("dataset_versions") or {}),
                "source_artifacts": source_artifacts,
                "entry_slice_binding": {
                    "schema_field": "entry_slice",
                    "artifact_field": ENTRY_SLICE_ARTIFACT_FIELD,
                },
                "seed_first80_n": len(first80),
                "join_unmatched_n": unmatched,
                "measurement_routing": "measurement_registry_v0",
            },
            "empirical_partition": partition,
            "caveats": caveats,
        }
    )


def _execute_roller_first80(spec: dict[str, Any], validation: dict[str, Any]) -> dict[str, Any]:
    """Execute roller_4.1.0-R binding only — never fall back to warehouse."""
    rid = validation.get("research_object_id")
    requested = BINDING_ROLLER_FIRST80
    try:
        from roller.config import RollerConfig
        from roller.research.first80 import load_first80
    except Exception as exc:  # pragma: no cover
        return _empty_result(
            research_object_id=rid,
            execution_status="ABSENT",
            validation=validation,
            bindings={
                "FIRST80": {
                    "requested_definition_version": requested,
                    "actual_definition_version": None,
                    "status": "ABSENT",
                    "reason": f"ROLLER first80 import failed: {exc}",
                }
            },
            caveats=["roller_4.1.0-R requested; warehouse_frozen_v1 was NOT used as fallback"],
            message="roller_4.1.0-R API unavailable",
        )

    try:
        cfg = RollerConfig()
        book = load_first80(cfg, sport="NBA", season="2025-2026", full_history=True)
    except Exception as exc:
        return _empty_result(
            research_object_id=rid,
            execution_status="ABSENT",
            validation=validation,
            bindings={
                "FIRST80": {
                    "requested_definition_version": requested,
                    "actual_definition_version": None,
                    "status": "ABSENT",
                    "reason": str(exc),
                }
            },
            message="roller_4.1.0-R load_first80 failed — warehouse not used",
        )

    rows = list(book.get("rows") or [])
    if not rows:
        return _empty_result(
            research_object_id=rid,
            execution_status="ABSENT",
            validation=validation,
            bindings={
                "FIRST80": {
                    "requested_definition_version": requested,
                    "actual_definition_version": None,
                    "status": "ABSENT",
                    "reason": "first80_triggers empty or missing for NBA 2025-2026",
                }
            },
            caveats=["roller_4.1.0-R requested; warehouse_frozen_v1 was NOT used as fallback"],
            message="ROLLER FIRST80 artifact absent — no silent warehouse fallback",
        )

    first_rows = [r for r in rows if r.get("status") == "FIRST_80"]
    partition = _empirical_partition(first_rows)
    rows_out, truncated = _serialize_population_rows(first_rows)
    return to_jsonable(
        {
            "research_object_id": rid,
            "execution_status": "COMPLETE",
            "validation": {
                "valid": validation.get("valid"),
                "runnable": validation.get("runnable"),
                "status": validation.get("status"),
                "errors": validation.get("errors") or [],
                "unresolved": validation.get("unresolved") or [],
            },
            "summary": {
                "population_n": len(first_rows),
                "population_description": "ROLLER load_first80 NBA 2025-2026 FIRST_80 rows",
            },
            "bindings": {
                "FIRST80": {
                    "requested_definition_version": requested,
                    "actual_definition_version": requested,
                    "status": "COMPLETE",
                }
            },
            "population": {
                "status": "COMPLETE",
                "count": len(first_rows),
                "rows": rows_out,
                "trades": _full_population_trades(first_rows),
                "rows_truncated": truncated,
            },
            "path_conditions": {"status": "ABSENT", "results": []},
            "terminal_conditions": {"status": "ABSENT", "results": []},
            "measurements": _route_measurements(
                spec,
                population=first_rows,
                population_context=_population_context_first80(first_rows),
            ),
            "provenance": {
                "definition_versions": dict(spec.get("definition_versions") or {}),
                "dataset_versions": dict(spec.get("dataset_versions") or {}),
                "source_artifacts": ["roller.research.first80.load_first80"],
                "rule_version": book.get("rule_version"),
            },
            "empirical_partition": partition,
            "caveats": list(_BASE_CAVEATS)
            + ["Executed roller_4.1.0-R only — warehouse not consulted"],
        }
    )



def _execute_ncaab_first80_p5(spec: dict[str, Any], validation: dict[str, Any]) -> dict[str, Any]:
    """Explicit NCAAB P5∩P5 FIRST80 route.

    Membership authority = frozen parquet rows alone.
    No P5 reconstruction, no candidates.json cross-check, no NBA fallback.
    """
    rid = validation.get("research_object_id")
    caveats = list(_BASE_CAVEATS)
    requested = BINDING_NCAAB_FIRST80_P5
    defs = spec.get("definition_versions") if isinstance(spec.get("definition_versions"), dict) else {}
    requested_ver = defs.get("NCAAB_FIRST80_P5")

    if requested_ver != BINDING_NCAAB_FIRST80_P5:
        return _empty_result(
            research_object_id=rid,
            execution_status="ABSENT",
            validation=validation,
            bindings={
                "NCAAB_FIRST80_P5": {
                    "requested_definition_version": requested_ver,
                    "actual_definition_version": None,
                    "status": "ABSENT",
                    "reason": (
                        f"NCAAB_FIRST80_P5 requires {BINDING_NCAAB_FIRST80_P5!r}; "
                        f"got {requested_ver!r}. No fallback to NBA FIRST80."
                    ),
                    "fallback": False,
                }
            },
            message="NCAAB_FIRST80_P5 binding version mismatch — ABSENT (no fallback)",
        )

    path = _ncaab_p5_path()
    if not path.is_file():
        return _empty_result(
            research_object_id=rid,
            execution_status="ABSENT",
            validation=validation,
            bindings={
                "NCAAB_FIRST80_P5": {
                    "requested_definition_version": requested,
                    "actual_definition_version": None,
                    "status": "ABSENT",
                    "reason": f"NCAAB P5 trades artifact missing: {path}",
                    "fallback": False,
                }
            },
            message="p5_half_barrier_survival_v1 trades.parquet not available",
        )

    # Membership = artifact rows as-is. No dedupe, no second-source validation.
    df = pd.read_parquet(path)
    source_artifacts = [str(path), NCAAB_FIRST80_P5_ARTIFACT_LABEL]
    population: list[dict[str, Any]] = []
    for _, trow in df.iterrows():
        population.append(
            {
                "ticker": to_jsonable(trow.get("ticker")),
                "event_id": to_jsonable(trow.get("event_id")),
                "game_date": to_jsonable(trow.get("game_date")),
                "team": to_jsonable(trow.get("team")),
                "first_80_timestamp": to_jsonable(trow.get("first_80_timestamp")),
                ENTRY_HALF_ARTIFACT_FIELD: to_jsonable(trow.get(ENTRY_HALF_ARTIFACT_FIELD)),
                "T40": to_jsonable(trow.get("T40")),
                "W": to_jsonable(trow.get("W")),
                "T50": to_jsonable(trow.get("T50")),
                "T60": to_jsonable(trow.get("T60")),
                "alignment_confidence": to_jsonable(trow.get("alignment_confidence")),
                "espn_game_id": to_jsonable(trow.get("espn_game_id")),
            }
        )

    caveats.append(
        "NCAAB_FIRST80_P5 membership authority = frozen parquet rows "
        "(no P5∩P5 reconstruction; no candidates.json cross-check)"
    )
    caveats.append(
        f"Phase 6 adapter binding: structural slices ↔ artifact {ENTRY_HALF_ARTIFACT_FIELD}"
    )

    slices = _requested_slices(spec)
    filter_notes: list[str] = []
    if slices:
        supported = {"H1_1", "H1_2", "H2_1", "H2_2", "OT", "UNALIGNED"}
        unsupported = [s for s in slices if s not in supported]
        usable = [s for s in slices if s in supported]
        if unsupported:
            filter_notes.append(
                f"Unsupported structural slices for NCAAB P5 path: {unsupported}"
            )
        if usable:
            population = [r for r in population if r.get(ENTRY_HALF_ARTIFACT_FIELD) in usable]
            filter_notes.append(
                f"Filtered {ENTRY_HALF_ARTIFACT_FIELD} in {usable}"
            )
        elif unsupported and not usable:
            return _empty_result(
                research_object_id=rid,
                execution_status="PARTIAL",
                validation=validation,
                bindings={
                    "NCAAB_FIRST80_P5": {
                        "requested_definition_version": requested,
                        "actual_definition_version": requested,
                        "status": "PARTIAL",
                        "reason": "structural slices unsupported for half-bucket axis",
                        "fallback": False,
                    }
                },
                caveats=filter_notes,
                message="Requested structural slices are not executable on NCAAB P5 half axis",
            )

    path_results: list[dict[str, Any]] = []
    path_status = "ABSENT"
    for cond in spec.get("path_conditions") or []:
        if not isinstance(cond, dict):
            continue
        kind = cond.get("kind")
        binding = cond.get("binding")
        price_e4 = cond.get("price_e4")
        if (
            kind == "EVER_CLOSE_LE"
            and price_e4 == 4000
            and binding in (BINDING_BARRIER_SURVIVAL_V1, None, "barrier_survival_v1")
        ):
            agg = _path_aggregate(population, "T40")
            path_results.append(
                {
                    "kind": kind,
                    "price_e4": price_e4,
                    "binding": BINDING_BARRIER_SURVIVAL_V1,
                    "label": "T40 path proportion (proportion of population with T40 == True)",
                    **agg,
                }
            )
            path_status = "COMPLETE"
        else:
            path_results.append(
                {
                    "kind": kind,
                    "binding": binding,
                    "status": "ABSENT",
                    "reason": "No authoritative binding for this path condition on NCAAB P5 route",
                }
            )
            if path_status != "COMPLETE":
                path_status = "PARTIAL"

    terminal_results: list[dict[str, Any]] = []
    terminal_status = "ABSENT"
    for cond in spec.get("terminal_conditions") or []:
        if not isinstance(cond, dict):
            continue
        kind = cond.get("kind")
        if kind in ("KALSHI_YES", "UNRESTRICTED"):
            agg = _path_aggregate(population, "W")
            terminal_results.append(
                {
                    "kind": kind,
                    "binding": cond.get("binding"),
                    "label": "terminal YES proportion (artifact field W)",
                    "W": agg,
                }
            )
            terminal_status = "COMPLETE"
        else:
            terminal_results.append(
                {
                    "kind": kind,
                    "status": "ABSENT",
                    "reason": "No authoritative binding for this terminal condition on NCAAB P5 route",
                }
            )
            if terminal_status != "COMPLETE":
                terminal_status = "PARTIAL"

    measurements = _route_measurements(
        spec,
        population=population,
        population_context=_population_context_ncaab_first80_p5(population),
    )

    partition = _empirical_partition(population)
    rows_out, truncated = _serialize_population_rows(population)
    if truncated:
        caveats.append(
            f"population.rows truncated to {POPULATION_ROWS_SERIALIZE_CAP} for transport; "
            f"population.count={len(population)} is full"
        )
    caveats.extend(filter_notes)

    desc_parts = ["NCAAB P5∩P5 FIRST80 frozen parquet"]
    if slices:
        desc_parts.append(f"structural slices {slices} via {ENTRY_HALF_ARTIFACT_FIELD}")
    description = " · ".join(desc_parts)

    return to_jsonable(
        {
            "research_object_id": rid,
            "execution_status": "COMPLETE",
            "validation": {
                "valid": validation.get("valid"),
                "runnable": validation.get("runnable"),
                "status": validation.get("status"),
                "errors": validation.get("errors") or [],
                "unresolved": validation.get("unresolved") or [],
            },
            "summary": {
                "population_n": len(population),
                "population_description": description,
            },
            "bindings": {
                "NCAAB_FIRST80_P5": {
                    "requested_definition_version": requested,
                    "actual_definition_version": requested,
                    "status": "COMPLETE",
                    "fallback": False,
                },
                "T40": {
                    "requested_definition_version": defs.get("T40"),
                    "actual_definition_version": BINDING_BARRIER_SURVIVAL_V1,
                    "status": "COMPLETE",
                },
            },
            "population": {
                "status": "COMPLETE",
                "count": len(population),
                "rows": rows_out,
                "rows_truncated": truncated,
                "trades": _full_population_trades(population),
            },
            "path_conditions": {"status": path_status, "results": path_results},
            "terminal_conditions": {"status": terminal_status, "results": terminal_results},
            "measurements": measurements,
            "provenance": {
                "definition_versions": dict(defs),
                "dataset_versions": dict(spec.get("dataset_versions") or {}),
                "source_artifacts": source_artifacts,
                "entry_slice_binding": {
                    "schema_field": "entry_slice",
                    "artifact_field": ENTRY_HALF_ARTIFACT_FIELD,
                },
                "fallback": False,
                "membership_authority": NCAAB_FIRST80_P5_ARTIFACT_LABEL,
                "measurement_routing": "measurement_registry_v0",
            },
            "empirical_partition": partition,
            "caveats": caveats,
        }
    )


def execute_research_object(spec: dict[str, Any]) -> dict[str, Any]:
    """Validate then orchestrate authoritative empirical execution for one research_spec."""
    t0 = time.perf_counter()
    validation = validate_for_api(spec)
    status = validation.get("status")
    rid = validation.get("research_object_id")

    if status == "INVALID":
        out = _empty_result(
            research_object_id=rid,
            execution_status="INVALID",
            validation=validation,
            message="NO EXECUTION — research_spec INVALID",
        )
        out["elapsed_ms"] = round((time.perf_counter() - t0) * 1000, 3)
        return out

    if status == "UNRESOLVED":
        out = _empty_result(
            research_object_id=rid,
            execution_status="UNRESOLVED",
            validation=validation,
            message="NO EXECUTION — research_spec UNRESOLVED (validation gate)",
        )
        out["elapsed_ms"] = round((time.perf_counter() - t0) * 1000, 3)
        return out

    if status != "RUNNABLE":
        out = _empty_result(
            research_object_id=rid,
            execution_status=str(status or "ABSENT"),
            validation=validation,
            message="NO EXECUTION — unexpected validation status",
        )
        out["elapsed_ms"] = round((time.perf_counter() - t0) * 1000, 3)
        return out

    defs = spec.get("definition_versions") if isinstance(spec.get("definition_versions"), dict) else {}
    # Explicit NCAAB key wins when present — never inferred from anchor alone.
    if "NCAAB_FIRST80_P5" in defs:
        out = _execute_ncaab_first80_p5(spec, validation)
        out["elapsed_ms"] = round((time.perf_counter() - t0) * 1000, 3)
        return out

    first80_ver = defs.get("FIRST80")
    anchor = spec.get("anchor") if isinstance(spec.get("anchor"), dict) else {}
    event = anchor.get("event")

    if first80_ver == BINDING_WAREHOUSE_FROZEN_V1 and event == "FIRST_PRICE_TOUCH":
        out = _execute_warehouse_first80(spec, validation)
    elif first80_ver == BINDING_ROLLER_FIRST80 and event == "FIRST_PRICE_TOUCH":
        out = _execute_roller_first80(spec, validation)
    elif first80_ver in (BINDING_WAREHOUSE_FROZEN_V1, BINDING_ROLLER_FIRST80):
        out = _empty_result(
            research_object_id=rid,
            execution_status="PARTIAL",
            validation=validation,
            bindings={
                "FIRST80": {
                    "requested_definition_version": first80_ver,
                    "actual_definition_version": None,
                    "status": "ABSENT",
                    "reason": f"anchor.event={event!r} not supported for FIRST80 Phase 4 path",
                }
            },
            message="FIRST80 binding present but anchor event not executable in Phase 4",
        )
    else:
        measurements = _route_measurements(
            spec,
            population=[],
            population_context={
                "definition_family": None,
                "available_fields": [],
            },
        )
        out = _empty_result(
            research_object_id=rid,
            execution_status="PARTIAL",
            validation=validation,
            bindings={
                "FIRST80": {
                    "requested_definition_version": first80_ver,
                    "actual_definition_version": None,
                    "status": "ABSENT",
                }
            },
            measurements=measurements,
            message=(
                "The research object is structurally valid, but Phase 6 has no authoritative "
                "empirical population/executor binding for this object."
            ),
        )

    out["elapsed_ms"] = round((time.perf_counter() - t0) * 1000, 3)
    return out



__all__ = ["execute_research_object"]
