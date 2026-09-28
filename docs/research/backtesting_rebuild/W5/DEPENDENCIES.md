# CTO-W5 DEPENDENCIES

**Upstream:** CTO-W3 (game/PBP) **and** CTO-W4 (Kalshi `MarketPath`).  
**Downstream:** path packaging / `GameMarketEpisode` / FIRST01 plugin (later).

## Blocking

| Blocker | Effect |
|---------|--------|
| W4 crate / honest MarketPath missing | Cannot join market ticks; W5 must not parse raw Kalshi as a substitute |
| Historical L2 UNAVAILABLE | `orderbook_path` stays UNAVAILABLE; not a W5 blocker |
| PBP missing for a ticker | `event_state = UNAVAILABLE`; market path retained |
| Metadata-only Kalshi | Sync to an empty t_game path; report gap; do not interpolate |

## Parallelism

Docs/fixtures for sync classes may be written in parallel with W4 **types**.
Implementation of join **no** until W4 bounded window (2026-06-18) reconstructs
real trades without calling them L2.

See [S_OF_T_FIELD_CONTRACT.md](S_OF_T_FIELD_CONTRACT.md).
