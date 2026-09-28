"""Load momento/registry/systems.yaml. Tiny YAML subset — no PyYAML dependency."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from roller.momento.bracket import OWNERSHIP_EDGES, assert_acyclic
from roller.paths import find_root, momento_root

REGISTRY_SCHEMA = "momento_systems_registry_v1"
CODE_VERSION = "momento_systems_v0.1.0"
SYSTEM_COUNT = 19
LIVE_EXECUTION = False

CANONICAL_IDS: tuple[str, ...] = (
    "database",
    "data_analysis",
    "fair_odds_modeling",
    "in_house_odds_modeling",
    "trade_breakdown",
    "position_stratification",
    "hedging_analysis",
    "relative_value_hedging",
    "data_modeling",
    "game_modeling",
    "dynamic_risk_engine",
    "position_management",
    "signal_generation",
    "algorithmic_execution",
    "momento_systems",
    "system_maintenance",
    "data_ingestion",
    "trade_reconciliation",
    "system_orchestration",
)

REQUIRED_FIELDS: tuple[str, ...] = (
    "id",
    "display_name",
    "short_name",
    "bracket_round",
    "bracket_position",
    "purpose",
    "status",
    "version",
    "implementation_paths",
    "research_paths",
    "frontend_target",
    "backend_target",
    "api_namespace",
    "upstream_systems",
    "downstream_systems",
    "input_contracts",
    "output_contracts",
    "health_check",
    "feature_flags",
    "live_capability",
    "migration_sources",
    "notes",
)

ALLOWED_ROUNDS = frozenset({"first", "second", "final_four", "champion", "infrastructure"})
ALLOWED_STATUS = frozenset({"COMPLETE", "PARTIAL", "NOT_IMPLEMENTED"})
ROUND_COUNTS = {"first": 8, "second": 4, "final_four": 2, "champion": 1, "infrastructure": 4}

KNOWN_FRONTEND_PRODUCTS = {
    "database": ("ROLLER", "http://127.0.0.1:5179"),
    "data_analysis": ("SuperASI", "http://127.0.0.1:5179/?app=superasi"),
    "data_modeling": ("Jump", "http://127.0.0.1:5179/?app=jump"),
    "trade_breakdown": ("Choosin Texas", "http://127.0.0.1:5182#/"),
    "position_stratification": ("Austin", "http://127.0.0.1:5182#/austin"),
    "dynamic_risk_engine": ("Drevo", "http://127.0.0.1:5191/"),
    "position_management": ("Positman", "http://127.0.0.1:5194/"),
    "hedging_analysis": ("Ballhog", "http://127.0.0.1:5192/"),
    "relative_value_hedging": ("TK Ultra", "http://127.0.0.1:5190/#/tk-ultra"),
    "system_maintenance": ("Systimo", "http://127.0.0.1:5193/"),
}


class RegistryError(ValueError):
    """Invalid Momento system registry."""


@dataclass(frozen=True)
class SystemRecord:
    id: str
    display_name: str
    short_name: str
    bracket_round: str
    bracket_position: int
    purpose: str
    status: str
    version: str
    implementation_paths: tuple[str, ...]
    research_paths: tuple[str, ...]
    frontend_target: dict[str, Any]
    backend_target: dict[str, Any]
    api_namespace: str
    upstream_systems: tuple[str, ...]
    downstream_systems: tuple[str, ...]
    input_contracts: tuple[str, ...]
    output_contracts: tuple[str, ...]
    health_check: str
    feature_flags: tuple[str, ...]
    live_capability: bool
    migration_sources: tuple[str, ...]
    notes: str
    extra: dict[str, Any]

    @property
    def frontend_url(self) -> str:
        return str(self.frontend_target.get("url", ""))

    @property
    def frontend_product(self) -> str:
        return str(self.frontend_target.get("product", ""))


@dataclass(frozen=True)
class SystemRegistry:
    schema_version: str
    code_version: str
    live_execution: bool
    systems: tuple[SystemRecord, ...]

    def by_id(self) -> dict[str, SystemRecord]:
        return {row.id: row for row in self.systems}

    def __len__(self) -> int:
        return len(self.systems)


def default_registry_path() -> Path:
    return momento_root(find_root()) / "momento" / "registry" / "systems.yaml"


def load_registry(path: Path | None = None) -> SystemRegistry:
    src = path or default_registry_path()
    if not src.is_file():
        raise RegistryError(f"missing registry {src}")
    payload = parse_yaml_subset(src.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RegistryError("registry root must be a mapping")
    return _validate(payload, src)


def parse_yaml_subset(text: str) -> Any:
    rows: list[tuple[int, int, str]] = []
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = _strip_comment(raw).rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        if indent % 2 != 0:
            raise RegistryError(f"line {lineno}: indent must be multiples of 2")
        rows.append((lineno, indent, line.lstrip(" ")))
    value, nxt = _parse_block(rows, 0, 0)
    if nxt != len(rows):
        raise RegistryError(f"line {rows[nxt][0]}: unexpected trailing content")
    return value


def _strip_comment(raw: str) -> str:
    in_single = False
    in_double = False
    for idx, ch in enumerate(raw):
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double:
            if idx == 0 or raw[idx - 1].isspace():
                return raw[:idx]
    return raw


def _parse_scalar(raw: str) -> Any:
    text = raw.strip()
    if text == "[]":
        return []
    if text == "{}":
        return {}
    if text in {"true", "false"}:
        return text == "true"
    if text in {"null", "~"}:
        return None
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        return text[1:-1]
    if text.isdigit() or (text.startswith("-") and text[1:].isdigit()):
        return int(text)
    return text


def _parse_block(rows: list[tuple[int, int, str]], index: int, indent: int) -> tuple[Any, int]:
    if index >= len(rows) or rows[index][1] != indent:
        raise RegistryError("empty YAML block")
    if rows[index][2].startswith("- "):
        return _parse_list(rows, index, indent)
    return _parse_map(rows, index, indent)


def _parse_map(rows: list[tuple[int, int, str]], index: int, indent: int) -> tuple[dict[str, Any], int]:
    out: dict[str, Any] = {}
    while index < len(rows) and rows[index][1] == indent:
        lineno, _, content = rows[index]
        if content.startswith("- "):
            raise RegistryError(f"line {lineno}: list item in mapping")
        if ":" not in content:
            raise RegistryError(f"line {lineno}: expected key:")
        key, rest = content.split(":", 1)
        key = key.strip()
        rest = rest.strip()
        index += 1
        if rest:
            out[key] = _parse_scalar(rest)
            continue
        if index < len(rows) and rows[index][1] > indent:
            value, index = _parse_block(rows, index, rows[index][1])
            out[key] = value
        else:
            out[key] = None
    return out, index


def _parse_list(rows: list[tuple[int, int, str]], index: int, indent: int) -> tuple[list[Any], int]:
    out: list[Any] = []
    while index < len(rows) and rows[index][1] == indent and rows[index][2].startswith("- "):
        lineno, _, content = rows[index]
        body = content[2:].strip()
        index += 1
        if not body:
            if index < len(rows) and rows[index][1] > indent:
                value, index = _parse_block(rows, index, rows[index][1])
                out.append(value)
            else:
                out.append(None)
            continue
        if ":" in body and not (body.startswith('"') or body.startswith("'")):
            key, rest = body.split(":", 1)
            item: dict[str, Any] = {key.strip(): _parse_scalar(rest) if rest.strip() else None}
            if index < len(rows) and rows[index][1] > indent:
                nested, index = _parse_block(rows, index, rows[index][1])
                if not isinstance(nested, dict):
                    raise RegistryError(f"line {lineno}: nested list item must be a mapping")
                item.update(nested)
            out.append(item)
            continue
        out.append(_parse_scalar(body))
    return out, index


def _as_str_tuple(value: Any, field: str, system_id: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise RegistryError(f"{system_id}.{field} must be a list")
    out: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise RegistryError(f"{system_id}.{field} items must be strings")
        out.append(item)
    return tuple(out)


def _system_from_map(row: dict[str, Any]) -> SystemRecord:
    if not isinstance(row, dict):
        raise RegistryError("system entry must be a mapping")
    system_id = str(row.get("id", ""))
    missing = [name for name in REQUIRED_FIELDS if name not in row]
    if missing:
        raise RegistryError(f"{system_id or '?'} missing {missing}")
    extra = {key: value for key, value in row.items() if key not in REQUIRED_FIELDS}
    frontend = row["frontend_target"]
    backend = row["backend_target"]
    if not isinstance(frontend, dict) or "kind" not in frontend or "url" not in frontend:
        raise RegistryError(f"{system_id}.frontend_target needs kind and url")
    if not isinstance(backend, dict) or "kind" not in backend:
        raise RegistryError(f"{system_id}.backend_target needs kind")
    if not isinstance(row["live_capability"], bool):
        raise RegistryError(f"{system_id}.live_capability must be bool")
    if not isinstance(row["bracket_position"], int):
        raise RegistryError(f"{system_id}.bracket_position must be int")
    return SystemRecord(
        id=system_id,
        display_name=str(row["display_name"]),
        short_name=str(row["short_name"]),
        bracket_round=str(row["bracket_round"]),
        bracket_position=int(row["bracket_position"]),
        purpose=str(row["purpose"]),
        status=str(row["status"]),
        version=str(row["version"]),
        implementation_paths=_as_str_tuple(row["implementation_paths"], "implementation_paths", system_id),
        research_paths=_as_str_tuple(row["research_paths"], "research_paths", system_id),
        frontend_target=dict(frontend),
        backend_target=dict(backend),
        api_namespace=str(row["api_namespace"]),
        upstream_systems=_as_str_tuple(row["upstream_systems"], "upstream_systems", system_id),
        downstream_systems=_as_str_tuple(row["downstream_systems"], "downstream_systems", system_id),
        input_contracts=_as_str_tuple(row["input_contracts"], "input_contracts", system_id),
        output_contracts=_as_str_tuple(row["output_contracts"], "output_contracts", system_id),
        health_check=str(row["health_check"]),
        feature_flags=_as_str_tuple(row["feature_flags"], "feature_flags", system_id),
        live_capability=bool(row["live_capability"]),
        migration_sources=_as_str_tuple(row["migration_sources"], "migration_sources", system_id),
        notes=str(row["notes"]),
        extra=extra,
    )


def _validate(payload: dict[str, Any], src: Path) -> SystemRegistry:
    schema = str(payload.get("schema_version", ""))
    if schema != REGISTRY_SCHEMA:
        raise RegistryError(f"{src}: schema_version must be {REGISTRY_SCHEMA}")
    live_execution = payload.get("live_execution")
    if live_execution is not False:
        raise RegistryError(f"{src}: live_execution must be false")
    raw_systems = payload.get("systems")
    if not isinstance(raw_systems, list):
        raise RegistryError(f"{src}: systems must be a list")
    systems = tuple(_system_from_map(row) for row in raw_systems)
    if len(systems) != SYSTEM_COUNT:
        raise RegistryError(f"{src}: expected {SYSTEM_COUNT} systems, got {len(systems)}")
    ids = tuple(row.id for row in systems)
    if len(set(ids)) != len(ids):
        raise RegistryError(f"{src}: duplicate system id")
    if set(ids) != set(CANONICAL_IDS):
        raise RegistryError(f"{src}: system ids must match canonical set")
    for row in systems:
        if row.bracket_round not in ALLOWED_ROUNDS:
            raise RegistryError(f"{row.id}: illegal bracket_round")
        if row.status not in ALLOWED_STATUS:
            raise RegistryError(f"{row.id}: illegal status")
        if row.live_capability:
            raise RegistryError(f"{row.id}: live_capability must be false in V0")
        if "LIVE_EXECUTION=FALSE" not in row.feature_flags:
            raise RegistryError(f"{row.id}: feature_flags must include LIVE_EXECUTION=FALSE")
    counts = {name: 0 for name in ROUND_COUNTS}
    for row in systems:
        counts[row.bracket_round] += 1
    if counts != ROUND_COUNTS:
        raise RegistryError(f"{src}: bracket round counts {counts}")
    by_id = {row.id: row for row in systems}
    for src_id, dst_id in OWNERSHIP_EDGES:
        if dst_id not in by_id[src_id].downstream_systems:
            raise RegistryError(f"{src_id} missing downstream {dst_id}")
        if src_id not in by_id[dst_id].upstream_systems:
            raise RegistryError(f"{dst_id} missing upstream {src_id}")
    for row in systems:
        for other in row.downstream_systems:
            if (row.id, other) not in OWNERSHIP_EDGES:
                raise RegistryError(f"{row.id}: undeclared downstream {other}")
        for other in row.upstream_systems:
            if (other, row.id) not in OWNERSHIP_EDGES:
                raise RegistryError(f"{row.id}: undeclared upstream {other}")
    assert_acyclic(ids, OWNERSHIP_EDGES)
    for system_id, (product, url) in KNOWN_FRONTEND_PRODUCTS.items():
        row = by_id[system_id]
        if row.frontend_product != product:
            raise RegistryError(f"{system_id}: frontend product must be {product}")
        if row.frontend_url != url:
            raise RegistryError(f"{system_id}: frontend url must be {url}")
    return SystemRegistry(
        schema_version=schema,
        code_version=str(payload.get("code_version", "")),
        live_execution=False,
        systems=systems,
    )
