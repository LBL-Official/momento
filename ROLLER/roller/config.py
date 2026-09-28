"""Load metadata-driven configuration. Seasons are not hard-coded in logic."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from roller.paths import find_root, momento_root


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


class RollerConfig:
    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root).resolve() if root is not None else find_root()
        self.db_map = load_json(self.root / "roller.json")
        self.sports = load_json(self.root / "config" / "sports.json")
        self.seasons = load_json(self.root / "config" / "seasons.json")
        self.schemas = load_json(self.root / "config" / "schemas.json")
        self.sources = load_json(self.root / "config" / "sources.json")
        self.features = load_json(self.root / "config" / "features.json")
        conferences_path = self.root / "config" / "conferences.json"
        self.conferences = load_json(conferences_path) if conferences_path.is_file() else {}
        aliases_path = self.root / "config" / "team_aliases.json"
        self.team_aliases = load_json(aliases_path) if aliases_path.is_file() else {}
        polymarket_path = self.root / "config" / "polymarket.json"
        self.polymarket = load_json(polymarket_path) if polymarket_path.is_file() else {}
        labels_path = self.root / "config" / "labels.json"
        self.labels = load_json(labels_path) if labels_path.is_file() else {}
        regimes_path = self.root / "config" / "regimes.json"
        self.regimes = load_json(regimes_path) if regimes_path.is_file() else {}
        feature_registry_path = self.root / "meta" / "feature_registry.json"
        self.feature_registry = (
            load_json(feature_registry_path) if feature_registry_path.is_file() else {}
        )
        meas_reg = self.root / "meta" / "measurement_registry.json"
        self.measurement_registry = load_json(meas_reg) if meas_reg.is_file() else {}
        horizons_path = self.root / "config" / "response_horizons.json"
        self.response_horizons = load_json(horizons_path) if horizons_path.is_file() else {}
        conditioning_path = self.root / "config" / "conditioning.json"
        self.conditioning = load_json(conditioning_path) if conditioning_path.is_file() else {}
        greek_defs = self.root / "config" / "greek_definitions.json"
        self.greek_definitions = load_json(greek_defs) if greek_defs.is_file() else {}
        fund_reg = self.root / "meta" / "fundamental_registry.json"
        self.fundamental_registry = load_json(fund_reg) if fund_reg.is_file() else {}
        fund_defs = self.root / "config" / "fundamental_definitions.json"
        self.fundamental_definitions = load_json(fund_defs) if fund_defs.is_file() else {}
        fund_cond = self.root / "config" / "fundamental_conditioning.json"
        self.fundamental_conditioning = load_json(fund_cond) if fund_cond.is_file() else {}
        greek_v4b_reg = self.root / "meta" / "greek_v4b_registry.json"
        self.greek_v4b_registry = load_json(greek_v4b_reg) if greek_v4b_reg.is_file() else {}
        greek_v4b_defs = self.root / "config" / "greek_v4b_definitions.json"
        self.greek_v4b_definitions = load_json(greek_v4b_defs) if greek_v4b_defs.is_file() else {}
        greek_v4c_reg = self.root / "config" / "greek_v4c_registry.json"
        self.greek_v4c_registry = load_json(greek_v4c_reg) if greek_v4c_reg.is_file() else {}

    @property
    def pipeline_version(self) -> str:
        return str(self.db_map["database"]["pipeline_version"])

    @property
    def state_schema_version(self) -> str:
        return str(self.db_map["database"].get("state_schema_version") or "2.0.0")

    @property
    def measurement_schema_version(self) -> str:
        return str(self.db_map["database"].get("measurement_schema_version") or "3.0.0")

    @property
    def fundamental_schema_version(self) -> str:
        return str(self.db_map["database"].get("fundamental_schema_version") or "4.0.0-A")

    @property
    def greek_schema_version(self) -> str:
        return str(self.db_map["database"].get("greek_schema_version") or "4.0.0-B")

    @property
    def greek_architecture_version(self) -> str:
        return str(self.db_map["database"].get("greek_architecture_version") or "4.0.0-C")

    @property
    def warehouse_root(self) -> Path:
        raw = self.sources["warehouse_root"]
        p = Path(raw)
        if p.is_absolute():
            return p
        return (self.root / raw).resolve()

    @property
    def repo_root(self) -> Path:
        return momento_root(self.root)

    def sport_ids(self) -> list[str]:
        return list(self.seasons.keys())

    def season_labels(self, sport: str) -> list[str]:
        return list(self.seasons[sport].keys())

    def season_meta(self, sport: str, season: str) -> dict[str, Any]:
        try:
            return dict(self.seasons[sport][season])
        except KeyError as exc:
            raise KeyError(f"unknown sport/season {sport!r} {season!r}") from exc

    def dataset_relpath(self, sport: str, season: str, dataset: str) -> str:
        return str(self.db_map["sports"][sport]["seasons"][season]["datasets"][dataset])

    def dataset_path(self, sport: str, season: str, dataset: str) -> Path:
        return self.root / self.dataset_relpath(sport, season, dataset)

    def conference_season(self, sport: str, season: str) -> str:
        block = self.conferences.get(sport) or {}
        if season in block:
            return season
        keys = list(block.keys())
        return keys[-1] if keys else season

    def p5_conference_ids(self, sport: str, season: str) -> set[str]:
        block = (self.conferences.get(sport) or {}).get(self.conference_season(sport, season)) or {}
        return set(block.get("p5_conference_ids") or [])

    def conference_of(self, sport: str, season: str, team_id: str) -> str | None:
        resolved = self.conference_season(sport, season)
        block = (self.conferences.get(sport) or {}).get(resolved) or {}
        teams = block.get("teams") or {}
        code = self.canon_team_id(sport, resolved, team_id)
        return teams.get(code)

    def canon_team_id(self, sport: str, season: str | None, team_id: str) -> str:
        """Stable team code. Never mint IDs from display names without an alias map."""
        raw = str(team_id or "").strip()
        if not raw:
            return ""
        if season:
            block = (self.conferences.get(sport) or {}).get(season) or {}
            aliased = (block.get("aliases") or {}).get(raw)
            if aliased:
                return str(aliased)
        sport_aliases = self.team_aliases.get(sport) or {}
        up = raw.upper()
        codes = sport_aliases.get("codes") or {}
        if up in codes:
            return str(codes[up])
        names = sport_aliases.get("names") or {}
        key = " ".join("".join(ch if ch.isalnum() else " " for ch in raw.lower()).split())
        if key in names:
            return str(names[key])
        return raw

    def is_p5_team(self, sport: str, season: str, team_id: str) -> bool:
        conf = self.conference_of(sport, season, team_id)
        return conf is not None and conf in self.p5_conference_ids(sport, season)

    def is_p5_vs_p5(self, sport: str, season: str, home: str, away: str) -> bool:
        return self.is_p5_team(sport, season, home) and self.is_p5_team(sport, season, away)
