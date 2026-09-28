"""Chronological game-level splits. A game belongs to exactly one split."""

from __future__ import annotations

from collections import defaultdict

from . import config as C


def split_manifest(panel: list[dict]) -> tuple[list[dict], dict]:
    games = {}
    for r in panel:
        eid = r["event_id"]
        g = games.setdefault(
            eid,
            {
                "event_id": eid,
                "game_date": r.get("game_date"),
                "split": r.get("dataset_split"),
                "nba_game_id": r.get("nba_game_id"),
                "n_possession_rows": 0,
            },
        )
        g["n_possession_rows"] += 1
        if g["split"] != r.get("dataset_split"):
            g["conflict"] = True

    rows = sorted(games.values(), key=lambda x: (x.get("game_date") or "", x["event_id"]))
    by_split = defaultdict(set)
    for g in rows:
        by_split[g["split"]].add(g["event_id"])
    overlap = (
        (by_split["TRAIN"] & by_split["VALIDATION"])
        | (by_split["TRAIN"] & by_split["OOS"])
        | (by_split["VALIDATION"] & by_split["OOS"])
    )
    status = "PASS" if not overlap else "FAIL"
    summary = {
        "gate": "E",
        "status": status,
        "n_games": len(rows),
        "train_games": len(by_split["TRAIN"]),
        "validation_games": len(by_split["VALIDATION"]),
        "oos_games": len(by_split["OOS"]),
        "overlap_games": sorted(overlap),
        "rule": "game-level chronological isolation; no row-level random split",
        "train_end": C.SPLIT_TRAIN_END,
        "validation_end": C.SPLIT_VAL_END,
    }
    return rows, summary
