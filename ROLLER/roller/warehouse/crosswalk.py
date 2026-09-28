"""Logical GameMarketLink construction. Phase 1: in-memory only.

Does not write parquet. Does not guess a game from a ticker.
Does not treat blank internal_game_id as a match.
"""

from __future__ import annotations

from roller.warehouse.entities import GameMarketLink, LinkStatus


def link_status(
    *,
    internal_game_id: str,
    ticker: str,
    candidate_game_ids: tuple[str, ...] = (),
) -> LinkStatus:
    """Deterministic status from known IDs. No fuzzy team/date match."""
    gid = str(internal_game_id or "").strip()
    tick = str(ticker or "").strip()
    candidates = tuple(str(c).strip() for c in candidate_game_ids if str(c).strip())
    unique_candidates = tuple(dict.fromkeys(candidates))
    if not tick:
        return LinkStatus.INVALID
    if len(unique_candidates) > 1:
        return LinkStatus.AMBIGUOUS
    if unique_candidates and gid and gid not in unique_candidates:
        return LinkStatus.AMBIGUOUS
    if not gid:
        return LinkStatus.UNLINKED
    return LinkStatus.LINKED


def make_link(
    *,
    internal_game_id: str = "",
    ticker: str = "",
    event_ticker: str = "",
    candidate_game_ids: tuple[str, ...] = (),
) -> GameMarketLink:
    status = link_status(
        internal_game_id=internal_game_id,
        ticker=ticker,
        candidate_game_ids=candidate_game_ids,
    )
    reason = {
        LinkStatus.LINKED: "game and ticker both present",
        LinkStatus.UNLINKED: "ticker present without internal_game_id",
        LinkStatus.AMBIGUOUS: "more than one candidate game id; no guess",
        LinkStatus.INVALID: "ticker missing",
    }[status]
    return GameMarketLink(
        status=status,
        internal_game_id=str(internal_game_id or "").strip(),
        ticker=str(ticker or "").strip(),
        event_ticker=str(event_ticker or "").strip(),
        reason=reason,
    )
