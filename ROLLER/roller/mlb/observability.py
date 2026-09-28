"""MLB execute funnel + exclusion reasons. Missing ticker is not silent N=0."""

from __future__ import annotations

from typing import Any

MLB_EXCLUSIONS = (
    "NO_MARKET",
    "NO_PBP",
    "NO_MATCH_MAPPING",
    "PIT_ALIGNMENT_FAILED",
    "MISSING_SCORE",
    "MISSING_OUTS",
    "MISSING_COUNT",
    "MISSING_RUNNERS",
    "UNSUPPORTED_RULE",
    "UNTRADABLE_CANDLES",
)

UNTRADABLE_CANDLES_REASON = (
    "UNTRADABLE_CANDLES — every loaded bar failed frozen quality() "
    "(volume not positive or uncrossed spread). Volume is not invented. "
    "This is not an empty FIRST_TOUCH population. LAST TRADE remains the runnable path."
)


def empty_exclusions() -> dict[str, int]:
    return {k: 0 for k in MLB_EXCLUSIONS}


def classify_te_drop(row: dict[str, Any]) -> str:
    te = row.get("te") if isinstance(row.get("te"), dict) else {}
    if te.get("alignment_status") == "UNALIGNED" or te.get("feature_status") == "UNALIGNED":
        return "PIT_ALIGNMENT_FAILED"
    if te.get("team_points") is None or te.get("point_differential") is None:
        return "MISSING_SCORE"
    if te.get("outs") is None:
        return "MISSING_OUTS"
    if te.get("count_display") is None and te.get("balls") is None:
        return "MISSING_COUNT"
    if te.get("runners") in (None, ""):
        return "MISSING_RUNNERS"
    return "UNSUPPORTED_RULE"


def count_te_drops(dropped: list[dict[str, Any]]) -> dict[str, int]:
    out = empty_exclusions()
    for row in dropped:
        out[classify_te_drop(row)] += 1
    return out


def build_mlb_observability(
    *,
    games: list[dict[str, Any]],
    markets: dict[str, dict[str, Any]],
    pbp_by_game: dict[str, list[dict[str, Any]]],
    ticker_payloads: dict[str, list[dict[str, Any]]],
    entry_candidates: int,
    pit_aligned: int,
    te_scoped: int,
    classified: int,
    exclusions: dict[str, int] | None = None,
    observation_basis: str,
) -> dict[str, Any]:
    ticker_game_ids = {
        str(row.get("internal_game_id") or "")
        for rows in ticker_payloads.values()
        for row in rows
        if row.get("internal_game_id")
    }
    market_game_ids = {
        str(m.get("internal_game_id") or "")
        for m in markets.values()
        if m.get("internal_game_id")
    }
    observed = ticker_game_ids | market_game_ids
    scoped = [
        g
        for g in games
        if str(g.get("internal_game_id") or "") in observed
    ] if observed else []
    game_ids = {str(g.get("internal_game_id") or "") for g in scoped if g.get("internal_game_id")}
    pbp_ids = {k for k, rows in pbp_by_game.items() if rows and (not observed or k in observed)}
    matched = game_ids & pbp_ids & market_game_ids
    reasons = empty_exclusions()
    reasons.update(exclusions or {})
    orphan_tickers = [t for t, rows in ticker_payloads.items() if not t or not rows]
    reasons["NO_MARKET"] = reasons.get("NO_MARKET", 0) + len(orphan_tickers)
    for gid in game_ids:
        if gid not in market_game_ids:
            reasons["NO_MARKET"] += 1
        if gid not in pbp_ids:
            reasons["NO_PBP"] += 1
        if gid in market_game_ids and gid in pbp_ids and gid not in matched:
            reasons["NO_MATCH_MAPPING"] += 1
    return {
        "observation_basis": observation_basis,
        "funnel": {
            "universe": len(ticker_payloads),
            "games": len(game_ids),
            "markets": len(markets),
            "pbp": len(pbp_ids),
            "matched": len(matched),
            "pit_aligned": pit_aligned,
            "entry_candidates": entry_candidates,
            "te_scoped": te_scoped,
            "classified": classified,
        },
        "exclusions": reasons,
        "notes": [
            "CANDLE/PRINT PATH ≠ FILL",
            "LAST TRADE ≠ YES BID" if observation_basis.startswith("LAST_TRADE") else "TRADABLE_YES_BID",
            "Missing ticker is counted as NO_MARKET, not silent N=0.",
            "UNTRADABLE_CANDLES is DATA_REQUIRED, not an empty FIRST_TOUCH population.",
        ],
    }
