"""Evaluation labels. Never used as features."""

from __future__ import annotations

LABELS = {
    "terminal": ["y_settle_yes"],
    "path_bins": ["path_bin_5", "path_bin_10", "path_bin_end"],
    "recovery": ["y_rec_ge_10_k5", "y_rec_ge_10_end", "y_rec_ge_30_end"],
    "downside": ["y_det_ge_10_end", "dd_end", "dd_5"],
    "jump_proxy": ["y_jump_40"],
    "v2_baseline": ["target_delta_M3_A", "target_delta_M3_D"],
}
