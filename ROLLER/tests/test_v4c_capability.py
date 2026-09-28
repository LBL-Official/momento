from __future__ import annotations

from roller.v4c.capability import constructible, instance_status


def test_seven_conjuncts_required():
    kwargs = dict(
        data_available=True,
        information_regime_valid=True,
        point_in_time_valid=True,
        definition_exists=True,
        definition_implemented=True,
        identity_unambiguous=True,
        proxy_prohibition_satisfied=True,
    )
    assert constructible(**kwargs)
    for key in kwargs:
        broken = dict(kwargs)
        broken[key] = False
        assert not constructible(**broken)


def test_instance_status_from_v4b():
    assert instance_status("valid", "IMPLEMENTED") == "IMPLEMENTED"
    assert instance_status("valid", "PARTIAL") == "PARTIAL"
    assert instance_status("MISSING_K", "IMPLEMENTED") == "DATA_UNAVAILABLE"
    assert instance_status("TIME_GAP", "IMPLEMENTED") == "INSUFFICIENT_SUPPORT"
    assert instance_status("RECONCILIATION_FAILED", "IMPLEMENTED") == "INVALID_INPUT"
