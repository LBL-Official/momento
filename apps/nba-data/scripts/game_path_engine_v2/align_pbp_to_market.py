#!/usr/bin/env python3
"""Align PBP to first-80 market timestamps. Modeled walls; never invented as observed."""

from __future__ import annotations

import sys

from common import (
    OUT,
    load_crosswalk,
    read_parquet_rows,
    utc_now,
    write_json,
    write_parquet,
)
from pbp import (
    box_header,
    classify_confidence,
    enrich_actions,
    load_box,
    load_pbp,
    parse_duration_seconds,
    parse_iso_dt,
    replay_residuals,
    snap_to_entry,
)


def main() -> int:
    obs_path = OUT / "observations.parquet"
    if not obs_path.exists():
        print("missing observations.parquet", file=sys.stderr)
        return 1
    obs = read_parquet_rows(obs_path)
    xwalk = load_crosswalk()
    rows = []
    duration_err = []
    tip_lag = []
    residual_all = []
    n_matched = 0
    n_pbp = 0
    for o in obs:
        event_id = o["event_id"]
        cw = xwalk.get(event_id) or {}
        nba_id = cw.get("nba_game_id")
        match_status = cw.get("match_status")
        entry_ts = int(o["entry_decision_time"])
        rec = {
            "observation_id": o["observation_id"],
            "event_id": event_id,
            "nba_game_id": nba_id,
            "crosswalk_status": match_status,
            "entry_decision_time": entry_ts,
            "alignment_model": "PERIOD_BOUNDED_LINEAR_GAME_CLOCK",
            "per_play_wall_clock_observed": False,
            "tip_inferred_from_kalshi_open": False,
        }
        if match_status != "MATCHED" or not nba_id:
            rec.update(
                {
                    "alignment_confidence": "UNUSABLE",
                    "alignment_reason": "UNMATCHED_CROSSWALK",
                    "snap_idx": None,
                    "game_phase": "UNALIGNED",
                }
            )
            rows.append(rec)
            continue
        n_matched += 1
        pbp = load_pbp(nba_id)
        box = load_box(nba_id)
        header = box_header(box)
        if not pbp:
            rec.update(
                {
                    "alignment_confidence": "UNUSABLE",
                    "alignment_reason": "NO_PBP",
                    "snap_idx": None,
                    "game_phase": "UNALIGNED",
                }
            )
            rows.append(rec)
            continue
        n_pbp += 1
        actions = enrich_actions(pbp.get("game", {}).get("actions") or [], header)
        snap = snap_to_entry(actions, entry_ts)
        residuals = replay_residuals(actions)
        residual_all.extend(residuals)
        conf, reason = classify_confidence(actions, snap, entry_ts, header, residuals)
        tip = parse_iso_dt(header.get("gameTimeUTC"))
        tip_ts = int(tip.timestamp()) if tip else None
        first_start = snap.get("first_period_start_ts")
        last_end = snap.get("last_period_end_ts")
        box_dur = parse_duration_seconds(header.get("duration"))
        if first_start and last_end and box_dur:
            duration_err.append((last_end - first_start) - box_dur)
        if tip_ts and first_start:
            tip_lag.append(first_start - tip_ts)
        rec.update(
            {
                "alignment_confidence": conf,
                "alignment_reason": reason,
                "snap_idx": snap.get("snap_idx"),
                "game_phase": snap.get("game_phase"),
                "snap_modeled_wall_ts": snap.get("snap_modeled_wall_ts"),
                "snap_lag_s": snap.get("snap_lag_s"),
                "first_period_start_ts": first_start,
                "last_period_end_ts": last_end,
                "gameTimeUTC": header.get("gameTimeUTC"),
                "gameEt": header.get("gameEt"),
                "box_duration": header.get("duration"),
                "n_replay_residuals": len(residuals),
                "median_replay_residual_s": (
                    sorted(residuals)[len(residuals) // 2] if residuals else None
                ),
                "tip_to_q1_start_s": None if not tip_ts or not first_start else first_start - tip_ts,
                "n_actions": len(actions),
            }
        )
        rows.append(rec)

    write_parquet(OUT / "alignment.parquet", rows)

    # merge confidence onto observations
    by_id = {r["observation_id"]: r for r in rows}
    merged = []
    for o in obs:
        a = by_id[o["observation_id"]]
        o = dict(o)
        o["nba_game_id"] = a.get("nba_game_id")
        o["alignment_confidence"] = a.get("alignment_confidence")
        o["alignment_reason"] = a.get("alignment_reason")
        o["alignment_model"] = a.get("alignment_model")
        o["game_phase"] = a.get("game_phase")
        o["snap_idx"] = a.get("snap_idx")
        o["snap_modeled_wall_ts"] = a.get("snap_modeled_wall_ts")
        o["snap_lag_s"] = a.get("snap_lag_s")
        merged.append(o)
    write_parquet(OUT / "observations.parquet", merged)

    from collections import Counter

    conf_c = Counter(r.get("alignment_confidence") for r in rows)
    write_json(
        OUT / "alignment_pass_summary.json",
        {
            "written_utc": utc_now(),
            "n": len(rows),
            "crosswalk_matched": n_matched,
            "pbp_loaded": n_pbp,
            "confidence_counts": dict(conf_c),
            "median_tip_to_q1_s": (
                sorted(tip_lag)[len(tip_lag) // 2] if tip_lag else None
            ),
            "median_duration_error_s": (
                sorted(duration_err)[len(duration_err) // 2] if duration_err else None
            ),
            "median_replay_residual_s": (
                sorted(residual_all)[len(residual_all) // 2] if residual_all else None
            ),
            "n_replay_residuals": len(residual_all),
        },
    )
    print("alignment", dict(conf_c), "pbp", n_pbp)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
