# FIRST80_OPPONENT_40_HEDGE_V1

Research only. **LIVE EXECUTION CHANGED: FALSE.**

```text
Fill favorite YES at 80
     │
     ▼
Rest maker bid on opponent YES at 40
     │
     ├── fills → locked −20¢   (80 + 40 − 100)
     └── never fills
            ├── settlement YES → +20¢
            └── settlement NO  → −80¢
```

This is not a 40¢ stop on the held contract. It is a complementary hedge.
Candle path ≠ fill. L2 / queue UNAVAILABLE. Fees UNRESOLVED.

Proxy (same tradable-bar rule as the 80/40 audit):

- **Close:** first later `opponent yes_bid_close ≥ 40¢`
- **Wick:** first later `opponent yes_bid_high ≥ 40¢`

Universe: frozen FIRST-80 entries. NBA 1,230. NCAAB 4,099. Opponent
ticker present on every game (`missing_opponent = 0`).

## Close-path results

| | NCAAB | NBA |
|---|---:|---:|
| n | 4,099 | 1,230 |
| Hedge lock (−20¢) | 1,546 (37.72%) | 456 (37.07%) |
| No hedge, win (+20¢) | 2,552 (62.26%) | 774 (62.93%) |
| No hedge, lose (−80¢) | 1 | 0 |
| **Hedge EV / contract** | **+4.89¢** | **+5.17¢** |
| Baseline 80/40 EV / contract | +3.90¢ | +4.39¢ |
| Hedge then settled YES | 842 / 1,546 (54.5%) | 245 / 456 (53.7%) |
| Hedge ∩ favorite close-40 | 1,096 | 320 |
| Hedge only (no favorite-40) | 450 | 136 |
| Favorite-40 only | 3 | 0 |

Held YES bid in the opponent-40 minute (complement check):

| | NCAAB | NBA |
|---|---:|---:|
| Mean held bid | 52.3¢ | 54.3¢ |
| Median | 55¢ | 56¢ |
| p10–p90 | 44–59 | 46–59 |
| Mean held + opp bid | 97.8¢ | 98.5¢ |

Opponent-40 fires when the favorite is still ~52–56¢, not 40¢.

## Wick-path (worse)

Wick locks more often and kills more winners.

| | NCAAB | NBA |
|---|---:|---:|
| Locks | 1,662 (40.55%) | 496 (40.33%) |
| EV / contract | **+3.76¢** | **+3.87¢** |
| vs 80/40 baseline | worse | worse |

Do not use wick as the working rule.

## Why close-path EV is higher per contract

NCAAB identity (cents, 4,099 trades):

```text
hedge    = 2,552×(+20) + 1,546×(−20) + 1×(−80) = +20,040   → +4.89¢
80/40    = 2,998×(+20) + 1,099×(−40) + 2×(0)   = +16,000   → +3.90¢
```

The +0.99¢ gap is:

| Effect | n | Δ vs 80/40 | $¢ |
|---|---:|---|---:|
| Overlap stops: −40 → −20 | 1,096 | +20 each | +21,920 |
| Extra hedges on winners: +20 → −20 | 449 | −40 each | −17,960 |
| 3 favorite-40 that never printed opponent-40, settled YES | 3 | −40 → +20 | +180 |
| Leak that hedged | 1 | 0 → −20 | −20 |
| Leak with no hedge | 1 | 0 → −80 | −80 |
| **Net** | | | **+4,040** |

Almost every eventual loser printed opponent 40 (NCAAB miss 1/4,099; NBA 0).
The −80 tail is rare in this candle proxy. The cost is **842 NCAAB / 245 NBA**
hedges that later settled YES — including 450 / 136 that never even printed
favorite 40.

## Capital (this can reverse the ranking)

Per-contract EV is not desk EV.

If both legs must be reserved up front on a $6.25 game budget:

```text
stop book   7 × 80¢  = $5.60   →  7 × 3.90¢ = +27.3¢
hedge book  5 × 120¢ = $6.00   →  5 × 4.89¢ = +24.4¢
```

On **reserved** capital, NCAAB 80/40 still makes more money per game.
NBA: 7 × 4.39¢ = +30.7¢ vs 5 × 5.17¢ = +25.9¢. Same ranking.

If the 40¢ bid is only funded when it fills, 7-contract sizing can stay
and hedge EV stays +4.89¢ / +5.17¢ per contract — but fade days need
spare cash, and Risk today does not book a second market.

Fees on two legs are not in any of these numbers.

## What this does not prove

- A resting 40 bid actually fills. This is a bid-close proxy.
- Post-only 40 rests when opponent ask is already ≤ 40 (would cross).
- Live FIRST01 can submit the opponent order (it cannot; opponent is ignored).
- L2 / queue / partials.

## Non-goals

- Do not change live FIRST01, Risk, or Execution.
- Do not arm NBA/NCAAB trading from this table.
- Do not treat −20 as a guaranteed lock.

Code: `apps/ncaab-data/scripts/first80_opponent_40_hedge_v1.py`  
Artifacts: `.../warehouse/derived/{ncaab,nba}/first80_opponent_40_hedge_v1/`
