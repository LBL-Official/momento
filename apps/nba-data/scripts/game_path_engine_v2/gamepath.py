"""Causal game-state / path / volatility / run features at first-80 snap."""

from __future__ import annotations

from common import mean, stdev
from pbp import game_seconds_remaining, team_scores


def _score_int(x) -> int:
    try:
        return int(x)
    except (TypeError, ValueError):
        return 0


def signed_diff(team_is_home: bool, score_home: int, score_away: int) -> int:
    return (score_home - score_away) if team_is_home else (score_away - score_home)


def path_state_label(
    *,
    game_phase: str,
    quarter: int | None,
    lead_size: int | None,
    team_is_leading: bool | None,
    lead_decay: float | None,
    current_lead_duration_s: float | None,
    lead_changes: int | None,
    lead_changes_last_10m: int | None,
    max_deficit_overcome: float | None,
    time_since_max_deficit_s: float | None,
    score_diff_trend: float | None,
) -> str:
    if game_phase == "GAME_NOT_STARTED":
        return "GAME_NOT_STARTED"
    late_cb = (
        (max_deficit_overcome or 0) >= 8
        and (time_since_max_deficit_s is not None)
        and time_since_max_deficit_s <= 360
        and quarter is not None
        and quarter >= 4
    )
    if late_cb:
        return "LATE_COMEBACK"
    recent_cb = (
        (max_deficit_overcome or 0) >= 8
        and time_since_max_deficit_s is not None
        and time_since_max_deficit_s <= 360
    )
    if recent_cb:
        return "RECENT_COMEBACK"
    if team_is_leading and (lead_decay or 0) >= 8:
        return "COLLAPSING_LEAD"
    volatile = (lead_changes or 0) >= 6 or (lead_changes_last_10m or 0) >= 3
    if volatile:
        return "VOLATILE_BACK_AND_FORTH"
    expanding = (
        team_is_leading
        and (lead_size or 0) >= 1
        and score_diff_trend is not None
        and score_diff_trend > 0
        and (lead_decay or 0) <= 2
    )
    if expanding:
        return "EXPANDING_LEAD"
    stable = (
        team_is_leading
        and (lead_size or 0) >= 4
        and (lead_decay or 0) < 4
        and current_lead_duration_s is not None
        and current_lead_duration_s >= 300
        and (lead_changes_last_10m or 0) <= 1
    )
    if stable:
        return "STABLE_LEAD"
    return "OTHER"


def game_market_alignment(score_mom: float | None, market_mom: float | None) -> str:
    if score_mom is None or market_mom is None:
        return "INSUFFICIENT"
    if score_mom >= 3 and market_mom >= 3:
        return "ALIGNED_UP"
    if score_mom <= -3 and market_mom <= -3:
        return "ALIGNED_DOWN"
    if score_mom >= 3 and abs(market_mom) <= 2:
        return "GAME_IMPROVING_MARKET_FLAT"
    if score_mom <= -3 and abs(market_mom) <= 2:
        return "GAME_WORSENING_MARKET_FLAT"
    if market_mom >= 5 and score_mom <= 0:
        return "MARKET_LEADING_GAME"
    if score_mom >= 5 and market_mom <= 0:
        return "GAME_LEADING_MARKET"
    return "MIXED"


def features_at_snap(
    rows: list[dict],
    snap_idx: int | None,
    team_is_home: bool,
    game_phase: str,
) -> dict:
    empty = _empty_game_features(game_phase)
    if snap_idx is None or not rows:
        return empty
    snap = rows[snap_idx]
    prior = rows[: snap_idx + 1]
    team_score, opp_score = team_scores(snap, team_is_home)
    if team_score is None:
        return empty
    diff = team_score - opp_score
    total = team_score + opp_score
    elapsed = snap.get("elapsed_s")
    remaining_period = snap.get("remaining_s")
    quarter = snap.get("period")
    remaining_game = game_seconds_remaining(quarter, remaining_period)

    series = []
    last_h, last_a = 0, 0
    for r in prior:
        h, a = r["score_home"], r["score_away"]
        if h == last_h and a == last_a and series:
            continue
        last_h, last_a = h, a
        d = signed_diff(team_is_home, h, a)
        series.append(
            {
                "elapsed": r.get("elapsed_s"),
                "diff": d,
                "home": h,
                "away": a,
                "idx": r["idx"],
            }
        )
    if not series:
        series.append({"elapsed": elapsed, "diff": diff, "home": snap["score_home"], "away": snap["score_away"], "idx": snap_idx})

    diffs = [s["diff"] for s in series]
    max_lead = max(diffs)
    min_diff = min(diffs)
    max_deficit_mag = max(0, -min_diff)
    lead_range = max_lead - min_diff
    dist_max_lead = max_lead - diff
    dist_max_deficit = diff - min_diff
    comeback_mag = diff - min_diff
    lead_decay = max(0, max_lead - max(diff, 0)) if diff >= 0 else max(0, max_lead)

    lead_changes = 0
    ties = 0
    last_leader = None
    last_non_tie = None
    last_lead_change_elapsed = None
    last_tie_elapsed = None
    current_lead_start = series[0]["elapsed"]
    for s in series:
        d = s["diff"]
        if d > 0:
            leader = "team"
        elif d < 0:
            leader = "opp"
        else:
            leader = "tie"
        if leader == "tie" and last_leader != "tie":
            ties += 1
            last_tie_elapsed = s["elapsed"]
        if leader != "tie":
            if last_non_tie is not None and leader != last_non_tie:
                lead_changes += 1
                last_lead_change_elapsed = s["elapsed"]
                current_lead_start = s["elapsed"]
            elif last_non_tie is None:
                current_lead_start = s["elapsed"]
            last_non_tie = leader
        last_leader = leader

    def window_count(seconds: float, kind: str) -> int | None:
        if elapsed is None or elapsed < seconds:
            return None
        cut = elapsed - seconds
        n = 0
        last_nt = None
        prev_leader = None
        for s in series:
            if s["elapsed"] is None or s["elapsed"] < cut:
                d0 = s["diff"]
                prev_leader = "team" if d0 > 0 else ("opp" if d0 < 0 else "tie")
                last_nt = None if prev_leader == "tie" else prev_leader
                continue
            d = s["diff"]
            leader = "team" if d > 0 else ("opp" if d < 0 else "tie")
            if kind == "tie" and leader == "tie" and prev_leader != "tie":
                n += 1
            if kind == "lead" and leader != "tie":
                if last_nt is not None and leader != last_nt:
                    n += 1
                last_nt = leader
            if leader != "tie":
                last_nt = leader
            prev_leader = leader
        return n

    def diff_at(seconds_ago: float) -> int | None:
        if elapsed is None or elapsed < seconds_ago:
            return None
        cut = elapsed - seconds_ago
        val = None
        for s in series:
            if s["elapsed"] is not None and s["elapsed"] <= cut:
                val = s["diff"]
            elif s["elapsed"] is not None and s["elapsed"] > cut:
                break
        return val

    def window_diffs(seconds: float) -> list[int] | None:
        if elapsed is None or elapsed < seconds:
            return None
        cut = elapsed - seconds
        return [s["diff"] for s in series if s["elapsed"] is not None and s["elapsed"] >= cut]

    lc5 = window_count(300, "lead")
    lc10 = window_count(600, "lead")
    ties5 = window_count(300, "tie")
    ties10 = window_count(600, "tie")
    d2 = diff_at(120)
    d5 = diff_at(300)
    d10 = diff_at(600)
    net2 = None if d2 is None else diff - d2
    net5 = None if d5 is None else diff - d5
    net10 = None if d10 is None else diff - d10

    w2 = window_diffs(120)
    w5 = window_diffs(300)
    w10 = window_diffs(600)

    def rng(xs):
        if not xs:
            return None
        return max(xs) - min(xs)

    # OLS trend vs elapsed
    trend = None
    pts = [(s["elapsed"], s["diff"]) for s in series if s["elapsed"] is not None]
    if len(pts) >= 3:
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        mx = sum(xs) / len(xs)
        my = sum(ys) / len(ys)
        den = sum((x - mx) ** 2 for x in xs)
        if den > 0:
            trend = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den  # points per second

    velocity = net2  # Δdiff last 2 game minutes

    # historical min location
    min_idx = min(range(len(series)), key=lambda i: series[i]["diff"])
    min_elapsed = series[min_idx]["elapsed"]
    time_since_max_deficit = None
    points_since_max_deficit = None
    if min_diff < 0 and min_elapsed is not None and elapsed is not None:
        time_since_max_deficit = elapsed - min_elapsed
        points_since_max_deficit = (team_score + opp_score) - (
            series[min_idx]["home"] + series[min_idx]["away"]
        )
    max_deficit_overcome = max(0, -min_diff) if diff >= 0 else 0

    # scoring runs
    runs = []
    run_team = None
    run_pts = 0
    run_start = series[0]["elapsed"]
    # walk raw prior actions for scoring increments
    prev_h = 0
    prev_a = 0
    for r in prior:
        h, a = r["score_home"], r["score_away"]
        dh, da = h - prev_h, a - prev_a
        prev_h, prev_a = h, a
        if dh == 0 and da == 0:
            continue
        if team_is_home:
            scorer = "team" if dh > 0 and dh >= da else "opp"
            pts = dh if scorer == "team" else da
            if dh > 0 and da > 0:
                # split: close run then ignore rare simultaneous
                scorer = "team" if dh >= da else "opp"
                pts = max(dh, da)
        else:
            scorer = "team" if da > 0 and da >= dh else "opp"
            pts = da if scorer == "team" else dh
            if dh > 0 and da > 0:
                scorer = "team" if da >= dh else "opp"
                pts = max(dh, da)
        if pts <= 0:
            continue
        if scorer == run_team:
            run_pts += pts
        else:
            if run_team is not None:
                dur = None
                if r.get("elapsed_s") is not None and run_start is not None:
                    dur = r["elapsed_s"] - run_start
                runs.append({"team": run_team, "points": run_pts, "duration_s": dur})
            run_team = scorer
            run_pts = pts
            run_start = r.get("elapsed_s")
    if run_team is not None:
        dur = None
        if elapsed is not None and run_start is not None:
            dur = elapsed - run_start
        runs.append({"team": run_team, "points": run_pts, "duration_s": dur})
    last_run = runs[-1] if runs else None
    prior_runs = runs[:-1] if len(runs) > 1 else []
    largest = max(prior_runs, key=lambda x: x["points"]) if prior_runs else None

    ppm = None
    if elapsed is not None and elapsed >= 60:
        ppm = total / (elapsed / 60.0)
    share = (team_score / total) if total > 0 else None

    half = None
    if quarter is not None:
        half = 1 if quarter <= 2 else 2
    early = mid = late = flag_q4 = flag_ot = None
    if quarter is not None:
        flag_q4 = quarter == 4
        flag_ot = quarter >= 5
        early = quarter == 1
        mid = quarter in (2, 3)
        late = quarter >= 4

    lead_size = max(diff, 0)
    deficit_size = max(-diff, 0)
    tslc = None
    if last_lead_change_elapsed is not None and elapsed is not None:
        tslc = elapsed - last_lead_change_elapsed
    tstie = None
    if last_tie_elapsed is not None and elapsed is not None:
        tstie = elapsed - last_tie_elapsed
    cld = None
    if current_lead_start is not None and elapsed is not None:
        cld = elapsed - current_lead_start

    # scoring rate last 5m
    team_rate_diff_5 = None
    if elapsed is not None and elapsed >= 300 and d5 is not None:
        # approximate: net5 is team-opp change
        team_rate_diff_5 = net5 / 5.0 if net5 is not None else None

    burst5 = None
    if w5 and len(w5) >= 2:
        burst5 = max(abs(w5[i] - w5[i - 1]) for i in range(1, len(w5)))

    path_state = path_state_label(
        game_phase=game_phase,
        quarter=quarter,
        lead_size=lead_size,
        team_is_leading=diff > 0,
        lead_decay=lead_decay,
        current_lead_duration_s=cld,
        lead_changes=lead_changes,
        lead_changes_last_10m=lc10,
        max_deficit_overcome=max_deficit_overcome,
        time_since_max_deficit_s=time_since_max_deficit,
        score_diff_trend=trend,
    )

    return {
        "quarter": quarter,
        "game_seconds_elapsed": elapsed,
        "game_seconds_remaining": remaining_game,
        "period_seconds_remaining": remaining_period,
        "half": half,
        "early_game": early,
        "mid_game": mid,
        "late_game": late,
        "flag_Q4": flag_q4,
        "flag_OT": flag_ot,
        "team_score": team_score,
        "opponent_score": opp_score,
        "score_differential": diff,
        "absolute_score_differential": abs(diff),
        "total_points": total,
        "points_per_game_minute": ppm,
        "team_share_of_total_points": share,
        "lead_size": lead_size,
        "deficit_size": deficit_size,
        "team_is_leading": diff > 0,
        "team_is_trailing": diff < 0,
        "game_is_tied": diff == 0,
        "number_of_lead_changes": lead_changes,
        "number_of_ties": ties,
        "time_since_last_lead_change_s": tslc,
        "time_since_last_tie_s": tstie,
        "lead_changes_last_5_game_minutes": lc5,
        "lead_changes_last_10_game_minutes": lc10,
        "ties_last_5_game_minutes": ties5,
        "ties_last_10_game_minutes": ties10,
        "current_lead_duration_s": cld,
        "maximum_team_lead": max_lead,
        "maximum_team_deficit": max_deficit_mag,
        "lead_range": lead_range,
        "score_differential_stdev": stdev(diffs),
        "score_differential_mean": mean(diffs),
        "score_differential_trend": trend,
        "score_differential_velocity": velocity,
        "distance_from_max_lead": dist_max_lead,
        "distance_from_max_deficit": dist_max_deficit,
        "comeback_magnitude": comeback_mag,
        "maximum_deficit_overcome": max_deficit_overcome,
        "points_scored_since_max_deficit": points_since_max_deficit,
        "time_since_max_deficit_s": time_since_max_deficit,
        "lead_decay": lead_decay,
        "path_state": path_state,
        "score_diff_stdev_2m": stdev(w2) if w2 is not None else None,
        "score_diff_stdev_5m": stdev(w5) if w5 is not None else None,
        "score_diff_stdev_10m": stdev(w10) if w10 is not None else None,
        "score_diff_range_2m": rng(w2) if w2 is not None else None,
        "score_diff_range_5m": rng(w5) if w5 is not None else None,
        "score_diff_range_10m": rng(w10) if w10 is not None else None,
        "score_diff_abs_change_2m": None if net2 is None else abs(net2),
        "score_diff_abs_change_5m": None if net5 is None else abs(net5),
        "score_diff_abs_change_10m": None if net10 is None else abs(net10),
        "scoring_burst_intensity_5m": burst5,
        "team_scoring_rate_diff_5m": team_rate_diff_5,
        "scoring_run_imbalance": None
        if last_run is None
        else (last_run["points"] if last_run["team"] == "team" else -last_run["points"]),
        "last_scoring_run_team": None if last_run is None else last_run["team"],
        "last_scoring_run_points": None if last_run is None else last_run["points"],
        "last_scoring_run_duration_s": None if last_run is None else last_run["duration_s"],
        "largest_prior_run_team": None if largest is None else largest["team"],
        "largest_prior_run_points": None if largest is None else largest["points"],
        "net_score_change_last_2m": net2,
        "net_score_change_last_5m": net5,
        "net_score_change_last_10m": net10,
        "pace_proxy": ppm,
        "n_score_path_points": len(series),
        "game_phase": game_phase,
    }


def _empty_game_features(game_phase: str) -> dict:
    keys = [
        "quarter",
        "game_seconds_elapsed",
        "game_seconds_remaining",
        "period_seconds_remaining",
        "half",
        "early_game",
        "mid_game",
        "late_game",
        "flag_Q4",
        "flag_OT",
        "team_score",
        "opponent_score",
        "score_differential",
        "absolute_score_differential",
        "total_points",
        "points_per_game_minute",
        "team_share_of_total_points",
        "lead_size",
        "deficit_size",
        "team_is_leading",
        "team_is_trailing",
        "game_is_tied",
        "number_of_lead_changes",
        "number_of_ties",
        "time_since_last_lead_change_s",
        "time_since_last_tie_s",
        "lead_changes_last_5_game_minutes",
        "lead_changes_last_10_game_minutes",
        "ties_last_5_game_minutes",
        "ties_last_10_game_minutes",
        "current_lead_duration_s",
        "maximum_team_lead",
        "maximum_team_deficit",
        "lead_range",
        "score_differential_stdev",
        "score_differential_mean",
        "score_differential_trend",
        "score_differential_velocity",
        "distance_from_max_lead",
        "distance_from_max_deficit",
        "comeback_magnitude",
        "maximum_deficit_overcome",
        "points_scored_since_max_deficit",
        "time_since_max_deficit_s",
        "lead_decay",
        "score_diff_stdev_2m",
        "score_diff_stdev_5m",
        "score_diff_stdev_10m",
        "score_diff_range_2m",
        "score_diff_range_5m",
        "score_diff_range_10m",
        "score_diff_abs_change_2m",
        "score_diff_abs_change_5m",
        "score_diff_abs_change_10m",
        "scoring_burst_intensity_5m",
        "team_scoring_rate_diff_5m",
        "scoring_run_imbalance",
        "last_scoring_run_team",
        "last_scoring_run_points",
        "last_scoring_run_duration_s",
        "largest_prior_run_team",
        "largest_prior_run_points",
        "net_score_change_last_2m",
        "net_score_change_last_5m",
        "net_score_change_last_10m",
        "pace_proxy",
        "n_score_path_points",
    ]
    out = {k: None for k in keys}
    out["path_state"] = "GAME_NOT_STARTED" if game_phase == "GAME_NOT_STARTED" else "OTHER"
    out["game_phase"] = game_phase
    return out
