# Vital MLB 001 Fill-Reconciliation Incident Report

## Incident

Date:
2026-09-15

Host: `i-0f0849d5829476c31` / `momento-live.service` PID 442826.
Read-only venue GETs used the existing production secret file on the host.
No production restart. No Create V2. No Risk/strategy/submit edit.

## Established Failure

Valid First80 → Confirm81 occurred.

Risk rejected entry because all 5 slots were occupied.

## Root Cause

The five stale slots are real venue-filled entry orders whose **fills
endpoint rows were never applied locally**.

`GET /fills?limit=100` **did retrieve** four of the five orders on page 0
(168 fills exist; page 1 then returned 68). Pagination alone is **not**
the reason those four never applied.

Every portfolio fill in the 168-row book **omits `client_order_id`**
(0 present, 168 absent). `ingest_one_fill` required
`decode_client_order_id` and returned on failure. Empty/missing client
id ⇒ **every fill skipped**. `fill_applied` today = 0.

That is a **systemic ingest identity failure**, not a one-off missing
row. Cursor pagination is still required (168 > 100) and is now
implemented; it was incomplete as the sole diagnosis.

DETCLE’s fill is integer `7.00` and is returned by
`GET /fills?order_id=…`. Its fill `ticker` is `…DETCLEG2-DET` while
`GET /orders/{id}` and local identity use `…DETCLEG2-CLE`. Matching is
by venue `order_id`, which agrees. The fill ticker is not used to
rebind the market.

AZHOU’s fills are `6.65` + `0.35` (`= 7.00`). Existing
`count_fp_to_contracts` fail-closes on fractional counts. Those two
rows **cannot** become a local fill without a new mapping rule or
inventing `7` from `get_order`. That was not done.

## Five Orders

| Order | Venue | Local | Venue Fill | Local Fill | Settlement | Result |
|---|---|---|---:|---:|---|---|
| CINMIL-MIL 82¢ | `GET /orders` executed 7.00 / remain 0.00; order `01a09c31-2a98-748f-82c5-af838141f658` | Working / Building / 0 fill / reservation 574¢ | 7.00 @ 0.8200; trade `0722ed3c-0679-93e9-3605-fc1bf0180598`; page 0 | 0 | finalized `result=no` proceeds `$0` `2026-09-13T20:52:38Z` | VENUE FILL PRESENT; local apply blocked by missing `client_order_id` (repair in repo; not loaded on host) |
| PHIATL-PHI 80¢ | executed 7.00; order `01a09365-6578-747f-bb6e-75ad9062a6e1` | Working / Building / 0 / reservation 560¢ | 7.00 @ 0.8000; trade `0722def0-f099-9305-59af-336aa9bb018d`; page 0 | 0 | finalized `result=no` `$0` `2026-09-12T03:17:38Z` | same |
| CWSSTL-STL 81¢ | executed 7.00; order `01a0982f-2e40-7140-9e4a-21fd1dc214a5` | Working / Building / 0 / reservation 567¢ | 7.00 @ 0.8100; trade `0722f8f2-0fa1-a882-1849-3e86f3bef831`; page 0 | 0 | finalized `result=no` `$0` `2026-09-13T02:57:28Z` | same |
| DETCLEG2-CLE 83¢ | executed 7.00; order `01a06f44-b568-732f-bc98-b3c90503dc5c`; `client_order_id` on **order** present | Working / Building / 0 / reservation 581¢ | 7.00 @ 0.8300 via `?order_id=`; fill ticker `…DET`; trade `0721d252-6989-bfd9-7cfc-fab1f934fb24` | 0 | CLE market finalized `result=yes` `$1.00` `2026-09-05T02:47:35Z` | VENUE FILL PRESENT (order_id query); default list ticker filter missed CLE; identity match is order_id |
| AZHOU-HOU 81¢ | executed 7.00; order `01a07435-5398-7fcd-82e4-ea6b1c8b44f9` | Working / Building / 0 / reservation 567¢ | **6.65 + 0.35** @ 0.8100; trades `0721a4ec-e0f9-92bf-1da2-85e37b1415d9`, `0721a4ec-f059-b213-bbb0-225a1b9d814d` | 0 | finalized `result=no` `$0` `2026-09-06T02:42:35Z` | **FILL UNREPRESENTABLE** under integer `Contracts`. `get_order` 7.00 was **not** applied |

Local bot: `mlb-001` / factory `mlb_factory_v1` / strategy id `1`.
Kill Armed. Tracker recon Healthy. `open_slots=5`, `open_desk_positions=0`.

## Fill Ingest

Verified causes:

1. **Identity:** portfolio fills omit `client_order_id`. Ingest required it
   and dropped the row. This affects **all 168** fills, not only the five.
2. **Pagination:** 168 > 100. Page 0 cursor is non-empty. DETCLE’s integer
   fill is older and is found reliably by `order_id`, not by a CLE ticker
   filter on page 0.
3. **Not** a bot/market filter on `list_fills("limit=100")`.
4. **Not** a persistence overwrite of applied fills (`fill_applied` never
   fired for these).
5. **AZHOU:** fill rows exist but `6.65` / `0.35` fail
   `count_fp_to_contracts` (existing fail-closed). Not applied.

`get_order` Filled is **not** treated as a local fill record.

## Repair

Minimal, existing path only:

- Accept missing/`null` `client_order_id` on `KalshiFill`.
- Resolve the local order by `decode_client_order_id` **or**
  `order_id` → `tracker.order_by_venue_id`.
- Hydrate the local client id onto the fill **after** that match, then
  `map_fill` → `PartialFill` / `LiquidationFill` (existing apply +
  `DuplicateIgnored`).
- Paginate `GET /fills` (`limit=100`, cursor, max 20 pages) — same
  pattern as order reconcile / `jump-fills-read`.
- If occupancy sees venue `Filled` with `filled>0`, fetch
  `GET /fills?order_id=` and ingest those rows. Still no fill invented
  from `get_order` counts.
- Demo/ITI now call the same `ingest_fills` (not a second engine; not
  factory 80/81).

Operator authorized deploy/restart 2026-09-16. Applied on host:

1. Factory binary `/usr/local/bin/momento-trading-engine`
   sha256 `610dd470b1769a0385c81942ec634362ce8607b2db6f8f44156cf7757a147250`
   (previous `fb939b622483553a5cb7d9c066944c5ec0065290d2eae9d478e71f078e9e00f8`).
2. `systemctl restart momento-live.service` — PID **1054745**
   started `2026-09-16 05:25:30 UTC`. Demo binary hash unchanged.
3. Official REST fill pages send both `ticker` and `market_ticker`.
   A serde alias treated that as a duplicate and dropped every page.
   Ingest now accepts both names and does not invent a fill from
   `get_order`.
4. Fractional `count_fp` parts that sum to an integer contract count
   on the same `order_id` + `yes_price_dollars` coalesce to one
   integer fill (observed AZHOU `6.65+0.35=7.00`). Mixed prices and
   non-integer sums stay fail-closed. Integer rows plus leftover
   fractional parts on the same order do not double-count.

## Trading Logic Changes

NONE

## Risk Changes

NONE

## Submit Changes

NONE

## Production Restart

Authorized. `momento-live.service` restarted 2026-09-16 05:25:30 UTC.
`live.toml`, Risk cap, 80/81/83/89, and Create V2 were not edited.

## Production Orders During Repair

NONE (`submit_to_ack=0`, `submit_refused=0` on the new PID).

## Occupancy Before

5 stale Working reservations (`pending_new_slots=5`,
`reservations=5`, `open_contracts=0`). Heartbeat `open_slots=5` all day
2026-09-15.

## Occupancy After

Measured on PID 1054745 after ingest + existing settlement (not
hand-edited):

| Order | Local after | Fills | Lifecycle |
|---|---|---:|---|
| CINMIL-MIL 82¢ | Filled 7 | 1 | Settled |
| PHIATL-PHI 80¢ | Filled 7 | 1 | Settled |
| CWSSTL-STL 81¢ | Filled 7 | 1 | Settled |
| DETCLEG2-CLE 83¢ | Filled 7 | 1 | Settled |
| AZHOU-HOU 81¢ | Filled 7 | 1 | Settled |

Heartbeat: `open_slots=0` `open_desk_positions=0` `max_open_slots=5`.
Risk persist: `pending_new_slots=0` `open_contracts=0`.
Journal since restart: `fill_applied=31` `fill_page_unreadable=0`
`fill_map_failed=0`. No fill was taken from `get_order` counts.
Settled positions `55 → 86` (31 venue fills applied, then existing
`refresh_held_positions`). Cap unchanged. No invented P&L on the
2026-09-15 missed First81s.

## Today's Trading Incident

```text
VALID SIGNAL
→ RISK
→ PositionLimitExceeded
→ NO SUBMIT
```

26,452 MLB YES updates; 1,368 ≥80; 594 in 80–83 below ask;
14 First80; 13 First81; 436 `PositionLimitExceeded`;
29 `entry_gate=resumed`; 0 `submit_to_ack`; 0 `submit_refused`;
0 `fill_applied`.

The 13 confirm-81 Builds never reached Create V2 because Risk already
counted five occupied slots. There is **no** basis for hypothetical
fills or P&L on today’s missed entries.

## Demo Bots

Journal since 2026-09-15 07:00 UTC. Factory live unit was not used.
Demo binary hash unchanged
`06bafb9ce974cabcb9cd088ec530477cb69f271aa846ba08beff23946d8ad0ee`.
Not factory-ized (`factory_80=0`). `live_armed=false` `env=demo`.

| Unit | Active | Heartbeats | submit_to_ack | fill_applied | Notes |
|---|---|---:|---:|---:|---|
| mlb-002 | active | 6218 | 0 | 0 | ITI heartbeat `sport=nba` `open_slots=0` |
| mlb-003 | active | 6212 | 0 | 0 | ITI heartbeat `sport=nba` `open_slots=0` |
| mlb-004 | active | 6215 | 0 | 0 | ITI heartbeat `sport=nba` `open_slots=0` |
| mlb-005 | active | 6203 | 0 | 0 | ITI heartbeat `sport=mlb` `open_slots=1`; `submit_refused=5` |
| atp-001 | active | 5133 | 0 | 0 | ITI heartbeat `sport=atp` `open_slots=0` |

They were alive on the isolated ITI path. They did not take a Demo
Create V2 ack in this window. They were not given 80/81. The factory
ingest binary was not installed on `momento-trading-engine-demo`.

## Tests

Run after the authorized deploy:

- `cargo test -p momento-kalshi --test adapter fill` — **10 passed**
  (includes `fill_json_with_ticker_and_market_ticker_deserializes`)
- `cargo test -p momento-trading-engine --test live_host fill` — **19 passed**
- `cargo clippy -p momento-kalshi -p momento-trading-engine --tests -- -D warnings` — clean

Added coverage:

- official REST page with both `ticker` and `market_ticker`
- `6.65+0.35` coalesce, idempotent coalesce, lone fractional skip,
  mixed-price fail-closed, split-page coalesce, integer+fractional
  no double-count
- existing missing-`client_order_id`, pagination, no fabricate-from-
  `get_order`, five-slot clear-after-fills

Risk cap in those tests remains `max_open_positions()==5`.

## Follow-up 2026-09-16 21:00Z — sticky Ambiguous after occupancy clear

After the authorized ingest deploy, Risk slots were empty (`open_slots=0`)
but the process stayed `reconciliation=Ambiguous` / `order_submission=blocked`.

Host persist (PID 1101134, started 20:00:11 UTC):

- `unknown=[]`, reservations empty
- one leftover entry `client=1788570063052088861` (`01a06f15-5098-7c5d-8027-522258f16b81`)
  locally `PartiallyFilled` 1/7 @ 82¢ on a **Settled** position
- Kalshi `get_order` reports `filled=7` every occupancy tick
- local fill received_at `2026-09-16T05:25:30Z` (ingest restart)

Cause: `Fill` `PartialEq` includes `received_at`. Housekeeping re-maps the
same venue `fill_id` with `utc_now()`, treats it as `ConflictingEvent`, and
`mark_ambiguous()` persists. `rebuild_recon_gate` is never called, so
Ambiguous survives a restart even with zero unknowns.

Repair in repo (not yet on the host binary `610dd470…`):

- same `fill_id` + same economic fields ⇒ `DuplicateIgnored` (ignore receipt /
  exchange-ts mapping)
- qty mismatch on a **Settled** position does not overwrite history and does
  not freeze the desk
- qty mismatch on an **open** position still `Ambiguous`
- `release_ambiguous_if_no_live_uncertainty` after housekeeping
- occupancy sync skips Settled leftovers

Do not invent the missing 6 contracts from `get_order`. Do not edit
`live-runtime.json` by hand. New entries still require a real 80→81.
