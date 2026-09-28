# ADR-0007 — Team A / Team B canonicalization

# Decision

Every MLB game preserves **both** YES contracts. Team A and Team B are coupled
market identities, not “the side FIRST01 traded.” The losing side is never
discarded.

# Context

Kalshi `KXMLBGAME` packs are two YES contracts per event_ticker. Local June
data: 172 games × 2 tickers. Identity today is hash(event_ticker) / hash(ticker)
plus Kalshi `subtitle` as `side_label`. No official team registry.

# Problem

Storing only the traded contract loses starting prices, paths, and Greeks for
the opponent — the information needed to study why the other side never hit 80,
or how books co-moved.

# Alternatives Considered

1. Persist only the FIRST01-selected contract.
2. Infer Team B book as `100 − Team A`.
3. Persist both contracts independently; couple them in `GameMarketEpisode`.

# Decision Made

Alternative 3. Minimum per contract:

- starting contract price (or UNAVAILABLE + reason)
- price path, event-state path, event Greek path, market Greek path

Also preserve which team first reached 80%, when, game state, inning, half,
outs, runners, score, batter, pitcher, PBP sequence, market state, orderbook
state (or UNAVAILABLE).

Team A/B labels are canonicalized via a future identity graph (W2), not by
discarding Kalshi tickers. Tickers remain aliases.

Do not clone Team A from 100 − Team B last trade.

# Rationale

The episode is the game × both markets. Strategy selection is downstream.

# Consequences

Identity waterfall must handle postponements, doubleheaders, missing opponent
contract, canceled markets. Missing opponent is UNAVAILABLE, not dropped game.

# Data/Model Implications

Features may include opponent path only if observed at ≤ t.

# Testing Implications

Both-sides invariant on COMPLETE two-contract packs. No 100-minus inference.
First-80 winner recorded without deleting loser path.

# Future Compatibility

NBA/NHL two-outcome packs reuse the same coupling pattern.

# Status

ACCEPTED

# Date

2026-08-26
