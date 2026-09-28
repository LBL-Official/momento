"""Jump catalog: Bot One origin, UNATTRIBUTED unmatched, no demo-into-live."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from roller.jump.bots.versions import BOT_ONE_ID
from roller.jump.catalog.analysis import analyze
from roller.jump.catalog.charts import render_yes_bid_svg
from roller.jump.catalog.identity import jump_trade_id
from roller.jump.catalog.refresh import refresh_catalog
from roller.jump.catalog.versions import UNATTRIBUTED
from roller.jump.dashboard.ledger import list_mlb_fills
from roller.jump.dashboard.rollup import rollup_tracks

_BANNED = ("KALSHI_API_KEY", "PRIVATE_KEY", "secret_key", "api_key=")


def _isolate(monkeypatch, tmp_path: Path) -> Path:
    bots = tmp_path / "bots"
    monkeypatch.setenv("JUMP_BOTS_ROOT", str(bots))
    monkeypatch.setenv("JUMP_CATALOG_ROOT", str(tmp_path / "catalog"))
    monkeypatch.setenv("JUMP_SKIP_KALSHI", "1")
    monkeypatch.delenv("JUMP_BOT_ONE_PROBE", raising=False)
    monkeypatch.delenv("JUMP_BOT_ONE_HOST_FETCH", raising=False)
    monkeypatch.delenv("JUMP_BOT_DEMO_SSM", raising=False)
    monkeypatch.setenv("VITAL_ROOT", str(tmp_path / "vital"))
    monkeypatch.setenv("VITAL_AWS_HOST_FETCH", "0")
    return bots


def _runtime(ts_a="2026-08-24T16:10:00Z", ts_b="2026-09-13T00:10:56Z"):
    return {
        "tracker": {
            "positions": [
                {
                    "strategy_id": 1,
                    "lifecycle": "Settled",
                    "filled_quantity": {"qty": 3},
                    "ticker": "KXMLBGAME-TEST",
                    "fill_history": [
                        {
                            "fill_id": 11,
                            "quantity": {"qty": 3},
                            "price": {"cents": 80},
                            "premium": {"cents": 240},
                            "fee": {"amount": {"cents": 5}, "kind": "Entry"},
                            "exchange_ts": ts_a,
                            "side": "yes",
                        }
                    ],
                    "settlement_proceeds": {"cents": 300},
                },
                {
                    "strategy_id": 1,
                    "lifecycle": "Settled",
                    "filled_quantity": {"qty": 1},
                    "ticker": "KXMLBGAME-LATER",
                    "fill_history": [
                        {
                            "fill_id": 12,
                            "quantity": {"qty": 1},
                            "price": {"cents": 82},
                            "premium": {"cents": 82},
                            "fee": {"amount": {"cents": 2}, "kind": "Entry"},
                            "exchange_ts": ts_b,
                            "side": "yes",
                        }
                    ],
                    "settlement_proceeds": {"cents": 0},
                },
            ]
        }
    }


def test_origin_is_earliest_bot_one_ledger_fill(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    state = tmp_path / "state"
    state.mkdir()
    runtime = _runtime()
    (state / "live-runtime.json").write_text(json.dumps(runtime), encoding="utf-8")
    monkeypatch.setenv("JUMP_BOT_ONE_STATE_DIR", str(state))
    now = datetime(2026, 9, 13, 1, 0, tzinfo=timezone.utc)
    fills = list_mlb_fills(runtime, None, now)
    earliest = min(row["exchange_ts"] for row in fills["trades"])
    body = refresh_catalog(root=tmp_path / "bots", now=now, pull_kalshi=False, fetch_charts=False)
    assert body["origin"]["bot_one_first_fill_ts"] == earliest
    assert earliest.startswith("2026-08-24")
    from roller.jump.catalog.store import load_trades

    for row in load_trades(root=tmp_path / "catalog"):
        if str(row.get("environment") or "") == "PRODUCTION":
            assert row["exchange_ts"] >= earliest


def test_unmatched_kalshi_is_unattributed(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    state = tmp_path / "state"
    state.mkdir()
    (state / "live-runtime.json").write_text(json.dumps(_runtime()), encoding="utf-8")
    monkeypatch.setenv("JUMP_BOT_ONE_STATE_DIR", str(state))
    now = datetime(2026, 9, 13, 1, 0, tzinfo=timezone.utc)
    body = refresh_catalog(
        root=tmp_path / "bots",
        now=now,
        pull_kalshi=False,
        fetch_charts=False,
        kalshi_books={
            "PRODUCTION": {
                "ok": True,
                "status": "CONFIRMED",
                "fills": [
                    {
                        "trade_id": "orphan-1",
                        "fill_id": "orphan-1",
                        "order_id": "ord-1",
                        "ticker": "KXMLBGAME-ORPHAN",
                        "qty": 1,
                        "yes_price_cents": 81,
                        "exchange_ts": "2026-08-26T12:00:00Z",
                    }
                ],
            },
            "DEMO": {"ok": False, "status": "OBSERVATION_UNAVAILABLE", "fills": []},
        },
    )
    from roller.jump.catalog.store import load_trades

    rows = load_trades(root=tmp_path / "catalog")
    orphans = [row for row in rows if row.get("kalshi_trade_id") == "orphan-1"]
    assert orphans
    assert orphans[0]["bot_id"] == UNATTRIBUTED
    assert orphans[0]["source"] == "kalshi"
    ledger_rows = [row for row in rows if row.get("source") == "ledger"]
    assert ledger_rows
    assert all(row["bot_id"] == BOT_ONE_ID for row in ledger_rows)


def test_refresh_without_secrets_marks_books_unavailable(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    state = tmp_path / "state"
    state.mkdir()
    (state / "live-runtime.json").write_text(json.dumps(_runtime()), encoding="utf-8")
    monkeypatch.setenv("JUMP_BOT_ONE_STATE_DIR", str(state))
    body = refresh_catalog(root=tmp_path / "bots", pull_kalshi=True, fetch_charts=False)
    assert body["books"]["PRODUCTION"]["status"] == "OBSERVATION_UNAVAILABLE"
    assert body["books"]["DEMO"]["status"] == "OBSERVATION_UNAVAILABLE"
    assert body["origin"]["bot_one_first_fill_ts"]
    assert body["trade_n"] >= 1


def test_demo_pnl_not_added_to_live():
    analysis = analyze(
        [
            {
                "bot_id": BOT_ONE_ID,
                "environment": "PRODUCTION",
                "exchange_ts": "2026-08-26T16:00:00Z",
                "result": 55,
                "jump_trade_id": "a",
            },
            {
                "bot_id": "demo-bot",
                "environment": "DEMO",
                "exchange_ts": "2026-08-26T16:05:00Z",
                "result": 100,
                "jump_trade_id": "b",
            },
        ],
        now=datetime(2026, 8, 26, 18, 0, tzinfo=timezone.utc),
        snapshot={"week_start_utc": "2026-08-24T11:00:00Z"},
    )
    assert analysis["by_book"]["PRODUCTION"]["day_fill_result_cents"] == 55
    assert analysis["by_book"]["PRODUCTION"]["fill_result_sum_cents"] == 55
    assert analysis["by_book"]["DEMO"]["day_fill_result_cents"] == 100
    assert analysis["by_book"]["DEMO"]["fill_result_sum_cents"] == 100
    assert analysis["by_bot"][BOT_ONE_ID]["fill_result_sum_cents"] == 55
    assert analysis["honesty"]["fill_result_sum_is_not_account_pnl"] is True
    rollup = rollup_tracks(
        [
            {
                "kind": "grandfathered",
                "environment": "PRODUCTION",
                "actual": {"day_pnl": {"value": analysis["by_book"]["PRODUCTION"]["day_fill_result_cents"], "status": "CONFIRMED"}},
                "expected": {},
            },
            {
                "kind": "iti",
                "environment": "DEMO",
                "actual": {"day_pnl": {"value": analysis["by_book"]["DEMO"]["day_fill_result_cents"], "status": "CONFIRMED"}},
                "expected": {},
            },
        ]
    )
    assert rollup["live"]["actual"]["day_pnl"]["value"] == 55
    assert rollup["demo"]["actual"]["day_pnl"]["value"] == 100
    assert rollup["honesty"]["demo_not_added_to_live"] is True


def test_mybots_posts_include_trade_weekly_every_10():
    from roller.jump.catalog.mybots import build_posts

    rows = []
    for i in range(10):
        rows.append(
            {
                "bot_id": BOT_ONE_ID,
                "environment": "PRODUCTION",
                "exchange_ts": f"2026-08-26T16:{i:02d}:00Z",
                "result": 1,
                "jump_trade_id": f"t{i}",
                "ticker": "KXMLBGAME-TEST",
            }
        )
    analysis = analyze(rows, now=datetime(2026, 8, 26, 18, 0, tzinfo=timezone.utc))
    posts = build_posts(BOT_ONE_ID, rows, analysis)
    kinds = {post["kind"] for post in posts}
    assert kinds == {"trade", "weekly", "every_10"}
    weekly = next(post for post in posts if post["kind"] == "weekly")
    every = next(post for post in posts if post["kind"] == "every_10")
    assert weekly["result"] == "UNAVAILABLE"
    assert every["result"] == "UNAVAILABLE"


def test_every_10_and_weekly_markers():
    rows = []
    for i in range(12):
        rows.append(
            {
                "bot_id": BOT_ONE_ID,
                "environment": "PRODUCTION",
                "exchange_ts": f"2026-08-26T16:{i:02d}:00Z",
                "result": 1,
                "jump_trade_id": f"t{i}",
            }
        )
    analysis = analyze(rows, now=datetime(2026, 8, 26, 18, 0, tzinfo=timezone.utc))
    assert analysis["every_ten"][BOT_ONE_ID][0]["n"] == 10
    assert analysis["weekly_markers"][BOT_ONE_ID]


def test_missing_candles_are_data_required():
    assert render_yes_bid_svg([], fill_ts=None, ticker="KXMLB") is None
    svg = render_yes_bid_svg(
        [
            {"end_period_ts": 1, "open_cents": 80, "high_cents": 82, "low_cents": 79, "close_cents": 81},
            {"end_period_ts": 61, "open_cents": 81, "high_cents": 83, "low_cents": 80, "close_cents": 80},
        ],
        fill_ts=datetime.fromtimestamp(30, tz=timezone.utc),
        ticker="KXMLBGAME-TEST",
    )
    assert svg and svg.startswith("<svg")
    assert "candle path ≠ fill" in svg


def test_ssm_compact_trades_fit_under_24kb():
    from roller.jump.catalog.reconcile import ledger_record
    from roller.jump.dashboard.ledger import compact_ssm_trades

    rows = []
    for i in range(95):
        rows.append(
            {
                "exchange_ts": "2026-08-24T16:10:00Z",
                "premium_cents": 80,
                "fee_cents": 2,
                "fee_kind": "Entry",
                "qty": 1,
                "price_cents": 80,
                "realized_cents": None,
                "market": "KXMLBGAME-TEST" if i == 0 else "1" * 39,
                "fill_id": str(i) + ("9" * 38),
                "side": "yes",
            }
        )
    compact, earliest = compact_ssm_trades(rows)
    payload = json.dumps({"ok": True, "fields": {"trade_n": 95, "earliest_fill_ts": earliest}, "trades": compact}, separators=(",", ":"))
    assert earliest.startswith("2026-08-24")
    assert compact[0]["ticker"] == "KXMLBGAME-TEST"
    assert "ticker" not in compact[1]
    assert compact[0]["fill_id"] != compact[1]["fill_id"]
    ids = {
        ledger_record({**row, "bot_id": BOT_ONE_ID}, environment="PRODUCTION", bot_id=BOT_ONE_ID)["jump_trade_id"]
        for row in compact
    }
    assert len(ids) == 95
    assert len(payload) < 24000


def test_jump_trade_id_is_stable():
    assert jump_trade_id("PRODUCTION", trade_id="abc") == jump_trade_id("PRODUCTION", trade_id="abc")
    assert jump_trade_id("DEMO", trade_id="abc") != jump_trade_id("PRODUCTION", trade_id="abc")


def test_http_catalog_and_mybots(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    state = tmp_path / "state"
    state.mkdir()
    (state / "live-runtime.json").write_text(json.dumps(_runtime()), encoding="utf-8")
    monkeypatch.setenv("JUMP_BOT_ONE_STATE_DIR", str(state))
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import terminal_api

    client = TestClient(terminal_api.app)
    refreshed = client.post("/jump/catalog/refresh", json={"pull_kalshi": False, "fetch_charts": False})
    assert refreshed.status_code == 200
    catalog = client.get("/jump/catalog").json()
    assert catalog["origin"]["bot_one_first_fill_ts"].startswith("2026-08-24")
    prod = client.get("/jump/catalog?environment=PRODUCTION").json()
    assert all(row["environment"] == "PRODUCTION" for row in prod["trades"])
    trades = client.get(f"/jump/bots/{BOT_ONE_ID}/trades").json()
    assert trades["status"] == "CONFIRMED"
    assert trades["source"] == "catalog"
    mybots = client.get("/jump/mybots").json()
    one = next(row for row in mybots["profiles"] if row["bot_id"] == BOT_ONE_ID)
    kinds = {post["kind"] for post in one["posts"]}
    assert "trade" in kinds
    assert "weekly" in kinds
    dash = client.get("/jump/dashboard").json()
    assert dash["catalog"]["origin"]["bot_one_first_fill_ts"].startswith("2026-08-24")
    assert dash["rollup"]["honesty"]["demo_not_added_to_live"] is True


def test_ensure_catalog_refreshes_when_host_newer(monkeypatch, tmp_path):
    from roller.jump.catalog.refresh import ensure_catalog
    from roller.jump.catalog.store import load_trades

    _isolate(monkeypatch, tmp_path)
    state = tmp_path / "state"
    state.mkdir()
    (state / "live-runtime.json").write_text(json.dumps(_runtime()), encoding="utf-8")
    monkeypatch.setenv("JUMP_BOT_ONE_STATE_DIR", str(state))
    catalog = tmp_path / "catalog"
    catalog.mkdir()
    (catalog / "origin.json").write_text(
        json.dumps({"bot_one_first_fill_ts": "2026-08-24T16:10:00Z", "source": "stale"}, indent=2) + "\n",
        encoding="utf-8",
    )
    (catalog / "trades.jsonl").write_text(
        json.dumps(
            {
                "jump_trade_id": "old-only",
                "bot_id": BOT_ONE_ID,
                "environment": "PRODUCTION",
                "exchange_ts": "2026-08-24T16:10:00Z",
                "result": 55,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (catalog / "analysis.json").write_text(
        json.dumps(
            {
                "by_bot": {
                    BOT_ONE_ID: {
                        "trade_n": 1,
                        "fill_result_sum_cents": 55,
                        "last_trade": "2026-08-24T16:10:00Z",
                    }
                },
                "by_book": {
                    "PRODUCTION": {"trade_n": 1, "fill_result_sum_cents": 55, "last_trade": "2026-08-24T16:10:00Z"},
                    "DEMO": {"trade_n": 0, "fill_result_sum_cents": 0},
                },
                "honesty": {"fill_result_sum_is_not_account_pnl": True},
            }
        ),
        encoding="utf-8",
    )
    now = datetime(2026, 9, 13, 1, 0, tzinfo=timezone.utc)
    cold = ensure_catalog(root=tmp_path / "bots", now=now)
    assert cold["ok"] is True
    from roller.jump.catalog.store import load_trades as _load

    assert not any(str(row.get("exchange_ts") or "").startswith("2026-09-13") for row in _load(root=tmp_path / "catalog"))
    body = ensure_catalog(root=tmp_path / "bots", now=now, sync_host=True)
    assert body["ok"] is True
    rows = load_trades(root=tmp_path / "catalog")
    assert any(str(row.get("exchange_ts") or "").startswith("2026-09-13") for row in rows)


def test_mlb_shard_not_combined_balance():
    from roller.jump.catalog.bankroll import dollars_to_truncated_cents, select_production_cents

    assert dollars_to_truncated_cents("25.3317") == 2533
    assert dollars_to_truncated_cents("24.1894") == 2418
    assert dollars_to_truncated_cents("49.5211") == 4952
    body = {
        "current_cents": 4952,
        "balance_breakdown": [
            {"exchange_index": 0, "balance": "24.1894"},
            {"exchange_index": 3, "balance": "25.3317"},
        ],
    }
    selected = select_production_cents(body)
    assert selected["ok"] is True
    assert selected["current_cents"] == 2533
    assert selected["exchange_index"] == 3
    assert selected["top_level_cents"] == 4952
    missing = select_production_cents({"current_cents": 4952, "balance_breakdown": [{"exchange_index": 0, "balance": "24.1894"}]})
    assert missing["ok"] is False


def test_account_origin_pnl_is_bankroll_delta():
    from roller.jump.catalog.bankroll import account_bankroll, account_origin_pnl

    payload = {
        "origin_bankroll_cents": 5000,
        "books": {
            "PRODUCTION": {"current_cents": 3500, "origin_cents": 5000},
            "DEMO": {"current_cents": 4800, "origin_cents": 5000},
        },
    }
    assert account_origin_pnl(payload, environment="PRODUCTION") == {"value": -1500, "status": "CONFIRMED"}
    assert account_bankroll(payload, environment="PRODUCTION") == {"value": 3500, "status": "CONFIRMED"}
    live = account_origin_pnl(payload, environment="PRODUCTION")
    demo = account_origin_pnl(payload, environment="DEMO")
    assert live["value"] != demo["value"]
    assert live["value"] + demo["value"] != live["value"]


def test_fetch_balance_skipped_is_unavailable(monkeypatch, tmp_path):
    from roller.jump.catalog.kalshi import fetch_balance

    _isolate(monkeypatch, tmp_path)
    monkeypatch.setenv("JUMP_SKIP_KALSHI", "1")
    body = fetch_balance("PRODUCTION")
    assert body["ok"] is False
    assert body["status"] == "OBSERVATION_UNAVAILABLE"
    assert "current_cents" not in body or body.get("current_cents") is None


def test_day_week_from_kalshi_history_not_zero_when_unread():
    from roller.jump.catalog.bankroll import day_week_from_history, open_mlb_positions

    empty = day_week_from_history([], environment="PRODUCTION", current=2533, now=datetime(2026, 9, 13, 18, 0, tzinfo=timezone.utc))
    assert empty["day_pnl"]["value"] is None
    assert empty["week_pnl"]["value"] is None
    history = [
        {"environment": "PRODUCTION", "observed_at": "2026-09-06T12:00:00Z", "current_cents": 4000},
        {"environment": "PRODUCTION", "observed_at": "2026-09-12T20:00:00Z", "current_cents": 2600},
        {"environment": "DEMO", "observed_at": "2026-09-12T20:00:00Z", "current_cents": 100},
    ]
    windows = day_week_from_history(
        history,
        environment="PRODUCTION",
        current=2533,
        now=datetime(2026, 9, 13, 18, 0, tzinfo=timezone.utc),
    )
    assert windows["day_pnl"] == {"value": -67, "status": "CONFIRMED"}
    assert windows["week_pnl"] == {"value": -1467, "status": "CONFIRMED"}
    assert open_mlb_positions(
        [
            {"ticker": "KXMLBGAME-A", "exchange_index": 3, "open": True},
            {"ticker": "KXWNBAGAME-A", "exchange_index": 0, "open": True},
            {"ticker": "KXMLBGAME-B", "position_hundredths": 0, "open": False},
        ]
    ) == 1


def test_kalshi_sync_skipped_does_not_invent(monkeypatch, tmp_path):
    from roller.jump.catalog.connection import handle_status, sync_kalshi

    _isolate(monkeypatch, tmp_path)
    monkeypatch.setenv("JUMP_SKIP_KALSHI", "1")
    body = sync_kalshi()
    assert body["ok"] is False
    assert body["status"] == "OBSERVATION_UNAVAILABLE"
    assert body["honesty"]["sharpe"] == "UNAVAILABLE"
    status = handle_status()
    assert status["metrics"]["sharpe"]["status"] == "UNAVAILABLE"
    assert status["metrics"]["sharpe"]["value"] is None


def test_kalshi_sync_ingests_new_mlb_fills_only(monkeypatch, tmp_path):
    from roller.jump.catalog.connection import sync_kalshi
    from roller.jump.catalog.store import persist_origin

    _isolate(monkeypatch, tmp_path)
    persist_origin({"bot_one_first_fill_ts": "2026-08-24T23:18:58Z"})
    existing = {
        "jump_trade_id": "already",
        "bot_id": "mlb-bot-one",
        "environment": "PRODUCTION",
        "kalshi_trade_id": "trade-1",
        "kalshi_fill_id": "fill-1",
        "ticker": "KXMLBGAME-A",
        "qty": 7,
        "yes_price_cents": 81,
        "exchange_ts": "2026-09-10T18:00:00Z",
        "source": "ledger",
        "result": "UNAVAILABLE",
    }
    (tmp_path / "catalog" / "trades.jsonl").write_text(json.dumps(existing) + "\n", encoding="utf-8")

    def _book(_env: str) -> dict:
        return {
            "ok": True,
            "status": "CONFIRMED",
            "current_cents": 2533,
            "balance_dollars": "49.5211",
            "balance_breakdown": [
                {"exchange_index": 0, "balance": "24.1894"},
                {"exchange_index": 3, "balance": "25.3317"},
            ],
            "fills": [
                {
                    "trade_id": "trade-1",
                    "fill_id": "fill-1",
                    "ticker": "KXMLBGAME-A",
                    "qty": 7,
                    "yes_price_cents": 81,
                    "exchange_ts": "2026-09-10T18:00:00Z",
                },
                {
                    "trade_id": "trade-2",
                    "fill_id": "fill-2",
                    "ticker": "KXMLBGAME-B",
                    "qty": 4,
                    "yes_price_cents": 80,
                    "exchange_ts": "2026-09-11T18:00:00Z",
                },
                {
                    "trade_id": "trade-nba",
                    "fill_id": "fill-nba",
                    "ticker": "KXNBAGAME-X",
                    "exchange_index": 0,
                    "qty": 1,
                    "yes_price_cents": 50,
                    "exchange_ts": "2026-09-11T18:00:00Z",
                },
            ],
            "positions": [
                {"ticker": "KXMLBGAME-OPEN", "exchange_index": 3, "open": True, "position_hundredths": 700},
                {"ticker": "KXNBAGAME-X", "exchange_index": 0, "open": True, "position_hundredths": 100},
            ],
        }

    monkeypatch.setattr("roller.jump.catalog.connection.fetch_connection", _book)
    body = sync_kalshi(now=datetime(2026, 9, 13, 18, 0, tzinfo=timezone.utc))
    assert body["ok"] is True
    assert body["added"] == 1
    rows = [
        json.loads(line)
        for line in (tmp_path / "catalog" / "trades.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == 2
    assert {row["kalshi_trade_id"] for row in rows} == {"trade-1", "trade-2"}
    assert all(str(row.get("ticker") or "").startswith("KXMLBGAME") or row.get("kalshi_trade_id") == "trade-1" for row in rows)
    book = json.loads((tmp_path / "catalog" / "kalshi_book.json").read_text(encoding="utf-8"))
    assert "fills" not in book["books"]["PRODUCTION"]
    assert book["books"]["PRODUCTION"]["fill_n"] == 3
    assert book["books"]["PRODUCTION"]["position_n"] == 1
    bankroll = json.loads((tmp_path / "catalog" / "bankroll.json").read_text(encoding="utf-8"))
    assert bankroll["books"]["PRODUCTION"]["current_cents"] == 2533
    assert body["metrics"]["sharpe"]["value"] is None
    assert body["metrics"]["positions"] == {"value": 1, "status": "CONFIRMED"}


def test_no_credentials_in_catalog():
    root = Path(__file__).resolve().parents[1] / "roller" / "jump" / "catalog"
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token in _BANNED:
            assert token not in text, f"{path} contains {token}"
