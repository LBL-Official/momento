"""Integrity, formula identity, and OBSERVED / THEORETICAL / MONTE_CARLO comparison."""

from __future__ import annotations

from typing import Any

from roller.superasi.base.validation import integrity_checks
from roller.superasi.debase.valuation import desk_identity_checks


def _f(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def phase_a_checks(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    rec = bundle.get("phase_a") if isinstance(bundle.get("phase_a"), dict) else {}
    return [
        {
            "id": "phase_a_folder",
            "ok": bool(bundle.get("result_id")),
            "severity": "hard",
            "detail": str(bundle.get("result_id") or ""),
        },
        {
            "id": "phase_a_roller_present",
            "ok": bool(bundle.get("roller_bytes")),
            "severity": "hard",
            "detail": str(bundle.get("roller_filename") or ""),
        },
        {
            "id": "phase_a_abase_present",
            "ok": bool(bundle.get("abase_bytes")),
            "severity": "hard",
            "detail": str(bundle.get("abase_filename") or ""),
        },
        {
            "id": "phase_a_base_grade",
            "ok": bool(bundle.get("BASE_GRADE")),
            "severity": "hard",
            "detail": str(bundle.get("BASE_GRADE") or ""),
        },
        {
            "id": "source_lab_id",
            "ok": bool(bundle.get("source_lab_id")),
            "severity": "hard",
            "detail": str(bundle.get("source_lab_id") or ""),
        },
        {
            "id": "plan_hash_present",
            "ok": bool(str((bundle.get("parsed_roller") or {}).get("meta", {}).get("plan_hash") or "").strip()),
            "severity": "hard",
            "detail": "",
        },
        {
            "id": "result_hash_present",
            "ok": bool(str((bundle.get("parsed_roller") or {}).get("meta", {}).get("result_hash") or "").strip()),
            "severity": "hard",
            "detail": "",
        },
        {
            "id": "question_persisted",
            "ok": bundle.get("question_status") in {"PRESENT", "UNAVAILABLE"},
            "severity": "warning",
            "detail": str(bundle.get("question_status") or ""),
        },
        {
            "id": "source_lab_matches_metadata",
            "ok": str(rec.get("source_lab_id") or "") == str(bundle.get("source_lab_id") or ""),
            "severity": "hard",
            "detail": "",
        },
    ]


def comparison_rows(
    *,
    observed: dict[str, Any],
    theoretical: dict[str, Any],
    bernoulli: dict[str, Any],
    empirical: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    mc = bernoulli.get("monte_carlo") if isinstance(bernoulli.get("monte_carlo"), dict) else {}
    probs = mc.get("probabilities") if isinstance(mc.get("probabilities"), dict) else {}
    term = mc.get("terminal_bankroll") if isinstance(mc.get("terminal_bankroll"), dict) else {}
    ret = mc.get("annual_return") if isinstance(mc.get("annual_return"), dict) else {}
    emp_mc = empirical.get("monte_carlo") if isinstance(empirical, dict) and isinstance(empirical.get("monte_carlo"), dict) else {}
    emp_ret = emp_mc.get("annual_return") if isinstance(emp_mc.get("annual_return"), dict) else {}
    return [
        {
            "metric": "win_rate",
            "OBSERVED": observed.get("win_rate"),
            "THEORETICAL": theoretical.get("p"),
            "MONTE_CARLO": None,
            "note": "THEORETICAL p is IQR 1 (Q1) as the mean, not desk 0.70",
        },
        {
            "metric": "trade_ev_e4",
            "OBSERVED": observed.get("gross_ev"),
            "THEORETICAL": observed.get("ev_debase"),
            "MONTE_CARLO": None,
        },
        {
            "metric": "break_even_probability",
            "OBSERVED": observed.get("p_be_roller"),
            "THEORETICAL": theoretical.get("p_be"),
            "MONTE_CARLO": None,
        },
        {
            "metric": "weekly_ev",
            "OBSERVED": None,
            "THEORETICAL": theoretical.get("weekly_ev"),
            "MONTE_CARLO": mc.get("mean_weekly_return"),
        },
        {
            "metric": "expected_20_week_return",
            "OBSERVED": None,
            "THEORETICAL": theoretical.get("compounded_20_week"),
            "MONTE_CARLO": ret.get("mean"),
        },
        {
            "metric": "terminal_bankroll_mean",
            "OBSERVED": None,
            "THEORETICAL": theoretical.get("compounded_terminal"),
            "MONTE_CARLO": term.get("mean"),
        },
        {
            "metric": "P_min_bankroll_le_floor",
            "OBSERVED": None,
            "THEORETICAL": None,
            "MONTE_CARLO": probs.get("P_min_bankroll_le_floor"),
        },
        {
            "metric": "P_final_ge_target",
            "OBSERVED": None,
            "THEORETICAL": None,
            "MONTE_CARLO": probs.get("P_final_ge_target"),
        },
        {
            "metric": "mode_b_expected_20_week_return",
            "OBSERVED": None,
            "THEORETICAL": None,
            "MONTE_CARLO": emp_ret.get("mean"),
        },
    ]


def disagreement_rows(comparison: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for row in comparison:
        obs = _f(row.get("OBSERVED"))
        th = _f(row.get("THEORETICAL"))
        mc = _f(row.get("MONTE_CARLO"))
        present = [x for x in (obs, th, mc) if x is not None]
        if len(present) < 2:
            continue
        spread = max(present) - min(present)
        if spread > 1e-6:
            out.append(
                {
                    "metric": row.get("metric"),
                    "spread": spread,
                    "note": "disagreement recorded; not averaged",
                }
            )
    return out


def collect_checks(
    *,
    parsed_roller: dict[str, Any],
    observed: dict[str, Any],
    bundle: dict[str, Any],
) -> list[dict[str, Any]]:
    checks = integrity_checks(parsed_roller, observed)
    checks.extend(phase_a_checks(bundle))
    for item in desk_identity_checks():
        checks.append(
            {
                "id": item["id"],
                "ok": bool(item["ok"]),
                "severity": "hard",
                "detail": str(item.get("detail") or ""),
            }
        )
    return checks
