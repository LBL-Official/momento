#!/usr/bin/env python3
"""Causal T_i feature table at ENTRY_DECISION_TIME."""

from __future__ import annotations

from collections import defaultdict

from common import OUT, PRIMARY_ALIGN, read_parquet_rows, utc_now, write_json, write_parquet
from feature_store.trade_state import assemble_trade_state


def main() -> int:
    obs = {r["observation_id"]: r for r in read_parquet_rows(OUT / "observations.parquet")}
    snaps = {r["observation_id"]: r for r in read_parquet_rows(OUT / "entry_snaps.parquet")}
    poss = read_parquet_rows(OUT / "possessions.parquet")
    ov = {r["observation_id"]: r for r in read_parquet_rows(OUT / "possession_market_overlay.parquet")}
    poss_mkt = {r["possession_id"]: r for r in read_parquet_rows(OUT / "possession_market.parquet")}
    by_nba = defaultdict(list)
    for p in poss:
        by_nba[p["nba_game_id"]].append(p)
    for lst in by_nba.values():
        lst.sort(key=lambda x: x["possession_sequence"])

    rows = []
    for oid, o in obs.items():
        s = snaps.get(oid) or {}
        plist = by_nba.get(s.get("nba_game_id"), [])
        entry = int(o["entry_decision_time"])
        pre = [
            p
            for p in plist
            if p.get("wall_start_ts") is not None and p["wall_start_ts"] <= entry
        ]
        if not pre and plist and s.get("snap_idx") is not None:
            pre = [p for p in plist if p["end_idx"] <= (s["snap_idx"] or 0)]
        # Overlays aligned to this observation only (entry market); path uses same-game overlays of pre poss.
        # We stored overlay per observation, not per possession. Use the entry overlay repeatedly is wrong.
        # Reconstruct path overlays as the single entry overlay's during-window is not a path.
        # Use possession-level fields from overlay row only for the snapped possession;
        # for windows, use repeated market_change if we lack per-possession overlay.
        # Build per-possession overlay index by possession_id from all observations in same game:
        # fallback: empty path except current overlay.
        pre_ov = [poss_mkt.get(p["possession_id"]) or {"alignment_quality": "PARTIAL_ALIGNMENT"} for p in pre]
        cur = ov.get(oid)
        rec = assemble_trade_state(o, s, pre, cur, pre_ov)
        rows.append(rec)

    write_parquet(OUT / "features.parquet", rows)
    n_primary = sum(1 for r in rows if r.get("primary_set"))
    meta = []
    skip = {
        "observation_id",
        "event_id",
        "ticker",
        "team_code",
        "game_date",
        "dataset_split",
        "entry_decision_time",
        "Y_40_CLOSE",
        "SURVIVE_40",
        "Y_40_WICK",
        "expiration_result_yes",
        "alignment_confidence",
        "alignment_reason",
        "game_phase",
        "possession_id",
        "maker_fill_confidence",
        "time_to_40_minutes",
        "primary_set",
        "z_uses_future_possession",
        "l2_invented",
        "wall_clock_claimed_observed",
    }
    sample = rows[0] if rows else {}
    for k in sample:
        if k in skip:
            continue
        family = "other"
        if k.startswith("mkt_"):
            family = "market_path" if any(k.endswith(f"{w}p") for w in (1, 3, 5, 10, 20, 30)) or "change" in k or "momentum" in k else "market_state"
        elif k.startswith("coupling_"):
            family = "coupling"
        elif k.startswith("pts_") or k.startswith("net_") or k.startswith("abs_score") or k.startswith("turnovers_") or k.startswith("oreb_") or k.startswith("fta_") or k.startswith("lead_changes_") or k.startswith("timeouts_") or k.startswith("scoring_") or k.startswith("directional_") or k.startswith("n_window_") or k.startswith("off_eff_"):
            family = "possession_path"
        elif k.startswith("game_") or k.startswith("net_score") or k.startswith("score_diff") or k.startswith("lead_reversal") or k.startswith("possession_outcome"):
            family = "game_dynamics"
        elif k in {
            "quarter",
            "official_time_remaining_s",
            "game_elapsed_seconds",
            "game_completion_pct",
            "possession_number",
            "estimated_possessions_remaining",
            "score_differential",
            "team_is_leading",
            "home_score",
            "away_score",
            "possession_team",
        }:
            family = "game_state"
        role = "TARGET_ONLY" if k in {"expiration_result_yes"} else "PREDICTOR"
        meta.append(
            {
                "feature_name": k,
                "feature_family": family,
                "causal": True,
                "source_ts_rule": "source_ts ≤ ENTRY_DECISION_TIME",
                "observed_or_derived": "DERIVED_PROXY"
                if family in {"game_dynamics", "coupling"}
                else ("OBSERVED" if family in {"game_state", "possession_path", "market_state"} else "MIXED"),
                "role": role,
                "l2_available": False,
            }
        )
    write_json(OUT / "feature_metadata.json", {"n": len(meta), "rows": meta})
    write_json(
        OUT / "features_summary.json",
        {
            "written_utc": utc_now(),
            "n": len(rows),
            "n_primary": n_primary,
            "n_columns": len(rows[0]) if rows else 0,
            "n_predictor_metadata": len(meta),
        },
    )
    print(f"features n={len(rows)} primary={n_primary} cols={len(rows[0]) if rows else 0}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
