"""Versioned ledger. Imports fee arithmetic. Does not patch portfolio.py."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from first78.money import contracts_for_principal, fee_charged_cents, fee_raw, net_r

EXIT_PRI = 0
CASH_PRI = 1
ENTRY_PRI = 2


def replay(
    candidates: list[dict[str, Any]],
    *,
    balance_cents: int = 2_000_000,
    cap: int = 7,
    entry_price_cents: int = 78,
    stop_price_cents: int = 67,
    fee_coef: Decimal = Decimal("0.0175"),
    allocation_bps: int = 600,
    horizon_ts: int | None = None,
) -> dict[str, Any]:
    cash = int(balance_cents)
    receivable = 0
    open_positions: dict[str, dict[str, Any]] = {}
    consumed: set[str] = set()
    sizing = int(balance_cents)
    epoch_id = 0
    completions = 0
    entry_sequence = 0
    events: list[dict[str, Any]] = []
    trades: list[dict[str, Any]] = []
    rejections: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    epochs: list[dict[str, Any]] = []
    max_open = 0
    queue: list[tuple] = []

    def enqueue(ts: int, priority: int, game_id: str, contract_id: str, stable_id: str, kind: str, payload: dict) -> None:
        queue.append((int(ts), priority, str(game_id), str(contract_id), str(stable_id), kind, payload))

    for index, cand in enumerate(candidates):
        if cand.get("partial_fill"):
            rejections.append({**cand, "reason": "PARTIAL_FILL_UNSUPPORTED"})
            continue
        enqueue(
            int(cand["action_ts"] if cand.get("action_ts") is not None else cand["signal_ts"]),
            ENTRY_PRI,
            cand["game_id"],
            cand["contract_id"],
            cand.get("stable_event_id") or f"entry-{index}",
            "entry",
            {"candidate": cand},
        )

    def cost_principal() -> int:
        return sum(int(pos["principal_cents"]) for pos in open_positions.values())

    def realized_equity() -> int:
        return cash + receivable

    def valued_at_cost() -> int:
        return cash + receivable + cost_principal()

    def log_event(ts: int, kind: str, **fields: Any) -> None:
        nonlocal max_open
        max_open = max(max_open, len(open_positions))
        events.append(
            {
                "ts": int(ts),
                "kind": kind,
                "cash_cents": cash,
                "receivable_cents": receivable,
                "open_count": len(open_positions),
                "realized_equity_cents": realized_equity(),
                "valued_equity_cents": valued_at_cost(),
                "unknown_terminal_cents": sum(
                    int(pos["principal_cents"]) for pos in open_positions.values() if pos["exit_reason"] == "UNRESOLVED"
                ),
                "sizing_balance_cents": sizing,
                "sizing_epoch_id": epoch_id,
                "completion_count": completions,
                **fields,
            }
        )
        if cash < 0 or receivable < 0:
            raise RuntimeError("negative cash or receivable")

    while queue:
        queue.sort()
        ts, _pri, _game, _contract, _stable, kind, payload = queue.pop(0)
        if kind == "entry":
            cand = payload["candidate"]
            game_id = str(cand["game_id"])
            if game_id in consumed:
                rejections.append({**cand, "reason": "REENTRY_CONSUMED", "ts": ts})
                log_event(ts, "reject", game_id=game_id, reason="REENTRY_CONSUMED")
                continue
            consumed.add(game_id)
            if len(open_positions) >= cap:
                rejections.append({**cand, "reason": "CAP", "ts": ts})
                log_event(ts, "reject", game_id=game_id, reason="CAP")
                continue
            price = int(cand.get("entry_price_cents") or entry_price_cents)
            planned_stop = int(cand.get("stop_price_cents") or stop_price_cents)
            contracts = contracts_for_principal(sizing, price, allocation_bps)
            if contracts <= 0 or price <= planned_stop or price >= 100:
                rejections.append({**cand, "reason": "ZERO_CONTRACTS" if contracts <= 0 else "PRICE_NOT_ABOVE_STOP", "ts": ts})
                log_event(ts, "reject", game_id=game_id, reason="PRICE_OR_SIZE")
                continue
            principal = contracts * price
            entry_fee = fee_charged_cents(fee_raw(contracts, price, fee_coef))
            debit = principal + entry_fee
            if cash < debit:
                rejections.append({**cand, "reason": "INSUFFICIENT_CASH", "ts": ts, "debit_cents": debit})
                log_event(ts, "reject", game_id=game_id, reason="INSUFFICIENT_CASH")
                continue
            exit_reason = str(cand.get("exit_reason") or "UNRESOLVED")
            exit_ts = cand.get("exit_ts")
            if exit_reason == "STOP":
                if exit_ts is None or int(exit_ts) <= int(ts):
                    rejections.append({**cand, "reason": "STOP_NOT_STRICTLY_LATER", "ts": ts})
                    consumed.remove(game_id)
                    log_event(ts, "reject", game_id=game_id, reason="STOP_NOT_STRICTLY_LATER")
                    continue
                exit_px = planned_stop
                exit_fee = fee_charged_cents(fee_raw(contracts, exit_px, fee_coef))
                payout = contracts * exit_px - exit_fee
                exit_ts = int(exit_ts)
            elif exit_reason in {"WIN_SETTLEMENT", "LOSS_SETTLEMENT"}:
                if exit_ts is None or int(exit_ts) < int(ts):
                    exit_reason = "UNRESOLVED"
                    exit_px = None
                    payout = None
                    exit_ts = None
                else:
                    exit_px = 100 if exit_reason == "WIN_SETTLEMENT" else 0
                    payout = contracts * exit_px
                    exit_ts = int(exit_ts)
            else:
                exit_reason = "UNRESOLVED"
                exit_px = None
                payout = None
                exit_ts = None
            cash_ts = None if exit_ts is None else int(cand.get("cash_ts") or exit_ts)
            if cash_ts is not None and cash_ts < exit_ts:
                raise RuntimeError("cash precedes exit")
            cash -= debit
            entry_sequence += 1
            planned_exit_fee = fee_charged_cents(fee_raw(contracts, planned_stop, fee_coef))
            r0 = contracts * (price - planned_stop) + entry_fee + planned_exit_fee
            trade_id = f"T{entry_sequence:04d}"
            pos = {
                "trade_id": trade_id,
                "game_id": game_id,
                "contract_id": str(cand["contract_id"]),
                "sport": str(cand.get("sport") or "ALL"),
                "contracts": contracts,
                "principal_cents": principal,
                "entry_fee_cents": entry_fee,
                "entry_price_cents": price,
                "entry_ts": int(ts),
                "signal_ts": int(cand.get("signal_ts") or ts),
                "exit_ts": exit_ts,
                "cash_ts": cash_ts,
                "exit_price_cents": exit_px,
                "payout_cents": payout,
                "exit_reason": exit_reason,
                "entry_sequence": entry_sequence,
                "epoch_id": epoch_id,
                "sizing_balance_cents": sizing,
                "r0_cents": r0,
                "local_day": cand.get("local_day"),
            }
            open_positions[trade_id] = pos
            log_event(ts, "entry", trade_id=trade_id, game_id=game_id, contract_id=pos["contract_id"], contracts=contracts, principal_cents=principal, entry_price_cents=price)
            if exit_ts is not None:
                enqueue(exit_ts, EXIT_PRI, game_id, pos["contract_id"], f"exit-{trade_id}", "exit", {"trade_id": trade_id})
            else:
                unresolved.append({"trade_id": trade_id, "game_id": game_id, "status": "UNRESOLVED_HOLDING"})
            continue
        if kind == "exit":
            pos = open_positions.get(payload["trade_id"])
            if pos is None:
                continue
            del open_positions[payload["trade_id"]]
            proceeds = int(pos["payout_cents"])
            receivable += proceeds
            completions += 1
            resized = False
            if completions % 10 == 0:
                sizing = valued_at_cost()
                epoch_id += 1
                resized = True
                epochs.append({"sizing_epoch_id": epoch_id, "ts": ts, "balance_cents": sizing, "completion_count": completions, "open_count": len(open_positions)})
            if pos["exit_reason"] == "STOP":
                sale_gross = pos["contracts"] * int(pos["exit_price_cents"])
                exit_fee = sale_gross - proceeds
                gross = sale_gross - pos["principal_cents"]
                net = gross - pos["entry_fee_cents"] - exit_fee
            else:
                exit_fee = 0
                gross = proceeds - pos["principal_cents"]
                net = gross - pos["entry_fee_cents"]
            trade = {
                **{k: pos[k] for k in ("trade_id", "game_id", "contract_id", "sport", "contracts", "principal_cents", "entry_fee_cents", "entry_price_cents", "entry_ts", "signal_ts", "exit_ts", "cash_ts", "exit_price_cents", "exit_reason", "entry_sequence", "epoch_id", "sizing_balance_cents", "r0_cents", "local_day")},
                "exit_fee_cents": exit_fee,
                "gross_pnl_cents": gross,
                "net_pnl_cents": net,
                "completion_sequence": completions,
                "resized_after": resized,
                "net_r": net_r(net, pos["r0_cents"]),
                "sport_scope": "ALL",
            }
            trades.append(trade)
            log_event(ts, "exit", trade_id=pos["trade_id"], game_id=pos["game_id"], net_pnl_cents=net, completion_sequence=completions)
            enqueue(int(pos["cash_ts"]), CASH_PRI, pos["game_id"], pos["contract_id"], f"cash-{pos['trade_id']}", "cash", {"trade_id": pos["trade_id"], "proceeds": proceeds})
            continue
        if kind == "cash":
            proceeds = int(payload["proceeds"])
            if receivable < proceeds:
                raise RuntimeError("receivable underflow")
            receivable -= proceeds
            cash += proceeds
            log_event(ts, "cash", trade_id=payload["trade_id"], proceeds_cents=proceeds)
            continue
        raise RuntimeError(kind)

    horizon_equity = None
    if horizon_ts is not None:
        horizon_equity = _equity_asof(events, int(horizon_ts))
    return {
        "events": events,
        "trades": trades,
        "rejections": rejections,
        "unresolved": unresolved,
        "epochs": epochs,
        "max_open": max_open,
        "ending_cash_cents": cash,
        "ending_receivable_cents": receivable,
        "realized_equity_cents": realized_equity(),
        "valued_equity_cents": valued_at_cost(),
        "ending_equity_cents": valued_at_cost(),
        "horizon_marked_equity_cents": horizon_equity,
        "open_positions": list(open_positions.values()),
    }


def _equity_asof(events: list[dict], ts: int) -> int | None:
    seen = [row for row in events if int(row["ts"]) <= ts]
    if not seen:
        return None
    return int(seen[-1]["valued_equity_cents"])
