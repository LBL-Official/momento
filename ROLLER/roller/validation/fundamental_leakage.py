"""V4A leakage: O_t stays clean; F_t is prior-only with current-game exclusion."""

from __future__ import annotations

from typing import Any

from roller.fundamental.eligibility import fundamental_eligible


FORBIDDEN_OBS_KEYS = {
    "fundamental",
    "F_t",
    "FUNDAMENTAL",
    "labels",
    "response",
    "baseline",
    "residual",
    "Y",
}


def audit_observation_excludes_fundamental(obs: dict[str, Any]) -> list[str]:
    errors = []
    for key in obs:
        low = str(key).lower()
        if key in FORBIDDEN_OBS_KEYS or low in {"fundamental", "f_t"}:
            errors.append(f"observation contains forbidden key {key}")
        if "fundamental" in low:
            errors.append(f"observation key {key} looks like a fundamental estimate")
    if "contains_future_information" in obs:
        errors.append("observation carries contains_future_information")
    return errors


def audit_eligible_row(row: dict[str, Any], *, current_game_id: str, cutoff) -> list[str]:
    errors = []
    if not fundamental_eligible(row, current_game_id=current_game_id, cutoff=cutoff):
        return errors
    if str(row.get("internal_game_id") or "") == str(current_game_id):
        errors.append("current game row marked eligible")
    return errors


def audit_fundamental_eligibility_example() -> list[str]:
    """State at 10:00, outcome at 10:05. Equality hidden. Current game excluded."""
    historical = {
        "internal_game_id": "GAME_A",
        "state_available_at": "2025-12-20T10:00:00Z",
        "result_available_at": "2025-12-20T10:05:00Z",
    }
    errors = []
    if fundamental_eligible(historical, current_game_id="GAME_B", cutoff="2025-12-20T10:02:00Z"):
        errors.append("outcome at 10:05 eligible for cutoff 10:02")
    if fundamental_eligible(historical, current_game_id="GAME_B", cutoff="2025-12-20T10:05:00Z"):
        errors.append("equality on result_available_at must be hidden")
    if not fundamental_eligible(historical, current_game_id="GAME_B", cutoff="2025-12-20T10:06:00Z"):
        errors.append("10:00/10:05 history should be eligible at 10:06")
    if fundamental_eligible(historical, current_game_id="GAME_A", cutoff="2025-12-20T10:06:00Z"):
        errors.append("current game identity must be excluded even after outcome exists")
    return errors
