"""Local ./momento CLI. Daily use takes no port arguments."""

from __future__ import annotations

import argparse
import json
import sys

from roller.systimo.errors import SystimoError
from roller.systimo.lifecycle import adopt, controller_port, launch, plan, read_runtime, stop_owned
from roller.systimo.store import CsvStore
from roller.systimo.topology import topology_status


def _print(body: dict) -> None:
    json.dump(body, sys.stdout, indent=2)
    sys.stdout.write("\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="momento")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("up", "down", "status", "plan", "doctor", "ports", "connections", "open"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--scope", default="all")
    start = sub.add_parser("start")
    start.add_argument("service_id")
    start.add_argument("--scope", default="all")
    stop = sub.add_parser("stop")
    stop.add_argument("service_id")
    stop.add_argument("--scope", default="all")
    restart = sub.add_parser("restart")
    restart.add_argument("service_id")
    restart.add_argument("--scope", default="all")
    logs = sub.add_parser("logs")
    logs.add_argument("service_id")
    logs.add_argument("--scope", default="all")
    ports_set = sub.add_parser("ports-set")
    ports_set.add_argument("service_id")
    ports_set.add_argument("--policy", required=True)
    ports_set.add_argument("--preferred", required=True, type=int)
    ports_set.add_argument("--scope", default="global")
    adopt_cmd = sub.add_parser("adopt")
    adopt_cmd.add_argument("service_id")
    adopt_cmd.add_argument("--pid", required=True, type=int)
    adopt_cmd.add_argument("--port", required=True, type=int)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    store = CsvStore()
    try:
        if args.command == "plan":
            _print(plan(args.scope, store))
            return 0
        if args.command == "doctor":
            _print(
                {
                    "topology": topology_status(store),
                    "controller_port": controller_port(store),
                    "live_execution": False,
                    "arms_trading": False,
                }
            )
            return 0
        if args.command == "status":
            _print({"scope": args.scope, "runs": read_runtime(store)["runs"], "trading_armed": False})
            return 0
        if args.command == "ports":
            from roller.systimo.ports import read_leases

            _print({"leases": read_leases(store), "controller_port": controller_port(store)})
            return 0
        if args.command == "connections":
            _print({"connections": store.read("connections"), "scope": args.scope})
            return 0
        if args.command == "open":
            port = controller_port(store)
            shell = read_runtime(store)["runs"].get("momento-shell")
            if shell and shell.get("owned"):
                _print({"url": f"http://127.0.0.1:{shell['port']}/#/quad/{args.scope}"})
            else:
                _print({"url": None, "controller_port": port, "status": "UNAVAILABLE"})
            return 0
        if args.command == "adopt":
            _print(adopt(args.service_id, pid=args.pid, port=args.port, store=store))
            return 0
        if args.command == "up":
            _print(launch(args.scope, store))
            return 0
        if args.command == "down":
            _print(stop_owned(args.scope, store))
            return 0
        if args.command in {"start", "stop", "restart", "logs", "ports-set"}:
            _print(
                {
                    "command": args.command,
                    "scope": getattr(args, "scope", None),
                    "service_id": getattr(args, "service_id", None),
                    "status": "RECORDED",
                    "live_execution": False,
                    "arms_trading": False,
                    "note": "up does not start momento-live.service and does not set VITAL_AWS_CONTROL",
                }
            )
            return 0
    except SystimoError as exc:
        _print(exc.as_dict())
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
