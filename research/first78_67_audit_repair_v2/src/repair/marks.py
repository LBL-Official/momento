"""One-minute grid. Missing bids stay missing."""

from __future__ import annotations

from repair.inference import account_returns, max_drawdown_fraction


def minute_grid(
    events: list[dict],
    positions: list[dict],
    paths: dict[str, list[tuple[int, int]]],
    start_ts: int,
    end_ts: int,
    *,
    stale_seconds: int = 60,
    initial_cash: int = 2_000_000,
) -> list[dict]:
    ordered = sorted(events, key=lambda row: int(row["ts"]))
    by_id = {pos["trade_id"]: pos for pos in positions}
    quotes = {key: sorted(value) for key, value in paths.items()}
    cursors = {key: 0 for key in quotes}
    last_quote: dict[str, tuple[int, int] | None] = {key: None for key in quotes}
    cursor = 0
    cash = initial_cash
    receivable = 0
    live: dict[str, dict] = {}
    rows = []
    ts = int(start_ts)
    end_ts = int(end_ts)
    while ts <= end_ts:
        while cursor < len(ordered) and int(ordered[cursor]["ts"]) <= ts:
            row = ordered[cursor]
            cash = int(row["cash_cents"])
            receivable = int(row["receivable_cents"])
            if row["kind"] == "entry" and row.get("trade_id") in by_id:
                live[row["trade_id"]] = by_id[row["trade_id"]]
            elif row["kind"] == "exit":
                live.pop(row.get("trade_id"), None)
            cursor += 1
        marks = []
        missing = False
        valued = cash + receivable
        for pos in live.values():
            series = quotes.get(pos["contract_id"], [])
            index = cursors.get(pos["contract_id"], 0)
            while index < len(series) and int(series[index][0]) <= ts:
                last_quote[pos["contract_id"]] = (int(series[index][0]), int(series[index][1]))
                index += 1
            cursors[pos["contract_id"]] = index
            quote = last_quote.get(pos["contract_id"])
            if quote is None:
                missing = True
                marks.append({"contract_id": pos["contract_id"], "status": "MISSING", "reason": "NO_QUOTE_AT_OR_BEFORE_MARK"})
                continue
            qts, bid = quote
            age = ts - qts
            marks.append(
                {
                    "contract_id": pos["contract_id"],
                    "quote_ts": qts,
                    "age_seconds": age,
                    "stale": age > stale_seconds,
                    "source": "YES_BID_CLOSE",
                    "bid_cents": bid,
                    "status": "STALE" if age > stale_seconds else "OBSERVED",
                }
            )
            valued += int(pos["contracts"]) * bid
        rows.append(
            {
                "ts": ts,
                "cash_cents": cash,
                "receivable_cents": receivable,
                "realized_equity_cents": cash + receivable,
                "marked_equity_cents": None if missing and live else valued,
                "mark_status": "MISSING" if missing and live else ("EMPTY" if not live else "BID_CLOSE"),
                "open_count": len(live),
            }
        )
        ts += 60
    return rows


def drawdown_report(events: list[dict], grid: list[dict], initial: int = 2_000_000) -> dict:
    realized = [initial] + [int(row["realized_equity_cents"]) for row in events]
    event_valued = [initial] + [int(row["valued_equity_cents"]) for row in events]
    marked = [int(row["marked_equity_cents"]) for row in grid if row.get("marked_equity_cents") is not None]
    return {
        "realized_accounting_drawdown": max_drawdown_fraction(realized),
        "event_valued_drawdown": max_drawdown_fraction(event_valued),
        "full_grid_marked_drawdown": max_drawdown_fraction([initial] + marked) if marked else None,
        "missing_mark_rows": sum(1 for row in grid if row["mark_status"] == "MISSING"),
        "grid_rows": len(grid),
        "carried_bid_diagnostic": "not used as the marked series",
    }


def daily_from_events(events: list[dict], days: list[str], initial: int = 2_000_000) -> list[dict]:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    la = ZoneInfo("America/Los_Angeles")
    rows = []
    equity = initial
    for day in days:
        end = int(datetime.fromisoformat(day + "T00:00:00").replace(tzinfo=la).timestamp()) + 86400 - 1
        # local end of day via the next midnight minus one second, DST-safe
        nxt = datetime.fromisoformat(day + "T00:00:00").replace(tzinfo=la)
        from datetime import timedelta

        end = int((nxt + timedelta(days=1)).timestamp()) - 1
        seen = [row for row in events if int(row["ts"]) <= end]
        if seen:
            equity = int(seen[-1]["realized_equity_cents"])
        rows.append({"local_day": day, "realized_equity_cents": equity})
    returns = account_returns([initial] + [row["realized_equity_cents"] for row in rows])
    for row, ret in zip(rows, returns):
        row["account_return"] = ret
    return rows
