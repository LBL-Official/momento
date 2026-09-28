"""Estimated fee wrapper. Not a production KalshiFeeModel."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

from roller.superasi.library import repo_root
from roller.superasi.models import SuperasiError

_FEE_PATH = repo_root() / "apps" / "nba-data" / "scripts" / "capture_program_v1" / "fee_models.py"

# FIRST80_REALISTIC_EXIT_FEE_AUDIT_V1 — entry/exit roles only (no hedge in SuperASI v1).
SCENARIOS = {
    "CURRENT": {"entry_maker": None, "exit_maker": False, "entry_fee": False},
    "MODERATE": {"entry_maker": True, "exit_maker": False, "entry_fee": True},
    "CONSERVATIVE": {"entry_maker": False, "exit_maker": False, "entry_fee": True},
}


def load_fee_models():
    if not _FEE_PATH.is_file():
        raise SuperasiError("FEE_DATA_REQUIRED", f"missing {_FEE_PATH}")
    spec = importlib.util.spec_from_file_location("capture_program_v1_fee_models", _FEE_PATH)
    if spec is None or spec.loader is None:
        raise SuperasiError("FEE_DATA_REQUIRED", "cannot load fee_models.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def estimate(
    *,
    scenario: str,
    contracts: int,
    entry_cents: int,
    exit_cents: int | None,
    price_basis: str,
) -> dict[str, Any]:
    if price_basis == "LAST_TRADE_PRINT":
        raise SuperasiError(
            "LAST_TRADE_PRINT_DATA_REQUIRED",
            "Last-trade prints do not establish an executable bid/ask exit.",
        )
    if scenario not in SCENARIOS:
        raise SuperasiError("PACKAGE_SCHEMA_INVALID", f"unknown fee scenario {scenario}")
    fm = load_fee_models()
    model = fm.PublishedScheduleEstimate()
    cfg = SCENARIOS[scenario]
    parts = []
    if cfg["entry_fee"]:
        parts.append(model.calculate_entry_fee(contracts, entry_cents, bool(cfg["entry_maker"])))
    if exit_cents is not None:
        parts.append(model.calculate_exit_fee(contracts, exit_cents, bool(cfg["exit_maker"])))
    settle = model.calculate_settlement_fee(contracts)
    parts.append(settle)
    total_e6 = sum(int(q.amount_e6 or 0) for q in parts)
    return {
        "scenario": scenario,
        "model_id": model.model_id,
        "status": "ESTIMATED",
        "label": "ESTIMATED FEE SCHEDULE",
        "contracts": contracts,
        "entry_cents": entry_cents,
        "exit_cents": exit_cents,
        "total_e6": total_e6,
        "total_cents": fm.e6_to_cents(total_e6),
        "components": [
            {
                "amount_e6": q.amount_e6,
                "amount_cents": q.amount_cents,
                "status": q.status,
                "note": q.note,
            }
            for q in parts
        ],
        "note": "NOT production KalshiFeeModel. FEE MODEL = ESTIMATED.",
    }


def quote_one_contract(price_cents: int, *, maker: bool) -> dict[str, Any]:
    fm = load_fee_models()
    model = fm.PublishedScheduleEstimate()
    q = model.calculate_entry_fee(1, price_cents, maker)
    return {
        "amount_e6": q.amount_e6,
        "amount_cents": q.amount_cents,
        "status": q.status,
        "model_id": q.model_id,
        "note": q.note,
    }


def scenario_book(price_basis: str, trades: list[dict[str, Any]], mix_rows: list[dict[str, Any]]) -> dict[str, Any]:
    if price_basis == "LAST_TRADE_PRINT":
        return {
            "status": "DATA_REQUIRED",
            "code": "LAST_TRADE_PRINT_DATA_REQUIRED",
            "reason": "Last-trade prints do not establish an executable bid/ask exit.",
        }
    maker = taker = unavail = 0
    for rec in mix_rows:
        liq = rec.get("liquidity")
        if liq == "MAKER":
            maker += 1
        elif liq == "TAKER":
            taker += 1
        else:
            unavail += 1
    return {
        "status": "ESTIMATED",
        "maker_count": maker,
        "taker_count": taker,
        "unavailable_count": unavail,
        "n_trades": len(trades),
        "quotes": {
            "one_contract_80_maker": quote_one_contract(80, maker=True),
            "one_contract_80_taker": quote_one_contract(80, maker=False),
            "one_contract_40_maker": quote_one_contract(40, maker=True),
            "one_contract_40_taker": quote_one_contract(40, maker=False),
        },
    }
