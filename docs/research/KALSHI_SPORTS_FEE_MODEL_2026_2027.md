# Kalshi NBA / NCAAB Game Fee Model — 2026–2027 Season

```text
FEE MODEL STATUS: ESTIMATED (API-VERIFIED SERIES METADATA)
OBSERVED_PRODUCTION_MODEL: UNAVAILABLE
LIVE EXECUTION CHANGED: FALSE
```

Research-only fee analysis for **`KXNBAGAME`** (NBA) and **`KXNCAAMBGAME`** (NCAAB men's game events) to support realistic maker/taker simulation at **80¢ entry / 40¢ stop** and comparative venue analysis vs **Polymarket Sports**.

**Does not wire fees into production risk or change live 80/40 logic.**

---

## Executive summary

| Finding | Detail |
| --- | --- |
| **Verified today (2026-09-03, Kalshi demo API)** | Both `KXNBAGAME` and `KXNCAAMBGAME` have `fee_type=quadratic`, `fee_multiplier=1`, **no scheduled fee changes** |
| **Production Momento path** | Post-only maker entry → **$0 entry fee**; reduce-only IOC taker exit @40 → **taker fee only on stop path** |
| **Per-contract stop-path fee (M=1)** | **1.6801¢** taker @40¢ (entry free) |
| **Per-contract full round-trip if both legs taker** | **2.8001¢** (1.12¢ @80 + 1.68¢ @40) |
| **NBA unconditional net EV @ q=26.02%** | Gross **+0.2195 R** → net **+0.1977 R** (fee drag **~10%** of gross, not ~16%) |
| **Polymarket Sports** | Makers **$0**; taker-only round trip 80→40 ≈ **2.0¢/share** (slightly higher than Kalshi stop-only path) |

**Critical correction vs prior Momento research:** `PUBLISHED_SCHEDULE_ESTIMATE` in `fee_models.py` assumed maker fees on entry (`0.0175` coef). Live series metadata shows **`quadratic`**, not `quadratic_with_maker_fees` — resting maker fills do **not** incur maker fees for these tickers **as of API verification date**.

---

## 1. Sources and verification status

| Source | URL / endpoint | Status |
| --- | --- | --- |
| Kalshi fee schedule PDF (effective **2026-07-07**) | [kalshi.com/docs/kalshi-fee-schedule.pdf](https://kalshi.com/docs/kalshi-fee-schedule.pdf) | Retrieved |
| Kalshi fee rounding | [docs.kalshi.com/getting_started/fee_rounding](https://docs.kalshi.com/getting_started/fee_rounding) | Retrieved |
| Series metadata | `GET /series/{ticker}` | **Verified** (demo API, 2026-09-03) |
| Scheduled overrides | `GET /series/fee_changes?series_ticker=…` | **Empty** for both series |
| Polymarket fees | [docs.polymarket.com/trading/fees](https://docs.polymarket.com/trading/fees) | Retrieved |
| Production elections API | `api.elections.kalshi.com` | **Blocked** from this network; demo API used |
| Observed production fills | Momento live ledger | **UNAVAILABLE** |

Re-verify before live trading: order ticket, `GET /series/KXNBAGAME`, and `GET /series/fee_changes` on production credentials.

---

## 2. Kalshi fee formulas (official)

### 2.1 Taker (immediately matched)

```text
fee = ceil_6dp(M × 0.07 × C × P × (1 − P))
```

- `P` = price in dollars (80¢ → 0.80)
- `C` = contract count (integer)
- `M` = series `fee_multiplier`
- `ceil_6dp` = round up to nearest $0.000001 ([fee rounding doc](https://docs.kalshi.com/getting_started/fee_rounding))

### 2.2 Maker (only when `fee_type` includes maker fees)

```text
maker_fee = ceil_6dp(M_maker × 0.0175 × C × P × (1 − P))
```

Maker fees apply **only** when:

1. Series `fee_type` is `quadratic_with_maker_fees` (or combo variant), **and**
2. Non-standard schedule assigns a **maker multiplier > 0**, **and**
3. The resting order ultimately executes.

Canceling an unfilled resting order: **$0**.

### 2.3 Settlement

Documented **$0** for simple yes/no event contracts.

### 2.4 FCM / balance rounding (desk note)

Non-direct (FCM-cleared) balances align to **$0.01**. Sub-cent trade fees can produce small **rounding fees** and cross-fill **rebates** via the per-order accumulator. Momento research uses model fee only; FCM rounding adds **≤ ~0.5–1¢ per order** in pathological cases — verify on first live fills.

---

## 3. Verified series metadata (2026-09-03)

| Series | Title | `fee_type` | `fee_multiplier` | Scheduled changes |
| --- | --- | --- | ---: | --- |
| **KXNBAGAME** | Pro Basketball Game | `quadratic` | 1 | none |
| **KXNCAAMBGAME** | Men's College Basketball Game | `quadratic` | 1 | none |

**Interpretation for 2026–2027 season:**

- **Resting post-only entry @80¢:** **$0 fee** when filled as maker
- **IOC taker exit @40¢:** full taker formula with M=1
- **Immediate taker entry @80¢:** taker formula (1.12¢/contract) — not production path but relevant for stress tests

**Cross-check:** `KXWNBAGAME` also `quadratic`, M=1. `KXMLBGAME` is `quadratic`, M=**0.5** (half taker coefficient) — do **not** assume MLB fee semantics apply to NBA/NCAAB.

**PDF non-standard table note:** The July 2026 PDF lists many sports series with maker multiplier 1 (e.g. `KXNFLGAME`, `KXWNBAGAME`). The live API `fee_type` field is authoritative: **`quadratic` ≠ `quadratic_with_maker_fees`**. NBA/NCAAB game series currently behave as **taker-only** regardless of PDF table rows for other tickers.

---

## 4. Per-leg fee tables (M=1, ESTIMATED)

Implementation matches frozen audit: `apps/nba-data/scripts/capture_program_v1/fee_models.py` → `quadratic_fee_e6`.

### 4.1 Kalshi — per contract

| Price | P(1−P) | Taker fee | Taker bps | Maker fee* | Maker bps* |
| ---: | ---: | ---: | ---: | ---: | ---: |
| **80¢** | 0.1600 | **1.1200¢** | 140 | 0.2800¢ | 35 |
| **83¢** | 0.1411 | 0.9878¢ | 119 | 0.2470¢ | 30 |
| **40¢** | 0.2400 | **1.6801¢** | 420 | 0.4200¢ | 105 |
| **39¢** | 0.2379 | 1.6653¢ | 427 | 0.4164¢ | 107 |
| **50¢** | 0.2500 | 1.7500¢ | 350 | 0.4375¢ | 88 |
| **60¢** | 0.2400 | 1.6801¢ | 280 | 0.4200¢ | 70 |
| **70¢** | 0.2100 | 1.4701¢ | 210 | 0.3675¢ | 53 |

\*Maker column shown for reference if Kalshi ever switches these series to `quadratic_with_maker_fees`. **Not charged today** for `KXNBAGAME` / `KXNCAAMBGAME`.

### 4.2 Kalshi — 100 contracts (matches official PDF table)

| Price | Notional | Taker fee (100C) | Per contract |
| ---: | ---: | ---: | ---: |
| 80¢ | $80 | $1.12 | 1.12¢ |
| 40¢ | $40 | $1.68 | 1.68¢ |
| 50¢ | $50 | $1.75 | 1.75¢ |

---

## 5. Exit liquidity scenarios — round-trip fees

Momento frozen unit: **R = 20¢** (80→100 win), **−2R = −40¢** (80→40 stop).

### 5.1 Per contract — all exit types

| # | Scenario | Entry fee | Exit fee | RT (stop path) | Win net | Stop net | q breakeven |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| **1** | **Production: maker entry @80 + IOC taker @40** | **0.00¢** | **1.68¢** | **1.68¢** | **+20.00¢** | **−41.68¢** | **32.40%** |
| 2 | Taker entry @80 + IOC taker @40 | 1.12¢ | 1.68¢ | 2.80¢ | +18.88¢ | −42.80¢ | 30.61% |
| 3 | Maker entry @80 + hold to $1 settlement | 0.00¢ | 0.00¢ | 0.00¢ | +20.00¢ | n/a | n/a |
| 4 | Maker entry @80 + maker exit @40 (theoretical) | 0.00¢ | 0.00¢* | 0.00¢* | +20.00¢ | −40.00¢ | 33.33% |
| 5 | Maker entry @80 + IOC taker @39 | 0.00¢ | 1.67¢ | 1.67¢ | +20.00¢ | −41.67¢ | 32.41% |
| 6 | Maker entry @83 (max band) + IOC taker @40 | 0.00¢ | 1.68¢ | 1.68¢ | +17.00¢ | −44.68¢ | 27.58% |
| 7 | **If maker fees turned ON** (stress): maker @80 + taker @40 | 0.28¢ | 1.68¢ | 1.96¢ | +19.72¢ | −41.96¢ | 31.97% |

\*Under current `quadratic` type, both legs free if filled as maker. IOC stop is taker by construction.

### 5.2 Round-trip matrix @ 80/40 (1 contract)

| Entry ↓ / Exit → | Taker @40 | Maker @40* |
| --- | ---: | ---: |
| **Maker @80 (current)** | **1.68¢ / q_BE 32.40%** | 0.00¢ / 33.33% |
| Taker @80 | 2.80¢ / 30.61% | 1.12¢ / 31.25% |

---

## 6. Desk sizing — dollar fees

Contracts = `floor(allocation / 0.80)`. Example: **12.5% of $50 = $6.25 → 7 contracts** ($5.60 notional).

| Bankroll / alloc | Contracts | Maker entry | Taker stop @40 | Stop-path total | Win-path fee | Stop-path as % notional |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| $50 / $6.25 | 7 | $0.000 | $0.1176 | **$0.1176** | $0.000 | **2.10%** |
| $100 / $12.50 | 15 | $0.000 | $0.2520 | **$0.2520** | $0.000 | 2.10% |
| $500 / $62.50 | 78 | $0.000 | $1.3104 | **$1.3104** | $0.000 | 2.10% |

If entry were taker @80 (stress): add **~0.35% of notional** entry fee on every path.

**Stress model (2× coefficients):** multiply taker leg fees by 2 → stop @40 ≈ **3.36¢/contract** → RT stop-path **3.36¢** with free maker entry.

---

## 7. EV / expectancy translation

### 7.1 Momento gross convention (frozen 80/40)

```text
EV_gross (R-units) = 1 − 3q
```

where `q = P(hit 40¢ stop)`.

| Metric | Value |
| --- | ---: |
| Gross breakeven q | **33.33%** |
| NBA unconditional q (frozen ledger) | **26.02%** |
| Gross EV @ q=26.02% | **+0.2195 R** (+4.39¢/contract) |

### 7.2 Net EV — verified Kalshi path (maker entry free, taker stop)

```text
EV_net = (1 − q) × (+20 − f_entry) + q × (−40 − f_entry − f_exit)
```

With `f_entry = 0`, `f_exit = 1.6801¢`:

| q (stop rate) | Gross EV | Net EV | Fee drag |
| ---: | ---: | ---: | ---: |
| 33.33% (gross BE) | 0.000 R | **−0.028 R** | — |
| 32.40% (net BE) | +0.018 R | 0.000 R | — |
| **26.02% (NBA uncond.)** | **+0.2195 R** | **+0.1977 R** | **0.0218 R (9.9%)** |
| 30.00% | +0.100 R | +0.080 R | 0.020 R |
| 20.00% | +0.400 R | +0.382 R | 0.018 R |

**Breakeven shift:** gross 33.33% → net **32.40%** (**−0.93 pp** on stop rate). Fees tighten edge modestly because **only ~26% of trades pay exit fees**.

### 7.3 Required edge to hold net EV constant

To maintain **+0.2195 R net** (same as gross unconditional today):

```text
q_max = (W_net − 0.2195 × 20) / (W_net + |L_net|)
      ≈ 24.0% stop rate  (vs 26.02% unconditional)
```

Interpretation: fees consume **~2 pp** of stop-rate budget vs gross research headline.

### 7.4 Prior (incorrect) maker-on-entry estimate

If Kalshi switched to `quadratic_with_maker_fees` with M_maker=1:

| Path | Net EV @ q=26.02% | Fee drag |
| --- | ---: | ---: |
| Maker entry + taker stop | +0.1835 R | 16.3% of gross |
| Taker + taker | +0.1415 R | 35.5% of gross |

Use as **stress bound**, not current baseline.

### 7.5 NCAAB (same fee structure; different q)

Fee formulas identical for `KXNCAAMBGAME`. Frozen P5-vs-P5 ledger uses different unconditional q — apply same fee algebra with sport-specific q:

```text
EV_net = EV_gross − q × f_exit_taker_40
       ≈ EV_gross − q × 1.6801¢     (maker entry, current API)
```

NCAAB gross research has **not** been re-run net-of-fees in warehouse dashboards (`fees: GROSS_UNRESOLVED`).

---

## 8. Polymarket comparative analysis

### 8.1 Fee structure (Sports category)

From [Polymarket docs](https://docs.polymarket.com/trading/fees):

```text
fee = C × feeRate × p × (1 − p)
```

| Parameter | Sports |
| --- | ---: |
| Taker fee rate | **0.05** |
| Maker fee rate | **0** |
| Maker rebate pool | 15% of taker fees |

### 8.2 Per-share fees (official 100-share table ÷ 100)

| Price | Polymarket taker | Kalshi taker (M=1) | Δ (PM − Kalshi) |
| ---: | ---: | ---: | ---: |
| 80¢ | **0.80¢** | 1.12¢ | −0.32¢ |
| 40¢ | **1.20¢** | 1.68¢ | −0.48¢ |
| 50¢ | 1.25¢ | 1.75¢ | −0.50¢ |

Kalshi taker fees are **~40% higher** than Polymarket Sports at the same price (0.07 vs 0.05 coefficient).

### 8.3 Round-trip comparison — 80→40 strategy

| Venue / path | Entry | Exit | RT stop-path | RT win-path | Notes |
| --- | ---: | ---: | ---: | ---: | --- |
| **Kalshi (current API)** maker + IOC taker | 0.00¢ | 1.68¢ | **1.68¢** | 0.00¢ | Production Momento path |
| Kalshi taker + taker | 1.12¢ | 1.68¢ | 2.80¢ | 1.12¢ | Cross-spread entry stress |
| **Polymarket** maker + taker | 0.00¢ | 1.20¢ | **1.20¢** | 0.00¢ | Makers always free |
| Polymarket taker + taker | 0.80¢ | 1.20¢ | 2.00¢ | 0.80¢ | Both legs cross |

**Stop-path fee advantage:** Polymarket **−0.48¢/contract** vs Kalshi on IOC exit only.

**At q=26.02%, expected fee drag:**

| Venue | E[fee] per contract | Net EV (from +0.2195 R gross) |
| --- | ---: | ---: |
| Kalshi (maker entry, taker stop) | 0.437¢ | +0.1977 R |
| Polymarket (maker entry, taker stop) | 0.312¢ | +0.2039 R |

Difference ≈ **0.006 R (~0.12¢/contract)** — meaningful at scale but **not** the dominant EV uncertainty vs stop-path realism (74% → 69% wick-stop gap in NBA audit).

### 8.4 Non-sports Polymarket note

Geopolitics/world events: **fee-free**. Not comparable to game-winner markets.

### 8.5 Polymarket US

Separate schedule (`docs.polymarket.us/fees`): taker θ=0.06, maker rebate −0.0125. Not analyzed here; Momento executes on Kalshi.

---

## 9. What the desk should expect (operational)

### 9.1 Production path (Kalshi, current metadata)

| Event | Fee |
| --- | --- |
| Post-only fill @80¢ | **$0** |
| Cancel unfilled maker | **$0** |
| IOC reduce-only sell @40¢ (stop) | **~1.68¢ × contracts** |
| Hold to settlement (win) | **$0** |
| Partial IOC fill @40 | Fee on **filled count only**, same formula |

### 9.2 Order-of-magnitude per trade ($6.25 alloc, 7 contracts)

| Outcome | P&L before fees | Fees | Net P&L |
| --- | ---: | ---: | ---: |
| Win to $1 | +$1.40 (+20¢×7) | $0.00 | **+$1.40** |
| Full stop @40 | −$2.80 (−40¢×7) | $0.12 | **−$2.92** |
| Expected @ q=26% | +$0.31 gross | −$0.03 | **+$0.28** |

### 9.3 Monitoring triggers

Re-run this model if:

1. `GET /series/fee_changes` returns non-empty for `KXNBAGAME` or `KXNCAAMBGAME`
2. `fee_type` changes to `quadratic_with_maker_fees`
3. First live fill shows `maker_fees_dollars > 0` on post-only entry
4. Polymarket sports taker rate changes (was 0.05 from July 2026)

---

## 10. Simulation guidance for research

### 10.1 Recommended models

| Model ID | Use | Entry | Exit @40 | Status |
| --- | --- | --- | --- | --- |
| `KALSHI_QUADRATIC_M1_V1` | **Primary** NBA/NCAAB 2026–27 | $0 (maker) | taker 1.68¢ | ESTIMATED, API-backed |
| `PUBLISHED_SCHEDULE_ESTIMATE` | Stress (maker fees ON) | 0.28¢ | taker 1.68¢ | ESTIMATED |
| `TAKER_TAKER_STRESS` | Worst-case cross both ways | 1.12¢ | 1.68¢ | ESTIMATED |
| `POLYMARKET_SPORTS_TAKER` | Cross-venue | 0 / 0.80¢ | 1.20¢ | From PM docs |
| `ZERO_FEE_MODEL` | Upper bound / legacy research | 0 | 0 | SIMULATED |
| `OBSERVED_PRODUCTION_MODEL` | Live validation | — | — | UNAVAILABLE |

### 10.2 Python reference (matches frozen audit)

```python
import math

TAKER_COEF = 0.07
MAKER_COEF = 0.0175  # only if fee_type includes maker fees

def ceil_e6(x: float) -> int:
    return int(math.ceil(x * 1_000_000.0 - 1e-12))

def kalshi_taker_fee_cents(contracts: int, price_cents: int, M: float = 1.0) -> float:
    p = price_cents / 100.0
    return ceil_e6(M * TAKER_COEF * contracts * p * (1.0 - p)) / 10_000.0

def ev_net_r(q: float, f_entry_cents: float, f_exit_cents: float) -> float:
    """R=20c win, -2R stop; fees in cents."""
    win = 20.0 - f_entry_cents
    loss = -40.0 - f_entry_cents - f_exit_cents
    ev_cents = (1.0 - q) * win + q * loss
    return ev_cents / 20.0
```

**Primary call:** `ev_net_r(q=0.2602, f_entry_cents=0.0, f_exit_cents=1.6801)` → **+0.1977 R**.

---

## 11. Open items

| Item | Status |
| --- | --- |
| Production API confirmation (elections host) | Blocked this session |
| Observed fee on first live NBA/NCAAB fill | UNAVAILABLE |
| FCM $0.01 rounding on partial IOC stops | Not modeled |
| NCAAB net-of-fees scoreboard refresh | Not run |
| Wire `KALSHI_QUADRATIC_M1_V1` into `fee_models.py` | Not implemented (research doc only) |

---

## 12. References in repo

- `apps/nba-data/scripts/capture_program_v1/fee_models.py` — pluggable fee interface
- `apps/nba-data/scripts/nba_80_40_execution_audit.py` — frozen `quadratic_fee_e6`
- `docs/research/nba/capture-program-v1/FEE_MODEL.md` — prior UNRESOLVED status
- `Backtesting Suite/.../QUESTION_B_SCOREBOARD.md` — maker-off net **+0.1977 R** (consistent with this doc)

---

*Generated 2026-09-03. Re-verify series metadata before 2026–27 season live deployment.*
