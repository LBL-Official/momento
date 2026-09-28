"""Terminal / horizon / path labels. contains_future_information is always true."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pandas as pd

from roller.admin import load_dataset, load_identity
from roller.canonical.events import event_records, project_events
from roller.config import RollerConfig
from roller.state.observation_id import make_observation_id, parse_observation_id
from roller.state.possessions import reconstruct_possessions
from roller.timeutil import parse_utc, resolve_cutoff, to_iso

LABEL_VERSION = "2.0.0"


def _score(rec: dict[str, Any] | None) -> tuple[int | None, int | None]:
    if not rec:
        return None, None
    try:
        h = int(rec["home_score"]) if rec.get("home_score") not in (None, "") else None
    except (TypeError, ValueError):
        h = None
    try:
        a = int(rec["away_score"]) if rec.get("away_score") not in (None, "") else None
    except (TypeError, ValueError):
        a = None
    return h, a


def _event_clock(rec: dict[str, Any]):
    return parse_utc(rec.get("event_time") or rec.get("event_timestamp") or rec.get("available_at"))


def _label(
    *,
    name: str,
    observation_time,
    horizon_definition: str,
    available_after,
    value: Any,
    observation_id: str,
    internal_game_id: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row = {
        "label_name": name,
        "label_version": LABEL_VERSION,
        "observation_id": observation_id,
        "internal_game_id": internal_game_id,
        "observation_time": to_iso(observation_time),
        "horizon_definition": horizon_definition,
        "label_available_only_after": available_after,
        "contains_future_information": True,
        "value": value,
    }
    if extra:
        row.update(extra)
    return row


def build_labels(
    cfg: RollerConfig,
    *,
    observation_id: str | None = None,
    internal_game_id: str | None = None,
    as_of=None,
    end_of_day: bool = False,
) -> dict[str, Any]:
    if observation_id:
        gid, obs_time, _ver = parse_observation_id(observation_id)
    elif internal_game_id and as_of is not None:
        gid = internal_game_id
        obs_time = resolve_cutoff(as_of, end_of_day=end_of_day)
        observation_id = make_observation_id(gid, obs_time, cfg.state_schema_version)
    else:
        raise ValueError("labels require observation_id or explicit internal_game_id + as_of")

    ident = load_identity(cfg)
    hit = ident[ident["internal_game_id"] == gid]
    if hit.empty:
        raise KeyError(gid)
    rec = hit.iloc[0].to_dict()
    sport, season = rec["sport"], rec["season"]

    try:
        games = load_dataset(cfg, sport, season, "games")
    except FileNotFoundError:
        games = pd.DataFrame()
    game_row = games[games["internal_game_id"] == gid] if not games.empty else games
    game = game_row.iloc[0].to_dict() if game_row is not None and not game_row.empty else {}

    try:
        pbp = load_dataset(cfg, sport, season, "pbp")
    except FileNotFoundError:
        pbp = pd.DataFrame()
    if not pbp.empty:
        pbp = pbp[pbp["internal_game_id"] == gid]
    events = event_records(project_events(pbp)) if not pbp.empty else []

    baseline = None
    for ev in events:
        ts = parse_utc(ev.get("available_at"))
        if ts is not None and ts < obs_time:
            baseline = ev
    base_h, _base_a = _score(baseline)

    labels: list[dict[str, Any]] = []
    result_after = game.get("result_available_at") or ""
    labels.append(
        _label(
            name="home_win",
            observation_time=obs_time,
            horizon_definition="terminal",
            available_after=result_after,
            value=game.get("home_win") or "",
            observation_id=observation_id,
            internal_game_id=gid,
        )
    )
    labels.append(
        _label(
            name="away_win",
            observation_time=obs_time,
            horizon_definition="terminal",
            available_after=result_after,
            value=game.get("away_win") or "",
            observation_id=observation_id,
            internal_game_id=gid,
        )
    )
    labels.append(
        _label(
            name="home_score_terminal",
            observation_time=obs_time,
            horizon_definition="terminal",
            available_after=result_after,
            value=game.get("final_home_score") or "",
            observation_id=observation_id,
            internal_game_id=gid,
        )
    )

    horizons = (cfg.labels.get("horizons") or {}) if cfg.labels else {}
    for sec in horizons.get("seconds") or [60, 300]:
        horizon_end = obs_time + timedelta(seconds=int(sec))
        future = None
        latest_avail = horizon_end
        path: list[dict[str, Any]] = []
        for ev in events:
            clock = _event_clock(ev)
            if clock is None or clock <= obs_time or clock > horizon_end:
                continue
            future = ev
            avail = parse_utc(ev.get("available_at"))
            if avail is not None and avail > latest_avail:
                latest_avail = avail
            h, a = _score(ev)
            if h is not None and a is not None:
                path.append({"event_time": ev.get("event_time") or ev.get("event_timestamp"), "home_score": h, "away_score": a})
        fut_h, _ = _score(future)
        change = None if base_h is None or fut_h is None else fut_h - base_h
        if change is None and base_h is not None and future is None:
            change = 0
        labels.append(
            _label(
                name=f"home_score_change_next_{int(sec)}_seconds",
                observation_time=obs_time,
                horizon_definition=f"seconds:{int(sec)}",
                available_after=to_iso(latest_avail),
                value=change,
                observation_id=observation_id,
                internal_game_id=gid,
            )
        )
        labels.append(
            _label(
                name=f"score_path_next_{int(sec)}_seconds",
                observation_time=obs_time,
                horizon_definition=f"path_seconds:{int(sec)}",
                available_after=to_iso(latest_avail),
                value=path,
                observation_id=observation_id,
                internal_game_id=gid,
            )
        )

    if sport in {"NBA", "WNBA", "NCAAB"} and events:
        built = reconstruct_possessions(events, sport=sport)
        future_poss = []
        for poss in built["possessions"]:
            start = parse_utc(poss.get("start_available_at"))
            if start is not None and start >= obs_time:
                future_poss.append(poss)
        for n in horizons.get("possessions") or [1, 3, 5]:
            slice_ = future_poss[: int(n)]
            avail = obs_time
            end_event_n = None
            for poss in slice_:
                end_a = parse_utc(poss.get("end_available_at"))
                if end_a is not None and end_a > avail:
                    avail = end_a
                end_event_n = poss.get("end_event_number")
            fut = None
            if end_event_n is not None:
                for ev in events:
                    if str(ev.get("event_number")) == str(end_event_n):
                        fut = ev
                        break
            fut_h, _ = _score(fut)
            change = None if base_h is None or fut_h is None else fut_h - base_h
            labels.append(
                _label(
                    name=f"home_score_change_next_{int(n)}_possession",
                    observation_time=obs_time,
                    horizon_definition=f"possessions:{int(n)}",
                    available_after=to_iso(avail),
                    value=change,
                    observation_id=observation_id,
                    internal_game_id=gid,
                    extra={"n_possessions_observed": len(slice_)},
                )
            )

    try:
        markets = load_dataset(cfg, sport, season, "kalshi_markets")
    except (FileNotFoundError, KeyError):
        markets = pd.DataFrame()
    mkt_rows = markets[markets["internal_game_id"] == gid] if not markets.empty else markets
    settle_after = result_after
    yes_settled = ""
    if mkt_rows is not None and not mkt_rows.empty:
        first_m = mkt_rows.iloc[0].to_dict()
        yes_settled = first_m.get("kalshi_yes_settled") or ""
        settle_after = first_m.get("result_available_at") or result_after
    labels.append(
        _label(
            name="kalshi_yes_settled",
            observation_time=obs_time,
            horizon_definition="kalshi_expiration",
            available_after=settle_after,
            value=yes_settled,
            observation_id=observation_id,
            internal_game_id=gid,
            extra={"note": "W is ticker expiration, not box home_win"},
        )
    )
    try:
        first80 = load_dataset(cfg, sport, season, "first80_triggers")
    except (FileNotFoundError, KeyError):
        first80 = pd.DataFrame()
    f80 = first80[first80["internal_game_id"] == gid] if not first80.empty else first80
    f80_row = f80.iloc[0].to_dict() if f80 is not None and not f80.empty else {}
    labels.append(
        _label(
            name="first80_trigger",
            observation_time=obs_time,
            horizon_definition="first80:tradable_close_ge_80",
            available_after=f80_row.get("available_at") or result_after,
            value=f80_row.get("status") or "",
            observation_id=observation_id,
            internal_game_id=gid,
            extra={"ticker": f80_row.get("ticker") or "", "note": "off O_t; candle path ≠ fill"},
        )
    )
    labels.append(
        _label(
            name="first80_t40",
            observation_time=obs_time,
            horizon_definition="first80:first_later_close_le_40",
            available_after=f80_row.get("t40_available_at") or f80_row.get("t40_timestamp") or result_after,
            value=f80_row.get("t40_timestamp") or "",
            observation_id=observation_id,
            internal_game_id=gid,
        )
    )
    labels.append(
        _label(
            name="first80_entry_slice",
            observation_time=obs_time,
            horizon_definition="first80:clock_snap_at_entry",
            available_after=f80_row.get("available_at") or result_after,
            value=f80_row.get("entry_slice") or "UNALIGNED",
            observation_id=observation_id,
            internal_game_id=gid,
            extra={"asked_six": f80_row.get("asked_six") or "0"},
        )
    )

    for barrier in (cfg.labels.get("barriers") or []) if cfg.labels else []:
        operator = barrier.get("operator")
        threshold = barrier.get("value")
        if not operator:
            continue
        labels.append(
            _label(
                name=f"barrier_{operator}_{threshold}",
                observation_time=obs_time,
                horizon_definition=f"barrier:{operator}:{threshold}",
                available_after=result_after,
                value=None,
                observation_id=observation_id,
                internal_game_id=gid,
                extra={"operator": operator, "barrier_value": threshold, "note": "generic operator only"},
            )
        )

    return {
        "observation_id": observation_id,
        "internal_game_id": gid,
        "observation_time": to_iso(obs_time),
        "contains_future_information": True,
        "labels": labels,
    }
