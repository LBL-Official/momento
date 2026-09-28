"""Tree and graph from systems.csv + connections.csv only."""

from __future__ import annotations

import json
from collections import defaultdict, deque
from typing import Any

from roller.systimo.models import now_iso
from roller.systimo.paths import generated_dir
from roller.systimo.store import CsvStore


def load_graph(store: CsvStore | None = None) -> dict[str, Any]:
    csv = store or CsvStore()
    systems = csv.read("systems")
    connections = csv.read("connections")
    nodes = []
    for row in systems:
        nodes.append(
            {
                "id": row["system_id"],
                "type": "SYSTEM",
                "name": row["name"],
                "product": row["product_name"],
                "domain": row["domain"],
                "status": row["status"],
                "ownership": row["owner_type"],
                "execution_capable": row["execution_capable"] == "true",
                "canonical_role": row["canonical_role"],
            }
        )
    edges = []
    for row in connections:
        edges.append(
            {
                "id": row["connection_id"],
                "source": row["source_system_id"],
                "target": row["target_system_id"],
                "connection_type": row["connection_type"],
                "direction": row["direction"],
                "health": row["health"],
                "lifecycle": row["lifecycle"],
                "permission": row["permission"],
                "schema": row["schema_version"],
                "capability": row["capability"],
            }
        )
    return {
        "generated_at": now_iso(),
        "nodes": nodes,
        "edges": edges,
        "node_count": len(nodes),
        "edge_count": len(edges),
    }


def load_tree(store: CsvStore | None = None) -> dict[str, Any]:
    graph = load_graph(store)
    by_domain: dict[str, list[dict[str, Any]]] = defaultdict(list)
    nodes = {node["id"]: node for node in graph["nodes"]}
    outgoing = defaultdict(list)
    incoming = defaultdict(list)
    for edge in graph["edges"]:
        outgoing[edge["source"]].append(edge)
        incoming[edge["target"]].append(edge)
    for node in graph["nodes"]:
        by_domain[node["domain"]].append(
            {
                **node,
                "reads": [
                    {
                        "connection_id": edge["id"],
                        "source": edge["source"],
                        "lifecycle": edge["lifecycle"],
                        "health": edge["health"],
                    }
                    for edge in incoming.get(node["id"], [])
                ],
                "consumed_by": [
                    {
                        "connection_id": edge["id"],
                        "target": edge["target"],
                        "lifecycle": edge["lifecycle"],
                        "health": edge["health"],
                    }
                    for edge in outgoing.get(node["id"], [])
                ],
            }
        )
    return {
        "generated_at": graph["generated_at"],
        "root": "Momento Systems",
        "domains": {key: by_domain[key] for key in sorted(by_domain)},
        "systems": nodes,
    }


def paths(store: CsvStore, source: str, target: str, limit: int = 8) -> list[list[str]]:
    graph = load_graph(store)
    adj: dict[str, list[str]] = defaultdict(list)
    for edge in graph["edges"]:
        adj[edge["source"]].append(edge["target"])
    found: list[list[str]] = []
    queue: deque[list[str]] = deque([[source]])
    while queue and len(found) < limit:
        trail = queue.popleft()
        here = trail[-1]
        if here == target and len(trail) > 1:
            found.append(trail)
            continue
        if len(trail) > 8:
            continue
        for nxt in adj.get(here, []):
            if nxt in trail:
                continue
            queue.append(trail + [nxt])
    return found


def path_back(store: CsvStore, start: str, limit: int = 8) -> list[list[str]]:
    graph = load_graph(store)
    incoming: dict[str, list[str]] = defaultdict(list)
    for edge in graph["edges"]:
        incoming[edge["target"]].append(edge["source"])
    found: list[list[str]] = []
    queue: deque[list[str]] = deque([[start]])
    while queue and len(found) < limit:
        trail = queue.popleft()
        here = trail[-1]
        parents = incoming.get(here, [])
        if not parents and len(trail) > 1:
            found.append(trail)
            continue
        if len(trail) > 8:
            continue
        branched = False
        for prev in parents:
            if prev in trail:
                continue
            branched = True
            queue.append(trail + [prev])
        if not branched and len(trail) > 1:
            found.append(trail)
    return found


def write_generated(store: CsvStore | None = None) -> dict[str, Any]:
    csv = store or CsvStore()
    tree = load_tree(csv)
    graph = load_graph(csv)
    out = generated_dir(csv.root)
    out.mkdir(parents=True, exist_ok=True)
    (out / "tree.json").write_text(json.dumps(tree, indent=2) + "\n", encoding="utf-8")
    (out / "graph.json").write_text(json.dumps(graph, indent=2) + "\n", encoding="utf-8")
    return {"tree": str(out / "tree.json"), "graph": str(out / "graph.json")}
