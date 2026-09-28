"""Formal no-lookahead audit. Fail the pipeline on future candles or future PBP features."""

from __future__ import annotations

from . import config as C
from .feature_builder import FAMILIES, FORBIDDEN_AS_FEATURES


LABEL_PREFIXES = ("y_", "future_", "recovery_from_current", "recovery_from_entry", "jump_")
EVAL_ONLY = frozenset(
    {
        "actual_remaining_possessions",
        "actual_remaining_possessions_eval_only",
        "terminal_pnl_hold",
        "terminal_pnl_hold_evidence",
        "expiration_result_yes",
    }
)


def classify(name: str) -> str:
    if name in EVAL_ONLY or name in FORBIDDEN_AS_FEATURES:
        return "EVALUATION_ONLY_NOT_A_FEATURE"
    if name.startswith(LABEL_PREFIXES) or name.startswith("future_"):
        return "FUTURE_DERIVED_LABEL"
    if "estimated_remaining" in name or name == "estimated_remaining_possessions":
        return "ESTIMATE_AT_STATE"
    return "OBSERVED_AT_STATE"


def audit(panel: list[dict]) -> dict:
    rows = []
    used = {c for cols in FAMILIES.values() for c in cols}
    sample_keys = set(panel[0].keys()) if panel else set()
    names = sorted(used | {k for k in sample_keys if k.startswith(LABEL_PREFIXES)} | set(EVAL_ONLY))

    market_lookahead = 0
    game_lookahead = 0
    illegal_features = []

    for name in names:
        kind = classify(name)
        used_as_feat = name in used
        passes = True
        notes = ""
        if used_as_feat and kind in ("FUTURE_DERIVED_LABEL", "EVALUATION_ONLY_NOT_A_FEATURE"):
            passes = False
            illegal_features.append(name)
            if name.startswith("future_") or name.startswith("y_min") or name.startswith("y_"):
                market_lookahead += 1
            if "actual_remaining" in name or name.startswith("future_"):
                game_lookahead += 1
            notes = "FEATURE USES INFORMATION NOT AVAILABLE AT STATE n"
        elif kind == "ESTIMATE_AT_STATE":
            notes = "PADE V1 remaining-possession ESTIMATE. Biased. Not a known clock."
        elif kind == "FUTURE_DERIVED_LABEL":
            notes = "Label only. Not a feature."
        elif kind == "EVALUATION_ONLY_NOT_A_FEATURE":
            notes = "Retrospective diagnostic / settlement label. Forbidden as feature."
        else:
            notes = "Constructed from PADE as-of state at possession n."

        rows.append(
            {
                "feature_name": name,
                "source_timestamp_or_index": "PADE_as_of_possession_n",
                "state_timestamp_or_index": "possession_index + market_observation_timestamp",
                "availability": kind,
                "used_as_model_feature": used_as_feat,
                "passes_no_lookahead": passes,
                "notes": notes,
            }
        )

    # Structural checks: no family feature is a future_* / y_* / actual remaining.
    for fam, cols in FAMILIES.items():
        for c in cols:
            if c.startswith("y_") or c.startswith("future_") or c in EVAL_ONLY:
                illegal_features.append(f"{fam}:{c}")
                market_lookahead += 1

    gate_c = "PASS" if market_lookahead == 0 and not illegal_features else "FAIL"
    gate_d = "PASS" if game_lookahead == 0 and not any("actual_remaining" in x for x in illegal_features) else "FAIL"
    if illegal_features:
        gate_d = "FAIL"

    return {
        "rows": rows,
        "illegal_features": illegal_features,
        "market_lookahead_count": market_lookahead,
        "game_lookahead_count": game_lookahead,
        "gate_c": gate_c,
        "gate_d": gate_d,
        "n_features_audited": len(rows),
        "rule": "Could this value have been known at possession state n?",
    }
