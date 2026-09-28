# A1 Hybrid Hedge Optimization — REPORT

Research only. **LIVE EXECUTION CHANGED: FALSE.**  
Does not change FIRST01, Risk, Execution, or live MLB 80/81/83/89.

```text
UNIVERSE_VERSION   A1_UNIVERSE_V1
DATASET_VERSION    FIRST80_V3OPP_V4LEDGER_2025_2026
CODE_VERSION       see universe_manifest.json
CONFIG_HASH        d7d2e9e55d9a426a
NCAAB working      P5 vs P5 (721) — warehouse 4,099 not used
Fees               GROSS / UNRESOLVED
Actual maker fill  UNOBSERVED
Timing             STRICT NEXT-BAR (V3 t > first_80_timestamp)
```

Recon: `docs/research/A1_HYBRID_HEDGE_RECONNAISSANCE.md`  
Engine: `apps/ncaab-data/scripts/a1_hybrid_hedge/`  
Dashboard: `frontend/a1-hybrid-hedge/` (reads experiment JSON only)

---

## Executive Summary

**Does realistic A1 hedging improve FIRST80?**

**No — not as a production or live rule.**

Under the headline book (conservative causal in-band + 80→40 fallback):

1. **H = 40 exact loses to 80→40 on the full sample**  
   NBA −0.065¢/trade · NCAAB P5 −0.222¢/trade.
2. **Most of V1’s theoretical edge is gap fiction.**  
   NBA: 456 closes ≥40, only 92 land *exactly* at 40, **364 jump through**.  
   Booking those 364 at 40¢ creates +0.85¢/trade of fake EV vs the causal book.
3. **VAL-selected H\* (NBA 34 / P5 29) beats 80→40 on VALIDATION and fails OOS.**  
   Verdict both sports: `RESULT_INCONCLUSIVE`.
4. **Wider bands raise modeled fill rates and worsen EV** because the fill is booked at the *observed* close, not normalized to 40.
5. **Lookahead persist k=3 at H=40** prints NBA +0.23¢ vs 80→40 on FULL. That uses bars *after* the first ≥40 close. It is **not** a T0 rule (see V5: wait-then-pay loses).

Classification: **RESULT INCONCLUSIVE** on the VAL→OOS lock, and **NO ECONOMIC CASE** for the pre-registered H=40 exact hedge.

Keep maker-80 + 80→40 as the research-supported causal trade.

---

## Data

| Universe | n | Dates | TRAIN | VAL | OOS |
|---|---:|---|---:|---:|---:|
| NBA FIRST-80 2025–26 | 1,230 | 2025-10-10 → 2026-06-13 | 504 | 483 | 243 |
| NCAAB P5 vs P5 | 721 | 2025-11-03 → 2026-04-04 | 137 | 555 | 29 |

P5 OOS n=29 is too small for a stable lock. Warehouse NCAAB 4,099 is historical V1 only.

Price fields: 1-minute `yes_bid_*` / `yes_ask_*` / last-trade `price_*` (e4). No L2.  
A1/A2: same `event_id`, opposing YES tickers. Not inferred from price.

---

## Methodology

```text
ENTER A1 @ nominal 80 (FIRST-80 definition unchanged)
        │
        ▼
A2 quotes with t > entry bar only
        │
        ▼
First close ≥ band_lo
        │
        ├─ close ∈ [lo, hi] and not jump_10c → modeled hedge @ OBSERVED close
        ├─ close > hi or jump_10c             → GAP / miss
        └─ never ≥ lo                         → miss
        │
        ├─ HEDGE MODELED → Π = 20 − H_obs − C    (C = 0)
        └─ MISS         → fallback
```

**Books**

| Book | Fill rule | Label |
|---|---|---|
| Original | 80→40 Model A | reproduced baseline |
| Theoretical replace | any close≥H fills **at H**, else hold | NON-EXECUTION-AUDITED |
| Theoretical hybrid | any close≥H fills **at H**, else 80→40 | NON-EXECUTION-AUDITED |
| Conservative causal | in-band observed close only | headline |
| Lookahead persist k | in-band **and** 1+persist ≥ k | LOOKAHEAD |
| Probabilistic q | q × hedge + (1−q) × fallback on in-band | SCENARIO |
| Partial f | f × hedge + (1−f) × fallback | SCENARIO |

Fallback A = Model A −40. Fallback C/D refuse the −40 A1 fill (hold). Fallback B equals A until an A1 stop-candle rescan exists.

Exact band at H means the first close ≥ H must **equal H**. A path 39→41 is a gap for exact-40. That is intentional.

---

## Experiment A — baseline reproduction

| Sport | n | Hold | 80→40 | V1 H=40 | Gate |
|---|---:|---:|---:|---:|---|
| NBA | 1,230 | +2.8455 | +4.3902 | +5.1707 | **PASS** |
| NCAAB P5 | 721 | +3.3564 | +4.3551 | +4.3551 | **PASS** |

Identities match the frozen V4 ledger. Universe was not silently changed.

---

## Experiment B — theoretical surface (upper bound)

Any later A2 close ≥ H is booked at **exactly H**. This includes 23→75.

At H=40 this **is** V1: NBA +5.1707 (+0.78 vs 80→40). NCAAB P5 ties 80→40 at +4.3551.

Do not use this as executable EV.

---

## Experiment C — conservative causal (headline)

H=40 exact, FULL:

| Sport | Close≥40 | In-band @40 | Gaps | Causal EV | vs 80→40 |
|---|---:|---:|---:|---:|---:|
| NBA | 456 | 92 | 364 | +4.3252 | **−0.065** |
| NCAAB P5 | 282 | 49 | 233 | +4.1331 | **−0.222** |

The hedge that “should” be the deterioration hedge **loses** once gaps are missed and the fill is not assumed at 40.

---

## Experiment D — moderate / probabilistic

q is a **scenario**, not an observed fill rate. On in-band closes only; gaps stay at q=0.

At H=40 exact FULL, q=1 is the causal book (already below 80→40). q<1 interpolates toward 80→40. There is no q that turns exact-40 into a robust winner without also booking gaps.

---

## Experiment E — partial fill

f ∈ {0, 0.25, 0.50, 0.75, 1.00} on in-band trades. Depth is UNOBSERVED. Partial completion moves EV from 80→40 toward the causal hedge. It does not rescue H=40 exact.

---

## Experiment F — gap stress

NBA H=40: fictional threshold EV − causal EV = **+0.846¢/trade**.  
That is the V1 premium. It is the 364 jump-throughs booked at 40.

NCAAB P5: the same gap premium is **+0.222¢/trade**, which is the entire difference between V1 and the causal book (V1 already tied 80→40).

```text
23 → 75   = GAP / NO OBSERVABLE FILL EVIDENCE
23 → 39 → 41  (exact 40) = still a miss if the first close ≥40 is 41
23 → 40 → 48  = in-band candidate @ 40 (still not a confirmed maker fill)
```

---

## Experiment G — train / VAL / OOS

Selection on VALIDATION only, conservative causal, exact band, H=10…60.

| Sport | Locked H | VAL EV | VAL vs 80→40 | OOS EV | OOS vs 80→40 |
|---|---:|---:|---:|---:|---:|
| NBA | 34 | +5.7267 | +0.385 | +4.9712 | **−0.214** |
| NCAAB P5 | 29 | +4.8378 | +0.730 | +7.7241 | **−1.931** |

P5 OOS is 29 trades; the −1.93¢ increment is noise. NBA OOS n=243 is usable and still fails.

**Pareto note:** every conservative book still realizes −40 on fallback stops, so p05 = −40 for all H. The “frontier” collapses to max VAL EV. Isolated H=34 / H=29 are **not** plateaus in the economic sense (NBA width 4 over 29–43 is sparse). Do not implement them.

Bootstrap (NBA locked H=34 FULL): IID 95% CI [3.04, 5.83] includes the 80→40 mean 4.39. Sampling uncertainty alone does not separate the hedge from the original.

---

## Named bands (FULL, persist k=3 informational)

| Band | NBA causal vs 80→40 | P5 causal vs 80→40 |
|---|---:|---:|
| 39–41 | −0.336 | −1.033 |
| 38–42 | −0.199 | −1.154 |
| 37–42 | −0.194 | −1.223 |
| 35–45 | −0.759 | −1.660 |
| 17–22 | −1.137 | −1.004 |
| 27–32 | −0.653 | +0.017 |

Cheaper / wider occupancy books **worse** average EV: you fill more often at worse (or earlier) locked P&L, and you still miss violent gaps.

---

## Risk

| Book (NBA FULL) | Mean | p05 | Worst | Max DD | Catastrophic (≤−60) |
|---|---:|---:|---:|---:|---:|
| Hold | +2.85 | −80 | −80 | −660 | 17.2% |
| 80→40 | +4.39 | −40 | −40 | −380 | 0 |
| V1 @40 (fake) | +5.17 | −20 | −20 | −200 | 0 |
| Causal @40 | +4.33 | −40 | −40 | −340 | 0 |

V1’s prettier tail is the fictional −20 lock on jump-throughs. Causal hedging does **not** improve p05 vs 80→40 (still −40).

---

## Recommendation

```text
Configuration tried:     H = 40 exact, and VAL H* = 34 / 29
Execution:               conservative causal in-band
Assumed fill:            observed close if it lands in band; else miss
Fallback:                legacy 80→40 Model A
Fees:                    0 (unresolved)
OOS:                     fails both sports

Class:                   RESULT INCONCLUSIVE (VAL lock)
                         NO ECONOMIC CASE (pre-registered H=40)

Do not implement A2 hedging in FIRST01 from this layer.
Do not rest a 40 post-only bid at T0 (through-market vs ~21 ask).
Do not start the deterioration-trigger / full DRE until A1 is reopened
with L2 or an authorized fill experiment.
```

---

## Limitations

- No historical L2; no confirmed maker fills.
- One-minute bars cannot prove a print inside a gap.
- Persist-k is lookahead.
- Fallback B has no extra A1 occupancy data.
- Fees, slippage, depth = unresolved.
- P5 OOS is 29 trades.
- Live Risk still allows one market per game.
- Multiple testing across H=10…60 is real; VAL H\* is not a discovery.

---

## Does realistic A1 hedging improve the FIRST80 strategy?

**No.** The theoretical hedge advantage is mostly impossible or weakly supported fills. Once those are refused, H=40 does not beat 80→40, and the VAL-picked hedge levels do not survive OOS.

That is the intended honest result of this layer.

Artifacts: `docs/research/A1_HYBRID_HEDGE/`  
Audit: `docs/research/A1_HYBRID_HEDGE/trade_audit.parquet`
