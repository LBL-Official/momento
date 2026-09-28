"""Market / game / label leakage audits. Halt on any leak."""

from __future__ import annotations

from . import config as C
from .features import FORBIDDEN


def audit(feature_cols: list[str]) -> dict:
    market, game, labels = [], [], []
    for c in feature_cols:
        for bad in FORBIDDEN:
            if c.startswith(bad) or bad in c:
                if c.startswith("future_") or c.startswith("y_min") or c.startswith("y_rec") or c.startswith("y_det"):
                    market.append(c)
                if "actual_remaining" in c:
                    game.append(c)
                if c.startswith("y_") or c.startswith("path_class") or c.startswith("dd_") or c.startswith("ue_"):
                    labels.append(c)
    # also catch leftover policy objects
    for c in feature_cols:
        if "target_delta" in c or c.startswith("h_"):
            labels.append(c)
    market = sorted(set(market))
    game = sorted(set(game))
    labels = sorted(set(labels))
    return {
        "market_lookahead": {"status": "PASS" if not market else "FAIL", "n": len(market), "items": market},
        "game_lookahead": {"status": "PASS" if not game else "FAIL", "n": len(game), "items": game},
        "label_leakage": {"status": "PASS" if not labels else "FAIL", "n": len(labels), "items": labels},
        "features": list(feature_cols),
        "rule": "Could this value have been known at possession state n?",
        "schema_version": C.SCHEMA_VERSION,
    }
