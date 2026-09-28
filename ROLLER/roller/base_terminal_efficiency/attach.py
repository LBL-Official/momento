"""Attach Base TE observation + WIN/LOSS book to a generic-query row.

Does not change path_true / generic minute-tie classification.
Does not modify first80 or generic PathOp semantics.
"""

from __future__ import annotations

from typing import Any, Callable

from roller.base_terminal_efficiency.builder import build_observation
from roller.base_terminal_efficiency.empirical import measure, partition
from roller.base_terminal_efficiency.exits import classify_first_exit
from roller.base_terminal_efficiency.models import LOSS, TERMINAL_NO, TERMINAL_YES, UNAVAILABLE, UNALIGNED, WIN
from roller.base_terminal_efficiency.settlement import terminal_outcome
from roller.base_terminal_efficiency.versions import CODE_VERSION, SEMANTICS_VERSION
from roller.mlb.state import runner_matches
from roller.research_query.entry_engine import TouchEvent, default_snap
from roller.research_query.hashing import _custom_range, _exact_diffs
from roller.research_query.models import ExitOutcome, PathOp, ResearchQuestion
from roller.research_query.path_engine import _elapsed_from_snap


def _magnitude_union(filters: dict[str, Any]) -> set[int] | None:
    """Unsigned magnitudes: exact ∪ preset ∪ custom. None means no magnitude chip."""
    parts: set[int] = set()
    parts.update(_exact_diffs(filters))
    band = str(filters.get("absDiff") or filters.get("abs_diff") or "any")
    if band == "1_5":
        parts.update(range(1, 6))
    elif band == "6_10":
        parts.update(range(6, 11))
    elif band == "11_plus":
        parts.update(range(11, 101))
    custom = _custom_range(filters)
    if custom:
        parts.update(range(custom[0], custom[1] + 1))
    return parts or None


def _signed_allowed(side: str, magnitudes: set[int] | None) -> set[int] | None:
    if side == "tied":
        return {0}
    if magnitudes is None:
        return None
    if side == "leading":
        return {abs(n) for n in magnitudes if n != 0}
    if side == "trailing":
        return {-abs(n) for n in magnitudes if n != 0}
    signed: set[int] = set()
    for n in magnitudes:
        if n == 0:
            signed.add(0)
        else:
            signed.add(n)
            signed.add(-n)
    return signed


def row_matches_te_filters(row: dict[str, Any], filters: dict[str, Any] | None) -> bool:
    te = row.get("te") if isinstance(row.get("te"), dict) else {}
    filters = filters or {}
    side = str(filters.get("scoreSide") or filters.get("score_side") or "any")
    diff = te.get("point_differential")
    if side == "leading" and not (diff is not None and int(diff) > 0):
        return False
    if side == "tied" and not (diff is not None and int(diff) == 0):
        return False
    if side == "trailing" and not (diff is not None and int(diff) < 0):
        return False
    magnitudes = _magnitude_union(filters)
    allowed = _signed_allowed(side, magnitudes)
    if allowed is not None:
        if diff is None:
            return False
        if int(diff) not in allowed:
            return False
    elif str(filters.get("absDiff") or filters.get("abs_diff") or "any") != "any":
        ad = te.get("point_differential_abs_e0")
        band = str(filters.get("absDiff") or filters.get("abs_diff") or "any")
        if band == "1_5" and not (ad is not None and 1 <= int(ad) <= 5):
            return False
        if band == "6_10" and not (ad is not None and 6 <= int(ad) <= 10):
            return False
        if band == "11_plus" and not (ad is not None and int(ad) >= 11):
            return False
    half = str(filters.get("half") or "").strip().lower()
    if half in {"top", "bottom"}:
        if str(te.get("half") or "") != half:
            return False
    yes_bat = filters.get("yesBatting") if "yesBatting" in filters else filters.get("yes_batting")
    if yes_bat in (True, False, "true", "false", "batting", "pitching"):
        want = yes_bat in (True, "true", "batting")
        got = te.get("yes_batting")
        if got is None or bool(got) != want:
            return False
    outs_f = filters.get("outs")
    if outs_f not in (None, "", "any"):
        got_outs = te.get("outs")
        if got_outs is None:
            return False
        want_outs = {int(x) for x in (outs_f if isinstance(outs_f, (list, tuple)) else [outs_f])}
        if int(got_outs) not in want_outs:
            return False
    count_f = str(filters.get("count") or "").strip()
    if count_f and count_f != "any":
        display = str(te.get("count_display") or "")
        leverage = str(te.get("count_leverage") or "")
        if count_f not in {display, leverage}:
            return False
    runners_f = str(filters.get("runners") or "").strip()
    if runners_f and runners_f != "any":
        if not runner_matches(te.get("runners"), runners_f):
            return False
    if not _tennis_filters_match(te, filters):
        return False
    return True


def _lead_filter_matches(value: Any, filt: dict[str, Any] | None) -> bool:
    """Fail closed when a tennis lead chip is set and the snapped lead is missing."""
    if not isinstance(filt, dict) or not filt:
        return True
    side = str(filt.get("scoreSide") or filt.get("score_side") or "any")
    has_mag = bool(_exact_diffs(filt) or _custom_range(filt) or str(filt.get("absDiff") or "any") != "any")
    if side == "any" and not has_mag:
        return True
    if value is None:
        return False
    signed = int(value)
    if side == "leading" and signed <= 0:
        return False
    if side == "tied" and signed != 0:
        return False
    if side == "trailing" and signed >= 0:
        return False
    magnitudes = _magnitude_union(filt)
    allowed = _signed_allowed(side, magnitudes)
    if allowed is not None and signed not in allowed:
        return False
    return True


def _tennis_filters_match(te: dict[str, Any], filters: dict[str, Any]) -> bool:
    scores = filters.get("tennisPointScores") or filters.get("tennis_point_scores") or []
    if scores:
        raw = str(te.get("point_score_raw") or "")
        wanted = {str(x).upper() for x in scores}
        if raw.upper() not in wanted and raw.replace(" ", "") not in {w.replace(" ", "") for w in wanted}:
            if "DEUCE" in wanted and raw.upper() not in {"40-40", "DEUCE"}:
                return False
            if "ADVANTAGE" in wanted and "AD" not in raw.upper():
                return False
            if "DEUCE" not in wanted and "ADVANTAGE" not in wanted:
                return False
    serve = filters.get("tennisServe") or filters.get("tennis_serve") or []
    if isinstance(serve, str):
        serve = [serve] if serve and serve != "any" else []
    if serve:
        want_serve = {str(x) for x in serve}
        got_s = te.get("yes_serving")
        got_r = te.get("yes_returning")
        ok = False
        if "serving" in want_serve and got_s is True:
            ok = True
        if "returning" in want_serve and got_r is True:
            ok = True
        if not ok:
            return False
    events = filters.get("tennisEventStates") or filters.get("tennis_event_states") or []
    if events:
        want_ev = {str(x) for x in events}
        hit = False
        if "break_point" in want_ev and te.get("break_point") is True:
            hit = True
        if "set_point" in want_ev and te.get("yes_set_point") is True:
            hit = True
        if "match_point" in want_ev and te.get("yes_match_point") is True:
            hit = True
        if "tiebreak" in want_ev and te.get("is_tiebreak") is True:
            hit = True
        if not hit:
            return False
    if not _lead_filter_matches(
        te.get("yes_set_lead"),
        filters.get("tennisSetLead") or filters.get("tennis_set_lead"),
    ):
        return False
    if not _lead_filter_matches(
        te.get("yes_game_lead"),
        filters.get("tennisGameLead") or filters.get("tennis_game_lead"),
    ):
        return False
    if not _lead_filter_matches(
        te.get("yes_point_lead"),
        filters.get("tennisPointLead") or filters.get("tennis_point_lead"),
    ):
        return False
    return True


def attach_to_row(
    row: dict[str, Any],
    *,
    entry: TouchEvent,
    bars: list,
    question: ResearchQuestion,
    pbp_events: list[dict[str, Any]] | None = None,
    game: dict[str, Any] | None = None,
    market: dict[str, Any] | None = None,
    snap_fn: Callable | None = None,
    sport: str = "NBA",
    league: str | None = None,
    season: str | None = None,
) -> dict[str, Any]:
    """Mutates row['te']. Leaves generic path/exit fields unchanged."""
    to_entry = [b for b in bars if b.ts <= entry.bar.ts] or [entry.bar]
    after = [b for b in bars if b.ts > entry.bar.ts]
    obs = build_observation(
        to_entry,
        pbp_events=pbp_events,
        game=game,
        market=market,
        league=league,
        season=season,
        sport=sport,
        attach_terminal=True,
    )
    if obs is None:
        te: dict[str, Any] = {
            "feature_status": UNALIGNED,
            "score_status": UNALIGNED,
            "alignment_status": UNALIGNED,
            "market_status": UNAVAILABLE,
            "terminal_outcome": terminal_outcome(market),
            "entry_price_e4": int(entry.bar.bid),
            "entry_price_cents": int(entry.bar.bid) // 100,
            "observation_ts": entry.bar.ts.isoformat().replace("+00:00", "Z"),
            "ticker": entry.bar.ticker,
            "game_id": entry.bar.game_id,
        }
    else:
        te = obs.to_dict()

    resolved_snap = snap_fn
    if resolved_snap is None and pbp_events:
        resolved_snap = lambda ts, _p=pbp_events: default_snap(ts, _p, sport)
    win_steps = [p for p in question.path_conditions if p.outcome is ExitOutcome.WIN]
    loss_steps = [p for p in question.path_conditions if p.outcome is ExitOutcome.LOSS]
    needs_game = any(
        p.op in (PathOp.HORIZON_WIN, PathOp.HORIZON_LOSS) and p.horizon_kind == "game"
        for p in (*win_steps, *loss_steps)
    )
    entry_elapsed = _elapsed_from_snap(entry.snap, sport) if needs_game else None
    classified = (
        classify_first_exit(
            entry.bar,
            after,
            win_steps=win_steps,
            loss_steps=loss_steps,
            snap_fn=resolved_snap,
            entry_elapsed_s=entry_elapsed,
            sport=sport,
        )
        if win_steps or loss_steps
        else {
            "status": None,
            "exit_outcome": None,
            "exclusion_reason": None,
            "exit_ts": None,
            "exit_price_e4": None,
        }
    )
    if classified.get("exit_outcome") is None:
        term = te.get("terminal_outcome")
        if question.win_hold and term == TERMINAL_YES:
            classified = {
                **classified,
                "status": WIN,
                "exit_outcome": WIN,
                "exit_type": "HOLD_EXPIRATION",
            }
        elif question.loss_hold and term == TERMINAL_NO:
            classified = {
                **classified,
                "status": LOSS,
                "exit_outcome": LOSS,
                "exit_type": "HOLD_EXPIRATION",
            }
    te["exit_outcome"] = classified.get("exit_outcome")
    te["exit_status"] = classified.get("status")
    te["exclusion_reason"] = classified.get("exclusion_reason")
    te["exit_ts"] = classified.get("exit_ts")
    te["exit_price_e4"] = classified.get("exit_price_e4")
    te["win_exit_ts"] = classified.get("win_exit_ts")
    te["loss_exit_ts"] = classified.get("loss_exit_ts")
    te["semantics_version"] = SEMANTICS_VERSION
    te["code_version"] = CODE_VERSION
    row["te"] = te
    return row


def summarize_rows(
    rows: list[dict[str, Any]],
    filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    tagged = [r for r in rows if isinstance(r.get("te"), dict)]
    scoped = [r for r in tagged if row_matches_te_filters(r, filters)]
    obs = [r["te"] for r in scoped]
    exits = [{"exit_outcome": t.get("exit_outcome")} for t in obs]

    def _side_pred(name: str):
        def _ok(te: dict[str, Any]) -> bool:
            d = te.get("point_differential")
            if d is None:
                return name == "unavailable"
            if name == "leading":
                return int(d) > 0
            if name == "trailing":
                return int(d) < 0
            if name == "tied":
                return int(d) == 0
            return False

        return _ok

    return {
        "semantics_version": SEMANTICS_VERSION,
        "code_version": CODE_VERSION,
        "note": (
            "Empirical PIT observation at the entry bar. Not a prediction. "
            "TE WIN/LOSS uses exact-timestamp AMBIGUOUS. Generic minute TIE_EXCLUDED is unchanged. "
            "CANDLE PATH ≠ FILL. MEASUREMENT ≠ EDGE."
        ),
        "n_entry_rows": len(rows),
        "n_te_attached": len(tagged),
        "n_te_scoped": len(scoped),
        "filters": filters or {},
        "overall": measure(obs, exit_results=exits),
        "by_score_side": {
            "leading": partition(obs, _side_pred("leading"), exit_results=exits),
            "tied": partition(obs, _side_pred("tied"), exit_results=exits),
            "trailing": partition(obs, _side_pred("trailing"), exit_results=exits),
            "unavailable": partition(obs, _side_pred("unavailable"), exit_results=exits),
        },
    }
