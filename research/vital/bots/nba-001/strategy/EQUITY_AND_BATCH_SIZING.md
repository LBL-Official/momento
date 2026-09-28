# NBA Bot 001 — reference equity, spendable cash, batch sizing

Status:

- Batch 1 sizing is **RESOLVED**: R0 = $20,000.
- The batch 2+ formula is **PROPOSED, NOT APPROVED**
  (`batch_resize.status = PROPOSED_NOT_APPROVED`). Until it is approved,
  batch 2 does not open: `BATCH_RESIZE_UNAPPROVED` blocks entries after
  the tenth completion.
- The rejected rule "exchange cash + open principal" is not used. It drops
  the $15,000 external reserve, and it values a two-leg position by one
  leg's principal.

Code: `strategies/nba/src/batch.rs` (`EquityLedger`). Tests are the six
`equity_*` tests in `strategies/nba/tests/first78_67.rs`.

## 1. Two separate quantities

| Quantity | Meaning | Source | Used for |
| --- | --- | --- | --- |
| Reference equity `E` | strategy capital, including the disclosed external reserve | ledger (fills, settlements, capital flows) | **sizing** (6% of E) |
| Spendable exchange cash `S[i]` | cash on shard `i` (and subaccount, if configured) | `GET /portfolio/balance?exchange_index=i` each account pass | **affordability** only |

- A trade is sized from `E` and admitted only if `S` covers its reserve
  (§4).
- An unaffordable trade is `BLOCKED_INSUFFICIENT_CASH`. It is never resized
  down.
- An unread `S` is `UNAVAILABLE`, never $0.

## 2. Capital flows

| Flow | Changes E? | Changes S? |
| --- | --- | --- |
| `RESERVE_TO_EXCHANGE` (part of the disclosed $15,000 deposited) | no | +amount |
| `EXCHANGE_TO_RESERVE` | no | −amount |
| `INTRA_ACCOUNT_TRANSFER` (shard 0↔3, subaccount↔primary) | no | moves between shards or subaccounts |
| `OWNER_CONTRIBUTION` (new capital beyond $20,000) | +amount | +amount if deposited |
| `OWNER_DISTRIBUTION` (capital removed from the strategy) | −amount | −amount if withdrawn |

- Internal transfers create no P&L.
- The reserve is counted exactly once. It is already inside R0, so
  depositing it does not add to E.
- `external_reserve_outstanding = 1,500,000¢ − deposits + returns` is
  informational.

## 3. Sizing formula (proposed for batch ≥ 2)

```text
E = R0 + Σ OWNER_CONTRIBUTION − Σ OWNER_DISTRIBUTION
      + Σ settled trades  net P&L
      + Σ open trades     open contribution

net P&L  = settlement payout + A sale proceeds
           − A cost − B cost − every trade fee (incl. rounding) − settlement fee

open contribution = locked pairs × 100¢
                  + unpaired contracts at average cost
                  + A sale proceeds − A cost − B cost − fees paid

batch n+1 reference = floor_to_cent(E) at the tenth completion of batch n
quantity            = floor( floor(reference × 600 / 10000) / 78 )
```

How the formula handles each case:

- **Both hedge legs.** A pair (A + B) is valued at exactly 100¢, which is
  what it pays. The two costs are subtracted separately.
- **Unhedged open trade.** It counts at cost, so its contribution is
  −(fees paid) and no mark-to-market. Owner option: value unpaired
  contracts at `min(average cost, current bid)` instead, which is more
  conservative. Not selected.
- **No double counting.** Each trade contributes either its open term or,
  once settled, its net P&L. Never both.
- **Fees.** Every fill fee, including order rounding, and the settlement
  fee.
- **Arithmetic.** Integers in centicents, floored to cents at the batch
  boundary.

### Worked example (illustrative results, not a forecast)

Batch 1: R0 = $20,000, 1538 contracts, maker entry. Ten settled trades plus
two still open at the tenth release:

| Trades | Each | Sum |
| --- | ---: | ---: |
| 6 won unhedged (settle 100) | +$333.7413 | +$2,002.4478 |
| 3 hedged at 33 | −$197.6024 | −$592.8072 |
| 1 emergency sale at 50 | −$462.1737 | −$462.1737 |
| open: hedge complete at 36 (1538 pairs) | −$244.7436 | −$244.7436 |
| open: entered, unhedged | −$4.6187 (fee) | −$4.6187 |

- E = $20,000 + $947.4669 − $249.3623 = **$20,698.1046**, floored to
  2,069,810¢.
- Batch 2 quantity = floor(floor(2,069,810 × 600 / 10000) / 78) =
  floor(124,188 / 78) = **1592**.
- After a $1,000 owner distribution, the quantity would be **1515**.
- Depositing the remaining $15,000 reserve changes neither number.

## 4. Reservation totals (reproduced)

Per entry (1538 contracts, M = 1):

```text
reserve = principal + entry fee + qty × exit price + taker fee at the exit price
exit price = 45 (ladder cap) for SELL_ORIGINAL; max(45, W) for BUY_OPPONENT
```

| Component | Maker entry (post-only) | Taker entry |
| --- | ---: | ---: |
| principal 1538 × 78 | 11,996,400cc | 11,996,400cc |
| entry fee @78 | 46,187cc | 184,745cc |
| hedge/exit 1538 × 45 | 6,921,000cc | 6,921,000cc |
| taker fee @45 | 266,459cc | 266,459cc |
| **total** | **19,230,046cc = $1,923.0046** | **19,368,604cc = $1,936.8604** |
| worker (fees rounded up to whole cents) | 192,301¢ | 193,687¢ |

- With `BUY_OPPONENT_IOC` and W = 55, the exit leg becomes 1538 × 55 =
  8,459,000cc. The totals are then 20,768,046cc (maker) and 20,906,604cc
  (taker).
- While the emergency action is unresolved, the exit bound is unbounded
  and entries stay blocked (`EXIT_CAPACITY_UNBOUNDED`).

Outstanding reserve per open trade = unfilled entry principal and fee +
(unhedged quantity × exit price + fee). It falls as the entry fills and the
hedge fills. It is released at settlement, not at `HEDGE_COMPLETE`, because
YES+YES collateral is not returned early.

### Capacity from cash (not from the 7-slot ceiling)

| Spendable on the NBA shard | Concurrent entries at 192,301¢ each (worker reserve) |
| ---: | ---: |
| $5,000 | **2** (3 would need $5,769.03) |
| $10,000 | 5 |
| $13,461.07 or more | 7 (ceiling) |
| $20,000 | 7 (ceiling) |

### Inputs and assumptions

| Input | Status |
| --- | --- |
| KXNBAGAME `quadratic_with_maker_fees`, M = 1 | observed from series metadata |
| taker 7%, maker 1.75%, rounding rule | documented (FEES.md §1); account fills pending (FEES.md §5) |
| entry fills at 78 (maker) | **assumption**: `entry_order.post_only` unresolved; taker column shown |
| hedge and emergency legs are taker | **assumption** (conservative) |
| exit bound 45 | follows from the ladder cap under SELL_ORIGINAL; **emergency action unresolved** |
| cash on shard 0 vs 3 | per-market `exchange_index` (FUNDING_ROUTING.md) |
| MLB shares the collateral pool | yes, unless a subaccount isolates NBA (FUNDING_ROUTING.md §subaccount) |
