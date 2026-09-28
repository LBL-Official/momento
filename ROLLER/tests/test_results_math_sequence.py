from roller.results_math.drawdown import max_drawdown
from roller.results_math.sequence import recovery_trades, sequence_report, streaks


def test_drawdown_known():
    dd = max_drawdown([10, -5, -20, 8])
    assert dd["max_drawdown_cents"] == 25
    assert dd["ordering"].startswith("entry_ts")


def test_streaks():
    st = streaks([1, 1, -1, -1, -1, 2])
    assert st["longest_winning_streak"] == 2
    assert st["longest_losing_streak"] == 3
    assert st["wins"] == 3
    assert st["losses"] == 3


def test_recovery():
    # peak 10, drop to -15 (dd 25) at index 2, then +8+20 recovers
    assert recovery_trades([10, -5, -20, 8, 20]) == 2


def test_not_outcome_sorted():
    seq = sequence_report([-5, 10, -1])
    assert seq["cumulative_end_cents"] == 4
    assert seq["cumulative_path_cents"] == [-5, 5, 4]


def test_empty_sequence():
    assert sequence_report([])["status"] == "UNAVAILABLE"
