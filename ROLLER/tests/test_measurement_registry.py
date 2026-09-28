"""Gate 1: measurement registry flags and versioning."""

from __future__ import annotations

from pathlib import Path

import pytest

from roller import Roller
from roller.config import RollerConfig
from roller.measurement.registry import implemented_measurements, load_measurement_registry
from roller.point_in_time.filters import FutureInformationError


SRC = Path(__file__).resolve().parents[1]


def test_registry_boundaries_and_versions():
    body = load_measurement_registry(RollerConfig(SRC))
    names = {m["measurement_name"]: m for m in body["measurements"]}
    assert names["market_return_1m_backward"]["information_boundary"] == "backward"
    assert names["market_return_1m_backward"]["contains_future_information"] is False
    assert names["market_response_1m"]["information_boundary"] == "forward"
    assert names["market_response_1m"]["contains_future_information"] is True
    assert names["basis"]["implementation_status"] == "SCHEMA_ONLY"
    assert names["market_delta_1s_l2"]["source_resolution"] == "1s"
    assert names["market_response_1m"]["source_resolution"] == "1m"
    assert names["market_delta_1s_l2"]["measurement_name"] != names["market_response_1m"]["measurement_name"]
    for m in implemented_measurements(body):
        assert m["measurement_version"]
        assert m["information_boundary"] in {"backward", "forward", "schema_only"}


def test_forward_dataset_names_rejected(roller_env: Path):
    db = Roller(roller_env)
    for name in ("market_response_1m", "response_corpus", "delta_residual", "greek_delta"):
        with pytest.raises(FutureInformationError):
            db.dataset("NBA", "2025-2026", name, as_of="2025-12-21")
