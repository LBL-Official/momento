"""Frozen MLB dated FT75 / TE lead+1 measurement object.

This is the canonical regression fixture. It is not an edge claim.
If warehouse last-trade coverage inside the window changes, this test
must fail — do not silently update N to make it pass.
"""

from __future__ import annotations

import pytest

from roller.config import RollerConfig
from roller.research_query.availability import baseball_warehouse_ready
from roller.research_query.execute import execute_question
from tests.mlb_golden import GOLDEN_DRAFT, assert_golden_compile, assert_golden_result


def test_golden_compile_contract():
    assert_golden_compile()


def test_golden_warehouse_identity():
    cfg = RollerConfig()
    if not baseball_warehouse_ready(cfg):
        pytest.skip("MLB canonical warehouse not ingested yet")
    out = execute_question(GOLDEN_DRAFT)
    assert_golden_result(out)
