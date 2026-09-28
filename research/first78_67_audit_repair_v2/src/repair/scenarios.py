"""Scenario application on top of the repaired ledger."""

from __future__ import annotations

from decimal import Decimal

from repair.chronology import delayed_entry
from repair.ledger import replay
from repair.stopfail import apply_failures

FEE = Decimal("0.0175")
SPECS = {
    "REF": {"entry": 78, "stop": 67, "fee": FEE},
    "ENTRY_1": {"entry": 79, "stop": 67, "fee": FEE},
    "ENTRY_2": {"entry": 80, "stop": 67, "fee": FEE},
    "EXIT_1": {"entry": 78, "stop": 66, "fee": FEE},
    "EXIT_2": {"entry": 78, "stop": 65, "fee": FEE},
    "JOINT_1": {"entry": 79, "stop": 66, "fee": FEE},
    "JOINT_2": {"entry": 80, "stop": 65, "fee": FEE},
    "FEE_007": {"entry": 78, "stop": 67, "fee": Decimal("0.07")},
    "JOINT_2_FEE_007": {"entry": 80, "stop": 65, "fee": Decimal("0.07")},
    "CASH_DELAY_15": {"entry": 78, "stop": 67, "fee": FEE, "delay": 900},
    "CASH_DELAY_60": {"entry": 78, "stop": 67, "fee": FEE, "delay": 3600},
    "STOP_FAIL_1": {"entry": 78, "stop": 67, "fee": FEE, "fail": 0.01},
    "STOP_FAIL_5": {"entry": 78, "stop": 67, "fee": FEE, "fail": 0.05},
    "LATENCY_60": {"entry": None, "stop": 67, "fee": FEE, "latency": 60},
    "LATENCY_120": {"entry": None, "stop": 67, "fee": FEE, "latency": 120},
}


def prepare(candidates: list[dict], scenario_id: str, *, seed: int = 1) -> tuple[list[dict], list[dict]]:
    if scenario_id.startswith("ORACLE"):
        raise RuntimeError(scenario_id)
    spec = SPECS[scenario_id]
    skipped = []
    rows = []
    source = candidates
    if spec.get("fail"):
        source = apply_failures(candidates, probability=float(spec["fail"]), seed=seed)
    for cand in source:
        row = dict(cand)
        if spec.get("latency"):
            found = delayed_entry(cand.get("bars") or [], int(cand["signal_ts"]), int(spec["latency"]), 60)
            if found.get("status") != "NEXT_BAR_PRICE_PROXY":
                skipped.append({"game_id": cand["game_id"], "reason": found.get("status")})
                continue
            row["action_ts"] = found["action_ts"]
            row["entry_price_cents"] = found["entry_price_cents"]
            row["evidence"] = "NEXT_BAR_PRICE_PROXY"
            if found.get("stop_ts"):
                row["exit_reason"] = "STOP"
                row["exit_ts"] = found["stop_ts"]
                row["cash_ts"] = found["stop_ts"]
            elif row.get("exit_ts") is not None and int(row["exit_ts"]) <= int(row["action_ts"]):
                skipped.append({"game_id": cand["game_id"], "reason": "STOP_NOT_STRICTLY_LATER"})
                continue
        else:
            row["entry_price_cents"] = int(spec["entry"])
            row["evidence"] = "FIRST78_CLOSE_PROXY"
        row["stop_price_cents"] = int(spec["stop"])
        if row.get("cash_ts") is not None:
            row["cash_ts"] = int(row["cash_ts"]) + int(spec.get("delay") or 0)
        if scenario_id.startswith("ENTRY") or scenario_id.startswith("EXIT") or scenario_id.startswith("JOINT") or scenario_id.startswith("FEE"):
            row["price_stress_cents"] = int(spec["entry"]) - 78
        rows.append(row)
    return rows, skipped


def play(candidates: list[dict], scenario_id: str, *, seed: int = 1, balance_cents: int = 2_000_000):
    rows, skipped = prepare(candidates, scenario_id, seed=seed)
    book = replay(rows, balance_cents=balance_cents, fee_coef=SPECS[scenario_id]["fee"])
    book["skipped"] = skipped
    return book
