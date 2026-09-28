# NBA Bot 001 — execution contract proposal V2

Status: **PROPOSED, NOT APPROVED.** Nothing here changes
`execution_contract.json`. Every owner field stays
`UNRESOLVED_OWNER_INPUT` until it is selected explicitly. Production
submission stays compiled out (`PRODUCTION_ORDERS_COMPILED = false`).

V1 proposals withdrawn:

- A fixed 33¢ first hedge. It ignores gaps; see [gap](#gap).
- "Stale 3 minutes, then hold." A stale feed never authorizes indefinite
  holding; see [outage](#outage).
- "Below 25¢, hold to settlement." That is a new loss policy. It is listed
  only as an explicit option and is not a default.
- "Sell the unhedged original." Selling now requires cancellation and
  late-fill reconciliation first; see [example 4](#ex4).
- "Next batch = cash + open principal." Replaced by
  `EQUITY_AND_BATCH_SIZING.md`.

## Conventions used in every example

- A = original team YES (the entry). B = opponent YES in the same event.
  The pair is verified exact before entry. One A plus one B pays exactly
  100¢ at settlement.
- Entry: 1538 A at 78¢, fully filled. 1538 = floor(floor(2,000,000 × 600 /
  10000) / 78). Maker entry fee: 46,187cc ($4.62). A taker entry would be
  184,745cc ($18.47).
- Fees (section 1 of `FEES.md`): KXNBAGAME, M = 1, taker 7%, maker 1.75%.
  Values are in centicents (cc); 1¢ = 100cc. Every hedge or emergency leg
  is a taker.
- "Close" means a quality one-minute YES-bid close of A.
- Reserve held from entry (maker entry, emergency sale):
  **19,230,046cc = $1,923.00** (see `EQUITY_AND_BATCH_SIZING.md` §4).
- Assumption, labeled: B's best ask is near `100 − A bid`. Candles do not
  prove this, because the two markets have separate books.

Unhedged reference at settlement:

- A wins: +$333.74 (22¢ × 1538 − entry fee).
- A loses: −$1,204.26.

## Invariants already implemented (not owner choices)

These are safety rules. They hold under every option below.

1. **Persist before send.** The order record is written as `SENDING`
   before any request leaves. If persistence fails, nothing is sent.
2. **Unknown is not failed.** A timeout, 5xx, 409, or 429 becomes
   `UNKNOWN`. The order is found by venue id or by client order id before
   any dependent action. It is never blindly retried.
3. **Emergency sequencing.** The steps always run in this order:
   1. Cancel every working order in the game.
   2. Wait for each final count (cancel `reduced_by` or `GET` status).
   3. Wait until every fill record is present.
   4. Compute `unhedged = confirmed A − confirmed B`.
   5. Act.

   No step uses a stale "unhedged" figure.
4. **Amend uses a total cap.** `count = own filled + still needed`. The
   venue never fills beyond that total. If fills arrive first, the venue
   rejects the amend (total < filled) and the order is reconciled.
5. **Over-hedged → HOLD.** If B > A, excess B is never auto-sold.
6. **Inconsistent → HOLD.** An overfill, a contradiction, or a ghost order
   holds the game until an operator acts. Nothing auto-repairs.
7. **Reduce-only sale.** `reduce_only` with IOC. The venue caps it at the
   position held.

Tests: `apps/nba-001/src/exec_tests.rs` (22), `lane_tests.rs` (8), and
`strategies/nba/tests/orders.rs` (26).

---

<a id="ex1"></a>
## Example 1 — first stop close at 67

Closes after entry: 72, 70, 68, **67**.

| Step | Order | Qty | Price bound | A long | B long | Unhedged | Cash needed |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: |
| 68 close | none (local preparation only) | — | — | 1538 | 0 | 1538 | — |
| 67 close | BUY B YES, GTC, not post-only, `cancel_on_pause=false` | 1538 | ≤ 33¢ | 1538 | 0 | 1538 until fills | ≤ 5,313,437cc ($531.34) |
| fully filled at 33 | — | — | — | 1538 | 1538 | 0 | — |

- Locked result: `1538 × (100 − 78 − 33)` − fees = **−$197.60**. The fees
  are $4.62 entry plus $23.80 hedge. With a taker entry: −$211.46.
- Cash: the hedge costs up to $531.34. YES+YES collateral is not returned
  before settlement. At settlement the 1538 pairs pay $1,538.00.
- Later closes (66…55) only matter if the hedge is not yet full. See
  [ladder](#ladder).

<a id="ex2"></a>
## Example 2 — first stop close gaps to 60

Closes after entry: 72, **60**. No close at 67–61 was printed.

<a id="gap"></a>
**Owner field `hedge_initial_limit_gap_policy`.** Two options:

| Option | First order | Price bound | Likely fill (assumption above) | Cash needed | Locked if filled |
| --- | --- | --- | --- | ---: | ---: |
| G1 `OBSERVED_CLOSE` | BUY B 1538 GTC | ≤ 40¢ (`100 − 60`, capped 45) | near the B ask, if any | ≤ $641.04 | −$307.30 |
| G2 `FIRST_RUNG` | BUY B 1538 GTC | ≤ 33¢ | unlikely while B ≈ 40 | ≤ $531.34 | −$197.60 only if B falls back to 33 |

Under G2, the whole 1538 stays unhedged while A sits at 60. The limit rises
only when a later close is printed. Under G1 the first order is already
priced at the gap.

If the field stays unresolved, the lane holds
`POLICY_UNRESOLVED:hedge_initial_limit_gap_policy`, and production cannot
enter at all.

<a id="ladder"></a>
**Owner field `hedge_ladder_advancement`.** Proposal `REPRICE_ON_CLOSE`:

- At each later close c (≤ 67, ≥ 55), amend the resting hedge to
  `max(current, 100 − c)`, capped at 45.
- Count = own filled + still needed.
- The limit is never lowered on a bounce.

Worked case: resting at 33, 400 filled, then a close at 64. The amend is
price 36, total 1538. The venue has 1138 resting at 36. A bounce to 66
keeps 36. Test: `ladder_reprices_upward_with_amend`.

<a id="ex3"></a>
## Example 3 — first stop close below 55 (Market Dump)

Closes after entry: 71, **50**.

<a id="emergency"></a>
**Owner field `emergency_action`.** Sequencing follows invariant 3. There
are no working orders here, so unhedged = 1538.

| Option | Order | Qty | Price bound | Cash needed | Result at 50 | After the order |
| --- | --- | ---: | --- | ---: | ---: | --- |
| E1 `SELL_ORIGINAL_REDUCE_ONLY_IOC` | SELL A, reduce-only IOC | 1538 | ≥ floor F | 0 (proceeds ≈ $742.09 at 50) | −$462.17 realized | flat; cash free now |
| E2 `BUY_OPPONENT_IOC` | BUY B, IOC | 1538 | ≤ worst W | ≈ $795.92 at 50 | −$462.17 locked | 1538 pairs held to settlement; cash returns then |

If the order runs out of liquidity above F, or below W, the IOC remainder
is cancelled by the venue. The residual is reconciled, then:

- **Owner input:** the re-issue rule. Options include every later close,
  every N seconds, or with a price step.
- **Owner input:** what happens when nothing fills at F. Holding the
  remainder to settlement is one option; it is **not approved** and is not
  the default. A 25¢ floor-then-hold is that option with F = 25.

Loss if all 1538 A are sold at a given bid (maker entry, taker sale):

| A bid | 40 | 30 | 25 | 10 | 5 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Realized | −$614.90 | −$765.47 | −$839.95 | −$1,060.15 | −$1,132.47 |

Reserve effect:

- E1 needs no cash beyond the 45-cap hedge reserve. Its exit bound is 45.
- E2 reserves `max(45, W)` × 1538 + fee. For W = 55 that is
  20,768,046cc ($2,076.80) per entry, versus $1,923.00 under E1.

<a id="ex4"></a>
## Example 4 — partial hedge, then emergency

State: the hedge rests at 40 for 1538 and has filled 600. The next close
is **54**, which is below 55, so it is an emergency (E1 shown). A further
150 B fill lands while the cancel is in flight.

| Step | Action | Venue truth after the step | A | B confirmed | Unhedged used |
| --- | --- | --- | ---: | ---: | --- |
| 1 | DELETE the hedge | 150 fill arrives; cancel `reduced_by = 788` | 1538 | 600 (records) | not computed |
| 2 | `GET` order: canceled, `fill_count = 750` | final count known | 1538 | 750 after fill records | not computed |
| 3 | fill records 750 = venue 750 | settled | 1538 | 750 | **788** |
| 4 | SELL A reduce-only IOC 788, ≥ F | fills 788 at 54 | 750 | 750 | 0 → flat (750 pairs) |

- Result: 750 pairs at 40 (−$135.00), 788 sold at 54 (−$189.12), and fees
  ($4.62 entry, $12.60 hedge, $13.70 sale) = **−$355.04**.
- Cash: hedge $312.60 spent. Sale proceeds $411.82 are returned at once.
  The pairs pay $750.00 at settlement.
- Stale sale that would be refused: selling `1538 − 600 = 938` would
  leave A 600 and B 750. That is 150 unpaired B, a new directional
  position. Invariant 3 prevents it.
- Tests: `partial_hedge_then_emergency_with_late_fill` (lane) and
  `partial_hedge_then_emergency_sale_of_reconciled_residual_only`
  (executor).

<a id="ex5"></a>
## Example 5 — late hedge fill during cancellation

Hedge resting at 36, 1538 total, 400 filled. A cancel is sent because of an
emergency, a game end, or a replace.

| Venue response | Meaning | Next step | Exposure used |
| --- | --- | --- | --- |
| `reduced_by = 1000` | 138 filled after the last read | final 538; wait for 538 fill records | unhedged = 1538 − 538 = 1000 |
| 404 on cancel | the order is already gone (fully filled or cancelled) | `UNKNOWN` → `GET` order → e.g. executed 1538 | 0 unhedged; flat |
| timeout | unknown whether the cancel landed | `UNKNOWN`; no new order in the game until `GET` shows a final count | none computed |
| amend race (price raise) | fills land before the amend | amend total 1538 caps it; if total < filled, 400 → reconcile | never above 1538 B |

Tests:

- `late_fill_during_cancel_is_reconciled_before_replacement`
- `cancel_404_after_full_fill_reads_final_count`
- `cancel_timeout_then_reconcile`
- `amend_raises_price_with_total_cap_under_a_race`

<a id="ex6"></a>
## Example 6 — data outage with an open position

State: the hedge rests at 36, 400 filled, so the residual is 1138. Candles
have been stale for 180 s. The account API may or may not be up.

<a id="outage"></a>
**Owner field `data_outage_policy`.** The proposal escalates on a finite
timer. Neither option holds indefinitely.

| Option | At T seconds stale | Order | Qty | Price bound | Cash needed |
| --- | --- | --- | ---: | --- | ---: |
| O1 `HEDGE_AT_CAP` | raise the residual hedge to the cap | amend B to 45, total 1538 | 1138 resting | ≤ 45¢ | ≤ 5,318,159cc ($531.82) |
| O2 `EMERGENCY` | run the emergency policy (example 4 sequencing) | cancel → reconcile → E1/E2 | reconciled residual | F or W | per E1/E2 |

- Owner inputs: T, the option, and which feeds count (candles, clock,
  account). The worked tests use T = 300 s as a fixture value only. That
  is not a proposal of 300.
- If the account API is also down, nothing new is sent, because the
  residual cannot be reconciled. The resting B order stays on
  (`cancel_on_pause = false`), and any fills are reconciled when the API
  returns. That is "no new orders without reconciliation", not "hold".
- If O1 fully fills: 400 at 36 and 1138 at 45, locked at −$348.53.
- Tests: `outage_escalates_only_under_a_policy`.

<a id="entry"></a>
## Entry order (owner field `entry_order`)

Proposal:

- BUY A 1538 at 78, GTC, `cancel_on_pause = true`.
- Expiry E seconds (owner input).
- Cancel on top-out (bid close ≥ 85), which is already resolved.
- Partial fill at cancel or expiry: keep the partial position and size the
  hedge to it.

`post_only` is an owner input:

- True: maker fee $4.62. The order is rejected if it would cross.
- False: it may take liquidity, with a taker fee of $18.47.

<a id="release"></a>
## Slot and batch release (owner field `slot_and_batch_release`)

Proposal: a slot is released at `CASH_AVAILABLE`, meaning after
settlement is confirmed and cash is visible on the shard. A trade counts
toward the batch at the same time. `HEDGE_COMPLETE` never releases a slot,
because YES+YES collateral stays locked until settlement.
