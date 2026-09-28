"""Stop versus hold on three explicit layers."""

from __future__ import annotations

from decimal import Decimal

from first78.money import fee_charged_cents, fee_raw

from repair.ledger import replay

FEE = Decimal("0.0175")


def layer_a_fixed_quantity(trades: list[dict], candidates: list[dict]) -> dict:
    meta = {c["game_id"]: c for c in candidates}
    total = 0
    rows = []
    for trade in trades:
        src = meta.get(trade["game_id"])
        if src is None or src.get("terminal_result") not in {"yes", "no"}:
            continue
        contracts = int(trade["contracts"])
        entry = int(trade["entry_price_cents"])
        entry_fee = fee_charged_cents(fee_raw(contracts, entry, FEE))
        payout = contracts * (100 if src["terminal_result"] == "yes" else 0)
        hold_net = payout - contracts * entry - entry_fee
        diff = int(trade["net_pnl_cents"]) - hold_net
        total += diff
        rows.append({"game_id": trade["game_id"], "stop_minus_hold_cents": diff, "layer": "A_FIXED_QUANTITY"})
    return {
        "layer": "A_FIXED_QUANTITY",
        "label": "unconstrained attribution of exit P&L on the stop book's quantities",
        "stop_minus_hold_cents": total,
        "rows": len(rows),
    }


def layer_b_fixed_unit(candidates: list[dict]) -> dict:
    unit = []
    for cand in candidates:
        row = dict(cand)
        row["entry_price_cents"] = int(cand.get("entry_price_cents") or 78)
        unit.append(row)
    # One contract is forced by a $78 balance and 100% allocation only inside this diagnostic.
    stop = replay(unit, balance_cents=78 * 100, allocation_bps=10_000, cap=10_000)
    hold = replay(_as_hold(unit), balance_cents=78 * 100, allocation_bps=10_000, cap=10_000)
    return {
        "layer": "B_FIXED_UNIT",
        "stop_admitted": len(stop["trades"]),
        "hold_admitted": len(hold["trades"]),
        "stop_net_cents": sum(int(t["net_pnl_cents"]) for t in stop["trades"]),
        "hold_net_cents": sum(int(t["net_pnl_cents"]) for t in hold["trades"]),
        "note": "same unit size; admission can still differ because cash and slots differ",
    }


def layer_c_completion(candidates: list[dict]) -> dict:
    stop = replay(candidates)
    hold = replay(_as_hold(candidates))
    return {
        "layer": "C_COMPLETION_SIZING",
        "stop_admitted": len(stop["trades"]),
        "hold_admitted": len(hold["trades"]),
        "stop_net_cents": sum(int(t["net_pnl_cents"]) for t in stop["trades"]),
        "hold_net_cents": sum(int(t["net_pnl_cents"]) for t in hold["trades"]),
        "difference_cents": sum(int(t["net_pnl_cents"]) for t in stop["trades"]) - sum(int(t["net_pnl_cents"]) for t in hold["trades"]),
        "note": "ordering of the decomposition is the stop book versus a separately financed hold book",
    }


def _as_hold(candidates: list[dict]) -> list[dict]:
    out = []
    for cand in candidates:
        result = cand.get("terminal_result")
        settlement = cand.get("settlement_ts")
        action = int(cand.get("action_ts") or cand["signal_ts"])
        if result not in {"yes", "no"} or settlement is None or int(settlement) < action:
            row = dict(cand)
            row["exit_reason"] = "UNRESOLVED"
            row["exit_ts"] = None
            out.append(row)
            continue
        row = dict(cand)
        row["exit_reason"] = "WIN_SETTLEMENT" if result == "yes" else "LOSS_SETTLEMENT"
        row["exit_ts"] = int(settlement)
        row["cash_ts"] = int(settlement)
        out.append(row)
    return out
