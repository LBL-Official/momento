"""Run SuperASI B — Debase against one Phase A folder."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from roller import desk_settings
from roller.config import RollerConfig
from roller.labs.schema import sanitize_name
from roller.superasi.base.observed import (
    BAD_CLASS,
    BAD_SETTLE,
    is_win_hold,
    summarize_observed,
    trade_outcome,
)
from roller.superasi.base.roller_desk import (
    compute_roller_desk,
    inspect_risk_profile_from_desk,
    instrument_from_composition,
)
from roller.superasi.debase.degrading import run_degrading
from roller.superasi.debase.devalidation import collect_checks, comparison_rows, disagreement_rows
from roller.superasi.debase.ingest import extract_entry, load_phase_a_folder
from roller.superasi.debase.iqr import working_p_from_observed
from roller.superasi.debase.rr import plan_prices, report_rr
from roller.superasi.debase.simulation import (
    attach_standard_errors,
    run_bernoulli,
    run_empirical,
    sensitivity_monte_carlo,
    simulate_weekly_bootstrap,
)
from roller.superasi.debase.store import save_debase_result
from roller.superasi.debase.valuation import (
    ev_at_p,
    observed_ev,
    observed_weeks,
    payoff_from_roller,
    reconcile_header_ev,
    sensitivity_theoretical,
    theoretical_at_p,
)
from roller.superasi.debase.versions import DEBASE_DESK_NOTE, DEBASE_MC_NOTE, DESK_PATHS, P_WORKING_BASIS
from roller.superasi.models import SuperasiError


def _opt_float(raw: object) -> float | None:
    if raw in (None, ""):
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _p_worst(
    trades: list[dict[str, str]], wins: int, losses: int, *, win_hold: bool = False
) -> float | None:
    extra = 0
    for row in trades:
        klass = str(row.get("classification") or "").strip()
        settle = str(row.get("settlement_status") or "").strip()
        bad = klass in BAD_CLASS or settle in BAD_SETTLE
        if bad and trade_outcome(row, win_hold=win_hold) is None:
            extra += 1
    denom = wins + losses + extra
    if denom <= 0:
        return None
    return wins / float(denom)


def run_debase(
    *,
    result_id: str,
    cfg: RollerConfig | None = None,
    monte_carlo_paths: int = DESK_PATHS,
) -> dict[str, Any]:
    bundle = load_phase_a_folder(result_id, cfg=cfg)
    parsed = bundle["parsed_roller"]
    observed = summarize_observed(parsed)
    win_hold = is_win_hold(parsed)
    average_win = observed.get("average_win")
    average_loss = observed.get("average_loss")
    levels = desk_settings.scaled_levels(cfg=cfg)
    desk_public = desk_settings.public_settings(cfg=cfg)
    desk_stamp = desk_settings.stamp(cfg=cfg)
    entry = extract_entry(parsed)
    prices = plan_prices(parsed)
    win_exit = prices.get("win_exit")
    loss_exit = prices.get("loss_exit")
    if win_exit is None and entry is not None and average_win is not None:
        win_exit = float(entry) + float(average_win)
    if loss_exit is None and entry is not None and average_loss is not None:
        loss_exit = float(entry) - float(average_loss)
    payoff = payoff_from_roller(
        average_win=average_win,
        average_loss=average_loss,
        entry=entry,
        allocation=float(levels["trade_allocation"]),
    )
    rr_block = report_rr(parsed, plan_entry=entry, plan_win=win_exit, plan_loss=loss_exit)
    payoff = {**payoff, **rr_block}
    wins = int(observed.get("wins") or 0)
    losses = int(observed.get("losses") or 0)
    population = int(observed.get("population") or 0)
    recomputed = observed_ev(
        wins=wins,
        losses=losses,
        population=population,
        average_win=float(average_win),
        average_loss=float(average_loss),
        trades=list(parsed.get("trade_rows") or []),
        entry=entry,
        win_exit=win_exit,
        loss_exit=loss_exit,
        win_hold=win_hold,
    )
    reconcile_header_ev(header_ev=observed.get("gross_ev"), recomputed=recomputed)
    hinges = working_p_from_observed(observed)
    p_working = float(hinges["p_working"])
    ev_debase = ev_at_p(p=p_working, average_win=float(average_win), average_loss=float(average_loss))
    p_worst = _p_worst(list(parsed.get("trade_rows") or []), wins, losses, win_hold=win_hold)
    observed = {
        **observed,
        **hinges,
        "p_working": p_working,
        "p_working_basis": P_WORKING_BASIS,
        "ev_debase": ev_debase,
        "ev_recomputed": recomputed,
        "p_be_roller": payoff["p_be"],
        "p_worst": p_worst,
        "entry": entry,
        "risk_reward": rr_block.get("risk_reward"),
        "risk_reward_plan": rr_block.get("risk_reward_plan"),
        "risk_reward_trade_mean": rr_block.get("risk_reward_trade_mean"),
        "risk_reward_display": rr_block.get("risk_reward_display"),
        "risk_reward_basis": rr_block.get("risk_reward_basis"),
        "risk_reward_methods_disagree": rr_block.get("risk_reward_methods_disagree"),
    }
    theoretical = theoretical_at_p(payoff, p_working, desk=levels)
    week_block = observed_weeks(list(parsed.get("trade_rows") or []), payoff, win_hold=win_hold)
    outcomes = [
        trade_outcome(row, win_hold=win_hold) or str(row.get("classification") or "")
        for row in parsed.get("trade_rows") or []
    ]
    research_hash = str(observed.get("result_hash") or "")
    bernoulli = attach_standard_errors(
        run_bernoulli(
            payoff,
            p=p_working,
            research_result_hash=research_hash,
            paths=monte_carlo_paths,
            desk=levels,
        )
    )
    empirical = None
    if any(item in {"WIN", "LOSS"} for item in outcomes):
        empirical = attach_standard_errors(
            run_empirical(
                payoff,
                outcomes,
                research_result_hash=research_hash,
                paths=monte_carlo_paths,
                p=p_working,
                desk=levels,
            )
        )
    weekly_bs = simulate_weekly_bootstrap(
        list(week_block.get("weekly_returns") or []),
        paths=monte_carlo_paths,
        desk=levels,
    )
    mc = bernoulli.get("monte_carlo") if isinstance(bernoulli.get("monte_carlo"), dict) else {}
    probs = mc.get("probabilities") if isinstance(mc.get("probabilities"), dict) else {}
    ret = mc.get("annual_return") if isinstance(mc.get("annual_return"), dict) else {}
    expected_20 = ret.get("mean")
    p_floor = probs.get("P_min_bankroll_le_floor")
    checks = collect_checks(parsed_roller=parsed, observed=observed, bundle=bundle)
    roller_desk = compute_roller_desk(parsed, observed, cfg=cfg, p_used=p_working)
    roller_desk = {**roller_desk, "note": DEBASE_DESK_NOTE, "p_basis": P_WORKING_BASIS}
    roller_risk = inspect_risk_profile_from_desk(
        roller_desk,
        research_result_hash=research_hash,
        monte_carlo_paths=monte_carlo_paths,
        cfg=cfg,
        public=desk_public,
    )
    roller_risk = {**roller_risk, "note": DEBASE_MC_NOTE, "p_basis": P_WORKING_BASIS}
    degrading = run_degrading(
        observed=observed,
        checks=checks,
        ev_debase=ev_debase,
        p_working=p_working,
        base_grade=str(bundle.get("BASE_GRADE") or ""),
        phase_a_components=dict(bundle.get("phase_a_components") or {}),
        expected_20_week_return=float(expected_20) if expected_20 is not None else None,
        p_floor=float(p_floor) if p_floor is not None else None,
    )
    comparison = comparison_rows(
        observed=observed,
        theoretical=theoretical,
        bernoulli=bernoulli,
        empirical=empirical,
    )
    disagreements = disagreement_rows(comparison)
    grid_theory = {row["p"]: row for row in sensitivity_theoretical(payoff, desk=levels)}
    grid_mc = sensitivity_monte_carlo(payoff, paths=monte_carlo_paths, desk=levels)
    sensitivity = []
    for row in grid_mc:
        merged = dict(grid_theory.get(row["p"]) or {})
        merged.update(row)
        sensitivity.append(merged)
    stress_ev = ev_at_p(p=p_worst, average_win=float(average_win), average_loss=float(average_loss)) if p_worst is not None else None
    strategy = sanitize_name(str(bundle.get("strategy_name") or "Untitled"))
    payload = {
        "strategy_name": strategy,
        "source_lab_id": bundle.get("source_lab_id"),
        "phase_a_result_id": bundle.get("result_id"),
        "source_csv_sha256": bundle.get("source_csv_sha256"),
        "abase_sha256": bundle.get("abase_sha256"),
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "meta": parsed["meta"],
        "observed": observed,
        "payoff": payoff,
        "theoretical": theoretical,
        "observed_weeks": week_block,
        "bernoulli": bernoulli,
        "empirical": empirical or {},
        "weekly_bootstrap": weekly_bs,
        "sensitivity": sensitivity,
        "stress": {"p_worst": p_worst, "ev_at_p_worst": stress_ev},
        "degrading": degrading,
        "checks": checks,
        "comparison": comparison,
        "disagreements": disagreements,
        "question": bundle.get("question"),
        "question_status": bundle.get("question_status"),
        "question_sha256": bundle.get("question_sha256"),
        "desk_break_even": bundle.get("desk_break_even"),
        "desk_trade_ev": bundle.get("desk_trade_ev"),
        "desk_weekly_ev": bundle.get("desk_weekly_ev"),
        "roller_desk": roller_desk,
        "roller_risk_profile": roller_risk,
        "desk_settings": desk_public,
        **desk_stamp,
    }
    saved = save_debase_result(
        payload=payload,
        roller_bytes=bundle["roller_bytes"],
        roller_filename=str(bundle["roller_filename"]),
        abase_bytes=bundle["abase_bytes"],
        abase_filename=str(bundle["abase_filename"]),
        cfg=cfg,
    )
    inspect = {
        "result_id": saved["result_id"],
        "strategy_name": strategy,
        "source_lab_id": bundle.get("source_lab_id"),
        "phase_a_result_id": bundle.get("result_id"),
        "created_at": saved["created_at"],
        "BASE_GRADE": degrading.get("BASE_GRADE"),
        "DEBASE_GRADE": degrading.get("DEBASE_GRADE"),
        "components": degrading.get("components"),
        "bottleneck": degrading.get("bottleneck"),
        "raise_requires": degrading.get("raise_requires"),
        "composite_score": degrading.get("composite_score"),
        "borderline": degrading.get("borderline"),
        "capped_to_base": degrading.get("capped_to_base"),
        "DEBASE_GRADE_uncapped": degrading.get("DEBASE_GRADE_uncapped"),
        "desk": roller_desk,
        "instrument": instrument_from_composition(
            {
                "mode": "A",
                "deterministic": {
                    "break_even_probability": _opt_float(bundle.get("desk_break_even")),
                    "trade_ev": _opt_float(bundle.get("desk_trade_ev")),
                    "weekly_ev": _opt_float(bundle.get("desk_weekly_ev")),
                    "required_win_probability": 0.70,
                },
            }
        ),
        "p_working": p_working,
        "p_working_basis": P_WORKING_BASIS,
        "p_iqr1": hinges["p_iqr1"],
        "p_iqr3": hinges["p_iqr3"],
        "p_be_roller": payoff["p_be"],
        "ev_debase": ev_debase,
        "gross_ev": observed.get("gross_ev"),
        "risk_reward": rr_block.get("risk_reward"),
        "risk_reward_plan": rr_block.get("risk_reward_plan"),
        "risk_reward_trade_mean": rr_block.get("risk_reward_trade_mean"),
        "risk_reward_display": rr_block.get("risk_reward_display"),
        "risk_reward_basis": rr_block.get("risk_reward_basis"),
        "risk_reward_methods_disagree": rr_block.get("risk_reward_methods_disagree"),
        "risk_reward_ratio_of_means": rr_block.get("risk_reward_ratio_of_means"),
        "desk_settings": desk_public,
        "instrument_gate": degrading.get("instrument_gate"),
        "observed": {
            "population": observed.get("population"),
            "wins": wins,
            "losses": losses,
            "win_rate": observed.get("win_rate"),
            "wilson_lower": observed.get("wilson_lower"),
            "wilson_upper": observed.get("wilson_upper"),
            "p_iqr1": hinges["p_iqr1"],
            "p_iqr3": hinges["p_iqr3"],
        },
        "valuation": {
            "R_w": payoff.get("R_w"),
            "R_l": payoff.get("R_l"),
            "weekly_ev": theoretical.get("weekly_ev"),
            "compounded_20_week": theoretical.get("compounded_20_week"),
            "weekly_table": theoretical.get("weekly_table") or [],
            "sensitivity": [
                {
                    "p": item.get("p"),
                    "weekly_ev": item.get("weekly_ev"),
                    "P_min_bankroll_le_floor": item.get("P_min_bankroll_le_floor"),
                    "P_final_ge_target": item.get("P_final_ge_target"),
                }
                for item in sensitivity
            ],
        },
        "risk_profile": roller_risk,
        "question_status": bundle.get("question_status"),
        "checks": checks,
        "honesty": {
            "risk_not": "candle_path_not_fill",
            "live_grade": "UNAVAILABLE",
            "fees": "UNAVAILABLE",
            "fills": "UNAVAILABLE",
            "net_ev": "NOT_COMPUTABLE",
        },
        "files": {
            "roller_filename": saved["roller_filename"],
            "abase_filename": saved["abase_filename"],
            "debase_filename": saved["debase_filename"],
            "debase_sha256": saved["debase_sha256"],
            "abase_sha256": saved["abase_sha256"],
            "source_csv_sha256": saved["source_csv_sha256"],
        },
    }
    return {**saved, "inspect": inspect}
