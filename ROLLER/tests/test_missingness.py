"""Field-level missingness statuses. Never a bare null without status."""

from __future__ import annotations

from roller.state.missingness import field, section


def test_known_missing_vs_source_missing_vs_not_supported():
    km = field(None, status="known_missing", source="pbp.personId")
    sm = field(None, status="source_missing", source="pbp.personId")
    ns = field(None, status="not_supported", source="wnba.normalized_plays")
    assert km["status"] == "known_missing"
    assert sm["status"] == "source_missing"
    assert ns["status"] == "not_supported"
    assert km["value"] is None
    assert "status" in km and "source" in km


def test_section_never_bare_null():
    out = section("INCOMPLETE", data=None)
    assert out["status"] == "INCOMPLETE"
    assert out["source_availability_status"] == "INCOMPLETE"
    assert out["data"] is None
    assert set(out) >= {"status", "source_availability_status", "data"}
