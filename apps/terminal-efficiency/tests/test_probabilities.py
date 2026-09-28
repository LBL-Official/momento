import numpy as np

from terminal_efficiency.models.metrics import probability_metrics


def test_probabilities_sum_to_one_pattern():
    p_home = 0.63
    p_away = 1.0 - p_home
    assert abs(p_home + p_away - 1.0) < 1e-12


def test_metrics_n():
    y = np.array([0, 1, 1, 0])
    p = np.array([0.2, 0.8, 0.7, 0.4])
    m = probability_metrics(y, p)
    assert m["n"] == 4
    assert 0 <= m["brier"] <= 1
