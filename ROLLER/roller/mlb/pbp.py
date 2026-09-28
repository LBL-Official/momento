"""Parse StatsAPI envelopes into canonical MLB PBP rows.

Scores come from the event row, never the final box.
Outs 3 / strikes 3 are not live states.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from roller.mlb.state import (
    batting_team,
    count_display,
    count_leverage,
    inning_slice,
    live_balls,
    live_outs,
    live_strikes,
    normalize_half,
    runner_category,
)

PBP_COLUMNS = [
    "internal_game_id",
    "source_game_id",
    "event_number",
    "event_timestamp",
    "available_at",
    "ingested_at",
    "availability_quality",
    "timestamp_status",
    "period",
    "clock",
    "inning",
    "half",
    "outs",
    "balls",
    "strikes",
    "count_display",
    "count_leverage",
    "runner_on_1",
    "runner_on_2",
    "runner_on_3",
    "runners",
    "batting_team",
    "home_score",
    "away_score",
    "score_differential_home",
    "event_type",
    "event_description",
    "source_dataset",
    "source_file_hash",
    "pipeline_version",
    "derived_at",
]


def _int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _iso(value: Any) -> str:
    text = str(value or "").strip()
    if text.endswith("+00:00"):
        return text.replace("+00:00", "Z")
    return text


def _flag(value: bool | None) -> str:
    if value is True:
        return "1"
    if value is False:
        return "0"
    return ""


def load_envelope(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "payload" in data:
        return data
    return {"payload": data, "source_game_id": data.get("gamePk") if isinstance(data, dict) else ""}


def _payload(envelope: dict[str, Any]) -> dict[str, Any]:
    payload = envelope.get("payload")
    return payload if isinstance(payload, dict) else envelope


def _base_key(raw: Any) -> int | None:
    text = str(raw or "").upper()
    if text in {"1B", "1", "FIRST"}:
        return 1
    if text in {"2B", "2", "SECOND"}:
        return 2
    if text in {"3B", "3", "THIRD"}:
        return 3
    return None


def _apply_movement(occ: list[bool], movement: dict[str, Any]) -> None:
    start = _base_key((movement or {}).get("start") or (movement or {}).get("originBase"))
    end = _base_key((movement or {}).get("end"))
    is_out = bool((movement or {}).get("isOut"))
    if start in (1, 2, 3):
        occ[start - 1] = False
    if not is_out and end in (1, 2, 3):
        occ[end - 1] = True


def parse_plays(
    envelope: dict[str, Any],
    *,
    internal_game_id: str,
    ingested_at: str,
    pipeline_version: str,
    source_dataset: str = "mlb_statsapi",
    source_file_hash: str = "",
) -> list[dict[str, str]]:
    payload = _payload(envelope)
    source_id = str(envelope.get("source_game_id") or payload.get("gamePk") or "")
    plays = ((payload.get("liveData") or {}).get("plays") or {}).get("allPlays") or []
    occ = [False, False, False]
    rows: list[dict[str, str]] = []
    n = 0
    for play in plays:
        if not isinstance(play, dict):
            continue
        about = play.get("about") or {}
        inning = _int(about.get("inning"))
        half = normalize_half(about.get("halfInning"))
        events = play.get("playEvents") or []
        runners = play.get("runners") or []
        movements_by_idx: dict[int, list[dict[str, Any]]] = {}
        for runner in runners:
            if not isinstance(runner, dict):
                continue
            idx = _int((runner.get("details") or {}).get("playIndex"))
            if idx is None:
                continue
            movements_by_idx.setdefault(idx, []).append(runner.get("movement") or {})
        if not events:
            events = [{}]
        for ev in events:
            if not isinstance(ev, dict):
                continue
            count = ev.get("count") or play.get("count") or {}
            outs = live_outs(count.get("outs"))
            balls = live_balls(count.get("balls"))
            strikes = live_strikes(count.get("strikes"))
            idx = _int(ev.get("index"))
            if idx is not None:
                for movement in movements_by_idx.get(idx, []):
                    _apply_movement(occ, movement)
            # Half-inning transition is not a live state.
            if _int(count.get("outs")) == 3:
                continue
            if outs is None and balls is None and strikes is None and inning is None:
                continue
            details = ev.get("details") or play.get("result") or {}
            home = _int(details.get("homeScore"))
            away = _int(details.get("awayScore"))
            if home is None or away is None:
                result = play.get("result") or {}
                home = _int(result.get("homeScore"))
                away = _int(result.get("awayScore"))
            ts = _iso(ev.get("endTime") or ev.get("startTime") or about.get("endTime") or play.get("playEndTime"))
            if not ts:
                continue
            sl = inning_slice(inning, half)
            if sl == "UNALIGNED":
                continue
            bat = batting_team(half)
            n += 1
            on1, on2, on3 = occ[0], occ[1], occ[2]
            cat = runner_category(on1, on2, on3)
            rows.append(
                {
                    "internal_game_id": internal_game_id,
                    "source_game_id": source_id,
                    "event_number": str(n),
                    "event_timestamp": ts,
                    "available_at": ts,
                    "ingested_at": ingested_at,
                    "availability_quality": "OBSERVED",
                    "timestamp_status": "OBSERVED",
                    "period": sl,
                    "clock": "",
                    "inning": "" if inning is None else str(inning),
                    "half": half or "",
                    "outs": "" if outs is None else str(outs),
                    "balls": "" if balls is None else str(balls),
                    "strikes": "" if strikes is None else str(strikes),
                    "count_display": count_display(balls, strikes) or "",
                    "count_leverage": count_leverage(balls, strikes) or "",
                    "runner_on_1": _flag(on1),
                    "runner_on_2": _flag(on2),
                    "runner_on_3": _flag(on3),
                    "runners": cat or "",
                    "batting_team": bat or "",
                    "home_score": "" if home is None else str(home),
                    "away_score": "" if away is None else str(away),
                    "score_differential_home": ""
                    if home is None or away is None
                    else str(home - away),
                    "event_type": str((details.get("eventType") or ev.get("type") or "")),
                    "event_description": str(details.get("description") or "")[:400],
                    "source_dataset": source_dataset,
                    "source_file_hash": source_file_hash,
                    "pipeline_version": pipeline_version,
                    "derived_at": ingested_at,
                }
            )
        if _int((play.get("count") or {}).get("outs")) == 3 or str(half) and False:
            pass
        # After a completed half-inning (3 outs on the at-bat), clear bases.
        final_outs = _int((play.get("count") or {}).get("outs"))
        if final_outs == 3:
            occ = [False, False, False]
    return rows


def parse_file(path: Path, **kwargs: Any) -> list[dict[str, str]]:
    return parse_plays(load_envelope(path), **kwargs)
