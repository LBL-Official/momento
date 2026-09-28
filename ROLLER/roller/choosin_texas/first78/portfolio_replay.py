"""One funded replay per stop. Admissions are not copied across variants."""

from __future__ import annotations

import sys

from roller.paths import find_root, momento_root


def _fee():
    root = momento_root(find_root())
    src = str(root / "research/first78_67_portfolio_v1/src")
    if src not in sys.path:
        sys.path.insert(0, src)
    from first78.money import contracts_for_principal, fee_charged_cents, fee_raw

    return contracts_for_principal, fee_charged_cents, fee_raw


def replay_variant(candidates: list[dict], stop_cents: int, *, balance_cents: int = 2_000_000, cap: int = 7) -> dict:
    """Size from equity after every tenth completion. Open quantities stay put."""
    contracts_for_principal, fee_charged_cents, fee_raw = _fee()
    events: list[tuple] = []
    for row in candidates:
        events.append((int(row["signal_ts"]), 2, str(row["game_id"]), str(row["contract_id"]), "ENTRY", row))
        if row.get("cell") != "UNRESOLVED" and row.get("exit_ts") is not None:
            events.append((int(row["exit_ts"]), 0, str(row["game_id"]), str(row["contract_id"]), "EXIT", row))
    events.sort(key=lambda item: (item[0], item[1], item[2], item[3]))
    cash = int(balance_cents)
    size_equity = cash
    open_slots: dict[str, dict] = {}
    completions = 0
    admitted: list[str] = []
    rejected: list[str] = []
    net = 0
    for _ts, _pri, _game, _contract, kind, row in events:
        game_id = str(row["game_id"])
        if kind == "EXIT":
            held = open_slots.pop(game_id, None)
            if held is None:
                continue
            quantity = int(held["contracts"])
            entry_fee = int(held["entry_fee_cents"])
            debit = quantity * 78 + entry_fee
            if row.get("stopped"):
                exit_fee = fee_charged_cents(fee_raw(quantity, int(stop_cents)))
                payout = quantity * int(stop_cents) - exit_fee
            elif row.get("terminal") == "yes":
                payout = quantity * 100
            elif row.get("terminal") == "no":
                payout = 0
            else:
                open_slots[game_id] = held
                continue
            cash += payout
            net += payout - debit
            completions += 1
            if completions % 10 == 0:
                size_equity = cash + sum(int(item["principal_cents"]) for item in open_slots.values())
            continue
        if game_id in open_slots or len(open_slots) >= cap:
            rejected.append(game_id)
            continue
        quantity = contracts_for_principal(size_equity, 78)
        if quantity < 1:
            rejected.append(game_id)
            continue
        entry_fee = fee_charged_cents(fee_raw(quantity, 78))
        principal = quantity * 78
        if cash < principal + entry_fee:
            rejected.append(game_id)
            continue
        cash -= principal + entry_fee
        open_slots[game_id] = {
            "contracts": quantity,
            "principal_cents": principal,
            "entry_fee_cents": entry_fee,
        }
        admitted.append(game_id)
    return {
        "stop_cents": int(stop_cents),
        "scenario_entry_cents": 78,
        "price_convention": "ASSUMED_THRESHOLD_PRICE",
        "fee_applicability": "FEE_APPLICABILITY_UNVERIFIED",
        "fee_coef": "0.0175",
        "admitted_game_ids": admitted,
        "admitted": len(admitted),
        "rejected": len(set(rejected)),
        "open_at_end": len(open_slots),
        "completions": completions,
        "ending_cash_cents": cash,
        "net_pnl_cents": net,
        "not_a_fill": True,
        "not_executable": True,
    }
