"""Vital observe must stay reachable while warehouse research is running.

Does not change Confirm & Run execute/compiler/load_dataset.
Does not change MLB 001 / Risk / Kalshi submit.
"""

from __future__ import annotations

import asyncio
import sys
import threading
import time
from pathlib import Path

ROLLER_ROOT = Path(__file__).resolve().parents[1]


def _app():
    sys.path.insert(0, str(ROLLER_ROOT / "scripts"))
    import terminal_api

    return terminal_api.app


def test_vital_health_during_warehouse_execute(monkeypatch):
    entered = threading.Event()
    release = threading.Event()

    def _slow_execute(*_args, **_kwargs):
        entered.set()
        if not release.wait(timeout=8):
            raise AssertionError("warehouse execute was not released")
        return {"ok": True, "n": 0, "http_200_not_running": True}

    monkeypatch.setattr(
        "roller.warehouse.frontend_contract.execute_frontend_research",
        _slow_execute,
    )

    async def _run() -> None:
        from httpx import ASGITransport, AsyncClient

        transport = ASGITransport(app=_app())
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            execute_task = asyncio.create_task(
                client.post("/warehouse-research/execute", json={"question": {}})
            )
            for _ in range(80):
                if entered.is_set():
                    break
                await asyncio.sleep(0.05)
            assert entered.is_set(), "warehouse execute never entered the worker thread"

            started = time.perf_counter()
            health = await client.get("/health")
            vital = await client.get("/vital/health")
            elapsed_ms = (time.perf_counter() - started) * 1000
            release.set()
            executed = await execute_task

        assert health.status_code == 200
        assert health.json()["reachable_during_execute"] is True
        assert vital.status_code == 200
        assert vital.json()["product"] == "Vital"
        assert vital.json()["http_200_not_running"] is True
        assert elapsed_ms < 1500
        assert executed.status_code == 200
        assert executed.json()["ok"] is True

    asyncio.run(_run())
