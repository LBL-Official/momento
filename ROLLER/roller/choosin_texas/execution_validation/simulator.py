"""Execution-aware accounting for explicit observations.

This is not applied to the historical book. Historical depth and queue
position are absent, so a portfolio P&L from this machine would invent fills.
"""

from __future__ import annotations

from typing import Any

from roller.choosin_texas.models import ChoosinTexasError


def attribute_versus_benchmark(
    *,
    benchmark_pnl_cents: int,
    benchmark_exit_cents: int,
    modeled_exit_cents: int | None,
) -> dict[str, Any]:
    """The through-close gap already sits inside the benchmark P&L."""
    if modeled_exit_cents is None:
        return {
            "benchmark_pnl_cents": int(benchmark_pnl_cents),
            "benchmark_exit_cents": int(benchmark_exit_cents),
            "execution_adjustment_cents": None,
            "gap_recharged": False,
            "comparison": "NOT_COMPARABLE",
        }
    return {
        "benchmark_pnl_cents": int(benchmark_pnl_cents),
        "benchmark_exit_cents": int(benchmark_exit_cents),
        "modeled_exit_cents": int(modeled_exit_cents),
        "exit_difference_cents": int(modeled_exit_cents) - int(benchmark_exit_cents),
        "gap_recharged": False,
        "comparison": "EXIT_DIFFERENCE_ONLY",
    }


def evaluate_observation(
    *,
    signal_ts: int,
    arrival_ts: int,
    post_only: bool,
    crosses: bool,
    queue_position: int | None,
    depth_contracts: int | None,
    sequence_gap: bool | None,
    trade_at_price: bool,
) -> dict[str, Any]:
    if int(arrival_ts) < int(signal_ts):
        raise ChoosinTexasError("LOCK_MISMATCH", "order arrival is before the signal is observable")
    if depth_contracts is None or sequence_gap is None or sequence_gap is True:
        return {
            "status": "UNCERTAIN",
            "modeled_filled_contracts": None,
            "fill_label": None,
            "reason": "Missing depth or a sequence gap leaves the fill unresolved.",
        }
    if crosses and post_only:
        return {
            "status": "POST_ONLY_REJECTED",
            "role": "POST_ONLY_REJECT",
            "modeled_filled_contracts": 0,
            "fill_label": None,
            "reason": "A marketable post-only order is not a resting maker fill.",
        }
    if crosses and not post_only:
        return {
            "status": "WOULD_TAKE",
            "role": "TAKER",
            "modeled_filled_contracts": None,
            "fill_label": None,
            "reason": "Taker fallback is not authorized, so a crossing order is not filled here.",
        }
    if trade_at_price and queue_position is None:
        return {
            "status": "UNCERTAIN",
            "modeled_filled_contracts": None,
            "fill_label": None,
            "reason": "A trade at our price without a queue position is not a fill.",
        }
    if queue_position is None:
        return {
            "status": "UNCERTAIN",
            "modeled_filled_contracts": None,
            "fill_label": None,
            "reason": "A quote touch does not establish a queue fill.",
        }
    return {
        "status": "RESTING_QUEUE_KNOWN",
        "role": "RESTING_UNFILLED",
        "queue_position": int(queue_position),
        "modeled_filled_contracts": 0,
        "fill_label": "SIMULATED_EXECUTION",
        "reason": "Known queue with no authorizing print model remains unfilled.",
    }


class ExecutionBook:
    """Cash, reservations, and slots. A slot ends only when nothing is open."""

    def __init__(self, cash_cents: int, *, max_open_positions: int = 3) -> None:
        if max_open_positions <= 0:
            raise ChoosinTexasError("LOCK_MISMATCH", "position cap must be positive")
        self.cash_cents = int(cash_cents)
        self.max_open_positions = int(max_open_positions)
        self.states: dict[str, dict[str, Any]] = {}

    def slots_open(self) -> int:
        return sum(1 for row in self.states.values() if row["slot_open"])

    def reserve_entry(
        self,
        *,
        event_id: str,
        signal_ts: int,
        arrival_ts: int,
        contracts: int,
        limit_cents: int,
    ) -> str:
        if int(arrival_ts) < int(signal_ts):
            raise ChoosinTexasError("LOCK_MISMATCH", "order arrival is before the signal is observable")
        if contracts <= 0 or limit_cents <= 0:
            raise ChoosinTexasError("LOCK_MISMATCH", "entry size must be positive")
        if event_id in self.states and self.states[event_id]["slot_open"]:
            return "SAME_EVENT"
        if self.slots_open() >= self.max_open_positions:
            return "POSITION_CAP"
        premium = int(contracts) * int(limit_cents)
        if premium > self.cash_cents:
            return "SKIP_CASH"
        self.cash_cents -= premium
        self.states[event_id] = {
            "slot_open": True,
            "slot_start": int(arrival_ts),
            "reserved_contracts": int(contracts),
            "filled_contracts": 0,
            "exit_filled_contracts": 0,
            "exit_open_contracts": 0,
            "reserved_premium_cents": premium,
            "limit_cents": int(limit_cents),
            "proceeds_cents": 0,
            "fees_cents": 0,
        }
        return "RESERVED"

    def apply_entry_fill(self, event_id: str, contracts: int, ts: int) -> None:
        state = self._open(event_id)
        if int(ts) < int(state["slot_start"]):
            raise ChoosinTexasError("LOCK_MISMATCH", "fill is before the order arrival")
        qty = int(contracts)
        if qty <= 0 or qty > state["reserved_contracts"]:
            raise ChoosinTexasError("LOCK_MISMATCH", "entry fill exceeds the reserved remainder")
        state["reserved_contracts"] -= qty
        state["filled_contracts"] += qty
        state["reserved_premium_cents"] -= qty * state["limit_cents"]

    def stop_during_entry(self, event_id: str, ts: int) -> None:
        """Cancel the unfilled entry remainder, then open an exit for the filled quantity."""
        state = self._open(event_id)
        if int(ts) < int(state["slot_start"]):
            raise ChoosinTexasError("LOCK_MISMATCH", "stop is before the entry order")
        self._release_unfilled_entry(state)
        exposure = state["filled_contracts"] - state["exit_filled_contracts"]
        if exposure == 0:
            self._close_slot(state, int(ts))
            return
        state["exit_open_contracts"] = exposure

    def apply_exit_fill(
        self,
        event_id: str,
        contracts: int,
        price_cents: int,
        fee_cents: int,
        ts: int,
    ) -> None:
        state = self._open(event_id)
        if int(ts) < int(state["slot_start"]):
            raise ChoosinTexasError("LOCK_MISMATCH", "exit is before the entry order")
        qty = int(contracts)
        remaining = state["filled_contracts"] - state["exit_filled_contracts"]
        if qty <= 0 or qty > remaining or qty > state["exit_open_contracts"]:
            raise ChoosinTexasError("LOCK_MISMATCH", "exit fill exceeds exposed quantity")
        state["exit_filled_contracts"] += qty
        state["exit_open_contracts"] -= qty
        proceeds = qty * int(price_cents)
        state["proceeds_cents"] += proceeds
        state["fees_cents"] += int(fee_cents)
        self.cash_cents += proceeds - int(fee_cents)
        self._maybe_close(state, int(ts))

    def assert_reconciled(self) -> None:
        for event_id, state in self.states.items():
            exposure = state["filled_contracts"] - state["exit_filled_contracts"]
            if exposure < 0 or state["reserved_contracts"] < 0 or state["reserved_premium_cents"] < 0:
                raise ChoosinTexasError("LOCK_MISMATCH", f"{event_id} accounting went negative")
            expected_reserve = state["reserved_contracts"] * state["limit_cents"]
            if state["reserved_premium_cents"] != expected_reserve:
                raise ChoosinTexasError("LOCK_MISMATCH", f"{event_id} reserved premium drifted")
            if state["slot_open"] and exposure == 0 and state["reserved_contracts"] == 0 and state["exit_open_contracts"] == 0:
                raise ChoosinTexasError("LOCK_MISMATCH", f"{event_id} slot stayed open after resolution")

    def reconcile(self, starting_cash_cents: int) -> None:
        reserved = 0
        open_cost = 0
        exited_cost = 0
        proceeds = 0
        fees = 0
        for state in self.states.values():
            reserved += int(state["reserved_premium_cents"])
            exposure = int(state["filled_contracts"]) - int(state["exit_filled_contracts"])
            open_cost += exposure * int(state["limit_cents"])
            exited_cost += int(state["exit_filled_contracts"]) * int(state["limit_cents"])
            proceeds += int(state["proceeds_cents"])
            fees += int(state["fees_cents"])
        expected = int(starting_cash_cents) - reserved - open_cost - exited_cost + proceeds - fees
        if self.cash_cents != expected:
            raise ChoosinTexasError("LOCK_MISMATCH", f"cash {self.cash_cents} != {expected}")

    def reconstruct_max_concurrent(self, *, horizon_ts: int | None = None) -> int:
        points: list[tuple[int, int, str]] = []
        for event_id, state in self.states.items():
            start = int(state["slot_start"])
            if "slot_end" in state:
                end = int(state["slot_end"])
            elif horizon_ts is None:
                raise ChoosinTexasError("LOCK_MISMATCH", f"{event_id} is still open")
            else:
                end = int(horizon_ts)
            if end <= start:
                raise ChoosinTexasError("LOCK_MISMATCH", f"{event_id} interval is not positive")
            points.append((start, 1, event_id))
            points.append((end, 0, event_id))
        points.sort(key=lambda item: (item[0], item[1], item[2]))
        open_ids: set[str] = set()
        maximum = 0
        for _ts, kind, event_id in points:
            if kind == 0:
                open_ids.discard(event_id)
            else:
                if event_id in open_ids:
                    raise ChoosinTexasError("LOCK_MISMATCH", f"{event_id} reserved twice")
                open_ids.add(event_id)
            maximum = max(maximum, len(open_ids))
        if maximum > self.max_open_positions:
            raise ChoosinTexasError("LOCK_MISMATCH", f"reconstructed occupancy {maximum} exceeds the cap")
        return maximum

    def _open(self, event_id: str) -> dict[str, Any]:
        state = self.states.get(event_id)
        if state is None or not state["slot_open"]:
            raise ChoosinTexasError("LOCK_MISMATCH", f"{event_id} has no open slot")
        return state

    def _release_unfilled_entry(self, state: dict[str, Any]) -> None:
        self.cash_cents += int(state["reserved_premium_cents"])
        state["reserved_contracts"] = 0
        state["reserved_premium_cents"] = 0

    def _maybe_close(self, state: dict[str, Any], ts: int) -> None:
        exposure = state["filled_contracts"] - state["exit_filled_contracts"]
        if exposure == 0 and state["reserved_contracts"] == 0 and state["exit_open_contracts"] == 0:
            self._close_slot(state, ts)

    def _close_slot(self, state: dict[str, Any], ts: int) -> None:
        if int(ts) <= int(state["slot_start"]):
            raise ChoosinTexasError("LOCK_MISMATCH", "slot end is not after the reservation")
        state["slot_open"] = False
        state["slot_end"] = int(ts)
