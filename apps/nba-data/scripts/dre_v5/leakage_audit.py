"""Market / game / label leakage audits. Halt on any leak."""

from __future__ import annotations

from . import config as C


def audit(feature_cols: list[str], pace_audit: dict) -> dict:
    market, game, labels = [], [], []
    for c in feature_cols:
        for bad in C.FORBIDDEN_IN_FEATURES:
            if c == bad or c.startswith(bad) or bad in c:
                if "actual_remaining" in c:
                    game.append(c)
                elif c.startswith("future_") or "future_" in c:
                    market.append(c)
                else:
                    labels.append(c)
    market = sorted(set(market))
    game = sorted(set(game))
    labels = sorted(set(labels))
    if pace_audit.get("actual_remaining_used_as_feature"):
        game.append("n_hat_remaining_prior_used_actual_remaining")
    prior_only = C.PACE_CHRONOLOGY == "COMPLETED_BEFORE_G_START_WALL_END_TS" and not pace_audit.get(
        "actual_remaining_used_as_feature"
    )
    return {
        "market_lookahead": {"status": "PASS" if not market else "FAIL", "n": len(market), "items": market},
        "game_lookahead": {"status": "PASS" if not game else "FAIL", "n": len(game), "items": game},
        "label_leakage": {"status": "PASS" if not labels else "FAIL", "n": len(labels), "items": labels},
        "prior_pace": {
            "status": "PASS" if prior_only else "FAIL",
            "chronology": C.PACE_CHRONOLOGY,
            "actual_remaining_used_as_feature": bool(pace_audit.get("actual_remaining_used_as_feature")),
        },
        "features": list(feature_cols),
        "rule": "Could this value have been known at possession state n?",
        "schema_version": C.SCHEMA_VERSION,
    }
