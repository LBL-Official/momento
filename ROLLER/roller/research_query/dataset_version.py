"""Warehouse fingerprint. Cache and goldens bind to this, not wall-clock."""

from __future__ import annotations

import hashlib
from pathlib import Path

from roller.config import RollerConfig
from roller.research_query.availability import resolve_league_scopes
from roller.research_query.models import ResearchQuestion


# Dual-write siblings sit beside monthly CSV. They are not the published source.
# Including them here would stale rq_index after every parquet copy.
_NON_CANONICAL_SUFFIXES = (".parquet", ".manifest.json")


def _is_canonical_source(path: Path) -> bool:
    name = path.name
    return not any(name.endswith(suffix) for suffix in _NON_CANONICAL_SUFFIXES)


def _file_stamp(path: Path) -> str:
    if not path.exists():
        return f"{path}:missing"
    if path.is_file():
        st = path.stat()
        return f"{path}:{st.st_size}:{int(st.st_mtime)}"
    stamps: list[str] = []
    for child in sorted(path.rglob("*")):
        if child.is_file() and _is_canonical_source(child):
            st = child.stat()
            stamps.append(f"{child.relative_to(path)}:{st.st_size}:{int(st.st_mtime)}")
    return f"{path}:dir:" + ";".join(stamps[:200])


def _scope_stamp_parts(
    scope,
    cfg: RollerConfig,
    *,
    names: list[str],
    multi: bool,
) -> list[str]:
    parts = [f"{scope.sport}/{scope.season}"]
    scoped = list(names)
    try:
        cfg.dataset_relpath(scope.sport, scope.season, "kalshi_last_trade")
        scoped.append("kalshi_last_trade")
    except (KeyError, FileNotFoundError):
        pass
    for name in scoped:
        try:
            path = cfg.dataset_path(scope.sport, scope.season, name)
        except (KeyError, FileNotFoundError):
            label = f"{scope.sport}:{name}:missing" if multi else f"{name}:missing"
            parts.append(label)
            continue
        parts.append(_file_stamp(Path(path)))
    return parts


def scope_fingerprint(scope, *, cfg: RollerConfig | None = None) -> str:
    """Single-league warehouse identity. Combined queries open each league's index with this."""
    cfg = cfg or RollerConfig()
    names = ["kalshi_candles", "pbp", "kalshi_markets", "games"]
    parts = _scope_stamp_parts(scope, cfg, names=names, multi=False)
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def dataset_fingerprint(question: ResearchQuestion, *, cfg: RollerConfig | None = None) -> str:
    cfg = cfg or RollerConfig()
    scopes = resolve_league_scopes(question.universe)
    if not scopes:
        return "dataset:unresolved"
    names = ["kalshi_candles", "pbp", "kalshi_markets", "games"]
    if "polymarket" in question.universe.markets:
        names.extend(["polymarket_candles", "polymarket_markets"])
    parts: list[str] = []
    multi = len(scopes) > 1
    for scope in scopes:
        parts.extend(_scope_stamp_parts(scope, cfg, names=names, multi=multi))
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
