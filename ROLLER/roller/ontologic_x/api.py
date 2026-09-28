"""HTTP handlers for /momento/ontologic-x. One leased poller per process."""

from __future__ import annotations

import threading
from datetime import datetime, timezone

from roller.ontologic_x.service import Service
from roller.ontologic_x.sources import cadence_for, provider_mode

_lock = threading.Lock()
_service: Service | None = None
_started = False


def get_service() -> Service:
    global _service, _started
    with _lock:
        if _service is None:
            _service = Service.open_default()
        if not _started:
            _started = True
            now = datetime.now(timezone.utc)
            if provider_mode() == "ODDS_API":
                _rehearse(_service, now)
            elif provider_mode() == "BETONLINE":
                _collect_betonline(_service, now)
            elif _service.store.current_body() is None:
                _service.tick(now, probe=False)
            threading.Thread(target=_loop, name="ontologic-x", daemon=True).start()
        return _service


def _rehearse(service: Service, now: datetime) -> None:
    from roller.ontologic_x.collector import LiveTransport, rehearse
    from roller.ontologic_x.identity import fetch_nba_catalog

    if service.store.meta_get("rehearsal") == "done":
        from roller.ontologic_x.collector import merge_unquoted_schedule

        probed = service.store.probe() or {}
        merge_unquoted_schedule(service.store, list(probed.get("games") or []), now)
        return
    catalog = fetch_nba_catalog(now)
    service.store.save_probe(
        now,
        str(catalog.get("status")),
        catalog.get("preseason_start"),
        str(catalog.get("season")),
        catalog.get("detail"),
        list(catalog.get("games") or []),
    )
    rehearse(service.store, LiveTransport(), list(catalog.get("games") or []), now)


def _loop() -> None:
    service = _service
    if service is None:
        return
    while True:
        mode = provider_mode()
        if mode == "ODDS_API":
            threading.Event().wait(600)
            try:
                service.refresh_game_state(datetime.now(timezone.utc))
            except Exception as exc:
                from roller.ontologic_x.sources import redact

                service.store.record_poll(datetime.now(timezone.utc), service.owner, False, "ERROR", redact(str(exc))[:240])
            continue
        if mode == "BETONLINE":
            seconds, _label = cadence_for(mode)
            threading.Event().wait(seconds)
            try:
                _collect_betonline(service, datetime.now(timezone.utc))
            except Exception as exc:
                from roller.ontologic_x.sources import redact

                service.store.record_poll(datetime.now(timezone.utc), service.owner, False, "ERROR", redact(str(exc))[:240])
            continue
        seconds, _label = cadence_for(mode)
        threading.Event().wait(seconds)
        try:
            service.tick(datetime.now(timezone.utc), probe=True)
        except Exception as exc:
            from roller.ontologic_x.sources import redact

            service.store.record_poll(datetime.now(timezone.utc), service.owner, False, "ERROR", redact(str(exc))[:240])


def handle_health() -> dict:
    return get_service().health()


def handle_board(date: str | None = None, view: str | None = None) -> dict:
    return get_service().board(date=date, view=view)


def handle_game(game_id: str) -> dict:
    game = get_service().game(game_id)
    if game is None:
        return {"live_execution": False, "submits": False, "empty_state": "UNMATCHED", "id": game_id}
    return game


def handle_history() -> dict:
    return get_service().history()


def _collect_betonline(service: Service, now: datetime) -> None:
    from roller.ontologic_x.betonline.collect import collect
    from roller.ontologic_x.betonline.client import Client
    from roller.ontologic_x.identity import fetch_nba_catalog

    probed = service.store.probe() or {}
    games = list(probed.get("games") or [])
    if not games:
        catalog = fetch_nba_catalog(now)
        games = list(catalog.get("games") or [])
        if games:
            service.store.save_probe(
                now,
                str(catalog.get("status")),
                catalog.get("preseason_start"),
                str(catalog.get("season")),
                catalog.get("detail"),
                games,
            )
    collect(service.store, Client(), games, now)


def handle_coverage() -> dict:
    if provider_mode() == "BETONLINE":
        from roller.ontologic_x.betonline.collect import betonline_coverage

        return betonline_coverage(get_service().store)
    from roller.ontologic_x.collector import coverage_view

    return coverage_view(get_service().store)


def handle_credits() -> dict:
    report = handle_coverage()
    return {
        "live_execution": False,
        "submits": False,
        "policy": report["policy"],
        "measured": report["measured"],
        "buckets": report["buckets"],
        "spent": report["spent"],
        "snapshot_collection": report["snapshot_collection"],
        "detailed_interval_seconds": report["detailed_interval_seconds"],
        "illustrative_costs": report["illustrative_costs"],
    }
