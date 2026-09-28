"""Map measured tables to one structural label. Association, not a rule."""

from __future__ import annotations

from typing import Any

TIME = {
    "period_remaining_s",
    "game_seconds_remaining",
    "frac_period_remaining",
    "frac_game_elapsed",
}
SCORE = {"bought_margin", "abs_margin", "leading", "tie", "favorite_leading"}
OPEN = {"pregame_cents", "distance_from_open"}
PRICE = {
    "entry_bid_cents",
    "jump_through_80",
    "exact_80",
    "prior_close_cents",
    "delta_5m",
    "velocity_5m",
}


def _mean_abs(values: list[float | None]) -> float | None:
    present = [abs(value) for value in values if value is not None]
    if not present:
        return None
    return float(sum(present) / len(present))


def _smd_map(rows: list[dict[str, Any]]) -> dict[str, float | None]:
    return {row["feature"]: row.get("standardized_difference") for row in rows}


def _subset_mean(smds: dict[str, float | None], names: set[str]) -> float | None:
    return _mean_abs([smds.get(name) for name in names])


def classify(analysis: dict[str, Any]) -> dict[str, Any]:
    diffs = analysis["composition"]["q2_vs_q3"]
    smds = _smd_map(diffs)
    all_mean = _mean_abs(list(smds.values()))
    all_max = None
    present = [abs(value) for value in smds.values() if value is not None]
    if present:
        all_max = float(max(present))
    time_m = _subset_mean(smds, TIME)
    score_m = _subset_mean(smds, SCORE)
    open_m = _subset_mean(smds, OPEN)
    price_m = _subset_mean(smds, PRICE)

    pops = {row["period"]: row for row in analysis["composition"]["population"]}
    q2 = pops.get("Q2") or pops.get("Q2 all-phase")
    q3 = pops.get("Q3") or pops.get("Q3 all-phase")
    raw_t40_gap = None
    if q2 and q3 and q2["n"] and q3["n"]:
        raw_t40_gap = (q2["t40"] / q2["n"]) - (q3["t40"] / q3["n"])

    match_rows = analysis.get("matching") or []
    q2_match = next((row for row in match_rows if row["source_period"] == "Q2"), None)
    match_shrink = None
    if q2_match is not None and raw_t40_gap not in {None, 0}:
        match_shrink = 1.0 - (abs(q2_match["difference"]) / abs(raw_t40_gap))

    temporal = analysis.get("temporal") or []
    overall_ev_gap = None
    if q2 and q3 and q2["n"] and q3["n"]:
        overall_ev_gap = (q2["book_cents"] / q2["n"]) - (q3["book_cents"] / q3["n"])
    bin_gaps = []
    by_bin: dict[tuple[str, str], dict[str, float]] = {}
    for row in temporal:
        key = (row["axis"], row["bin"])
        by_bin.setdefault(key, {})[row["period"]] = row["ev_cents"]
    for pair in by_bin.values():
        if "Q2" in pair and "Q3" in pair:
            bin_gaps.append(abs(pair["Q2"] - pair["Q3"]))
    temporal_shrink = None
    if overall_ev_gap not in {None, 0} and bin_gaps:
        temporal_shrink = 1.0 - (float(sum(bin_gaps) / len(bin_gaps)) / abs(overall_ev_gap))

    within = analysis.get("within") or []
    within_q2 = _mean_abs([row.get("q2_smd") for row in within])
    within_q3 = _mean_abs([row.get("q3_smd") for row in within])

    non_time = [smds.get(name) for name in smds if name not in TIME]
    non_time_mean = _mean_abs(non_time)
    compositional_region = (non_time_mean is not None and non_time_mean >= 0.25) or (
        all_max is not None and all_max >= 0.50 and (price_m or 0) >= 0.40
    )
    matching_explains = match_shrink is not None and match_shrink >= 0.50
    # Q2 vs Q3 always differ on frac_game_elapsed. That is not an explanation
    # unless holding clock fixed shrinks the outcome gap.
    time_flag = bool(temporal_shrink is not None and temporal_shrink >= 0.50)
    market_flag = bool(
        matching_explains
        and ((price_m is not None and price_m >= 0.25) or (open_m is not None and open_m >= 0.25))
    )
    score_flag = bool(
        matching_explains and score_m is not None and score_m >= 0.25
    ) or bool(
        (within_q2 is not None and within_q2 >= 0.25 and (score_m or 0) >= 0.20)
        or (within_q3 is not None and within_q3 >= 0.25 and (score_m or 0) >= 0.20)
    )
    state_flag = bool(
        (non_time_mean is None or non_time_mean < 0.20)
        and (
            (within_q2 is not None and within_q2 >= 0.25)
            or (within_q3 is not None and within_q3 >= 0.25)
        )
    )

    flags: list[str] = []
    if compositional_region and matching_explains:
        flags.append("COMPOSITIONAL")
    if time_flag:
        flags.append("TIME-STRUCTURAL")
    if market_flag or score_flag:
        flags.append("MARKET-STRUCTURAL")
    if state_flag:
        flags.append("STATE-DIFFERENTIAL")
    if len(flags) >= 2:
        label = "JOINT"
    elif len(flags) == 1:
        label = flags[0]
    else:
        label = "UNEXPLAINED"

    return {
        "label": label,
        "flags": flags,
        "mean_abs_smd_q2_q3": all_mean,
        "mean_abs_smd_q2_q3_ex_time": non_time_mean,
        "max_abs_smd_q2_q3": all_max,
        "time_mean_abs_smd": time_m,
        "score_mean_abs_smd": score_m,
        "open_mean_abs_smd": open_m,
        "price_mean_abs_smd": price_m,
        "raw_t40_gap": raw_t40_gap,
        "match_shrink": match_shrink,
        "temporal_shrink": temporal_shrink,
        "within_q2_mean_abs_smd": within_q2,
        "within_q3_mean_abs_smd": within_q3,
        "caveat": (
            "Association on candle-path FIRST80 80→40. Not causation. "
            "Not a live filter. Not a fill."
        ),
    }
