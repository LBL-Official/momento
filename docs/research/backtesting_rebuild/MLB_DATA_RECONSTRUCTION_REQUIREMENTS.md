# MLB Data Reconstruction Requirements

**Sport:** MLB first, end-to-end, before other sports.  
**Target universe:** every **available** 2025–2026 MLB Kalshi game market, plus the richest available official game/PBP for those games.  
**This document does not choose a commercial PBP vendor.** Waterfall 1 catalogs sources; it does not scrape or invent.

---

## 1. Two reconstructions, then a join

| Domain | Reconstruct independently | Then |
|--------|---------------------------|------|
| EVENT | Official MLB game + PBP state path | |
| MARKET | Kalshi contracts + trades/quotes/candles | |
| SYNC | | `SynchronizedState` + confidence |

If PBP is missing, the market path still exists and is labeled `event_state = UNAVAILABLE`. If Kalshi is missing, the game path still exists and is labeled `market_state = UNAVAILABLE`. **Do not drop raw because the join failed.**

---

## 2. EVENT DOMAIN — required fields (when source allows)

Must be representable (OBSERVED or UNAVAILABLE, never fake):

- `game_id` (internal), official game id when mapped
- timestamp (official play time vs wall clock — both stored)
- inning, half inning
- outs, remaining outs (DERIVED, versioned definition)
- score, score differential
- runners on base
- batter, pitcher
- pitch count, plate appearance state
- pitch state where available
- play result, previous play, PBP sequence
- home/away, game status
- eventual outcome — **terminal/label only**, not in replay-at-t views

Event clock: outs/opportunities remaining is the discrete MLB backbone, **plus** inning, half, base/out, batter/pitcher, PBP context. Wall clock is not sufficient.

---

## 3. MARKET DOMAIN — required fields (when source allows)

Per contract (Team A YES and Team B YES):

- ticker, market_id, timestamps
- YES bid, YES ask, sizes
- last trade, trade size
- spread (DERIVED)
- depth / L2 if historically OBSERVED (today: UNAVAILABLE)
- volume, status, settlement, metadata

**Starting state is mandatory to preserve whenever available** for **both** contracts:

- first observed bid/ask/spread/liquidity
- market-open timestamp if in metadata
- lag from open to first observation

Local lake today **does not guarantee** lifetime start: partitions are close/settled **PT day** windows. Reconstruction must pull **market lifetime** (open_time → settlement), not only the settlement-day slice.

---

## 4. PATH DATA

For each episode, retain pointers to:

- full event path (PBP sequence)
- full market path (both contracts)
- synchronized path

Threshold nodes (first touch of YES bid): 20, 30, 40, 50, 60, 70, 80, 90, 95.

80% first-touch is the research anchor FIRST01 will consume later. Engine must capture it even for games FIRST01 never trades.

---

## 5. Identity mapping (MLB-specific adapter)

Must eventually map, deterministically:

```text
MLB game (date, home, away, game number / doubleheader)
    ↔ internal GameId
    ↔ Kalshi event_ticker
    ↔ Team A contract + Team B contract
```

Handle: abbreviations, city/team changes, postponements, doubleheaders, canceled/unsettled markets, missing opponent contract.

Today: GameId = hash(event_ticker) only. That is necessary but not sufficient.

---

## 6. Time synchronization requirements (later waterfall; listed so raw can support it)

Join keys that raw must preserve:

- PBP timestamps (if any) + sequence numbers
- Kalshi trade `created_time`
- Candle `end_period_ts`
- Metadata `open_time` / `close_time` / `settlement_ts`

Do not assume PBP time == Kalshi trade time. Record lag. Confidence enum required.

---

## 7. What local data can support today vs not

| Requirement | Local Data-Real (Jun 18–30 2026) | Gap |
|-------------|----------------------------------|-----|
| Both contracts per game | Yes (172×2) | Only 13 days |
| Trades path | Yes, dense | Close-day window only |
| 1-min bid/ask close | Yes | Not ticks; not L2 |
| Starting price at market creation | Unknown / likely incomplete | Need lifetime candlesticks/trades from `open_time` |
| Settlement result | Metadata fields exist | Must catalog null rate |
| Inning/outs/score/PBP | No | Need MLB source |
| L2 / queue | No | Prospective WS only going forward |
| 2025 season | No | Re-query Kalshi; may be UNAVAILABLE |
| Rest of 2026 | No | Collect after catalog |

---

## 8. Honesty rules for MLB reconstruction

1. If Kalshi only has candles for a period, observability = `CANDLESTICK`. FIRST01 plugin may still **observe** first_80 on candle bid, but execution plugin must not claim maker fills.
2. If PBP lacks pitch-by-pitch, store play-level and mark pitch fields UNAVAILABLE.
3. Extra innings, rain delay, suspended games: explicit status, no silent skip.
4. Do not use eventual score to backfill missing PBP.
5. Do not infer missing L2 from trades.

---

## 9. Completion definition (MLB engine, not this step)

MLB reconstruction is complete only when, for every in-universe game/market that sources can provide:

- raw Kalshi + raw PBP archived immutably
- identity mapped or explicitly unmatched
- event path + market path + starting states
- sync confidence recorded
- first-touch table generated without lookahead
- FIRST01 plugin can consume 80% touches **without changing live code**

That is many waterfalls away. This file only constrains the data so those layers are possible.
