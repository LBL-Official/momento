"""Build the execution-validation artifact off the request path.

The HTTP handler only reads the written summary. It does not scan candles
and it does not submit orders.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from roller.choosin_texas.execution_validation.classify import (
    classify_buy_limit,
    classify_sell_limit,
    e4_to_cents,
)
from roller.choosin_texas.execution_validation.fees import historical_fee_status
from roller.choosin_texas.execution_validation.policy import (
    CAPITAL_6PCT_INITIAL_CONTRACTS,
    CAPITAL_6PCT_PNL_CENTS,
    CONFIGURATION_ID,
    INITIAL_CONTRACTS,
    REFERENCE_ACCEPTED,
    REFERENCE_PNL_CENTS,
    SPEC_ID,
    STARTING_CASH_CENTS,
    UNIT_BOOK_CENTS,
    specification,
)
from roller.choosin_texas.models import ChoosinTexasError
from roller.choosin_texas.paired_replay import load_rows, unit_book_cents
from roller.choosin_texas.sources import repo_root

SUBMISSION_ACTIONS = frozenset(
    {"place_order", "submit_order", "create_order", "cancel_order", "decrease_order"}
)
CANDLE_COLUMNS = [
    "end_period_ts",
    "yes_bid_close_e4",
    "yes_ask_close_e4",
    "orderbook_depth_available",
    "ingested_at",
    "source",
    "market_data_type",
]
TRADE_COLUMNS = ["timestamp", "yes_price_e4", "quantity_hundredths", "taker_side"]


def artifact_dir() -> Path:
    return repo_root() / "research" / "choosin_texas" / "execution_validation"


def summary_path() -> Path:
    return artifact_dir() / "summary.json"


def accept_read_only(record: dict[str, Any]) -> dict[str, Any]:
    action = record.get("action")
    if action in SUBMISSION_ACTIONS:
        raise ChoosinTexasError("LOCK_MISMATCH", "execution validation cannot submit orders")
    return {
        "status": "NOT_A_FILL",
        "evidence_level": "OBSERVED_MARKET_DATA",
        "submits": False,
    }


def load_summary() -> dict[str, Any]:
    path = summary_path()
    if not path.is_file():
        raise ChoosinTexasError("DATA_REQUIRED", f"missing {path}")
    body = json.loads(path.read_text(encoding="utf-8"))
    if body.get("spec_id") != SPEC_ID or body.get("configuration_id") != CONFIGURATION_ID:
        raise ChoosinTexasError("LOCK_MISMATCH", "execution summary is not the frozen specification")
    if body.get("execution_aware_portfolio_pnl") != "NOT_REPORTED":
        raise ChoosinTexasError("LOCK_MISMATCH", "execution summary published a portfolio P&L")
    if body.get("live_execution") != "LIVE_EXECUTION_DISABLED":
        raise ChoosinTexasError("LOCK_MISMATCH", "execution summary is not research-only")
    from roller.choosin_texas.execution_validation.prospective import (
        collector_health,
        observation_policy,
    )

    body["prospective_collector"] = collector_health()
    body["observation_policy"] = observation_policy()
    body["execution_aware_portfolio_pnl"] = "NOT_REPORTED"
    return body


def verify_baseline() -> dict[str, Any]:
    """Halt if the frozen candle results or the separate 6% file have drifted."""
    root = repo_root() / "research" / "choosin_texas" / "paired_replay" / "prior"
    planned_path = root / "planned_risk_cap3.json"
    capital_path = root / "capital_6pct_cap3.json"
    planned_text = planned_path.read_text(encoding="utf-8")
    capital_text = capital_path.read_text(encoding="utf-8")
    if "11164842" in planned_text:
        raise ChoosinTexasError("LOCK_MISMATCH", "planned-risk prior still contains the 6% profit")
    planned = json.loads(planned_text)
    capital = json.loads(capital_text)
    if planned.get("policy_id") != CONFIGURATION_ID:
        raise ChoosinTexasError("LOCK_MISMATCH", "planned-risk prior is not PLANNED_RISK_CAP3")
    if capital.get("policy_id") != "CAPITAL_6PCT_CAP3":
        raise ChoosinTexasError("LOCK_MISMATCH", "6% prior is not CAPITAL_6PCT_CAP3")
    planned_books = planned["planned_risk_policy"]["books"]
    capital_books = capital["capital_policy"]["books"]
    for book, pnl in REFERENCE_PNL_CENTS.items():
        if int(planned_books[book]["through_close_pnl_cents"]) != pnl:
            raise ChoosinTexasError("LOCK_MISMATCH", f"{book} planned profit drifted")
        if int(planned_books[book]["accepted"]) != REFERENCE_ACCEPTED[book]:
            raise ChoosinTexasError("LOCK_MISMATCH", f"{book} planned admissions drifted")
        if int(planned_books[book]["initial_full_position_contracts"]) != INITIAL_CONTRACTS[book]:
            raise ChoosinTexasError("LOCK_MISMATCH", f"{book} planned size drifted")
    for book, pnl in CAPITAL_6PCT_PNL_CENTS.items():
        if int(capital_books[book]["through_close_pnl_cents"]) != pnl:
            raise ChoosinTexasError("LOCK_MISMATCH", f"{book} 6% profit drifted")
        if int(capital_books[book]["initial_full_position_contracts"]) != CAPITAL_6PCT_INITIAL_CONTRACTS[book]:
            raise ChoosinTexasError("LOCK_MISMATCH", f"{book} 6% size drifted")
    rows = load_rows()
    for book, expected in UNIT_BOOK_CENTS.items():
        if unit_book_cents(rows, book) != expected:
            raise ChoosinTexasError("LOCK_MISMATCH", f"{book} unit book drifted")
    return {
        "planned_risk_cap3": {
            "initial_contracts": dict(INITIAL_CONTRACTS),
            "through_close_pnl_cents": dict(REFERENCE_PNL_CENTS),
            "accepted": dict(REFERENCE_ACCEPTED),
            "starting_cash_cents": STARTING_CASH_CENTS,
        },
        "capital_6pct_cap3": {
            "initial_contracts": dict(CAPITAL_6PCT_INITIAL_CONTRACTS),
            "through_close_pnl_cents": dict(CAPITAL_6PCT_PNL_CENTS),
        },
        "unit_book_cents": dict(UNIT_BOOK_CENTS),
        "candidate_rows": len(rows),
    }


def _sport_roots() -> dict[str, dict[str, Path]]:
    base = repo_root() / "Backtesting Suite" / "Data"
    return {
        "NBA": {
            "candles": base / "NBA/2025-2026/warehouse/normalized/nba/candles_1m",
            "trades": base / "NBA/2025-2026/warehouse/normalized/nba/trades",
        },
        "NCAAB": {
            "candles": base / "NCAAB/2025-2026/warehouse/normalized/ncaab/candles_1m",
            "trades": base / "NCAAB/2025-2026/warehouse/normalized/ncaab/trades",
        },
    }


def _index(directory: Path) -> dict[str, Path]:
    if not directory.is_dir():
        raise ChoosinTexasError("DATA_REQUIRED", f"missing {directory}")
    found: dict[str, Path] = {}
    for path in directory.rglob("*.parquet"):
        if path.stem in found:
            raise ChoosinTexasError("LOCK_MISMATCH", f"duplicate market file {path.stem}")
        found[path.stem] = path
    return found


def _candle_at(path: Path, ts: int) -> dict[str, Any] | None:
    table = pq.read_table(path, columns=CANDLE_COLUMNS, filters=[("end_period_ts", "=", int(ts))])
    if table.num_rows == 0:
        return None
    if table.num_rows != 1:
        raise ChoosinTexasError("LOCK_MISMATCH", f"{path.name} has more than one candle at {ts}")
    return {name: table.column(name)[0].as_py() for name in CANDLE_COLUMNS}


def _trades_after(path: Path | None, signal_ts: int, limit_cents: int) -> dict[str, Any]:
    if path is None:
        return {
            "trade_file": "MISSING",
            "trades_at_limit_after_signal": None,
            "quantity_hundredths_at_limit_after_signal": None,
        }
    table = pq.read_table(path, columns=TRADE_COLUMNS)
    signal = datetime.fromtimestamp(int(signal_ts), tz=timezone.utc)
    count = 0
    quantity = 0
    for i in range(table.num_rows):
        stamp = table.column("timestamp")[i].as_py()
        if stamp is None or stamp <= signal:
            continue
        price = e4_to_cents(table.column("yes_price_e4")[i].as_py())
        if price != int(limit_cents):
            continue
        count += 1
        raw_qty = table.column("quantity_hundredths")[i].as_py()
        if raw_qty is not None:
            quantity += int(raw_qty)
    return {
        "trade_file": "PRESENT",
        "trades_at_limit_after_signal": count,
        "quantity_hundredths_at_limit_after_signal": quantity,
        "queue_position": None,
        "note": "Public trades after the close are observed. They are not our fills.",
    }


def _quote_fields(row: dict[str, Any] | None) -> dict[str, Any]:
    if row is None:
        return {
            "candle": "MISSING",
            "bid_cents": None,
            "ask_cents": None,
            "depth_available": False,
            "sequence_known": False,
            "source": None,
            "market_data_type": None,
            "ingested_at": None,
        }
    return {
        "candle": "PRESENT",
        "bid_cents": e4_to_cents(row["yes_bid_close_e4"]),
        "ask_cents": e4_to_cents(row["yes_ask_close_e4"]),
        "depth_available": bool(row["orderbook_depth_available"]),
        "sequence_known": False,
        "source": row["source"],
        "market_data_type": row["market_data_type"],
        "ingested_at": row["ingested_at"].isoformat() if row["ingested_at"] is not None else None,
    }


def diagnose_position(
    position: dict[str, Any],
    *,
    candle_path: Path | None,
    trade_path: Path | None,
) -> dict[str, Any]:
    book = str(position["strategy"])
    stop = 40 if book == "80/40" else 65
    entry_ts = int(position["entry_ts"])
    exit_ts = int(position["exit_ts"])
    entry_candle = _candle_at(candle_path, entry_ts) if candle_path else None
    entry_quote = _quote_fields(entry_candle)
    if entry_quote["bid_cents"] is not None and int(entry_quote["bid_cents"]) < 80:
        raise ChoosinTexasError(
            "LOCK_MISMATCH",
            f"{position['ticker']} entry candle bid is below 80",
        )
    entry_class = classify_buy_limit(
        limit_cents=80,
        bid_cents=entry_quote["bid_cents"],
        ask_cents=entry_quote["ask_cents"],
        depth_available=bool(entry_quote["depth_available"]),
        sequence_known=False,
        queue_position=None,
    )
    entry_trades = _trades_after(trade_path, entry_ts, 80)
    exit_type = str(position["exit_type"])
    if exit_type == "SETTLEMENT_YES":
        exit_body: dict[str, Any] = {
            "kind": "SETTLEMENT_BENCHMARK",
            "evidence_level": "CANDLE_PATH_NOT_FILL",
            "quote_relation": "NO_EXIT_ORDER",
            "modeled_filled_contracts": None,
            "fill_label": None,
            "reason": "The survivor mark at 100 cents is the candle benchmark. It is not an exchange fill of our order.",
        }
        exit_quote = {"candle": "NOT_AN_EXIT_ORDER"}
    else:
        exit_candle = _candle_at(candle_path, exit_ts) if candle_path else None
        exit_quote = _quote_fields(exit_candle)
        if exit_quote["bid_cents"] is not None and int(exit_quote["bid_cents"]) != int(position["through_close_cents"]):
            raise ChoosinTexasError(
                "LOCK_MISMATCH",
                f"{position['ticker']} exit candle bid does not match the benchmark close",
            )
        exit_body = classify_sell_limit(
            limit_cents=stop,
            bid_cents=exit_quote["bid_cents"],
            ask_cents=exit_quote["ask_cents"],
            depth_available=bool(exit_quote["depth_available"]),
            sequence_known=False,
            queue_position=None,
            taker_fallback="NOT_AUTHORIZED",
        )
        exit_body["kind"] = "STOP_DETECTION_THEN_HYPOTHETICAL_SELL"
        exit_body["stop_cents"] = stop
        exit_body["detection_is_not_an_order"] = True
        exit_body["trades_after_signal"] = _trades_after(trade_path, exit_ts, stop)
    if entry_class["modeled_filled_contracts"] is not None or exit_body["modeled_filled_contracts"] is not None:
        raise ChoosinTexasError("LOCK_MISMATCH", f"{position['ticker']} diagnostic invented a fill")
    bid = entry_quote["bid_cents"]
    return {
        "strategy": book,
        "configuration_id": position["configuration_id"],
        "event_id": position["event_id"],
        "instrument": position["ticker"],
        "signal_ts": entry_ts,
        "hypothetical_arrival_ts": entry_ts,
        "reference": "CANDLE_PATH_NOT_FILL",
        "entry": {
            "quote": entry_quote,
            "classification": entry_class,
            "nominal_limit_cents": 80,
            "candle_bid_minus_nominal_cents": None if bid is None else int(bid) - 80,
            "trades": entry_trades,
            "contracts_requested": int(position["contracts"]),
            "modeled_filled_contracts": None,
        },
        "exit": exit_body,
        "exit_quote": exit_quote,
        "benchmark_exit_cents": int(position["through_close_cents"]),
        "benchmark_pnl_cents": int(position["realized_pnl_cents"]),
        "execution_adjustment_cents": None,
        "gap_recharged": False,
        "fees": "FEES_UNAVAILABLE",
        "actual_fill": None,
    }


def _gap_sort(item: tuple[str, int]) -> tuple[int, int]:
    if item[0] == "MISSING":
        return (1, 0)
    return (0, int(item[0]))


def _tally(rows: list[dict[str, Any]]) -> dict[str, Any]:
    entry_relations: Counter[str] = Counter()
    exit_relations: Counter[str] = Counter()
    bid_gaps: Counter[str] = Counter()
    missing_entry_candle = 0
    missing_trade_file = 0
    depth_rows = 0
    unresolved = 0
    ingest_lags: list[int] = []
    for row in rows:
        entry_relations[row["entry"]["classification"]["quote_relation"]] += 1
        exit_relations[row["exit"]["quote_relation"]] += 1
        gap = row["entry"]["candle_bid_minus_nominal_cents"]
        bid_gaps["MISSING" if gap is None else str(gap)] += 1
        quote = row["entry"]["quote"]
        if quote["candle"] != "PRESENT":
            missing_entry_candle += 1
        if row["entry"]["trades"]["trade_file"] != "PRESENT":
            missing_trade_file += 1
        if quote["depth_available"]:
            depth_rows += 1
        if row["entry"]["modeled_filled_contracts"] is None:
            unresolved += 1
        ingested = quote.get("ingested_at")
        if ingested:
            ingest_lags.append(int(datetime.fromisoformat(ingested).timestamp()) - int(row["signal_ts"]))
    return {
        "events": len(rows),
        "unresolved_events": unresolved,
        "partial_fills_modeled": 0,
        "stop_signals_without_a_fill": sum(1 for row in rows if row["exit"]["quote_relation"] != "NO_EXIT_ORDER"),
        "settlement_benchmarks": sum(1 for row in rows if row["exit"]["quote_relation"] == "NO_EXIT_ORDER"),
        "missing_entry_candle": missing_entry_candle,
        "missing_trade_file": missing_trade_file,
        "depth_available_entry_rows": depth_rows,
        "sequence_numbers_present": 0,
        "entry_quote_relations": dict(sorted(entry_relations.items())),
        "exit_quote_relations": dict(sorted(exit_relations.items())),
        "entry_bid_minus_nominal_80": dict(sorted(bid_gaps.items(), key=_gap_sort)),
        "backfill_ingest_minus_candle_end_seconds": {
            "min": min(ingest_lags) if ingest_lags else None,
            "max": max(ingest_lags) if ingest_lags else None,
            "meaning": "File ingest clock minus the candle end. Not a game-time receive lag.",
        },
    }


def build_execution_validation(dest: Path | None = None) -> dict[str, Any]:
    baseline = verify_baseline()
    roots = _sport_roots()
    candles = {sport: _index(paths["candles"]) for sport, paths in roots.items()}
    trades = {sport: _index(paths["trades"]) for sport, paths in roots.items()}
    audit = repo_root() / "research" / "choosin_texas" / "paired_replay" / "audit"
    books: dict[str, Any] = {}
    coverage_files = {"candle_files_indexed": {}, "trade_files_indexed": {}}
    for sport in ("NBA", "NCAAB"):
        coverage_files["candle_files_indexed"][sport] = len(candles[sport])
        coverage_files["trade_files_indexed"][sport] = len(trades[sport])
    for book in ("80/40", "80/65"):
        positions = json.loads((audit / book.replace("/", "_") / "open_3" / "positions.json").read_text(encoding="utf-8"))
        if len(positions) != REFERENCE_ACCEPTED[book]:
            raise ChoosinTexasError("LOCK_MISMATCH", f"{book} audit positions {len(positions)}")
        pnl = sum(int(row["realized_pnl_cents"]) for row in positions)
        if pnl != REFERENCE_PNL_CENTS[book]:
            raise ChoosinTexasError("LOCK_MISMATCH", f"{book} audit P&L {pnl} != {REFERENCE_PNL_CENTS[book]}")
        diagnosed = []
        for position in positions:
            if position["configuration_id"] != CONFIGURATION_ID:
                raise ChoosinTexasError("LOCK_MISMATCH", f"{position['event_id']} is not PLANNED_RISK_CAP3")
            ticker = str(position["ticker"])
            if ticker.startswith("KXNBAGAME"):
                sport = "NBA"
            elif ticker.startswith("KXNCAAMBGAME"):
                sport = "NCAAB"
            else:
                raise ChoosinTexasError("LOCK_MISMATCH", f"unexpected series {ticker}")
            diagnosed.append(
                diagnose_position(
                    position,
                    candle_path=candles[sport].get(ticker),
                    trade_path=trades[sport].get(ticker),
                )
            )
        first = min(positions, key=lambda row: (int(row["entry_ts"]), row["event_id"]))
        if int(first["contracts"]) != INITIAL_CONTRACTS[book]:
            raise ChoosinTexasError("LOCK_MISMATCH", f"{book} first position is not the initial size")
        books[book] = {
            "accepted": len(diagnosed),
            "benchmark_pnl_cents": pnl,
            "initial_contracts": INITIAL_CONTRACTS[book],
            "diagnostics": _tally(diagnosed),
            "rows": diagnosed,
        }
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    vital_nba = repo_root() / "research" / "vital" / "bots" / "nba-001" / "execution"
    summary = {
        "page": "paired_execution_validation",
        "spec_id": SPEC_ID,
        "configuration_id": CONFIGURATION_ID,
        "separate_configuration_id": "CAPITAL_6PCT_CAP3",
        "generated_at": generated_at,
        "live_execution": "LIVE_EXECUTION_DISABLED",
        "submits": False,
        "reference_evidence": "CANDLE_PATH_NOT_FILL",
        "simulated_evidence": "SIMULATED_EXECUTION",
        "actual_evidence": "ACTUAL_FILL",
        "actual_fills": 0,
        "out_of_sample": False,
        "execution_aware_portfolio_pnl": "NOT_REPORTED",
        "comparison_status": "NOT_COMPARABLE",
        "comparison_reason": (
            "Every accepted event lacks depth, queue position, and sequence numbers. "
            "A maker fill is not established, so no execution-aware portfolio P&L is reported."
        ),
        "baseline": baseline,
        "specification": specification(),
        "fees": historical_fee_status(),
        "coverage": {
            **coverage_files,
            "order_book_depth_snapshots": "UNAVAILABLE",
            "order_book_deltas": "UNAVAILABLE",
            "feed_sequence_numbers": "UNAVAILABLE",
            "game_time_local_receive_timestamps": "UNAVAILABLE",
            "exchange_trade_timestamps": "PRESENT_ON_PUBLIC_TRADES",
            "trade_timestamp_precision": "millisecond datetime on the public-trade timestamp field",
            "candle_timestamp_precision": "unix second at the one-minute period end",
            "candle_quote": "yes bid and yes ask open/high/low/close for the minute. No size.",
            "public_trades": "price, quantity_hundredths, taker side. No bid or ask resting at the print.",
            "provenance": "historical_rest backfill. ingested_at is the collection clock, not a game-time receive time.",
            "point_in_time_order_book": "UNAVAILABLE",
            "actual_order_records": "UNAVAILABLE" if not vital_nba.is_dir() else "PRESENT_UNEXPECTED",
            "mlb_execution_ledger_not_used": True,
        },
        "prospective_collector": {
            "status": "NOT_CONFIGURED",
            "submits": False,
            "credentials_read": False,
            "websocket": "NOT_STARTED",
            "observations_collected": 0,
            "spec_frozen_at": generated_at,
            "note": "The specification is timestamped before any prospective capture. No capture is running.",
        },
        "attribution": {
            "gap_recharged": False,
            "entry_price_component": "REPORTED_AS_CANDLE_BID_MINUS_NOMINAL_80",
            "exit_execution_component": "NOT_SEPARATED",
            "fee_component": "FEES_UNAVAILABLE",
            "admission_changes": "NOT_RUN",
            "note": "The through-close gap remains inside the candle benchmark. It is not subtracted again.",
        },
        "books": {
            book: {
                "accepted": body["accepted"],
                "benchmark_pnl_cents": body["benchmark_pnl_cents"],
                "initial_contracts": body["initial_contracts"],
                "diagnostics": body["diagnostics"],
                "example_event_id": body["rows"][0]["event_id"],
                "example_entry_relation": body["rows"][0]["entry"]["classification"]["quote_relation"],
                "example_entry_bid_minus_nominal_cents": body["rows"][0]["entry"]["candle_bid_minus_nominal_cents"],
            }
            for book, body in books.items()
        },
    }
    if summary["coverage"]["actual_order_records"] != "UNAVAILABLE":
        raise ChoosinTexasError("LOCK_MISMATCH", "an NBA execution ledger appeared; it was not reviewed")
    target = dest or artifact_dir()
    target.mkdir(parents=True, exist_ok=True)
    _write_json(target / "specification.json", specification())
    _write_json(target / "source_manifest.json", summary["coverage"])
    for book, body in books.items():
        _write_json(target / f"diagnostics_{book.replace('/', '_')}.json", body["rows"])
    _write_json(target / "summary.json", summary)
    (target / "SPEC.md").write_text(_spec_markdown(summary), encoding="utf-8")
    prospective = target / "prospective"
    prospective.mkdir(exist_ok=True)
    (prospective / "STATUS.txt").write_text(
        "NOT_CONFIGURED\nsubmits=false\ncredentials_read=false\nwebsocket=NOT_STARTED\nobservations_collected=0\n",
        encoding="utf-8",
    )
    return summary


def _write_json(path: Path, body: Any) -> None:
    path.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")


def _spec_markdown(summary: dict[str, Any]) -> str:
    spec = summary["specification"]
    lines = [
        f"# {spec['spec_id']}",
        "",
        f"Frozen at {summary['generated_at']}. Configuration `{summary['configuration_id']}`.",
        "This file is research. It does not arm a book.",
        "",
        "## Established",
        "",
    ]
    for item in spec["established"]:
        lines.append(f"- {item['name']}: {item['value']}")
    lines.extend(["", "## Missing", ""])
    for item in spec["missing"]:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "Canonical net return: NOT_PUBLISHED.",
            "Execution-aware portfolio P&L: NOT_REPORTED.",
            "Reference label: CANDLE_PATH_NOT_FILL.",
            "",
        ]
    )
    return "\n".join(lines)
