"""Jump research-object identity. Pointers only. No silent merges."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from roller.jump.library import repo_root
from roller.jump.versions import LIVE_EXECUTION

ASKED_SIX_KEY = "FIRST80_ASKED_SIX_80_40"
ASKED_SIX_DISPLAY = "FIRST80 Asked Six 80→40"
ASKED_SIX_PACKAGE_ID = "asked_six_first80_80_40"
ASKED_SIX_SPORTS = ("NBA", "NCAAB", "WNBA")
ASKED_SIX_ALIASES = frozenset(
    {
        ASKED_SIX_KEY,
        ASKED_SIX_PACKAGE_ID,
        "asked_six",
        "ASKED_SIX",
        "first80_asked_six_80_40",
    }
)
SPORT_ORDER = ("NBA", "NCAAB", "MLB", "WNBA", "TENNIS")
DEFAULT_SPORT = "NBA"
NEEDS_RESOLUTION = "NEEDS_RESOLUTION"
PRESENT = "PRESENT"
UNAVAILABLE = "Unavailable"

_UUID_RE = re.compile(r"^[0-9a-f]{32}$", re.IGNORECASE)


@dataclass
class JumpSourceReference:
    owner: str
    role: str
    path: str
    status: str
    note: str = ""
    api_target: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "owner": self.owner,
            "role": self.role,
            "path": self.path,
            "status": self.status,
            "note": self.note,
            "api_target": self.api_target,
        }


@dataclass
class JumpDocument:
    doc_id: str
    canonical_key: str
    slug: str
    title: str
    body_markdown: str
    provenance: list[JumpSourceReference] = field(default_factory=list)
    status: str = PRESENT

    def as_dict(self) -> dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "canonical_key": self.canonical_key,
            "slug": self.slug,
            "title": self.title,
            "body_markdown": self.body_markdown,
            "provenance": [row.as_dict() for row in self.provenance],
            "status": self.status,
            "live_execution": LIVE_EXECUTION,
        }


@dataclass
class JumpArtifact:
    artifact_id: str
    name: str
    kind: str
    source_path: str
    status: str
    canonical_key: str
    note: str = ""
    parent_folder: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "name": self.name,
            "kind": self.kind,
            "source_path": self.source_path,
            "status": self.status,
            "canonical_key": self.canonical_key,
            "note": self.note,
            "parent_folder": self.parent_folder,
            "live_execution": LIVE_EXECUTION,
        }


@dataclass
class FolderScan:
    folder_name: str
    folder_path: str
    package_id: str | None
    research_object_id: str | None
    question_hash: str | None
    name: str | None
    identity_name: str | None
    population_n: int | None
    sports: tuple[str, ...]
    package: dict[str, Any]
    files: dict[str, bool]
    folder_matches_package_id: bool


@dataclass
class JumpResearchObject:
    canonical_key: str
    display_name: str
    sports: list[str]
    home_sport: str
    status: str
    population_n: int | None = None
    population_label: str = UNAVAILABLE
    research_object_id: str | None = None
    package_id: str | None = None
    package_folder: str | None = None
    question_hash: str | None = None
    uuid: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    sources: list[JumpSourceReference] = field(default_factory=list)
    unresolved_aliases: list[JumpSourceReference] = field(default_factory=list)
    documents: list[JumpDocument] = field(default_factory=list)
    artifacts: list[JumpArtifact] = field(default_factory=list)
    package: dict[str, Any] | None = field(default=None, repr=False)

    def as_dict(self, *, include_documents: bool = False) -> dict[str, Any]:
        body = {
            "canonical_key": self.canonical_key,
            "display_name": self.display_name,
            "name": self.display_name,
            "sports": list(self.sports),
            "home_sport": self.home_sport,
            "status": self.status,
            "population_n": self.population_n,
            "population_label": self.population_label,
            "research_object_id": self.research_object_id,
            "package_id": self.package_id,
            "package_folder": self.package_folder,
            "question_hash": self.question_hash,
            "uuid": self.uuid,
            "metadata": dict(self.metadata),
            "sources": [row.as_dict() for row in self.sources],
            "unresolved_aliases": [row.as_dict() for row in self.unresolved_aliases],
            "needs_resolution": bool(self.unresolved_aliases) or self.status == NEEDS_RESOLUTION,
            "live_execution": LIVE_EXECUTION,
            "writable": False,
        }
        if include_documents:
            body["documents"] = [doc.as_dict() for doc in self.documents]
            body["artifacts"] = [art.as_dict() for art in self.artifacts]
        return body


def looks_like_uuid(value: str | None) -> bool:
    if not value:
        return False
    compact = value.replace("-", "")
    return bool(_UUID_RE.fullmatch(compact))


def _rel(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def _clean_name(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _leagues(pkg: dict[str, Any]) -> tuple[str, ...]:
    spec = pkg.get("research_spec") if isinstance(pkg.get("research_spec"), dict) else {}
    binding = spec.get("population_binding") if isinstance(spec.get("population_binding"), dict) else {}
    leagues = binding.get("leagues") if isinstance(binding.get("leagues"), list) else []
    out: list[str] = []
    for item in leagues:
        token = str(item or "").strip().upper()
        if token and token not in out:
            out.append(token)
    return tuple(out)


def _identity_name(pkg: dict[str, Any]) -> str | None:
    spec = pkg.get("research_spec") if isinstance(pkg.get("research_spec"), dict) else {}
    identity = spec.get("identity") if isinstance(spec.get("identity"), dict) else {}
    return _clean_name(identity.get("name"))


def _is_asked_six_token(value: str | None) -> bool:
    if not value:
        return False
    if value in ASKED_SIX_ALIASES:
        return True
    return value.strip().lower() in {item.lower() for item in ASKED_SIX_ALIASES}


def humanize_key(key: str) -> str:
    if looks_like_uuid(key):
        return "Untitled research object"
    if key == ASKED_SIX_KEY:
        return ASKED_SIX_DISPLAY
    text = key.replace("-", "_")
    text = re.sub(r"(\d+)_(\d+)", r"\1→\2", text)
    parts = [part for part in text.split("_") if part]
    pretty: list[str] = []
    for part in parts:
        if part.isupper() or part in {"NBA", "MLB", "WNBA", "NCAAB", "FIRST80", "ITI"}:
            pretty.append(part)
        elif "→" in part:
            pretty.append(part)
        else:
            pretty.append(part[:1].upper() + part[1:].lower())
    return " ".join(pretty) or key


def display_name_for(*, canonical_key: str, identity_name: str | None, pkg_name: str | None) -> str:
    if canonical_key == ASKED_SIX_KEY:
        return ASKED_SIX_DISPLAY
    named = identity_name or pkg_name
    if named:
        return named
    return humanize_key(canonical_key)


def home_sport_for(sports: list[str] | tuple[str, ...]) -> str:
    wanted = {item.upper() for item in sports}
    for sport in SPORT_ORDER:
        if sport in wanted:
            return sport
    return DEFAULT_SPORT


def _file_map(folder: Path) -> dict[str, bool]:
    return {
        "package.json": (folder / "package.json").is_file(),
        "trades.json": (folder / "trades.json").is_file(),
        "decomp.json": (folder / "decomp.json").is_file(),
        "path_windows.json": (folder / "path_windows.json").is_file(),
    }


def scan_superasi_folders(root: Path | None = None) -> list[FolderScan]:
    base = (root or repo_root()) / "research" / "superasi" / "library"
    if not base.is_dir():
        return []
    scans: list[FolderScan] = []
    for child in sorted(base.iterdir()):
        pkg_path = child / "package.json"
        if not child.is_dir() or not pkg_path.is_file():
            continue
        try:
            pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(pkg, dict):
            continue
        package_id = _clean_name(pkg.get("package_id"))
        research_object_id = _clean_name(pkg.get("research_object_id"))
        asked = _is_asked_six_token(research_object_id) or _is_asked_six_token(package_id) or _is_asked_six_token(
            child.name
        )
        sports = ASKED_SIX_SPORTS if asked else _leagues(pkg)
        scans.append(
            FolderScan(
                folder_name=child.name,
                folder_path=_rel(root or repo_root(), child),
                package_id=package_id,
                research_object_id=research_object_id,
                question_hash=_clean_name(pkg.get("question_hash")),
                name=_clean_name(pkg.get("name")),
                identity_name=_identity_name(pkg),
                population_n=pkg.get("population_n") if isinstance(pkg.get("population_n"), int) else None,
                sports=sports,
                package=pkg,
                files=_file_map(child),
                folder_matches_package_id=bool(package_id) and child.name == package_id,
            )
        )
    return scans


def _priority_key(scan: FolderScan) -> str | None:
    if scan.research_object_id and not looks_like_uuid(scan.research_object_id):
        if _is_asked_six_token(scan.research_object_id):
            return ASKED_SIX_KEY
        return scan.research_object_id
    if scan.folder_matches_package_id and scan.package_id:
        if _is_asked_six_token(scan.package_id):
            return ASKED_SIX_KEY
        return scan.package_id
    if _is_asked_six_token(scan.folder_name) or _is_asked_six_token(scan.package_id):
        return ASKED_SIX_KEY
    roller_id = _clean_name((scan.package.get("research_spec") or {}).get("template_id") if isinstance(scan.package.get("research_spec"), dict) else None)
    if roller_id and roller_id.startswith("RSH_"):
        return roller_id
    if scan.question_hash:
        return f"hash:{scan.question_hash}"
    if scan.folder_name:
        return scan.folder_name
    return None


def _canonical_source_preferred(scan: FolderScan) -> bool:
    return scan.folder_matches_package_id


def _asked_six_population_label(n: int | None) -> str:
    if n != 1182:
        return f"MIXED asked-six N={n if n is not None else UNAVAILABLE}. Not NBA-only 604/936."
    return "MIXED (NBA 604 + NCAAB 332 + WNBA 246). Asked-six N=1182, not NBA-only 604/936."


def _attach_roller_and_choosin(obj: JumpResearchObject, root: Path) -> None:
    if obj.canonical_key != ASKED_SIX_KEY:
        return
    first80 = root / "ROLLER" / "roller" / "research" / "first80.py"
    obj.sources.append(
        JumpSourceReference(
            owner="roller",
            role="FIRST80 measurement loader",
            path=_rel(root, first80),
            status=PRESENT if first80.is_file() else "MISSING",
            note="Frozen. Touch-80 is not live FIRST01. Jump does not edit this file.",
        )
    )
    csv_path = root / "research" / "first80_asked_six_chatgpt_export" / "first80_asked_six.csv"
    obj.sources.append(
        JumpSourceReference(
            owner="roller",
            role="asked-six CSV provenance",
            path=_rel(root, csv_path),
            status=PRESENT if csv_path.is_file() else "MISSING",
            note="Related provenance. Not a second Jump folder.",
        )
    )
    try:
        from roller.choosin_texas.locks_asked_six import ASKED_SIX_CELLS_80, ASKED_SIX_N_80

        obj.sources.append(
            JumpSourceReference(
                owner="choosin",
                role="asked-six lock integers τ=80",
                path="ROLLER/roller/choosin_texas/locks_asked_six.py",
                status=PRESENT,
                note=f"N={ASKED_SIX_N_80} cells={list(ASKED_SIX_CELLS_80)}. Related provenance, not a second folder.",
                api_target="/choosin-texas/asked-six",
            )
        )
        obj.metadata["choosin_asked_six"] = {
            "tau": 80,
            "N": ASKED_SIX_N_80,
            "cells": list(ASKED_SIX_CELLS_80),
        }
    except Exception:  # noqa: BLE001 — lock module unread stays Unavailable
        obj.sources.append(
            JumpSourceReference(
                owner="choosin",
                role="asked-six lock integers τ=80",
                path="ROLLER/roller/choosin_texas/locks_asked_six.py",
                status="MISSING",
                note=UNAVAILABLE,
            )
        )
    from roller.jump.warehouse.registry import get_warehouse

    for sport in ("nba", "ncaab", "wnba"):
        rec = get_warehouse(sport, root=root)
        obj.sources.append(
            JumpSourceReference(
                owner="roller",
                role=f"{sport.upper()} warehouse pointer",
                path=rec.source_uri,
                status="POINTER" if rec.status == "AVAILABLE" else rec.status,
                note="Phase 8 parquet desk. Pointer, not a copy.",
            )
        )


def _object_from_canonical(scan: FolderScan, canonical_key: str, root: Path) -> JumpResearchObject:
    sports = list(scan.sports) or ([DEFAULT_SPORT] if canonical_key == ASKED_SIX_KEY else [])
    if canonical_key == ASKED_SIX_KEY:
        sports = list(ASKED_SIX_SPORTS)
    uuid = scan.package_id if looks_like_uuid(scan.package_id) else None
    status = PRESENT if scan.folder_matches_package_id or canonical_key == ASKED_SIX_KEY else NEEDS_RESOLUTION
    if not scan.folder_matches_package_id and canonical_key != ASKED_SIX_KEY:
        status = NEEDS_RESOLUTION
    obj = JumpResearchObject(
        canonical_key=canonical_key,
        display_name=display_name_for(
            canonical_key=canonical_key,
            identity_name=scan.identity_name,
            pkg_name=scan.name,
        ),
        sports=sports,
        home_sport=home_sport_for(sports),
        status=status if scan.folder_matches_package_id else (PRESENT if canonical_key == ASKED_SIX_KEY else NEEDS_RESOLUTION),
        population_n=scan.population_n,
        population_label=(
            _asked_six_population_label(scan.population_n)
            if canonical_key == ASKED_SIX_KEY
            else (f"N={scan.population_n}" if scan.population_n is not None else UNAVAILABLE)
        ),
        research_object_id=scan.research_object_id,
        package_id=scan.package_id,
        package_folder=scan.folder_name,
        question_hash=scan.question_hash,
        uuid=uuid,
        metadata={
            "imported_at": scan.package.get("imported_at"),
            "code_version": scan.package.get("code_version"),
            "price_basis": scan.package.get("price_basis"),
            "source": scan.package.get("source"),
            "package_id": scan.package_id,
            "folder_name": scan.folder_name,
            "uuid": uuid,
        },
        package=scan.package,
    )
    obj.sources.append(
        JumpSourceReference(
            owner="superasi",
            role="library package",
            path=scan.folder_path,
            status=PRESENT,
            api_target=f"/superasi/library/{scan.folder_name}",
            note="Canonical SuperASI folder (folder name equals package_id)."
            if scan.folder_matches_package_id
            else "SuperASI package pointer.",
        )
    )
    if scan.files.get("decomp.json"):
        obj.sources.append(
            JumpSourceReference(
                owner="superasi",
                role="decomposition",
                path=f"{scan.folder_path}/decomp.json",
                status=PRESENT,
                api_target=f"/superasi/library/{scan.folder_name}",
            )
        )
    else:
        obj.sources.append(
            JumpSourceReference(
                owner="superasi",
                role="decomposition",
                path=f"{scan.folder_path}/decomp.json",
                status="MISSING",
                note=UNAVAILABLE,
            )
        )
    _attach_roller_and_choosin(obj, root)
    return obj


def _alias_source(scan: FolderScan) -> JumpSourceReference:
    return JumpSourceReference(
        owner="superasi",
        role="unresolved package alias",
        path=scan.folder_path,
        status=NEEDS_RESOLUTION,
        api_target=f"/superasi/library/{scan.folder_name}",
        note=(
            f"Folder {scan.folder_name!r} repeats package_id={scan.package_id!r} "
            "but is not the canonical folder. Not merged."
        ),
    )


def resolve_all_jump_research_objects(*, root: Path | None = None) -> list[JumpResearchObject]:
    repo = root or repo_root()
    scans = scan_superasi_folders(repo)
    objects: dict[str, JumpResearchObject] = {}
    hash_index: dict[str, str] = {}

    canonical_scans = [scan for scan in scans if _canonical_source_preferred(scan)]
    extra_scans = [scan for scan in scans if not _canonical_source_preferred(scan)]

    for scan in canonical_scans:
        key = _priority_key(scan)
        if not key:
            continue
        if key.startswith("hash:"):
            digest = key.removeprefix("hash:")
            if digest in hash_index:
                key = hash_index[digest]
            else:
                key = scan.package_id or scan.folder_name
                hash_index[digest] = key
        elif scan.question_hash:
            hash_index.setdefault(scan.question_hash, key)
        if key in objects:
            objects[key].unresolved_aliases.append(_alias_source(scan))
            continue
        objects[key] = _object_from_canonical(scan, key, repo)

    for scan in extra_scans:
        key = _priority_key(scan)
        if key and key in objects:
            objects[key].unresolved_aliases.append(_alias_source(scan))
            continue
        if scan.question_hash and scan.question_hash in hash_index:
            existing = hash_index[scan.question_hash]
            objects[existing].unresolved_aliases.append(_alias_source(scan))
            continue
        fallback_key = key if key and not key.startswith("hash:") else scan.folder_name
        obj = _object_from_canonical(scan, fallback_key, repo)
        obj.status = NEEDS_RESOLUTION
        obj.unresolved_aliases.append(_alias_source(scan))
        objects[fallback_key] = obj

    from roller.jump.documents import attach_documents

    resolved = list(objects.values())
    for obj in resolved:
        attach_documents(obj, root=repo)
    resolved.sort(key=lambda row: (row.home_sport, row.display_name.lower(), row.canonical_key))
    return resolved


def resolve_jump_research_object(
    identifier: str | None = None,
    *,
    root: Path | None = None,
) -> JumpResearchObject | list[JumpResearchObject]:
    objects = resolve_all_jump_research_objects(root=root)
    if identifier is None or str(identifier).strip() == "":
        return objects
    needle = str(identifier).strip()
    for obj in objects:
        ids = {
            obj.canonical_key,
            obj.package_id or "",
            obj.package_folder or "",
            obj.research_object_id or "",
            obj.display_name,
        }
        if needle in ids:
            return obj
        for alias in obj.unresolved_aliases:
            if alias.path.endswith("/" + needle) or alias.path.endswith(needle):
                return obj
        if _is_asked_six_token(needle) and obj.canonical_key == ASKED_SIX_KEY:
            return obj
    from roller.jump.errors import JumpError

    raise JumpError("RESULT_NOT_FOUND", f"unknown research object {needle}")
