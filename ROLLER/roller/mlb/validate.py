"""Integrity checks for canonical MLB warehouse rows."""

from __future__ import annotations

from collections import Counter
from typing import Any

from roller.mlb.state import VALID_BALLS, VALID_HALVES, VALID_OUTS, VALID_STRIKES, normalize_half


def _int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def validate_pbp_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    issues: list[str] = []
    seen_ids: set[tuple[str, str]] = set()
    for i, row in enumerate(rows):
        key = (str(row.get("internal_game_id") or ""), str(row.get("event_number") or ""))
        if key in seen_ids:
            issues.append(f"duplicate_id:{key[0]}:{key[1]}")
        seen_ids.add(key)
        inning = _int(row.get("inning"))
        if inning is None or inning < 1:
            issues.append(f"invalid_inning:{i}")
        half = normalize_half(row.get("half"))
        if half not in VALID_HALVES:
            issues.append(f"invalid_half:{i}")
        outs = _int(row.get("outs"))
        if outs is not None and outs not in VALID_OUTS:
            issues.append(f"invalid_outs:{i}")
        balls = _int(row.get("balls"))
        if balls is not None and balls not in VALID_BALLS:
            issues.append(f"invalid_balls:{i}")
        strikes = _int(row.get("strikes"))
        if strikes is not None and strikes not in VALID_STRIKES:
            issues.append(f"invalid_strikes:{i}")
        if str(row.get("batting_team") or "") not in {"home", "away"}:
            issues.append(f"missing_batting_team:{i}")
        home = _int(row.get("home_score"))
        away = _int(row.get("away_score"))
        if home is None or away is None:
            issues.append(f"missing_score:{i}")
        elif home < 0 or away < 0:
            issues.append(f"invalid_score:{i}")
    return {"ok": not issues, "n": len(rows), "issues": issues[:50], "issue_count": len(issues)}


def validate_score_transitions(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Scores may stay or increase; they must not decrease within a game."""
    by_game: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_game.setdefault(str(row.get("internal_game_id") or ""), []).append(row)
    issues: list[str] = []
    for gid, evs in by_game.items():
        ordered = sorted(evs, key=lambda r: (str(r.get("event_timestamp") or ""), int(r.get("event_number") or 0)))
        prev_h = prev_a = 0
        for row in ordered:
            h = _int(row.get("home_score"))
            a = _int(row.get("away_score"))
            if h is None or a is None:
                continue
            if h < prev_h or a < prev_a:
                issues.append(f"score_regression:{gid}:{row.get('event_number')}")
            prev_h, prev_a = max(prev_h, h), max(prev_a, a)
    return {"ok": not issues, "issues": issues[:50], "issue_count": len(issues)}


def validate_orphans(
    games: list[dict[str, Any]],
    pbp: list[dict[str, Any]],
    markets: list[dict[str, Any]],
) -> dict[str, Any]:
    game_ids = {str(g.get("internal_game_id") or "") for g in games}
    pbp_ids = {str(r.get("internal_game_id") or "") for r in pbp}
    market_ids = {str(r.get("internal_game_id") or "") for r in markets}
    market_tickers = [str(r.get("ticker") or "") for r in markets]
    counts = Counter(market_tickers)
    dup_tickers = [t for t, n in counts.items() if t and n > 1]
    orphan_pbp = sorted(pbp_ids - game_ids)
    orphan_markets = sorted(x for x in (market_ids - game_ids) if x)
    return {
        "ok": not orphan_pbp and not dup_tickers,
        "orphan_pbp": orphan_pbp[:20],
        "orphan_markets": orphan_markets[:20],
        "duplicate_tickers": dup_tickers[:20],
    }


def validate_warehouse(
    *,
    games: list[dict[str, Any]],
    pbp: list[dict[str, Any]],
    markets: list[dict[str, Any]],
) -> dict[str, Any]:
    pbp_rep = validate_pbp_rows(pbp)
    trans = validate_score_transitions(pbp)
    orphans = validate_orphans(games, pbp, markets)
    ok = pbp_rep["ok"] and trans["ok"] and orphans["ok"]
    return {"ok": ok, "pbp": pbp_rep, "score_transitions": trans, "orphans": orphans}
