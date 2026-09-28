"""LAST_TRADE_PRINT cannot host stop-path or fee economics."""

from __future__ import annotations

import pytest

from roller.superasi.fees import estimate
from roller.superasi.models import SuperasiError


def test_last_trade_fees_data_required():
    with pytest.raises(SuperasiError) as ei:
        estimate(
            scenario="CURRENT",
            contracts=1,
            entry_cents=80,
            exit_cents=40,
            price_basis="LAST_TRADE_PRINT",
        )
    assert ei.value.code == "LAST_TRADE_PRINT_DATA_REQUIRED"
