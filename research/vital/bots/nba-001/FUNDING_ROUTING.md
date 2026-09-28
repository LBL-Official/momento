# NBA Bot 001 — funding and routing evidence

```text
NO FUNDS MOVED
NO FUNDING INSTRUCTION UNTIL ROUTING IS VERIFIED
SHARD IS AN ASSERTION TO VERIFY, NOT A DEFAULT
```

Nothing was transferred during this task. MLB routing is not reused.

## Public API evidence (unsigned, production host)

Read 2026-09-27T03:54Z from `https://external-api.kalshi.com/trade-api/v2`.

| Object | `exchange_index` | Other |
| --- | --- | --- |
| Series `KXNBAGAME` | **3** | `fee_type=quadratic_with_maker_fees`, `fee_multiplier=1`, `last_updated_ts=2026-09-25T15:42:42Z` |
| Series `KXWNBAGAME` | 3 | `fee_multiplier=1`, updated 2026-09-25 |
| Series `KXMLBGAME` | 3 | `fee_multiplier=0.5`, updated 2026-09-25 |
| Series `KXNCAAMBGAME` | 3 | updated 2026-09-24 |
| Open `KXNBAGAME` markets (6, three Oct 20 games, created 2026-08-20) | **0** | all six |
| Open `KXWNBAGAME` markets (16, created 2026-09-25) | 3 | all sixteen |
| Open `KXMLBGAME` markets (34) | 3 | all |
| `KXNBAPRESEASON`, `KXNBAPRE` | — | `not_found` |
| `GET /series/fee_changes?series_ticker=KXNBAGAME` | — | empty |

Event `KXNBAGAME-26OCT20BOSDET`: `mutually_exclusive=true`, two markets
(BOS, DET). `rules_primary` differs only by the YES team.
`rules_secondary` is identical: a game postponed more than 48 hours, or
cancelled, resolves all markets to a fair price.

## Routing: resolved from documentation (2026-09-27)

Source: Kalshi "Exchange Sharding"
(`docs.kalshi.com/getting_started/exchange_sharding`), read 2026-09-27.

- "The `exchange_index` field is the authoritative source of truth" for a
  market. "All child markets of an event will live on the same exchange
  instance." "There is currently no plan to migrate any live market."
- The series table is "Upcoming Series Shard Assignments": it "determines
  the shard where new events will be created." Basketball moved to shard 3
  on 2026-09-10 12:00 ET, which matches the `KXNBAGAME` series change.
- Orders omit `exchange_index` and pass the market ticker, so they
  auto-route by ticker. "An order ID alone cannot identify the exchange
  shard", so cancels also pass `market_ticker`.

A series showing 3 while an older event shows 0 is expected, not a
conflict. The earlier `ROUTE_CONFLICT` blocker is removed. What remains:

| Rule | Reason code |
| --- | --- |
| The market's own `exchange_index` is the shard for its cash and orders | — |
| Both legs of a pair must report the same index (an event cannot span shards, so a mismatch, or one leg missing its index, means bad data) | `ROUTE_PAIR_MISMATCH` |
| Neither leg's index has been read | `ROUTING_UNVERIFIED` |

Practical consequence:

- The three Oct 20 games (listed 2026-08-20) trade on **shard 0**.
- Every NBA event listed after 2026-09-10, including the Oct 3 preseason
  game once listed, is expected on **shard 3**. The worker reads each
  market's index rather than assuming this.
- Shard 3 is where `momento-live.service` submits MLB and WNBA orders
  from the same credential.

## Subaccount: what it isolates

Source: Kalshi "Subaccounts" and "Exchange Sharding", read 2026-09-27.

| Question | Documented answer |
| --- | --- |
| Does a subaccount isolate cash? | Yes. Subaccounts "partition its balance and positions into independent buckets under one set of API credentials." |
| Does it isolate order collateral? | Orders placed with `subaccount = n` are collateralized from subaccount `n` ("collateralization checks … run within the matching engine" per shard; "subaccount balances are local to a specific exchange instance"). |
| Per shard? | Yes. A subaccount must be provisioned with `exchange_index` on each shard it trades, and funded there. |
| Who can create one? | Advanced API tier and above. Numbers 1–63. API only, not in the web app. |
| Transfers | `POST /portfolio/subaccounts/transfer` with `exchange_index`, idempotent on `client_transfer_id` (retry returns 409). Nothing leaves the account. |
| Restricted key | A key restricted to one subaccount "can only read and trade on that subaccount". It cannot transfer funds or manage subaccounts or keys. Other subaccounts are rejected. |
| Auto-rebalancing | Opt-in target percentages across shards, applied every 10 s using "account balance minus the value of its resting orders". The docs do not say whether numbered subaccounts are included. **Unverified.** |

## Host evidence (2026-09-27, GET-only)

`momento-nba-001 evidence`, one-off copy of build
`nba001-20260927T073047Z` on `i-0f0849d5829476c31` (service binary
unchanged, `non_get_sent=false`, `funds_moved=false`):

| Read | Result |
| --- | --- |
| API tier (`/account/limits`) | **`basic`** (read 200/s, write 100/s) |
| Subaccounts (`/portfolio/subaccounts/balances`) | only subaccount 0: shard 0 $57.4100, shard 3 $0.5682 |
| Netting (`/portfolio/subaccounts/netting`) | disabled for subaccount 0 on shards 0 and 3 |
| Auto-rebalancing (`/portfolio/target_balance_allocation`) | `allocations: []` (disabled); `resting_margin_reservation: sum` |
| Routing | series `KXNBAGAME` 3; open events BOS–DET, PHI–NYK, OKC–SAS: event and both markets 0 |

Consequence: **subaccounts are not available at the `basic` tier**
(Create Subaccount needs Advanced or above). Configuration S1 below needs
a tier change first. Auto-rebalancing is off, so no automatic transfer
moves cash under either bot today.

## Subaccount: concrete configuration (proposal, nothing created)

**Configuration S1:** NBA subaccount `1` with its own restricted key.

0. Move the account to the Advanced API tier. It is `basic` today.
1. Create subaccount 1 with `exchange_index = 0`, and again with
   `exchange_index = 3`.
2. Move the NBA working capital from the primary account to subaccount 1
   on the shard of the market being traded:
   - shard 0 for the Oct 20 games;
   - shard 3 for games listed after 2026-09-10.
3. Issue a new API key restricted to subaccount 1 for `nba-001` only,
   stored in a separate AWS secret. MLB keeps its current key.
4. The worker sets `subaccount = 1` on every order and read. With a
   restricted key the venue enforces it anyway.

**Effect on MLB Bot 001 (`momento-live.service`):**

- MLB orders carry no `subaccount` and so use the primary account (0).
  That is unchanged.
- Cash moved into subaccount 1 is no longer available to MLB orders. NBA
  orders can no longer consume MLB's collateral on shard 3.
- MLB sizing does not read the exchange balance: it uses the configured
  weekly snapshot (`available_balance` is unsupported in
  `crates/kalshi/src/venue.rs`). So MLB sizing does not change, but MLB's
  primary-account cash on shard 3 must still cover MLB's own orders.
- MLB's binary, service, policy, and key are untouched.
- A restricted NBA key cannot see or cancel MLB orders. The shared-key
  risk goes away for NBA; it does not change for MLB.

**Effect on `SHARED_COLLATERAL_UNACCOUNTED`:** with S1 in place and
verified by a GET of `/portfolio/subaccounts/balances`, NBA reservations
are checked against subaccount 1's cash on the traded shard only. The
blocker becomes a per-shard subaccount balance check.

**What S1 does not solve:**

- Shard placement. Cash on shard 0 cannot collateralize a shard-3 market.
  Each game's shard decides where the NBA cash must sit.
- Auto-rebalancing. It is off today (`allocations: []`). If it were
  enabled, it might move primary cash between shards under MLB. Whether
  it touches numbered subaccounts is unverified.

**Configuration S0 (no subaccount), for comparison:**

- NBA and MLB share primary cash on shard 3.
- The worker would have to subtract MLB's resting-order value and open
  exposure, which it can read, before admitting an entry. MLB can still
  consume cash between the read and the NBA order.
- `SHARED_COLLATERAL_UNACCOUNTED` stays.

Choosing S1, or S0 with an account-wide reservation rule, is an owner
decision. No subaccount was created, no key was issued, and no transfer
was made.

## October 3

ESPN lists MIA @ TOR, 2026-10-03T23:00Z, `season.slug=preseason`.
Kalshi has no `KXNBAGAME` event for it yet. Status: `UNAVAILABLE`.

## Signed account evidence

Collected on the host by `momento-nba-001 probe` (read-only
`ProductionObserveTransport`, GET only). Not collected from a laptop:
the credential stays in AWS.

Read 2026-09-27T04:30:21Z on `i-0f0849d5829476c31`, build
`nba001-20260927T042347Z` (binary `9ef129e1…6789`). Probe output:
`funds_moved:false`, `non_get_sent:false`, 5 GETs.

| Shard (`exchange_index`) | Cash (API string) | Cents (floored) |
| --- | --- | --- |
| 0 | `57.4100` | 5741 |
| 1 | `0.0000` | 0 |
| 2 | `0.0000` | 0 |
| 3 | `0.5682` | 56 |

Total balance 5797¢. Portfolio value 0¢. No `KXNBAGAME` positions. No
resting orders. No order carrying the `nba001-` client-order-id prefix.

The same credential is used by `momento-live.service` (MLB/WNBA on
shard 3), so these balances are shared, not NBA-owned. The probe's
event read from the host agreed with the earlier public read: all three Oct 20
events report `exchange_index` 0 at event and market level, and series
`KXNBAGAME` reports 3.

Capacity at these balances: per-entry reserve is unbounded (emergency
bound unresolved), so capacity is `UNAVAILABLE` on every shard, not a
number. Even with the ladder cap alone (193,687¢ per standard entry),
5741¢ on shard 0 funds zero standard entries.

## Funding instruction

Still withheld. Routing is resolved, but the destination depends on
owner choices:

1. The subaccount configuration (S1 or S0).
2. Which games are in scope:
   - The three Oct 20 games trade on shard 0.
   - Games listed after 2026-09-10 are expected on shard 3.
3. The amount. Capacity follows from the per-entry reserve (see
   `strategy/EQUITY_AND_BATCH_SIZING.md`: $5,000 on one shard funds two
   concurrent standard entries at the worker's 192,301¢ reserve).

Funding also does not activate trading, because production orders are
compiled out of the worker.
