# October 3 protocol

First registered 2026-09-22 under `nba-001-v0`. Revised 2026-09-26 for
`nba-001-v1` (FIRST78_67), before any October 3, 2026 outcome. This file
is the test plan. It is not a result.

The October 3 run does not submit orders: the worker links no submission
adapter. It does not set `VITAL_AWS_CONTROL` and does not start or stop
`momento-live.service`.

## Lookup

On 2026-09-22 and again on 2026-09-26, Kalshi listed no `KXNBAGAME` event
for 2026-10-03. The listed NBA game events are three games dated
2026-10-20 (OKC–SAS, PHI–NYK, BOS–DET). Those October 20 games are not the
October 3 slate and are not substituted for it. ESPN lists MIA @ TOR at
2026-10-03T23:00Z as preseason.

October 3, 2026 `KXNBAGAME` markets: `UNAVAILABLE`.

The deployed worker rediscovers every 300 s. If an October 3 event is
listed, `status.json` `october_3` changes from `UNAVAILABLE` to `LISTED`
with the event ticker, and the game enters the normal per-game path
(24 h backfill, then live). Do not fill a missing game with a nearby date.

## Separation

Preseason is reported separately from regular season. A preseason game is
not pooled into the regular-season count. The same FIRST78_67 rule applies
to both. If the slate is `UNAVAILABLE`, both cells stay `UNAVAILABLE`
rather than zero.

## What the worker records

When a game and its markets exist, in SHADOW:

- Series and per-market `exchange_index`. The market index is the authority
  (the series index names the shard for new events only). The two legs must
  agree, or `ROUTE_PAIR_MISMATCH`.
- Each one-minute candle close used for a decision, and that the rule
  waited for the close. Non-quality bars (spread > 10, missing sides)
  do not qualify.
- The Kalshi `live_data` clock (quarter, time remaining, age). A stale
  clock blocks the signal.
- The first 78 touch or cross in Q2/Q3 and the top-out 85 check.
- The complement pair check (same event, opponent team, both active,
  same index).
- The admission result with every blocker, and the local intent with its
  deterministic `client_order_id`. No order is sent.
- After an entry signal in SHADOW: the local 68 preparation and the first
  later close at or below 67. The hedge ladder is local only.
- Fill: `UNAVAILABLE` unless an exchange fill is observed. A close is not
  a fill.

## Expected blockers on October 3

Unless the owner resolves them first, any October 3 signal is blocked by
`CONTRACT_UNRESOLVED`, `EXIT_CAPACITY_UNBOUNDED`, `FEE_UNVERIFIED`,
`LIVE_GATES_UNSET`, `SHARED_COLLATERAL_UNACCOUNTED`, and
`PRODUCTION_SUBMISSION_DISABLED` (production orders are compiled out). A new
NBA event listed after 2026-09-10 is expected on shard 3, so its cash check
reads shard 3.

## Stop

`execution_authorized` stays false. Fills and P&L stay `UNAVAILABLE`.
