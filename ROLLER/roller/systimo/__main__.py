"""python -m roller.systimo"""

from __future__ import annotations

import argparse
import json
import sys

from roller.systimo.api import (
    handle_connections,
    handle_health,
    handle_query,
    handle_query_artifact,
    handle_refresh,
    handle_systems,
    handle_tree,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="roller.systimo")
    parser.add_argument("command", choices=["health", "refresh", "systems", "tree", "connections", "query", "artifact"])
    parser.add_argument("--type", dest="query_type", default="")
    parser.add_argument("--system", default="")
    parser.add_argument("--from", dest="src", default="")
    parser.add_argument("--to", dest="dst", default="")
    parser.add_argument("--health", dest="health_filter", default="")
    parser.add_argument("query_id", nargs="?", default="")
    args = parser.parse_args(argv)
    if args.command == "health":
        body = handle_health()
    elif args.command == "refresh":
        body = handle_refresh({})
    elif args.command == "systems":
        body = handle_systems()
    elif args.command == "tree":
        body = handle_tree()
    elif args.command == "connections":
        body = handle_connections()
    elif args.command == "query":
        payload = {"query_type": args.query_type, "system": args.system, "from": args.src, "to": args.dst}
        if args.health_filter:
            payload["health"] = args.health_filter
        body = handle_query(payload)
    elif args.command == "artifact":
        if not args.query_id:
            print("artifact requires query_id", file=sys.stderr)
            return 2
        body = handle_query_artifact(args.query_id)
    else:
        return 2
    print(json.dumps(body, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
