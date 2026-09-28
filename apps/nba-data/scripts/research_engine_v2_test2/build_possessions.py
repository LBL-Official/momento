#!/usr/bin/env python3
"""Build canonical possession table + snap first-80 to last pre-entry possession."""

from __future__ import annotations

import sys
from collections import defaultdict

from common import (
    OUT,
    gpe_pbp,
    load_crosswalk,
    read_parquet_rows,
    utc_now,
    write_json,
    write_parquet,
)
from possessions import build_possessions


def main() -> int:
    obs = read_parquet_rows(OUT / "observations.parquet")
    xwalk = load_crosswalk()
    by_nba = defaultdict(list)
    unmatched = 0
    no_pbp = 0
    for o in obs:
        cw = xwalk.get(o["event_id"]) or {}
        nba_id = cw.get("nba_game_id")
        if cw.get("match_status") != "MATCHED" or not nba_id:
            unmatched += 1
            continue
        by_nba[nba_id].append(o)

    all_poss = []
    align_rows = []
    issue_sum = {
        "impossible_score_jumps": 0,
        "nonmonotonic_clock": 0,
        "open_possession_at_end": 0,
        "duplicate_ids": 0,
        "unmapped_action_types": {},
        "games_built": 0,
        "games_no_pbp": 0,
    }

    for nba_id, olist in by_nba.items():
        pbp = gpe_pbp.load_pbp(nba_id)
        box = gpe_pbp.load_box(nba_id)
        header = gpe_pbp.box_header(box)
        if not pbp:
            no_pbp += 1
            issue_sum["games_no_pbp"] += 1
            continue
        actions = gpe_pbp.enrich_actions(gpe_pbp.actions_of(pbp), header)
        poss, issues = build_possessions(nba_id, actions)
        issue_sum["games_built"] += 1
        issue_sum["impossible_score_jumps"] += issues["impossible_score_jumps"]
        issue_sum["nonmonotonic_clock"] += issues["nonmonotonic_clock"]
        issue_sum["open_possession_at_end"] += issues["open_possession_at_end"]
        issue_sum["duplicate_ids"] += issues["duplicate_ids"]
        for k, v in issues["unmapped_action_types"].items():
            issue_sum["unmapped_action_types"][k] = issue_sum["unmapped_action_types"].get(k, 0) + v
        all_poss.extend(poss)

        residuals = gpe_pbp.replay_residuals(actions)
        for o in olist:
            entry_ts = int(o["entry_decision_time"])
            snap = gpe_pbp.snap_to_entry(actions, entry_ts)
            conf, reason = gpe_pbp.classify_confidence(actions, snap, entry_ts, header, residuals)
            # Last possession with wall_start <= entry (or elapsed fallback).
            pre = [
                p
                for p in poss
                if (p.get("wall_start_ts") is not None and p["wall_start_ts"] <= entry_ts)
                or (
                    p.get("wall_start_ts") is None
                    and p.get("elapsed_start_s") is not None
                    and snap.get("snap_idx") is not None
                    and p["end_idx"] <= snap["snap_idx"]
                )
            ]
            last = pre[-1] if pre else None
            post_leak = [
                p
                for p in poss
                if p.get("wall_start_ts") is not None and p["wall_start_ts"] > entry_ts
            ]
            align_rows.append(
                {
                    "observation_id": o["observation_id"],
                    "event_id": o["event_id"],
                    "nba_game_id": nba_id,
                    "entry_decision_time": entry_ts,
                    "alignment_model": "PERIOD_BOUNDED_LINEAR_GAME_CLOCK",
                    "per_play_wall_clock_observed": False,
                    "alignment_confidence": conf,
                    "alignment_reason": reason,
                    "game_phase": snap.get("game_phase"),
                    "snap_idx": snap.get("snap_idx"),
                    "possession_id": None if last is None else last["possession_id"],
                    "possession_sequence": None if last is None else last["possession_sequence"],
                    "n_possessions_pre_entry": len(pre),
                    "n_possessions_post_entry": len(post_leak),
                    "leakage_post_entry_in_z": False,  # we snap pre-entry only
                    "Y_40_CLOSE": o["Y_40_CLOSE"],
                    "dataset_split": o["dataset_split"],
                }
            )

    write_parquet(OUT / "possessions.parquet", all_poss)
    write_parquet(OUT / "entry_snaps.parquet", align_rows)
    n_dup = issue_sum["duplicate_ids"]
    write_json(
        OUT / "possession_validation.json",
        {
            "written_utc": utc_now(),
            "n_possessions": len(all_poss),
            "n_snaps": len(align_rows),
            "unmatched_observations": unmatched,
            "no_pbp": no_pbp,
            "issues": issue_sum,
            "duplicate_possession_ids": n_dup,
        },
    )
    print(
        f"possessions n={len(all_poss)} snaps={len(align_rows)} "
        f"unmatched={unmatched} no_pbp={no_pbp} dup={n_dup}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
