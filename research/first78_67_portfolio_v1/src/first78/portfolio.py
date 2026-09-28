"""Single merged portfolio ledger.

Headline mode is completion-count sizing. Strict ten-entry batches are a
separate policy. Same-timestamp baseline orders exits, then cash releases,
then entries.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from first78.money import contracts_for_principal, fee_charged_cents, fee_raw, net_r

EXIT_PRI = 0
CASH_PRI = 1
ENTRY_PRI = 2


@dataclass
class OpenPos:
    trade_id: str
    game_id: str
    contract_id: str
    sport: str
    contracts: int
    principal_cents: int
    entry_fee_cents: int
    entry_ts: int
    exit_ts: int
    cash_ts: int
    exit_price_cents: int
    settlement_payout_cents: int | None
    exit_reason: str
    entry_sequence: int
    cohort_id: int
    epoch_id: int
    sizing_balance_cents: int
    planned_exit_fee_cents: int
    r0_cents: int
    batch_id: int | None = None


@dataclass
class Ledger:
    events: list[dict[str, Any]] = field(default_factory=list)
    trades: list[dict[str, Any]] = field(default_factory=list)
    rejections: list[dict[str, Any]] = field(default_factory=list)
    epochs: list[dict[str, Any]] = field(default_factory=list)
    max_open: int = 0
    ending_cash_cents: int = 0
    ending_equity_cents: int = 0
    ending_receivable_cents: int = 0


def _priority(kind: str, reverse: bool) -> int:
    if not reverse:
        return {"exit": EXIT_PRI, "cash": CASH_PRI, "entry": ENTRY_PRI}[kind]
    return {"entry": 0, "exit": 1, "cash": 2}[kind]


def replay(
    candidates: list[dict[str, Any]],
    *,
    balance_cents: int = 2_000_000,
    cap: int = 7,
    mode: str = "completion_epochs",
    reverse_priority: bool = False,
    entry_price_cents: int = 78,
    stop_price_cents: int = 67,
    fee_coef: Decimal = Decimal("0.0175"),
    allocation_bps: int = 600,
    fee_inside_allocation: bool = False,
) -> Ledger:
    if mode not in {"completion_epochs", "strict_batches"}:
        raise ValueError(mode)
    if entry_price_cents <= stop_price_cents:
        raise ValueError("stop must be below entry for planned risk")

    ledger = Ledger()
    cash = int(balance_cents)
    receivable = 0
    open_positions: dict[str, OpenPos] = {}
    consumed: set[str] = set()
    b = int(balance_cents)
    epoch_id = 0
    completions = 0
    entry_sequence = 0
    strict_admitted = 0
    strict_open = 0
    strict_batch_index = 0
    heap: list[tuple] = []
    seq = 0

    def push(ts: int, kind: str, payload: dict[str, Any]) -> None:
        nonlocal seq
        seq += 1
        heapq.heappush(heap, (int(ts), _priority(kind, reverse_priority), seq, kind, payload))

    for cand in candidates:
        push(int(cand["signal_ts"]), "entry", {"candidate": cand})

    def equity() -> int:
        principal_open = sum(p.principal_cents for p in open_positions.values())
        return cash + receivable + principal_open

    def log_event(ts: int, kind: str, **fields: Any) -> None:
        row = {
            "ts": int(ts),
            "kind": kind,
            "cash_cents": cash,
            "receivable_cents": receivable,
            "open_count": len(open_positions),
            "equity_cents": equity(),
            "sizing_balance_cents": b,
            "sizing_epoch_id": epoch_id,
            "completion_count": completions,
        }
        row.update(fields)
        ledger.events.append(row)
        ledger.max_open = max(ledger.max_open, len(open_positions))

    while heap:
        ts, _pri, _seq, kind, payload = heapq.heappop(heap)
        if kind == "entry":
            cand = payload["candidate"]
            game_id = str(cand["game_id"])
            if game_id in consumed:
                ledger.rejections.append({**cand, "reason": "REENTRY_CONSUMED", "ts": ts})
                log_event(ts, "reject", game_id=game_id, reason="REENTRY_CONSUMED")
                continue
            consumed.add(game_id)
            if mode == "strict_batches" and strict_admitted >= 10 and strict_open > 0:
                ledger.rejections.append({**cand, "reason": "BATCH_WAIT", "ts": ts})
                log_event(ts, "reject", game_id=game_id, reason="BATCH_WAIT")
                continue
            if mode == "strict_batches" and strict_admitted >= 10 and strict_open == 0:
                strict_admitted = 0
                strict_batch_index += 1
            if len(open_positions) >= cap:
                ledger.rejections.append({**cand, "reason": "CAP", "ts": ts, "open_count": len(open_positions)})
                log_event(ts, "reject", game_id=game_id, reason="CAP")
                continue
            price = int(cand.get("entry_price_cents") or entry_price_cents)
            contracts = contracts_for_principal(b, price, allocation_bps)
            if contracts <= 0:
                ledger.rejections.append({**cand, "reason": "ZERO_CONTRACTS", "ts": ts})
                log_event(ts, "reject", game_id=game_id, reason="ZERO_CONTRACTS")
                continue
            if fee_inside_allocation:
                target = (b * allocation_bps) // 10_000
                while contracts > 0:
                    principal_try = contracts * price
                    fee_try = fee_charged_cents(fee_raw(contracts, price, fee_coef))
                    if principal_try + fee_try <= target:
                        break
                    contracts -= 1
                if contracts <= 0:
                    ledger.rejections.append({**cand, "reason": "ALL_IN_CAP", "ts": ts})
                    log_event(ts, "reject", game_id=game_id, reason="ALL_IN_CAP")
                    continue
            principal = contracts * price
            entry_fee = fee_charged_cents(fee_raw(contracts, price, fee_coef))
            debit = principal + entry_fee
            if cash < debit:
                ledger.rejections.append({**cand, "reason": "INSUFFICIENT_CASH", "ts": ts, "debit_cents": debit, "cash_cents": cash})
                log_event(ts, "reject", game_id=game_id, reason="INSUFFICIENT_CASH")
                continue
            exit_reason = str(cand["exit_reason"])
            planned_stop = int(cand.get("stop_price_cents") or stop_price_cents)
            if price <= planned_stop or price >= 100:
                ledger.rejections.append({**cand, "reason": "PRICE_NOT_ABOVE_STOP", "ts": ts})
                log_event(ts, "reject", game_id=game_id, reason="PRICE_NOT_ABOVE_STOP")
                continue
            if exit_reason == "STOP":
                exit_px = planned_stop
                exit_fee = fee_charged_cents(fee_raw(contracts, exit_px, fee_coef))
                payout = contracts * exit_px - exit_fee
                exit_ts = int(cand["exit_ts"])
            elif exit_reason in {"WIN_SETTLEMENT", "LOSS_SETTLEMENT"}:
                exit_px = 100 if exit_reason == "WIN_SETTLEMENT" else 0
                exit_fee = 0
                payout = contracts * exit_px
                exit_ts = int(cand["exit_ts"])
            else:
                ledger.rejections.append({**cand, "reason": "UNRESOLVED", "ts": ts})
                log_event(ts, "reject", game_id=game_id, reason="UNRESOLVED")
                continue
            cash_ts = int(cand["cash_ts"])
            if cash_ts < exit_ts or exit_ts < ts:
                raise RuntimeError("cash or exit precedes entry")
            cash -= debit
            entry_sequence += 1
            cohort = (entry_sequence - 1) // 10
            planned_exit_fee = fee_charged_cents(fee_raw(contracts, planned_stop, fee_coef))
            r0 = contracts * (price - planned_stop) + entry_fee + planned_exit_fee
            trade_id = f"T{entry_sequence:04d}"
            pos = OpenPos(
                trade_id=trade_id,
                game_id=game_id,
                contract_id=str(cand["contract_id"]),
                sport=str(cand["sport"]),
                contracts=contracts,
                principal_cents=principal,
                entry_fee_cents=entry_fee,
                entry_ts=ts,
                exit_ts=exit_ts,
                cash_ts=cash_ts,
                exit_price_cents=exit_px,
                settlement_payout_cents=payout,
                exit_reason=exit_reason,
                entry_sequence=entry_sequence,
                cohort_id=cohort,
                epoch_id=epoch_id,
                sizing_balance_cents=b,
                planned_exit_fee_cents=planned_exit_fee,
                r0_cents=r0,
                batch_id=strict_batch_index if mode == "strict_batches" else None,
            )
            open_positions[trade_id] = pos
            if mode == "strict_batches":
                strict_admitted += 1
                strict_open += 1
            log_event(
                ts,
                "entry",
                trade_id=trade_id,
                game_id=game_id,
                contract_id=pos.contract_id,
                sport=pos.sport,
                contracts=contracts,
                principal_cents=principal,
                entry_fee_cents=entry_fee,
                entry_sequence=entry_sequence,
                cohort_id=cohort,
            )
            push(exit_ts, "exit", {"trade_id": trade_id})
            continue

        if kind == "exit":
            trade_id = payload["trade_id"]
            pos = open_positions.get(trade_id)
            if pos is None:
                continue
            del open_positions[trade_id]
            if mode == "strict_batches":
                strict_open -= 1
            proceeds = int(pos.settlement_payout_cents or 0)
            net = proceeds - pos.principal_cents - pos.entry_fee_cents
            if pos.exit_reason == "STOP":
                # proceeds already net of the stop fee
                pass
            receivable += proceeds
            completions += 1
            completion_batch = (completions - 1) // 10
            resized = False
            if mode == "completion_epochs" and completions % 10 == 0:
                b = equity()
                epoch_id += 1
                resized = True
                ledger.epochs.append({"sizing_epoch_id": epoch_id, "ts": ts, "balance_cents": b, "completion_count": completions})
            if mode == "strict_batches" and strict_admitted >= 10 and strict_open == 0:
                b = equity()
                epoch_id += 1
                resized = True
                ledger.epochs.append({"sizing_epoch_id": epoch_id, "ts": ts, "balance_cents": b, "completion_count": completions, "strict_batch": pos.batch_id})
            trade = {
                "trade_id": pos.trade_id,
                "game_id": pos.game_id,
                "contract_id": pos.contract_id,
                "sport": pos.sport,
                "contracts": pos.contracts,
                "principal_cents": pos.principal_cents,
                "entry_fee_cents": pos.entry_fee_cents,
                "exit_fee_cents": pos.principal_cents and (pos.contracts * pos.exit_price_cents - proceeds if pos.exit_reason == "STOP" else 0),
                "entry_ts": pos.entry_ts,
                "exit_ts": pos.exit_ts,
                "cash_ts": pos.cash_ts,
                "entry_price_cents": entry_price_cents,
                "exit_price_cents": pos.exit_price_cents,
                "exit_reason": pos.exit_reason,
                "net_pnl_cents": net,
                "gross_pnl_cents": (proceeds + (pos.contracts * pos.exit_price_cents - proceeds if pos.exit_reason == "STOP" else 0)) - pos.principal_cents if pos.exit_reason == "STOP" else proceeds - pos.principal_cents,
                "entry_sequence": pos.entry_sequence,
                "completion_sequence": completions,
                "cohort_id": pos.cohort_id,
                "completion_batch_id": completion_batch,
                "epoch_id": pos.epoch_id,
                "sizing_balance_cents": pos.sizing_balance_cents,
                "r0_cents": pos.r0_cents,
                "net_r": net_r(net, pos.r0_cents),
                "resized_after": resized,
                "strict_batch_id": pos.batch_id,
            }
            if pos.exit_reason == "STOP":
                sale_gross = pos.contracts * pos.exit_price_cents
                trade["exit_fee_cents"] = sale_gross - proceeds
                trade["gross_pnl_cents"] = sale_gross - pos.principal_cents
                trade["net_pnl_cents"] = sale_gross - pos.principal_cents - pos.entry_fee_cents - trade["exit_fee_cents"]
            else:
                trade["exit_fee_cents"] = 0
                trade["gross_pnl_cents"] = proceeds - pos.principal_cents
                trade["net_pnl_cents"] = trade["gross_pnl_cents"] - pos.entry_fee_cents
            trade["net_r"] = net_r(trade["net_pnl_cents"], pos.r0_cents)
            ledger.trades.append(trade)
            log_event(ts, "exit", trade_id=trade_id, game_id=pos.game_id, net_pnl_cents=trade["net_pnl_cents"], completion_sequence=completions)
            push(pos.cash_ts, "cash", {"trade_id": trade_id, "proceeds": proceeds})
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

    if cash < 0 or receivable < 0:
        raise RuntimeError("negative cash or receivable")
    ledger.ending_cash_cents = cash
    ledger.ending_receivable_cents = receivable
    ledger.ending_equity_cents = equity()
    return ledger
