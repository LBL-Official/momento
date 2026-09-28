"""Execute a compiled plan. Server recompiles. Client cannot force the path."""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Any, Callable

from roller.config import RollerConfig
from roller.dashboard_adapter.research_executor import execute_research_object
from roller.dashboard_adapter.research_object_ops import list_templates
from roller.research_query import cache as rq_cache
from roller.research_query import result_cache as rq_result
from roller.research_query.availability import (
    RESEARCH_LEAGUE,
    RESEARCH_SEASON,
    RESEARCH_SPORT,
    LeagueScope,
    resolve_league_scopes,
    resolve_sport_season,
)
from roller.research_query.season_mapping import sport_from_league
from roller.research_query.planner import QueryPlan, bundle_from_index, plan_query
from roller.research_query.compiler import compile_draft, compile_question
from roller.research_query.dataset_version import dataset_fingerprint
from roller.research_query.entry_engine import (
    TouchEvent,
    observation_sequence,
    observe_entry,
    same_minute_ties,
)
from roller.research_query.facts import TradableIndex
from roller.research_query.hashing import layer_hashes, normalize_state_filters, te_scope_funnel_label
from roller.research_query.identity import EXCLUSION_KEYS, build_identity
from roller.research_query.measurements import measure_finite_math, measure_rows
from roller.research_query.official_settlement import (
    OFFICIAL_W_TAG,
    merge_official_settlement,
    needs_official_settlement,
)
from roller.exposure_contract import (
    GAME,
    MODE_STRATEGY_ENFORCED,
    MODE_VERIFY_ONLY,
    STATUS_CARDINALITY,
    STATUS_DATA_REQUIRED,
    enforce_exposure,
    enforcement_request_from_draft,
    executable_strategy_contract,
    exposure_identity_payload,
    unit_key,
)
from roller.results_math import analyze_result
from roller.research_query.models import (
    BASIS_LAST_TRADE,
    BASIS_TRADABLE,
    CompileResult,
    ExecutionPath,
    ExitOutcome,
    FunnelStep,
    PathOp,
    ResearchQuestion,
    ResearchStatus,
    TerminalOutcome,
    TouchOrdinal,
)
from roller.research_query.path_engine import _elapsed_from_snap, run_path
from roller.research_query.population import intersect_tickers
from roller.research_query.provenance import (
    GENERIC_CAVEATS,
    KALSHI_LAST_TRADE_CAVEATS,
    LAST_TRADE_CAVEATS,
    generic_provenance,
)
from roller.timeutil import parse_utc


def _settled_yes(market: dict[str, Any] | None) -> bool | None:
    if not market:
        return None
    result = str(market.get("result") or market.get("kalshi_result") or "").lower()
    if result == "yes":
        return True
    if result == "no":
        return False
    for key in ("expiration_result_yes", "W", "terminal_yes"):
        flag = market.get(key)
        if flag in (True, 1, "1", "true", "True", "yes", "YES"):
            return True
        if flag in (False, 0, "0", "false", "False", "no", "NO"):
            return False
    sv = market.get("settlement_value_e4")
    try:
        if sv in (None, ""):
            return None
        iv = int(sv)
    except (TypeError, ValueError):
        return None
    if iv == 10000:
        return True
    if iv == 0:
        return False
    return None


def _all_loaded_bars_untradable(
    question: ResearchQuestion,
    diag_sum: dict[str, int],
    identity: set[str],
    ticker_payloads: dict[str, list[dict[str, Any]]],
    perf: dict[str, Any],
) -> bool:
    """True when every scanned TRADABLE bar failed quality(). Not last-trade."""
    if identity:
        return False
    if (question.basis() or BASIS_TRADABLE) != BASIS_TRADABLE:
        return False
    scanned = int(perf.get("rows_scanned") or 0)
    if scanned <= 0:
        scanned = sum(len(v) for v in ticker_payloads.values())
    skipped = int(diag_sum.get("skipped_untradable") or 0)
    return scanned > 0 and skipped >= scanned


def _ms(started: float) -> int:
    return int(round((time.perf_counter() - started) * 1000))


def apply_te_population_scope(
    rows: list[dict[str, Any]],
    filters: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Restrict reported N to requested PIT score chips. Missing score fails closed."""
    from roller.base_terminal_efficiency.attach import row_matches_te_filters

    requested = normalize_state_filters(filters)
    n_entry = len(rows)
    if not requested:
        return list(rows), {
            "requested": None,
            "n_entry": n_entry,
            "n_scoped": n_entry,
            "n_dropped": 0,
        }
    kept = [r for r in rows if row_matches_te_filters(r, filters)]
    return kept, {
        "requested": requested,
        "n_entry": n_entry,
        "n_scoped": len(kept),
        "n_dropped": n_entry - len(kept),
    }


def _league_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        key = str(row.get("league") or row.get("sport") or "unknown")
        counts[key] = counts.get(key, 0) + 1
    return counts


def _candidate_from_event(ev: TouchEvent) -> dict[str, Any]:
    """Already-qualified entry. Does not invent a game id from ticker."""
    gid = str(ev.bar.game_id or "").strip()
    ticker = str(ev.bar.ticker or "")
    ts = ev.bar.ts.isoformat().replace("+00:00", "Z")
    raw = ev.bar.raw if isinstance(ev.bar.raw, dict) else {}
    return {
        "ticker": ticker,
        "internal_game_id": gid or None,
        "game_id": gid or None,
        "entry_ts": ts,
        "candidate_id": f"{ts}|{ticker}|{gid}",
        "team_id": raw.get("team_id") or raw.get("team"),
        "event_id": raw.get("event_id") or raw.get("event_ticker") or raw.get("kalshi_event_ticker"),
    }


def _public_exposure(decision: dict[str, Any]) -> dict[str, Any]:
    out = {k: v for k, v in decision.items() if k != "retained"}
    out["retained_tickers"] = [r.get("ticker") for r in decision.get("retained") or []]
    return out


def _envelope(
    *,
    compiled: CompileResult,
    execution_status: str,
    rows: list[dict[str, Any]] | None,
    funnel: list[dict[str, Any]] | None,
    diagnostics: dict[str, Any] | None,
    message: str | None = None,
    identity: dict[str, Any] | None = None,
    performance: dict[str, Any] | None = None,
    stages: list[dict[str, Any]] | None = None,
    hashes: dict[str, str] | None = None,
    dataset_version: str | None = None,
    te_summary: dict[str, Any] | None = None,
    mlb_observability: dict[str, Any] | None = None,
    exposure: dict[str, Any] | None = None,
) -> dict[str, Any]:
    measured = rows is not None
    metrics = measure_rows(rows) if rows is not None else None
    n = metrics["n"] if metrics else None
    last_trade = compiled.question.basis() == BASIS_LAST_TRADE
    kalshi_only = "kalshi" in compiled.question.universe.markets and "polymarket" not in compiled.question.universe.markets
    if last_trade and kalshi_only:
        caveats = list(KALSHI_LAST_TRADE_CAVEATS)
    elif last_trade:
        caveats = list(LAST_TRADE_CAVEATS)
    else:
        caveats = list(GENERIC_CAVEATS)
    if message:
        caveats.append(message)
    prov = generic_provenance(compiled.question, compiled, diagnostics=diagnostics)
    if exposure:
        prov = {
            **prov,
            "exposure_unit": exposure.get("exposure_unit"),
            "max_entries_per_unit": exposure.get("max_entries_per_unit"),
            "exposure_enforcement_version": exposure.get("exposure_enforcement_version"),
            "exposure_enforcement_mode": exposure.get("enforcement_mode"),
            "exposure_selection_policy": exposure.get("selection_policy"),
            "raw_entry_candidates": exposure.get("raw_entry_candidates"),
            "exposure_retained": exposure.get("exposure_retained"),
            "exposure_excluded": exposure.get("exposure_excluded"),
            "exposure_ambiguous": exposure.get("exposure_ambiguous"),
            "unique_units_before": exposure.get("unique_units_before"),
            "unique_units_after": exposure.get("unique_units_after"),
            "max_entries_observed": exposure.get("max_entries_observed"),
            "exposure_status": exposure.get("exposure_status"),
        }
    measurements = []
    partition: dict[str, Any] = {"status": "ABSENT", "cells": {}}
    if metrics:
        measurements = [
            {
                "name": "path_rate",
                "status": "COMPLETE" if metrics["path_available"] else "ABSENT",
                "value": metrics["path_rate"],
                "detail": {
                    "count_true": metrics["path_true"],
                    "count_available": metrics["path_available"],
                },
            },
            {
                "name": "kalshi_yes_rate",
                "status": "COMPLETE" if metrics["terminal_available"] else "ABSENT",
                "value": metrics["yes_rate"],
                "detail": {
                    "count_true": metrics["terminal_yes"],
                    "count_available": metrics["terminal_available"],
                    "terminal_missing": metrics["terminal_missing"],
                },
            },
        ]
        measurements.extend(
            [
                {
                    "name": "win_on_n",
                    "status": "COMPLETE" if metrics["n"] else "ABSENT",
                    "value": metrics.get("win_on_n"),
                    "detail": {
                        "count_true": metrics["win_exit"],
                        "count_available": metrics["n"],
                    },
                    "caveat": "WIN_EXIT / N. Same population as LOSS_EXIT / N. Residual is not LOSS.",
                },
                {
                    "name": "loss_on_n",
                    "status": "COMPLETE" if metrics["n"] else "ABSENT",
                    "value": metrics.get("loss_on_n"),
                    "detail": {
                        "count_true": metrics["loss_exit"],
                        "count_available": metrics["n"],
                    },
                    "caveat": "LOSS_EXIT / N. Same population as WIN_EXIT / N. PATH FALSE is not LOSS.",
                },
            ]
        )
        if metrics.get("exit_classified"):
            measurements.extend(
                [
                    {
                        "name": "win_exit_rate",
                        "status": "COMPLETE",
                        "value": metrics["win_exit_rate"],
                        "detail": {
                            "count_true": metrics["win_exit"],
                            "count_available": metrics["exit_classified"],
                        },
                    },
                    {
                        "name": "loss_exit_rate",
                        "status": "COMPLETE",
                        "value": metrics["loss_exit_rate"],
                        "detail": {
                            "count_true": metrics["loss_exit"],
                            "count_available": metrics["exit_classified"],
                        },
                    },
                ]
            )
        p = metrics["partition"]
        cells = [
            {"key": "T_AND_W", "path_true": True, "terminal_true": True, "n": p["T_AND_W"]},
            {"key": "T_AND_NOT_W", "path_true": True, "terminal_true": False, "n": p["T_AND_NOT_W"]},
            {"key": "NOT_T_AND_W", "path_true": False, "terminal_true": True, "n": p["NOT_T_AND_W"]},
            {"key": "NOT_T_AND_NOT_W", "path_true": False, "terminal_true": False, "n": p["NOT_T_AND_NOT_W"]},
        ]
        partition = {
            "status": "COMPLETE",
            "reason": None,
            "axes": [
                {"id": "path", "field": "path_true", "true_label": "PATH TRUE", "false_label": "PATH FALSE"},
                {"id": "terminal", "field": "terminal_yes", "true_label": "TERMINAL YES", "false_label": "TERMINAL NO"},
            ],
            "cells": cells,
            "n_population": metrics["n"],
            "n_joint_available": p["joint_n"],
            "n_missing": metrics["terminal_missing"],
            "path_margin": {
                "true": metrics["path_true"],
                "false": metrics["path_false"],
                "available": metrics["path_available"],
            },
            "joint_measured": p["joint_n"] > 0,
        }
        if not last_trade:
            # A last-trade print is not an executable price, so no P&L, EV,
            # drawdown or risk-of-ruin is reported on that basis.
            math = measure_finite_math(
                rows or [],
                model_a_8040=_is_model_a_8040(compiled.question),
                path_rate=metrics["path_rate"],
                path_true=metrics["path_true"],
                path_available=metrics["path_available"],
            )
            measurements.extend(_finite_math_measurements(math))
    tennis_obs = None
    from roller.research_query.sport_family import is_tennis

    if any(
        is_tennis(x)
        for x in (*compiled.question.universe.sports, *compiled.question.universe.leagues)
    ):
        from roller.tennis.observability import build_tennis_observability

        tennis_obs = build_tennis_observability(
            observation_basis=BASIS_LAST_TRADE if last_trade else BASIS_TRADABLE
        )
    ident_out = dict(identity or {})
    if exposure:
        ident_out["exposure"] = exposure
        ident_out.setdefault("exposure_unit", exposure.get("exposure_unit"))
        ident_out.setdefault("max_entries_per_unit", exposure.get("max_entries_per_unit"))
        ident_out.setdefault("max_entries_per_game", exposure.get("max_entries_per_game"))
    if te_summary:
        overall = te_summary.get("overall") or {}
        n_win = int(overall.get("n_win_exit") or 0)
        n_loss = int(overall.get("n_loss_exit") or 0)
        n_class = n_win + n_loss
        measurements.extend(
            [
                {
                    "name": "te_win_exit_rate",
                    "status": "COMPLETE" if n_class else "ABSENT",
                    "value": (n_win / n_class) if n_class else None,
                    "detail": {"count_true": n_win, "count_available": n_class},
                    "caveat": "Base TE exact-timestamp book. Not generic minute TIE_EXCLUDED.",
                },
                {
                    "name": "te_loss_exit_rate",
                    "status": "COMPLETE" if n_class else "ABSENT",
                    "value": (n_loss / n_class) if n_class else None,
                    "detail": {"count_true": n_loss, "count_available": n_class},
                    "caveat": "Base TE exact-timestamp book. Not generic minute TIE_EXCLUDED.",
                },
            ]
        )
    out = {
        "research_object_id": None,
        "execution_status": execution_status,
        "compile": compiled.to_dict(),
        "summary": {
            "population_n": n if measured else None,
            "population_description": (
                (
                    (
                        "kalshi last-trade query · LAST-TRADE PRINT OBSERVED · LAST TRADE ≠ YES BID"
                        if kalshi_only
                        else "polymarket last-trade query · LAST-TRADE PRINT OBSERVED"
                    )
                    if last_trade
                    else "generic candle query · CANDLE-LEVEL OBSERVED"
                )
                if measured
                else (
                    message
                    if message
                    else compiled.status.value
                )
            ),
        },
        "population": {
            "status": "COMPLETE" if measured else "ABSENT",
            "count": n if measured else 0,
            "rows": (rows or [])[:200],
            "rows_truncated": bool(rows and len(rows) > 200),
            "trades": list(rows or []),
            "funnel": funnel or [],
        },
        "measurements": measurements,
        "empirical_partition": partition,
        "provenance": prov,
        "caveats": caveats,
        "identity": ident_out,
        "performance": performance or {},
        "stages": stages or [],
        "hashes": hashes or {},
        "dataset_version": dataset_version,
        "analysis": (
            None
            if not measured
            else analyze_result(
                rows or [],
                question=compiled.question,
                funnel=funnel,
                hashes=hashes,
                dataset_version=dataset_version,
                last_trade=last_trade,
                metrics=metrics,
                identity=ident_out,
            )
        ),
        "base_terminal_efficiency": te_summary,
        "observation_basis": BASIS_LAST_TRADE if last_trade else BASIS_TRADABLE,
        "mlb": mlb_observability,
        "tennis": tennis_obs,
        "bindings": {
            "GENERIC_QUERY": {
                "status": execution_status,
                "path": "generic_query",
                "observability": (
                    "LAST-TRADE PRINT OBSERVED"
                    if last_trade
                    else "CANDLE-LEVEL OBSERVED"
                ),
            }
        },
    }
    if exposure:
        out["exposure"] = exposure
    return out


def evaluate_ticker(
    candles: list[dict[str, Any]],
    question: ResearchQuestion,
    *,
    sport: str = "NBA",
    pbp_events: list[dict[str, Any]] | None = None,
    snap_fn: Callable | None = None,
    market: dict[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, dict[str, int]]:
    """One ticker path. Returns a result row or None if entry AND fails."""
    if not question.entry_conditions:
        return None, {}
    basis = question.basis() or BASIS_TRADABLE
    merged_diag: dict[str, int] = defaultdict(int)
    events: list[TouchEvent] = []
    for cond in question.entry_conditions:
        ev, diag = observe_entry(
            candles,
            cond,
            sport=sport,
            snap_fn=snap_fn,
            pbp_events=pbp_events,
            prior_event=events[0] if events else None,
        )
        for k, v in diag.items():
            if isinstance(v, int):
                merged_diag[k] += v
        if ev is None:
            return None, dict(merged_diag)
        events.append(ev)
    # AND on same ticker: all conditions must fire on this path.
    entry = events[0]
    bars, skipped = observation_sequence(candles, basis=basis)
    merged_diag["skipped_untradable" if basis == BASIS_TRADABLE else "skipped_no_print"] = skipped
    return _result_row(
        entry,
        bars,
        question,
        market,
        snap_fn=snap_fn,
        sport=sport,
        pbp_events=pbp_events,
    ), dict(merged_diag)


def _result_row(
    entry: TouchEvent,
    bars: list,
    question: ResearchQuestion,
    market: dict[str, Any] | None,
    *,
    snap_fn: Callable | None = None,
    sport: str = "NBA",
    league: str | None = None,
    season: str | None = None,
    pbp_events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    from roller.research_query.entry_engine import default_snap

    after = [b for b in bars if b.ts > entry.bar.ts]
    resolved_snap = snap_fn
    if resolved_snap is None and pbp_events:
        resolved_snap = lambda ts: default_snap(ts, pbp_events, sport)
    needs_game = any(
        p.op in (PathOp.HORIZON_WIN, PathOp.HORIZON_LOSS) and p.horizon_kind == "game"
        for p in question.path_conditions
    )
    entry_elapsed = _elapsed_from_snap(entry.snap, sport) if needs_game else None
    classified = _classify_exits(
        after,
        entry,
        question,
        market,
        entry_elapsed=entry_elapsed,
        snap_fn=resolved_snap,
        sport=sport,
    )
    exit_bar = classified["exit_bar"]
    basis = entry.bar.basis
    hyp_pnl_cents = None
    mae_cents = None
    mfe_cents = None
    holding_seconds = None
    if exit_bar is not None and basis == BASIS_TRADABLE:
        hyp_pnl_cents = (int(exit_bar.bid) - int(entry.bar.bid)) // 100
        holding_seconds = int((exit_bar.ts - entry.bar.ts).total_seconds())
    if after and basis == BASIS_TRADABLE:
        entry_bid = int(entry.bar.bid)
        deltas = [(int(b.bid) - entry_bid) // 100 for b in after]
        if deltas:
            mfe_cents = max(deltas)
            mae_cents = min(deltas)
    # Semantic identity: Cross/Break/… must never appear as FIRST_TOUCH in CSV.
    touch_vals = {o.value for o in TouchOrdinal}
    resolved = entry.operation.value if entry.operation is not None else entry.ordinal.value
    is_touch = resolved in touch_vals
    return {
        "ticker": entry.bar.ticker,
        "internal_game_id": entry.bar.game_id,
        "sport": sport,
        "league": league,
        "warehouse_season": season,
        "price_basis": basis,
        "entry_operation": resolved,
        "entry_direction": entry.direction,
        "entry_ordinal": entry.ordinal.value if is_touch else "FIRST",
        "entry_price_e4": entry.price_e4,
        "entry_ts": entry.bar.ts.isoformat().replace("+00:00", "Z"),
        "entry_close": entry.bar.bid,
        "exit_close": exit_bar.bid if exit_bar is not None else None,
        "exit_ts": (
            exit_bar.ts.isoformat().replace("+00:00", "Z") if exit_bar is not None else None
        ),
        "hyp_pnl_cents": hyp_pnl_cents,
        "mae_cents": mae_cents,
        "mfe_cents": mfe_cents,
        "holding_seconds": holding_seconds,
        "path_true": classified["path_true"],
        "path_steps": classified["path_steps"],
        "win_exit": classified["win_exit"],
        "loss_exit": classified["loss_exit"],
        "exit_outcome": classified["exit_outcome"],
        "terminal_yes": classified["terminal_yes"],
        "alignment": entry.alignment,
    }


def _classify_exits(
    after: list,
    entry: TouchEvent,
    question: ResearchQuestion,
    market: dict[str, Any] | None,
    *,
    entry_elapsed: int | None,
    snap_fn: Callable | None,
    sport: str,
) -> dict[str, Any]:
    ty = _settled_yes(market)
    resolve_bar = after[-1] if after else None
    if not question.tagged_exits():
        path_hits, path_ok, exit_bar = run_path(
            after,
            entry.bar.bid,
            list(question.path_conditions),
            entry_ts=entry.bar.ts,
            entry_elapsed_s=entry_elapsed,
            snap_fn=snap_fn,
            sport=sport,
            resolve_bar=resolve_bar,
        )
        return {
            "path_true": path_ok if question.path_conditions else False,
            "path_steps": [h.op.value for h in path_hits],
            "win_exit": False,
            "loss_exit": False,
            "exit_outcome": None,
            "exit_bar": exit_bar,
            "terminal_yes": ty,
        }

    win_steps = [p for p in question.path_conditions if p.outcome is ExitOutcome.WIN]
    loss_steps = [p for p in question.path_conditions if p.outcome is ExitOutcome.LOSS]
    win_hits, win_ok, win_bar = (
        run_path(
            after,
            entry.bar.bid,
            win_steps,
            entry_ts=entry.bar.ts,
            entry_elapsed_s=entry_elapsed,
            snap_fn=snap_fn,
            sport=sport,
            resolve_bar=resolve_bar,
        )
        if win_steps
        else ([], False, None)
    )
    loss_hits, loss_ok, loss_bar = (
        run_path(
            after,
            entry.bar.bid,
            loss_steps,
            entry_ts=entry.bar.ts,
            entry_elapsed_s=entry_elapsed,
            snap_fn=snap_fn,
            sport=sport,
            resolve_bar=resolve_bar,
        )
        if loss_steps
        else ([], False, None)
    )
    win_ts = win_bar.ts if win_ok and win_bar is not None else None
    loss_ts = loss_bar.ts if loss_ok and loss_bar is not None else None
    outcome = None
    exit_bar = None
    path_steps: list[str] = []
    if win_ts is not None and loss_ts is not None:
        win_min = win_ts.strftime("%Y-%m-%dT%H:%M")
        loss_min = loss_ts.strftime("%Y-%m-%dT%H:%M")
        if win_min == loss_min:
            outcome = "TIE_EXCLUDED"
            exit_bar = None
        elif win_ts < loss_ts:
            outcome = "WIN_EXIT"
            exit_bar = win_bar
            path_steps = [h.op.value for h in win_hits]
        else:
            outcome = "LOSS_EXIT"
            exit_bar = loss_bar
            path_steps = [h.op.value for h in loss_hits]
    elif win_ts is not None:
        outcome = "WIN_EXIT"
        exit_bar = win_bar
        path_steps = [h.op.value for h in win_hits]
    elif loss_ts is not None:
        outcome = "LOSS_EXIT"
        exit_bar = loss_bar
        path_steps = [h.op.value for h in loss_hits]
    elif question.win_hold and ty is True:
        outcome = "WIN_EXIT"
    elif question.loss_hold and ty is False:
        outcome = "LOSS_EXIT"
    return {
        "path_true": outcome == "WIN_EXIT",
        "path_steps": path_steps,
        "win_exit": outcome == "WIN_EXIT",
        "loss_exit": outcome == "LOSS_EXIT",
        "exit_outcome": outcome,
        "exit_bar": exit_bar,
        "terminal_yes": ty,
    }


def _is_model_a_8040(question: ResearchQuestion) -> bool:
    """Documented FIRST80 Model A: enter 80, observe reach 40. Do not apply to other prices."""
    if len(question.entry_conditions) != 1 or not question.path_conditions:
        return False
    entry = question.entry_conditions[0]
    if entry.price_e4 != 8000:
        return False
    return any(p.op is PathOp.REACH and p.price_e4 == 4000 for p in question.path_conditions)


def _finite_math_measurements(math: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if math.get("model_a_ev_cents") is not None:
        rows.append(
            {
                "name": "model_a_8040_ev_cents",
                "status": "COMPLETE",
                "value": math["model_a_ev_cents"],
                "detail": {
                    "q": math.get("model_a_q"),
                    "formula": math.get("model_a_formula"),
                    "unit": "cents_per_contract",
                },
                "caveat": "HYPOTHETICAL · CANDLE PATH ≠ FILL · Model A +20 survive / −40 close-40 / 0 leak",
            }
        )
    if math.get("mean_hyp_pnl_cents") is not None:
        rows.append(
            {
                "name": "observed_hyp_ev_cents",
                "status": "COMPLETE",
                "value": math["mean_hyp_pnl_cents"],
                "detail": {"n": math.get("observed_n"), "unit": "cents_per_contract"},
                "caveat": "HYPOTHETICAL · CANDLE PATH ≠ FILL · mean(exit_close − entry_close)",
            }
        )
    if math.get("max_drawdown_cents") is not None:
        rows.append(
            {
                "name": "max_drawdown_cents",
                "status": "COMPLETE",
                "value": math["max_drawdown_cents"],
                "detail": {"source": math.get("max_drawdown_source"), "unit": "cents"},
                "caveat": "HYPOTHETICAL peak-to-trough on the chronological candle-path P&L sequence",
            }
        )
    return rows


def _frozen_spec(template_id: str) -> dict[str, Any]:
    for t in list_templates():
        if t.get("id") == template_id and t.get("research_spec"):
            return t["research_spec"]
    raise KeyError(f"frozen template {template_id} not found")


def execute_compiled(
    compiled: CompileResult,
    *,
    cfg: RollerConfig | None = None,
    ticker_payloads: dict[str, list[dict[str, Any]]] | None = None,
    pbp_by_game: dict[str, list[dict[str, Any]]] | None = None,
    markets_by_ticker: dict[str, dict[str, Any]] | None = None,
    snap_fn: Callable | None = None,
    games: list[dict[str, Any]] | None = None,
    tradable_index: TradableIndex | None = None,
    te_filters: dict[str, Any] | None = None,
    exposure_enforcement_mode: str | None = None,
    exposure_unit: str | None = None,
    max_entries_per_unit: int | None = None,
    force_full_scan: bool = False,
) -> dict[str, Any]:
    if compiled.status is ResearchStatus.OPERATION_REQUIRED:
        return _envelope(
            compiled=compiled,
            execution_status="OPERATION_REQUIRED",
            rows=None,
            funnel=None,
            diagnostics=None,
            message="NO EXECUTION — operation has no approved definition. Not an empty population.",
        )
    if compiled.status is ResearchStatus.DATA_REQUIRED:
        return _envelope(
            compiled=compiled,
            execution_status="DATA_REQUIRED",
            rows=None,
            funnel=None,
            diagnostics=None,
            message="NO EXECUTION — required data is missing. Kalshi is not substituted.",
        )
    if compiled.status is ResearchStatus.READY_WITH_LIMITATIONS and not compiled.question.accept_limitations:
        return _envelope(
            compiled=compiled,
            execution_status="READY_WITH_LIMITATIONS",
            rows=None,
            funnel=None,
            diagnostics=None,
            message="NO EXECUTION — acknowledge omitted_dimensions first.",
        )
    if compiled.execution_path is ExecutionPath.FROZEN_REFERENCE and compiled.reference_match:
        spec = _frozen_spec(compiled.reference_match)
        out = execute_research_object(spec)
        out.setdefault("compile", compiled.to_dict())
        return out

    q = compiled.question
    cfg = cfg or RollerConfig()
    scopes = resolve_league_scopes(q.universe) or ()
    resolved = resolve_sport_season(q.universe)
    fallback_sport = scopes[0].sport if len(scopes) == 1 else (resolved[0] if resolved else "NBA")
    sport = fallback_sport
    t0 = time.perf_counter()
    exp_mode = str(exposure_enforcement_mode or MODE_VERIFY_ONLY)
    exp_contract = None
    exp_payload = None
    if exp_mode == MODE_STRATEGY_ENFORCED:
        unit = exposure_unit or GAME
        cap = max_entries_per_unit
        if cap is None and unit == GAME:
            cap = 1
        exp_contract = executable_strategy_contract(
            exposure_unit=unit,
            max_entries_per_unit=cap,
            enforcement_mode=MODE_STRATEGY_ENFORCED,
        )
        exp_payload = exposure_identity_payload(exp_contract)
    hashes = layer_hashes(q, state=te_filters, exposure=exp_payload)
    ds_ver = dataset_fingerprint(q, cfg=cfg) if ticker_payloads is None else "injected"
    stages: list[dict[str, Any]] = []
    perf = {
        "dataset_load_ms": 0,
        "entry_scan_ms": 0,
        "pbp_alignment_ms": 0,
        "population_intersection_ms": 0,
        "path_measurement_ms": 0,
        "aggregation_ms": 0,
        "total_ms": 0,
        "index_build_ms": 0,
        "cache_hit_warehouse": False,
        "cache_hit_entry": False,
        "cache_hit_path": False,
        "cache_hit_result": False,
        "execution_mode": "full_scan",
        "index_version": None,
        "rows_scanned": None,
    }

    injected = ticker_payloads is not None
    loaded_here = not injected
    uh = hashes["universe_hash"]
    eh = hashes["entry_hash"]
    ph = hashes["path_hash"]
    overlay_on = (not injected) and needs_official_settlement(q)
    exp_tag = f":exp:{hashes['exposure_hash'][:16]}" if hashes.get("exposure_hash") else ""
    path_cache_key = f"{ph}:{OFFICIAL_W_TAG}{exp_tag}" if overlay_on else f"{ph}{exp_tag}"
    result_key = None
    settlement_meta: dict[str, Any] | None = None
    prebuilt_index = tradable_index
    skip_csv = False
    indexed_games: list[dict[str, Any]] = []
    games_rows: list[dict[str, Any]] = list(games or [])
    cached_wh = rq_cache.get_warehouse(uh, ds_ver) if loaded_here else None
    if injected:
        plan = QueryPlan("full_scan", None, None, None, "injected")
    elif force_full_scan:
        plan = QueryPlan("full_scan", None, None, None, "reference_engine")
        prebuilt_index = None
        if cached_wh is not None:
            ticker_payloads, pbp_by_game, markets_by_ticker, games_rows = cached_wh
            skip_csv = True
            perf["cache_hit_warehouse"] = True
        perf["execution_mode"] = "full_scan"
    elif cached_wh is not None:
        ticker_payloads, pbp_by_game, markets_by_ticker, games_rows = cached_wh
        skip_csv = True
        perf["cache_hit_warehouse"] = True
        cached_idx = rq_cache.get_index(uh, ds_ver)
        if cached_idx is not None:
            from roller.research_query.indexes.manifest import INDEX_VERSION

            prebuilt_index = cached_idx
            plan = QueryPlan(
                "indexed",
                INDEX_VERSION,
                sum(len(seq) for seq in cached_idx.bars.values()),
                None,
                None,
            )
        else:
            plan = QueryPlan("full_scan", None, None, None, "warehouse_cache")
        perf["execution_mode"] = plan.execution_mode
        perf["index_version"] = plan.index_version
        perf["rows_scanned"] = plan.rows_scanned
        result_key = rq_result.result_key(
            question_hash=hashes["question_hash"],
            dataset_version=f"{ds_ver}:{OFFICIAL_W_TAG}" if overlay_on else ds_ver,
            index_version=plan.index_version or "none",
        )
        cached_env = rq_result.get(result_key)
        if cached_env is not None:
            trades = (cached_env.get("population") or {}).get("trades") or []
            if trades and not any(isinstance(r.get("te"), dict) for r in trades):
                cached_env = None
            else:
                from roller.base_terminal_efficiency.attach import summarize_rows

                cached_env["base_terminal_efficiency"] = summarize_rows(trades, te_filters)
                perf_hit = cached_env.setdefault("performance", {})
                perf_hit["cache_hit_result"] = True
                perf_hit["cache_hit_warehouse"] = True
                perf_hit["cache_hit_entry"] = True
                perf_hit["cache_hit_path"] = True
                return cached_env
    else:
        plan = plan_query(compiled, cfg=cfg, dataset_version=ds_ver)
        perf["execution_mode"] = plan.execution_mode
        perf["index_version"] = plan.index_version
        perf["rows_scanned"] = plan.rows_scanned
        if plan.execution_mode == "unavailable":
            return _envelope(
                compiled=compiled,
                execution_status="DATA_REQUIRED",
                rows=None,
                funnel=None,
                diagnostics=None,
                message=f"NO EXECUTION — observation index unusable ({plan.reason}). Fail closed.",
                hashes=hashes,
                dataset_version=ds_ver,
                performance=perf,
            )
        result_key = rq_result.result_key(
            question_hash=hashes["question_hash"],
            dataset_version=f"{ds_ver}:{OFFICIAL_W_TAG}" if overlay_on else ds_ver,
            index_version=plan.index_version or "none",
        )
        cached_env = rq_result.get(result_key)
        if cached_env is not None:
            trades = (cached_env.get("population") or {}).get("trades") or []
            if trades and not any(isinstance(r.get("te"), dict) for r in trades):
                cached_env = None
            else:
                from roller.base_terminal_efficiency.attach import summarize_rows

                cached_env["base_terminal_efficiency"] = summarize_rows(trades, te_filters)
                perf_hit = cached_env.setdefault("performance", {})
                perf_hit["cache_hit_result"] = True
                perf_hit["cache_hit_warehouse"] = True
                perf_hit["cache_hit_entry"] = True
                perf_hit["cache_hit_path"] = True
                return cached_env
        if plan.execution_mode == "indexed" and plan.index is not None:
            bundle = bundle_from_index(plan.index)
            ticker_payloads = bundle["ticker_payloads"]
            pbp_by_game = bundle["pbp_by_game"]
            markets_by_ticker = bundle["markets_by_ticker"]
            prebuilt_index = bundle["tradable_index"]
            indexed_games = list(bundle.get("games") or [])
            if q.universe.date_from or q.universe.date_to:
                prebuilt_index = _clip_tradable_index(
                    prebuilt_index, q.universe.date_from, q.universe.date_to
                )
                ticker_payloads = {
                    t: rows for t, rows in ticker_payloads.items() if t in prebuilt_index.bars
                }
            skip_csv = True

    t_load = time.perf_counter()
    if skip_csv:
        ticker_payloads = ticker_payloads or {}
        if not games_rows:
            games_rows = list(indexed_games)
        if prebuilt_index is not None:
            perf["rows_scanned"] = sum(len(seq) for seq in prebuilt_index.bars.values())
        if loaded_here and cached_wh is None:
            rq_cache.put_warehouse(
                uh, ds_ver, (ticker_payloads, pbp_by_game, markets_by_ticker, games_rows)
            )
            if prebuilt_index is not None:
                rq_cache.put_index(uh, ds_ver, prebuilt_index)
    elif loaded_here:
        cached_wh = rq_cache.get_warehouse(uh, ds_ver)
        if cached_wh is not None:
            ticker_payloads, pbp_by_game, markets_by_ticker, games_rows = cached_wh
            perf["cache_hit_warehouse"] = True
        else:
            ticker_payloads, pbp_by_game, markets_by_ticker, games_rows = _load_warehouse(cfg, q)
            rq_cache.put_warehouse(
                uh, ds_ver, (ticker_payloads, pbp_by_game, markets_by_ticker, games_rows)
            )
        perf["rows_scanned"] = sum(len(v) for v in ticker_payloads.values())
    ticker_payloads = _clip_ticker_payloads_to_window(
        ticker_payloads or {},
        q.universe.date_from,
        q.universe.date_to,
    )
    if skip_csv:
        ticker_payloads = _apply_ncaab_p5_universe(ticker_payloads, games_rows, q, scopes)
        if prebuilt_index is not None:
            prebuilt_index = TradableIndex(
                bars={t: seq for t, seq in prebuilt_index.bars.items() if t in ticker_payloads},
                skipped={t: n for t, n in prebuilt_index.skipped.items() if t in ticker_payloads},
                basis=prebuilt_index.basis,
            )
    if overlay_on:
        markets_by_ticker, settlement_meta = merge_official_settlement(
            markets_by_ticker or {},
            tickers=(ticker_payloads or {}).keys(),
        )
    perf["dataset_load_ms"] = _ms(t_load)
    stages.append(
        {
            "stage": "universe_loaded",
            "ok": True,
            "tickers": len(ticker_payloads),
            "ms": perf["dataset_load_ms"],
            "cache_hit": perf["cache_hit_warehouse"],
        }
    )

    t_idx = time.perf_counter()
    if prebuilt_index is not None:
        index = prebuilt_index
        index_hit = True
    else:
        index_hit = bool(loaded_here and rq_cache.get_index(uh, ds_ver) is not None)
        index = rq_cache.get_index(uh, ds_ver) if loaded_here else None
        if index is None:
            index = TradableIndex.build(ticker_payloads, basis=q.basis() or BASIS_TRADABLE)
            if loaded_here:
                rq_cache.put_index(uh, ds_ver, index)
    perf["index_build_ms"] = 0 if index_hit else _ms(t_idx)

    universe_tickers = set(ticker_payloads.keys())
    layers: list[tuple[str, str, set[str]]] = []
    per_cond: dict[str, set[str]] = {}
    events_all: list[TouchEvent] = []
    diag_sum: dict[str, int] = defaultdict(int)
    exclusions: dict[str, int] = {k: 0 for k in EXCLUSION_KEYS}
    first_kept: set[str] = set()
    events_by_ticker: dict[str, TouchEvent] = {}

    cached_entry = rq_cache.get_entry(eh, ds_ver) if loaded_here else None
    t_entry = time.perf_counter()
    align_ms = 0
    games_by_id = {str(g.get("internal_game_id") or ""): g for g in games_rows}
    if cached_entry:
        perf["cache_hit_entry"] = True
        identity = cached_entry["identity"]
        funnel = cached_entry["funnel"]
        exclusions = dict(cached_entry["exclusions"])
        events_by_ticker = dict(cached_entry["events_by_ticker"])
        diag_sum = defaultdict(int, cached_entry["diag_sum"])
        first_kept = set(cached_entry["first_kept"])
    else:
        for cond_i, cond in enumerate(q.entry_conditions):
            evs: list[TouchEvent] = []
            for ticker, candles in ticker_payloads.items():
                if not ticker or not candles:
                    if cond_i == 0:
                        exclusions["empty_ticker"] += 1
                    continue
                gid = str((candles[0] if candles else {}).get("internal_game_id") or "")
                sport_i = _scope_sport(candles, games_by_id, scopes, fallback_sport)
                if not sport_i:
                    if cond_i == 0:
                        exclusions["period_unaligned"] += 1
                    continue
                t_snap = time.perf_counter()
                prior = events_by_ticker.get(ticker) if cond_i > 0 else None
                ev, diag = observe_entry(
                    candles,
                    cond,
                    sport=sport_i,
                    snap_fn=snap_fn,
                    pbp_events=(pbp_by_game or {}).get(gid),
                    precomputed=index.precomputed(ticker),
                    prior_event=prior,
                )
                align_ms += _ms(t_snap)
                for k, v in diag.items():
                    if k == "reject_reason":
                        continue
                    if isinstance(v, int):
                        diag_sum[k] += v
                if ev is not None:
                    evs.append(ev)
                elif cond_i == 0:
                    reason = str(diag.get("reject_reason") or "no_nth_touch")
                    if reason in exclusions:
                        exclusions[reason] += 1
                    else:
                        exclusions["no_nth_touch"] += 1
            kept, excluded = same_minute_ties(evs)
            diag_sum["tie_same_minute_excluded"] += excluded
            if cond_i == 0:
                exclusions["tie_same_minute"] += excluded
                events_by_ticker = {e.bar.ticker: e for e in kept}
            kept_tickers = {e.bar.ticker for e in kept}
            if cond_i == 0:
                first_kept = set(kept_tickers)
            per_cond[cond.id] = kept_tickers
            layers.append(
                (cond.id, f"{cond.resolved_operation().value} {cond.price_e4}", kept_tickers)
            )
            events_all.extend(kept)
        identity, funnel = intersect_tickers(layers, universe_n=len(universe_tickers))
        if first_kept:
            exclusions["and_intersection_drop"] = len(first_kept - identity)
        if loaded_here:
            rq_cache.put_entry(
                eh,
                ds_ver,
                {
                    "identity": identity,
                    "funnel": funnel,
                    "exclusions": dict(exclusions),
                    "events_by_ticker": events_by_ticker,
                    "diag_sum": dict(diag_sum),
                    "first_kept": first_kept,
                },
            )
    perf["entry_scan_ms"] = _ms(t_entry)
    perf["pbp_alignment_ms"] = align_ms
    stages.append(
        {
            "stage": "entry_events",
            "ok": True,
            "n": len(first_kept),
            "ms": perf["entry_scan_ms"],
            "cache_hit": perf["cache_hit_entry"],
        }
    )

    if _all_loaded_bars_untradable(q, diag_sum, identity, ticker_payloads or {}, perf):
        from roller.mlb.observability import (
            UNTRADABLE_CANDLES_REASON,
            build_mlb_observability,
        )
        from roller.research_query.sport_family import is_baseball

        mlb_obs = None
        if any(is_baseball(s.sport) or is_baseball(s.league) for s in scopes):
            untradable_ex = {"UNTRADABLE_CANDLES": len(ticker_payloads or {})}
            mlb_obs = build_mlb_observability(
                games=games_rows,
                markets=markets_by_ticker or {},
                pbp_by_game=pbp_by_game or {},
                ticker_payloads=ticker_payloads or {},
                entry_candidates=0,
                pit_aligned=0,
                te_scoped=0,
                classified=0,
                exclusions=untradable_ex,
                observation_basis=q.basis() or BASIS_TRADABLE,
            )
        ident = build_identity(
            universe_tickers=len(universe_tickers),
            exclusions=exclusions,
            entry_eligible=0,
            entry_rows=[],
            terminal=q.terminal,
            reported_n=0,
            path_requested=bool(q.path_conditions),
        )
        return _envelope(
            compiled=compiled,
            execution_status="DATA_REQUIRED",
            rows=None,
            funnel=[s.to_dict() for s in funnel],
            diagnostics=dict(diag_sum),
            message=UNTRADABLE_CANDLES_REASON,
            identity=ident,
            performance=perf,
            stages=stages,
            hashes=hashes,
            dataset_version=ds_ver,
            mlb_observability=mlb_obs,
        )

    t_pop = time.perf_counter()
    exposure_ledger: dict[str, Any] | None = None
    pre_exposure_n = len(identity)
    if exp_contract is not None:
        candidates = [_candidate_from_event(events_by_ticker[t]) for t in identity if t in events_by_ticker]
        decision = enforce_exposure(candidates, exp_contract)
        exposure_ledger = _public_exposure(decision)
        withhold = (
            decision.get("hard_failure")
            or decision.get("status") in {STATUS_CARDINALITY, STATUS_DATA_REQUIRED}
            or int(decision.get("exposure_data_required") or 0) > 0
        )
        if withhold:
            status = (
                "DATA_REQUIRED"
                if decision.get("status") == STATUS_DATA_REQUIRED
                or int(decision.get("exposure_data_required") or 0) > 0
                else "CARDINALITY_VIOLATION"
            )
            ident = build_identity(
                universe_tickers=len(universe_tickers),
                exclusions=exclusions,
                entry_eligible=pre_exposure_n,
                entry_rows=[],
                terminal=q.terminal,
                reported_n=0,
                path_requested=bool(q.path_conditions),
            )
            ident["exposure"] = exposure_ledger
            return _envelope(
                compiled=compiled,
                execution_status=status,
                rows=None,
                funnel=[s.to_dict() for s in funnel],
                diagnostics=dict(diag_sum),
                message=(
                    "EXPOSURE DATA_REQUIRED — missing unit identity. Population withheld. Results did not rewrite N."
                    if status == "DATA_REQUIRED"
                    else "EXPOSURE CARDINALITY_VIOLATION — strategy population withheld. Results did not rewrite N."
                ),
                identity=ident,
                performance=perf,
                stages=stages,
                hashes=hashes,
                dataset_version=ds_ver,
                exposure=exposure_ledger,
            )
        kept = {str(r.get("ticker") or "") for r in decision.get("retained") or []}
        identity = {t for t in identity if t in kept}
        events_by_ticker = {t: ev for t, ev in events_by_ticker.items() if t in kept}
        if exp_contract.max_entries_per_unit is not None:
            seen: dict[str, int] = {}
            for ticker in identity:
                ev = events_by_ticker.get(ticker)
                if ev is None:
                    continue
                key = unit_key(_candidate_from_event(ev), exp_contract.exposure_unit)
                if key is None:
                    continue
                seen[key] = seen.get(key, 0) + 1
            if any(n > int(exp_contract.max_entries_per_unit) for n in seen.values()):
                exposure_ledger = {
                    **exposure_ledger,
                    "status": STATUS_CARDINALITY,
                    "exposure_status": STATUS_CARDINALITY,
                    "hard_failure": True,
                }
                ident = build_identity(
                    universe_tickers=len(universe_tickers),
                    exclusions=exclusions,
                    entry_eligible=pre_exposure_n,
                    entry_rows=[],
                    terminal=q.terminal,
                    reported_n=0,
                    path_requested=bool(q.path_conditions),
                )
                ident["exposure"] = exposure_ledger
                return _envelope(
                    compiled=compiled,
                    execution_status="CARDINALITY_VIOLATION",
                    rows=None,
                    funnel=[s.to_dict() for s in funnel],
                    diagnostics=dict(diag_sum),
                    message="EXPOSURE CARDINALITY_VIOLATION — retained population exceeded MAX_ENTRIES_PER_UNIT. Results did not rewrite N.",
                    identity=ident,
                    performance=perf,
                    stages=stages,
                    hashes=hashes,
                    dataset_version=ds_ver,
                    exposure=exposure_ledger,
                )
        funnel.append(
            FunnelStep(
                condition_id="exposure",
                label=f"EXPOSURE {exp_contract.exposure_unit} max {exp_contract.max_entries_per_unit}",
                qualifying=len(identity),
                population_before=pre_exposure_n,
            )
        )
    perf["population_intersection_ms"] = _ms(t_pop)
    stages.append(
        {
            "stage": "period_filter",
            "ok": True,
            "n": len(identity),
            "ms": perf["population_intersection_ms"],
        }
    )

    t_path = time.perf_counter()
    cached_rows = rq_cache.get_path_rows(eh, path_cache_key, ds_ver) if loaded_here else None
    te_ready = False
    if cached_rows is not None:
        entry_rows = list(cached_rows)
        perf["cache_hit_path"] = True
        te_ready = bool(entry_rows) and all(isinstance(r.get("te"), dict) for r in entry_rows)
    else:
        entry_rows = []
        for ticker in sorted(identity):
            ev = events_by_ticker.get(ticker)
            if ev is None:
                continue
            bars, _ = index.precomputed(ticker)
            candles = ticker_payloads.get(ticker) or []
            sport_i = _scope_sport(candles, games_by_id, scopes, fallback_sport) or fallback_sport
            entry_rows.append(
                _result_row(
                    ev,
                    bars,
                    q,
                    (markets_by_ticker or {}).get(ticker),
                    snap_fn=snap_fn,
                    sport=sport_i,
                    league=_league_of(candles, games_by_id.get(ev.bar.game_id), scopes),
                    season=_season_of(candles, games_by_id.get(ev.bar.game_id), scopes),
                    pbp_events=(pbp_by_game or {}).get(ev.bar.game_id),
                )
            )
        if loaded_here:
            rq_cache.put_path_rows(eh, path_cache_key, ds_ver, entry_rows)
    if not te_ready:
        _attach_base_te(
            entry_rows,
            question=q,
            events_by_ticker=events_by_ticker,
            index=index,
            pbp_by_game=pbp_by_game or {},
            markets_by_ticker=markets_by_ticker or {},
            games_rows=games_rows,
            snap_fn=snap_fn,
            sport=fallback_sport,
            scopes=scopes,
        )
        if loaded_here and entry_rows:
            rq_cache.put_path_rows(eh, path_cache_key, ds_ver, entry_rows)
    before_te = list(entry_rows)
    entry_rows, te_scope = apply_te_population_scope(entry_rows, te_filters)
    te_drop_excl: dict[str, int] | None = None
    if te_scope.get("n_dropped"):
        from roller.mlb.observability import count_te_drops

        kept = {id(r) for r in entry_rows}
        te_drop_excl = count_te_drops([r for r in before_te if id(r) not in kept])
    if te_scope.get("requested"):
        funnel.append(
            FunnelStep(
                condition_id="te_scope",
                label=te_scope_funnel_label(te_scope.get("requested")),
                qualifying=int(te_scope["n_scoped"]),
                population_before=int(te_scope["n_entry"]),
            )
        )
    perf["path_measurement_ms"] = _ms(t_path)
    stages.append(
        {
            "stage": "path",
            "ok": True,
            "n": len(entry_rows),
            "ms": perf["path_measurement_ms"],
        }
    )

    t_agg = time.perf_counter()
    term = q.terminal
    rows = list(entry_rows)
    if not q.tagged_exits():
        if term is TerminalOutcome.YES:
            rows = [r for r in rows if r.get("terminal_yes") is True]
        elif term is TerminalOutcome.NO:
            rows = [r for r in rows if r.get("terminal_yes") is False]
    ident = build_identity(
        universe_tickers=len(universe_tickers),
        exclusions=exclusions,
        entry_eligible=len(identity),
        entry_rows=entry_rows,
        terminal=term,
        reported_n=len(rows),
        path_requested=bool(q.path_conditions),
    )
    ident["te_scope"] = te_scope
    ident["n_entry_events"] = te_scope.get("n_entry")
    ident["league_counts"] = _league_counts(rows)
    if exposure_ledger:
        ident["exposure"] = exposure_ledger
        ident["exposure_unit"] = exposure_ledger.get("exposure_unit")
        ident["max_entries_per_unit"] = exposure_ledger.get("max_entries_per_unit")
        ident["max_entries_per_game"] = exposure_ledger.get("max_entries_per_game")
        ident["pre_exposure_n"] = pre_exposure_n
        ident["raw_entry_candidates"] = exposure_ledger.get("raw_entry_candidates")
    perf["aggregation_ms"] = _ms(t_agg)
    perf["total_ms"] = _ms(t0)
    stages.append(
        {
            "stage": "measurements",
            "ok": True,
            "n": len(rows),
            "ms": perf["aggregation_ms"],
        }
    )

    from roller.base_terminal_efficiency.attach import summarize_rows
    from roller.mlb.observability import build_mlb_observability
    from roller.research_query.sport_family import is_baseball

    te_summary = summarize_rows(rows, te_filters)
    mlb_obs = None
    if any(is_baseball(s.sport) or is_baseball(s.league) for s in scopes):
        pit_ok = sum(
            1
            for r in rows
            if isinstance(r.get("te"), dict) and r["te"].get("alignment_status") not in (None, "UNALIGNED")
        )
        classified = sum(
            1
            for r in rows
            if isinstance(r.get("te"), dict) and r["te"].get("exit_outcome") in ("WIN", "LOSS")
        )
        mlb_obs = build_mlb_observability(
            games=games_rows,
            markets=markets_by_ticker or {},
            pbp_by_game=pbp_by_game or {},
            ticker_payloads=ticker_payloads or {},
            entry_candidates=len(identity),
            pit_aligned=pit_ok,
            te_scoped=int(te_scope.get("n_scoped") or 0),
            classified=classified,
            exclusions=te_drop_excl,
            observation_basis=q.basis() or BASIS_LAST_TRADE,
        )
    env = _envelope(
        compiled=compiled,
        execution_status="COMPLETE",
        rows=rows,
        funnel=[s.to_dict() for s in funnel],
        diagnostics={
            **dict(diag_sum),
            **({"official_settlement": settlement_meta} if settlement_meta else {}),
        },
        identity=ident,
        performance=perf,
        stages=stages,
        hashes=hashes,
        dataset_version=ds_ver,
        te_summary=te_summary,
        mlb_observability=mlb_obs,
        exposure=exposure_ledger,
    )
    if result_key:
        rq_result.put(result_key, env)
    return env


_KALSHI_MON = {
    "JAN": "01",
    "FEB": "02",
    "MAR": "03",
    "APR": "04",
    "MAY": "05",
    "JUN": "06",
    "JUL": "07",
    "AUG": "08",
    "SEP": "09",
    "OCT": "10",
    "NOV": "11",
    "DEC": "12",
}


def _ticker_game_date(ticker: str | None) -> str | None:
    """KXMLBGAME-25APR16ATHCWS-ATH → 2025-04-16. Not a settlement result."""
    parts = str(ticker or "").split("-")
    if len(parts) < 2:
        return None
    token = parts[1]
    if len(token) < 7:
        return None
    yy, mon, dd = token[:2], token[2:5], token[5:7]
    month = _KALSHI_MON.get(mon)
    if month is None or not yy.isdigit() or not dd.isdigit():
        return None
    day_n = int(dd)
    if day_n < 1 or day_n > 31:
        return None
    return f"{2000 + int(yy)}-{month}-{dd}"


def _game_date_token(rec: dict[str, Any]) -> str | None:
    raw = rec.get("game_date")
    if raw not in (None, ""):
        return str(raw)[:10]
    gid = str(rec.get("internal_game_id") or "")
    parts = gid.split("_")
    if len(parts) >= 2 and parts[0] == "MLB" and parts[1].isdigit() and len(parts[1]) == 8:
        day = parts[1]
        return f"{day[:4]}-{day[4:6]}-{day[6:8]}"
    return _ticker_game_date(str(rec.get("ticker") or ""))


def _clip_tradable_index(
    index: TradableIndex,
    date_from: str | None,
    date_to: str | None,
) -> TradableIndex:
    """Drop indexed tickers whose game day is outside the compiled window."""
    if not date_from and not date_to:
        return index
    bars: dict[str, list] = {}
    skipped: dict[str, int] = {}
    for ticker, seq in index.bars.items():
        if not seq:
            continue
        rec = {
            "ticker": ticker,
            "internal_game_id": seq[0].game_id,
            "available_at": seq[0].ts.isoformat().replace("+00:00", "Z"),
        }
        if _in_date_window(rec, date_from, date_to):
            bars[ticker] = seq
            skipped[ticker] = int(index.skipped.get(ticker, 0))
    return TradableIndex(bars=bars, skipped=skipped, basis=index.basis)


def _apply_ncaab_p5_universe(
    ticker_payloads: dict[str, list[dict[str, Any]]],
    games_rows: list[dict[str, Any]],
    question: ResearchQuestion,
    scopes: tuple[LeagueScope, ...],
) -> dict[str, list[dict[str, Any]]]:
    """Same P5 gate as warehouse load. Only NCAAB rows; other leagues stay."""
    if not any(e.names_period("P5") for e in question.entry_conditions):
        return ticker_payloads
    if not any(s.sport == "NCAAB" for s in scopes):
        return ticker_payloads
    p5 = {
        str(game.get("internal_game_id") or game.get("game_id") or "")
        for game in games_rows
        if str(game.get("p5_vs_p5") or "") == "1"
    }
    out: dict[str, list[dict[str, Any]]] = {}
    for ticker, rows in ticker_payloads.items():
        sport = _sport_token((rows[0] if rows else {}).get(RESEARCH_SPORT) or (rows[0] if rows else {}).get("sport"))
        if sport != "NCAAB":
            out[ticker] = rows
            continue
        if any(str(row.get("internal_game_id") or "") in p5 for row in rows):
            out[ticker] = rows
    return out


def _clip_ticker_payloads_to_window(
    ticker_payloads: dict[str, list[dict[str, Any]]],
    date_from: str | None,
    date_to: str | None,
) -> dict[str, list[dict[str, Any]]]:
    """Drop bars whose game day is outside the compiled window. Missing game day uses bar time."""
    if not date_from and not date_to:
        return ticker_payloads
    out: dict[str, list[dict[str, Any]]] = {}
    for ticker, rows in ticker_payloads.items():
        kept = [row for row in rows if _in_date_window(row, date_from, date_to)]
        if kept:
            out[ticker] = kept
    return out


def _in_date_window(rec: dict[str, Any], date_from: str | None, date_to: str | None) -> bool:
    """Game-day window. A known game date outside the range is excluded.

    Do not rescue an out-of-window game with available_at / ingest time.
    LAST TRADE ≠ YES BID. ingested_at is not a game date.
    """
    if not date_from and not date_to:
        return True
    lo = str(date_from)[:10] if date_from else None
    hi = str(date_to)[:10] if date_to else None
    game_day = _game_date_token(rec)
    if game_day:
        return (lo is None or game_day >= lo) and (hi is None or game_day <= hi)
    raw = rec.get("available_at") or rec.get("ts") or rec.get("candle_timestamp") or rec.get("event_timestamp")
    if raw is None:
        return False
    try:
        ts = parse_utc(str(raw))
    except (TypeError, ValueError):
        return False
    if date_from:
        try:
            if ts < parse_utc(str(date_from) if "T" in str(date_from) else f"{date_from}T00:00:00Z"):
                return False
        except (TypeError, ValueError):
            return False
    if date_to:
        try:
            end = str(date_to)
            if "T" not in end:
                end = f"{end}T23:59:59Z"
            if ts > parse_utc(end):
                return False
        except (TypeError, ValueError):
            return False
    return True


def _tag_row(rec: dict[str, Any], scope: LeagueScope) -> dict[str, Any]:
    out = dict(rec)
    out[RESEARCH_SPORT] = scope.sport
    out[RESEARCH_LEAGUE] = scope.league
    out[RESEARCH_SEASON] = scope.season
    return out


def _sport_token(raw: Any) -> str | None:
    if raw in (None, ""):
        return None
    text = str(raw)
    try:
        return sport_from_league(text)
    except ValueError:
        up = text.upper()
        if up in {"NBA", "NCAAB", "WNBA", "MLB", "ATP", "WTA", "TENNIS"}:
            return up
        return None


def _scope_sport(
    candles: list[dict[str, Any]],
    games_by_id: dict[str, dict[str, Any]],
    scopes: tuple[LeagueScope, ...],
    fallback: str,
) -> str | None:
    if candles:
        tagged = _sport_token(candles[0].get(RESEARCH_SPORT) or candles[0].get("sport"))
        if tagged:
            return tagged
        gid = str(candles[0].get("internal_game_id") or "")
        game = games_by_id.get(gid) or {}
        from_game = _sport_token(
            game.get(RESEARCH_SPORT) or game.get("league") or game.get("sport")
        )
        if from_game:
            return from_game
    if len(scopes) == 1:
        return scopes[0].sport
    if len(scopes) == 0:
        return fallback
    return None


def _league_of(
    candles: list[dict[str, Any]],
    game: dict[str, Any] | None,
    scopes: tuple[LeagueScope, ...],
) -> str | None:
    if candles:
        raw = candles[0].get(RESEARCH_LEAGUE) or candles[0].get("league")
        if raw:
            return str(raw)
    if game:
        raw = game.get(RESEARCH_LEAGUE) or game.get("league")
        if raw:
            return str(raw)
    if len(scopes) == 1:
        return scopes[0].league
    return None


def _season_of(
    candles: list[dict[str, Any]],
    game: dict[str, Any] | None,
    scopes: tuple[LeagueScope, ...],
) -> str | None:
    if candles:
        raw = candles[0].get(RESEARCH_SEASON)
        if raw:
            return str(raw)
    if game:
        raw = game.get(RESEARCH_SEASON) or game.get("season")
        if raw:
            return str(raw)
    if len(scopes) == 1:
        return scopes[0].season
    return None


def _record_tour(rec: dict[str, Any]) -> str | None:
    """ATP/WTA identity. Never invent a tour from a foreign ticker."""
    for field in ("league", "sport"):
        token = str(rec.get(field) or "").strip().upper()
        if token in {"ATP", "WTA"}:
            return token
    for field in ("ticker", "internal_game_id", "event_ticker"):
        raw = str(rec.get(field) or "")
        if raw.startswith("KXATPMATCH"):
            return "ATP"
        if raw.startswith("KXWTAMATCH"):
            return "WTA"
    return None


def _scope_keeps_record(rec: dict[str, Any], scope: LeagueScope) -> bool:
    if scope.sport not in {"ATP", "WTA"}:
        return True
    tour = _record_tour(rec)
    if tour is None:
        return False
    return tour == scope.sport or tour == scope.league


def _dataset_path_str(cfg: RollerConfig | None, scope: LeagueScope, name: str) -> str | None:
    if cfg is None:
        return None
    try:
        return str(cfg.dataset_path(scope.sport, scope.season, name))
    except (KeyError, FileNotFoundError):
        return None


def _scopes_share_canonical_tree(cfg: RollerConfig | None, scopes: tuple[LeagueScope, ...]) -> bool:
    if cfg is None or len(scopes) < 2:
        return False
    candle_paths = {_dataset_path_str(cfg, s, "kalshi_candles") for s in scopes}
    if len(candle_paths) != 1 or None in candle_paths:
        return False
    for name in ("pbp", "kalshi_markets", "games", "kalshi_last_trade"):
        paths = {_dataset_path_str(cfg, s, name) for s in scopes}
        paths.discard(None)
        if len(paths) > 1:
            return False
    return True


_SCOPE_TABLES_CACHE: tuple[tuple[str, ...], dict[str, Any]] | None = None


def _read_scope_tables(
    cfg: RollerConfig,
    question: ResearchQuestion,
    scope: LeagueScope,
) -> dict[str, Any]:
    from roller.admin import load_dataset
    from roller.research_query.market_path import candle_dataset_name

    candle_dataset = candle_dataset_name(question)
    date_from = question.universe.date_from
    date_to = question.universe.date_to
    cache_key = (
        str(_dataset_path_str(cfg, scope, candle_dataset) or f"{scope.sport}:{candle_dataset}"),
        str(date_from or ""),
        str(date_to or ""),
        candle_dataset,
    )
    global _SCOPE_TABLES_CACHE
    if _SCOPE_TABLES_CACHE is not None and _SCOPE_TABLES_CACHE[0] == cache_key:
        return _SCOPE_TABLES_CACHE[1]
    tables: dict[str, Any] = {}
    try:
        tables["candles"] = load_dataset(
            cfg, scope.sport, scope.season, candle_dataset, date_from=date_from, date_to=date_to
        )
    except (FileNotFoundError, KeyError):
        tables["candles"] = None
    try:
        tables["pbp"] = load_dataset(
            cfg, scope.sport, scope.season, "pbp", date_from=date_from, date_to=date_to
        )
    except (FileNotFoundError, KeyError):
        tables["pbp"] = None
    try:
        tables["markets"] = load_dataset(cfg, scope.sport, scope.season, "kalshi_markets")
    except (FileNotFoundError, KeyError):
        tables["markets"] = None
    try:
        tables["games"] = load_dataset(cfg, scope.sport, scope.season, "games")
    except (FileNotFoundError, KeyError):
        tables["games"] = None
    _SCOPE_TABLES_CACHE = (cache_key, tables)
    return tables


def _load_one_scope(
    cfg: RollerConfig,
    question: ResearchQuestion,
    scope: LeagueScope,
    tables: dict[str, Any] | None = None,
) -> tuple[
    dict[str, list[dict[str, Any]]],
    dict[str, list[dict[str, Any]]],
    dict[str, dict[str, Any]],
    list[dict[str, Any]],
]:
    last_trade = question.basis() == BASIS_LAST_TRADE
    date_from = question.universe.date_from
    date_to = question.universe.date_to
    if tables is None:
        tables = _read_scope_tables(cfg, question, scope)
    candles = tables.get("candles")
    pbp = tables.get("pbp")
    markets = tables.get("markets")
    games_df = tables.get("games")

    by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    if candles is not None and not candles.empty:
        records = tables.get("candle_records")
        if records is None:
            records = candles.to_dict("records")
            tables["candle_records"] = records
        for rec in records:
            if not _in_date_window(rec, date_from, date_to):
                continue
            if not _scope_keeps_record(rec, scope):
                continue
            ticker = str(rec.get("ticker") or "")
            if not ticker:
                continue
            by_ticker[ticker].append(_tag_row(rec, scope))
    pbp_by: dict[str, list[dict[str, Any]]] = defaultdict(list)
    needed_gids = {
        str(row.get("internal_game_id") or "")
        for rows in by_ticker.values()
        for row in rows
        if row.get("internal_game_id")
    }
    if pbp is not None and not pbp.empty:
        from roller.research_query.entry_engine import order_pbp_events

        for rec in pbp.to_dict("records"):
            gid = str(rec.get("internal_game_id") or "")
            if needed_gids and gid not in needed_gids:
                continue
            pbp_by[gid].append(rec)
        for gid, events in list(pbp_by.items()):
            pbp_by[gid] = order_pbp_events(events)
    mkt: dict[str, dict[str, Any]] = {}
    if markets is not None and not markets.empty:
        for rec in markets.to_dict("records"):
            if not _scope_keeps_record(rec, scope):
                continue
            ticker = str(rec.get("ticker") or "")
            if ticker and ticker not in by_ticker and needed_gids:
                gid = str(rec.get("internal_game_id") or "")
                if gid and gid not in needed_gids:
                    continue
            if ticker:
                mkt[ticker] = rec
    if last_trade and "polymarket" in question.universe.markets:
        by_pm: dict[str, dict[str, Any]] = {}
        for pm_ticker, rows in by_ticker.items():
            kalshi_ticker = next(
                (str(r.get("kalshi_ticker") or "") for r in rows if r.get("kalshi_ticker")),
                "",
            )
            settlement = mkt.get(kalshi_ticker)
            if settlement is not None:
                by_pm[pm_ticker] = settlement
        mkt = by_pm
    games = games_df.to_dict("records") if games_df is not None and not games_df.empty else []
    games = [_tag_row(g, scope) for g in games if _scope_keeps_record(g, scope)]
    if date_from or date_to:
        games = [g for g in games if _in_date_window(g, date_from, date_to)]
    elif needed_gids:
        games = [g for g in games if str(g.get("internal_game_id") or "") in needed_gids]
    if scope.sport == "NCAAB" and any(e.names_period("P5") for e in question.entry_conditions):
        p5 = {str(g.get("internal_game_id") or "") for g in games if str(g.get("p5_vs_p5") or "") == "1"}
        by_ticker = {
            t: rows
            for t, rows in by_ticker.items()
            if any(str(r.get("internal_game_id") or "") in p5 for r in rows)
        }
    return dict(by_ticker), dict(pbp_by), mkt, games


def _union_league_warehouses(
    loaded: list[
        tuple[
            tuple[
                dict[str, list[dict[str, Any]]],
                dict[str, list[dict[str, Any]]],
                dict[str, dict[str, Any]],
                list[dict[str, Any]],
            ],
            LeagueScope,
        ]
    ],
) -> tuple[
    dict[str, list[dict[str, Any]]],
    dict[str, list[dict[str, Any]]],
    dict[str, dict[str, Any]],
    list[dict[str, Any]],
]:
    ticker_owners: dict[str, set[str]] = defaultdict(set)
    game_owners: dict[str, set[str]] = defaultdict(set)
    for (by_t, pbp, _mkt, games), scope in loaded:
        for ticker in by_t:
            if ticker:
                ticker_owners[ticker].add(scope.sport)
        for gid in pbp:
            if gid:
                game_owners[gid].add(scope.sport)
        for game in games:
            gid = str(game.get("internal_game_id") or "")
            if gid:
                game_owners[gid].add(scope.sport)
    collide_t = {t for t, owners in ticker_owners.items() if len(owners) > 1}
    collide_g = {g for g, owners in game_owners.items() if len(owners) > 1}

    def ticker_key(sport: str, ticker: str) -> str:
        return f"{sport}:{ticker}" if ticker in collide_t else ticker

    def game_key(sport: str, gid: str) -> str:
        return f"{sport}:{gid}" if gid in collide_g else gid

    out_t: dict[str, list[dict[str, Any]]] = {}
    out_p: dict[str, list[dict[str, Any]]] = {}
    out_m: dict[str, dict[str, Any]] = {}
    out_g: list[dict[str, Any]] = []
    for (by_t, pbp, mkt, games), scope in loaded:
        for ticker, rows in by_t.items():
            key = ticker_key(scope.sport, ticker)
            tagged: list[dict[str, Any]] = []
            for rec in rows:
                rec = dict(rec)
                gid = str(rec.get("internal_game_id") or "")
                if gid in collide_g:
                    rec["internal_game_id"] = game_key(scope.sport, gid)
                if ticker in collide_t:
                    rec["source_ticker"] = ticker
                    rec["ticker"] = key
                tagged.append(rec)
            out_t[key] = tagged
        for gid, events in pbp.items():
            key = game_key(scope.sport, gid)
            rewritten = []
            for ev in events:
                ev = dict(ev)
                if gid in collide_g:
                    ev["internal_game_id"] = key
                rewritten.append(ev)
            out_p[key] = rewritten
        for ticker, rec in mkt.items():
            key = ticker_key(scope.sport, ticker)
            rec = dict(rec)
            if ticker in collide_t:
                rec["source_ticker"] = ticker
                rec["ticker"] = key
            out_m[key] = rec
        for game in games:
            game = dict(game)
            gid = str(game.get("internal_game_id") or "")
            if gid in collide_g:
                game["internal_game_id"] = game_key(scope.sport, gid)
            out_g.append(game)
    return out_t, out_p, out_m, out_g


def _load_warehouse(
    cfg: RollerConfig,
    question: ResearchQuestion,
) -> tuple[
    dict[str, list[dict[str, Any]]],
    dict[str, list[dict[str, Any]]],
    dict[str, dict[str, Any]],
    list[dict[str, Any]],
]:
    scopes = resolve_league_scopes(question.universe)
    if not scopes:
        return {}, {}, {}, []
    shared = _read_scope_tables(cfg, question, scopes[0]) if _scopes_share_canonical_tree(cfg, scopes) else None
    loaded = [(_load_one_scope(cfg, question, scope, tables=shared), scope) for scope in scopes]
    if len(loaded) == 1:
        return loaded[0][0]
    return _union_league_warehouses(loaded)


def execute_question(
    payload: dict[str, Any],
    *,
    cfg: RollerConfig | None = None,
    ticker_payloads: dict[str, list[dict[str, Any]]] | None = None,
    pbp_by_game: dict[str, list[dict[str, Any]]] | None = None,
    markets_by_ticker: dict[str, dict[str, Any]] | None = None,
    snap_fn: Callable | None = None,
) -> dict[str, Any]:
    """Authoritative execute. Ignores client execution_path / status / reference_match."""
    payload = dict(payload)
    payload.pop("execution_path", None)
    payload.pop("reference_match", None)
    payload.pop("status", None)
    draft = payload.get("draft") if isinstance(payload.get("draft"), dict) else payload
    te_filters = None
    exp_mode, exp_unit, exp_max = MODE_VERIFY_ONLY, None, None
    if isinstance(draft, dict):
        te_filters = draft.get("teFilters") or draft.get("te_filters")
        exp_mode, exp_unit, exp_max = enforcement_request_from_draft(draft)
    if "universe" in payload and "entry_conditions" in payload:
        q = ResearchQuestion.from_dict(payload)
        compiled = compile_question(q, cfg=cfg)
    elif "question" in payload:
        q = ResearchQuestion.from_dict(payload["question"])
        compiled = compile_question(q, cfg=cfg, draft=payload.get("draft"))
    else:
        compiled = compile_draft(payload.get("draft") or payload, cfg=cfg)
    return execute_compiled(
        compiled,
        cfg=cfg,
        ticker_payloads=ticker_payloads,
        pbp_by_game=pbp_by_game,
        markets_by_ticker=markets_by_ticker,
        snap_fn=snap_fn,
        te_filters=te_filters if isinstance(te_filters, dict) else None,
        exposure_enforcement_mode=exp_mode,
        exposure_unit=exp_unit,
        max_entries_per_unit=exp_max,
    )


def _attach_base_te(
    rows: list[dict[str, Any]],
    *,
    question: ResearchQuestion,
    events_by_ticker: dict[str, TouchEvent],
    index: TradableIndex,
    pbp_by_game: dict[str, list[dict[str, Any]]],
    markets_by_ticker: dict[str, dict[str, Any]],
    games_rows: list[dict[str, Any]],
    snap_fn: Callable | None,
    sport: str,
    scopes: tuple[LeagueScope, ...] = (),
) -> None:
    if not rows:
        return
    from roller.base_terminal_efficiency.attach import attach_to_row

    games_by_id = {str(g.get("internal_game_id") or ""): g for g in games_rows}
    default_league = scopes[0].league if len(scopes) == 1 else (
        question.universe.leagues[0] if question.universe.leagues else None
    )
    default_season = scopes[0].season if len(scopes) == 1 else (
        question.universe.seasons[0] if question.universe.seasons else None
    )
    for row in rows:
        if isinstance(row.get("te"), dict) and row["te"].get("observation_ts"):
            continue
        ev = events_by_ticker.get(str(row.get("ticker") or ""))
        if ev is None:
            continue
        bars, _ = index.precomputed(ev.bar.ticker)
        sport_i = str(row.get("sport") or sport)
        league_i = row.get("league") or default_league
        season_i = row.get("warehouse_season") or default_season
        attach_to_row(
            row,
            entry=ev,
            bars=bars,
            question=question,
            pbp_events=pbp_by_game.get(ev.bar.game_id),
            game=games_by_id.get(ev.bar.game_id),
            market=markets_by_ticker.get(ev.bar.ticker),
            snap_fn=snap_fn,
            sport=sport_i,
            league=str(league_i) if league_i else None,
            season=str(season_i) if season_i else None,
        )
