"""Market / game / label leakage audits."""

from __future__ import annotations

from . import config as C
from .features import FEATURE_COLS, FORBIDDEN_FEATURES


def audit(feature_cols=None) -> dict:
    cols = list(feature_cols or FEATURE_COLS)
    illegal = []
    for c in cols:
        for bad in FORBIDDEN_FEATURES:
            if c.startswith(bad) or bad in c:
                illegal.append(c)
    market = [c for c in cols if c.startswith("future_") or c.startswith("y_min") or c.startswith("y_rec") or c.startswith("y_det")]
    game = [c for c in cols if "actual_remaining" in c]
    labels_as_feat = [c for c in cols if c.startswith("y_") or c.startswith("path_bin")]
    return {
        "market_lookahead": {"status": "PASS" if not market and not illegal else "FAIL", "n": len(market), "items": market},
        "game_lookahead": {"status": "PASS" if not game else "FAIL", "n": len(game), "items": game},
        "label_leakage": {"status": "PASS" if not labels_as_feat and not illegal else "FAIL", "n": len(labels_as_feat) + len(illegal), "items": labels_as_feat + illegal},
        "features": cols,
        "rule": "Could this value have been known at possession state n?",
        "schema_version": C.SCHEMA_VERSION,
    }
