# Desk loss review — 2026-08-25 (America/Los_Angeles)

**Source:** production `momento-live` on `i-0f0849d5829476c31`  
**State files:** `/var/lib/momento/state/live-runtime.json`, `mlb-strategy.json`, `wnba-strategy.json`  
**Bankroll snapshot:** $50.00 (5 000¢), week of 2026-08-24  
**Day window:** 2026-08-25 00:00–24:00 PT (fills timed in that window)

---

## Executive summary

| Metric | Value |
|--------|------:|
| Realized P&L (ledger) | **−$31.77** (−3 177¢) |
| % of $50 bankroll | **−63.5%** |
| Filled trades | **9** (7 MLB, 2 WNBA) |
| Wins | **0** |
| Stop liquidations | **4** (−$11.52) |
| Settlement losses | **5** (−$20.25) |
| Fees recorded in state | **$0.00** (fees not modeled / not present on fills) |

Every filled trade today was **YES** after the standard **80 → 81** confirmation, maker entry in **80–83**. Losses came from two paths:

1. **50% VWAP stop** — favorite faded after entry; IOC liquidation sold into a falling book.
2. **Hold through GAME_LOCK (≥89) then settle against** — market looked “locked” as favorite, then the position settled for essentially full premium loss.

We do **not** have inning-level sports data in the trading ledger. “Where in the game” below is inferred from **Kalshi YES-bid path timing** (entry → 89 lock → stop/settlement), which is what the algo actually sees.

**Caveat — settlement proceeds:** five settled losers show `settlement_proceeds = $1.00` (100¢) against multi-contract entries. For a full YES loss, expected proceeds are **$0**. If the true Kalshi settlement was $0, those five losses are **~$1 each worse** (~−$35.77 / −71.5%). Figures below use the **on-disk ledger**.

---

## Loss mix

```
Stop liquidations   ███░░░░░░  $11.52   36%
Settlement losses   ██████░░░  $20.25   64%
```

---

## Trade-by-trade (chronological by entry)

### 1. TEX @ CWS — YES **CWS** (MLB) — settlement loss −$4.81

| | |
|--|--|
| Ticker | `KXMLBGAME-26AUG251940TEXCWS-CWS` |
| Entry | 17:01:07 PT · 7 @ **83¢** · premium $5.81 |
| First 80 | 16:59:31 PT @ 80¢ |
| GAME_LOCK (≥89) | **17:08:16 PT @ 89¢** (~7 min after entry) |
| Exit | Held to **settlement** · proceeds $1.00 |
| Realized | **−$4.81** |

**Where it went wrong:** Entered early evening; CWS YES bid ran to **89 within ~7 minutes** (looked locked). Never hit the 50% stop. Settled against the position — full favorite collapse after lock, or wrong side relative to final result. Largest single settlement loss today.

---

### 2. CHI @ CONN — YES **CONN** (WNBA) — settlement loss −$3.05

| | |
|--|--|
| Ticker | `KXWNBAGAME-26AUG25CHICONN-CONN` |
| Entry | 17:07:10 PT · 5 @ **81¢** · premium $4.05 |
| First 80 | 17:06:32 PT @ 80¢ |
| GAME_LOCK | **17:19:22 PT @ 89¢** (~12 min after entry) |
| Exit | Settlement · proceeds $1.00 |
| Realized | **−$3.05** |

**Where it went wrong:** Same pattern as MLB: quick run to 89, no stop, settlement loss. WNBA book used 12.5%→~$4.16 budget (5 contracts).

---

### 3. PDX @ DAL — YES **DAL** (WNBA) — settlement loss −$3.05

| | |
|--|--|
| Ticker | `KXWNBAGAME-26AUG25PDXDAL-DAL` |
| Entry | 17:27:00 PT · 5 @ **81¢** · premium $4.05 |
| First 80 | 17:03:22 PT @ 80¢ (earlier watch) |
| GAME_LOCK | **17:37:37 PT @ 89¢** (~10 min after entry) |
| Exit | Settlement · proceeds $1.00 |
| Realized | **−$3.05** |

**Where it went wrong:** Locked favorite after entry; held through lock; settled as a loser.

---

### 4. BOS @ MIA — YES **BOS** (MLB) — stop −$1.26

| | |
|--|--|
| Ticker | `KXMLBGAME-26AUG251840BOSMIA-BOS` |
| Entry | 18:37:22 PT · 7 @ **81¢** · premium $5.67 |
| First 80 | 18:37:21 PT @ 80¢ (same minute) |
| Stop | **18:41:15 PT** · sold 7 @ **63¢** · proceeds $4.41 |
| Hold | **~3.9 minutes** |
| GAME_LOCK (after stop) | 18:54:55 PT @ **93¢** |
| Realized | **−$1.26** |

**Where it went wrong:** **Immediate post-entry fade.** Stopped out within 4 minutes at 63¢. Minutes later the same market locked at 93¢ — i.e. the algo sold the dip that then recovered into a lock. Smallest loss of the day, but a classic **whipsaw**: stop before lock, then lock without us.

Approx 50% threshold on 81¢ VWAP ≈ **40¢**; fill at 63¢ means the trigger print was ≤ threshold and IOC lifted remaining liquidity above that.

---

### 5. LAD @ ATL — YES **ATL** (MLB) — stop −$1.93

| | |
|--|--|
| Ticker | `KXMLBGAME-26AUG251915LADATL-ATL` |
| Entry | 18:47:39 PT · 7 @ **81¢** · premium $5.67 |
| First 80 | 18:47:38 PT @ 80¢ |
| Stop | **18:51:50–53 PT** · 5 @ 54¢ + 2 @ 52¢ · proceeds $3.74 |
| Hold | **~4.2 minutes** |
| GAME_LOCK (after stop) | 18:58:43 PT @ 89¢ |
| Realized | **−$1.93** |

**Where it went wrong:** Same **early fade / stop / then lock** pattern as BOS. Stopped ~4 minutes in; market later printed 89 without the desk still long.

---

### 6. CLE @ LAA — YES **LAA** (MLB) — stop −$2.87

| | |
|--|--|
| Ticker | `KXMLBGAME-26AUG252138CLELAA-LAA` |
| Entry | 19:17:28 PT · 7 @ **82¢** · premium $5.74 |
| First 80 | 19:14:16 PT @ 80¢ |
| GAME_LOCK | **19:22:45 PT @ 89¢** (~5 min after entry) |
| Stop | **20:31:44 PT** · 7 @ **41¢** · proceeds $2.87 |
| Hold | **~74 minutes** |
| Realized | **−$2.87** |

**Where it went wrong:** **Post-lock collapse.** Favorited and locked within minutes of entry, then ~70 minutes later YES bid fell through the **~41¢** 50% band and IOC exited at 41¢. This is the “locked favorite reverses” path the stop is meant to catch — still a full half-premium loss.

---

### 7. CHC @ AZ — YES **CHC** (MLB) — stop −$5.46 **(worst trade)**

| | |
|--|--|
| Ticker | `KXMLBGAME-26AUG252140CHCAZ-CHC` |
| Entry | 19:25:30 PT · 7 @ **81¢** · premium $5.67 |
| First 80 | 19:25:18 PT @ 80¢ |
| GAME_LOCK | **19:50:50 PT @ 89¢** (~25 min after entry) |
| Stop | **21:15:59 PT** · 7 @ **3¢** · proceeds $0.21 |
| Hold | **~110 minutes** |
| Realized | **−$5.46** |

**Where it went wrong:** Locked as favorite, then a **late blow-up**. Stop fired into an almost empty/toxic book — fill at **3¢**. Largest single loss of the day. Desk takeaway: after 89 lock, a late reverse can gap through the 50% stop with near-zero recovery on IOC.

---

### 8. PHI @ SEA — YES **SEA** (MLB) — settlement loss −$4.67

| | |
|--|--|
| Ticker | `KXMLBGAME-26AUG252140PHISEA-SEA` |
| Entry | 20:32:23 PT · 7 @ **81¢** · premium $5.67 |
| First 80 | 20:27:57 PT @ 80¢ |
| GAME_LOCK | **20:35:40 PT @ 90¢** (~3 min after entry) |
| Exit | Settlement · proceeds $1.00 |
| Realized | **−$4.67** |

**Where it went wrong:** Very fast lock after entry; no stop; settled as a loser. Late West-coast slate.

---

### 9. PIT @ SD — YES **PIT** (MLB) — settlement loss −$4.67

| | |
|--|--|
| Ticker | `KXMLBGAME-26AUG252140PITSD-PIT` |
| Entry | 20:49:37 PT · 7 @ **81¢** · premium $5.67 |
| First 80 | 20:48:53 PT @ 80¢ |
| GAME_LOCK | **20:56:21 PT @ 89¢** (~7 min after entry) |
| Exit | Settlement · proceeds $1.00 |
| Realized | **−$4.67** |

**Where it went wrong:** Same as SEA — quick 89 lock, hold to settlement, lose.

---

## Patterns for desk review

### A. “Lock then lose” (5 trades, −$20.25)

Timeline shape:

```
80 → 81 entry (80–83) → YES ≥89 GAME_LOCK within ~3–12 min → hold → settle loss
```

Games: **CWS, CONN, DAL, SEA, PIT**.

Implication: GAME_LOCK correctly blocks *new* entries but **does not flatten**. Tonight, several locked favorites still lost at settlement. The 50% stop never fired on these (bid never sustained ≤ ~½ entry before settle).

### B. “Stop before lock, then lock without us” (2 trades, −$3.19)

Timeline shape:

```
entry → fade in ~4 min → 50% stop fill → later YES ≥89 lock
```

Games: **BOS, ATL**.

Implication: early noise / swing stops; market later confirmed the original favorite. Whipsaw cost was small vs settlement losses, but directionally painful.

### C. “Lock then reverse into stop” (2 trades, −$8.33)

Timeline shape:

```
entry → ≥89 lock → long hold → late collapse → IOC stop (41¢ / 3¢)
```

Games: **LAA, CHC**.

Implication: stop worked as designed after reverse; **CHC @ 3¢** shows gap risk on reduce-only IOC when the book is gone.

---

## Timing heatmap (entry hour PT)

| PT hour | Trades | Realized |
|---------|-------:|---------:|
| 17:00 | 3 (1 MLB + 2 WNBA) | −$10.91 |
| 18:00 | 2 MLB stops | −$3.19 |
| 19:00 | 2 MLB (1 stop, 1 later stop) | −$8.33 |
| 20:00 | 2 MLB settlements | −$9.34 |

Evening West-coast slate (19:00–21:00 PT entries / locks) drove most of the dollar loss.

---

## Strategy rules that fired (unchanged)

| Rule | Behavior tonight |
|------|------------------|
| 80 → 81 → maker 80–83 | All nine entries |
| Max 83 | Entries at 81–83 |
| GAME_LOCK ≥89 | Observed on all nine games (before or after stop) |
| 50% entry VWAP stop | Fired on 4; did not fire on 5 settlers |
| One position / game budget | MLB ~$6.25 / WNBA ~$4.16 |

No evidence in this ledger of duplicate game entries or live-gate bypass.

---

## Open questions for next desk sync

1. **Settlement proceeds = $1.00** on multi-contract losers — reconcile vs Kalshi portfolio history (expect $0 on full NO).
2. Should **GAME_LOCK** change exit policy (e.g. tighter stop, partial harvest) once ≥89, given five lock-then-settle losses?
3. **CHC 3¢ IOC** — acceptable gap outcome, or need liquidity / max-slippage guard on stop?
4. Early **4-minute stops** that later locked (BOS/ATL) — noise vs structural; any debounce only if we invent new behavior deliberately (do not change live without review).

---

## Appendix — ID map

| Position ID | Ticker | Outcome | P&L |
|------------:|--------|---------|----:|
| 1787564398221931119 | TEXCWS-CWS | settlement | −$4.81 |
| 1787582621909588218 | CHICONN-CONN | settlement | −$3.05 |
| 1787582621909744235 | PDXDAL-DAL | settlement | −$3.05 |
| 1787564398221938157 | BOSMIA-BOS | stop @ 63¢ | −$1.26 |
| 1787564398221932302 | LADATL-ATL | stop @ 54/52¢ | −$1.93 |
| 1787564398221927996 | CLELAA-LAA | stop @ 41¢ | −$2.87 |
| 1787564398221926919 | CHCAZ-CHC | stop @ 3¢ | −$5.46 |
| 1787564398221929837 | PHISEA-SEA | settlement | −$4.67 |
| 1787564398221928604 | PITSD-PIT | settlement | −$4.67 |
| | | **Total** | **−$31.77** |

*Generated for desk review from production state as of pull ~2026-08-26 05:42 UTC. Not a backtest. Production orders were not submitted by this review.*
