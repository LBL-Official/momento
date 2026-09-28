"""Write the V1 topology tables. Idempotent. Does not start processes."""

from __future__ import annotations

import json

from roller.systimo.store import CsvStore
from roller.systimo.topology import SYSTEM_TYPES

QUADS = (
    ("quad-1", "NBA", "Quad 1 — NBA North", "upper-left", "active", "lbl-north"),
    ("quad-2", "NCAAB", "Quad 2 — NCAAB", "upper-right", "placeholder", ""),
    ("quad-3", "WNBA", "Quad 3 — WNBA", "lower-right", "placeholder", ""),
    ("quad-4", "MLB", "Quad 4 — MLB", "lower-left", "placeholder", ""),
)
SUPPORT = (
    "system_maintenance",
    "data_ingestion",
    "trade_reconciliation",
    "system_orchestration",
)
GLOBAL_LABELS = {
    "system_maintenance": "Systimo",
    "data_ingestion": "Data Ingestion",
    "trade_reconciliation": "Trade Conciliation",
    "system_orchestration": "Orchestra",
}


def _service(
    service_id: str,
    argv: list[str],
    *,
    scope: str,
    mode: str,
    port: int | str,
    autostart: str,
    role: str,
    dependencies: str = "",
    policy: str = "preferred-with-fallback",
    probe: str = "/health",
    identity: str = "ok",
) -> dict[str, str]:
    return {
        "service_id": service_id,
        "argv_json": json.dumps(argv),
        "cwd": ".",
        "role": role,
        "dependencies": dependencies,
        "scope": scope,
        "enabled": "true",
        "autostart": autostart,
        "ownership_mode": mode,
        "port_policy": policy,
        "preferred_port": str(port),
        "probe_path": probe,
        "probe_timeout_ms": "3000",
        "probe_identity": identity,
    }


def build() -> dict[str, list[dict[str, str]]]:
    quadrants = [
        {
            "quadrant_id": qid,
            "sport": sport,
            "heading": heading,
            "position": position,
            "state": state,
            "alias": alias,
        }
        for qid, sport, heading, position, state, alias in QUADS
    ]
    instances: list[dict[str, str]] = []
    nodes: list[dict[str, str]] = []
    for qid, _sport, _heading, _position, _state, _alias in QUADS:
        for system_type in SYSTEM_TYPES:
            instance_id = f"{qid}:{system_type}"
            if qid == "quad-1" and system_type == "algorithmic_execution":
                interactive = "true"
                label = "Algorithmic Execution"
            elif qid == "quad-1":
                interactive = "true"
                label = "NBA North" if system_type == "momento_systems" else system_type
            elif system_type == "algorithmic_execution" and qid in {"quad-3", "quad-4"}:
                interactive = "true"
                label = "Algorithmic Execution"
            else:
                interactive = "false"
                label = ""
            instances.append(
                {
                    "instance_id": instance_id,
                    "quadrant_id": qid,
                    "system_type": system_type,
                    "label": label,
                    "interactive": interactive,
                }
            )
            override = "NBA North" if qid == "quad-1" and system_type == "momento_systems" else ""
            nodes.append(
                {
                    "node_id": f"node:{instance_id}",
                    "instance_id": instance_id,
                    "geometry_key": system_type,
                    "label_override": override,
                }
            )
    for system_type in SUPPORT:
        instance_id = f"global:{system_type}"
        instances.append(
            {
                "instance_id": instance_id,
                "quadrant_id": "global",
                "system_type": system_type,
                "label": GLOBAL_LABELS[system_type],
                "interactive": "true",
            }
        )
        nodes.append(
            {
                "node_id": f"node:{instance_id}",
                "instance_id": instance_id,
                "geometry_key": system_type,
                "label_override": GLOBAL_LABELS[system_type],
            }
        )
    services = [
        _service(
            "roller-api",
            ["ROLLER/.venv/bin/python", "ROLLER/scripts/terminal_api.py"],
            scope="shared",
            mode="shared",
            port=8791,
            autostart="true",
            role="controller",
        ),
        _service(
            "roller-terminal",
            ["npm", "run", "dev", "--prefix", "frontend/roller-terminal"],
            scope="shared",
            mode="shared",
            port=5179,
            autostart="true",
            role="frontend",
            dependencies="roller-api",
        ),
        _service(
            "choosin-texas",
            ["npm", "run", "dev", "--prefix", "frontend/choosin-texas"],
            scope="quad-1",
            mode="managed",
            port=5182,
            autostart="true",
            role="frontend",
            dependencies="roller-api",
        ),
        _service(
            "momento-shell",
            ["npm", "run", "dev", "--prefix", "frontend/momento-systems"],
            scope="shared",
            mode="shared",
            port=5190,
            autostart="true",
            role="frontend",
            dependencies="roller-api",
        ),
        _service(
            "drevo",
            ["npm", "run", "dev", "--prefix", "frontend/dynamic-risk-engine"],
            scope="quad-1",
            mode="managed",
            port=5191,
            autostart="true",
            role="frontend",
            dependencies="roller-api",
        ),
        _service(
            "ballhog",
            ["npm", "run", "dev", "--prefix", "frontend/ballhog"],
            scope="quad-1",
            mode="managed",
            port=5192,
            autostart="true",
            role="frontend",
            dependencies="roller-api",
        ),
        _service(
            "systimo-ui",
            ["npm", "run", "dev", "--prefix", "frontend/systimo"],
            scope="shared",
            mode="shared",
            port=5193,
            autostart="true",
            role="frontend",
            dependencies="roller-api",
        ),
        _service(
            "positman",
            ["npm", "run", "dev", "--prefix", "frontend/positman"],
            scope="quad-1",
            mode="managed",
            port=5194,
            autostart="true",
            role="frontend",
            dependencies="roller-api",
        ),
        _service(
            "mlb-execution-desk",
            ["npm", "run", "dev", "--prefix", "frontend/vital-terminal"],
            scope="quad-4",
            mode="managed",
            port=5180,
            autostart="true",
            role="observe-desk",
            dependencies="roller-api",
        ),
        _service(
            "momento-ls",
            ["ROLLER/.venv/bin/python", "ROLLER/scripts/ls_api.py"],
            scope="unmanaged",
            mode="unmanaged",
            port=8792,
            autostart="false",
            role="observe-adapter",
        ),
        _service(
            "mlb-001",
            [],
            scope="quad-4",
            mode="external",
            port="",
            autostart="false",
            role="remote-worker",
            policy="pinned",
            probe="",
            identity="",
        ),
    ]
    # pinned empty port is invalid for allocate but the row is not autostarted.
    services[-1]["preferred_port"] = "0"
    bindings = [
        ("bind:roller-api:database", "roller-api", "quad-1:database"),
        ("bind:roller-api:analysis", "roller-api", "quad-1:data_analysis"),
        ("bind:roller-api:modeling", "roller-api", "quad-1:data_modeling"),
        ("bind:roller-api:breakdown", "roller-api", "quad-1:trade_breakdown"),
        ("bind:roller-api:austin", "roller-api", "quad-1:position_stratification"),
        ("bind:roller-api:drevo", "roller-api", "quad-1:dynamic_risk_engine"),
        ("bind:roller-api:positman", "roller-api", "quad-1:position_management"),
        ("bind:roller-api:ballhog", "roller-api", "quad-1:hedging_analysis"),
        ("bind:roller-api:tk", "roller-api", "quad-1:relative_value_hedging"),
        ("bind:roller-api:ingest", "roller-api", "global:data_ingestion"),
        ("bind:roller-api:recon", "roller-api", "global:trade_reconciliation"),
        ("bind:roller-api:orchestra", "roller-api", "global:system_orchestration"),
        ("bind:roller-api:systimo", "roller-api", "global:system_maintenance"),
        ("bind:terminal:database", "roller-terminal", "quad-1:database"),
        ("bind:terminal:analysis", "roller-terminal", "quad-1:data_analysis"),
        ("bind:terminal:modeling", "roller-terminal", "quad-1:data_modeling"),
        ("bind:choosin:breakdown", "choosin-texas", "quad-1:trade_breakdown"),
        ("bind:choosin:austin", "choosin-texas", "quad-1:position_stratification"),
        ("bind:shell:systems", "momento-shell", "quad-1:momento_systems"),
        ("bind:shell:tk", "momento-shell", "quad-1:relative_value_hedging"),
        ("bind:shell:ingest", "momento-shell", "global:data_ingestion"),
        ("bind:shell:recon", "momento-shell", "global:trade_reconciliation"),
        ("bind:shell:orchestra", "momento-shell", "global:system_orchestration"),
        ("bind:shell:wnba-exec", "momento-shell", "quad-3:algorithmic_execution"),
        ("bind:drevo", "drevo", "quad-1:dynamic_risk_engine"),
        ("bind:ballhog", "ballhog", "quad-1:hedging_analysis"),
        ("bind:systimo-ui:global", "systimo-ui", "global:system_maintenance"),
        ("bind:systimo-ui:nba", "systimo-ui", "quad-1:system_maintenance"),
        ("bind:positman", "positman", "quad-1:position_management"),
        ("bind:mlb-desk", "mlb-execution-desk", "quad-4:algorithmic_execution"),
        ("bind:mlb-001", "mlb-001", "quad-4:algorithmic_execution"),
    ]
    bots = [
        {
            "bot_id": "mlb-001",
            "sport": "MLB",
            "quadrant_id": "quad-4",
            "owner": "vital",
            "runtime_pointer": "momento-live.service",
            "desk_instance_id": "quad-4:algorithmic_execution",
            "verified": "true",
        },
        {
            "bot_id": "nba-001",
            "sport": "NBA",
            "quadrant_id": "quad-1",
            "owner": "vital",
            "runtime_pointer": "momento-nba-001.service",
            "desk_instance_id": "quad-1:algorithmic_execution",
            "verified": "true",
        },
    ]
    return {
        "quadrants": quadrants,
        "instances": instances,
        "nodes": nodes,
        "services": services,
        "service_bindings": [
            {"binding_id": bid, "service_id": sid, "instance_id": iid} for bid, sid, iid in bindings
        ],
        "bots": bots,
    }


def write(store: CsvStore | None = None) -> dict[str, int]:
    store = store or CsvStore()
    tables = build()
    counts = {}
    for name, rows in tables.items():
        store.write(name, rows)
        counts[name] = len(rows)
    return counts


if __name__ == "__main__":
    print(write())
