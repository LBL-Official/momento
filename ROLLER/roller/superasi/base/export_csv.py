"""Canonical SuperasiABase CSV. Long-format metrics + Roller metadata."""

from __future__ import annotations

import csv
import io
from typing import Any

from roller.labs.schema import cell
from roller.superasi.base.ingest import ROLLER_META
from roller.superasi.base.versions import (
    GRADE_CONFIG_VERSION,
    HONESTY,
    SUPERASI_BASE_VERSION,
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
    "source_csv_sha256",
    "abase_sha256",
    *ROLLER_META,
    "risk_not",
    "fees",
    "slippage",
    "fills",
    "net_ev",
    "live_grade",
)


def csv_filename(strategy_name: str) -> str:
    return f"SuperasiABase[{strategy_name}].csv"


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


def _ctx(
    meta: dict[str, str],
    *,
    created_at: str,
    lab_id: str,
    source_hash: str,
    abase_hash: str = "",
) -> dict[str, str]:
    ctx = {col: str(meta.get(col) or "") for col in ROLLER_META}
    ctx.update(
        {
            "superasi_version": SUPERASI_BASE_VERSION,
            "grade_config_version": GRADE_CONFIG_VERSION,
            "created_at": created_at,
            "source_lab_id": lab_id,
            "source_csv_sha256": source_hash,
            "abase_sha256": abase_hash,
            **HONESTY,
        }
    )
    return ctx


def render_rows(payload: dict[str, Any], *, abase_hash: str = "") -> list[dict[str, str]]:
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    observed = payload.get("observed") if isinstance(payload.get("observed"), dict) else {}
    composition = payload.get("composition") if isinstance(payload.get("composition"), dict) else {}
    profile = payload.get("risk_profile") if isinstance(payload.get("risk_profile"), dict) else {}
    grading = payload.get("grading") if isinstance(payload.get("grading"), dict) else {}
    checks = payload.get("checks") if isinstance(payload.get("checks"), list) else []
    comparison = payload.get("comparison") if isinstance(payload.get("comparison"), list) else []
    ctx = _ctx(
        meta,
        created_at=str(payload.get("created_at") or ""),
        lab_id=str(payload.get("source_lab_id") or ""),
        source_hash=str(payload.get("source_csv_sha256") or ""),
        abase_hash=abase_hash,
    )
    out: list[dict[str, str]] = []
    add = out.append
    add(_row(record_type="meta", evidence_layer="", program="base_validation", metric="superasi_version", value=SUPERASI_BASE_VERSION, unit="", source="superasi", ctx=ctx))
    add(_row(record_type="meta", evidence_layer="", program="base_validation", metric="grade_config_version", value=GRADE_CONFIG_VERSION, unit="", source="superasi", ctx=ctx))
    add(_row(record_type="meta", evidence_layer="OBSERVED", program="base_validation", metric="source_lab_id", value=payload.get("source_lab_id"), unit="", source="labs_csv", ctx=ctx))
    add(_row(record_type="meta", evidence_layer="OBSERVED", program="base_validation", metric="candle_path_not_fill", value=HONESTY["risk_not"], unit="", source="honesty", ctx=ctx))
    add(_row(record_type="meta", evidence_layer="OBSERVED", program="base_validation", metric="live_grade", value=HONESTY["live_grade"], unit="", source="honesty", ctx=ctx))

    for key, unit in (
        ("population", "count"),
        ("wins", "count"),
        ("losses", "count"),
        ("decided", "count"),
        ("win_rate", "fraction"),
        ("loss_rate", "fraction"),
        ("gross_ev", "e4"),
        ("average_win", "e4"),
        ("average_loss", "e4"),
        ("risk_reward", "ratio"),
        ("decided_rate", "fraction"),
        ("bad_settle_rate", "fraction"),
        ("wilson_lower", "fraction"),
        ("wilson_upper", "fraction"),
        ("wilson_width", "fraction"),
        ("wilson_z", ""),
    ):
        add(_row(record_type="observed", evidence_layer="OBSERVED", program="base_grading", metric=key, value=observed.get(key), unit=unit, source="labs_row", ctx=ctx))

    det = composition.get("deterministic") if isinstance(composition.get("deterministic"), dict) else {}
    cfg = composition.get("config") if isinstance(composition.get("config"), dict) else {}
    for key, unit, src in (
        ("risk_win_probability", "fraction", cfg.get("win_probability")),
        ("break_even_probability", "fraction", det.get("break_even_probability")),
        ("trade_ev", "fraction", det.get("trade_ev")),
        ("trade_ev_dollars", "usd", det.get("trade_ev_dollars")),
        ("weekly_ev", "fraction", det.get("weekly_ev")),
        ("weekly_ev_dollars", "usd", det.get("weekly_ev_dollars")),
        ("capital_per_trade", "usd", det.get("capital_per_trade")),
        ("R_w", "fraction", det.get("R_w")),
        ("R_l", "fraction", det.get("R_l")),
        ("weekly_volatility", "fraction", det.get("weekly_volatility")),
        ("required_win_probability", "fraction", det.get("required_win_probability")),
        ("P_target_week", "fraction", det.get("P_target_week")),
        ("P_negative_week", "fraction", det.get("P_negative_week")),
        ("static_weekly_sizing", "", composition.get("static_weekly_sizing")),
        ("risk_mode", "", composition.get("mode")),
        ("risk_seed", "", composition.get("seed")),
        ("risk_result_hash", "", composition.get("risk_result_hash")),
    ):
        add(_row(record_type="composition", evidence_layer="THEORETICAL", program="base_composition", metric=key, value=src, unit=unit, source="run_risk_mode_a", ctx=ctx))

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
                record_type="composition",
                evidence_layer="THEORETICAL",
                program="base_composition",
                metric=key,
                value=roller_desk.get(src_key),
                unit="fraction",
                source="roller_payoff",
                ctx=ctx,
            )
        )
    roller_risk = payload.get("roller_risk_profile") if isinstance(payload.get("roller_risk_profile"), dict) else {}

    table = det.get("weekly_table") if isinstance(det.get("weekly_table"), list) else []
    for item in table:
        if not isinstance(item, dict):
            continue
        add(_row(record_type="weekly", evidence_layer="THEORETICAL", program="base_composition", metric=f"wins_{item.get('wins')}", value=item.get("weekly_return"), unit="fraction", source="binomial", ctx=ctx))
        add(_row(record_type="weekly", evidence_layer="THEORETICAL", program="base_composition", metric=f"wins_{item.get('wins')}_probability", value=item.get("probability"), unit="fraction", source="binomial", ctx=ctx))

    components = grading.get("components") if isinstance(grading.get("components"), dict) else {}
    add(_row(record_type="grading", evidence_layer="OBSERVED", program="base_grading", metric="BASE_GRADE", value=grading.get("BASE_GRADE"), unit="letter", source="grade_config_v1", ctx=ctx))
    add(_row(record_type="grading", evidence_layer="OBSERVED", program="base_grading", metric="composite_score", value=grading.get("composite_score"), unit="score", source="grade_config_v1", ctx=ctx))
    add(_row(record_type="grading", evidence_layer="OBSERVED", program="base_grading", metric="borderline", value=grading.get("borderline"), unit="", source="grade_config_v1", ctx=ctx))
    for name, letter in components.items():
        add(_row(record_type="grading", evidence_layer="OBSERVED", program="base_grading", metric=f"{name}_grade", value=letter, unit="letter", source="grade_config_v1", ctx=ctx))
    add(_row(record_type="grading", evidence_layer="THEORETICAL", program="base_grading", metric="risk_win_probability", value=cfg.get("win_probability"), unit="fraction", source="desk_instrument", ctx=ctx))
    add(_row(record_type="grading", evidence_layer="OBSERVED", program="base_grading", metric="win_rate", value=observed.get("win_rate"), unit="fraction", source="labs_row", ctx=ctx))

    for check in checks:
        if not isinstance(check, dict):
            continue
        add(_row(record_type="validation", evidence_layer="OBSERVED", program="base_validation", metric=str(check.get("id") or ""), value="PASS" if check.get("ok") else "FAIL", unit="", source=str(check.get("severity") or ""), ctx=ctx))

    mc = profile.get("monte_carlo") if isinstance(profile.get("monte_carlo"), dict) else {}
    probs = mc.get("probabilities") if isinstance(mc.get("probabilities"), dict) else {}
    term = mc.get("terminal_bankroll") if isinstance(mc.get("terminal_bankroll"), dict) else {}
    ret = mc.get("annual_return") if isinstance(mc.get("annual_return"), dict) else {}
    mdd = mc.get("max_drawdown") if isinstance(mc.get("max_drawdown"), dict) else {}
    add(_row(record_type="risk_profile", evidence_layer="MONTE_CARLO", program="base_composition", metric="not_base_grade", value="true", unit="", source="risk_profile", ctx=ctx))
    add(_row(record_type="risk_profile", evidence_layer="MONTE_CARLO", program="base_composition", metric="horizon_weeks", value=profile.get("config", {}).get("weeks_per_year") if isinstance(profile.get("config"), dict) else "", unit="week", source="run_risk_mode_a", ctx=ctx))
    add(_row(record_type="risk_profile", evidence_layer="MONTE_CARLO", program="base_composition", metric="paths", value=mc.get("paths"), unit="count", source="run_risk_mode_a", ctx=ctx))
    add(_row(record_type="risk_profile", evidence_layer="MONTE_CARLO", program="base_composition", metric="P_min_bankroll_le_floor", value=probs.get("P_min_bankroll_le_floor"), unit="fraction", source="run_risk_mode_a", ctx=ctx))
    add(_row(record_type="risk_profile", evidence_layer="MONTE_CARLO", program="base_composition", metric="P_final_ge_target", value=probs.get("P_final_ge_target"), unit="fraction", source="run_risk_mode_a", ctx=ctx))
    add(_row(record_type="risk_profile", evidence_layer="MONTE_CARLO", program="base_composition", metric="expected_20_week_return", value=ret.get("mean"), unit="fraction", source="run_risk_mode_a", ctx=ctx))
    add(_row(record_type="risk_profile", evidence_layer="MONTE_CARLO", program="base_composition", metric="median_terminal_bankroll", value=term.get("median"), unit="usd", source="run_risk_mode_a", ctx=ctx))
    add(_row(record_type="risk_profile", evidence_layer="MONTE_CARLO", program="base_composition", metric="mean_terminal_bankroll", value=term.get("mean"), unit="usd", source="run_risk_mode_a", ctx=ctx))
    add(_row(record_type="risk_profile", evidence_layer="MONTE_CARLO", program="base_composition", metric="mdd_p95", value=mdd.get("p95"), unit="fraction", source="run_risk_mode_a", ctx=ctx))
    for key in ("P_final_ge_1_5x", "P_final_lt_B0", "P_mdd_le_neg_5", "P_mdd_le_neg_10", "P_mdd_le_neg_20"):
        add(_row(record_type="risk_profile", evidence_layer="MONTE_CARLO", program="base_composition", metric=key, value=probs.get(key), unit="fraction", source="run_risk_mode_a", ctx=ctx))

    bands = mc.get("weekly_path_bands") if isinstance(mc.get("weekly_path_bands"), list) else []
    for band in bands:
        if not isinstance(band, dict):
            continue
        week = band.get("week")
        for stat in ("p5", "p25", "p50", "p75", "p95"):
            add(_row(record_type="risk_profile", evidence_layer="MONTE_CARLO", program="base_composition", metric=f"path_week_{week}_{stat}", value=band.get(stat), unit="usd", source="run_risk_mode_a", ctx=ctx))

    add(_row(record_type="risk_profile", evidence_layer="MONTE_CARLO", program="base_composition", metric="roller_horizon_weeks", value=roller_risk.get("weeks"), unit="week", source="roller_payoff", ctx=ctx))
    add(_row(record_type="risk_profile", evidence_layer="MONTE_CARLO", program="base_composition", metric="roller_paths", value=roller_risk.get("paths"), unit="count", source="roller_payoff", ctx=ctx))
    add(_row(record_type="risk_profile", evidence_layer="MONTE_CARLO", program="base_composition", metric="roller_P_min_bankroll_le_floor", value=roller_risk.get("P_min_bankroll_le_floor"), unit="fraction", source="roller_payoff", ctx=ctx))
    add(_row(record_type="risk_profile", evidence_layer="MONTE_CARLO", program="base_composition", metric="roller_P_final_ge_target", value=roller_risk.get("P_final_ge_target"), unit="fraction", source="roller_payoff", ctx=ctx))
    add(_row(record_type="risk_profile", evidence_layer="MONTE_CARLO", program="base_composition", metric="roller_mean_terminal_bankroll", value=roller_risk.get("mean_terminal_bankroll"), unit="usd", source="roller_payoff", ctx=ctx))
    add(_row(record_type="risk_profile", evidence_layer="MONTE_CARLO", program="base_composition", metric="roller_p_used", value=roller_risk.get("p_used") if roller_risk.get("p_used") is not None else roller_desk.get("p_used"), unit="fraction", source="roller_payoff", ctx=ctx))

    for item in comparison:
        if not isinstance(item, dict):
            continue
        metric = str(item.get("metric") or "")
        for layer in ("OBSERVED", "THEORETICAL", "MONTE_CARLO"):
            add(_row(record_type="comparison", evidence_layer=layer, program="base_validation", metric=metric, value=item.get(layer), unit="", source="comparison", ctx=ctx))
    return out


def render_csv(payload: dict[str, Any], *, abase_hash: str = "") -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(SUPERASI_COLUMNS), lineterminator="\n", extrasaction="ignore")
    writer.writeheader()
    for row in render_rows(payload, abase_hash=abase_hash):
        writer.writerow({col: row.get(col, "") for col in SUPERASI_COLUMNS})
    return buf.getvalue()
