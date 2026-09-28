"""Lease-owned ingestion for Ontologic X."""

from __future__ import annotations

import os
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from roller.ontologic_x import LIVE_EXECUTION, METHOD
from roller.ontologic_x.identity import fetch_nba_catalog
from roller.ontologic_x.snapshot import build_snapshot
from roller.ontologic_x.sources import (
    FixtureSource,
    PollGate,
    cadence_for,
    fetch_odds_api,
    fetch_opticodds,
    load_fixture_document,
    provider_mode,
    redact,
)
from roller.ontologic_x.store import Store, utc_stamp

REPO = Path(__file__).resolve().parents[3]
FIXTURE_PATH = REPO / "research" / "ontologic_x" / "fixtures" / "baseline.json"
DB_PATH = REPO / "research" / "ontologic_x" / "v1" / "ontologic_x.sqlite"
PROBE_INTERVAL = timedelta(minutes=10)


def _default_owner() -> str:
    return f"ontologic-x:{os.getpid()}"


class Service:
    def __init__(self, store: Store, transport, owner: str, gate: PollGate | None = None):
        self.store = store
        self.transport = transport
        self.owner = owner
        self.gate = gate or PollGate()
        self._last_probe: datetime | None = None
        self._poll_lock = threading.Lock()

    @classmethod
    def open_default(cls) -> "Service":
        from roller.ontologic_x.collector import load_secrets

        load_secrets()
        document = load_fixture_document(FIXTURE_PATH)
        fixture = FixtureSource(document)
        mode = provider_mode()

        def transport(revision: int) -> dict:
            if mode == "OPTICODDS":
                result = fetch_opticodds([])
            elif mode == "ODDS_API":
                result = fetch_odds_api()
            else:
                return fixture.fetch(revision)
            result["nba_games"] = []
            result["canonical_games"] = []
            seconds, label = cadence_for(mode)
            result["cadence_label"] = label
            result["interval_seconds"] = seconds
            return result

        return cls(Store(DB_PATH), transport, _default_owner())

    def tick(self, now: datetime, *, probe: bool = False) -> dict:
        if not self._poll_lock.acquire(blocking=False):
            return {"polled": False, "ok": False, "reason": "IN_PROCESS_LOCK", "lease_owner": self.owner}
        try:
            return self._tick_locked(now, probe=probe)
        finally:
            self._poll_lock.release()

    def _tick_locked(self, now: datetime, *, probe: bool) -> dict:
        if not self.store.try_acquire(self.owner, now):
            return {
                "polled": False,
                "ok": False,
                "reason": "LEASE_HELD",
                "lease_owner": self.store.lease_owner(),
            }
        if not self.gate.allowed(now):
            self.store.record_poll(now, self.owner, False, "BACKOFF", "BACKOFF")
            return {"polled": False, "ok": False, "reason": "BACKOFF", "lease_owner": self.owner}
        revision = self.store.successful_polls()
        try:
            fetched = self.transport(revision)
        except Exception as exc:  # noqa: BLE001 — transport failures back off, they do not invent quotes
            delay = self.gate.failure(now)
            self.store.record_poll(now, self.owner, False, "ERROR", redact(str(exc))[:240])
            return {"polled": True, "ok": False, "reason": "TRANSPORT", "backoff_seconds": delay, "lease_owner": self.owner}
        self.gate.success()
        mode = str(fetched.get("mode") or "FIXTURE")
        if fetched.get("error") and mode != "FIXTURE":
            poll_id = self.store.record_poll(now, self.owner, False, mode, str(fetched.get("error")))
            probed = self.store.probe() or {}
            scheduled = list(probed.get("games") or [])
            if scheduled:
                body, states = build_snapshot(
                    nba_games=scheduled,
                    canonical_games=[],
                    quotes=[],
                    previous={},
                    retrieved_at=utc_stamp(now),
                    snapshot_id=f"ox-{poll_id}",
                    source_label="SOURCE_UNAVAILABLE",
                    mode=mode,
                    cadence_label=str(fetched.get("cadence_label") or mode),
                    rejected=[{"bookmaker": item, "reason": item} for item in fetched.get("rejected") or []],
                )
                body["empty_state"] = "SOURCE_UNAVAILABLE"
                self.store.save_snapshot(body["snapshot_id"], now, body, states)
            else:
                body = {
                    "snapshot_id": f"ox-{poll_id}",
                    "retrieved_at": utc_stamp(now),
                    "method": METHOD,
                    "live_execution": LIVE_EXECUTION,
                    "submits": False,
                    "source_label": "SOURCE_UNAVAILABLE",
                    "mode": mode,
                    "cadence_label": fetched.get("cadence_label"),
                    "preseason_start": None,
                    "preseason_start_source": "SOURCE_UNAVAILABLE",
                    "rejected_books": [{"bookmaker": item, "reason": item} for item in fetched.get("rejected") or []],
                    "games": [],
                    "empty_state": "SOURCE_UNAVAILABLE",
                }
                self.store.save_snapshot(body["snapshot_id"], now, body, self.store.quote_state())
            return {"polled": True, "ok": False, "reason": "SOURCE_UNAVAILABLE", "snapshot_id": body["snapshot_id"], "lease_owner": self.owner}
        poll_id = self.store.record_poll(now, self.owner, True, mode, "ok")
        retrieved = utc_stamp(now)
        nba_games = list(fetched.get("nba_games") or [])
        if mode != "FIXTURE":
            probed = self.store.probe()
            if probed and probed.get("games"):
                nba_games = probed["games"]
        body, states = build_snapshot(
            nba_games=nba_games,
            canonical_games=list(fetched.get("canonical_games") or []),
            quotes=list(fetched.get("quotes") or []),
            previous=self.store.quote_state(),
            retrieved_at=retrieved,
            snapshot_id=f"ox-{poll_id}",
            source_label=str(fetched.get("label") or mode),
            mode=mode,
            cadence_label=str(fetched.get("cadence_label") or mode),
            rejected=list(fetched.get("rejected") or []),
        )
        self.store.save_snapshot(body["snapshot_id"], now, body, states)
        if probe:
            self.maybe_probe(now)
        return {"polled": True, "ok": True, "snapshot_id": body["snapshot_id"], "lease_owner": self.owner}

    def maybe_probe(self, now: datetime) -> dict:
        if self._last_probe is not None and now - self._last_probe < PROBE_INTERVAL:
            current = self.store.probe()
            return current or {"status": "CACHED"}
        self._last_probe = now
        result = fetch_nba_catalog(now)
        self.store.save_probe(
            now,
            str(result.get("status")),
            result.get("preseason_start"),
            str(result.get("season")),
            result.get("detail"),
            list(result.get("games") or []),
        )
        return result

    def health(self) -> dict:
        mode = provider_mode()
        seconds, label = cadence_for(mode)
        body = self.store.current_body() or {}
        probe = self.store.probe()
        return {
            "live_execution": LIVE_EXECUTION,
            "submits": False,
            "method": METHOD,
            "mode": body.get("mode") or mode,
            "source_label": body.get("source_label") or ("FIXTURE" if mode == "FIXTURE" else "SOURCE_UNAVAILABLE"),
            "provider_configured": mode != "FIXTURE",
            "live_connectivity": "BLOCKED",
            "five_second_book_freshness": "NOT_CLAIMED",
            "source_freshness_measured": False,
            "cadence_label": body.get("cadence_label") or label,
            "provider_interval_seconds": seconds,
            "client_refresh_seconds": 5,
            "lease_owner": self.store.lease_owner(),
            "last_successful_poll_at": self.store.last_success(),
            "snapshot_id": body.get("snapshot_id"),
            "retrieved_at": body.get("retrieved_at"),
            "fixture_preseason_start": body.get("preseason_start") if body.get("mode") == "FIXTURE" else None,
            "nba_probe": None
            if probe is None
            else {
                "status": probe.get("status"),
                "season": probe.get("season"),
                "preseason_start": probe.get("preseason_start"),
                "probed_at": probe.get("probed_at"),
                "detail": probe.get("detail"),
            },
            "bookmaker": "betonline" if mode == "BETONLINE" else body.get("bookmaker") or "williamhill",
            "williamhill_us_key": "Caesars on the current Odds API catalog; not accepted as William Hill",
            "empty_state": body.get("empty_state") if body.get("empty_state") else (None if mode != "FIXTURE" else "NO_CREDENTIALS"),
        }

    def board(self, *, date: str | None = None, view: str | None = None) -> dict:
        body = self.store.current_body()
        if body is None:
            self.tick(datetime.now(timezone.utc), probe=False)
            body = self.store.current_body() or {"games": [], "empty_state": "NO_CREDENTIALS"}
        if body.get("mode") == "BETONLINE":
            from roller.ontologic_x.betonline.collect import annotate_age

            body = annotate_age(body, datetime.now(timezone.utc))
        games = list(body.get("games") or [])
        if date:
            games = [game for game in games if str(game.get("start_utc") or "").startswith(date)]
        if view in {"live", "upcoming", "completed"}:
            games = [game for game in games if game.get("status") == view]
        payload = dict(body)
        payload["games"] = games
        payload["live_execution"] = False
        payload["submits"] = False
        return payload

    def game(self, game_id: str) -> dict | None:
        body = self.board()
        for game in body.get("games") or []:
            if game.get("id") == game_id:
                return game
        return None

    def refresh_game_state(self, now: datetime) -> None:
        """Scoreboard period and clock only. This path does not buy odds."""
        self.maybe_probe(now)
        probed = self.store.probe() or {}
        for game in probed.get("games") or []:
            if not game.get("nba_game_id"):
                continue
            self.store.save_game_state(
                {
                    "nba_game_id": game.get("nba_game_id"),
                    "period": game.get("period"),
                    "clock": game.get("clock"),
                    "status": game.get("status"),
                    "observed_at": utc_stamp(now),
                    "source": "nba_scoreboard",
                    "season_phase": game.get("season_type"),
                }
            )
        from roller.ontologic_x.collector import LiveTransport, merge_unquoted_schedule, refresh_listing

        games = list(probed.get("games") or [])
        refresh_listing(self.store, LiveTransport(), games, now)
        merge_unquoted_schedule(self.store, games, now)

    def history(self) -> dict:
        return {
            "live_execution": False,
            "submits": False,
            "method": METHOD,
            "snapshots": self.store.history(),
        }
