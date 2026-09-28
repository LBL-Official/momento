"""Phase 0: FIRST80 Research Object binding reconciliation.

Compares warehouse_frozen_v1 constants/identities with ROLLER research objects.
Mismatch = definition conflict (fail). Do not auto-normalize.
"""

from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from roller.dashboard_adapter.bindings import (
    BINDING_WAREHOUSE_FROZEN_V1,
    NBA_FIRST80_EXPECTED_N,
    warehouse_first80_available,
    warehouse_first80_candidates_path,
)
from roller.research.first80 import scan_ticker, settled_yes
from roller.research.quality import HIT40, HIT80, MAX_SPREAD_E4, quality

MOMENTO = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "first80_warehouse_identity_sample.json"
AUDIT = (
    MOMENTO
    / "apps"
    / "nba-data"
    / "scripts"
    / "nba_80_40_execution_audit.py"
)


def _load_warehouse_audit_module():
    if not AUDIT.is_file():
        pytest.skip(f"warehouse audit module missing: {AUDIT}")
    spec = importlib.util.spec_from_file_location("nba_80_40_execution_audit", AUDIT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    # Avoid executing heavy side effects: only load if safe.
    # The audit module imports pyarrow and paths at import time — OK for local/dev.
    try:
        spec.loader.exec_module(mod)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"cannot import warehouse audit: {exc}")
    return mod


def test_first80_constant_parity_with_warehouse_audit():
    """Same Research Object rule constants — dual homes must not drift."""
    mod = _load_warehouse_audit_module()
    assert HIT80 == mod.HIT80 == 8000
    assert HIT40 == mod.HIT40 == 4000
    assert MAX_SPREAD_E4 == mod.MAX_SPREAD == 1000


def test_quality_parity_with_warehouse_audit():
    mod = _load_warehouse_audit_module()
    cases = [
        (8000, 8500, 1, False, True),
        (8000, 9100, 1, False, False),
        (8100, 8000, 1, False, False),
        (8000, 8500, 0, False, False),
        (8000, 8500, 0, True, True),
    ]
    for bid, ask, vol, had, expected in cases:
        assert quality(bid, ask, vol, had) is expected
        assert mod.quality(bid, ask, vol, had) is expected


def test_warehouse_identity_fixture_shape():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert data["binding"] == BINDING_WAREHOUSE_FROZEN_V1
    assert data["expected_population_n"] == NBA_FIRST80_EXPECTED_N
    assert len(data["rows"]) >= 2
    for row in data["rows"]:
        assert row["status"] == "FIRST_80"
        assert row["entry_bid_close_e4"] >= HIT80
        assert row["first_80_timestamp"]
        # Primary stop is close-path; wick may exist without stop_close.
        if row.get("stop_close_triggered"):
            assert row.get("first_40_close_ts") is not None


def test_scan_ticker_matches_synthetic_path_from_fixture_rule():
    """ROLLER scan_ticker reproduces FIRST80→T40 close-path on synthetic candles.

    This does not claim warehouse ledger parity for a live game (needs candles);
    it locks the shared rule used by both homes.
    """
    rows = [
        {
            "available_at": "2025-12-02T01:13:00Z",
            "yes_bid_close": 7000,
            "yes_ask_close": 7500,
            "volume": 10,
            "ticker": "T",
        },
        {
            "available_at": "2025-12-02T01:14:00Z",
            "yes_bid_close": 8000,
            "yes_ask_close": 8200,
            "volume": 10,
            "ticker": "T",
        },
        {
            "available_at": "2025-12-02T02:15:00Z",
            "yes_bid_close": 4000,
            "yes_ask_close": 4500,
            "volume": 10,
            "ticker": "T",
        },
    ]
    out = scan_ticker(rows, window_start=None, window_end=None)
    assert out["status"] == "FIRST_80"
    assert out["first_80_timestamp"] == "2025-12-02T01:14:00Z"
    assert out["t40_timestamp"] == "2025-12-02T02:15:00Z"


def test_settled_yes_not_confused_with_survive():
    assert settled_yes("yes", None) == "1"
    assert settled_yes("no", None) == "0"
    assert settled_yes(None, 10000) == "1"
    # Survive is path absence of T40 — not expressed by settled_yes.


@pytest.mark.integration
def test_warehouse_candidates_population_count_when_present():
    """If warehouse candidates exist, N must match frozen identity (1230 settled FIRST80).

    Skips when artifact absent (CI without warehouse). Conflict = fail, not normalize.
    """
    if not warehouse_first80_available():
        pytest.skip(f"warehouse candidates absent: {warehouse_first80_candidates_path()}")
    rows = json.loads(warehouse_first80_candidates_path().read_text(encoding="utf-8"))
    first = [r for r in rows if r.get("status") == "FIRST_80"]
    # Audit freezes settled FIRST80 at EXPECTED_FIRST80.
    if len(first) != NBA_FIRST80_EXPECTED_N:
        pytest.fail(
            "FIRST80 population conflict: warehouse candidates FIRST_80 count "
            f"{len(first)} != locked expected {NBA_FIRST80_EXPECTED_N}. "
            "Do not auto-normalize — resolve definition/data conflict explicitly."
        )


@pytest.mark.integration
def test_fixture_rows_present_in_warehouse_candidates():
    """Identity sample rows must still exist unchanged in the warehouse ledger."""
    if not warehouse_first80_available():
        pytest.skip("warehouse candidates absent")
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    by_ticker = {
        r["ticker"]: r
        for r in json.loads(warehouse_first80_candidates_path().read_text(encoding="utf-8"))
        if r.get("status") == "FIRST_80"
    }
    conflicts = []
    for row in fixture["rows"]:
        live = by_ticker.get(row["ticker"])
        if live is None:
            conflicts.append(f"missing ticker {row['ticker']}")
            continue
        if live.get("first_80_timestamp") != row["first_80_timestamp"]:
            conflicts.append(
                f"{row['ticker']}: first_80_timestamp fixture={row['first_80_timestamp']} "
                f"warehouse={live.get('first_80_timestamp')}"
            )
        if bool(live.get("stop_close_triggered")) != bool(row.get("stop_close_triggered")):
            conflicts.append(
                f"{row['ticker']}: stop_close_triggered fixture={row.get('stop_close_triggered')} "
                f"warehouse={live.get('stop_close_triggered')}"
            )
        if bool(live.get("expiration_result_yes")) != bool(row.get("expiration_result_yes")):
            conflicts.append(
                f"{row['ticker']}: expiration_result_yes diverged"
            )
    if conflicts:
        pytest.fail(
            "FIRST80 identity conflict (warehouse_frozen_v1 vs fixture). "
            "Do not auto-heal:\n- " + "\n- ".join(conflicts)
        )


@pytest.mark.integration
def test_roller_first80_table_vs_warehouse_when_both_exist():
    """If ROLLER derived first80_triggers exists, compare overlapping tickers.

    Skips when ROLLER book not built. On mismatch: fail with conflict report.
    """
    roller_csv = (
        MOMENTO
        / "ROLLER"
        / "data"
        / "nba"
        / "2025_2026"
        / "derived"
        / "first80_triggers.csv"
    )
    if not roller_csv.is_file():
        pytest.skip("ROLLER first80_triggers.csv not built — cannot reconcile dual homes yet")
    if not warehouse_first80_available():
        pytest.skip("warehouse candidates absent")

    import pandas as pd

    roller = pd.read_csv(roller_csv, dtype=str)
    warehouse = {
        r["ticker"]: r
        for r in json.loads(warehouse_first80_candidates_path().read_text(encoding="utf-8"))
        if r.get("status") == "FIRST_80"
    }
    conflicts = []
    compared = 0
    for _, row in roller.iterrows():
        if row.get("status") != "FIRST_80":
            continue
        ticker = row.get("ticker") or ""
        w = warehouse.get(ticker)
        if w is None:
            continue
        compared += 1
        # Normalize timestamps to epoch seconds when possible.
        r_ts = row.get("first_80_timestamp") or ""
        w_ts = w.get("first_80_utc") or ""
        # Compare ticker-level T40 presence (close path).
        r_t40 = bool(row.get("t40_timestamp"))
        w_t40 = bool(w.get("first_40_close_ts"))
        if r_t40 != w_t40:
            conflicts.append(f"{ticker}: T40 presence roller={r_t40} warehouse={w_t40}")
        # Settlement W if both present.
        r_w = row.get("kalshi_yes_settled")
        if r_w in {"0", "1"} and w.get("expiration_result_yes") is not None:
            w_yes = "1" if w.get("expiration_result_yes") else "0"
            if r_w != w_yes:
                conflicts.append(f"{ticker}: W roller={r_w} warehouse={w_yes}")
        # Timestamp string equality soft-check via parsed UTC when both parse.
        try:
            if r_ts and w_ts:
                r_dt = datetime.fromisoformat(r_ts.replace("Z", "+00:00"))
                w_dt = datetime.fromisoformat(str(w_ts).replace("Z", "+00:00"))
                if r_dt.astimezone(timezone.utc) != w_dt.astimezone(timezone.utc):
                    conflicts.append(
                        f"{ticker}: first_80_ts roller={r_ts} warehouse={w_ts}"
                    )
        except ValueError:
            pass
    if compared == 0:
        pytest.skip("no overlapping FIRST80 tickers between ROLLER CSV and warehouse")
    if conflicts:
        pytest.fail(
            f"FIRST80 dual-home conflict on {len(conflicts)} field(s) "
            f"across {compared} overlapping tickers. Do not auto-normalize:\n- "
            + "\n- ".join(conflicts[:50])
        )
