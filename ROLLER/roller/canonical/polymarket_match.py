"""Link Polymarket moneyline events to existing internal_game_id rows.

Join key is identity (sport, eventDate, away, home), not a minted PM id.
Kalshi mapping_status is not reused and is never overwritten.
"""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any

import pandas as pd

from roller.config import RollerConfig
from roller.identity import CONFIDENCE_HIGH, CONFIDENCE_NONE, MAPPING_REVIEW, MAPPING_UNMAPPED, MAPPING_MAPPED
from roller.ingest.polymarket import json_list, moneyline_market, polymarket_cfg
from roller.timeutil import parse_utc

REMATCH_MAX_DELTA = timedelta(hours=6)

MAP_COLUMNS = [
    "internal_game_id",
    "sport",
    "season",
    "game_date",
    "home_team_id",
    "away_team_id",
    "polymarket_event_id",
    "polymarket_event_slug",
    "polymarket_game_id",
    "polymarket_start_time",
    "token_yes_home",
    "token_yes_away",
    "outcome_home",
    "outcome_away",
    "kalshi_market_yes_home",
    "kalshi_market_yes_away",
    "mapping_status",
    "mapping_confidence",
    "mapping_method",
]


def _norm_name(value: str) -> str:
    return " ".join("".join(ch if ch.isalnum() else " " for ch in str(value).lower()).split())


def team_code(cfg: RollerConfig, sport: str, season: str, team: dict[str, Any] | None) -> str:
    if not team:
        return ""
    abbr = str(team.get("abbreviation") or "").strip()
    if abbr:
        return cfg.canon_team_id(sport, season, abbr.upper())
    logo = str(team.get("logo") or "")
    if "/" in logo and logo.lower().endswith(".png"):
        stem = logo.rsplit("/", 1)[-1][:-4]
        if stem:
            return cfg.canon_team_id(sport, season, stem.upper())
    for key in ("name", "alias"):
        raw = str(team.get(key) or "").strip()
        if raw:
            mapped = cfg.canon_team_id(sport, season, raw)
            if mapped and mapped != raw:
                return mapped
            mapped = cfg.canon_team_id(sport, season, _norm_name(raw))
            if mapped and mapped != _norm_name(raw):
                return mapped
    return cfg.canon_team_id(sport, season, abbr or "")


def split_home_away(event: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    home = None
    away = None
    for team in event.get("teams") or []:
        order = str(team.get("ordering") or "").lower()
        if order == "home":
            home = team
        elif order == "away":
            away = team
    return home, away


def outcome_to_code(
    cfg: RollerConfig,
    sport: str,
    season: str,
    outcome: str,
    teams: list[dict[str, Any]],
) -> str:
    raw = str(outcome or "").strip()
    if not raw:
        return ""
    for team in teams:
        names = {
            str(team.get("name") or "").strip().lower(),
            str(team.get("alias") or "").strip().lower(),
            str(team.get("abbreviation") or "").strip().lower(),
        }
        if raw.lower() in names or _norm_name(raw) in {_norm_name(n) for n in names if n}:
            return team_code(cfg, sport, season, team)
    return cfg.canon_team_id(sport, season, raw)


def assign_tokens(
    cfg: RollerConfig,
    sport: str,
    season: str,
    event: dict[str, Any],
    home_id: str,
    away_id: str,
) -> tuple[str, str, str, str]:
    pm = polymarket_cfg(cfg)
    market = moneyline_market(event, str(pm.get("moneyline_type") or "moneyline"))
    if market is None:
        return "", "", "", ""
    outcomes = [str(x) for x in json_list(market.get("outcomes"))]
    tokens = [str(x) for x in json_list(market.get("clobTokenIds"))]
    if len(outcomes) != 2 or len(tokens) != 2:
        return "", "", "", ""
    teams = list(event.get("teams") or [])
    home_token = away_token = ""
    home_out = away_out = ""
    for outcome, token in zip(outcomes, tokens):
        code = outcome_to_code(cfg, sport, season, outcome, teams)
        if code == home_id and not home_token:
            home_token, home_out = token, outcome
        elif code == away_id and not away_token:
            away_token, away_out = token, outcome
    return home_token, away_token, home_out, away_out


def _index_identity(identity: pd.DataFrame, sport: str, season: str) -> dict[tuple[str, str, str], list[dict[str, Any]]]:
    out: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    sub = identity[(identity["sport"] == sport) & (identity["season"] == season)]
    for rec in sub.to_dict("records"):
        key = (
            str(rec.get("game_date") or "")[:10],
            str(rec.get("away_team_id") or ""),
            str(rec.get("home_team_id") or ""),
        )
        out.setdefault(key, []).append(rec)
    return out


def _is_date_only(value: Any) -> bool:
    text = str(value or "").strip()
    return len(text) == 10 and text[4] == "-" and text[7] == "-"


def official_event_start(cfg: RollerConfig, event: dict[str, Any]):
    """Official Gamma timestamp only. Never invent tip-off from eventDate."""
    for raw in (event.get("startTime"), event.get("startDate")):
        if raw in (None, "") or _is_date_only(raw):
            continue
        start = parse_utc(raw)
        if start is not None:
            return start
    market = moneyline_market(event, str(polymarket_cfg(cfg).get("moneyline_type") or "moneyline"))
    if market:
        for key in ("gameStartTime", "eventStartTime", "startDate"):
            raw = market.get(key)
            if raw in (None, "") or _is_date_only(raw):
                continue
            start = parse_utc(raw)
            if start is not None:
                return start
    return None


def match_event(
    cfg: RollerConfig,
    sport: str,
    season: str,
    event: dict[str, Any],
    by_pair: dict[tuple[str, str, str], list[dict[str, Any]]],
) -> dict[str, Any]:
    home_t, away_t = split_home_away(event)
    home_id = team_code(cfg, sport, season, home_t)
    away_id = team_code(cfg, sport, season, away_t)
    event_date = str(event.get("eventDate") or "")[:10]
    start = official_event_start(cfg, event)
    base = {
        "internal_game_id": "",
        "sport": sport,
        "season": season,
        "game_date": event_date,
        "home_team_id": home_id,
        "away_team_id": away_id,
        "polymarket_event_id": str(event.get("id") or ""),
        "polymarket_event_slug": str(event.get("slug") or ""),
        "polymarket_game_id": str(event.get("gameId") or ""),
        "polymarket_start_time": "" if start is None else start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "token_yes_home": "",
        "token_yes_away": "",
        "outcome_home": "",
        "outcome_away": "",
        "kalshi_market_yes_home": "",
        "kalshi_market_yes_away": "",
        "mapping_status": MAPPING_UNMAPPED,
        "mapping_confidence": CONFIDENCE_NONE,
        "mapping_method": "",
    }
    if not home_id or not away_id or not event_date or home_id == away_id:
        base["mapping_method"] = "missing_team_or_date"
        return base
    candidates = list(by_pair.get((event_date, away_id, home_id)) or [])
    if not candidates:
        base["mapping_method"] = "no_identity_row"
        return base
    chosen = None
    method = "eventDate+team_pair"
    status = MAPPING_MAPPED
    conf = CONFIDENCE_HIGH
    if len(candidates) == 1:
        chosen = candidates[0]
    else:
        if start is None:
            status, conf, method = MAPPING_REVIEW, CONFIDENCE_NONE, "rematch_no_start"
        else:
            scored: list[tuple[timedelta, dict[str, Any]]] = []
            for rec in candidates:
                other = parse_utc(rec.get("scheduled_start") or rec.get("game_date"))
                if other is None:
                    continue
                scored.append((abs(other - start), rec))
            scored.sort(key=lambda item: (item[0], str(item[1].get("internal_game_id") or "")))
            if not scored:
                status, conf, method = MAPPING_REVIEW, CONFIDENCE_NONE, "rematch_unparsed"
            elif scored[0][0] > REMATCH_MAX_DELTA:
                status, conf, method = MAPPING_REVIEW, CONFIDENCE_NONE, "rematch_far"
            elif len(scored) > 1 and scored[0][0] == scored[1][0]:
                status, conf, method = MAPPING_REVIEW, CONFIDENCE_NONE, "rematch_tie"
            else:
                chosen = scored[0][1]
                method = "eventDate+team_pair+startTime"
    if chosen is None or status != MAPPING_MAPPED:
        base["mapping_status"] = status
        base["mapping_confidence"] = conf
        base["mapping_method"] = method
        return base
    home_tok, away_tok, home_out, away_out = assign_tokens(cfg, sport, season, event, home_id, away_id)
    if not home_tok or not away_tok:
        base["internal_game_id"] = str(chosen.get("internal_game_id") or "")
        base["kalshi_market_yes_home"] = str(chosen.get("kalshi_market_yes_home") or "")
        base["kalshi_market_yes_away"] = str(chosen.get("kalshi_market_yes_away") or "")
        base["mapping_status"] = MAPPING_REVIEW
        base["mapping_confidence"] = CONFIDENCE_NONE
        base["mapping_method"] = "identity_hit_missing_moneyline_tokens"
        return base
    base.update(
        {
            "internal_game_id": str(chosen.get("internal_game_id") or ""),
            "token_yes_home": home_tok,
            "token_yes_away": away_tok,
            "outcome_home": home_out,
            "outcome_away": away_out,
            "kalshi_market_yes_home": str(chosen.get("kalshi_market_yes_home") or ""),
            "kalshi_market_yes_away": str(chosen.get("kalshi_market_yes_away") or ""),
            "mapping_status": MAPPING_MAPPED,
            "mapping_confidence": CONFIDENCE_HIGH,
            "mapping_method": method,
        }
    )
    return base


def match_events(
    cfg: RollerConfig,
    sport: str,
    season: str,
    events: list[dict[str, Any]],
    identity: pd.DataFrame,
) -> pd.DataFrame:
    by_pair = _index_identity(identity, sport, season)
    rows = [match_event(cfg, sport, season, ev, by_pair) for ev in events]
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=MAP_COLUMNS)
    return df[MAP_COLUMNS]


def mapped_token_jobs(crosswalk: pd.DataFrame) -> list[dict[str, str]]:
    jobs: list[dict[str, str]] = []
    if crosswalk.empty:
        return jobs
    mapped = crosswalk[crosswalk["mapping_status"] == MAPPING_MAPPED]
    for rec in mapped.to_dict("records"):
        start = str(rec.get("polymarket_start_time") or "")
        for side, token_key in (("home", "token_yes_home"), ("away", "token_yes_away")):
            token = str(rec.get(token_key) or "")
            if not token:
                continue
            jobs.append(
                {
                    "internal_game_id": str(rec.get("internal_game_id") or ""),
                    "token_id": token,
                    "team_side": side,
                    "start_time": start,
                    "ticker": f"{rec.get('polymarket_event_slug')}-{rec.get('home_team_id' if side == 'home' else 'away_team_id')}",
                    "kalshi_ticker": str(
                        rec.get("kalshi_market_yes_home" if side == "home" else "kalshi_market_yes_away") or ""
                    ),
                }
            )
    return jobs


def crosswalk_to_json(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df.empty:
        return []
    return json.loads(df.to_json(orient="records"))
