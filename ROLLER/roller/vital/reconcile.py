"""Reconcile MLB 001 fills and trades. Idempotent. Does not submit."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from roller.jump.dashboard.ledger import (
    _checked_add,
    _checked_sub,
    _fill_market,
    _fill_side,
    _positions,
    _qty,
    _strategy_id,
    last_fill_utc,
    money_cents,
    parse_utc,
    position_is_open,
    realized_from_position,
    MLB_STRATEGY_ID,
)
from roller.vital.aws import load_local_runtime, load_local_snapshot

RESEARCH_ITI_STRATEGY_ID = 3
from roller.vital.bots import get_bot
from roller.vital.execution import (
    FILL_FACT_KEYS,
    SOURCE_HOST,
    TRADE_CLOSED,
    TRADE_FACT_KEYS,
    TRADE_OPEN,
    TRADE_PARTIAL,
    catalog_source,
    fact,
    fact_value,
    facts_equal,
    fill_identity,
    is_confirmed,
    trade_identity,
    unwrap_id,
    vwap_cents,
)
from roller.vital.honesty import observation_unavailable, unavailable
from roller.vital.mlb_001.kalshi_observe import kalshi_status
from roller.vital.mlb_001.settlement import observe_settlements
from roller.vital.mlb_001.ticker_trades import reconstruct_ticker_trades
from roller.vital.mlb_001.trade_row import (
    apply_standard_row,
    identity_maps,
    resolve_identity_ticker,
)
from roller.vital.models import resolve_bot_id, utc_now
from roller.vital.store import (
    append_event,
    append_jsonl,
    execution_fills_path,
    execution_observed_path,
    execution_trades_path,
    load_execution_fills,
    load_execution_trades,
    write_json,
)
from roller.vital.versions import BOT_ID

_CATALOG_BOTS = {BOT_ID, "mlb-bot-one", "UNATTRIBUTED"}


def _iso(ts: datetime | None) -> str | None:
    if ts is None:
        return None
    return ts.strftime("%Y-%m-%dT%H:%M:%SZ")


def _sum_ints(values: list[int | None]) -> int | None:
    if not values:
        return None
    if any(item is None for item in values):
        return None
    total = 0
    for item in values:
        nxt = _checked_add(total, int(item))
        if nxt is None:
            return None
        total = nxt
    return total


def _stamp(items: list[dict[str, Any]], *, how: str) -> datetime | None:
    stamps = [row["ts"] for row in items]
    if not stamps or any(item is None for item in stamps):
        return None
    return min(stamps) if how == "min" else max(stamps)


def coalesce_fills(*groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per fill_id / venue_fill_id. Disk + catalog must not double-count."""
    by_id: dict[str, dict[str, Any]] = {}
    by_venue: dict[str, dict[str, Any]] = {}
    for group in groups:
        for row in group:
            if not isinstance(row, dict):
                continue
            venue = str(row.get("venue_fill_id") or "").strip()
            fid = str(row.get("fill_id") or "").strip()
            current = by_id.get(fid) if fid else None
            if current is None and venue:
                current = by_venue.get(venue)
            if current is None:
                key = fid or venue
                if not key:
                    continue
                by_id[key] = row
                if venue:
                    by_venue[venue] = row
                continue
            merged = merge_fill(current, row)
            keep = str(merged.get("fill_id") or fid or venue)
            by_id[keep] = merged
            if merged.get("venue_fill_id"):
                by_venue[str(merged["venue_fill_id"])] = merged
    return list(by_id.values())


def _prefer_fact(base: dict[str, Any], extra: dict[str, Any], key: str) -> Any:
    if is_confirmed(base.get(key)):
        return base.get(key)
    if is_confirmed(extra.get(key)):
        return extra.get(key)
    return extra.get(key) if extra.get(key) is not None else base.get(key)


def merge_fill(base: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key in FILL_FACT_KEYS:
        if key in {"source", "sources", "observation_status", "bot_id"}:
            continue
        out[key] = _prefer_fact(base, extra, key)
    sources: list[str] = []
    for raw in list(base.get("sources") or [base.get("source")]) + list(extra.get("sources") or [extra.get("source")]):
        token = str(raw or "").strip()
        if token and token not in sources:
            sources.append(token)
    out["sources"] = sources
    if SOURCE_HOST in sources:
        out["source"] = SOURCE_HOST
    elif extra.get("source"):
        out["source"] = extra.get("source")
    else:
        out["source"] = base.get("source")
    out["observation_status"] = "CONFIRMED"
    out["fill_id"] = base.get("fill_id") or extra.get("fill_id")
    out["venue_fill_id"] = base.get("venue_fill_id") or extra.get("venue_fill_id")
    out["bot_id"] = base.get("bot_id") or extra.get("bot_id")
    return out


def normalize_host_fill(bot_id: str, position: dict[str, Any], fill: dict[str, Any], seq: int) -> dict[str, Any] | None:
    if not isinstance(fill, dict):
        return None
    ts = parse_utc(fill.get("exchange_ts"))
    venue = unwrap_id(fill.get("venue_fill_id")) or unwrap_id(fill.get("fill_id"))
    qty = _qty(fill.get("quantity")) if fill.get("quantity") is not None else _qty(fill.get("qty"))
    price = money_cents(fill.get("price"))
    premium = money_cents(fill.get("premium"))
    fee = fill.get("fee") if isinstance(fill.get("fee"), dict) else {}
    fee_amt = money_cents(fee.get("amount")) if fee else None
    if price is None and qty and qty > 0 and premium is not None and premium % qty == 0:
        price = premium // qty
    if premium is None and qty is not None and price is not None:
        premium = qty * price
    pid = unwrap_id(position.get("id")) or unwrap_id(position.get("position_id"))
    market = _fill_market(position, fill)
    fallback = "|".join(
        [
            str(pid or ""),
            _iso(ts) or "",
            str(qty if qty is not None else ""),
            str(price if price is not None else ""),
            str(premium if premium is not None else ""),
            str(seq),
        ]
    )
    return {
        "fill_id": fill_identity(venue_id=venue, source=SOURCE_HOST, fallback=fallback),
        "bot_id": bot_id,
        "position_id": fact(pid),
        "event_ticker": fact(market),
        "market": fact(market),
        "side": fact(_fill_side(fill) or unwrap_id(position.get("side"))),
        "timestamp": fact(_iso(ts)),
        "price_cents": fact(price),
        "contracts": fact(qty),
        "amount_cents": fact(premium),
        "fee_cents": fact(fee_amt),
        "fee_kind": fact(str(fee.get("kind") or "") or None),
        "venue_fill_id": venue,
        "order_id": fact(unwrap_id(fill.get("order_id")) or unwrap_id(fill.get("venue_order_id"))),
        "source": SOURCE_HOST,
        "sources": [SOURCE_HOST],
        "observation_status": "CONFIRMED",
        "rev": 0,
    }


def normalize_catalog_fill(bot_id: str, row: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(row, dict):
        return None
    env = str(row.get("environment") or "").strip().upper()
    if env and env != "PRODUCTION":
        return None
    owner = str(row.get("bot_id") or "").strip()
    if owner and owner not in _CATALOG_BOTS:
        return None
    venue = str(row.get("kalshi_fill_id") or row.get("kalshi_trade_id") or "").strip() or None
    qty = row.get("qty")
    try:
        qty = int(qty) if qty is not None and not isinstance(qty, bool) else None
    except (TypeError, ValueError):
        qty = None
    price = row.get("yes_price_cents")
    try:
        price = int(price) if price is not None and not isinstance(price, bool) else None
    except (TypeError, ValueError):
        price = None
    premium = row.get("premium_cents")
    try:
        premium = int(premium) if premium is not None and not isinstance(premium, bool) else None
    except (TypeError, ValueError):
        premium = None
    if premium is None and qty is not None and price is not None:
        premium = qty * price
    ticker = str(row.get("ticker") or "").strip() or None
    source = catalog_source(row.get("source"))
    fallback = str(row.get("jump_trade_id") or "").strip() or None
    ts = parse_utc(row.get("exchange_ts"))
    return {
        "fill_id": fill_identity(venue_id=venue, source=source, fallback=fallback),
        "bot_id": bot_id,
        "position_id": observation_unavailable("catalog has no position_id"),
        "event_ticker": fact(ticker),
        "market": fact(ticker),
        "side": fact(row.get("side")),
        "timestamp": fact(_iso(ts)),
        "price_cents": fact(price),
        "contracts": fact(qty),
        "amount_cents": fact(premium),
        "fee_cents": unavailable("UNAVAILABLE"),
        "fee_kind": fact(row.get("fee_kind")),
        "venue_fill_id": venue,
        "order_id": fact(row.get("order_id")),
        "source": source,
        "sources": [source],
        "observation_status": "CONFIRMED",
        "rev": 0,
    }


def reconstruct_trade(
    bot_id: str,
    position: dict[str, Any],
    *,
    snapshot: dict[str, Any] | None = None,
    history: list[dict[str, Any]] | None = None,
    identity: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    sid = _strategy_id(position.get("strategy_id"))
    if sid not in {MLB_STRATEGY_ID, RESEARCH_ITI_STRATEGY_ID}:
        return None
    fills = position.get("fill_history") or []
    if not isinstance(fills, list):
        return None
    if not fills and money_cents(position.get("settlement_proceeds")) is None:
        return None
    pid = unwrap_id(position.get("id")) or unwrap_id(position.get("position_id"))
    if not pid:
        first = fills[0] if fills and isinstance(fills[0], dict) else {}
        pid = "|".join(
            [
                "synthetic",
                str(_fill_market(position, first) or ""),
                _iso(parse_utc(first.get("exchange_ts")) if isinstance(first, dict) else None) or "",
                str(len(fills)),
            ]
        )
    entries: list[dict[str, Any]] = []
    exits: list[dict[str, Any]] = []
    for fill in fills:
        if not isinstance(fill, dict):
            continue
        fee = fill.get("fee") if isinstance(fill.get("fee"), dict) else {}
        kind = str(fee.get("kind") or "")
        qty = _qty(fill.get("quantity")) if fill.get("quantity") is not None else _qty(fill.get("qty"))
        row = {
            "premium": money_cents(fill.get("premium")),
            "qty": qty,
            "ts": parse_utc(fill.get("exchange_ts")),
            "fee": money_cents(fee.get("amount")) if fee else None,
            "kind": kind,
        }
        if kind == "Liquidation":
            exits.append(row)
        elif kind in {"Entry", ""}:
            entries.append(row)
    entry_amount = _sum_ints([row["premium"] for row in entries]) if entries else None
    entry_qty = _sum_ints([row["qty"] for row in entries]) if entries else None
    exit_prem = _sum_ints([row["premium"] for row in exits]) if exits else None
    exit_qty = _sum_ints([row["qty"] for row in exits]) if exits else None
    settlement = money_cents(position.get("settlement_proceeds"))
    lifecycle = str(position.get("lifecycle") or "")
    filled = _qty(position.get("filled_quantity"))
    open_pos = position_is_open(position)
    if lifecycle in {"Settled", "Flat"} or (filled == 0 and (exits or settlement is not None)):
        status = TRADE_CLOSED
    elif open_pos and exits:
        status = TRADE_PARTIAL
    else:
        status = TRADE_OPEN

    if status == TRADE_CLOSED:
        if settlement is not None and exits:
            exit_amount = _checked_add(exit_prem, settlement) if exit_prem is not None else None
        elif settlement is not None:
            exit_amount = settlement
        else:
            exit_amount = exit_prem
        exit_contracts = entry_qty if settlement is not None and not exits else exit_qty
        exit_date = _stamp(exits, how="max") if exits else last_fill_utc(position)
        exit_price = (
            vwap_cents(settlement, exit_contracts)
            if settlement is not None and not exits
            else vwap_cents(exit_prem, exit_qty)
        )
        exit_wrap = {
            "exit_date": fact(_iso(exit_date)),
            "exit_amount": fact(exit_amount),
            "exit_price": fact(exit_price),
            "exit_contracts": fact(exit_contracts),
        }
    elif status == TRADE_PARTIAL:
        exit_wrap = {
            "exit_date": fact(_iso(_stamp(exits, how="max"))),
            "exit_amount": fact(exit_prem),
            "exit_price": fact(vwap_cents(exit_prem, exit_qty)),
            "exit_contracts": fact(exit_qty),
        }
    else:
        exit_wrap = {
            "exit_date": unavailable("UNAVAILABLE"),
            "exit_amount": unavailable("UNAVAILABLE"),
            "exit_price": unavailable("UNAVAILABLE"),
            "exit_contracts": unavailable("UNAVAILABLE"),
        }

    fee_values = [row["fee"] for row in entries + exits]
    if entries + exits and all(item is not None for item in fee_values):
        fee_total = _sum_ints(fee_values)
        net = realized_from_position(position)
        fee_fact = fact(fee_total)
        net_fact = fact(net, missing="UNAVAILABLE")
    else:
        fee_fact = unavailable("UNAVAILABLE")
        net_fact = unavailable("UNAVAILABLE")

    gross = None
    if status == TRADE_CLOSED and entry_amount is not None:
        if settlement is not None and exits:
            if exit_prem is not None:
                credits = _checked_add(exit_prem, settlement)
                gross = _checked_sub(credits, entry_amount) if credits is not None else None
        elif settlement is not None:
            gross = _checked_sub(settlement, entry_amount)
        elif exit_prem is not None:
            gross = _checked_sub(exit_prem, entry_amount)

    market = None
    for fill in fills:
        if isinstance(fill, dict):
            market = _fill_market(position, fill)
            if market:
                break
    if not market:
        market = _fill_market(position, {})
    if not market:
        market = resolve_identity_ticker(position, identity)
    entry_date = _stamp(entries, how="min") if entries else last_fill_utc(position)
    trade = {
        "trade_id": trade_identity(bot_id, pid),
        "bot_id": bot_id,
        "position_id": pid,
        "event_ticker": fact(market),
        "market": fact(market),
        "status": status,
        "entry_date": fact(_iso(entry_date)),
        "entry_amount": fact(entry_amount),
        "entry_price": fact(vwap_cents(entry_amount, entry_qty)),
        "entry_contracts": fact(entry_qty),
        "gross_realized_cents": fact(gross, missing="UNAVAILABLE") if status == TRADE_CLOSED else unavailable("UNAVAILABLE"),
        "fee_cents": fee_fact,
        "net_realized_cents": net_fact if status == TRADE_CLOSED else unavailable("UNAVAILABLE"),
        "source": SOURCE_HOST,
        "observation_status": "CONFIRMED",
        "lifecycle": lifecycle or None,
        "rev": 0,
        **exit_wrap,
    }
    return apply_standard_row(trade, snapshot=snapshot, history=history)


def _read_catalog() -> dict[str, Any]:
    try:
        from roller.jump.catalog.store import load_trades, trades_path
    except Exception:
        return {"ok": False, "reason": "jump catalog unread", "rows": None, "source": "JUMP_CATALOG"}
    path = trades_path()
    if not path.is_file():
        return {"ok": False, "reason": "jump catalog absent", "rows": None, "source": "JUMP_CATALOG"}
    try:
        rows = load_trades()
    except Exception:
        return {"ok": False, "reason": "jump catalog unreadable", "rows": None, "source": "JUMP_CATALOG"}
    return {"ok": True, "reason": None, "rows": rows, "source": "JUMP_CATALOG"}


def _host_strategy_id(bot: dict[str, Any]) -> int:
    if str(bot.get("bot_id") or "") == BOT_ID or bot.get("kind") == "grandfathered":
        return MLB_STRATEGY_ID
    return RESEARCH_ITI_STRATEGY_ID


def _kalshi_layer(bot: dict[str, Any]) -> dict[str, Any]:
    if str(bot.get("bot_id") or "") == BOT_ID or bot.get("kind") == "grandfathered":
        return kalshi_status()
    attach = bot.get("attach") if isinstance(bot.get("attach"), dict) else {}
    demo = attach.get("kalshi_demo") if isinstance(attach.get("kalshi_demo"), dict) else {}
    if str(bot.get("environment") or "").upper() == "PRODUCTION":
        book = kalshi_status()
        return {
            "layer": "kalshi_observe",
            "read_only": True,
            "submits": False,
            "status": book.get("status") or "OBSERVATION_UNAVAILABLE",
            "detail": "ITI production book; not the MLB 001 ledger",
            "observed_at": book.get("observed_at"),
            "fill_n": None,
            "position_n": None,
            "demo_book": demo.get("status") or "OBSERVATION_UNAVAILABLE",
            "source": "isolated_unit",
            "post": "POST /vital/bots/{id}/kalshi/observe",
        }
    return {
        "layer": "kalshi_observe",
        "read_only": True,
        "submits": False,
        "status": demo.get("status") or "OBSERVATION_UNAVAILABLE",
        "detail": "ITI ledger does not read the MLB 001 Kalshi book",
        "observed_at": None,
        "fill_n": None,
        "position_n": None,
        "demo_book": demo.get("status") or "OBSERVATION_UNAVAILABLE",
        "source": "isolated_unit",
        "post": "POST /vital/bots/{id}/kalshi/observe",
    }


def _read_unit_runtime(bot: dict[str, Any]) -> dict[str, Any]:
    """Read this bot's live-runtime.json only. Never MLB 001's file."""
    from roller.jump.bots.demo_host import load_demo_host_state
    from roller.jump.bots.live_host import load_local_live_state

    ident = str(bot.get("bot_id") or "")
    local = load_local_live_state(ident)
    if not local.get("ok"):
        local = load_demo_host_state(ident)
    runtime = local.get("runtime") if isinstance(local.get("runtime"), dict) else None
    positions = _positions(runtime) if runtime is not None else None
    if local.get("ok") and runtime is not None and positions is not None:
        return {
            "ok": True,
            "reason": None,
            "runtime": runtime,
            "positions": positions,
            "snapshot": local.get("snapshot"),
            "source": SOURCE_HOST,
        }
    return {
        "ok": False,
        "reason": str(local.get("reason") or "unit live-runtime.json unread"),
        "runtime": None,
        "positions": None,
        "snapshot": local.get("snapshot") if isinstance(local, dict) else None,
        "source": SOURCE_HOST,
    }


def _inspect_runtime_presence() -> dict[str, Any]:
    """SSM/local inspect can confirm the host file exists without the fill body."""
    from roller.vital.aws import inspect_mlb_001

    inspect = inspect_mlb_001()
    paths = inspect.get("paths") if isinstance(inspect.get("paths"), dict) else {}
    ledger = inspect.get("ledger") if isinstance(inspect.get("ledger"), dict) else {}
    present = bool(paths.get("runtime_exists") or (isinstance(ledger, dict) and ledger.get("ok")))
    if present:
        return {
            "present": True,
            "source": inspect.get("source") or "inspect",
            "reason": "host live-runtime.json confirmed present; local fill body unread",
        }
    return {
        "present": False,
        "source": inspect.get("source") or "inspect",
        "reason": str(inspect.get("reason") or "host unread"),
    }


def _host_source(*, host_ok: bool, present: bool, reason: str | None) -> dict[str, Any]:
    return {
        "status": "CONFIRMED" if host_ok or present else "OBSERVATION_UNAVAILABLE",
        "fill_body": "CONFIRMED" if host_ok else "OBSERVATION_UNAVAILABLE",
        "detail": reason,
    }


def _read_host() -> dict[str, Any]:
    host = load_local_runtime()
    snapshot = host.get("snapshot") if isinstance(host.get("snapshot"), dict) else load_local_snapshot()
    if not host.get("ok"):
        presence = _inspect_runtime_presence()
        reason = str(host.get("reason") or "host unread")
        if presence.get("present"):
            reason = str(presence.get("reason") or reason)
        return {
            "ok": False,
            "present": bool(presence.get("present")),
            "reason": reason,
            "runtime": None,
            "positions": None,
            "snapshot": snapshot,
            "source": SOURCE_HOST,
        }
    runtime = host.get("runtime")
    if not isinstance(runtime, dict):
        return {
            "ok": False,
            "reason": "live-runtime.json unreadable",
            "runtime": None,
            "positions": None,
            "snapshot": snapshot,
            "source": SOURCE_HOST,
        }
    positions = _positions(runtime)
    if positions is None:
        return {
            "ok": False,
            "reason": "live-runtime tracker.positions unreadable",
            "runtime": runtime,
            "positions": None,
            "snapshot": snapshot,
            "source": SOURCE_HOST,
        }
    return {
        "ok": True,
        "present": True,
        "reason": None,
        "runtime": runtime,
        "positions": positions,
        "snapshot": snapshot,
        "source": SOURCE_HOST,
    }


def _bankroll_history() -> list[dict[str, Any]]:
    try:
        from roller.jump.catalog.store import load_bankroll_history
    except Exception:
        return []
    try:
        return load_bankroll_history()
    except Exception:
        return []


def _upsert_fill(
    bot_id: str,
    incoming: dict[str, Any],
    by_id: dict[str, dict[str, Any]],
    by_venue: dict[str, dict[str, Any]],
    *,
    root: Path | None,
) -> str:
    venue = str(incoming.get("venue_fill_id") or "").strip()
    current = by_id.get(str(incoming.get("fill_id") or ""))
    if current is None and venue:
        current = by_venue.get(venue)
        if current is not None:
            incoming = dict(incoming)
            incoming["fill_id"] = current["fill_id"]
    if current is None:
        incoming["rev"] = 0
        incoming["recorded_at"] = utc_now()
        append_jsonl(execution_fills_path(bot_id, root=root), incoming)
        by_id[incoming["fill_id"]] = incoming
        if venue:
            by_venue[venue] = incoming
        return "added"
    merged = merge_fill(current, incoming)
    if facts_equal(current, merged, FILL_FACT_KEYS):
        return "unchanged"
    merged["rev"] = int(current.get("rev") or 0) + 1
    merged["updated_at"] = utc_now()
    append_jsonl(execution_fills_path(bot_id, root=root), merged)
    by_id[merged["fill_id"]] = merged
    if merged.get("venue_fill_id"):
        by_venue[str(merged["venue_fill_id"])] = merged
    return "updated"


def _upsert_trade(
    bot_id: str,
    incoming: dict[str, Any],
    by_id: dict[str, dict[str, Any]],
    *,
    root: Path | None,
) -> str:
    current = by_id.get(incoming["trade_id"])
    if current is None:
        incoming["rev"] = 0
        incoming["recorded_at"] = utc_now()
        append_jsonl(execution_trades_path(bot_id, root=root), incoming)
        by_id[incoming["trade_id"]] = incoming
        return "opened" if incoming.get("status") != TRADE_CLOSED else "closed"
    if facts_equal(current, incoming, TRADE_FACT_KEYS):
        return "unchanged"
    incoming["rev"] = int(current.get("rev") or 0) + 1
    incoming["updated_at"] = utc_now()
    incoming["recorded_at"] = current.get("recorded_at") or utc_now()
    append_jsonl(execution_trades_path(bot_id, root=root), incoming)
    prev_status = current.get("status")
    by_id[incoming["trade_id"]] = incoming
    if prev_status != TRADE_CLOSED and incoming.get("status") == TRADE_CLOSED:
        return "closed"
    return "updated"


def _sort_fills(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda row: (str(fact_value(row.get("timestamp")) or ""), str(row.get("fill_id") or "")),
        reverse=True,
    )


def _measurable_trade(trade: dict[str, Any]) -> bool:
    if trade.get("status") not in {TRADE_OPEN, TRADE_PARTIAL}:
        return True
    keys = (
        "entry_amount",
        "entry_contracts",
        "entry_price",
        "amount_traded_cents",
        "entry_price_cents",
        "entry_contracts",
    )
    for key in keys:
        if is_confirmed(trade.get(key)) and fact_value(trade.get(key)) is not None:
            return True
    return False


def _sort_trades(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda row: (str(fact_value(row.get("entry_date")) or ""), str(row.get("trade_id") or "")),
        reverse=True,
    )


def _summary(trades: list[dict[str, Any]] | None, fills: list[dict[str, Any]] | None, *, trades_ok: bool, fills_ok: bool) -> dict[str, Any]:
    if not trades_ok:
        trade_n = observation_unavailable("trade history could not be read")
        open_n = observation_unavailable("trade history could not be read")
        closed_n = observation_unavailable("trade history could not be read")
    else:
        rows = trades or []
        trade_n = fact(len(rows))
        open_n = fact(sum(1 for row in rows if row.get("status") in {TRADE_OPEN, TRADE_PARTIAL}))
        closed_n = fact(sum(1 for row in rows if row.get("status") == TRADE_CLOSED))
    fill_n = fact(len(fills or [])) if fills_ok else observation_unavailable("fill history could not be read")
    return {
        "total_trades": trade_n,
        "open": open_n,
        "closed": closed_n,
        "total_fills": fill_n,
    }


def reconcile_bot(
    bot_id: str = BOT_ID,
    *,
    root: Path | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    bot = get_bot(bot_id, root=root)
    resolved = str(bot.get("bot_id") or resolve_bot_id(bot_id))
    host = _read_host() if resolved == BOT_ID or bot.get("kind") == "grandfathered" else _read_unit_runtime(bot)
    catalog = _read_catalog() if resolved == BOT_ID or bot.get("kind") == "grandfathered" else {
        "ok": False,
        "reason": "ITI ledger reads the isolated unit only",
        "rows": None,
        "source": "JUMP_CATALOG",
    }
    snapshot = host.get("snapshot") if isinstance(host.get("snapshot"), dict) else None
    bankroll_history = _bankroll_history()
    identity = identity_maps(host.get("runtime") if isinstance(host.get("runtime"), dict) else None)
    existing_fills = load_execution_fills(resolved, root=root)
    existing_trades = load_execution_trades(resolved, root=root)
    by_fill = {str(row.get("fill_id")): row for row in existing_fills if row.get("fill_id")}
    by_venue = {
        str(row.get("venue_fill_id")): row
        for row in existing_fills
        if row.get("venue_fill_id")
    }
    by_trade = {str(row.get("trade_id")): row for row in existing_trades if row.get("trade_id")}

    fills_added = 0
    fills_updated = 0
    trades_opened = 0
    trades_updated = 0
    trades_closed = 0
    incoming_fills: list[dict[str, Any]] = []
    incoming_trades: list[dict[str, Any]] = []

    if host.get("ok"):
        for position in host.get("positions") or []:
            if _strategy_id(position.get("strategy_id")) != _host_strategy_id(bot):
                continue
            fills_on_position = position.get("fill_history") or []
            if not isinstance(fills_on_position, list):
                continue
            for seq, fill in enumerate(fills_on_position):
                normalized = normalize_host_fill(resolved, position, fill, seq)
                if normalized:
                    incoming_fills.append(normalized)
            trade = reconstruct_trade(
                resolved,
                position,
                snapshot=snapshot,
                history=bankroll_history,
                identity=identity,
            )
            if trade:
                incoming_trades.append(trade)

    if catalog.get("ok"):
        for row in catalog.get("rows") or []:
            normalized = normalize_catalog_fill(resolved, row)
            if normalized:
                incoming_fills.append(normalized)

    host_trades_present = bool(host.get("ok")) or any(
        row.get("source") == SOURCE_HOST for row in list(by_trade.values()) + incoming_trades
    )
    if not host_trades_present:
        seed_fills = coalesce_fills(list(by_fill.values()), incoming_fills)
        tickers = [
            str(fact_value(row.get("market")) or "")
            for row in seed_fills
            if is_confirmed(row.get("market"))
        ]
        settlements = observe_settlements(resolved, tickers, root=root)
        incoming_trades.extend(
            reconstruct_ticker_trades(
                resolved,
                seed_fills,
                snapshot=snapshot,
                history=bankroll_history,
                settlements=settlements,
            )
        )

    if persist:
        for fill in incoming_fills:
            action = _upsert_fill(resolved, fill, by_fill, by_venue, root=root)
            if action == "added":
                fills_added += 1
                append_event(
                    resolved,
                    {
                        "kind": "fill_recorded",
                        "fill_id": fill.get("fill_id"),
                        "source": fill.get("source"),
                        "market": fact_value(fill.get("market")),
                    },
                    root=root,
                )
            elif action == "updated":
                fills_updated += 1
        for trade in incoming_trades:
            action = _upsert_trade(resolved, trade, by_trade, root=root)
            if action == "opened":
                trades_opened += 1
                append_event(resolved, {"kind": "trade_opened", "trade_id": trade["trade_id"], "status": trade.get("status")}, root=root)
            elif action == "updated":
                trades_updated += 1
                append_event(resolved, {"kind": "trade_updated", "trade_id": trade["trade_id"], "status": trade.get("status")}, root=root)
            elif action == "closed":
                trades_closed += 1
                append_event(resolved, {"kind": "trade_closed", "trade_id": trade["trade_id"], "status": TRADE_CLOSED}, root=root)
        if not host.get("ok"):
            for row in list(by_trade.values()):
                enriched = apply_standard_row(dict(row), snapshot=snapshot, history=bankroll_history)
                action = _upsert_trade(resolved, enriched, by_trade, root=root)
                if action == "updated":
                    trades_updated += 1
        observed = {
            "ts": utc_now(),
            "host": _host_source(
                host_ok=bool(host.get("ok")),
                present=bool(host.get("present")),
                reason=host.get("reason"),
            ),
            "catalog": {
                "status": "CONFIRMED" if catalog.get("ok") else "OBSERVATION_UNAVAILABLE",
                "detail": catalog.get("reason"),
            },
            "fills_added": fills_added,
            "fills_updated": fills_updated,
            "trades_opened": trades_opened,
            "trades_updated": trades_updated,
            "trades_closed": trades_closed,
        }
        write_json(execution_observed_path(resolved, root=root), observed)
        changed = fills_added + fills_updated + trades_opened + trades_updated + trades_closed
        if changed:
            append_event(
                resolved,
                {
                    "kind": "reconciliation_completed",
                    "fills_added": fills_added,
                    "trades_opened": trades_opened,
                    "trades_updated": trades_updated,
                    "trades_closed": trades_closed,
                    "host": observed["host"]["status"],
                    "catalog": observed["catalog"]["status"],
                },
                root=root,
            )
            append_event(
                resolved,
                {
                    "kind": "execution_observed",
                    "host": observed["host"]["status"],
                    "catalog": observed["catalog"]["status"],
                },
                root=root,
            )

    fills = _sort_fills(list(by_fill.values()) if persist else list(by_fill.values()) + incoming_fills)
    if not persist:
        # persist=False still needs a coherent view from this observation + disk
        merged_fills = {row["fill_id"]: row for row in existing_fills}
        for row in incoming_fills:
            venue = str(row.get("venue_fill_id") or "")
            current = merged_fills.get(row["fill_id"])
            if current is None and venue:
                for item in merged_fills.values():
                    if item.get("venue_fill_id") == venue:
                        current = item
                        break
            merged_fills[row["fill_id"] if current is None else current["fill_id"]] = (
                merge_fill(current, row) if current else row
            )
        fills = _sort_fills(list(merged_fills.values()))
        merged_trades = {row["trade_id"]: row for row in existing_trades}
        for row in incoming_trades:
            merged_trades[row["trade_id"]] = row
        trades_rows = _sort_trades(list(merged_trades.values()))
    else:
        fills = _sort_fills(list(by_fill.values()))
        trades_rows = _sort_trades(list(by_trade.values()))

    host_ok = bool(host.get("ok"))
    catalog_ok = bool(catalog.get("ok"))
    if host_ok:
        trades_status = "CONFIRMED"
        trades: list[dict[str, Any]] | None = trades_rows
    elif trades_rows:
        trades_status = "CONFIRMED"
        trades = trades_rows
    else:
        trades_status = "OBSERVATION_UNAVAILABLE"
        trades = None

    if host_ok or catalog_ok:
        fills_status = "CONFIRMED"
        fills_out: list[dict[str, Any]] | None = fills
    elif existing_fills:
        fills_status = "CONFIRMED"
        fills_out = _sort_fills(existing_fills if not persist else fills)
    else:
        fills_status = "OBSERVATION_UNAVAILABLE"
        fills_out = None

    if trades_status == "OBSERVATION_UNAVAILABLE" and fills_status == "OBSERVATION_UNAVAILABLE":
        status = "OBSERVATION_UNAVAILABLE"
        detail = host.get("reason") or catalog.get("reason") or "execution source unread"
        observation = "UNAVAILABLE"
    elif not host_ok and not catalog_ok:
        status = "CONFIRMED"
        detail = "historical ledger; current source unread"
        observation = "HISTORICAL"
    elif host_ok:
        status = "CONFIRMED"
        detail = None
        observation = "CURRENT"
    else:
        status = "CONFIRMED"
        if trades:
            detail = (
                "host unread; one row per confirmed Kalshi ticker. "
                "JUMP_CATALOG fills without ticker are not grouped"
            )
        else:
            detail = "fills from catalog; logical trades require a host position or a confirmed ticker"
        observation = "CURRENT"

    if isinstance(trades, list):
        trades = [
            apply_standard_row(dict(row), snapshot=snapshot, history=bankroll_history)
            for row in trades
        ]
        trades = [row for row in trades if _measurable_trade(row)]

    view = {
        "bot_id": resolved,
        "status": status,
        "trades_status": trades_status,
        "fills_status": fills_status,
        "trades": trades,
        "fills": fills_out,
        "summary": _summary(trades, fills_out, trades_ok=trades_status == "CONFIRMED", fills_ok=fills_status == "CONFIRMED"),
        "one_row_per": "market",
        "grouping": "host_position" if host_ok or any(row.get("source") == SOURCE_HOST for row in (trades or [])) else "kalshi_ticker",
        "catalog_does_not_group": True,
        "ticker_group_when_confirmed": True,
        "kalshi": _kalshi_layer(bot),
        "source": {
            "host": _host_source(
                host_ok=host_ok,
                present=bool(host.get("present")),
                reason=host.get("reason"),
            ),
            "catalog": {"status": "CONFIRMED" if catalog_ok else "OBSERVATION_UNAVAILABLE", "detail": catalog.get("reason")},
        },
        "observation": observation,
        "layers": {
            "orders": "What orders were observed?",
            "positions": "What inventory is currently observed?",
            "execution": "What actual executions/fills were established?",
            "trades": "What logical entry → exit trades can be reconstructed?",
            "pnl": "What financial result can actually be established?",
        },
        "live_ev": unavailable("UNAVAILABLE"),
        "sharpe": unavailable("UNAVAILABLE"),
        "http_200_not_running": True,
    }
    if detail:
        view["detail"] = detail
    return view


def execution_view(bot_id: str = BOT_ID, *, root: Path | None = None) -> dict[str, Any]:
    return reconcile_bot(bot_id, root=root, persist=True)


def _standard_rows(trades: list[dict[str, Any]] | None) -> list[dict[str, Any]] | None:
    if trades is None:
        return None
    rows: list[dict[str, Any]] = []
    for trade in trades:
        row = dict(trade.get("standard_row") or {})
        row["trade_id"] = trade.get("trade_id")
        row["status"] = trade.get("status")
        rows.append(row)
    return rows


def trades_view(bot_id: str = BOT_ID, *, root: Path | None = None) -> dict[str, Any]:
    view = execution_view(bot_id, root=root)
    return {
        "bot_id": view["bot_id"],
        "status": view["trades_status"],
        "trades": view["trades"],
        "rows": _standard_rows(view["trades"]),
        "one_row_per": view.get("one_row_per"),
        "grouping": view.get("grouping"),
        "catalog_does_not_group": view.get("catalog_does_not_group"),
        "summary": view["summary"],
        "source": view["source"],
        "observation": view["observation"],
        "detail": view.get("detail"),
        "live_ev": unavailable("UNAVAILABLE"),
    }


def fills_view(bot_id: str = BOT_ID, *, root: Path | None = None) -> dict[str, Any]:
    view = execution_view(bot_id, root=root)
    return {
        "bot_id": view["bot_id"],
        "status": view["fills_status"],
        "fills": view["fills"],
        "summary": view["summary"],
        "source": view["source"],
        "observation": view["observation"],
        "detail": view.get("detail"),
    }


def trade_detail_view(bot_id: str, trade_id: str, *, root: Path | None = None) -> dict[str, Any]:
    from roller.vital.errors import VitalError

    view = execution_view(bot_id, root=root)
    if view["trades_status"] != "CONFIRMED":
        return {
            "bot_id": view["bot_id"],
            "status": "OBSERVATION_UNAVAILABLE",
            "trade": None,
            "detail": view.get("detail") or "trade history could not be read",
        }
    wanted = str(trade_id or "").strip()
    for row in view.get("trades") or []:
        if str(row.get("trade_id")) == wanted:
            return {
                "bot_id": view["bot_id"],
                "status": "CONFIRMED",
                "trade": row,
                "observation": view.get("observation"),
                "source": row.get("source"),
            }
    raise VitalError("TRADE_NOT_FOUND", f"trade not found: {trade_id}")
