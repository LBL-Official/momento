"""Generate, execute, independently evaluate, and save three NBA strategies."""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import urllib.error
import urllib.request

from roller.config import RollerConfig
from roller.labs.schema import CSV_COLUMNS
from roller.labs.store import get_lab_csv_bytes, save_lab
from roller.research_query.models import ResearchQuestion
from roller.warehouse.production import unavailable_production_sport

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from independent_nba_evaluator import compare_production, evaluate_question

VALIDATION_SEED = 20260913
ENTRY_OPS = ("CROSS", "BREAK", "ABOVE", "BELOW", "FIRST_TOUCH")
EXIT_OPS = ("REACH", "DROP_TO", "RISE_TO")
PERIODS = (None, "Q1", "Q2", "Q3", "Q4")
THRESHOLDS = (55, 60, 63, 65, 70, 75, 80)
WIN_THRESHOLDS = (80, 85, 87, 90)
LOSS_THRESHOLDS = (30, 35, 40, 41, 45)


def _question(spec: dict) -> dict:
    period = spec.get("period")
    entry = {
        "id": "e1",
        "ordinal": "FIRST_TOUCH",
        "price_e4": int(spec["entry_cents"]) * 100,
        "period": period,
        "clock": None,
        "nth": None,
        "event_definition": "TRADABLE_CLOSE_CROSS",
        "price_field": "yes_bid_close",
        "operation": spec["entry_op"],
    }
    return {
        "universe": {
            "sports": ["NBA"],
            "leagues": ["NBA"],
            "seasons": ["2025-2026"],
            "markets": ["kalshi"],
            "market_data": ["candles"],
            "game_data": ["pbp"] if period else [],
            "date_from": spec["date_from"],
            "date_to": spec["date_to"],
        },
        "entry_conditions": [entry],
        "path_conditions": [
            {
                "id": "win",
                "op": spec["win_op"],
                "price_e4": int(spec["win_cents"]) * 100,
                "sequential": False,
                "outcome": "win",
            },
            {
                "id": "loss",
                "op": spec["loss_op"],
                "price_e4": int(spec["loss_cents"]) * 100,
                "sequential": False,
                "outcome": "loss",
            },
        ],
        "terminal": spec["terminal"],
        "requested_dimensions": ["HOLD_TO_SETTLEMENT"],
        "accept_limitations": False,
        "win_hold": spec["terminal"] in {"YES", "BOTH"},
        "loss_hold": spec["terminal"] in {"NO", "BOTH"},
    }


def _draw(rng: random.Random, used: set[tuple]) -> dict:
    for _ in range(80):
        spec = {
            "entry_op": rng.choice(ENTRY_OPS),
            "entry_cents": rng.choice(THRESHOLDS),
            "period": rng.choice(PERIODS),
            "win_op": rng.choice(("REACH", "RISE_TO")),
            "win_cents": rng.choice(WIN_THRESHOLDS),
            "loss_op": rng.choice(("REACH", "DROP_TO")),
            "loss_cents": rng.choice(LOSS_THRESHOLDS),
            "terminal": rng.choice(("BOTH", "YES", "NO")),
            "date_from": "2025-10-10",
            "date_to": "2025-10-31",
        }
        if spec["win_cents"] <= spec["entry_cents"] or spec["loss_cents"] >= spec["entry_cents"]:
            continue
        key = (spec["entry_op"], spec["entry_cents"], spec["period"], spec["win_op"], spec["loss_op"], spec["terminal"])
        if key in used:
            continue
        used.add(key)
        return spec
    raise RuntimeError("could not draw a distinct valid strategy")


def _post_execute(question: dict, base: str) -> tuple[dict, float]:
    raw = json.dumps({"question": question, "engine_id": "optimized"}).encode("utf-8")
    req = urllib.request.Request(
        f"{base}/warehouse-research/execute",
        data=raw,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=600) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return body, time.perf_counter() - t0


def _name(spec: dict, index: int) -> str:
    period = spec["period"] or "GAME"
    return (
        f"NBA {period} {spec['entry_op']} {spec['entry_cents']} — "
        f"{spec['win_op']} {spec['win_cents']} / {spec['loss_op']} {spec['loss_cents']} #{index}"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=VALIDATION_SEED)
    parser.add_argument("--out", default=str(_ROOT / "reports" / "three_random_nba_validation.json"))
    parser.add_argument("--api", default="http://127.0.0.1:8791")
    args = parser.parse_args()
    rng = random.Random(args.seed)
    cfg = RollerConfig(_ROOT)
    used: set[tuple] = set()
    strategies = []
    for i in range(1, 4):
        strategy_seed = rng.randint(1, 10_000_000)
        local = random.Random(strategy_seed)
        spec = None
        payload = None
        question = None
        for _ in range(40):
            spec = _draw(local, used)
            question = _question(spec)
            model = ResearchQuestion.from_dict(question)
            if unavailable_production_sport(model) is not None:
                continue
            payload, backend_s = _post_execute(question, args.api)
            if payload.get("status") in {"READY", "ZERO_RESULTS"}:
                payload["_backend_s"] = backend_s
                break
            payload = None
        if payload is None or spec is None or question is None:
            raise SystemExit(f"strategy {i} could not compile READY/ZERO_RESULTS")
        t1 = time.perf_counter()
        expected = evaluate_question(ResearchQuestion.from_dict(question), cfg)
        expected["timings_s"]["wall"] = time.perf_counter() - t1
        cmp = compare_production(payload, expected)
        lab = save_lab(name=_name(spec, i), payload=payload, folder="validation", question=question, cfg=cfg)
        csv_found = get_lab_csv_bytes(lab["lab_id"], cfg)
        csv_ok = False
        if csv_found:
            header = csv_found[1].split(b"\n", 1)[0].decode("utf-8").split(",")
            csv_ok = header == list(CSV_COLUMNS) and csv_found[1] == csv_found[1]
        rec = {
            "index": i,
            "strategy_seed": strategy_seed,
            "name": _name(spec, i),
            "spec": spec,
            "question": question,
            "production_status": payload.get("status"),
            "plan_hash": payload.get("plan_hash"),
            "result_hash": (payload.get("result") or {}).get("result_hash"),
            "population": (payload.get("results_contract") or {}).get("population"),
            "classification": (payload.get("results_contract") or {}).get("classification"),
            "backend_s": payload.get("_backend_s"),
            "evaluator": expected,
            "comparison": cmp,
            "lab": {k: lab[k] for k in ("lab_id", "filename", "csv_sha256", "folder") if k in lab},
            "csv_schema_ok": csv_ok,
        }
        strategies.append(rec)
        print(
            f"S{i} status={rec['production_status']} N={rec['population']} "
            f"exact={cmp['exact']} diffs={cmp['difference_count']} backend={rec['backend_s']:.3f}s",
            flush=True,
        )
    exact = all(s["comparison"]["exact"] and s["csv_schema_ok"] for s in strategies)
    report = {
        "validation_seed": args.seed,
        "strategy_1_seed": strategies[0]["strategy_seed"],
        "strategy_2_seed": strategies[1]["strategy_seed"],
        "strategy_3_seed": strategies[2]["strategy_seed"],
        "exact_3_of_3": exact,
        "strategies": strategies,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {out} exact_3_of_3={exact}", flush=True)
    return 0 if exact else 2


if __name__ == "__main__":
    raise SystemExit(main())
