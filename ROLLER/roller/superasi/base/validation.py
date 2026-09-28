"""Integrity checks and OBSERVED vs THEORETICAL vs MONTE_CARLO comparison."""

from __future__ import annotations

from typing import Any

from roller.labs.schema import CSV_COLUMNS


def _close(a: float | None, b: float | None, tol: float = 1e-6) -> bool:
    if a is None or b is None:
        return False
    return abs(float(a) - float(b)) <= tol


def integrity_checks(parsed: dict[str, Any], observed: dict[str, Any]) -> list[dict[str, Any]]:
    header = list(parsed.get("header") or [])
    n = int(observed.get("population") or 0)
    header_n = observed.get("header_population")
    header_w = observed.get("header_wins")
    header_l = observed.get("header_losses")
    header_wr = observed.get("header_win_rate")
    decided = int(observed.get("decided") or 0)
    p_hat = observed.get("win_rate")
    schema_ok = not parsed.get("schema_missing") and set(CSV_COLUMNS).issubset(set(header))
    checks = [
        {
            "id": "labs_header",
            "ok": bool(schema_ok),
            "severity": "hard",
            "detail": "missing:" + ",".join(parsed.get("schema_missing") or []) if parsed.get("schema_missing") else "",
        },
        {
            "id": "population_matches_rows",
            "ok": header_n is not None and int(header_n) == n,
            "severity": "hard",
            "detail": f"header={header_n} rows={n}",
        },
        {
            "id": "wins_match_recount",
            "ok": header_w is not None and int(header_w) == int(observed.get("wins") or 0),
            "severity": "hard",
            "detail": f"header={header_w} recount={observed.get('wins')}",
        },
        {
            "id": "losses_match_recount",
            "ok": header_l is not None and int(header_l) == int(observed.get("losses") or 0),
            "severity": "hard",
            "detail": f"header={header_l} recount={observed.get('losses')}",
        },
        {
            "id": "win_rate_reconciles",
            "ok": decided <= 0 or _close(header_wr, float(p_hat) if p_hat is not None else None),
            "severity": "hard",
            "detail": f"header={header_wr} recount={p_hat}",
        },
        {
            "id": "result_hash_present",
            "ok": bool(str(observed.get("result_hash") or "").strip()),
            "severity": "hard",
            "detail": "",
        },
        {
            "id": "plan_hash_present",
            "ok": bool(str(observed.get("plan_hash") or "").strip()),
            "severity": "hard",
            "detail": "",
        },
        {
            "id": "risk_record_present",
            "ok": bool(observed.get("has_risk_record")),
            "severity": "warning",
            "detail": "legacy CSV missing risk" if not observed.get("has_risk_record") else "",
        },
    ]
    return checks


def comparison_rows(observed: dict[str, Any], composition: dict[str, Any], profile: dict[str, Any]) -> list[dict[str, Any]]:
    det = composition.get("deterministic") if isinstance(composition.get("deterministic"), dict) else {}
    mc = profile.get("monte_carlo") if isinstance(profile.get("monte_carlo"), dict) else {}
    probs = mc.get("probabilities") if isinstance(mc.get("probabilities"), dict) else {}
    term = mc.get("terminal_bankroll") if isinstance(mc.get("terminal_bankroll"), dict) else {}
    ret = mc.get("annual_return") if isinstance(mc.get("annual_return"), dict) else {}
    return [
        {
            "metric": "win_rate",
            "OBSERVED": observed.get("win_rate"),
            "THEORETICAL": composition.get("config", {}).get("win_probability")
            if isinstance(composition.get("config"), dict)
            else None,
            "MONTE_CARLO": None,
        },
        {
            "metric": "trade_ev",
            "OBSERVED": observed.get("gross_ev"),
            "THEORETICAL": det.get("trade_ev"),
            "MONTE_CARLO": None,
        },
        {
            "metric": "weekly_ev",
            "OBSERVED": None,
            "THEORETICAL": det.get("weekly_ev"),
            "MONTE_CARLO": mc.get("mean_weekly_return"),
        },
        {
            "metric": "break_even_probability",
            "OBSERVED": None,
            "THEORETICAL": det.get("break_even_probability"),
            "MONTE_CARLO": None,
        },
        {
            "metric": "terminal_bankroll_mean",
            "OBSERVED": None,
            "THEORETICAL": det.get("deterministic_compound_if_ev_realized"),
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
            "metric": "expected_20_week_return",
            "OBSERVED": None,
            "THEORETICAL": None,
            "MONTE_CARLO": ret.get("mean"),
        },
    ]
