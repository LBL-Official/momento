"""78/67 Ballhog lock and the unchanged 80/40 policy."""

from fractions import Fraction

from roller.ballhog.arithmetic import lock_cents as lock_80
from roller.ballhog.policy import load_policy as load_80
from roller.ballhog_first78.arithmetic import lock_cents
from roller.ballhog_first78.api import handle_health
from roller.ballhog_first78.policy import load_policy
from roller.tk_ultra.assessment import assess_binary
from roller.tk_ultra.relationship import complementary


def test_paired_unit_at_67_locks_22_minus_price():
    assert lock_cents(67) == 22 - 67
    assert lock_cents(67) == -45


def test_first80_policy_and_lock_are_unchanged():
    policy = load_80()
    assert policy.lock_gain_cents == 20
    assert policy.price_grid == tuple(range(35, 46))
    assert lock_80(40) == -20


def test_first78_policy_is_the_62_through_72_grid():
    policy = load_policy()
    assert policy.entry_cents == 78
    assert policy.lock_gain_cents == 22
    assert policy.price_grid == tuple(range(62, 73))
    assert policy.risk_metric == "T67_RISK_PROXY"
    assert policy.live_execution is False


def test_health_keeps_the_books_apart():
    health = handle_health()
    austin_n = health["austin"]["n"]
    choosin_n = health["choosin_texas"]["n"]
    assert austin_n == 569
    assert choosin_n not in (None, 569, 604, 936)
    assert health["lock"] == "22-p"
    assert health["choosin_texas"]["universe"] == "DERIVED_FOUR_FIRST78"


def test_anchors_78_and_22_are_complementary():
    assert complementary(Fraction(78), Fraction(22))
    valid = assess_binary(
        {
            "a_entry_cents": "78",
            "a_stop_cents": "67",
            "a_anchor_cents": "78",
            "b_anchor_cents": "22",
            "a_ref_cents": "70",
            "b_observed_cents": "28",
        }
    )
    assert valid["relationship"]["anchor_validity"] == "COMPLEMENT_100"
    invalid = assess_binary(
        {
            "a_anchor_cents": "78",
            "b_anchor_cents": "40",
            "a_ref_cents": "70",
            "b_observed_cents": "28",
        }
    )
    assert invalid["relationship"]["status"] == "ANCHOR_INVALID"
