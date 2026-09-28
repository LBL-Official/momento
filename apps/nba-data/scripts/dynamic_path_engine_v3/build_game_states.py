#!/usr/bin/env python3
"""Post-entry game states via PERIOD_BOUNDED_LINEAR_GAME_CLOCK. Quality, not a filter."""

from __future__ import annotations

import bisect
import sys
from collections import defaultdict
from functools import lru_cache

from common import OUT, load_crosswalk, read_parquet_rows, write_parquet
from pbp_align import (
    box_header,
    enrich_actions,
    load_box,
    load_pbp,
    replay_residuals,
    team_scores,
)


@lru_cache(maxsize=2048)
def enriched(nba_id: str):
    pbp = load_pbp(nba_id)
    header = box_header(load_box(nba_id))
    actions = enrich_actions((pbp or {}).get("game", {}).get("actions") or [], header)
    index = [i for i, a in enumerate(actions) if a["modeled_wall_ts"] is not None]
    ts = [actions[i]["modeled_wall_ts"] for i in index]
    residuals = replay_residuals(actions)
    return actions, tuple(index), tuple(ts), header, tuple(residuals)


def snap_at(actions, index, ts_list, t):
    if not ts_list:
        return None
    k = bisect.bisect_right(ts_list, t) - 1
    if k < 0:
        return None
    return actions[index[k]]


def main() -> int:
    trades = {t["trade_id"]: t for t in read_parquet_rows(OUT / "first80_trades.parquet")}
    panel = read_parquet_rows(OUT / "post_entry_state_panel.parquet")
    xwalk = load_crosswalk()
    by_trade = defaultdict(list)
    for p in panel:
        by_trade[p["trade_id"]].append(p)
    rows = []
    for tid, plist in by_trade.items():
        tr = trades[tid]
        cw = xwalk.get(tr["event_id"]) or {}
        nba_id = cw.get("nba_game_id")
        code = (tr.get("team_code") or "").upper()
        home = (tr.get("home_team_code") or "").upper()
        team_home = True if code and code == home else False if code else None
        entry_erow = None
        pack = None
        if nba_id and cw.get("match_status") == "MATCHED":
            pack = enriched(nba_id)
            actions, index, ts_list, header, residuals = pack
            index = list(index)
            ts_list = list(ts_list)
            pack = (actions, index, ts_list, header, residuals)
            residuals = list(residuals)
            first_start = next(
                (
                    a["knot_wall_ts"]
                    for a in actions
                    if (a.get("actionType") or "").lower() == "period"
                    and (a.get("subType") or "").lower() == "start"
                    and a.get("period") == 1
                    and a.get("knot_wall_ts")
                ),
                None,
            )
            last_end = None
            for a in actions:
                if (a.get("actionType") or "").lower() == "period" and (
                    a.get("subType") or ""
                ).lower() == "end" and a.get("knot_wall_ts"):
                    last_end = a["knot_wall_ts"]
            med_res = sorted(residuals)[len(residuals) // 2] if residuals else None
            replay_ok = med_res is None or med_res <= 180
            n_rep = len(residuals)
            entry_erow = snap_at(actions, index, ts_list, int(tr["entry_decision_time"]))
        else:
            first_start = last_end = None
            replay_ok = False
            n_rep = 0
            med_res = None
        timeline = []
        if pack is not None and team_home is not None:
            actions, index, ts_list, header, residuals = pack
            for ix in index:
                a = actions[ix]
                w = a.get("modeled_wall_ts")
                if w is None:
                    continue
                ts_s, os_ = team_scores(a, team_home)
                timeline.append((w, ts_s, os_))
            timeline.sort(key=lambda x: x[0])
        plist = sorted(plist, key=lambda p: int(p["state_timestamp"]))
        lead_ch = max_lead = max_def = time_lead = time_trail = None
        run_team = run_opp = 0
        cur_run_t = cur_run_o = 0
        prev_diff = None
        n_ev = 0
        j_ev = 0
        entry_ts = int(tr["entry_decision_time"])
        for p in plist:
            ts = int(p["state_timestamp"])
            rec = {
                "trade_id": tid,
                "state_timestamp": ts,
                "nba_game_id": nba_id,
                "game_feature_status": "UNAVAILABLE",
                "alignment_confidence": "UNUSABLE",
                "alignment_reason": "NO_PBP",
                "alignment_model": "PERIOD_BOUNDED_LINEAR_GAME_CLOCK",
                "per_play_wall_clock_observed": False,
                "feature_maximum_source_timestamp": ts,
            }
            if pack is None or team_home is None:
                rec["alignment_reason"] = "UNMATCHED" if not nba_id else "NO_TEAM"
                rows.append(rec)
                continue
            actions, index, ts_list, header, residuals = pack
            row = snap_at(actions, index, ts_list, ts)
            if first_start is not None and ts < first_start:
                rec["game_phase"] = "GAME_NOT_STARTED"
                rec["alignment_confidence"] = "MEDIUM"
                rec["alignment_reason"] = "GAME_NOT_STARTED"
            elif last_end is not None and ts > last_end + 30:
                rec["game_phase"] = "GAME_ENDED"
                rec["alignment_confidence"] = "MEDIUM"
                rec["alignment_reason"] = "GAME_ENDED"
            elif row is None:
                rec["game_phase"] = "UNALIGNED"
                rec["alignment_confidence"] = "UNUSABLE"
                rec["alignment_reason"] = "NO_MODELED_WALL"
            else:
                rec["game_phase"] = "IN_PERIOD"
                if n_rep >= 2 and replay_ok:
                    rec["alignment_confidence"] = "HIGH"
                    rec["alignment_reason"] = "IN_PERIOD_REPLAY_VALIDATED"
                elif n_rep >= 2 and not replay_ok:
                    rec["alignment_confidence"] = "MEDIUM"
                    rec["alignment_reason"] = "IN_PERIOD_REPLAY_RESIDUAL"
                else:
                    rec["alignment_confidence"] = "HIGH"
                    rec["alignment_reason"] = "IN_PERIOD_BOUNDS"
            conf = rec["alignment_confidence"]
            team_s = opp_s = None
            if row is not None:
                team_s, opp_s = team_scores(row, team_home)
                rec.update(
                    {
                        "quarter": row.get("period"),
                        "period_seconds_remaining": row.get("remaining_s"),
                        "game_seconds_elapsed": row.get("elapsed_s"),
                        "team_score": team_s,
                        "opponent_score": opp_s,
                        "score_differential": None if team_s is None else team_s - opp_s,
                        "total_points": None if team_s is None else team_s + opp_s,
                        "snap_modeled_wall_ts": row.get("modeled_wall_ts"),
                    }
                )
                if entry_erow is not None and team_s is not None:
                    et, eo = team_scores(entry_erow, team_home)
                    if et is not None:
                        rec["points_scored_since_entry"] = team_s - et
                        rec["points_allowed_since_entry"] = opp_s - eo
                        rec["net_score_since_entry"] = (team_s - et) - (opp_s - eo)
                        rec["score_diff_at_entry"] = et - eo
                        rec["lead_drawdown_since_entry"] = max(0, (et - eo) - (team_s - opp_s))
                if conf in ("HIGH", "MEDIUM") and team_s is not None:
                    rec["game_feature_status"] = "AVAILABLE"
            while j_ev < len(timeline) and timeline[j_ev][0] <= ts:
                w, ts_s, os_ = timeline[j_ev]
                j_ev += 1
                if w <= entry_ts or ts_s is None or os_ is None:
                    continue
                n_ev += 1
                d = ts_s - os_
                if max_lead is None or d > max_lead:
                    max_lead = d
                if max_def is None or d < max_def:
                    max_def = d
                if prev_diff is not None:
                    if prev_diff <= 0 < d or prev_diff >= 0 > d:
                        lead_ch = 0 if lead_ch is None else lead_ch
                        lead_ch += 1
                    ddelt = d - prev_diff
                    if ddelt > 0:
                        cur_run_t += ddelt
                        cur_run_o = 0
                        run_team = max(run_team, cur_run_t)
                    elif ddelt < 0:
                        cur_run_o += -ddelt
                        cur_run_t = 0
                        run_opp = max(run_opp, cur_run_o)
                prev_diff = d
                if d > 0:
                    time_lead = 0 if time_lead is None else time_lead
                    time_lead += 1
                elif d < 0:
                    time_trail = 0 if time_trail is None else time_trail
                    time_trail += 1
            rec["lead_changes_since_entry"] = lead_ch
            rec["max_lead_since_entry"] = max_lead
            rec["max_deficit_since_entry"] = max_def
            rec["events_since_entry"] = n_ev
            rec["largest_team_run_since_entry"] = run_team
            rec["largest_opp_run_since_entry"] = run_opp
            rec["score_events_leading"] = time_lead
            rec["score_events_trailing"] = time_trail
            if rec.get("score_differential") is not None and max_lead is not None:
                rec["lead_vs_max_lead"] = rec["score_differential"] - max_lead
            rows.append(rec)
    write_parquet(OUT / "post_entry_game_states.parquet", rows)
    n_av = sum(1 for r in rows if r.get("game_feature_status") == "AVAILABLE")
    print(f"game_states n={len(rows)} available={n_av}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
