"""Asked-six path-window locks. Do not fabricate missing +4/+5 minutes."""

from __future__ import annotations

from roller.superasi.path_windows import (
    LOCK_OFFSET0_SUM,
    LOCK_OFFSET_M1_SUM,
    LOCK_PATH_LOSSES,
    LOCK_PRE_38_40,
    aggregate,
    load_asked_six_windows,
    validate_asked_six_locks,
)


def test_asked_six_window_locks():
    windows = load_asked_six_windows()
    validate_asked_six_locks(windows)
    agg = aggregate(windows)
    assert agg["path_loss_n"] == LOCK_PATH_LOSSES
    assert agg["offsets"]["0"]["sum"] == LOCK_OFFSET0_SUM
    assert agg["offsets"]["-1"]["sum"] == LOCK_OFFSET_M1_SUM
    assert agg["pre_t40_38_40_trades"] == LOCK_PRE_38_40
    # Spec 3289 vs locked CSV 3285: missing minutes stay absent / UNAVAILABLE.
    assert agg["n_window_rows"] == 3285
    assert agg["offsets"]["4"]["n"] == 297
    assert agg["offsets"]["5"]["n"] == 297
