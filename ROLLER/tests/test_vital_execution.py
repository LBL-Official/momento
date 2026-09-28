"""Vital MLB 001 execution ledger. No invented fills. No fake zeros."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from roller.vital import api as vapi
from roller.vital.execution import trade_identity
from roller.vital.reconcile import (
    execution_view,
    normalize_catalog_fill,
    normalize_host_fill,
    reconstruct_trade,
    reconcile_bot,
)
from roller.vital.store import load_execution_trades, seed_mlb_001
from roller.vital.versions import BOT_ID

_BANNED = ("KALSHI_API_KEY", "PRIVATE_KEY", "secret_key", "api_key=", "BEGIN RSA PRIVATE KEY")
_FORBIDDEN = (
    "strategies/mlb",
    "apps/trading-engine",
    "crates/risk",
    "config/live.toml",
    "deploy/momento-live.service",
)
_REPO = Path(__file__).resolve().parents[2]


def _isolate(monkeypatch, tmp_path):
    monkeypatch.setenv("VITAL_ROOT", str(tmp_path))
    monkeypatch.setenv("JUMP_CATALOG_ROOT", str(tmp_path / "catalog"))
    monkeypatch.setenv("JUMP_SKIP_KALSHI", "1")
    monkeypatch.setenv("VITAL_AWS_HOST_FETCH", "0")
    monkeypatch.delenv("VITAL_AWS_INSPECT_FIXTURE", raising=False)
    monkeypatch.delenv("VITAL_BOT_RUNTIME_PATH", raising=False)
    monkeypatch.delenv("VITAL_ENABLE_CONTROL", raising=False)
    monkeypatch.delenv("VITAL_AWS_CONTROL", raising=False)
    state = tmp_path / "state"
    state.mkdir()
    monkeypatch.setenv("VITAL_BOT_STATE_DIR", str(state))
    seed_mlb_001(root=tmp_path)
    return state


def _write_runtime(state: Path, positions: list[dict]) -> None:
    (state / "live-runtime.json").write_text(
        json.dumps({"tracker": {"positions": positions}}),
        encoding="utf-8",
    )


def _fill(*, ts: str, premium: int, qty: int, price: int, kind: str, fee: int | None = 0, fill_id: str | None = None, ticker: str | None = "KXMLBGAME-TEST") -> dict:
    row = {
        "premium": {"cents": premium},
        "quantity": {"qty": qty},
        "price": {"cents": price},
        "fee": {"kind": kind} if fee is None else {"amount": {"cents": fee}, "kind": kind},
        "exchange_ts": ts,
        "side": "yes",
    }
    if fill_id is not None:
        row["fill_id"] = fill_id
    if ticker:
        row["ticker"] = ticker
    return row


def _closed_pair() -> list[dict]:
    return [
        {
            "id": 184,
            "strategy_id": 1,
            "lifecycle": "Flat",
            "filled_quantity": {"qty": 0},
            "ticker": "KXMLBGAME-TEST",
            "side": "yes",
            "fill_history": [
                _fill(ts="2026-09-14T02:31:00Z", premium=405, qty=5, price=81, kind="Entry", fill_id="entry-184"),
                _fill(ts="2026-09-14T03:10:00Z", premium=485, qty=5, price=97, kind="Liquidation", fill_id="exit-184"),
            ],
        }
    ]


def test_fill_normalization():
    position = _closed_pair()[0]
    fill = normalize_host_fill(BOT_ID, position, position["fill_history"][0], 0)
    assert fill is not None
    assert fill["observation_status"] == "CONFIRMED"
    assert fill["source"] == "HOST_LEDGER"
    assert fill["amount_cents"]["value"] == 405
    assert fill["price_cents"]["value"] == 81
    assert fill["contracts"]["value"] == 5
    assert fill["fee_kind"]["value"] == "Entry"
    assert fill["market"]["value"] == "KXMLBGAME-TEST"


def test_duplicate_prevention(monkeypatch, tmp_path):
    state = _isolate(monkeypatch, tmp_path)
    _write_runtime(state, _closed_pair())
    first = reconcile_bot(BOT_ID, root=tmp_path)
    second = reconcile_bot(BOT_ID, root=tmp_path)
    assert first["fills_status"] == "CONFIRMED"
    assert len(first["fills"]) == len(second["fills"]) == 2
    lines = (tmp_path / "bots" / BOT_ID / "execution" / "fills.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    trade_lines = (tmp_path / "bots" / BOT_ID / "execution" / "trades.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(trade_lines) == 1
    assert first["trades"][0]["trade_id"] == second["trades"][0]["trade_id"]
    events = (tmp_path / "bots" / BOT_ID / "events" / "events.jsonl").read_text(encoding="utf-8")
    assert events.count("reconciliation_completed") == 1


def test_multiple_entry_fills_one_trade(monkeypatch, tmp_path):
    state = _isolate(monkeypatch, tmp_path)
    _write_runtime(
        state,
        [
            {
                "id": 200,
                "strategy_id": 1,
                "lifecycle": "Flat",
                "filled_quantity": {"qty": 0},
                "ticker": "KXMLBGAME-MULTI",
                "fill_history": [
                    _fill(ts="2026-09-14T01:00:00Z", premium=324, qty=4, price=81, kind="Entry", fill_id="e1", ticker="KXMLBGAME-MULTI"),
                    _fill(ts="2026-09-14T01:00:01Z", premium=243, qty=3, price=81, kind="Entry", fill_id="e2", ticker="KXMLBGAME-MULTI"),
                    _fill(ts="2026-09-14T02:00:00Z", premium=679, qty=7, price=97, kind="Liquidation", fill_id="x1", ticker="KXMLBGAME-MULTI"),
                ],
            }
        ],
    )
    view = reconcile_bot(BOT_ID, root=tmp_path)
    assert view["trades_status"] == "CONFIRMED"
    assert len(view["trades"]) == 1
    trade = view["trades"][0]
    assert trade["entry_contracts"]["value"] == 7
    assert trade["entry_amount"]["value"] == 567
    assert trade["entry_price"]["value"] == 81
    assert trade["status"] == "CLOSED"


def test_partial_exit(monkeypatch, tmp_path):
    state = _isolate(monkeypatch, tmp_path)
    _write_runtime(
        state,
        [
            {
                "id": 201,
                "strategy_id": 1,
                "lifecycle": "Holding",
                "filled_quantity": {"qty": 2},
                "ticker": "KXMLBGAME-PART",
                "fill_history": [
                    _fill(ts="2026-09-14T01:00:00Z", premium=567, qty=7, price=81, kind="Entry", fill_id="p-e", ticker="KXMLBGAME-PART"),
                    _fill(ts="2026-09-14T02:00:00Z", premium=485, qty=5, price=97, kind="Liquidation", fill_id="p-x", ticker="KXMLBGAME-PART"),
                ],
            }
        ],
    )
    trade = reconcile_bot(BOT_ID, root=tmp_path)["trades"][0]
    assert trade["status"] == "PARTIAL"
    assert trade["exit_contracts"]["value"] == 5
    assert trade["net_realized_cents"]["status"] == "UNAVAILABLE"
    assert trade["net_realized_cents"]["value"] is None


def test_full_exit(monkeypatch, tmp_path):
    state = _isolate(monkeypatch, tmp_path)
    _write_runtime(state, _closed_pair())
    trade = reconcile_bot(BOT_ID, root=tmp_path)["trades"][0]
    assert trade["status"] == "CLOSED"
    assert trade["entry_amount"]["value"] == 405
    assert trade["exit_amount"]["value"] == 485
    assert trade["gross_realized_cents"]["value"] == 80
    assert trade["net_realized_cents"]["value"] == 80
    assert trade["fee_cents"]["value"] == 0


def test_open_trade(monkeypatch, tmp_path):
    state = _isolate(monkeypatch, tmp_path)
    _write_runtime(
        state,
        [
            {
                "id": 202,
                "strategy_id": 1,
                "lifecycle": "Holding",
                "filled_quantity": {"qty": 5},
                "ticker": "KXMLBGAME-OPEN",
                "fill_history": [
                    _fill(ts="2026-09-14T02:31:00Z", premium=405, qty=5, price=81, kind="Entry", fill_id="open-e", ticker="KXMLBGAME-OPEN"),
                ],
            }
        ],
    )
    trade = reconcile_bot(BOT_ID, root=tmp_path)["trades"][0]
    assert trade["status"] == "OPEN"
    assert trade["exit_date"]["status"] == "UNAVAILABLE"
    assert trade["exit_amount"]["value"] is None
    assert trade["net_realized_cents"]["status"] == "UNAVAILABLE"
    assert trade["net_realized_cents"]["value"] is None


def test_missing_source_is_not_empty_history(monkeypatch, tmp_path):
    monkeypatch.setenv("VITAL_ROOT", str(tmp_path))
    monkeypatch.setenv("JUMP_CATALOG_ROOT", str(tmp_path / "catalog"))
    monkeypatch.delenv("VITAL_BOT_STATE_DIR", raising=False)
    monkeypatch.delenv("VITAL_BOT_RUNTIME_PATH", raising=False)
    monkeypatch.setenv("VITAL_AWS_HOST_FETCH", "0")
    monkeypatch.delenv("VITAL_AWS_INSPECT_FIXTURE", raising=False)
    seed_mlb_001(root=tmp_path)
    view = reconcile_bot(BOT_ID, root=tmp_path)
    assert view["status"] == "OBSERVATION_UNAVAILABLE"
    assert view["trades"] is None
    assert view["fills"] is None
    assert view["summary"]["total_trades"]["status"] == "OBSERVATION_UNAVAILABLE"
    assert view["summary"]["total_trades"]["value"] is None
    assert view["summary"]["total_fills"]["value"] is None


def test_pnl_honesty_unknown_fees(monkeypatch, tmp_path):
    state = _isolate(monkeypatch, tmp_path)
    _write_runtime(
        state,
        [
            {
                "id": 203,
                "strategy_id": 1,
                "lifecycle": "Flat",
                "filled_quantity": {"qty": 0},
                "ticker": "KXMLBGAME-FEE",
                "fill_history": [
                    _fill(ts="2026-09-14T01:00:00Z", premium=405, qty=5, price=81, kind="Entry", fee=None, fill_id="fee-e"),
                    _fill(ts="2026-09-14T02:00:00Z", premium=485, qty=5, price=97, kind="Liquidation", fee=None, fill_id="fee-x"),
                ],
            }
        ],
    )
    trade = reconcile_bot(BOT_ID, root=tmp_path)["trades"][0]
    assert trade["gross_realized_cents"]["value"] == 80
    assert trade["net_realized_cents"]["status"] == "UNAVAILABLE"
    assert trade["net_realized_cents"]["value"] is None
    assert trade["fee_cents"]["status"] == "UNAVAILABLE"


def test_restart_persistence(monkeypatch, tmp_path):
    state = _isolate(monkeypatch, tmp_path)
    _write_runtime(state, _closed_pair())
    first = reconcile_bot(BOT_ID, root=tmp_path)
    trade_id = first["trades"][0]["trade_id"]
    monkeypatch.delenv("VITAL_BOT_STATE_DIR", raising=False)
    reloaded = load_execution_trades(BOT_ID, root=tmp_path)
    assert len(reloaded) == 1
    assert reloaded[0]["trade_id"] == trade_id
    view = reconcile_bot(BOT_ID, root=tmp_path)
    assert view["trades_status"] == "CONFIRMED"
    assert view["observation"] == "HISTORICAL"
    assert view["trades"][0]["trade_id"] == trade_id
    assert len(view["trades"]) == 1


def test_confirmed_empty_host(monkeypatch, tmp_path):
    state = _isolate(monkeypatch, tmp_path)
    _write_runtime(state, [])
    view = reconcile_bot(BOT_ID, root=tmp_path)
    assert view["status"] == "CONFIRMED"
    assert view["trades"] == []
    assert view["fills"] == []
    assert view["summary"]["total_trades"]["value"] == 0
    assert view["summary"]["total_fills"]["value"] == 0


def test_kalshi_ticker_fills_group_open_trades(monkeypatch, tmp_path):
    monkeypatch.setenv("VITAL_ROOT", str(tmp_path))
    monkeypatch.setenv("JUMP_SKIP_KALSHI", "1")
    catalog = tmp_path / "catalog"
    catalog.mkdir()
    monkeypatch.setenv("JUMP_CATALOG_ROOT", str(catalog))
    monkeypatch.delenv("VITAL_BOT_STATE_DIR", raising=False)
    monkeypatch.delenv("VITAL_BOT_RUNTIME_PATH", raising=False)
    (catalog / "trades.jsonl").write_text(
        json.dumps(
            {
                "jump_trade_id": "abc123abc123abc123abc123abc123ab",
                "bot_id": "mlb-bot-one",
                "environment": "PRODUCTION",
                "kalshi_fill_id": "0722f8f2-0fa1-a882-1849-3e86f3bef831",
                "order_id": "01a0982f-2e40-7140-9e4a-21fd1dc214a5",
                "ticker": "KXMLBGAME-26SEP121915CWSSTL-STL",
                "qty": 7,
                "yes_price_cents": 81,
                "exchange_ts": "2026-09-13T00:42:35Z",
                "source": "kalshi",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    seed_mlb_001(root=tmp_path)
    view = reconcile_bot(BOT_ID, root=tmp_path)
    assert view["fills_status"] == "CONFIRMED"
    assert view["fills"] is not None
    assert len(view["fills"]) == 1
    assert view["fills"][0]["source"] == "KALSHI_ACCOUNT"
    assert view["fills"][0]["fee_cents"]["status"] == "UNAVAILABLE"
    assert view["trades_status"] == "CONFIRMED"
    assert view["trades"] is not None
    assert len(view["trades"]) == 1
    assert view["trades"][0]["market"]["value"] == "KXMLBGAME-26SEP121915CWSSTL-STL"
    assert view["trades"][0]["source"] == "KALSHI_ACCOUNT"
    assert view["trades"][0]["status"] == "OPEN"
    assert view["trades"][0]["amount_exited_cents"]["status"] == "UNAVAILABLE"
    assert view["grouping"] == "kalshi_ticker"
    again = reconcile_bot(BOT_ID, root=tmp_path)
    assert again["trades"][0]["entry_contracts"]["value"] == 7
    assert again["trades"][0]["amount_traded_cents"]["value"] == 567


def test_public_settlement_closes_ticker_trade(monkeypatch, tmp_path):
    monkeypatch.setenv("VITAL_ROOT", str(tmp_path))
    monkeypatch.setenv("JUMP_SKIP_KALSHI", "1")
    catalog = tmp_path / "catalog"
    catalog.mkdir()
    monkeypatch.setenv("JUMP_CATALOG_ROOT", str(catalog))
    monkeypatch.delenv("VITAL_BOT_STATE_DIR", raising=False)
    monkeypatch.delenv("VITAL_BOT_RUNTIME_PATH", raising=False)
    ticker = "KXMLBGAME-26SEP131340HOUTB-TB"
    (catalog / "trades.jsonl").write_text(
        json.dumps(
            {
                "jump_trade_id": "d" * 32,
                "bot_id": "mlb-bot-one",
                "environment": "PRODUCTION",
                "kalshi_fill_id": "0722f41b-0949-87ec-8de5-4cccba900348",
                "ticker": ticker,
                "qty": 7,
                "yes_price_cents": 81,
                "exchange_ts": "2026-09-13T18:17:51Z",
                "source": "kalshi",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    seed_mlb_001(root=tmp_path)
    from roller.vital.mlb_001.settlement import persist_settlements

    persist_settlements(
        BOT_ID,
        {
            ticker: {
                "ticker": ticker,
                "result": "yes",
                "settlement_value_cents": 100,
                "settlement_ts": "2026-09-13T20:27:00Z",
                "status": "CONFIRMED",
                "source": "kalshi_public_market",
            }
        },
        root=tmp_path,
    )
    view = reconcile_bot(BOT_ID, root=tmp_path)
    trade = view["trades"][0]
    assert trade["status"] == "CLOSED"
    assert trade["entry_contracts"]["value"] == 7
    assert trade["amount_traded_cents"]["value"] == 567
    assert trade["amount_exited_cents"]["value"] == 700
    assert trade["exit_price_cents"]["value"] == 100
    assert trade["gross_realized_cents"]["value"] == 133


def test_catalog_normalize_notional():
    row = normalize_catalog_fill(
        BOT_ID,
        {
            "jump_trade_id": "x" * 32,
            "bot_id": "mlb-bot-one",
            "environment": "PRODUCTION",
            "kalshi_fill_id": "fill-1",
            "qty": 5,
            "yes_price_cents": 81,
            "source": "kalshi",
            "ticker": "KXMLBGAME-X",
        },
    )
    assert row is not None
    assert row["amount_cents"]["value"] == 405
    assert row["source"] == "KALSHI_ACCOUNT"


def test_no_secrets_in_execution_artifacts(monkeypatch, tmp_path):
    state = _isolate(monkeypatch, tmp_path)
    _write_runtime(state, _closed_pair())
    view = vapi.handle_execution(BOT_ID, root=tmp_path)
    blob = json.dumps(view)
    for token in _BANNED:
        assert token not in blob
    dest = tmp_path / "bots" / BOT_ID / "execution"
    for path in dest.rglob("*"):
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            for token in _BANNED:
                assert token not in text
            assert "momento-kalshi-live.json" not in text


def test_existing_execution_untouched():
    for rel in _FORBIDDEN:
        path = _REPO / rel
        assert path.exists(), rel
    vital = Path(__file__).resolve().parents[1] / "roller" / "vital"
    text = "\n".join(path.read_text(encoding="utf-8") for path in vital.glob("*.py"))
    assert "ENABLE_LIVE_TRADING" not in text or "LIVE_CONFIRMATION" in text
    assert "Create V2" not in text
    assert "/dev/shm/momento-kalshi-live.json" not in text


def test_api_and_alias(monkeypatch, tmp_path):
    state = _isolate(monkeypatch, tmp_path)
    _write_runtime(state, _closed_pair())
    body = vapi.handle_execution("mlb-bot-one", root=tmp_path)
    assert body["bot_id"] == BOT_ID
    assert body["status"] == "CONFIRMED"
    assert body["trades"][0]["trade_id"] == trade_identity(BOT_ID, "184")
    trades = vapi.handle_execution_trades(BOT_ID, root=tmp_path)
    fills = vapi.handle_execution_fills(BOT_ID, root=tmp_path)
    assert trades["status"] == "CONFIRMED"
    assert fills["status"] == "CONFIRMED"
    assert trades["trades"] is not None
    assert fills["fills"] is not None
    detail = vapi.handle_execution_trade(BOT_ID, body["trades"][0]["trade_id"], root=tmp_path)
    assert detail["trade"]["status"] == "CLOSED"
    orders = vapi.handle_orders(BOT_ID, root=tmp_path)
    positions = vapi.handle_positions(BOT_ID, root=tmp_path)
    assert orders["layer"] == "orders"
    assert positions["layer"] == "positions"


def test_http_execution_routes(monkeypatch, tmp_path):
    state = _isolate(monkeypatch, tmp_path)
    _write_runtime(state, _closed_pair())
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import terminal_api

    client = TestClient(terminal_api.app)
    one = client.get("/vital/bots/mlb-001/execution").json()
    alias = client.get("/vital/bots/mlb-bot-one/execution").json()
    assert one["bot_id"] == alias["bot_id"] == BOT_ID
    assert one["trades_status"] == "CONFIRMED"
    fills = client.get("/vital/bots/mlb-001/execution/fills").json()
    assert fills["status"] == "CONFIRMED"
    trade_id = one["trades"][0]["trade_id"]
    detail = client.get(f"/vital/bots/mlb-001/execution/trades/{trade_id}").json()
    assert detail["status"] == "CONFIRMED"
    missing = client.get("/vital/bots/mlb-001/execution/trades/not-a-trade")
    assert missing.status_code == 404
    kalshi = client.get("/vital/bots/mlb-001/kalshi").json()
    assert kalshi["read_only"] is True
    assert kalshi["submits"] is False
    posted = client.post("/vital/bots/mlb-001/kalshi/observe").json()
    assert posted["read_only"] is True
    assert posted["submits"] is False
    assert posted["status"] == "OBSERVATION_UNAVAILABLE"


def test_no_fake_zeros_on_unread_http(monkeypatch, tmp_path):
    monkeypatch.setenv("VITAL_ROOT", str(tmp_path))
    monkeypatch.setenv("JUMP_CATALOG_ROOT", str(tmp_path / "catalog"))
    monkeypatch.delenv("VITAL_BOT_STATE_DIR", raising=False)
    monkeypatch.delenv("VITAL_BOT_RUNTIME_PATH", raising=False)
    seed_mlb_001(root=tmp_path)
    body = vapi.handle_execution(BOT_ID, root=tmp_path)
    assert body["trades"] is None
    assert body["fills"] is None
    assert body["summary"]["total_trades"]["status"] == "OBSERVATION_UNAVAILABLE"
    assert body["summary"]["total_trades"]["value"] is None
    dumped = json.dumps(body)
    assert '"trades": []' not in dumped.replace(" ", "")
    assert body["live_ev"]["status"] == "UNAVAILABLE"


def test_reconstruct_settlement_net():
    position = {
        "id": 9,
        "strategy_id": 1,
        "lifecycle": "Settled",
        "filled_quantity": {"qty": 3},
        "ticker": "KXMLBGAME-SET",
        "settlement_proceeds": {"cents": 300},
        "fill_history": [
            _fill(ts="2026-08-26T16:00:00Z", premium=240, qty=3, price=80, kind="Entry", fee=5, fill_id="s1", ticker="KXMLBGAME-SET"),
        ],
    }
    trade = reconstruct_trade(BOT_ID, position)
    assert trade["status"] == "CLOSED"
    assert trade["gross_realized_cents"]["value"] == 60
    assert trade["net_realized_cents"]["value"] == 55
    assert trade["fee_cents"]["value"] == 5


def test_trade_identity_stable():
    assert trade_identity(BOT_ID, "184") == trade_identity("mlb-001", "184")
