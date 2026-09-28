from __future__ import annotations

from pathlib import Path

from roller.config import RollerConfig


def test_p5_vs_p5_is_metadata(roller_env: Path):
    cfg = RollerConfig(roller_env)
    assert cfg.is_p5_vs_p5("NCAAB", "2025-2026", "DUKE", "UNC")
    assert cfg.is_p5_vs_p5("NCAAB", "2025-2026", "TEX", "OKLA")
    assert not cfg.is_p5_team("NCAAB", "2025-2026", "TLSA")
    assert cfg.conference_of("NCAAB", "2025-2026", "OU") == "SEC"
    assert len(cfg.p5_conference_ids("NCAAB", "2025-2026")) == 5


def test_wnba_city_names_canonicalize(roller_env: Path):
    cfg = RollerConfig(roller_env)
    assert cfg.canon_team_id("WNBA", "2025", "Dallas") == "DAL"
    assert cfg.canon_team_id("WNBA", "2025", "Los Angeles") == "LA"
    assert cfg.canon_team_id("WNBA", "2025", "LAS") == "LA"
    assert cfg.canon_team_id("WNBA", "2025", "LVA") == "LV"
    assert cfg.canon_team_id("WNBA", "2025", "CON") == "CONN"
