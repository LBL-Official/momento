"""Jump Drive index. Sport-first research library. Pointers only."""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any

from roller.jump.library import repo_root
from roller.jump.research import (
    DEFAULT_SPORT,
    PRESENT,
    SPORT_ORDER,
    JumpResearchObject,
    resolve_all_jump_research_objects,
)
from roller.jump.versions import LIVE_EXECUTION

DRIVE_SCHEMA = "jump_drive_v2"
ROOT_ID = "root"
SPORTS = SPORT_ORDER
ROOT_ORDER = tuple(f"sport.{sport.lower()}" for sport in SPORT_ORDER)
PREVIEW_MAX_BYTES = 2_000_000
PREVIEW_MAX_ROWS = 40

_LOCK = threading.Lock()
_CACHE: dict[str, Any] | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _node(
    artifact_id: str,
    name: str,
    artifact_type: str,
    *,
    parent_id: str | None,
    system_owner: str,
    sport: str | None = None,
    strategy: str | None = None,
    source_path: str | None = None,
    api_target: str | None = None,
    frontend_target: str | None = None,
    status: str = "POINTER",
    description: str = "",
    tags: list[str] | None = None,
    upstream: list[str] | None = None,
    downstream: list[str] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body = {
        "artifact_id": artifact_id,
        "name": name,
        "artifact_type": artifact_type,
        "system_owner": system_owner,
        "sport": sport,
        "strategy": strategy,
        "parent_folder": parent_id,
        "source_path": source_path,
        "api_target": api_target,
        "frontend_target": frontend_target,
        "created_at": None,
        "updated_at": None,
        "version": None,
        "status": status,
        "research_stage": "RESEARCH_ONLY",
        "model_version": None,
        "manifest_hash": None,
        "tags": list(tags or []),
        "upstream_artifacts": list(upstream or []),
        "downstream_artifacts": list(downstream or []),
        "description": description,
        "live_execution": LIVE_EXECUTION,
        "canonical_key": None,
        "display_name": name,
    }
    if extra:
        body.update(extra)
    return body


def _add(index: dict[str, dict[str, Any]], node: dict[str, Any]) -> dict[str, Any]:
    index[node["artifact_id"]] = node
    return node


def _children(index: dict[str, dict[str, Any]], parent_id: str) -> list[dict[str, Any]]:
    rows = [row for row in index.values() if row.get("parent_folder") == parent_id]
    if parent_id == ROOT_ID:
        order = {artifact_id: i for i, artifact_id in enumerate(ROOT_ORDER)}
        rows.sort(key=lambda row: (order.get(row["artifact_id"], 99), str(row["name"]).lower()))
        return rows
    rows.sort(key=lambda row: (row["artifact_type"] != "FOLDER", str(row["name"]).lower(), row["artifact_id"]))
    return rows


def _public(row: dict[str, Any]) -> dict[str, Any]:
    return dict(row)


def _empty_message(sport: str) -> str:
    return f"No {sport} research objects found."


def _object_folder_id(obj: JumpResearchObject, sport: str) -> str:
    if sport == obj.home_sport:
        return f"research.{obj.canonical_key}"
    return f"sport.{sport.lower()}.research.{obj.canonical_key}"


def _doc_node_id(doc_id: str) -> str:
    return doc_id


def _index_object(index: dict[str, dict[str, Any]], obj: JumpResearchObject) -> None:
    home_id = _object_folder_id(obj, obj.home_sport)
    home_parent = f"sport.{obj.home_sport.lower()}"
    _add(
        index,
        _node(
            home_id,
            obj.display_name,
            "FOLDER",
            parent_id=home_parent,
            system_owner="data_modeling",
            sport=obj.home_sport,
            strategy=obj.research_object_id,
            source_path=obj.package_folder and f"research/superasi/library/{obj.package_folder}",
            api_target=f"/jump/research/{obj.canonical_key}",
            frontend_target=f"http://127.0.0.1:5179/?app=jump#/{obj.home_sport.lower()}/{obj.canonical_key}",
            status=obj.status,
            description=obj.population_label,
            tags=["research_object", obj.home_sport.lower()],
            extra={
                "canonical_key": obj.canonical_key,
                "display_name": obj.display_name,
                "uuid": obj.uuid,
                "package_id": obj.package_id,
                "needs_resolution": bool(obj.unresolved_aliases) or obj.status == "NEEDS_RESOLUTION",
                "updated_at": (obj.metadata or {}).get("imported_at"),
                "created_at": (obj.metadata or {}).get("imported_at"),
                "version": (obj.metadata or {}).get("code_version"),
                "manifest_hash": obj.question_hash,
            },
        ),
    )
    for sport in obj.sports:
        if sport == obj.home_sport:
            continue
        alias_id = _object_folder_id(obj, sport)
        _add(
            index,
            _node(
                alias_id,
                obj.display_name,
                "FOLDER",
                parent_id=f"sport.{sport.lower()}",
                system_owner="data_modeling",
                sport=sport,
                strategy=obj.research_object_id,
                api_target=f"/jump/research/{obj.canonical_key}",
                frontend_target=f"http://127.0.0.1:5179/?app=jump#/{sport.lower()}/{obj.canonical_key}",
                status="SHARED",
                description=f"Same object as {obj.home_sport}/{obj.display_name}. Shared id, not a copy.",
                tags=["research_object", "shared", sport.lower()],
                extra={
                    "canonical_key": obj.canonical_key,
                    "display_name": obj.display_name,
                    "shared_of": home_id,
                    "uuid": obj.uuid,
                    "package_id": obj.package_id,
                    "needs_resolution": bool(obj.unresolved_aliases),
                },
            ),
        )

    for slug, title, note in (
        ("data", "Data", "Dataset pointers. Jump does not duplicate warehouse files."),
        ("models", "Models", "Model references. Not executable."),
        ("source-artifacts", "Source Artifacts", "Canonical source pointers."),
    ):
        has_children = any(art.parent_folder == slug for art in obj.artifacts)
        if not has_children:
            continue
        _add(
            index,
            _node(
                f"research.{obj.canonical_key}.{slug}",
                title,
                "FOLDER",
                parent_id=home_id,
                system_owner="data_modeling",
                sport=obj.home_sport,
                status=PRESENT,
                description=note,
                extra={"canonical_key": obj.canonical_key, "display_name": title},
            ),
        )

    for doc in obj.documents:
        _add(
            index,
            _node(
                _doc_node_id(doc.doc_id),
                doc.title,
                "DOCUMENT",
                parent_id=home_id,
                system_owner="data_modeling",
                sport=obj.home_sport,
                source_path=None,
                api_target=f"/jump/documents/{doc.doc_id}",
                frontend_target=(
                    f"http://127.0.0.1:5179/?app=jump#/{obj.home_sport.lower()}/{obj.canonical_key}/{doc.slug}"
                ),
                status=doc.status,
                description="Generated projection from ROLLER/SuperASI sources.",
                tags=["document", doc.slug],
                extra={
                    "canonical_key": obj.canonical_key,
                    "display_name": doc.title,
                    "slug": doc.slug,
                    "doc_id": doc.doc_id,
                    "body_markdown": doc.body_markdown,
                    "provenance": [row.as_dict() for row in doc.provenance],
                },
            ),
        )

    for art in obj.artifacts:
        parent = f"research.{obj.canonical_key}.{art.parent_folder}" if art.parent_folder else home_id
        if parent not in index:
            parent = home_id
        warehouse_id = None
        table_name = None
        artifact_type = "ARTIFACT"
        frontend_target = None
        sport = obj.home_sport
        if art.kind == "warehouse":
            artifact_type = "WAREHOUSE"
            warehouse_id = art.name.split()[0].lower() if art.name else None
            if warehouse_id:
                sport = warehouse_id.upper() if warehouse_id != "wnba" else "WNBA"
                if warehouse_id in {"nba", "ncaab", "wnba"}:
                    sport = warehouse_id.upper()
                frontend_target = f"http://127.0.0.1:5179/?app=jump#/{warehouse_id}/warehouses/{warehouse_id}"
        elif art.kind == "table":
            artifact_type = "TABLE"
            bits = art.name.split(".", 1)
            warehouse_id = bits[0].lower() if bits else None
            table_name = bits[1] if len(bits) == 2 else None
            if warehouse_id:
                sport = warehouse_id.upper()
                frontend_target = (
                    f"http://127.0.0.1:5179/?app=jump#/{warehouse_id}/warehouses/{warehouse_id}/tables/{table_name}"
                )
        _add(
            index,
            _node(
                art.artifact_id,
                art.name,
                artifact_type,
                parent_id=parent,
                system_owner="data_modeling" if art.kind == "model" else (
                    "database" if art.source_path.startswith("ROLLER/") else "data_analysis"
                ),
                sport=sport,
                source_path=art.source_path,
                api_target=(
                    f"/jump/warehouses/{warehouse_id}"
                    if artifact_type == "WAREHOUSE" and warehouse_id
                    else (
                        f"/jump/warehouses/{warehouse_id}/tables/{table_name}"
                        if artifact_type == "TABLE" and warehouse_id and table_name
                        else f"/jump/artifacts/{art.artifact_id}/preview"
                    )
                ),
                frontend_target=frontend_target,
                status=art.status,
                description=art.note,
                extra={
                    "canonical_key": obj.canonical_key,
                    "display_name": art.name,
                    "kind": art.kind,
                    "warehouse_id": warehouse_id,
                    "table_name": table_name,
                    "used_by": ["FIRST80_ASKED_SIX_80_40"] if artifact_type in {"WAREHOUSE", "TABLE"} else None,
                },
            ),
        )


def build_library(*, force: bool = False, root=None) -> dict[str, Any]:
    global _CACHE
    with _LOCK:
        if _CACHE is not None and not force:
            return _CACHE
        repo = root or repo_root()
        objects = resolve_all_jump_research_objects(root=repo)
        index: dict[str, dict[str, Any]] = {}
        _add(
            index,
            _node(
                ROOT_ID,
                "Jump",
                "FOLDER",
                parent_id=None,
                system_owner="data_modeling",
                description="Data Modeling research filesystem. Sport-first. Pointers to ROLLER and SuperASI.",
                frontend_target="http://127.0.0.1:5179/?app=jump",
                tags=["drive", "root"],
                extra={"default_sport": DEFAULT_SPORT},
            ),
        )
        by_sport: dict[str, int] = {sport: 0 for sport in SPORT_ORDER}
        for obj in objects:
            for sport in obj.sports:
                if sport in by_sport:
                    by_sport[sport] += 1
            if not obj.sports and obj.home_sport in by_sport:
                by_sport[obj.home_sport] += 1
        for sport in SPORT_ORDER:
            count = by_sport.get(sport, 0)
            _add(
                index,
                _node(
                    f"sport.{sport.lower()}",
                    sport,
                    "FOLDER",
                    parent_id=ROOT_ID,
                    system_owner="data_modeling",
                    sport=sport,
                    api_target=f"/jump/research?sport={sport}",
                    frontend_target=f"http://127.0.0.1:5179/?app=jump#/{sport.lower()}",
                    status=PRESENT if count else "EMPTY",
                    description=_empty_message(sport) if count == 0 else f"{sport} research objects.",
                    tags=["sport", "root"],
                    extra={"object_count": count, "empty_message": _empty_message(sport)},
                ),
            )
        for obj in objects:
            _index_object(index, obj)
        payload = {
            "index": index,
            "objects": {obj.canonical_key: obj for obj in objects},
            "built_at": _utc_now(),
        }
        _CACHE = payload
        return payload


def reset_library_cache() -> None:
    global _CACHE
    with _LOCK:
        _CACHE = None


def build_index() -> dict[str, dict[str, Any]]:
    return build_library()["index"]


def _objects() -> dict[str, JumpResearchObject]:
    return build_library()["objects"]


def breadcrumbs(index: dict[str, dict[str, Any]], artifact_id: str) -> list[dict[str, str]]:
    trail: list[dict[str, str]] = []
    current = index.get(artifact_id)
    seen: set[str] = set()
    while current and current["artifact_id"] not in seen:
        seen.add(current["artifact_id"])
        trail.append({"artifact_id": current["artifact_id"], "name": current["name"]})
        parent = current.get("parent_folder")
        current = index.get(parent) if parent else None
    trail.reverse()
    return trail


def _normalize_sport(sport: str | None) -> str:
    token = str(sport or DEFAULT_SPORT).strip().upper()
    if token not in SPORT_ORDER:
        from roller.jump.errors import JumpError

        raise JumpError("RESULT_NOT_FOUND", f"unknown sport {sport}")
    return token


def handle_root(sport: str | None = None) -> dict[str, Any]:
    library = build_library()
    index = library["index"]
    chosen = _normalize_sport(sport or DEFAULT_SPORT)
    sport_id = f"sport.{chosen.lower()}"
    return {
        "schema_version": DRIVE_SCHEMA,
        "product": "Jump",
        "role": "data_modeling_drive",
        "live_execution": LIVE_EXECUTION,
        "bot_ui": False,
        "writable": False,
        "default_sport": DEFAULT_SPORT,
        "sport": chosen,
        "sports": handle_sports()["sports"],
        "roots": [_public(row) for row in _children(index, ROOT_ID)],
        "children": [_public(row) for row in _children(index, sport_id)],
        "empty_message": _empty_message(chosen) if not _children(index, sport_id) else None,
        "built_at": library["built_at"],
    }


def handle_sports() -> dict[str, Any]:
    index = build_index()
    sports = []
    for sport in SPORT_ORDER:
        row = index[f"sport.{sport.lower()}"]
        sports.append(
            {
                "id": sport,
                "name": sport,
                "artifact_id": row["artifact_id"],
                "object_count": row.get("object_count") or 0,
                "status": row["status"],
                "empty_message": row.get("empty_message"),
            }
        )
    return {
        "default_sport": DEFAULT_SPORT,
        "sports": sports,
        "live_execution": LIVE_EXECUTION,
    }


def handle_tree() -> dict[str, Any]:
    index = build_index()

    def walk(parent_id: str, depth: int = 0) -> list[dict[str, Any]]:
        out = []
        for row in _children(index, parent_id):
            item = _public(row)
            if "body_markdown" in item:
                item = dict(item)
                item.pop("body_markdown", None)
            if row["artifact_type"] == "FOLDER" and depth < 1:
                item["children"] = walk(row["artifact_id"], depth + 1)
            out.append(item)
        return out

    return {"schema_version": DRIVE_SCHEMA, "live_execution": LIVE_EXECUTION, "tree": walk(ROOT_ID)}


def handle_folder(folder_id: str) -> dict[str, Any]:
    index = build_index()
    row = index.get(folder_id)
    if row is None:
        objects = _objects()
        if folder_id in objects:
            return handle_research_children(folder_id)
        from roller.jump.errors import JumpError

        raise JumpError("RESULT_NOT_FOUND", f"unknown folder {folder_id}")
    parent_id = folder_id
    if row.get("status") == "SHARED" and row.get("shared_of"):
        parent_id = str(row["shared_of"])
    children = [_public(child) for child in _children(index, parent_id)]
    for child in children:
        child.pop("body_markdown", None)
    return {
        "folder": _public({k: v for k, v in row.items() if k != "body_markdown"}),
        "breadcrumbs": breadcrumbs(index, folder_id),
        "children": children,
        "live_execution": LIVE_EXECUTION,
        "empty_message": row.get("empty_message") if not children else None,
    }


def handle_artifact(artifact_id: str) -> dict[str, Any]:
    index = build_index()
    row = index.get(artifact_id)
    if row is None:
        from roller.jump.errors import JumpError

        raise JumpError("RESULT_NOT_FOUND", f"unknown artifact {artifact_id}")
    return {
        "artifact": _public(row),
        "breadcrumbs": breadcrumbs(index, artifact_id),
        "live_execution": LIVE_EXECUTION,
    }


def handle_research(sport: str | None = None) -> dict[str, Any]:
    chosen = _normalize_sport(sport or DEFAULT_SPORT)
    objects = _objects()
    rows = []
    for obj in objects.values():
        if chosen in obj.sports or (not obj.sports and obj.home_sport == chosen):
            rows.append(obj.as_dict())
    rows.sort(key=lambda row: str(row["display_name"]).lower())
    return {
        "sport": chosen,
        "default_sport": DEFAULT_SPORT,
        "count": len(rows),
        "objects": rows,
        "empty_message": _empty_message(chosen) if not rows else None,
        "live_execution": LIVE_EXECUTION,
    }


def _lookup_object(identifier: str) -> JumpResearchObject:
    from roller.jump.errors import JumpError
    from roller.jump.research import ASKED_SIX_KEY, _is_asked_six_token

    objects = _objects()
    if identifier in objects:
        return objects[identifier]
    if _is_asked_six_token(identifier) and ASKED_SIX_KEY in objects:
        return objects[ASKED_SIX_KEY]
    for obj in objects.values():
        aliases = {obj.package_id or "", obj.package_folder or "", obj.research_object_id or "", obj.display_name}
        if identifier in aliases:
            return obj
        for alias in obj.unresolved_aliases:
            path = str(alias.path or "")
            if path.endswith("/" + identifier) or path.endswith(identifier):
                return obj
    raise JumpError("RESULT_NOT_FOUND", f"unknown research object {identifier}")


def handle_research_object(canonical_key: str) -> dict[str, Any]:
    obj = _lookup_object(canonical_key)
    return {
        "object": obj.as_dict(include_documents=True),
        "live_execution": LIVE_EXECUTION,
        "writable": False,
    }


def handle_research_children(canonical_key: str) -> dict[str, Any]:
    obj = _lookup_object(canonical_key)
    index = build_index()
    folder_id = _object_folder_id(obj, obj.home_sport)
    row = index.get(folder_id)
    if row is None:
        from roller.jump.errors import JumpError

        raise JumpError("RESULT_NOT_FOUND", f"unknown research object {canonical_key}")
    return {
        "object": obj.as_dict(),
        "folder": _public(row),
        "breadcrumbs": breadcrumbs(index, folder_id),
        "children": [_public({k: v for k, v in child.items() if k != "body_markdown"}) for child in _children(index, folder_id)],
        "live_execution": LIVE_EXECUTION,
    }


def handle_document(doc_id: str) -> dict[str, Any]:
    index = build_index()
    row = index.get(doc_id)
    if row is None or row.get("artifact_type") != "DOCUMENT":
        from roller.jump.errors import JumpError

        raise JumpError("RESULT_NOT_FOUND", f"unknown document {doc_id}")
    objects = _objects()
    obj = objects.get(str(row.get("canonical_key") or ""))
    return {
        "document": {
            "doc_id": doc_id,
            "title": row["name"],
            "slug": row.get("slug"),
            "canonical_key": row.get("canonical_key"),
            "body_markdown": row.get("body_markdown") or "",
            "body": row.get("body_markdown") or "",
            "provenance": row.get("provenance") or [],
            "status": row.get("status"),
            "live_execution": LIVE_EXECUTION,
        },
        "object": obj.as_dict() if obj else None,
        "breadcrumbs": breadcrumbs(index, doc_id),
        "live_execution": LIVE_EXECUTION,
        "writable": False,
    }


def handle_search(q: str) -> dict[str, Any]:
    needle = q.strip().lower()
    index = build_index()
    objects = _objects()
    hits: list[dict[str, Any]] = []
    if needle:
        for obj in objects.values():
            hay = " ".join(
                [
                    obj.display_name,
                    obj.canonical_key,
                    obj.package_id or "",
                    obj.package_folder or "",
                    obj.research_object_id or "",
                    " ".join(obj.sports),
                    obj.population_label,
                    obj.question_hash or "",
                    obj.uuid or "",
                    " ".join(alias.path for alias in obj.unresolved_aliases),
                    " ".join(alias.note for alias in obj.unresolved_aliases),
                ]
            ).lower()
            if needle in hay:
                hits.append(
                    {
                        "title": obj.display_name,
                        "name": obj.display_name,
                        "kind": "folder",
                        "canonical_key": obj.canonical_key,
                        "folder": obj.display_name,
                        "sport": obj.home_sport,
                        "artifact_id": _object_folder_id(obj, obj.home_sport),
                        "snippet": obj.population_label,
                    }
                )
            for doc in obj.documents:
                doc_hay = f"{doc.title} {doc.body_markdown} {doc.doc_id}".lower()
                if needle in doc_hay:
                    idx = doc_hay.find(needle)
                    snippet = doc.body_markdown[max(0, idx - 40) : idx + 80].replace("\n", " ")
                    hits.append(
                        {
                            "title": doc.title,
                            "name": doc.title,
                            "kind": "document",
                            "canonical_key": obj.canonical_key,
                            "folder": obj.display_name,
                            "sport": obj.home_sport,
                            "artifact_id": doc.doc_id,
                            "doc_id": doc.doc_id,
                            "slug": doc.slug,
                            "snippet": snippet.strip(),
                        }
                    )
            for art in obj.artifacts:
                art_hay = f"{art.name} {art.source_path} {art.artifact_id}".lower()
                if needle in art_hay:
                    hits.append(
                        {
                            "title": art.name,
                            "name": art.name,
                            "kind": "artifact",
                            "canonical_key": obj.canonical_key,
                            "folder": obj.display_name,
                            "sport": obj.home_sport,
                            "artifact_id": art.artifact_id,
                            "snippet": art.source_path,
                        }
                    )
        for row in index.values():
            if row["artifact_type"] == "FOLDER" and str(row.get("artifact_id") or "").startswith("sport."):
                hay = f"{row.get('name')} {row.get('description')}".lower()
                if needle in hay:
                    hits.append(
                        {
                            "title": row["name"],
                            "name": row["name"],
                            "kind": "sport",
                            "canonical_key": None,
                            "folder": row["name"],
                            "sport": row.get("sport"),
                            "artifact_id": row["artifact_id"],
                            "snippet": row.get("description") or "",
                        }
                    )
    # Prefer folder context titles; drop duplicate artifact_ids
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for hit in hits:
        key = str(hit.get("artifact_id") or hit.get("title"))
        if key in seen:
            continue
        seen.add(key)
        unique.append(hit)
    return {
        "q": q,
        "count": len(unique),
        "results": unique[:80],
        "live_execution": LIVE_EXECUTION,
    }


def handle_recent() -> dict[str, Any]:
    objects = _objects()
    rows = list(objects.values())
    rows.sort(key=lambda obj: str((obj.metadata or {}).get("imported_at") or obj.display_name), reverse=True)
    results = []
    for obj in rows[:30]:
        results.append(
            {
                "title": obj.display_name,
                "name": obj.display_name,
                "canonical_key": obj.canonical_key,
                "folder": obj.display_name,
                "sport": obj.home_sport,
                "kind": "folder",
                "artifact_id": _object_folder_id(obj, obj.home_sport),
                "updated_at": (obj.metadata or {}).get("imported_at"),
                "status": obj.status,
            }
        )
    return {"results": results, "live_execution": LIVE_EXECUTION}


def handle_edges(artifact_id: str, direction: str) -> dict[str, Any]:
    index = build_index()
    row = index.get(artifact_id)
    if row is None:
        from roller.jump.errors import JumpError

        raise JumpError("RESULT_NOT_FOUND", f"unknown artifact {artifact_id}")
    key = "upstream_artifacts" if direction == "upstream" else "downstream_artifacts"
    ids = list(row.get(key) or [])
    return {
        "artifact_id": artifact_id,
        "direction": direction,
        "results": [_public(index[item]) for item in ids if item in index],
        "unresolved": [item for item in ids if item not in index],
        "live_execution": LIVE_EXECUTION,
    }


def handle_preview(artifact_id: str) -> dict[str, Any]:
    index = build_index()
    row = index.get(artifact_id)
    if row is None:
        from roller.jump.errors import JumpError

        raise JumpError("RESULT_NOT_FOUND", f"unknown artifact {artifact_id}")
    rel = row.get("source_path")
    kind = row.get("kind") or ""
    artifact_type = row.get("artifact_type")
    if artifact_type in {"WAREHOUSE", "TABLE"}:
        return {
            "artifact_id": artifact_id,
            "name": row.get("name"),
            "source_path": rel,
            "status": row.get("status") or "POINTER",
            "kind": kind or artifact_type.lower(),
            "artifact_type": artifact_type,
            "warehouse_id": row.get("warehouse_id"),
            "table_name": row.get("table_name"),
            "frontend_target": row.get("frontend_target"),
            "preview": None,
            "note": "Phase 8 parquet desk. Open in the warehouse workbench. Jump does not copy rows.",
            "live_execution": LIVE_EXECUTION,
        }
    if not rel:
        return {
            "artifact_id": artifact_id,
            "name": row.get("name"),
            "source_path": None,
            "status": "SOURCE_UNAVAILABLE",
            "preview": None,
            "note": "Unavailable",
            "live_execution": LIVE_EXECUTION,
        }
    path = repo_root() / str(rel)
    if not path.is_file():
        return {
            "artifact_id": artifact_id,
            "name": row.get("name"),
            "source_path": rel,
            "status": "MISSING" if not path.exists() else "POINTER",
            "preview": None,
            "kind": kind,
            "note": "Directory pointer" if path.is_dir() else "Unavailable",
            "live_execution": LIVE_EXECUTION,
        }
    size = path.stat().st_size
    if size > PREVIEW_MAX_BYTES:
        return {
            "artifact_id": artifact_id,
            "name": row.get("name"),
            "source_path": rel,
            "status": "TOO_LARGE",
            "bytes": size,
            "preview": None,
            "note": "Preview capped. Canonical file is not copied.",
            "live_execution": LIVE_EXECUTION,
        }
    text = path.read_text(encoding="utf-8")
    preview: Any
    truncated = False
    suffix = path.suffix.lower()
    if suffix == ".json":
        import json

        payload = json.loads(text)
        if isinstance(payload, list):
            truncated = len(payload) > PREVIEW_MAX_ROWS
            preview = payload[:PREVIEW_MAX_ROWS]
        elif isinstance(payload, dict):
            keys = list(payload.keys())
            preview = {key: payload[key] for key in keys[:40]}
            truncated = len(keys) > 40
        else:
            preview = payload
    elif suffix == ".csv":
        lines = text.splitlines()
        truncated = len(lines) > PREVIEW_MAX_ROWS + 1
        preview = "\n".join(lines[: PREVIEW_MAX_ROWS + 1])
    else:
        preview = text[:8000]
        truncated = len(text) > 8000
    return {
        "artifact_id": artifact_id,
        "name": row.get("name"),
        "source_path": rel,
        "kind": kind or suffix.lstrip("."),
        "status": PRESENT,
        "truncated": truncated,
        "preview": preview,
        "note": "Pointer preview. Jump does not duplicate the canonical file.",
        "live_execution": LIVE_EXECUTION,
    }


def handle_refresh() -> dict[str, Any]:
    library = build_library(force=True)
    return {
        "status": "ok",
        "rebuilt_at": library["built_at"],
        "object_count": len(library["objects"]),
        "artifact_count": len(library["index"]),
        "live_execution": LIVE_EXECUTION,
        "writable": False,
    }
