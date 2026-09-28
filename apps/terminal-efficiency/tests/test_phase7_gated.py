import pytest

from terminal_efficiency.pipeline import Phase7NotAuthorized, evaluate_oos


def test_phase7_blocked():
    with pytest.raises(Phase7NotAuthorized):
        evaluate_oos("2025-2026")
