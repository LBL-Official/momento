"""Chronological NBA 001 portfolio replay.

Candle-path prices are not fills. This module does not submit orders.
"""

from __future__ import annotations

import hashlib
import math
import random
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

STARTING_BANKROLL_CENTS = 2_000_000
ALLOCATION_NUMERATOR = 4
ALLOCATION_DENOMINATOR = 100
MAX_LIFECYCLES = 5
MARK_STALE_AFTER_SECONDS = 180
BOOTSTRAP_BLOCK = 4
BOOTSTRAP_DRAWS = 2000
BOOTSTRAP_SEED = 604
THRESHOLD = Decimal("0.015")
NY = ZoneInfo("America/New_York")
OCCUPIES = frozenset({"pending", "partial", "unknown", "open", "working"})

REPO_ROOT = Path(__file__).resolve().parents[3]

PROTECTED_FILES = (
    "ROLLER/roller/choosin_texas/locks.py",
    "ROLLER/roller/choosin_texas/locks_asked_six.py",
    "ROLLER/roller/choosin_texas/locks75.py",
    "ROLLER/roller/choosin_texas/locks77.py",
    "ROLLER/roller/choosin_texas/locks81.py",
    "ROLLER/roller/choosin_texas/locks83.py",
    "ROLLER/roller/austin/locks.py",
    "ROLLER/roller/nba_8040_reverse_features/locks.py",
    "research/choosin_texas/library/nba_2q_regular_8040_1lot_2026_27/book.json",
    "research/austin/experiments/AUSTIN_CONFIRMATION_GATE_V1/MANIFEST.json",
    "research/austin/experiments/AUSTIN_CONFIRMATION_GATE_V1/confirmation_cohort_audit.json",
    "ROLLER/roller/research/first80.py",
    "deploy/momento-live.service",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def mlb_tree_sha256(root: Path | None = None) -> tuple[str, int]:
    base = (root or REPO_ROOT) / "research" / "vital" / "bots" / "mlb-001"
    digest = hashlib.sha256()
    files = [path for path in base.rglob("*") if path.is_file()]
    files.sort(key=lambda path: path.relative_to(base).as_posix())
    for path in files:
        digest.update(path.relative_to(base).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest(), len(files)


def protected_hashes(root: Path | None = None) -> dict[str, str]:
    base = root or REPO_ROOT
    return {rel: sha256_file(base / rel) for rel in PROTECTED_FILES}


def kalshi_fee_cents(
    contracts: int,
    price_cents: int,
    *,
    role: str,
    maker_multiplier: int = 1,
) -> int:
    """Cent-aligned Kalshi fee. Model fee ceils to 1e-6 dollars, then cash ceils to the cent."""
    if contracts <= 0 or price_cents <= 0 or price_cents >= 100:
        return 0
    price = Decimal(price_cents) / Decimal(100)
    if role == "taker":
        rate = Decimal(7) / Decimal(100)
    elif role == "maker":
        rate = (Decimal(175) / Decimal(10000)) * Decimal(int(maker_multiplier))
    else:
        raise ValueError(role)
    raw = rate * Decimal(contracts) * price * (Decimal(1) - price)
    micro = (raw * Decimal(1_000_000)).to_integral_value(rounding=ROUND_CEILING)
    fee_dollars = Decimal(micro) / Decimal(1_000_000)
    notional = Decimal(contracts * price_cents) / Decimal(100)
    debit_cents = ((notional + fee_dollars) * Decimal(100)).to_integral_value(rounding=ROUND_CEILING)
    return int(debit_cents - (contracts * price_cents))


def half_away_fee_cents(contracts: int, price_cents: int, *, role: str, maker_multiplier: int = 1) -> int:
    """Sensitivity only. Not the venue rule and not the selection fee."""
    if contracts <= 0 or price_cents <= 0 or price_cents >= 100:
        return 0
    price = Decimal(price_cents) / Decimal(100)
    if role == "taker":
        rate = Decimal(7) / Decimal(100)
    elif role == "maker":
        rate = (Decimal(175) / Decimal(10000)) * Decimal(int(maker_multiplier))
    else:
        raise ValueError(role)
    raw = rate * Decimal(contracts) * price * (Decimal(1) - price)
    return int((raw * Decimal(100)).to_integral_value(rounding=ROUND_HALF_UP))


def entry_contracts(
    equity_cents: int,
    free_cash_cents: int,
    price_cents: int,
    fee_fn: Callable[[int, int], int],
) -> int:
    if equity_cents <= 0 or free_cash_cents <= 0 or price_cents <= 0:
        return 0
    budget = (equity_cents * ALLOCATION_NUMERATOR) // ALLOCATION_DENOMINATOR
    count = budget // price_cents
    while count > 0:
        cost = count * price_cents + fee_fn(count, price_cents)
        if cost <= budget and cost <= free_cash_cents:
            return count
        count -= 1
    return 0


def occupies_slot(status: str) -> bool:
    return status in OCCUPIES


def slots_used(statuses: list[str]) -> int:
    return sum(1 for status in statuses if occupies_slot(status))


def entry_allowed(statuses: list[str], *, max_slots: int = MAX_LIFECYCLES) -> bool:
    return slots_used(statuses) < max_slots


def hedge_reserve_cents(contracts: int, fee_fn: Callable[[int, int], int], *, price_cents: int = 40) -> int:
    return contracts * price_cents + fee_fn(contracts, price_cents)


def signal_order(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda row: (row["entry_ts"], str(row["game_id"]).encode("utf-8")))


def week_start(stamp: datetime) -> datetime:
    local = stamp.astimezone(NY)
    monday = local.date() - timedelta(days=local.weekday())
    return datetime(monday.year, monday.month, monday.day, tzinfo=NY)


def week_grid(start: datetime, end: datetime) -> list[datetime]:
    cursor = week_start(start)
    last = week_start(end)
    weeks = []
    while cursor <= last:
        weeks.append(cursor)
        cursor += timedelta(days=7)
    return weeks


def _parse_ts(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    stamp = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=ZoneInfo("UTC"))
    return stamp


def prepare_trade(row: dict[str, Any], *, layer: str) -> dict[str, Any]:
    entry = int(row["entry_bid_cents"] if "entry_bid_cents" in row else row["entry_price_cents"])
    t40 = bool(row["t40"])
    post_min = row.get("post_entry_min")
    trade: dict[str, Any] = {
        "game_id": str(row["game_id"]),
        "event_id": str(row.get("event_id") or row["game_id"]),
        "ticker": str(row.get("ticker") or row["game_id"]),
        "entry_ts": row["entry_ts"] if isinstance(row.get("entry_ts"), datetime) else _parse_ts(row.get("timestamp_utc") or row.get("entry_ts")),
        "exit_ts": row["exit_ts"] if isinstance(row.get("exit_ts"), datetime) else _parse_ts(row.get("exit_timestamp_utc") or row.get("exit_ts")),
        "phase": str(row.get("phase") or row.get("season_phase") or "UNSPECIFIED"),
        "slice": str(row.get("slice") or ""),
        "entry_price_cents": entry,
        "fill_observed": False,
        "entry_role": "maker",
    }
    if layer == "theoretical":
        if t40:
            trade["exit_price_cents"] = 40
            trade["settle_yes"] = False
            trade["exit_role"] = "taker"
            trade["exit_basis"] = "THEORETICAL_EXIT_AT_40"
        else:
            trade["exit_price_cents"] = None
            trade["settle_yes"] = bool(row.get("terminal_yes", True))
            trade["exit_role"] = "settlement"
            trade["exit_basis"] = "CANDLE_SETTLEMENT"
        return trade
    if layer != "conservative":
        raise ValueError(layer)
    if entry != 80:
        trade["skip"] = "INFEASIBLE_MAKER"
        return trade
    if t40:
        if post_min is None or int(post_min) > 40:
            trade["skip"] = "STOP_PRICE_UNAVAILABLE"
            return trade
        trade["exit_price_cents"] = int(post_min)
        trade["settle_yes"] = False
        trade["exit_role"] = "taker"
        trade["exit_basis"] = "POST_ENTRY_MIN_NOT_FIRST_CLOSE"
        return trade
    trade["exit_price_cents"] = None
    trade["settle_yes"] = bool(row.get("terminal_yes", True))
    trade["exit_role"] = "settlement"
    trade["exit_basis"] = "CANDLE_SETTLEMENT"
    return trade


class Mark:
    def __init__(self, cents: int, at: datetime, stale: bool) -> None:
        self.cents = cents
        self.at = at
        self.stale = stale


MarkFn = Callable[[str, datetime], Mark | None]


def _fee(contracts: int, price_cents: int, role: str, maker_multiplier: int) -> int:
    return kalshi_fee_cents(contracts, price_cents, role=role, maker_multiplier=maker_multiplier)


def replay_portfolio(
    trades: list[dict[str, Any]],
    *,
    mark_at: MarkFn | None = None,
    week_starts: list[datetime] | None = None,
    bankroll_cents: int = STARTING_BANKROLL_CENTS,
    max_slots: int = MAX_LIFECYCLES,
    maker_multiplier: int = 1,
    seed_occupants: list[str] | None = None,
) -> dict[str, Any]:
    """One chronological pass. Missing marks block entries and blank the weekly return."""
    ordered = signal_order([row for row in trades if "skip" not in row])
    skipped = [{"game_id": row["game_id"], "reason": row["skip"]} for row in trades if row.get("skip")]
    seen: set[str] = set()
    for row in skipped:
        seen.add(str(row["game_id"]))
    occupants = [status for status in (seed_occupants or []) if occupies_slot(status)]
    cash = int(bankroll_cents)
    reserved = 0
    open_positions: dict[str, dict[str, Any]] = {}
    phase_cents: dict[str, int] = {}
    entries_taken = 0
    reasons: dict[str, int] = {}

    def count(reason: str) -> None:
        reasons[reason] = reasons.get(reason, 0) + 1

    def equity_at(when: datetime) -> int | None:
        marked = 0
        for position in open_positions.values():
            if mark_at is None:
                return None
            mark = mark_at(position["ticker"], when)
            if mark is None:
                return None
            if mark.stale:
                return None
            marked += position["contracts"] * mark.cents
        return cash + reserved + marked

    events: list[tuple[datetime, int, bytes, tuple[str, Any]]] = []
    for trade in ordered:
        events.append((trade["entry_ts"], 2, trade["game_id"].encode("utf-8"), ("entry", trade)))
        if trade.get("exit_ts") is not None:
            events.append((trade["exit_ts"], 0, trade["game_id"].encode("utf-8"), ("exit", trade["game_id"])))
    if week_starts is None:
        stamps = [item[0] for item in events] or [datetime(2025, 10, 6, tzinfo=NY)]
        week_starts = week_grid(min(stamps), max(stamps))
    for start in week_starts:
        events.append((start, 1, b"", ("week", start)))
    if week_starts:
        tail = week_starts[-1] + timedelta(days=7)
        events.append((tail, 1, b"", ("week", tail)))
    events.sort(key=lambda item: (item[0], item[1], item[2]))

    snapshots: dict[datetime, int | None] = {}
    for _stamp, _order, _game, (kind, payload) in events:
        if kind == "exit":
            position = open_positions.pop(str(payload), None)
            if position is None:
                continue
            contracts = position["contracts"]
            if position["exit_role"] == "settlement":
                proceeds = contracts * 100 if position["settle_yes"] else 0
                fee = 0
            else:
                price = int(position["exit_price_cents"])
                fee = _fee(contracts, price, "taker", maker_multiplier)
                proceeds = contracts * price - fee
            cash += proceeds
            phase_cents[position["phase"]] = phase_cents.get(position["phase"], 0) + (
                proceeds - position["debit_cents"]
            )
            continue
        if kind == "week":
            snapshots[payload] = equity_at(payload)
            continue
        trade = payload
        game_id = str(trade["game_id"])
        if game_id in seen or game_id in open_positions:
            count("REENTRY")
            skipped.append({"game_id": game_id, "reason": "REENTRY"})
            continue
        seen.add(game_id)
        if len(open_positions) + len(occupants) >= max_slots:
            count("SLOT_FULL")
            skipped.append({"game_id": game_id, "reason": "SLOT_FULL"})
            continue
        if open_positions:
            if mark_at is None:
                count("MARK_UNAVAILABLE")
                skipped.append({"game_id": game_id, "reason": "MARK_UNAVAILABLE"})
                continue
            blocked = None
            for position in open_positions.values():
                mark = mark_at(position["ticker"], trade["entry_ts"])
                if mark is None:
                    blocked = "MARK_UNAVAILABLE"
                    break
                if mark.stale:
                    blocked = "STALE_MARK"
                    break
            if blocked:
                count(blocked)
                skipped.append({"game_id": game_id, "reason": blocked})
                continue
        equity = equity_at(trade["entry_ts"])
        if equity is None:
            count("MARK_UNAVAILABLE")
            skipped.append({"game_id": game_id, "reason": "MARK_UNAVAILABLE"})
            continue
        price = int(trade["entry_price_cents"])

        def fee_fn(count_n: int, price_n: int, _price: int = price) -> int:
            return _fee(count_n, price_n, "maker", maker_multiplier)

        contracts = entry_contracts(equity, cash, price, fee_fn)
        if contracts <= 0:
            count("BUDGET")
            skipped.append({"game_id": game_id, "reason": "BUDGET"})
            continue
        fee = fee_fn(contracts, price)
        debit = contracts * price + fee
        cash -= debit
        open_positions[game_id] = {
            "ticker": trade["ticker"],
            "contracts": contracts,
            "debit_cents": debit,
            "phase": trade["phase"],
            "exit_price_cents": trade.get("exit_price_cents"),
            "exit_role": trade["exit_role"],
            "settle_yes": trade["settle_yes"],
        }
        entries_taken += 1

    weeks = list(week_starts)
    returns: list[Decimal | None] = []
    for start in weeks:
        end = start + timedelta(days=7)
        begin = snapshots.get(start)
        finish = snapshots.get(end)
        if begin is None or finish is None or begin <= 0:
            returns.append(None)
            continue
        returns.append((Decimal(finish) - Decimal(begin)) / Decimal(begin))

    return {
        "fill_observed": False,
        "basis": "CANDLE_PATH_NOT_A_FILL",
        "bankroll_cents": bankroll_cents,
        "ending_cash_cents": cash,
        "open_positions": len(open_positions),
        "entries": entries_taken,
        "skips": skipped,
        "skip_reasons": reasons,
        "phase_realized_cents": phase_cents,
        "week_starts": [item.isoformat() for item in weeks],
        "weekly_returns": [None if item is None else format(item, "f") for item in returns],
        "maker_multiplier": maker_multiplier,
        "submits": False,
    }


def block_bootstrap_lower(
    returns: list[Decimal],
    *,
    block: int = BOOTSTRAP_BLOCK,
    draws: int = BOOTSTRAP_DRAWS,
    seed: int = BOOTSTRAP_SEED,
) -> dict[str, Any]:
    count = len(returns)
    if count < block:
        return {"status": "UNAVAILABLE", "reason": "SERIES_SHORTER_THAN_BLOCK"}
    rng = random.Random(seed)
    starts = count - block + 1
    means: list[Decimal] = []
    for _ in range(draws):
        sample: list[Decimal] = []
        while len(sample) < count:
            start = rng.randrange(starts)
            sample.extend(returns[start : start + block])
        sample = sample[:count]
        means.append(sum(sample, Decimal(0)) / Decimal(count))
    ordered = sorted(means)
    rank = math.ceil(Decimal("0.10") * draws)
    lower = ordered[rank - 1]
    point = sum(returns, Decimal(0)) / Decimal(count)
    return {
        "status": "OK",
        "block": block,
        "draws": draws,
        "seed": seed,
        "weeks": count,
        "point": format(point, "f"),
        "lower": format(lower, "f"),
        "rank": rank,
    }


def claim_label(point: Decimal, lower: Decimal) -> str:
    if lower >= THRESHOLD:
        return "INTERVAL_CLEARS_PRIOR_EXPLORATION_LIMITS_THE_CLAIM"
    if point >= THRESHOLD:
        return "UNCERTAIN"
    return "UNSUPPORTED"


def choose_candidate(
    bounds: dict[str, Decimal | None],
    *,
    fill_executable: bool,
) -> dict[str, Any]:
    """Hedge is ignored even when its bound is the largest."""
    union = bounds.get("union")
    if union is None:
        return {
            "status": "NO_SELECTION",
            "candidate": None,
            "reason": "UNION_BOUND_UNAVAILABLE",
            "fill_executable": fill_executable,
        }
    candidate = "union"
    chosen = union
    for name in ("q2", "q3"):
        bound = bounds.get(name)
        if bound is not None and bound > chosen:
            candidate = name
            chosen = bound
    if chosen >= THRESHOLD and fill_executable:
        status = "SELECTED_FOR_PAPER_TEST"
    else:
        status = "PROVISIONAL"
    return {
        "status": status,
        "candidate": candidate,
        "lower_bound": format(chosen, "f"),
        "fill_executable": fill_executable,
        "hedge_eligible": False,
    }
