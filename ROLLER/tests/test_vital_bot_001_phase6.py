"""Vital Bot Standard Phase 6 — one row per market. Host wins; confirmed ticker only."""

from __future__ import annotations

import json

from roller.vital.mlb_001.market import game_label, parse_mlb_ticker
from roller.vital.mlb_001.trade_row import apply_standard_row, basis_points
from roller.vital.naming import BOT_STANDARD_PHASE
from roller.vital.reconcile import reconstruct_trade, reconcile_bot
from roller.vital.store import seed_mlb_001
from roller.vital.versions import BOT_ID


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
    (tmp_path / "catalog").mkdir(exist_ok=True)
    seed_mlb_001(root=tmp_path)
    return state


def _fill(*, ts: str, premium: int, qty: int, price: int, kind: str, fill_id: str, ticker: str | None = None) -> dict:
    row = {
        "premium": {"cents": premium},
        "quantity": {"qty": qty},
        "price": {"cents": price},
        "fee": {"amount": {"cents": 0}, "kind": kind},
        "exchange_ts": ts,
        "side": "yes",
        "fill_id": fill_id,
    }
    if ticker:
        row["ticker"] = ticker
    return row


def _closed(*, ticker: str = "KXMLBGAME-26AUG291915TEXMIL-MIL", pid: int = 184) -> dict:
    return {
        "id": pid,
        "strategy_id": 1,
        "lifecycle": "Flat",
        "filled_quantity": {"qty": 0},
        "ticker": ticker,
        "side": "yes",
        "fill_history": [
            _fill(ts="2026-09-14T02:31:00Z", premium=405, qty=5, price=81, kind="Entry", fill_id="e", ticker=ticker),
            _fill(ts="2026-09-14T03:10:00Z", premium=485, qty=5, price=97, kind="Liquidation", fill_id="x", ticker=ticker),
        ],
    }


def _write_runtime(state, positions, *, identity=None, snapshot=None):
    payload = {"tracker": {"positions": positions}}
    if identity is not None:
        payload["identity"] = identity
    (state / "live-runtime.json").write_text(json.dumps(payload), encoding="utf-8")
    if snapshot is not None:
        (state / "weekly-snapshot.json").write_text(json.dumps(snapshot), encoding="utf-8")


def test_phase_6_marked():
    assert BOT_STANDARD_PHASE["6"] == "IMPLEMENTED"


def test_ticker_game_label():
    parsed = parse_mlb_ticker("KXMLBGAME-26AUG291915TEXMIL-MIL")
    assert parsed is not None
    assert parsed["away"] == "TEX"
    assert parsed["home"] == "MIL"
    assert parsed["side"] == "MIL"
    assert parsed["date"] == "2026-08-29"
    assert game_label("KXMLBGAME-26JUN18NYYBOS-NYY") == "NYY @ BOS YES NYY"
    assert game_label("KXMLBGAME-26SEP131340HOUTB-TB") == "HOU @ TB YES TB"
    assert game_label("KXMLBGAME-26SEP131340HOUTB-HOU") == "HOU @ TB YES HOU"
    assert game_label("KXMLBGAME-26SEP041915DETCLEG2-DET") == "DET @ CLE YES DET"
    assert game_label("KXMLBGAME-26SEP041410DETCLEG1-DET") == "DET @ CLE YES DET"
    assert game_label("KXMLBGAME-TEST") is None
    assert game_label(None) is None


def test_basis_points_integer_only():
    assert basis_points(405, 5000) == 810
    assert basis_points(80, 405) == 1975
    assert basis_points(None, 5000) is None
    assert basis_points(405, 0) is None
    assert basis_points(-80, 405) == -1975


def test_closed_row_with_in_week_snapshot(monkeypatch, tmp_path):
    state = _isolate(monkeypatch, tmp_path)
    _write_runtime(
        state,
        [_closed()],
        snapshot={"bankroll": {"cents": 5000}, "week_start_utc": "2026-09-08T07:00:00Z"},
    )
    trade = reconcile_bot(BOT_ID, root=tmp_path)["trades"][0]
    assert trade["status"] == "CLOSED"
    assert trade["game"]["value"] == "TEX @ MIL YES MIL"
    assert trade["entry_price_cents"]["value"] == 81
    assert trade["exit_price_cents"]["value"] == 97
    assert trade["amount_traded_cents"]["value"] == 405
    assert trade["amount_exited_cents"]["value"] == 485
    assert trade["bankroll_at_entry_cents"]["value"] == 5000
    assert trade["pct_bankroll_allocated_bp"]["value"] == 810
    assert trade["pct_bankroll_returned_bp"]["value"] == 970
    assert trade["pct_allocated_pnl_bp"]["value"] == 1975
    assert trade["standard_row"]["market"]["value"] == "KXMLBGAME-26AUG291915TEXMIL-MIL"


def test_factory_bankroll_is_not_used(monkeypatch, tmp_path):
    state = _isolate(monkeypatch, tmp_path)
    _write_runtime(state, [_closed()])
    trade = reconcile_bot(BOT_ID, root=tmp_path)["trades"][0]
    assert trade["bankroll_at_entry_cents"]["status"] == "OBSERVATION_UNAVAILABLE"
    assert trade["pct_bankroll_allocated_bp"]["status"] == "UNAVAILABLE"
    assert trade["pct_bankroll_allocated_bp"]["value"] is None


def test_snapshot_wrong_week_is_not_bankroll(monkeypatch, tmp_path):
    state = _isolate(monkeypatch, tmp_path)
    _write_runtime(
        state,
        [_closed()],
        snapshot={"bankroll": {"cents": 5000}, "week_start_utc": "2026-08-31T07:00:00Z"},
    )
    trade = reconcile_bot(BOT_ID, root=tmp_path)["trades"][0]
    assert trade["bankroll_at_entry_cents"]["status"] == "OBSERVATION_UNAVAILABLE"


def test_history_at_or_before_entry(monkeypatch, tmp_path):
    state = _isolate(monkeypatch, tmp_path)
    catalog = tmp_path / "catalog"
    (catalog / "bankroll_history.jsonl").write_text(
        json.dumps({"environment": "PRODUCTION", "observed_at": "2026-09-14T02:00:00Z", "current_cents": 4000})
        + "\n"
        + json.dumps({"environment": "PRODUCTION", "observed_at": "2026-09-14T04:00:00Z", "current_cents": 2600})
        + "\n",
        encoding="utf-8",
    )
    _write_runtime(state, [_closed()])
    trade = reconcile_bot(BOT_ID, root=tmp_path)["trades"][0]
    assert trade["bankroll_at_entry_cents"]["value"] == 4000
    assert trade["pct_bankroll_allocated_bp"]["value"] == 1012


def test_history_after_entry_is_future_information(monkeypatch, tmp_path):
    state = _isolate(monkeypatch, tmp_path)
    (tmp_path / "catalog" / "bankroll_history.jsonl").write_text(
        json.dumps({"environment": "PRODUCTION", "observed_at": "2026-09-14T04:00:00Z", "current_cents": 4000})
        + "\n",
        encoding="utf-8",
    )
    _write_runtime(state, [_closed()])
    trade = reconcile_bot(BOT_ID, root=tmp_path)["trades"][0]
    assert trade["bankroll_at_entry_cents"]["status"] == "OBSERVATION_UNAVAILABLE"


def test_open_contract_exits_unavailable(monkeypatch, tmp_path):
    state = _isolate(monkeypatch, tmp_path)
    ticker = "KXMLBGAME-26AUG291915TEXMIL-MIL"
    _write_runtime(
        state,
        [
            {
                "id": 202,
                "strategy_id": 1,
                "lifecycle": "Holding",
                "filled_quantity": {"qty": 5},
                "ticker": ticker,
                "fill_history": [
                    _fill(ts="2026-09-14T02:31:00Z", premium=405, qty=5, price=81, kind="Entry", fill_id="open-e", ticker=ticker),
                ],
            }
        ],
        snapshot={"bankroll": {"cents": 5000}, "week_start_utc": "2026-09-08T07:00:00Z"},
    )
    trade = reconcile_bot(BOT_ID, root=tmp_path)["trades"][0]
    assert trade["status"] == "OPEN"
    assert trade["amount_traded_cents"]["value"] == 405
    assert trade["pct_bankroll_allocated_bp"]["value"] == 810
    assert trade["amount_exited_cents"]["status"] == "UNAVAILABLE"
    assert trade["exit_price_cents"]["status"] == "UNAVAILABLE"
    assert trade["pct_bankroll_returned_bp"]["status"] == "UNAVAILABLE"
    assert trade["pct_allocated_pnl_bp"]["status"] == "UNAVAILABLE"


def test_partial_is_open_for_contract_exit(monkeypatch, tmp_path):
    state = _isolate(monkeypatch, tmp_path)
    ticker = "KXMLBGAME-26AUG291915TEXMIL-MIL"
    _write_runtime(
        state,
        [
            {
                "id": 201,
                "strategy_id": 1,
                "lifecycle": "Holding",
                "filled_quantity": {"qty": 2},
                "ticker": ticker,
                "fill_history": [
                    _fill(ts="2026-09-14T01:00:00Z", premium=567, qty=7, price=81, kind="Entry", fill_id="p-e", ticker=ticker),
                    _fill(ts="2026-09-14T02:00:00Z", premium=485, qty=5, price=97, kind="Liquidation", fill_id="p-x", ticker=ticker),
                ],
            }
        ],
    )
    trade = reconcile_bot(BOT_ID, root=tmp_path)["trades"][0]
    assert trade["status"] == "PARTIAL"
    assert trade["exit_amount"]["value"] == 485
    assert trade["amount_exited_cents"]["status"] == "UNAVAILABLE"
    assert trade["pct_allocated_pnl_bp"]["status"] == "UNAVAILABLE"


def test_identity_resolves_ticker_without_guessing_two_sides(monkeypatch, tmp_path):
    state = _isolate(monkeypatch, tmp_path)
    position = {
        "id": 9,
        "strategy_id": 1,
        "lifecycle": "Flat",
        "filled_quantity": {"qty": 0},
        "market_id": 99,
        "game_id": 1,
        "fill_history": [
            _fill(ts="2026-09-14T02:31:00Z", premium=405, qty=5, price=81, kind="Entry", fill_id="id-e"),
            _fill(ts="2026-09-14T03:10:00Z", premium=485, qty=5, price=97, kind="Liquidation", fill_id="id-x"),
        ],
    }
    _write_runtime(
        state,
        [position],
        identity=[["KXMLBGAME-26AUG291915TEXMIL-MIL", 99, 1]],
    )
    trade = reconcile_bot(BOT_ID, root=tmp_path)["trades"][0]
    assert trade["market"]["value"] == "KXMLBGAME-26AUG291915TEXMIL-MIL"
    assert trade["game"]["value"] == "TEX @ MIL YES MIL"

    two_sides = reconstruct_trade(
        BOT_ID,
        {**position, "market_id": None},
        identity={
            "by_market": {},
            "by_game": {
                "1": [
                    "KXMLBGAME-26AUG291915TEXMIL-MIL",
                    "KXMLBGAME-26AUG291915TEXMIL-TEX",
                ]
            },
        },
    )
    assert two_sides is not None
    assert two_sides["market"]["status"] == "OBSERVATION_UNAVAILABLE"
    assert two_sides["game"]["status"] == "OBSERVATION_UNAVAILABLE"


def test_catalog_same_ticker_still_does_not_invent_trades(monkeypatch, tmp_path):
    monkeypatch.setenv("VITAL_ROOT", str(tmp_path))
    catalog = tmp_path / "catalog"
    catalog.mkdir()
    monkeypatch.setenv("JUMP_CATALOG_ROOT", str(catalog))
    monkeypatch.delenv("VITAL_BOT_STATE_DIR", raising=False)
    monkeypatch.delenv("VITAL_BOT_RUNTIME_PATH", raising=False)
    ticker = "KXMLBGAME-26SEP121915CWSSTL-STL"
    lines = []
    for i, fill_id in enumerate(("a", "b")):
        lines.append(
            json.dumps(
                {
                    "jump_trade_id": f"{fill_id}" * 32,
                    "bot_id": "mlb-bot-one",
                    "environment": "PRODUCTION",
                    "kalshi_fill_id": f"00000000-0000-0000-0000-00000000000{i}",
                    "ticker": ticker,
                    "qty": 7,
                    "yes_price_cents": 81,
                    "exchange_ts": "2026-09-13T00:42:35Z",
                    "source": "kalshi",
                }
            )
        )
    (catalog / "trades.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    seed_mlb_001(root=tmp_path)
    view = reconcile_bot(BOT_ID, root=tmp_path)
    assert view["fills_status"] == "CONFIRMED"
    assert len(view["fills"]) == 2
    assert view["trades_status"] == "CONFIRMED"
    assert view["trades"] is not None
    assert len(view["trades"]) == 1
    assert view["trades"][0]["market"]["value"] == ticker
    assert view["trades"][0]["source"] == "KALSHI_ACCOUNT"
    assert view["catalog_does_not_group"] is True
    assert view["grouping"] == "kalshi_ticker"


def test_ledger_fills_without_ticker_still_do_not_invent_trades(monkeypatch, tmp_path):
    monkeypatch.setenv("VITAL_ROOT", str(tmp_path))
    catalog = tmp_path / "catalog"
    catalog.mkdir()
    monkeypatch.setenv("JUMP_CATALOG_ROOT", str(catalog))
    monkeypatch.delenv("VITAL_BOT_STATE_DIR", raising=False)
    monkeypatch.delenv("VITAL_BOT_RUNTIME_PATH", raising=False)
    (catalog / "trades.jsonl").write_text(
        json.dumps(
            {
                "jump_trade_id": "a" * 32,
                "bot_id": "mlb-bot-one",
                "environment": "PRODUCTION",
                "kalshi_fill_id": "d4ead132a4f7ad62",
                "qty": 7,
                "yes_price_cents": 83,
                "premium_cents": 581,
                "exchange_ts": "2026-08-24T23:18:58Z",
                "fee_kind": "Entry",
                "source": "ledger",
                "ticker": None,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    seed_mlb_001(root=tmp_path)
    view = reconcile_bot(BOT_ID, root=tmp_path)
    assert view["fills_status"] == "CONFIRMED"
    assert view["fills"][0]["market"]["status"] == "OBSERVATION_UNAVAILABLE"
    assert view["trades"] is None
    assert view["trades_status"] == "OBSERVATION_UNAVAILABLE"


def test_kalshi_observe_is_read_only_and_fail_closed(monkeypatch, tmp_path):
    monkeypatch.setenv("VITAL_ROOT", str(tmp_path))
    monkeypatch.setenv("JUMP_SKIP_KALSHI", "1")
    seed_mlb_001(root=tmp_path)
    from roller.vital.api import handle_kalshi, handle_kalshi_observe

    status = handle_kalshi(BOT_ID, root=tmp_path)
    assert status["read_only"] is True
    assert status["submits"] is False
    assert status["status"] == "OBSERVATION_UNAVAILABLE"
    observed = handle_kalshi_observe(BOT_ID, root=tmp_path)
    assert observed["read_only"] is True
    assert observed["submits"] is False
    assert observed["status"] == "OBSERVATION_UNAVAILABLE"


def test_host_position_wins_over_ticker_grouping(monkeypatch, tmp_path):
    state = _isolate(monkeypatch, tmp_path)
    catalog = tmp_path / "catalog"
    extra = "KXMLBGAME-26SEP121915CWSSTL-STL"
    (catalog / "trades.jsonl").write_text(
        json.dumps(
            {
                "jump_trade_id": "c" * 32,
                "bot_id": "mlb-bot-one",
                "environment": "PRODUCTION",
                "kalshi_fill_id": "11111111-1111-1111-1111-111111111111",
                "ticker": extra,
                "qty": 7,
                "yes_price_cents": 81,
                "exchange_ts": "2026-09-13T00:42:35Z",
                "source": "kalshi",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    _write_runtime(state, [_closed()])
    view = reconcile_bot(BOT_ID, root=tmp_path)
    assert view["grouping"] == "host_position"
    assert view["trades"] is not None
    assert len(view["trades"]) == 1
    assert view["trades"][0]["source"] == "HOST_LEDGER"
    assert view["trades"][0]["market"]["value"] == "KXMLBGAME-26AUG291915TEXMIL-MIL"


def test_settlement_no_is_zero_payout():
    from roller.vital.mlb_001.ticker_trades import apply_settlement, reconstruct_ticker_trades

    fills = [
        {
            "source": "KALSHI_ACCOUNT",
            "fill_id": "one",
            "venue_fill_id": "v1",
            "market": {"status": "CONFIRMED", "value": "KXMLBGAME-26SEP131410CINMIL-MIL"},
            "timestamp": {"status": "CONFIRMED", "value": "2026-09-13T19:34:11Z"},
            "contracts": {"status": "CONFIRMED", "value": 7},
            "price_cents": {"status": "CONFIRMED", "value": 82},
            "amount_cents": {"status": "CONFIRMED", "value": 574},
            "fee_kind": {"status": "OBSERVATION_UNAVAILABLE", "value": None},
        },
        {
            "source": "KALSHI_ACCOUNT",
            "fill_id": "dup",
            "venue_fill_id": "v1",
            "market": {"status": "CONFIRMED", "value": "KXMLBGAME-26SEP131410CINMIL-MIL"},
            "timestamp": {"status": "CONFIRMED", "value": "2026-09-13T19:34:11Z"},
            "contracts": {"status": "CONFIRMED", "value": 7},
            "price_cents": {"status": "CONFIRMED", "value": 82},
            "amount_cents": {"status": "CONFIRMED", "value": 574},
            "fee_kind": {"status": "OBSERVATION_UNAVAILABLE", "value": None},
        },
    ]
    trades = reconstruct_ticker_trades(
        BOT_ID,
        fills,
        settlements={
            "KXMLBGAME-26SEP131410CINMIL-MIL": {
                "result": "no",
                "settlement_value_cents": 0,
                "settlement_ts": "2026-09-13T20:52:00Z",
                "status": "CONFIRMED",
            }
        },
    )
    assert len(trades) == 1
    trade = trades[0]
    assert trade["entry_contracts"]["value"] == 7
    assert trade["amount_traded_cents"]["value"] == 574
    assert trade["status"] == "CLOSED"
    assert trade["amount_exited_cents"]["value"] == 0
    assert trade["gross_realized_cents"]["value"] == -574
    assert apply_settlement({"entry_contracts": {"status": "CONFIRMED", "value": 7}}, None)[
        "entry_contracts"
    ]["value"] == 7


def test_ticker_skips_open_rows_without_entry():
    from roller.vital.mlb_001.ticker_trades import reconstruct_ticker_trades

    trades = reconstruct_ticker_trades(
        BOT_ID,
        [
            {
                "source": "KALSHI_ACCOUNT",
                "fill_id": "exit-only",
                "venue_fill_id": "vx",
                "market": {"status": "CONFIRMED", "value": "KXMLBGAME-26SEP112016CWSSTL-STL"},
                "timestamp": {"status": "CONFIRMED", "value": "2026-09-15T20:00:00Z"},
                "contracts": {"status": "CONFIRMED", "value": 1},
                "price_cents": {"status": "CONFIRMED", "value": 50},
                "amount_cents": {"status": "CONFIRMED", "value": 50},
                "fee_kind": {"status": "CONFIRMED", "value": "Liquidation"},
            }
        ],
    )
    assert trades == []


def test_unparseable_ticker_game_unavailable():
    trade = apply_standard_row(
        {
            "status": "CLOSED",
            "market": {"value": "KXMLBGAME-TEST", "status": "CONFIRMED"},
            "entry_date": {"value": "2026-09-14T02:31:00Z", "status": "CONFIRMED"},
            "entry_amount": {"value": 405, "status": "CONFIRMED"},
            "entry_price": {"value": 81, "status": "CONFIRMED"},
            "exit_amount": {"value": 485, "status": "CONFIRMED"},
            "exit_price": {"value": 97, "status": "CONFIRMED"},
        }
    )
    assert trade["game"]["status"] == "OBSERVATION_UNAVAILABLE"
    assert trade["bankroll_at_entry_cents"]["status"] == "OBSERVATION_UNAVAILABLE"
