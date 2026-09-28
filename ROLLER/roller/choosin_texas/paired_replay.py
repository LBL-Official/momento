"""Paired chronological replay of the derived-four 936. Research only.

80/40 and 80/65 see the same events. Size uses the flat stop known at
entry. P&L is marked at the first through-close. That close is not a fill.
Neither book is live.
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from roller.choosin_texas.models import ChoosinTexasError, frac, pct_display, ratio_display
from roller.choosin_texas.sources import default_asked_six_csv, repo_root

WANTED = {("NBA", "Q2"), ("NBA", "Q3"), ("NCAAB", "H1_2"), ("NCAAB", "H2_1")}
POOL_N = 936
ENTRY_CENTS = 80
GAIN_CENTS = 20
BANKROLL_CENTS = 2_000_000
PORTFOLIO_RISK_CENTS = 120_000
UNIT_BOOK_CENTS = {"80/40": 3297, "80/65": 2410}
STOP_N = {"80/40": 236, "80/65": 421}
SURVIVOR_N = {"80/40": 700, "80/65": 515}
FLAT_LOSS_CENTS = {"80/40": 40, "80/65": 15}
LOSS_MICRO_CENTS = {"80/40": 453517, "80/65": 187411}
SETTLEMENT_YES_AND_T65 = 185

CONFIGS: tuple[dict[str, Any], ...] = (
    {"id": "cap_1", "position_cap": 1, "per_position_risk_cents": 120_000},
    {"id": "cap_4", "position_cap": 4, "per_position_risk_cents": 30_000},
    {"id": "no_count_cap", "position_cap": None, "per_position_risk_cents": 30_000},
)

POLICY_ID = "CAPITAL_6PCT_CAP3"
PLANNED_RISK_ID = "PLANNED_RISK_CAP3"
CAPITAL_POSITION_PERCENT = 6
CAPITAL_PORTFOLIO_PERCENT = 18
CAPITAL_POSITION_CAP = 3
PLANNED_LOSS_PERCENT = 2
NY = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")

STRESS_NAME = "flat_stop_stress_proxy"
STRESS_MEANING = (
    "Realized through-close P&L minus open flat-stop risk. "
    "A flat-stop stress proxy. Not marked-to-market equity. "
    "Not an actual maximum drawdown. A through-close can lose more than the reserved flat risk."
)
REALIZED_NAME = "realized_through_close_pnl"


def touches_json_path() -> Path:
    return repo_root() / "research" / "choosin_texas" / "t60_band" / "touches.json"


def touches_csv_path() -> Path:
    return repo_root() / "research" / "first80_asked_six_45_35_barriers" / "touches.csv"


def _require_file(path: Path) -> None:
    if not path.is_file():
        raise ChoosinTexasError("DATA_REQUIRED", f"missing {path}")


def _as_int(value: Any, *, label: str) -> int:
    if value in (None, ""):
        raise ChoosinTexasError("LOCK_MISMATCH", f"missing integer {label}")
    try:
        return int(float(value))
    except (TypeError, ValueError) as exc:
        raise ChoosinTexasError("LOCK_MISMATCH", f"{label} is not an integer") from exc


def _optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(float(value))


def load_rows(
    *,
    ledger_path: Path | None = None,
    touch_json_path: Path | None = None,
    touch_csv_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Join the ledger, the 65/40 timestamps, and the 40 through-close."""
    ledger_path = ledger_path or default_asked_six_csv()
    touch_json_path = touch_json_path or touches_json_path()
    touch_csv_path = touch_csv_path or touches_csv_path()
    for path in (ledger_path, touch_json_path, touch_csv_path):
        _require_file(path)

    ledger: dict[str, dict[str, str]] = {}
    with ledger_path.open(newline="", encoding="utf-8") as handle:
        for rec in csv.DictReader(handle):
            key = (rec["sport"].strip(), rec["slice"].strip())
            if key not in WANTED:
                continue
            ticker = rec["ticker"].strip()
            if ticker in ledger:
                raise ChoosinTexasError("LOCK_MISMATCH", f"duplicate ledger ticker {ticker}")
            ledger[ticker] = rec
    if len(ledger) != POOL_N:
        raise ChoosinTexasError("LOCK_MISMATCH", f"derived four {len(ledger)} != {POOL_N}")

    doc = json.loads(touch_json_path.read_text(encoding="utf-8"))
    touch_rows = doc.get("rows")
    if not isinstance(touch_rows, list):
        raise ChoosinTexasError("LOCK_MISMATCH", "touch artifact rows missing")
    touches: dict[str, dict[str, Any]] = {}
    for row in touch_rows:
        ticker = str(row.get("ticker") or "")
        if not ticker or ticker in touches:
            raise ChoosinTexasError("LOCK_MISMATCH", f"duplicate or blank touch ticker {ticker}")
        touches[ticker] = row
    if set(touches) != set(ledger):
        raise ChoosinTexasError("LOCK_MISMATCH", "touch tickers do not match the derived four")

    closes: dict[str, int | None] = {}
    with touch_csv_path.open(newline="", encoding="utf-8") as handle:
        for rec in csv.DictReader(handle):
            key = (rec["sport"].strip(), rec["slice"].strip())
            if key not in WANTED:
                continue
            ticker = rec["ticker"].strip()
            if ticker in closes:
                raise ChoosinTexasError("LOCK_MISMATCH", f"duplicate t40 close {ticker}")
            raw = rec.get("t40_close")
            closes[ticker] = None if raw in (None, "") else _as_int(raw, label=f"{ticker} t40_close")
    if set(closes) != set(ledger):
        raise ChoosinTexasError("LOCK_MISMATCH", "t40 close tickers do not match the derived four")

    rows: list[dict[str, Any]] = []
    event_ids: set[str] = set()
    for ticker, rec in ledger.items():
        touch = touches[ticker]
        event_id = str(rec["event_id"]).strip()
        if not event_id or event_id in event_ids:
            raise ChoosinTexasError("LOCK_MISMATCH", f"duplicate or blank event_id {event_id}")
        event_ids.add(event_id)
        entry_ts = _as_int(rec["timestamp"], label=f"{ticker} entry")
        ledger_exit_ts = _as_int(rec["exit_timestamp"], label=f"{ticker} exit")
        if ledger_exit_ts < entry_ts:
            raise ChoosinTexasError("LOCK_MISMATCH", f"{ticker} settlement before entry")
        exit_kind = str(rec["exit_kind"])
        t40_ts = _optional_int(touch.get("t40_ts"))
        t65_ts = _optional_int(touch.get("t65_ts"))
        t65_close = _optional_int(touch.get("t65_close"))
        t40_close = closes[ticker]
        post_min = _as_int(touch["post_min"], label=f"{ticker} post_min")
        if (t65_close is not None) != (post_min <= 65):
            raise ChoosinTexasError("LOCK_MISMATCH", f"{ticker} t65 flag drifted from post_min")
        if (t65_close is None) != (t65_ts is None):
            raise ChoosinTexasError("DATA_REQUIRED", f"{ticker} t65 timestamp missing")
        if exit_kind == "T40_CLOSE":
            if t40_ts is None or t40_ts != ledger_exit_ts or t40_close is None:
                raise ChoosinTexasError("LOCK_MISMATCH", f"{ticker} t40 clock or close mismatch")
        elif t40_ts is not None or t40_close is not None:
            raise ChoosinTexasError("LOCK_MISMATCH", f"{ticker} t40 set without T40_CLOSE")
        if t65_ts is not None and t65_ts <= entry_ts:
            raise ChoosinTexasError("LOCK_MISMATCH", f"{ticker} t65_ts not after entry")
        if t40_ts is not None and t65_ts is not None and t65_ts > t40_ts:
            raise ChoosinTexasError("LOCK_MISMATCH", f"{ticker} t65_ts after t40_ts")
        rows.append(
            {
                "ticker": ticker,
                "event_id": event_id,
                "sport": str(rec["sport"]).strip(),
                "slice": str(rec["slice"]).strip(),
                "entry_ts": entry_ts,
                "ledger_exit_ts": ledger_exit_ts,
                "ledger_exit_kind": exit_kind,
                "t40_ts": t40_ts,
                "t40_close": t40_close,
                "t65_ts": t65_ts,
                "t65_close": t65_close,
            }
        )
    rows.sort(key=lambda row: (row["entry_ts"], row["ticker"]))
    return rows


def exit_view(row: dict[str, Any], book: str) -> dict[str, Any]:
    if book == "80/40":
        stopped = row["t40_ts"] is not None
        exit_ts = row["t40_ts"] if stopped else row["ledger_exit_ts"]
        exit_px = row["t40_close"] if stopped else 100
    elif book == "80/65":
        stopped = row["t65_close"] is not None
        if stopped and row["t65_ts"] is None:
            raise ChoosinTexasError("DATA_REQUIRED", f"{row['ticker']} t65 timestamp missing")
        exit_ts = row["t65_ts"] if stopped else row["ledger_exit_ts"]
        exit_px = row["t65_close"] if stopped else 100
    else:
        raise ChoosinTexasError("LOCK_MISMATCH", f"unknown book {book}")
    if int(exit_ts) <= int(row["entry_ts"]):
        raise ChoosinTexasError("LOCK_MISMATCH", f"{row['ticker']} {book} exit is not after entry")
    if not stopped and row["ledger_exit_kind"] != "SETTLEMENT_YES":
        raise ChoosinTexasError("LOCK_MISMATCH", f"{row['ticker']} {book} survivor is not SETTLEMENT_YES")
    return {
        "stopped": stopped,
        "exit_ts": int(exit_ts),
        "exit_px": int(exit_px),
        "flat_loss_cents": FLAT_LOSS_CENTS[book],
    }


def _loss_micro(rows: list[dict[str, Any]], book: str) -> int:
    closes = [int(exit_view(row, book)["exit_px"]) for row in rows if exit_view(row, book)["stopped"]]
    n_stops = len(closes)
    if n_stops != STOP_N[book]:
        raise ChoosinTexasError("LOCK_MISMATCH", f"{book} stops {n_stops} != {STOP_N[book]}")
    total_loss = sum(ENTRY_CENTS - close for close in closes)
    micro = (total_loss * 10_000 + n_stops // 2) // n_stops
    if micro != LOSS_MICRO_CENTS[book]:
        raise ChoosinTexasError("LOCK_MISMATCH", f"{book} loss micro {micro} != {LOSS_MICRO_CENTS[book]}")
    return micro


def unit_book_cents(rows: list[dict[str, Any]], book: str) -> int:
    total = 0
    survivors = 0
    for row in rows:
        view = exit_view(row, book)
        total += int(view["exit_px"]) - ENTRY_CENTS
        survivors += int(not view["stopped"])
    if survivors != SURVIVOR_N[book]:
        raise ChoosinTexasError("LOCK_MISMATCH", f"{book} survivors {survivors} != {SURVIVOR_N[book]}")
    if total != UNIT_BOOK_CENTS[book]:
        raise ChoosinTexasError("LOCK_MISMATCH", f"{book} unit book {total} != {UNIT_BOOK_CENTS[book]}")
    return total


def _budget_contracts(budget_units: int, loss_units: int) -> int:
    if loss_units <= 0:
        raise ChoosinTexasError("LOCK_MISMATCH", "loss unit must be positive")
    if budget_units <= 0:
        return 0
    return budget_units // loss_units


def replay(
    rows: list[dict[str, Any]],
    book: str,
    config: dict[str, Any],
    *,
    sizing: str,
) -> dict[str, Any]:
    """One book, one cap, one sizing rule. Integer cents."""
    if sizing not in ("flat_stop", "in_sample_average_gap"):
        raise ChoosinTexasError("LOCK_MISMATCH", f"unknown sizing {sizing}")
    flat_loss = FLAT_LOSS_CENTS[book]
    loss_micro = LOSS_MICRO_CENTS[book]
    per_position = int(config["per_position_risk_cents"])
    position_cap = config["position_cap"]
    if sizing == "flat_stop":
        loss_units = flat_loss
        scale = 1
    else:
        loss_units = loss_micro
        scale = 10_000

    events = []
    for row in rows:
        view = exit_view(row, book)
        events.append(
            {
                "ticker": row["ticker"],
                "event_id": row["event_id"],
                "entry_ts": row["entry_ts"],
                "ledger_exit_ts": row["ledger_exit_ts"],
                "ledger_exit_kind": row["ledger_exit_kind"],
                **view,
            }
        )

    actions: list[tuple[Any, ...]] = []
    for event in events:
        actions.append((event["entry_ts"], 1, event["ticker"], event["event_id"], "entry", event))
        actions.append((event["exit_ts"], 0, event["ticker"], event["event_id"], "exit", event))
    actions.sort()

    cash = BANKROLL_CENTS
    open_positions: dict[str, dict[str, int]] = {}
    open_ids: set[str] = set()
    open_budget = 0
    open_flat = 0
    deployed = 0
    realized_through = 0
    realized_flat = 0
    skips: Counter[str] = Counter()
    resized: list[dict[str, Any]] = []
    entries_taken = 0
    contracts_taken = 0
    max_open = 0
    max_deployed = 0
    proxy_path: list[int] = []
    realized_path: list[int] = []
    proxy_min = 0
    realized_min = 0

    def mark(*, on_exit: bool) -> None:
        nonlocal proxy_min, realized_min
        proxy = realized_through - open_flat
        proxy_path.append(proxy)
        if proxy < proxy_min:
            proxy_min = proxy
        if on_exit:
            realized_path.append(realized_through)
            if realized_through < realized_min:
                realized_min = realized_through

    for _ts, _order, _ticker, _event_id, kind, event in actions:
        if kind == "exit":
            pos = open_positions.pop(event["ticker"], None)
            if pos is None:
                continue
            contracts = pos["contracts"]
            cash += event["exit_px"] * contracts
            realized_through += (event["exit_px"] - ENTRY_CENTS) * contracts
            if event["stopped"]:
                realized_flat += -flat_loss * contracts
            else:
                realized_flat += GAIN_CENTS * contracts
            open_budget -= pos["reserved_budget"]
            open_flat -= pos["flat_risk_cents"]
            deployed -= ENTRY_CENTS * contracts
            open_ids.discard(event["event_id"])
            mark(on_exit=True)
            continue

        if position_cap is not None and len(open_positions) >= int(position_cap):
            skips["POSITION_CAP"] += 1
            continue
        if event["event_id"] in open_ids:
            skips["SAME_EVENT"] += 1
            continue
        remaining_budget = PORTFOLIO_RISK_CENTS * scale - open_budget
        by_position = _budget_contracts(per_position * scale, loss_units)
        by_remaining = _budget_contracts(remaining_budget, loss_units)
        requested = min(by_position, by_remaining)
        if requested < 1:
            skips["SKIP_RISK_BUDGET"] += 1
            continue
        by_cash = cash // ENTRY_CENTS
        if by_cash < 1:
            skips["SKIP_CASH"] += 1
            continue
        contracts = requested
        if by_cash < requested:
            contracts = by_cash
            resized.append(
                {
                    "ticker": event["ticker"],
                    "contracts_requested": requested,
                    "contracts_taken": contracts,
                    "premium_cut_cents": (requested - contracts) * ENTRY_CENTS,
                }
            )
        cash -= ENTRY_CENTS * contracts
        reserved_budget = contracts * loss_units
        flat_risk = contracts * flat_loss
        open_budget += reserved_budget
        open_flat += flat_risk
        deployed += ENTRY_CENTS * contracts
        open_positions[event["ticker"]] = {
            "contracts": contracts,
            "reserved_budget": reserved_budget,
            "flat_risk_cents": flat_risk,
        }
        open_ids.add(event["event_id"])
        entries_taken += 1
        contracts_taken += contracts
        if len(open_positions) > max_open:
            max_open = len(open_positions)
        if deployed > max_deployed:
            max_deployed = deployed
        mark(on_exit=False)

    if open_positions or open_budget or open_flat or deployed:
        raise ChoosinTexasError("LOCK_MISMATCH", f"{book} {config['id']} left positions open")
    if cash != BANKROLL_CENTS + realized_through:
        raise ChoosinTexasError("LOCK_MISMATCH", f"{book} {config['id']} cash ledger broke")

    body = {
        "book": book,
        "configuration_id": config["id"],
        "sizing": sizing,
        "live_size": False,
        "per_position_risk_cents": per_position,
        "position_cap": position_cap,
        "flat_loss_cents": flat_loss,
        "loss_micro_cents": loss_micro if sizing == "in_sample_average_gap" else None,
        "entries_taken": entries_taken,
        "contracts_taken": contracts_taken,
        "max_concurrent": max_open,
        "max_deployed_cents": max_deployed,
        "final_cash_cents": cash,
        "through_close_pnl_cents": realized_through,
        "flat_stop_pnl_cents": realized_flat,
        "skips": {
            "SKIP_CASH": int(skips["SKIP_CASH"]),
            "SKIP_RISK_BUDGET": int(skips["SKIP_RISK_BUDGET"]),
            "POSITION_CAP": int(skips["POSITION_CAP"]),
            "SAME_EVENT": int(skips["SAME_EVENT"]),
        },
        "resized_cash_n": len(resized),
        "resized_cash": resized,
        "flat_stop_stress_proxy": {
            "name": STRESS_NAME,
            "meaning": STRESS_MEANING,
            "min_cents": proxy_min,
            "final_cents": realized_through,
            "path_cents": proxy_path,
        },
        "realized_pnl_path": {
            "name": REALIZED_NAME,
            "meaning": "Cumulative realized through-close P&L on closed trades only.",
            "min_cents": realized_min,
            "final_cents": realized_through,
            "path_cents": realized_path,
        },
    }
    if sizing == "in_sample_average_gap":
        body["sizing_label"] = "IN_SAMPLE"
    return body


def _clock_audit(rows: list[dict[str, Any]]) -> dict[str, int]:
    settlement_yes_stops = [
        row
        for row in rows
        if row["t65_ts"] is not None and row["ledger_exit_kind"] == "SETTLEMENT_YES"
    ]
    used_settlement = 0
    for row in settlement_yes_stops:
        view = exit_view(row, "80/65")
        if view["exit_ts"] != row["t65_ts"] or view["exit_ts"] == row["ledger_exit_ts"]:
            used_settlement += 1
    if len(settlement_yes_stops) != SETTLEMENT_YES_AND_T65:
        raise ChoosinTexasError(
            "LOCK_MISMATCH",
            f"SETTLEMENT_YES and T65 {len(settlement_yes_stops)} != {SETTLEMENT_YES_AND_T65}",
        )
    if used_settlement != 0:
        raise ChoosinTexasError("LOCK_MISMATCH", "a 65-stop used the settlement clock")
    return {
        "t65_stops": STOP_N["80/65"],
        "t65_stops_ledger_settlement_yes": len(settlement_yes_stops),
        "those_marked_at_settlement": used_settlement,
    }


def _require_unix(ts: Any, *, label: str) -> int:
    if type(ts) is not int:
        raise ChoosinTexasError("LOCK_MISMATCH", f"{label} timestamp is not a Unix second")
    return ts


def ny_session_date(ts: int) -> date:
    instant = datetime.fromtimestamp(_require_unix(ts, label="session"), tz=UTC)
    return instant.astimezone(NY).date()


def _is_ny_midnight(ts: int) -> bool:
    local = datetime.fromtimestamp(ts, tz=UTC).astimezone(NY)
    return local.hour == 0 and local.minute == 0 and local.second == 0


def _ny_clock(ts: int) -> str:
    local = datetime.fromtimestamp(int(ts), tz=UTC).astimezone(NY)
    return local.strftime("%Y-%m-%d %H:%M:%S America/New_York")


def _dollars(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    amount = abs(int(cents))
    return f"{sign}{amount // 100}.{amount % 100:02d}"


def _require_positive_int(value: Any, *, label: str) -> int:
    if type(value) is not int or value < 1:
        raise ChoosinTexasError("LOCK_MISMATCH", f"{label} must be a positive integer")
    return value


def decide_capital_entry(
    *,
    same_event: bool,
    open_count: int,
    per_position_cap_cents: int,
    portfolio_premium_cap_cents: int,
    open_premium_cents: int,
    cash_cents: int,
    max_open_positions: int = CAPITAL_POSITION_CAP,
) -> dict[str, Any]:
    """One reason. Capital is entry premium. Stop distance is not an input."""
    _require_positive_int(max_open_positions, label="max_open_positions")
    if same_event:
        return {
            "reason": "SAME_EVENT",
            "requested_contracts": 0,
            "accepted_contracts": 0,
            "constraint_tie": False,
        }
    if open_count >= max_open_positions:
        return {
            "reason": "POSITION_CAP",
            "requested_contracts": 0,
            "accepted_contracts": 0,
            "constraint_tie": False,
        }
    per_contracts = per_position_cap_cents // ENTRY_CENTS
    remaining = max(0, portfolio_premium_cap_cents - open_premium_cents)
    capital_contracts = min(per_contracts, remaining // ENTRY_CENTS)
    cash_contracts = cash_cents // ENTRY_CENTS
    if capital_contracts < 1:
        return {
            "reason": "SKIP_CAPITAL_BUDGET",
            "requested_contracts": per_contracts,
            "accepted_contracts": 0,
            "constraint_tie": False,
        }
    if cash_contracts < 1:
        return {
            "reason": "SKIP_CASH",
            "requested_contracts": capital_contracts,
            "accepted_contracts": 0,
            "constraint_tie": False,
        }
    if cash_contracts < capital_contracts:
        return {
            "reason": "RESIZED_CASH",
            "requested_contracts": capital_contracts,
            "accepted_contracts": cash_contracts,
            "constraint_tie": False,
        }
    if capital_contracts < per_contracts:
        return {
            "reason": "RESIZED_CAPITAL_BUDGET",
            "requested_contracts": per_contracts,
            "accepted_contracts": capital_contracts,
            "constraint_tie": cash_contracts == capital_contracts,
        }
    return {
        "reason": "ADMITTED",
        "requested_contracts": per_contracts,
        "accepted_contracts": per_contracts,
        "constraint_tie": False,
    }


def _events_for_book(rows: list[dict[str, Any]], book: str) -> list[dict[str, Any]]:
    events = []
    for row in rows:
        view = exit_view(row, book)
        for label, ts in (("entry", row["entry_ts"]), ("exit", view["exit_ts"])):
            _require_unix(ts, label=f"{row['ticker']} {label}")
        events.append(
            {
                "ticker": row["ticker"],
                "event_id": row["event_id"],
                "sport": row.get("sport", ""),
                "slice": row.get("slice", ""),
                "entry_ts": row["entry_ts"],
                "ledger_exit_ts": row["ledger_exit_ts"],
                "ledger_exit_kind": row["ledger_exit_kind"],
                **view,
            }
        )
    return events


def position_premium_cap_cents(basis: int, book: str, mode: str) -> int:
    """Cents of entry premium allowed for one new position.

    premium6 is the 6% cap. planned_risk keeps that cap for 80/65 and, for
    80/40, uses the tighter of 6% premium and 2% planned stop loss. The 2%
    figure is the target size, not a resize and not a realized-loss cap.
    """
    premium_cap = basis * CAPITAL_POSITION_PERCENT // 100
    if mode != "planned_risk" or book != "80/40":
        return premium_cap
    by_premium = premium_cap // ENTRY_CENTS
    by_risk = (basis * PLANNED_LOSS_PERCENT // 100) // FLAT_LOSS_CENTS["80/40"]
    return min(by_premium, by_risk) * ENTRY_CENTS


def _loss_breaches_plan(book: str, loss_cents: int, basis_cents: int) -> bool:
    if loss_cents <= 0 or basis_cents <= 0:
        return False
    if book == "80/40":
        return loss_cents * 100 > basis_cents * PLANNED_LOSS_PERCENT
    if book == "80/65":
        return loss_cents * 800 > basis_cents * 9
    raise ChoosinTexasError("LOCK_MISMATCH", f"unknown book {book}")


def replay_capital_6pct(
    rows: list[dict[str, Any]],
    book: str,
    *,
    mode: str = "premium6",
    max_open_positions: int = CAPITAL_POSITION_CAP,
) -> dict[str, Any]:
    """Session replay. premium6 is 6% entry premium. planned_risk adds the 80/40 2% planned-loss target."""
    if mode not in ("premium6", "planned_risk"):
        raise ChoosinTexasError("LOCK_MISMATCH", f"unknown capital mode {mode}")
    _require_positive_int(max_open_positions, label="max_open_positions")
    flat_loss = FLAT_LOSS_CENTS[book]
    events = _events_for_book(rows, book)
    actions: list[tuple[Any, ...]] = []
    for event in events:
        actions.append((event["entry_ts"], 1, event["ticker"], event["event_id"], "entry", event))
        actions.append((event["exit_ts"], 0, event["ticker"], event["event_id"], "exit", event))
    actions.sort()

    cash = BANKROLL_CENTS
    open_positions: dict[str, dict[str, Any]] = {}
    open_ids: set[str] = set()
    realized_through = 0
    realized_flat = 0
    contracts_taken = 0
    max_open = 0
    max_premium = 0
    max_premium_basis = BANKROLL_CENTS
    max_premium_session = ""
    largest_loss = 0
    largest_loss_basis = BANKROLL_CENTS
    max_planned = 0
    max_planned_basis = 1
    breaches: list[dict[str, Any]] = []
    proxy_min = 0
    capital_peak = BANKROLL_CENTS
    max_drawdown = 0
    drawdown_peak = BANKROLL_CENTS
    session_date: date | None = None
    need_freeze = False
    pending_midnight_pnl = 0
    basis = BANKROLL_CENTS
    per_cap = position_premium_cap_cents(BANKROLL_CENTS, book, mode)
    port_cap = BANKROLL_CENTS * CAPITAL_PORTFOLIO_PERCENT // 100
    sessions: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    capital_path: list[int] = []
    proxy_path: list[int] = []
    drawdown_path: list[int] = []
    path_ts: list[int] = []
    reason_counts: Counter[str] = Counter()

    def open_premium() -> int:
        return sum(int(pos["entry_premium"]) for pos in open_positions.values())

    def open_flat() -> int:
        return sum(int(pos["flat_risk"]) for pos in open_positions.values())

    def mark(ts: int) -> None:
        nonlocal proxy_min, capital_peak, max_drawdown, drawdown_peak
        nonlocal max_premium, max_premium_basis, max_premium_session
        realized_capital = BANKROLL_CENTS + realized_through
        if realized_capital > capital_peak:
            capital_peak = realized_capital
        drawdown = capital_peak - realized_capital
        if drawdown > max_drawdown:
            max_drawdown = drawdown
            drawdown_peak = capital_peak
        proxy = realized_through - open_flat()
        if proxy < proxy_min:
            proxy_min = proxy
        premium = open_premium()
        if premium > max_premium and session_date is not None:
            max_premium = premium
            max_premium_basis = basis
            max_premium_session = session_date.isoformat()
        capital_path.append(realized_capital)
        proxy_path.append(proxy)
        drawdown_path.append(drawdown)
        path_ts.append(ts)

    def freeze(day: date, midnight_pnl: int) -> None:
        nonlocal basis, per_cap, port_cap
        premium = open_premium()
        basis = cash + premium
        if basis <= 0:
            raise ChoosinTexasError("LOCK_MISMATCH", f"{book} session basis is not positive")
        per_cap = position_premium_cap_cents(basis, book, mode)
        port_cap = basis * CAPITAL_PORTFOLIO_PERCENT // 100
        sessions.append(
            {
                "date": day.isoformat(),
                "session_basis_cents": basis,
                "per_position_cap_cents": per_cap,
                "portfolio_premium_cap_cents": port_cap,
                "open_entry_premium_at_freeze_cents": premium,
                "carried_positions": len(open_positions),
                "carried_positions_priced_at_entry_cost": True,
                "carried_over_cap": premium > port_cap,
                "realized_exit_pnl_cents": midnight_pnl,
            }
        )

    def apply_exit(event: dict[str, Any]) -> int:
        nonlocal cash, realized_through, realized_flat, largest_loss, largest_loss_basis
        pos = open_positions.pop(event["event_id"], None)
        if pos is None:
            return 0
        contracts = int(pos["contracts"])
        cash += int(event["exit_px"]) * contracts
        if cash < 0:
            raise ChoosinTexasError("LOCK_MISMATCH", f"{book} cash went negative")
        through = (int(event["exit_px"]) - ENTRY_CENTS) * contracts
        if event["stopped"]:
            flat = -flat_loss * contracts
        else:
            flat = GAIN_CENTS * contracts
        realized_through += through
        realized_flat += flat
        entry_basis = int(pos.get("entry_basis") or basis)
        if through < largest_loss:
            largest_loss = through
            largest_loss_basis = entry_basis
        if mode == "planned_risk" and through < 0 and _loss_breaches_plan(book, -through, entry_basis):
            loss = -through
            cap = entry_basis * PLANNED_LOSS_PERCENT // 100 if book == "80/40" else entry_basis * 9 // 800
            breaches.append(
                {
                    "event_id": event["event_id"],
                    "entry_ts": pos["entry_ts"],
                    "exit_ts": event["exit_ts"],
                    "contracts": contracts,
                    "session_basis_cents": entry_basis,
                    "planned_loss_cents": int(pos["planned_loss"]),
                    "through_close_cents": int(event["exit_px"]),
                    "realized_loss_cents": loss,
                    "excess_cents": loss - cap,
                }
            )
        if mode == "planned_risk":
            recorded = pos.get("decision")
            if recorded is not None:
                recorded["through_close_cents"] = int(event["exit_px"])
                recorded["realized_pnl_cents"] = through
        open_ids.discard(event["event_id"])
        return through

    seen_exit: set[str] = set()
    for ts, _order, _ticker, _event_id, kind, event in actions:
        if kind == "exit" and event["event_id"] in seen_exit:
            raise ChoosinTexasError("LOCK_MISMATCH", f"{book} duplicate exit {event['event_id']}")
        if kind == "exit":
            seen_exit.add(event["event_id"])
        day = ny_session_date(ts)
        if session_date != day:
            if session_date is not None and need_freeze:
                freeze(session_date, pending_midnight_pnl)
                need_freeze = False
            session_date = day
            need_freeze = True
            pending_midnight_pnl = 0
        if need_freeze and kind == "exit" and _is_ny_midnight(ts):
            pending_midnight_pnl += apply_exit(event)
            mark(ts)
            continue
        if need_freeze:
            freeze(day, pending_midnight_pnl)
            need_freeze = False
        if kind == "exit":
            pnl = apply_exit(event)
            if sessions:
                sessions[-1]["realized_exit_pnl_cents"] += pnl
            mark(ts)
            continue
        cash_before = cash
        premium_before = open_premium()
        open_before = len(open_positions)
        occupants = sorted(open_ids)
        decision = decide_capital_entry(
            same_event=event["event_id"] in open_ids,
            open_count=open_before,
            per_position_cap_cents=per_cap,
            portfolio_premium_cap_cents=port_cap,
            open_premium_cents=premium_before,
            cash_cents=cash_before,
            max_open_positions=max_open_positions,
        )
        accepted = int(decision["accepted_contracts"])
        reason = str(decision["reason"])
        reason_counts[reason] += 1
        premium_taken = ENTRY_CENTS * accepted
        record = {
            "event_id": event["event_id"],
            "ticker": event["ticker"],
            "sport": event.get("sport", ""),
            "slice": event.get("slice", ""),
            "configuration_id": (
                PLANNED_RISK_ID
                if mode == "planned_risk" and max_open_positions == CAPITAL_POSITION_CAP
                else f"PLANNED_RISK_OPEN_{max_open_positions}"
                if mode == "planned_risk"
                else POLICY_ID
            ),
            "max_open_positions": max_open_positions,
            "session_date": day.isoformat(),
            "entry_ts": event["entry_ts"],
            "reason": reason,
            "accepted": accepted > 0,
            "requested_contracts": decision["requested_contracts"],
            "accepted_contracts": accepted,
            "constraint_tie": decision["constraint_tie"],
            "open_count_before": open_before,
            "open_count_after": open_before + (1 if accepted > 0 else 0),
            "occupying_event_ids": occupants,
            "blocking_event_ids": occupants if reason == "POSITION_CAP" else [],
            "cash_before_cents": cash_before,
            "cash_after_cents": cash_before - premium_taken,
            "open_premium_before_cents": premium_before,
            "open_premium_after_cents": premium_before + premium_taken,
            "per_position_premium_cap_cents": per_cap,
            "portfolio_premium_cap_cents": port_cap,
            "session_basis_cents": basis,
            "exit_ts": event["exit_ts"],
            "ledger_exit_ts": event["ledger_exit_ts"],
            "ledger_exit_kind": event["ledger_exit_kind"],
            "stopped": event["stopped"],
        }
        if mode == "planned_risk":
            record["entry_session_basis_cents"] = basis
            record["planned_loss_cents"] = accepted * flat_loss
            record["through_close_cents"] = None
            record["realized_pnl_cents"] = 0
        decisions.append(record)
        if accepted < 1:
            mark(ts)
            continue
        premium = ENTRY_CENTS * accepted
        planned_loss = accepted * flat_loss
        if planned_loss * max_planned_basis > max_planned * basis:
            max_planned = planned_loss
            max_planned_basis = basis
        if premium > cash:
            raise ChoosinTexasError("LOCK_MISMATCH", f"{book} entry spent cash it did not have")
        cash -= premium
        open_positions[event["event_id"]] = {
            "contracts": accepted,
            "entry_premium": premium,
            "flat_risk": planned_loss,
            "planned_loss": planned_loss,
            "entry_basis": basis,
            "entry_ts": event["entry_ts"],
            "decision": record if mode == "planned_risk" else None,
        }
        open_ids.add(event["event_id"])
        contracts_taken += accepted
        if len(open_positions) > max_open:
            max_open = len(open_positions)
        mark(ts)

    if need_freeze and session_date is not None:
        freeze(session_date, pending_midnight_pnl)
    if open_positions:
        raise ChoosinTexasError("LOCK_MISMATCH", f"{book} capital policy left positions open")
    if cash != BANKROLL_CENTS + realized_through:
        raise ChoosinTexasError("LOCK_MISMATCH", f"{book} capital cash ledger broke")
    if not sessions:
        raise ChoosinTexasError("LOCK_MISMATCH", f"{book} capital policy had no session")

    accepted = [row for row in decisions if int(row["accepted_contracts"]) > 0]
    stopped = sum(1 for row in accepted if row["stopped"])
    survivors = len(accepted) - stopped
    worst = min(sessions, key=lambda row: (int(row["realized_exit_pnl_cents"]), row["date"]))
    carried_sessions = sum(1 for row in sessions if int(row["carried_positions"]) > 0)
    if max_premium_basis <= 0:
        raise ChoosinTexasError("LOCK_MISMATCH", f"{book} premium basis is not positive")
    if drawdown_peak <= 0:
        raise ChoosinTexasError("LOCK_MISMATCH", f"{book} drawdown peak is not positive")
    full_contracts = position_premium_cap_cents(BANKROLL_CENTS, book, mode) // ENTRY_CENTS
    loss_pct_basis = largest_loss_basis if largest_loss < 0 else 1
    loss_pct_numer = -largest_loss if largest_loss < 0 else 0
    result = {
        "book": book,
        "policy_id": PLANNED_RISK_ID if mode == "planned_risk" else POLICY_ID,
        "live_authorized": False,
        "session_timezone": "America/New_York",
        "timestamp_convention": "Unix seconds interpreted as UTC, then America/New_York calendar dates",
        "date_start": sessions[0]["date"],
        "date_end": sessions[-1]["date"],
        "candidates": len(decisions),
        "accepted": len(accepted),
        "stopped": stopped,
        "survivors": survivors,
        "accepted_win_rate_display": ratio_display(survivors, len(accepted)) if accepted else "0/0",
        "full_book_survivor_display": ratio_display(SURVIVOR_N[book], POOL_N),
        "reasons": {
            "ADMITTED": int(reason_counts["ADMITTED"]),
            "SAME_EVENT": int(reason_counts["SAME_EVENT"]),
            "POSITION_CAP": int(reason_counts["POSITION_CAP"]),
            "SKIP_CAPITAL_BUDGET": int(reason_counts["SKIP_CAPITAL_BUDGET"]),
            "SKIP_CASH": int(reason_counts["SKIP_CASH"]),
            "RESIZED_CAPITAL_BUDGET": int(reason_counts["RESIZED_CAPITAL_BUDGET"]),
            "RESIZED_CASH": int(reason_counts["RESIZED_CASH"]),
        },
        "constraint_tie_n": sum(1 for row in decisions if row["constraint_tie"]),
        "contracts_taken": contracts_taken,
        "through_close_pnl_cents": realized_through,
        "flat_stop_pnl_cents": realized_flat,
        "ending_cash_cents": cash,
        "return_on_initial_display": ratio_display(realized_through, BANKROLL_CENTS),
        "return_on_initial_pct_display": pct_display(realized_through, BANKROLL_CENTS),
        "max_concurrent": max_open,
        "max_open_entry_premium_cents": max_premium,
        "max_open_entry_premium_dollars_display": _dollars(max_premium),
        "max_open_entry_premium_session": max_premium_session,
        "max_open_entry_premium_of_basis_display": ratio_display(max_premium, max_premium_basis),
        "max_open_entry_premium_of_basis_pct_display": pct_display(max_premium, max_premium_basis),
        "largest_single_realized_loss_cents": largest_loss,
        "largest_single_realized_loss_dollars_display": _dollars(largest_loss),
        "worst_session_date": worst["date"],
        "worst_session_realized_exit_pnl_cents": worst["realized_exit_pnl_cents"],
        "sessions_with_carried_positions": carried_sessions,
        "planned_flat_loss_per_full_position_cents": full_contracts * flat_loss,
        "initial_full_position_contracts": full_contracts,
        "position_cap": max_open_positions,
        "max_open_positions": max_open_positions,
        "realized_capital": {
            "name": "realized_capital",
            "meaning": "Initial capital plus cumulative realized exit P&L. Open P&L is omitted.",
            "final_cents": BANKROLL_CENTS + realized_through,
            "path_cents": capital_path,
            "path_ts": path_ts,
        },
        "realized_capital_max_drawdown": {
            "name": "realized_capital_max_drawdown",
            "meaning": (
                "Peak-to-trough decline of realized capital. "
                "Not actual portfolio mark-to-market drawdown."
            ),
            "cents": max_drawdown,
            "dollars_display": _dollars(max_drawdown),
            "peak_cents": drawdown_peak,
            "of_peak_display": ratio_display(max_drawdown, drawdown_peak),
            "of_peak_pct_display": pct_display(max_drawdown, drawdown_peak),
            "path_cents": drawdown_path,
        },
        "flat_stop_stress_proxy": {
            "name": STRESS_NAME,
            "meaning": STRESS_MEANING,
            "min_cents": proxy_min,
            "final_cents": realized_through,
            "path_cents": proxy_path,
        },
        "sessions": [
            {
                "date": row["date"],
                "session_basis_cents": row["session_basis_cents"],
                "carried_positions": row["carried_positions"],
                "carried_positions_priced_at_entry_cost": row["carried_positions_priced_at_entry_cost"],
                "carried_over_cap": row["carried_over_cap"],
                "open_entry_premium_at_freeze_cents": row["open_entry_premium_at_freeze_cents"],
                "realized_exit_pnl_cents": row["realized_exit_pnl_cents"],
            }
            for row in sessions
        ],
        "decisions": decisions,
    }
    if mode == "planned_risk":
        breach_loss = sum(int(row["realized_loss_cents"]) for row in breaches)
        largest_breach = max(breaches, key=lambda row: int(row["realized_loss_cents"])) if breaches else None
        result["realized_loss_cap"] = "NOT_ESTABLISHED"
        result["sizing_note"] = (
            "The 80/40 2% planned-loss limit normally deploys 4% of session basis, not 6%."
            if book == "80/40"
            else "80/65 is sized on 6% entry premium. Planned loss is 15¢ per contract, not a 6% risk budget."
        )
        result["max_planned_stop_risk_of_basis_display"] = ratio_display(max_planned, max_planned_basis)
        result["max_planned_stop_risk_of_basis_pct_display"] = pct_display(max_planned, max_planned_basis)
        result["largest_single_realized_loss_of_basis_pct_display"] = pct_display(loss_pct_numer, loss_pct_basis)
        result["worst_session_dollars_display"] = _dollars(int(worst["realized_exit_pnl_cents"]))
        result["worst_session_of_basis_pct_display"] = pct_display(
            int(worst["realized_exit_pnl_cents"]),
            int(worst["session_basis_cents"]),
        )
        result["loss_breaches"] = breaches if book == "80/40" else []
        result["loss_breach_summary"] = {
            "threshold": "2% of entry session basis" if book == "80/40" else "1.125% of entry session basis",
            "count": len(breaches),
            "total_realized_loss_cents": breach_loss,
            "largest_event_id": None if largest_breach is None else largest_breach["event_id"],
            "largest_realized_loss_cents": 0 if largest_breach is None else largest_breach["realized_loss_cents"],
            "largest_of_basis_pct_display": (
                "0/1"
                if largest_breach is None
                else pct_display(
                    int(largest_breach["realized_loss_cents"]),
                    int(largest_breach["session_basis_cents"]),
                )
            ),
        }
    return result


def build_capital_policy(rows: list[dict[str, Any]]) -> dict[str, Any]:
    books = {book: replay_capital_6pct(rows, book) for book in ("80/40", "80/65")}
    accepted = {
        book: {row["event_id"] for row in body["decisions"] if int(row["accepted_contracts"]) > 0}
        for book, body in books.items()
    }
    both = accepted["80/40"] & accepted["80/65"]
    return {
        "id": POLICY_ID,
        "live_authorized": False,
        "october_3_arms_either_book": False,
        "primary_research_candidate": "80/40",
        "session_timezone": "America/New_York",
        "timestamp_convention": "Unix seconds interpreted as UTC, then America/New_York calendar dates",
        "premium_percent_per_position": CAPITAL_POSITION_PERCENT,
        "premium_percent_portfolio": CAPITAL_PORTFOLIO_PERCENT,
        "position_cap": CAPITAL_POSITION_CAP,
        "entry_cents": ENTRY_CENTS,
        "initial_cash_cents": BANKROLL_CENTS,
        "initial_per_position_premium_cents": BANKROLL_CENTS * CAPITAL_POSITION_PERCENT // 100,
        "initial_portfolio_premium_cents": BANKROLL_CENTS * CAPITAL_PORTFOLIO_PERCENT // 100,
        "initial_full_position_contracts": (BANKROLL_CENTS * CAPITAL_POSITION_PERCENT // 100) // ENTRY_CENTS,
        "notices": {
            "CANDLE_PATH_NOT_FILL": "CANDLE_PATH_NOT_FILL",
            "FEES_UNAVAILABLE": "FEES_UNAVAILABLE",
            "LIVE_EXECUTION_DISABLED": "LIVE_EXECUTION_DISABLED",
            "forecast": "Historical chronological replay; not a forecast.",
        },
        "accepted_both": len(both),
        "accepted_only_80_40": len(accepted["80/40"] - accepted["80/65"]),
        "accepted_only_80_65": len(accepted["80/65"] - accepted["80/40"]),
        "books": books,
    }


QUANTILE_CONVENTION = (
    "Sort ascending. An even count uses the lower of the two middle observed values. "
    "The 95th percentile is the observed value at index ceil(0.95 * n) - 1. No averaging."
)
PRIOR_PLANNED_ACCEPTED = {"80/40": 820, "80/65": 865}
PRIOR_PLANNED_PNL = {"80/40": 5_335_376, "80/65": 8_119_467}


def _lower_median(sorted_vals: list[int]) -> int:
    count = len(sorted_vals)
    if count < 1:
        raise ChoosinTexasError("LOCK_MISMATCH", "quantile of an empty sample")
    if count % 2 == 1:
        return sorted_vals[count // 2]
    return sorted_vals[count // 2 - 1]


def _percentile_95(sorted_vals: list[int]) -> int:
    count = len(sorted_vals)
    if count < 1:
        raise ChoosinTexasError("LOCK_MISMATCH", "quantile of an empty sample")
    index = (95 * count + 99) // 100 - 1
    return sorted_vals[index]


def _fraction_less(left: tuple[int, int, str], right: tuple[int, int, str]) -> bool:
    return left[0] * right[1] < right[0] * left[1]


def reconstruct_occupancy(
    positions: list[dict[str, Any]],
    *,
    max_open_positions: int | None = None,
) -> dict[str, Any]:
    """Rebuild occupancy from accepted [entry, exit) intervals. Ignores engine counters."""
    if max_open_positions is not None:
        _require_positive_int(max_open_positions, label="max_open_positions")
    actions: list[tuple[Any, ...]] = []
    seen: set[str] = set()
    for pos in positions:
        event_id = str(pos["event_id"])
        if event_id in seen:
            raise ChoosinTexasError("LOCK_MISMATCH", f"duplicate accepted interval {event_id}")
        seen.add(event_id)
        entry_ts = int(pos["entry_ts"])
        exit_ts = int(pos["exit_ts"])
        if exit_ts <= entry_ts:
            raise ChoosinTexasError("LOCK_MISMATCH", f"{event_id} interval is not positive")
        actions.append((entry_ts, 1, str(pos["ticker"]), event_id, 1))
        actions.append((exit_ts, 0, str(pos["ticker"]), event_id, -1))
    actions.sort()
    open_ids: set[str] = set()
    max_count = 0
    points: list[dict[str, Any]] = []
    seconds: Counter[int] = Counter()
    if not actions:
        return {
            "max_concurrent": 0,
            "window_start_ts": None,
            "window_end_ts": None,
            "window": "No accepted positions.",
            "seconds_at_open_count": {"0": 0, "1": 0, "2": 0, "3": 0},
            "change_points": [],
        }
    prev_ts = int(actions[0][0])
    prev_count = 0
    for ts, _order, _ticker, event_id, delta in actions:
        ts = int(ts)
        if ts != prev_ts:
            seconds[prev_count] += ts - prev_ts
            prev_ts = ts
        before = len(open_ids)
        if delta < 0:
            if event_id not in open_ids:
                raise ChoosinTexasError("LOCK_MISMATCH", f"{event_id} exit has no open interval")
            open_ids.remove(event_id)
            kind = "exit"
        else:
            if event_id in open_ids:
                raise ChoosinTexasError("LOCK_MISMATCH", f"{event_id} is already open")
            open_ids.add(event_id)
            kind = "entry"
        after = len(open_ids)
        if after > max_count:
            max_count = after
        points.append(
            {
                "ts": ts,
                "kind": kind,
                "event_id": event_id,
                "open_count_before": before,
                "open_count": after,
            }
        )
        prev_count = after
    if open_ids:
        raise ChoosinTexasError("LOCK_MISMATCH", "reconstructed occupancy did not finish flat")
    if max_open_positions is not None and max_count > max_open_positions:
        raise ChoosinTexasError(
            "LOCK_MISMATCH",
            f"reconstructed occupancy {max_count} exceeds cap {max_open_positions}",
        )
    window_end = int(actions[-1][0])
    reported = {str(level): int(seconds[level]) for level in range(4)}
    return {
        "max_concurrent": max_count,
        "window_start_ts": int(actions[0][0]),
        "window_end_ts": window_end,
        "window": (
            "Unix seconds from the first accepted entry through the last accepted exit. "
            "The final exit second is excluded."
        ),
        "seconds_at_open_count": reported,
        "change_points": points,
    }


def _expected_occupants(positions: list[dict[str, Any]], decision: dict[str, Any]) -> list[str]:
    entry_ts = int(decision["entry_ts"])
    ticker = str(decision["ticker"])
    event_id = str(decision["event_id"])
    occupants: list[str] = []
    for pos in positions:
        pos_entry = int(pos["entry_ts"])
        pos_exit = int(pos["exit_ts"])
        if pos_exit <= entry_ts or pos_entry > entry_ts:
            continue
        if pos_entry < entry_ts or (pos["ticker"], pos["event_id"]) < (ticker, event_id):
            occupants.append(str(pos["event_id"]))
    return sorted(occupants)


def _positions_from_decisions(book: str, decisions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    positions = []
    for row in decisions:
        if int(row["accepted_contracts"]) < 1:
            continue
        if row.get("through_close_cents") is None or "realized_pnl_cents" not in row:
            raise ChoosinTexasError("LOCK_MISMATCH", f"{row['event_id']} accepted position has no exit")
        stopped = bool(row["stopped"])
        if book == "80/40":
            exit_type = "T40_CLOSE" if stopped else "SETTLEMENT_YES"
        else:
            exit_type = "T65_CLOSE" if stopped else "SETTLEMENT_YES"
        positions.append(
            {
                "strategy": book,
                "configuration_id": row["configuration_id"],
                "event_id": row["event_id"],
                "ticker": row["ticker"],
                "sport": row.get("sport", ""),
                "slice": row.get("slice", ""),
                "entry_ts": row["entry_ts"],
                "exit_ts": row["exit_ts"],
                "contracts": row["accepted_contracts"],
                "entry_premium_cents": ENTRY_CENTS * int(row["accepted_contracts"]),
                "exit_type": exit_type,
                "through_close_cents": row["through_close_cents"],
                "planned_loss_cents": row["planned_loss_cents"],
                "realized_pnl_cents": row["realized_pnl_cents"],
                "entry_session_basis_cents": row["entry_session_basis_cents"],
            }
        )
    return positions


def verify_admission_ledger(
    body: dict[str, Any],
    *,
    expected_candidates: int | None = None,
) -> dict[str, Any]:
    decisions = body["decisions"]
    if expected_candidates is not None and len(decisions) != expected_candidates:
        raise ChoosinTexasError(
            "LOCK_MISMATCH",
            f"{body['book']} candidates {len(decisions)} != {expected_candidates}",
        )
    accepted_rows = [row for row in decisions if int(row["accepted_contracts"]) > 0]
    rejected_rows = [row for row in decisions if int(row["accepted_contracts"]) < 1]
    if len(accepted_rows) + len(rejected_rows) != len(decisions):
        raise ChoosinTexasError("LOCK_MISMATCH", f"{body['book']} admissions do not partition candidates")
    if len({row["event_id"] for row in decisions}) != len(decisions):
        raise ChoosinTexasError("LOCK_MISMATCH", f"{body['book']} duplicate candidate")
    for row in rejected_rows:
        if int(row["cash_after_cents"]) != int(row["cash_before_cents"]):
            raise ChoosinTexasError("LOCK_MISMATCH", f"{row['event_id']} rejected trade changed cash")
        if int(row["open_count_after"]) != int(row["open_count_before"]):
            raise ChoosinTexasError("LOCK_MISMATCH", f"{row['event_id']} rejected trade changed occupancy")
    positions = _positions_from_decisions(str(body["book"]), decisions)
    occupancy = reconstruct_occupancy(positions, max_open_positions=int(body["max_open_positions"]))
    if int(occupancy["max_concurrent"]) != int(body["max_concurrent"]):
        raise ChoosinTexasError(
            "LOCK_MISMATCH",
            f"{body['book']} reconstructed max {occupancy['max_concurrent']} != engine {body['max_concurrent']}",
        )
    if int(body["ending_cash_cents"]) != BANKROLL_CENTS + int(body["through_close_pnl_cents"]):
        raise ChoosinTexasError("LOCK_MISMATCH", f"{body['book']} cash does not match realized P&L")
    cap = int(body["max_open_positions"])
    for row in decisions:
        expected = _expected_occupants(positions, row)
        if expected != sorted(row["occupying_event_ids"]):
            raise ChoosinTexasError("LOCK_MISMATCH", f"{row['event_id']} occupants do not match intervals")
        if len(expected) != int(row["open_count_before"]):
            raise ChoosinTexasError("LOCK_MISMATCH", f"{row['event_id']} open count does not match intervals")
        if row["reason"] == "POSITION_CAP" and len(row["blocking_event_ids"]) != cap:
            raise ChoosinTexasError("LOCK_MISMATCH", f"{row['event_id']} position cap did not name {cap} blockers")
    occupancy["accepted_positions"] = len(positions)
    return occupancy


def _loss_rank_row(event_id: str, loss: int, basis: int) -> dict[str, Any]:
    return {
        "event_id": event_id,
        "realized_loss_cents": loss,
        "dollars_display": _dollars(-loss),
        "entry_session_basis_cents": basis,
        "of_basis_pct_display": pct_display(loss, basis),
    }


def loss_severity(body: dict[str, Any]) -> dict[str, Any]:
    """Dollar rank and percentage rank stay separate. Threshold tests stay integer."""
    book = str(body["book"])
    losses = []
    stopped_frac: list[tuple[int, int, str]] = []
    for row in body["decisions"]:
        if int(row["accepted_contracts"]) < 1:
            continue
        pnl = int(row["realized_pnl_cents"])
        basis = int(row["entry_session_basis_cents"])
        if pnl < 0:
            losses.append(( -pnl, basis, str(row["event_id"])))
        if row["stopped"]:
            loss = -pnl if pnl < 0 else 0
            stopped_frac.append((loss, basis, str(row["event_id"])))
    dollar = max(losses, key=lambda item: (item[0], item[2])) if losses else None
    percent = None
    if losses:
        percent = losses[0]
        for item in losses[1:]:
            if item[0] * percent[1] > percent[0] * item[1]:
                percent = item
    excesses = sorted(int(row["excess_cents"]) for row in body.get("loss_breaches", []))
    if book == "80/65":
        excesses = []
        for row in body["decisions"]:
            if int(row["accepted_contracts"]) < 1 or int(row["realized_pnl_cents"]) >= 0:
                continue
            loss = -int(row["realized_pnl_cents"])
            basis = int(row["entry_session_basis_cents"])
            if loss * 800 > basis * 9:
                excesses.append(loss - (basis * 9 // 800))
        excesses.sort()
    stopped_n = sum(1 for row in body["decisions"] if int(row["accepted_contracts"]) > 0 and row["stopped"])
    breach_n = len(excesses) if book == "80/65" else int(body["loss_breach_summary"]["count"])
    stopped_pct = {}
    if stopped_frac:
        ordered_index = list(range(len(stopped_frac)))
        ordered = list(stopped_frac)
        for index in range(1, len(ordered)):
            cursor = index
            while cursor > 0 and _fraction_less(ordered[cursor], ordered[cursor - 1]):
                ordered[cursor - 1], ordered[cursor] = ordered[cursor], ordered[cursor - 1]
                cursor -= 1
        picks = {
            "median": _lower_median(ordered_index),
            "p95": _percentile_95(ordered_index),
            "maximum": ordered_index[-1],
        }
        stopped_pct = {
            name: pct_display(ordered[index][0], ordered[index][1]) for name, index in picks.items()
        }
    excess_stats = {}
    if excesses:
        excess_stats = {
            "median_cents": _lower_median(excesses),
            "p95_cents": _percentile_95(excesses),
            "maximum_cents": excesses[-1],
        }
    return {
        "quantile_convention": QUANTILE_CONVENTION,
        "largest_dollar_loss": None if dollar is None else _loss_rank_row(dollar[2], dollar[0], dollar[1]),
        "largest_percent_loss": None if percent is None else _loss_rank_row(percent[2], percent[0], percent[1]),
        "largest_dollar_and_percent_same_event": (
            False if dollar is None or percent is None else dollar[2] == percent[2]
        ),
        "breach_count": breach_n,
        "stopped": stopped_n,
        "breach_share_display": ratio_display(breach_n, stopped_n) if stopped_n else "0/0",
        "breach_share_pct_display": pct_display(breach_n, stopped_n) if stopped_n else "0/0",
        "stopped_loss_pct": stopped_pct,
        "breach_excess": excess_stats,
    }


def _blocked_example(
    blocked: dict[str, Any],
    accepted_by_id: dict[str, dict[str, Any]],
    freed: dict[str, Any] | None,
) -> dict[str, Any]:
    blockers = []
    for event_id in blocked["blocking_event_ids"]:
        pos = accepted_by_id[str(event_id)]
        blockers.append(
            {
                "event_id": event_id,
                "entry_ts": pos["entry_ts"],
                "entry_ts_display": _ny_clock(int(pos["entry_ts"])),
                "exit_ts": pos["exit_ts"],
                "exit_ts_display": _ny_clock(int(pos["exit_ts"])),
            }
        )
    entry_clock = _ny_clock(int(blocked["entry_ts"]))
    relation = "This rejection is its own timestamp."
    if freed is not None:
        admitted_id = str(freed["entry"]["event_id"])
        admitted_clock = str(freed["entry"]["ts_display"])
        if admitted_id in blocked["blocking_event_ids"] and int(blocked["entry_ts"]) > int(freed["entry"]["ts"]):
            relation = (
                f"{admitted_id} is admitted at {admitted_clock} in the freed-slot window. "
                f"It is already open when {blocked['event_id']} is rejected at {entry_clock}."
            )
        elif int(blocked["entry_ts"]) != int(freed["entry"]["ts"]):
            relation = "This rejection is a different timestamp from the freed-slot window."
    return {
        "event_id": blocked["event_id"],
        "ticker": blocked["ticker"],
        "sport": blocked.get("sport", ""),
        "slice": blocked.get("slice", ""),
        "entry_ts": blocked["entry_ts"],
        "entry_ts_display": entry_clock,
        "session_date": blocked["session_date"],
        "blocking_event_ids": blocked["blocking_event_ids"],
        "blocking_event_ids_display": ", ".join(blocked["blocking_event_ids"]),
        "blockers": blockers,
        "relation_to_freed_window": relation,
    }


def turnover_report(body: dict[str, Any], occupancy: dict[str, Any]) -> dict[str, Any]:
    decisions = body["decisions"]
    accepted = [row for row in decisions if int(row["accepted_contracts"]) > 0]
    by_date: Counter[str] = Counter(str(row["session_date"]) for row in accepted)
    daily = sorted(by_date.values())
    holds = sorted(int(row["exit_ts"]) - int(row["entry_ts"]) for row in accepted)
    arrivals: Counter[str] = Counter()
    for row in decisions:
        before = int(row["open_count_before"])
        key = str(before) if before <= 3 else "4_or_more"
        arrivals[key] += 1
    busiest = None
    if by_date:
        busiest_date = min(by_date, key=lambda day: (-by_date[day], day))
        busiest = {"date": busiest_date, "accepted": by_date[busiest_date]}
    blocked = next((row for row in decisions if row["reason"] == "POSITION_CAP"), None)
    accepted_by_id = {str(row["event_id"]): row for row in accepted}
    open_now: set[str] = set()
    enriched: list[dict[str, Any]] = []
    for point in occupancy["change_points"]:
        event_id = str(point["event_id"])
        if point["kind"] == "exit":
            open_now.discard(event_id)
        else:
            open_now.add(event_id)
        if len(open_now) != int(point["open_count"]):
            raise ChoosinTexasError("LOCK_MISMATCH", f"{event_id} occupancy step does not match the open set")
        occupants = sorted(open_now)
        enriched.append(
            {
                **point,
                "ts_display": _ny_clock(int(point["ts"])),
                "occupying_event_ids": occupants,
                "occupying_event_ids_display": ", ".join(occupants) if occupants else "none",
            }
        )
    freed = None
    cap = int(body["max_open_positions"])
    for index, point in enumerate(enriched):
        if point["kind"] != "exit" or int(point["open_count_before"]) != cap or int(point["open_count"]) != cap - 1:
            continue
        steps = [point]
        for item in enriched[index + 1 :]:
            if int(item["open_count_before"]) != int(steps[-1]["open_count"]):
                raise ChoosinTexasError("LOCK_MISMATCH", "freed-slot steps do not chain")
            steps.append(item)
            if item["kind"] == "entry":
                break
        if steps[-1]["kind"] != "entry":
            continue
        freed = {
            "exit": steps[0],
            "entry": steps[-1],
            "steps": steps,
            "sequence_display": " then ".join(
                f"{step['ts_display']} {step['kind']} {step['event_id']} leaves {step['open_count']}: {step['occupying_event_ids_display']}"
                for step in steps
            ),
        }
        break
    other_skips = int(body["candidates"]) - int(body["accepted"]) - int(body["reasons"]["POSITION_CAP"])
    return {
        "quantile_convention": QUANTILE_CONVENTION,
        "date_start": body["date_start"],
        "date_end": body["date_end"],
        "dates_with_candidates": len({row["session_date"] for row in decisions}),
        "dates_with_accepted_entries": len(by_date),
        "accepted_per_entry_date": {
            "median": _lower_median(daily) if daily else None,
            "p95": _percentile_95(daily) if daily else None,
            "maximum": daily[-1] if daily else None,
        },
        "holding_seconds": {
            "median": _lower_median(holds) if holds else None,
            "p95": _percentile_95(holds) if holds else None,
            "maximum": holds[-1] if holds else None,
        },
        "candidates_by_open_count_before": {key: int(arrivals[key]) for key in ("0", "1", "2", "3", "4_or_more")},
        "position_cap_skips": int(body["reasons"]["POSITION_CAP"]),
        "other_skips": other_skips,
        "busiest_entry_date": busiest,
        "blocked_example": None if blocked is None else _blocked_example(blocked, accepted_by_id, freed),
        "freed_example": freed,
        "blocked_example_note": None if blocked is not None else "No POSITION_CAP rejection exists in this replay.",
        "freed_example_note": None if freed is not None else "No exit-then-entry window exists in this replay.",
    }


def _annotate_planned_book(body: dict[str, Any], *, expected_candidates: int | None) -> dict[str, Any]:
    occupancy = verify_admission_ledger(body, expected_candidates=expected_candidates)
    body["configuration_id"] = (
        PLANNED_RISK_ID
        if int(body["max_open_positions"]) == CAPITAL_POSITION_CAP
        else f"PLANNED_RISK_OPEN_{body['max_open_positions']}"
    )
    body["occupancy"] = occupancy
    body["turnover"] = turnover_report(body, occupancy)
    body["loss_severity"] = loss_severity(body)
    return body


def _diagnostic_row(body: dict[str, Any]) -> dict[str, Any]:
    return {
        "book": body["book"],
        "configuration_id": body["configuration_id"],
        "max_open_positions": body["max_open_positions"],
        "primary": int(body["max_open_positions"]) == CAPITAL_POSITION_CAP,
        "label": "primary policy" if int(body["max_open_positions"]) == CAPITAL_POSITION_CAP else "diagnostic count only",
        "accepted": body["accepted"],
        "through_close_pnl_cents": body["through_close_pnl_cents"],
        "ending_cash_cents": body["ending_cash_cents"],
        "reconstructed_max_concurrent": body["occupancy"]["max_concurrent"],
        "position_cap_skips": body["reasons"]["POSITION_CAP"],
        "other_skips": body["turnover"]["other_skips"],
        "initial_full_position_contracts": body["initial_full_position_contracts"],
        "largest_dollar_loss_event": None
        if body["loss_severity"]["largest_dollar_loss"] is None
        else body["loss_severity"]["largest_dollar_loss"]["event_id"],
        "largest_percent_loss_event": None
        if body["loss_severity"]["largest_percent_loss"] is None
        else body["loss_severity"]["largest_percent_loss"]["event_id"],
    }


def _planned_risk_runs(rows: list[dict[str, Any]]) -> dict[tuple[str, int], dict[str, Any]]:
    expected = POOL_N if len(rows) == POOL_N else None
    runs: dict[tuple[str, int], dict[str, Any]] = {}
    for cap in (1, 2, 3):
        for book in ("80/40", "80/65"):
            body = replay_capital_6pct(rows, book, mode="planned_risk", max_open_positions=cap)
            runs[(book, cap)] = _annotate_planned_book(body, expected_candidates=expected)
    return runs


def _policy_from_runs(runs: dict[tuple[str, int], dict[str, Any]]) -> dict[str, Any]:
    books = {book: runs[(book, CAPITAL_POSITION_CAP)] for book in ("80/40", "80/65")}
    accepted = {
        book: {row["event_id"] for row in body["decisions"] if int(row["accepted_contracts"]) > 0}
        for book, body in books.items()
    }
    both = accepted["80/40"] & accepted["80/65"]
    confirmed = all(
        books[book]["accepted"] == PRIOR_PLANNED_ACCEPTED[book]
        and books[book]["through_close_pnl_cents"] == PRIOR_PLANNED_PNL[book]
        for book in ("80/40", "80/65")
    )
    return {
        "id": PLANNED_RISK_ID,
        "live_authorized": False,
        "october_3_arms_either_book": False,
        "primary_research_candidate": "80/40",
        "prior_result_status": "CONFIRMED" if confirmed else "SUPERSEDED",
        "selects_a_cap": False,
        "realized_loss_cap": "NOT_ESTABLISHED",
        "sizing_note": "The 80/40 2% planned-loss limit normally deploys 4% of session basis, not 6%.",
        "session_timezone": "America/New_York",
        "timestamp_convention": "Unix seconds interpreted as UTC, then America/New_York calendar dates",
        "position_cap": CAPITAL_POSITION_CAP,
        "entry_cents": ENTRY_CENTS,
        "initial_cash_cents": BANKROLL_CENTS,
        "quantile_convention": QUANTILE_CONVENTION,
        "configuration": {
            "max_open_positions": CAPITAL_POSITION_CAP,
            "premium_percent_per_position": CAPITAL_POSITION_PERCENT,
            "planned_stop_risk_percent_80_40": PLANNED_LOSS_PERCENT,
            "planned_stop_risk_percent_80_65": None,
            "premium_percent_portfolio": CAPITAL_PORTFOLIO_PERCENT,
            "session_timezone": "America/New_York",
            "session_convention": (
                "Frozen America/New_York session basis. Same-session wins do not raise size. "
                "A gap is not cut to the planned-loss percent."
            ),
            "reconstructed_max_concurrent_80_40": books["80/40"]["occupancy"]["max_concurrent"],
            "reconstructed_max_concurrent_80_65": books["80/65"]["occupancy"]["max_concurrent"],
        },
        "headings": {
            "book_40": "80/40: 2% planned risk, up to 6% premium",
            "book_65": "80/65: 6% premium",
            "both": "Both: maximum 3 simultaneous positions",
        },
        "notices": {
            "CANDLE_PATH_NOT_FILL": "CANDLE_PATH_NOT_FILL",
            "FEES_UNAVAILABLE": "FEES_UNAVAILABLE",
            "LIVE_EXECUTION_DISABLED": "LIVE_EXECUTION_DISABLED",
            "forecast": "Historical chronological replay; not a forecast.",
        },
        "accepted_both": len(both),
        "accepted_only_80_40": len(accepted["80/40"] - accepted["80/65"]),
        "accepted_only_80_65": len(accepted["80/65"] - accepted["80/40"]),
        "diagnostics": [
            _diagnostic_row(runs[(book, cap)]) for cap in (1, 2, 3) for book in ("80/40", "80/65")
        ],
        "books": books,
    }


def build_planned_risk_policy(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return _policy_from_runs(_planned_risk_runs(rows))


def write_planned_risk_audit(rows: list[dict[str, Any]], dest: Path | None = None) -> Path:
    """Write the admission ledgers. The HTTP handler does not call this."""
    runs = _planned_risk_runs(rows)
    policy = _policy_from_runs(runs)
    root = dest or (repo_root() / "research" / "choosin_texas" / "paired_replay" / "audit")
    root.mkdir(parents=True, exist_ok=True)
    for (book, cap), body in runs.items():
        folder = root / book.replace("/", "_") / f"open_{cap}"
        folder.mkdir(parents=True, exist_ok=True)
        admissions = body["decisions"]
        positions = _positions_from_decisions(book, admissions)
        (folder / "admissions.json").write_text(json.dumps(admissions, indent=2) + "\n", encoding="utf-8")
        (folder / "positions.json").write_text(json.dumps(positions, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "prior_result_status": policy["prior_result_status"],
        "live_authorized": False,
        "selects_a_cap": False,
        "quantile_convention": QUANTILE_CONVENTION,
        "configuration": policy["configuration"],
        "runs": policy["diagnostics"],
    }
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    prior = repo_root() / "research" / "choosin_texas" / "paired_replay" / "prior" / "planned_risk_cap3.json"
    if prior.is_file() and policy["prior_result_status"] == "CONFIRMED":
        saved = json.loads(prior.read_text(encoding="utf-8"))
        saved["status"] = "CONFIRMED"
        saved["enforcement"] = (
            "Independent interval reconstruction matched the engine. "
            "PLANNED_RISK_CAP3 accepted counts and through-close P&L are unchanged. "
            "CAPITAL_6PCT_CAP3 is a separate file."
        )
        saved.pop("capital_policy", None)
        prior.write_text(json.dumps(saved, indent=2) + "\n", encoding="utf-8")
    elif prior.is_file():
        saved = json.loads(prior.read_text(encoding="utf-8"))
        saved["status"] = "SUPERSEDED"
        saved["enforcement"] = "A later audit disagreed with these counts. This file keeps the prior numbers."
        prior.write_text(json.dumps(saved, indent=2) + "\n", encoding="utf-8")
    return root


def build_paired_replay(
    *,
    ledger_path: Path | None = None,
    touch_json_path: Path | None = None,
    touch_csv_path: Path | None = None,
) -> dict[str, Any]:
    rows = load_rows(
        ledger_path=ledger_path,
        touch_json_path=touch_json_path,
        touch_csv_path=touch_csv_path,
    )
    if len(rows) != POOL_N:
        raise ChoosinTexasError("LOCK_MISMATCH", f"replay rows {len(rows)} != {POOL_N}")
    unit = {}
    for book in ("80/40", "80/65"):
        _loss_micro(rows, book)
        unit[book] = {
            "through_close_book_cents": unit_book_cents(rows, book),
            "stops": STOP_N[book],
            "survivors": SURVIVOR_N[book],
            "flat_loss_cents": FLAT_LOSS_CENTS[book],
            "contracts": 1,
        }
    runs = []
    for sizing in ("flat_stop", "in_sample_average_gap"):
        for book in ("80/40", "80/65"):
            for config in CONFIGS:
                runs.append(replay(rows, book, config, sizing=sizing))
    return {
        "status": "OBSERVED",
        "product": "Choosin Texas",
        "page": "paired_replay",
        "live_execution": False,
        "submits": False,
        "live_authorized": False,
        "primary_research_candidate": "80/40",
        "label": "CANDLE_PATH_NOT_FILL",
        "n": POOL_N,
        "bankroll_cents": BANKROLL_CENTS,
        "portfolio_risk_cents": PORTFOLIO_RISK_CENTS,
        "entry_cents": ENTRY_CENTS,
        "gain_cents": GAIN_CENTS,
        "fees": "UNAVAILABLE",
        "configurations": [
            {
                "id": config["id"],
                "position_cap": config["position_cap"],
                "per_position_risk_cents": config["per_position_risk_cents"],
                "portfolio_risk_cents": PORTFOLIO_RISK_CENTS,
            }
            for config in CONFIGS
        ],
        "unit_book": unit,
        "clock": _clock_audit(rows),
        "runs": runs,
        "capital_policy": build_capital_policy(rows),
        "planned_risk_policy": build_planned_risk_policy(rows),
        "disclaimers": [
            "LIVE EXECUTION = FALSE",
            "CANDLE PATH ≠ ACTUAL FILL",
            "Neither 80/40 nor 80/65 is authorized for live trading",
            "80/40 remains the primary research candidate",
            "flat_stop_stress_proxy is not marked-to-market equity and not maximum drawdown",
            "Fees are UNAVAILABLE, not zero",
            "In-sample average-gap sizing is fit on these 936 events and is not a live size",
            "CAPITAL_6PCT_CAP3 sizes entry premium. It is not a live deployment rule",
            "PLANNED_RISK_CAP3 limits 80/40 by 2% planned stop risk. A gap is not cut to 2%",
            "asked-six (1182) ≠ derived four (936)",
        ],
    }
