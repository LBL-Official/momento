# ADR-0018 — Internal GameId is canonical

# Decision

Internal `GameId` is the canonical game identity. Kalshi tickers and event
tickers are aliases. Official MLB game pk is an additional mapped identifier,
nullable until Waterfall 2.

# Context

`crates/kalshi/src/identity.rs`: `GameId` = SHA-256(`"game" || event_ticker`) →
u128; `MarketId` similarly from ticker. No MLB pk, no postponement/DH handler.

# Problem

Using ticker strings as primary identity breaks when markets are recreated,
canceled, or when official games must join PBP.

# Alternatives Considered

1. Ticker as primary key.
2. MLB pk as primary before mapping exists.
3. Internal GameId canonical; identity graph adds aliases and official ids.

# Decision Made

Alternative 3. Waterfall 1 identity stub:

```text
game_id, market_id, ticker, event_ticker, series
mlb_game_pk = null
match_status = UNMAPPED
```

Do not invent official pks. Hash function stays shared with live for ticker-stable
ids. Waterfall 2 builds the mapping engine.

# Rationale

Live and research should not fork identity for the same Kalshi event.

# Consequences

Core financial `GameId` type is UNTOUCHED. Research wraps an identity graph.

# Data/Model Implications

Joins to PBP wait on mapped pk or explicit UNMATCHED.

# Testing Implications

No fake MLB pks. Unmapped is valid. Duplicate ticker → same GameId.

# Future Compatibility

NBA official ids attach the same way after MLB mapping is proven.

# Status

ACCEPTED

# Date

2026-08-26
