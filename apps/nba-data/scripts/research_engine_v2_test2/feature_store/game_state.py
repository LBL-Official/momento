"""Family A — instantaneous game state at entry snap (possession-normalized)."""

from __future__ import annotations


def game_state_at_possession(p: dict | None, *, team_code: str | None, n_poss_pre: int | None, total_poss_est: int | None) -> dict:
    if p is None:
        return {
            "quarter": None,
            "official_time_remaining_s": None,
            "game_elapsed_seconds": None,
            "game_completion_pct": None,
            "possession_number": n_poss_pre,
            "estimated_possessions_remaining": None,
            "score_differential": None,
            "team_is_leading": None,
            "home_score": None,
            "away_score": None,
        }
    elapsed = p.get("elapsed_end_s")
    remaining = p.get("remaining_end_s")
    # Regulation 2880s; OT unknown.
    completion = None
    if elapsed is not None:
        completion = min(1.0, max(0.0, float(elapsed) / 2880.0))
    est_rem = None
    if n_poss_pre and elapsed and elapsed > 60:
        pace = n_poss_pre / (elapsed / 60.0)
        rem_min = max(0.0, (2880.0 - elapsed) / 60.0)
        est_rem = pace * rem_min
    diff_home = (p.get("home_score_end") or 0) - (p.get("away_score_end") or 0)
    # Signed for traded team if we know whether they are home.
    signed = p.get("score_differential_start")
    if p.get("possession_team") and team_code:
        # Prefer end scores signed if team is possession team; else home-away.
        signed = diff_home
    leading = None if signed is None else signed > 0
    return {
        "quarter": p.get("period"),
        "official_time_remaining_s": remaining,
        "game_elapsed_seconds": elapsed,
        "game_completion_pct": completion,
        "possession_number": n_poss_pre,
        "estimated_possessions_remaining": est_rem,
        "score_differential": signed,
        "team_is_leading": leading,
        "home_score": p.get("home_score_end"),
        "away_score": p.get("away_score_end"),
        "possession_team": p.get("possession_team"),
    }
