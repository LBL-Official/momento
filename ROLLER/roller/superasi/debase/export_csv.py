"""Canonical SuperasiBDeBase CSV. Long-format metrics + Roller metadata."""

from __future__ import annotations

import csv
import io
from typing import Any

from roller.labs.schema import cell
from roller.superasi.base.ingest import ROLLER_META
from roller.superasi.debase.versions import (
    GRADE_CONFIG_VERSION,
    HONESTY,
    SUPERASI_DEBASE_VERSION,
)

SUPERASI_COLUMNS: tuple[str, ...] = (
    "record_type",
    "evidence_layer",
    "program",
    "metric",
    "value",
    "unit",
    "source",
    "superasi_version",
    "grade_config_version",
    "created_at",
    "source_lab_id",
    "phase_a_result_id",
    "source_csv_sha256",
    "abase_sha256",
    "debase_sha256",
    *ROLLER_META,
    "risk_not",
    "fees",
    "slippage",
    "fills",
    "net_ev",
    "live_grade",
)


def csv_filename(strategy_name: str) -> str:
    return f"SuperasiBDeBase[{strategy_name}].csv"


def _row(
    *,
    record_type: str,
    evidence_layer: str,
    program: str,
    metric: str,
    value: object,
    unit: str,
    source: str,
    ctx: dict[str, str],
) -> dict[str, str]:
    out = {col: "" for col in SUPERASI_COLUMNS}
    out.update(ctx)
    out.update(
        {
            "record_type": record_type,
            "evidence_layer": evidence_layer,
            "program": program,
            "metric": metric,
            "value": cell(value),
            "unit": unit,
            "source": source,
        }
    )
    return out


def _ctx(payload: dict[str, Any], *, debase_hash: str = "") -> dict[str, str]:
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    ctx = {col: str(meta.get(col) or "") for col in ROLLER_META}
    ctx.update(
        {
            "superasi_version": SUPERASI_DEBASE_VERSION,
            "grade_config_version": GRADE_CONFIG_VERSION,
            "created_at": str(payload.get("created_at") or ""),
            "source_lab_id": str(payload.get("source_lab_id") or ""),
            "phase_a_result_id": str(payload.get("phase_a_result_id") or ""),
            "source_csv_sha256": str(payload.get("source_csv_sha256") or ""),
            "abase_sha256": str(payload.get("abase_sha256") or ""),
            "debase_sha256": debase_hash,
            **HONESTY,
        }
    )
    return ctx


def render_rows(payload: dict[str, Any], *, debase_hash: str = "") -> list[dict[str, str]]:
    observed = payload.get("observed") if isinstance(payload.get("observed"), dict) else {}
    payoff = payload.get("payoff") if isinstance(payload.get("payoff"), dict) else {}
    theoretical = payload.get("theoretical") if isinstance(payload.get("theoretical"), dict) else {}
    degrading = payload.get("degrading") if isinstance(payload.get("degrading"), dict) else {}
    checks = payload.get("checks") if isinstance(payload.get("checks"), list) else []
    comparison = payload.get("comparison") if isinstance(payload.get("comparison"), list) else []
    disagreements = payload.get("disagreements") if isinstance(payload.get("disagreements"), list) else []
    weeks = payload.get("observed_weeks") if isinstance(payload.get("observed_weeks"), dict) else {}
    bernoulli = payload.get("bernoulli") if isinstance(payload.get("bernoulli"), dict) else {}
    empirical = payload.get("empirical") if isinstance(payload.get("empirical"), dict) else {}
    weekly_bs = payload.get("weekly_bootstrap") if isinstance(payload.get("weekly_bootstrap"), dict) else {}
    sensitivity = payload.get("sensitivity") if isinstance(payload.get("sensitivity"), list) else []
    stress = payload.get("stress") if isinstance(payload.get("stress"), dict) else {}
    ctx = _ctx(payload, debase_hash=debase_hash)
    out: list[dict[str, str]] = []
    add = out.append

    add(_row(record_type="meta", evidence_layer="", program="base_devalidation", metric="superasi_version", value=SUPERASI_DEBASE_VERSION, unit="", source="superasi", ctx=ctx))
    add(_row(record_type="meta", evidence_layer="", program="base_devalidation", metric="grade_config_version", value=GRADE_CONFIG_VERSION, unit="", source="superasi", ctx=ctx))
    add(_row(record_type="meta", evidence_layer="OBSERVED", program="base_devalidation", metric="phase_a_result_id", value=payload.get("phase_a_result_id"), unit="", source="phase_a", ctx=ctx))
    add(_row(record_type="meta", evidence_layer="OBSERVED", program="base_devalidation", metric="source_lab_id", value=payload.get("source_lab_id"), unit="", source="labs_csv", ctx=ctx))
    add(_row(record_type="meta", evidence_layer="OBSERVED", program="base_devalidation", metric="question_status", value=payload.get("question_status"), unit="", source="labs_metadata", ctx=ctx))
    add(_row(record_type="meta", evidence_layer="OBSERVED", program="base_devalidation", metric="question_sha256", value=payload.get("question_sha256"), unit="", source="labs_metadata", ctx=ctx))
    add(_row(record_type="meta", evidence_layer="OBSERVED", program="base_devalidation", metric="plan_hash", value=observed.get("plan_hash"), unit="", source="labs_csv", ctx=ctx))
    add(_row(record_type="meta", evidence_layer="OBSERVED", program="base_devalidation", metric="result_hash", value=observed.get("result_hash"), unit="", source="labs_csv", ctx=ctx))
    add(_row(record_type="meta", evidence_layer="OBSERVED", program="base_devalidation", metric="candle_path_not_fill", value=HONESTY["risk_not"], unit="", source="honesty", ctx=ctx))
    add(_row(record_type="meta", evidence_layer="OBSERVED", program="base_devalidation", metric="live_grade", value=HONESTY["live_grade"], unit="", source="honesty", ctx=ctx))

    for key, unit in (
        ("population", "count"),
        ("wins", "count"),
        ("losses", "count"),
        ("decided", "count"),
        ("win_rate", "fraction"),
        ("gross_ev", "e4"),
        ("average_win", "e4"),
        ("average_loss", "e4"),
        ("risk_reward", "ratio"),
        ("wilson_lower", "fraction"),
        ("wilson_upper", "fraction"),
        ("wilson_width", "fraction"),
        ("p_working", "fraction"),
        ("p_working_basis", ""),
        ("p_iqr1", "fraction"),
        ("p_iqr3", "fraction"),
        ("iqr", "fraction"),
        ("ev_debase", "e4"),
        ("ev_recomputed", "e4"),
        ("p_be_roller", "fraction"),
        ("p_worst", "fraction"),
        ("decided_rate", "fraction"),
        ("bad_settle_rate", "fraction"),
        ("risk_reward_plan", "ratio"),
        ("risk_reward_trade_mean", "ratio"),
        ("risk_reward_display", ""),
        ("risk_reward_basis", ""),
        ("risk_reward_methods_disagree", ""),
    ):
        add(_row(record_type="observed", evidence_layer="OBSERVED", program="base_decomposition", metric=key, value=observed.get(key), unit=unit, source="labs_row", ctx=ctx))

    for key, unit in (
        ("entry", "e4"),
        ("win_return_on_capital", "fraction"),
        ("loss_return_on_capital", "fraction"),
        ("R_w", "fraction"),
        ("R_l", "fraction"),
        ("p_be", "fraction"),
        ("risk_reward", "ratio"),
        ("risk_reward_plan", "ratio"),
        ("risk_reward_trade_mean", "ratio"),
        ("risk_reward_ratio_of_means", "ratio"),
        ("risk_reward_display", ""),
        ("allocation_rate", "fraction"),
    ):
        add(_row(record_type="decomposition", evidence_layer="THEORETICAL", program="base_decomposition", metric=key, value=payoff.get(key), unit=unit, source="roller_payoff", ctx=ctx))

    for key, unit in (
        ("p", "fraction"),
        ("trade_ev_bankroll", "fraction"),
        ("weekly_ev", "fraction"),
        ("required_p_for_target_week", "fraction"),
        ("arithmetic_20_week", "fraction"),
        ("compounded_20_week", "fraction"),
        ("compounded_terminal", "usd"),
    ):
        add(_row(record_type="decomposition", evidence_layer="THEORETICAL", program="base_decomposition", metric=key, value=theoretical.get(key), unit=unit, source="roller_payoff", ctx=ctx))

    add(_row(record_type="decomposition", evidence_layer="THEORETICAL", program="base_decomposition", metric="desk_break_even_probability", value=payload.get("desk_break_even"), unit="fraction", source="superasi_abase", ctx=ctx))
    add(_row(record_type="decomposition", evidence_layer="THEORETICAL", program="base_decomposition", metric="desk_trade_ev", value=payload.get("desk_trade_ev"), unit="fraction", source="superasi_abase", ctx=ctx))
    add(_row(record_type="decomposition", evidence_layer="THEORETICAL", program="base_decomposition", metric="desk_weekly_ev", value=payload.get("desk_weekly_ev"), unit="fraction", source="superasi_abase", ctx=ctx))
    roller_desk = payload.get("roller_desk") if isinstance(payload.get("roller_desk"), dict) else {}
    for key, src_key in (
        ("roller_break_even_probability", "break_even_probability"),
        ("roller_trade_ev", "trade_ev"),
        ("roller_weekly_ev", "weekly_ev"),
        ("roller_required_win_probability", "required_win_probability"),
        ("roller_p_used", "p_used"),
    ):
        add(
            _row(
                record_type="decomposition",
                evidence_layer="THEORETICAL",
                program="base_decomposition",
                metric=key,
                value=roller_desk.get(src_key),
                unit="fraction",
                source="roller_payoff",
                ctx=ctx,
            )
        )
    roller_risk = payload.get("roller_risk_profile") if isinstance(payload.get("roller_risk_profile"), dict) else {}
    add(_row(record_type="risk_profile", evidence_layer="MONTE_CARLO", program="base_decomposition", metric="roller_horizon_weeks", value=roller_risk.get("weeks"), unit="week", source="roller_payoff", ctx=ctx))
    add(_row(record_type="risk_profile", evidence_layer="MONTE_CARLO", program="base_decomposition", metric="roller_paths", value=roller_risk.get("paths"), unit="count", source="roller_payoff", ctx=ctx))
    add(_row(record_type="risk_profile", evidence_layer="MONTE_CARLO", program="base_decomposition", metric="roller_P_min_bankroll_le_floor", value=roller_risk.get("P_min_bankroll_le_floor"), unit="fraction", source="roller_payoff", ctx=ctx))
    add(_row(record_type="risk_profile", evidence_layer="MONTE_CARLO", program="base_decomposition", metric="roller_P_final_ge_target", value=roller_risk.get("P_final_ge_target"), unit="fraction", source="roller_payoff", ctx=ctx))
    add(_row(record_type="risk_profile", evidence_layer="MONTE_CARLO", program="base_decomposition", metric="roller_mean_terminal_bankroll", value=roller_risk.get("mean_terminal_bankroll"), unit="usd", source="roller_payoff", ctx=ctx))
    add(_row(record_type="risk_profile", evidence_layer="MONTE_CARLO", program="base_decomposition", metric="roller_p_used", value=roller_risk.get("p_used"), unit="fraction", source="roller_payoff", ctx=ctx))
    desk = payload.get("desk_settings") if isinstance(payload.get("desk_settings"), dict) else {}
    for key, unit in (
        ("bankroll_cents", "usd_cents"),
        ("allocation_bps", "bps"),
        ("floor_cents", "usd_cents"),
        ("target_cents", "usd_cents"),
    ):
        add(_row(record_type="meta", evidence_layer="THEORETICAL", program="base_decomposition", metric=key, value=desk.get(key, payload.get(key)), unit=unit, source="desk_settings", ctx=ctx))

    table = theoretical.get("weekly_table") if isinstance(theoretical.get("weekly_table"), list) else []
    for item in table:
        if not isinstance(item, dict):
            continue
        add(_row(record_type="weekly", evidence_layer="THEORETICAL", program="base_decomposition", metric=f"wins_{item.get('wins')}", value=item.get("weekly_return"), unit="fraction", source="binomial_roller_payoff", ctx=ctx))
        add(_row(record_type="weekly", evidence_layer="THEORETICAL", program="base_decomposition", metric=f"wins_{item.get('wins')}_probability", value=item.get("probability"), unit="fraction", source="binomial_roller_payoff", ctx=ctx))

    add(_row(record_type="weekly_observed", evidence_layer="OBSERVED", program="base_decomposition", metric="status", value=weeks.get("status"), unit="", source="iso_week", ctx=ctx))
    add(_row(record_type="weekly_observed", evidence_layer="OBSERVED", program="base_decomposition", metric="observed_weekly_return_mean", value=weeks.get("observed_weekly_return_mean"), unit="fraction", source="iso_week", ctx=ctx))
    for item in weeks.get("weeks") or []:
        if not isinstance(item, dict):
            continue
        add(_row(record_type="weekly_observed", evidence_layer="OBSERVED", program="base_decomposition", metric=str(item.get("week_id") or ""), value=item.get("weekly_return"), unit="fraction", source="iso_week", ctx=ctx))

    add(_row(record_type="grading", evidence_layer="OBSERVED", program="base_degrading", metric="BASE_GRADE", value=degrading.get("BASE_GRADE"), unit="letter", source="superasi_abase", ctx=ctx))
    phase_a_components = degrading.get("phase_a_components") if isinstance(degrading.get("phase_a_components"), dict) else {}
    for name, letter in phase_a_components.items():
        add(_row(record_type="grading", evidence_layer="OBSERVED", program="base_degrading", metric=f"phase_a_{name}_grade", value=letter, unit="letter", source="superasi_abase", ctx=ctx))

    add(_row(record_type="degrading", evidence_layer="OBSERVED", program="base_degrading", metric="DEBASE_GRADE", value=degrading.get("DEBASE_GRADE"), unit="letter", source="grade_config_v1", ctx=ctx))
    add(_row(record_type="degrading", evidence_layer="OBSERVED", program="base_degrading", metric="DEBASE_GRADE_uncapped", value=degrading.get("DEBASE_GRADE_uncapped"), unit="letter", source="grade_config_v1", ctx=ctx))
    add(_row(record_type="degrading", evidence_layer="OBSERVED", program="base_degrading", metric="capped_to_base", value=degrading.get("capped_to_base"), unit="", source="grade_config_v1", ctx=ctx))
    add(_row(record_type="degrading", evidence_layer="OBSERVED", program="base_degrading", metric="composite_score", value=degrading.get("composite_score"), unit="score", source="grade_config_v1", ctx=ctx))
    add(_row(record_type="degrading", evidence_layer="OBSERVED", program="base_degrading", metric="bottleneck", value=degrading.get("bottleneck"), unit="letter", source="grade_config_v1", ctx=ctx))
    add(_row(record_type="degrading", evidence_layer="OBSERVED", program="base_degrading", metric="raise_requires", value=degrading.get("raise_requires"), unit="", source="grade_config_v1", ctx=ctx))
    components = degrading.get("components") if isinstance(degrading.get("components"), dict) else {}
    for name, letter in components.items():
        add(_row(record_type="degrading", evidence_layer="OBSERVED", program="base_degrading", metric=f"{name}_grade", value=letter, unit="letter", source="grade_config_v1", ctx=ctx))
    gate = degrading.get("instrument_gate") if isinstance(degrading.get("instrument_gate"), dict) else {}
    add(_row(record_type="degrading", evidence_layer="MONTE_CARLO", program="base_degrading", metric="A_PLUS_INSTRUMENT_GATE", value=gate.get("value"), unit="", source="valuation_gate", ctx=ctx))
    add(_row(record_type="degrading", evidence_layer="MONTE_CARLO", program="base_degrading", metric="A_PLUS_INSTRUMENT_GATE_reasons", value=",".join(gate.get("reasons") or []), unit="", source="valuation_gate", ctx=ctx))

    for check in checks:
        if not isinstance(check, dict):
            continue
        add(_row(record_type="devalidation", evidence_layer="OBSERVED", program="base_devalidation", metric=str(check.get("id") or ""), value="PASS" if check.get("ok") else "FAIL", unit="", source=str(check.get("severity") or ""), ctx=ctx))

    def _mc_block(sim: dict[str, Any], label: str) -> None:
        mc = sim.get("monte_carlo") if isinstance(sim.get("monte_carlo"), dict) else {}
        probs = mc.get("probabilities") if isinstance(mc.get("probabilities"), dict) else {}
        term = mc.get("terminal_bankroll") if isinstance(mc.get("terminal_bankroll"), dict) else {}
        ret = mc.get("annual_return") if isinstance(mc.get("annual_return"), dict) else {}
        mdd = mc.get("max_drawdown") if isinstance(mc.get("max_drawdown"), dict) else {}
        se = sim.get("standard_errors") if isinstance(sim.get("standard_errors"), dict) else {}
        add(_row(record_type="risk_profile", evidence_layer="MONTE_CARLO", program="base_decomposition", metric=f"{label}_paths", value=mc.get("paths"), unit="count", source=label, ctx=ctx))
        add(_row(record_type="risk_profile", evidence_layer="MONTE_CARLO", program="base_decomposition", metric=f"{label}_P_min_bankroll_le_floor", value=probs.get("P_min_bankroll_le_floor"), unit="fraction", source=label, ctx=ctx))
        add(_row(record_type="risk_profile", evidence_layer="MONTE_CARLO", program="base_decomposition", metric=f"{label}_P_final_ge_target", value=probs.get("P_final_ge_target"), unit="fraction", source=label, ctx=ctx))
        add(_row(record_type="risk_profile", evidence_layer="MONTE_CARLO", program="base_decomposition", metric=f"{label}_expected_20_week_return", value=ret.get("mean"), unit="fraction", source=label, ctx=ctx))
        add(_row(record_type="risk_profile", evidence_layer="MONTE_CARLO", program="base_decomposition", metric=f"{label}_mean_terminal_bankroll", value=term.get("mean"), unit="usd", source=label, ctx=ctx))
        add(_row(record_type="risk_profile", evidence_layer="MONTE_CARLO", program="base_decomposition", metric=f"{label}_median_terminal_bankroll", value=term.get("median"), unit="usd", source=label, ctx=ctx))
        add(_row(record_type="risk_profile", evidence_layer="MONTE_CARLO", program="base_decomposition", metric=f"{label}_mdd_p95", value=mdd.get("p95"), unit="fraction", source=label, ctx=ctx))
        for key, value in se.items():
            add(_row(record_type="risk_profile", evidence_layer="MONTE_CARLO", program="base_decomposition", metric=f"{label}_{key}", value=value, unit="fraction", source=label, ctx=ctx))
        bands = mc.get("weekly_path_bands") if isinstance(mc.get("weekly_path_bands"), list) else []
        for band in bands:
            if not isinstance(band, dict):
                continue
            week = band.get("week")
            for stat in ("p5", "p25", "p50", "p75", "p95"):
                add(_row(record_type="path_bands", evidence_layer="MONTE_CARLO", program="base_decomposition", metric=f"{label}_week_{week}_{stat}", value=band.get(stat), unit="usd", source=label, ctx=ctx))

    _mc_block(bernoulli, "bernoulli")
    _mc_block(empirical, "mode_b")
    add(_row(record_type="risk_profile", evidence_layer="MONTE_CARLO", program="base_decomposition", metric="weekly_bootstrap_status", value=weekly_bs.get("status"), unit="", source="weekly_bootstrap", ctx=ctx))
    if weekly_bs.get("status") == "MONTE_CARLO":
        for key in ("mean_terminal_bankroll", "median_terminal_bankroll", "mean_return", "P_min_bankroll_le_floor", "P_final_ge_target", "P_return_lt_0"):
            add(_row(record_type="risk_profile", evidence_layer="MONTE_CARLO", program="base_decomposition", metric=f"weekly_bootstrap_{key}", value=weekly_bs.get(key), unit="", source="weekly_bootstrap", ctx=ctx))

    for item in sensitivity:
        if not isinstance(item, dict):
            continue
        p = item.get("p")
        add(_row(record_type="sensitivity", evidence_layer="THEORETICAL", program="base_decomposition", metric=f"p_{p}_trade_ev", value=item.get("trade_ev_bankroll"), unit="fraction", source="p_grid", ctx=ctx))
        add(_row(record_type="sensitivity", evidence_layer="THEORETICAL", program="base_decomposition", metric=f"p_{p}_weekly_ev", value=item.get("weekly_ev"), unit="fraction", source="p_grid", ctx=ctx))
        add(_row(record_type="sensitivity", evidence_layer="MONTE_CARLO", program="base_decomposition", metric=f"p_{p}_expected_20_week", value=item.get("expected_20_week_return"), unit="fraction", source="p_grid", ctx=ctx))
        add(_row(record_type="sensitivity", evidence_layer="MONTE_CARLO", program="base_decomposition", metric=f"p_{p}_P_floor", value=item.get("P_min_bankroll_le_floor"), unit="fraction", source="p_grid", ctx=ctx))
        add(_row(record_type="sensitivity", evidence_layer="MONTE_CARLO", program="base_decomposition", metric=f"p_{p}_P_target", value=item.get("P_final_ge_target"), unit="fraction", source="p_grid", ctx=ctx))
        add(_row(record_type="sensitivity", evidence_layer="MONTE_CARLO", program="base_decomposition", metric=f"p_{p}_median_terminal", value=item.get("median_terminal_bankroll"), unit="usd", source="p_grid", ctx=ctx))

    add(_row(record_type="stress", evidence_layer="STRESS", program="base_decomposition", metric="p_worst", value=stress.get("p_worst"), unit="fraction", source="missing_as_loss", ctx=ctx))
    add(_row(record_type="stress", evidence_layer="STRESS", program="base_decomposition", metric="ev_at_p_worst", value=stress.get("ev_at_p_worst"), unit="e4", source="missing_as_loss", ctx=ctx))

    for item in comparison:
        if not isinstance(item, dict):
            continue
        metric = str(item.get("metric") or "")
        for layer in ("OBSERVED", "THEORETICAL", "MONTE_CARLO"):
            add(_row(record_type="comparison", evidence_layer=layer, program="base_devalidation", metric=metric, value=item.get(layer), unit="", source="comparison", ctx=ctx))
    for item in disagreements:
        if not isinstance(item, dict):
            continue
        add(_row(record_type="comparison", evidence_layer="", program="base_devalidation", metric=f"disagree_{item.get('metric')}", value=item.get("spread"), unit="", source="not_averaged", ctx=ctx))
    return out


def render_csv(payload: dict[str, Any], *, debase_hash: str = "") -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(SUPERASI_COLUMNS), lineterminator="\n", extrasaction="ignore")
    writer.writeheader()
    for row in render_rows(payload, debase_hash=debase_hash):
        writer.writerow({col: row.get(col, "") for col in SUPERASI_COLUMNS})
    return buf.getvalue()
