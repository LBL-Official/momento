# Roller V4 Greeks

**A lossless empirical measurement architecture for state-conditional probability-market dynamics.**

This is not a claim about Jump Trading, or any other firm’s proprietary stack. Greeks are the first taxonomy imposed on those measurements — not the system itself.

```text
ROLLER V4
MEASUREMENT BEFORE INTERPRETATION

NO PROXY WITHOUT IDENTITY
NO SIGNAL WITHOUT REPLICATION

A GREEK IS NOT A NAME FOR A STATISTIC.
IT IS AN IDENTITY WITH A REQUIRED INFORMATION REGIME.
```

```text
RESEARCH ONLY
LIVE EXECUTION = FALSE

MEASUREMENT ≠ EDGE
SENSITIVITY ≠ EDGE
UNUSUAL ≠ PREDICTIVE
PREDICTIVE ≠ CAUSAL
CAUSAL ≠ ECONOMICALLY EXPLOITABLE
MODEL DISAGREEMENT ≠ MARKET INEFFICIENCY
MARKET INEFFICIENCY ≠ EXECUTABLE PROFIT
CANDLE PATH ≠ EXECUTABLE PATH
Rᵐ ≠ CAUSAL RESIDUAL
Rᵐ ≠ MARKET ERROR
```

---

## Direct answer

**No. V4 does not implement the full Greek desk as measurements.**

**Yes. Everything V4 *does* measure is lossless relative to its approved definition. Everything else is constitutionally null, not a proxy.**

V4A / V4B / V4C are the operational names. Intellectually the stack is:

```text
EPISTEMIC LAYER       What could have been known?
        ↓
FUNDAMENTAL LAYER     What historically happened from states
                      that were knowable at that time?
        ↓
MEASUREMENT LAYER     What can the current information regime
                      actually observe?
        ↓
IDENTITY LAYER        Name × definition × regime × resolution
                      × class × conditioning set
        ↓
RESIDUAL LAYER        How unusual vs comparable observations?
        ↓
RESEARCH LAYER        Does the relationship structurally replicate?
        ↓
ECONOMIC LAYER        NOT YET AUTHORIZED
```

| Operational | Intellectual layer | Status |
|-------------|--------------------|--------|
| **V4A `O_t` / `I(t)`** | Epistemic | **Implemented.** Half-open PIT. |
| **V4A `F_t`** | Fundamental | **Implemented.** Prior-only `wins / n`. |
| **V4B** | Measurement + residual | **Implemented.** Thirteen families + `E[M \| core_v1]`. Not “the Greek layer.” |
| **V4C** | Identity / **measurement constitution** | **Implemented.** Lossless overlay. Zero new numbers. |
| — | Research / economic | **Not authorized.** |

The most important equation is not `ΔK = βΔF + ε` and not `B = K − F`. It is:

```text
MeasurementIdentity =
    measurement_name
  + measurement_class
  + definition_version
  + information_regime
  + resolution
  + conditioning_schema
```

The Jump-style memo describes three generations at once: basketball-state Greeks, probability-path Greeks, and market-microstructure Greeks. ROLLER V4 implements **Generation 1 measurement** (candle path + `F_t`) and **the Generation 1–3 constitution**. It does **not** pretend Generation 2/3 objects exist.

V4C’s job is not “here are all the Greeks we hope to calculate.” It is: **here are the conditions under which the system may claim that an object exists.** See [V4C_MEASUREMENT_CONSTITUTION.md](V4C_MEASUREMENT_CONSTITUTION.md).

### Measurement classes (machine-readable)

V4B field names stay frozen. Class is a V4C identity field so a discrete analogue cannot silently become a surface.

| Class | Meaning | V4 examples |
|-------|---------|-------------|
| `DIRECT_DIFFERENCE` | Observed / independently computed difference | `market_delta_1m`, `fundamental_delta`, `response_delta`, `basis_delta`, `absolute_return` |
| `EMPIRICAL_DISCRETE_SENSITIVITY` | Discrete analogue, not ∂ | `score_delta`, `theta_observed`, `discrete_gamma` (`identity_kind=temporal_second_difference`) |
| `PATH_DESCRIPTOR` | Path shape, not a sensitivity | `candle_range`, `directional_efficiency`, **`market_absolute_variation`** |
| `CONDITIONAL_SURFACE` | True conditional object | reserved: `response_beta`, `σ_K`, `possession_delta`, score-surface Γ |
| `MICROSTRUCTURE` | Book / flow | reserved: `microprice`, OBI, λ, Ψ |

```text
DIRECT DIFFERENCE
        ≠
EMPIRICAL DISCRETE SENSITIVITY
        ≠
PATH DESCRIPTOR
        ≠
CONDITIONAL SURFACE
        ≠
MICROSTRUCTURE MEASUREMENT
```

The V4B public key `realized_market_volatility` is **too generous**. It is not renamed (V4B is frozen). Its constitutional identity is:

```text
NAME (frozen key) → realized_market_volatility
CANONICAL         → market_absolute_variation
WHAT IT MEASURES  → Σ|ΔK|
INFORMAL FAMILY   → VEGA_ANALOGUE
WHAT IT IS NOT    → σ_K / implied volatility / Vega
```

```text
IMPLEMENTED          = an approved definition produced a number
PARTIAL              = a number exists, but the broader Greek name overclaims
NOT_YET_IMPLEMENTED  = may become constructible; no proxy
NOT_CONSTRUCTIBLE    = current information regime cannot produce the object
```

Lossless means:

```text
V4C numerator   == V4B numerator
V4C denominator == V4B denominator
```

Not float equality. V4C copies the V4B rational and attaches identity. It does not recalculate Δ, rediscover candles, or reconstruct `F`.

```python
db.greeks(id)                            # V4B payload
db.greeks(id, schema_version="4.0.0-B")  # same
db.greeks(id, schema_version="4.0.0-C")  # measurements + catalog
```

---

## 1. Executive summary — what the desk would want vs what V4 is

A binary NBA contract has payoff in `{0, 1}`. Price is approximately `K_t ≈ Pr(team wins | I_t)` only as a *market object*, not as truth.

The research problem is:

> How does market-implied probability respond to basketball state, clock, volatility, liquidity, information, and (eventually) the book?

V4 accepts that problem and then **refuses to invent the data required to finish it**.

```text
CURRENT DATA
────────────
1-minute OHLC candles
No historical L2
No signed flow
No queue state
No second snapshot
Possession events exist (NBA V2 REAL)
Possession-conditioned F is NOT validated

THEREFORE

Market microstructure Greeks = NOT_CONSTRUCTIBLE
Possession / event / surface Greeks = NOT_YET_IMPLEMENTED
Candle Greeks                    = IMPLEMENTED (V4B)
Architecture catalog             = IMPLEMENTED (V4C)
```

The memo is right that the first generation must not reconstruct:

```text
true order-flow
true queue position
true order-book imbalance
true fill probability
```

V4 goes one step further than “label them proxies.” **It does not emit proxies.** A catalog row with `value=None` means *intentionally no measurement*, not missing data.

```text
Price-path research   = V4B  (what we have)
Price-formation research = reserved  (needs book / flow)
```

---

## 2. The fundamental object

The institutional object in the memo is:

```text
X_t = { G_t, F_t, K_t, O_t, L_t, τ_t }
B_t = K_t − F_t
```

ROLLER’s actual `X_t` (assembled inside `db.greeks()`, never written onto `O_t`):

| Symbol | In the memo | In V4 | Status |
|--------|-------------|-------|--------|
| `G_t` | Full basketball state | Period, clock, home−away score; NBA possessions exist as **data** | **Partial state.** Possession is not a validated conditioner of `F`. |
| `F_t` | Modeled P(win) | V4A prior-only empirical win rate among other games | **Implemented.** `F_t ≠ truth`. |
| `K_t` | Market-implied probability | Latest visible home `yes_bid_close` (integer E4) | **Implemented as candle close.** Not mid, not microprice. |
| `O_t` | Order-book state | Observation `O_t` is the PIT information set, **not** the book | **Name collision.** ROLLER `O_t` ≠ book. Book `O_t` is absent. |
| `L_t` | Liquidity vector | Not present | **Not constructible** from OHLC. |
| `τ_t` | Remaining game time | Elapsed / remaining clock on the observation | **Implemented** as state fields. |
| `B_t` | Market basis | `market_fundamental_basis` | **Implemented.** Exact rational. `B_t ≠ edge`. |

The questions the memo wants — why is the market at 80, how did it get there, how unstable is that probability, did the market’s response differ from the historically expected response — are only **partially** answerable:

| Question | V4 object | Limit |
|----------|-----------|--------|
| What was knowable? | `db.observation()` / V4A `F_t` | No future labels on `O_t`. |
| What did K and F do over the last visible minute? | V4B deltas + basis | 60-second candle identity only. |
| Was that move unusual in the same `core_v1` cell? | V4B `E[M \| core_v1]` residual | Not the full `E[ΔK \| G, τ, F, σ, L, O]` residual. |
| Did the book cause it? | — | **Not constructible.** |

---

## 3. Core Greek stack

| Greek | Memo measures | V4 measurement | Constructibility |
|-------|---------------|----------------|------------------|
| Δ | First-order sensitivity | `market_delta_1m`, `fundamental_delta`, path `score_delta` | **Implemented** as candle/path objects. Not a full ∂F/∂G surface. |
| Γ | Curvature | `discrete_gamma` = `ΔF_t − ΔF_{t-1}` | **Implemented as temporal second difference.** **Not** `∂²F/∂S²`. |
| Θ | Clock | `theta_observed`, `pure_theta` | **Implemented / PARTIAL.** `pure_theta ≠ no-event theta`. |
| ν Vega | Volatility sensitivity | V4B key `realized_market_volatility` = Σ\|ΔK\| | **Path descriptor.** Canonical identity `market_absolute_variation`. **Not** `σ_K`, IV, or Vega. |
| Λ | Liquidity sensitivity | — | **NOT_CONSTRUCTIBLE** |
| Π / λ | Price impact | `price_impact_lambda` | **NOT_CONSTRUCTIBLE** |
| Ω | Book pressure / OBI | `order_book_imbalance` | **NOT_CONSTRUCTIBLE** |
| Ψ | Resilience | `psi_resilience` | **NOT_CONSTRUCTIBLE** |
| B | Basis | `market_fundamental_basis`, `basis_delta` | **Implemented.** Standardized basis and half-life are **not**. |
| R | Residual | V4B `R = M − E[M \| core_v1]` | **Implemented** for the thirteen V4B families. Residual-Γ / residual-ν families beyond that are reserved. |

```text
MEASUREMENT ≠ EDGE
```

---

## Part I — Basketball-state Greeks

### 4. Delta / score delta

**Wanted:** `Δ_score = ∂F/∂(score differential)` as a function of period, clock, possession, team quality, home/away, volatility regime.

**Have:**

- `score_delta` = path `ΔF / ΔS` where `S = home − away`, null if `ΔS = 0`.
- Conditioning of `F` itself is `core_v1` only: period, clock bucket, score-margin bucket.
- **Not** possession, pre-game strength, home/away as extra `F` dimensions.

```text
IMPLEMENTED:     path score_delta
NOT YET:         conditional_score_surface_delta
NEVER ASSUMED:   +1 point = constant probability change
```

`+1` is not treated as a constant. The path measurement is silent when the score does not change. A full surface is a different identity and is reserved.

### 5. Possession delta

**Wanted:** `F(G | team possession) − F(G | opponent possession)` on TIME × SCORE × PERIOD.

**Have:**

```text
NBA V2 possessions = REAL          ← data capability
POSSESSION_CONDITIONED_F           ← NOT VALIDATED
possession_delta                   ← NOT_YET_IMPLEMENTED
value                              ← null
```

`DATA EXISTS ≠ MEASUREMENT IS VALID`. V4 will not infer possession from candles.

### 6. Event delta

**Wanted:** `F_{t+} − F_{t−}` on made 3, turnover, foul, timeout, injury, … then `ΔK = ΔF + R`.

**Have:**

- Event sequence exists in PBP (separate from Greeks).
- `event_delta` = **NOT_YET_IMPLEMENTED**.
- `response_delta` = `ΔK − ΔF` over the **candle interval**, not over a named basketball event.

So the residual philosophy is present at candle resolution. The event-conditioned version is not.

---

## Part II — Gamma

### 7. Score gamma

**Wanted:** `Γ_score = ∂²F/∂S²` and a convexity map of the win-probability surface.

**Have:** `discrete_gamma` = temporal `ΔF_t − ΔF_{t-1}` on two compatible 60-second intervals.

```text
discrete_gamma  ≠  score_surface_gamma
```

That inequality is an identity firewall, not a comment.

### 8. Time gamma

**Wanted:** `∂²F/∂τ²`, regimes clustered from data (early / late / terminal).

**Have:** `time_gamma` = **NOT_YET_IMPLEMENTED**. No unsupervised clustering. No invented regimes.

---

## Part III — Theta

### 9. Clock decay

**Wanted:** `Θ = ∂F/∂τ` conditioned on lead/trail, plus a pure-clock object that isolates time with *no basketball information*.

**Have:**

| Object | Definition | Status |
|--------|------------|--------|
| `theta_observed` | `ΔF / Δelapsed_game_seconds` | **Implemented.** Null if `Δelapsed = 0`. |
| `pure_theta` | `theta_observed` only if period **and** `S` unchanged | **PARTIAL.** |
| `no_event_theta` | Requires a validated no-event window | **NOT_YET_IMPLEMENTED.** |

```text
PURE THETA ≠ NO-EVENT THETA
```

Same score and same period is **not** proof that no basketball events occurred. V4 refuses that leap.

---

## Part IV — Vega

### 10. Volatility objects

| Memo object | V4 | Status |
|-------------|----|--------|
| `σ_G` game-path variance | — | **NOT_YET_IMPLEMENTED** |
| `σ_F = Std(ΔF)` | — | **NOT_YET_IMPLEMENTED** (`sigma_F`) |
| `σ_K = Std(ΔK)` | — | **NOT_YET_IMPLEMENTED** (`sigma_K`) |
| Excess `σ_K − σ_F` / ratio | — | **NOT_YET_IMPLEMENTED** |
| Candle realized vol | V4B key `realized_market_volatility` = rolling Σ\|ΔK\| | **Implemented as `market_absolute_variation`.** |
| Candle range | `candle_range` | **Implemented.** Unordered OHLC summary. |
| Directional efficiency | `abs(close−open)/(high−low)` | **Implemented.** |

```text
realized_market_volatility  ≠  sigma_K
canonical_identity          =  market_absolute_variation
measurement_class           =  PATH_DESCRIPTOR
```

The memo is correct that stdev of candle returns is a weak definition of Vega. V4 therefore **does not rename** absolute variation as `σ_K`, and V4C will not let the frozen V4B key be read as “market volatility.”

```text
VR > 1  ≠  edge
Model disagreement ≠ market inefficiency
```

---

## Part V — Market delta / response beta

### 11. `ΔK = β ΔF + ε`

**Wanted:** estimated `β_t = ∂K/∂F` (under/over-reaction research).

**Have:**

| Object | Meaning |
|--------|---------|
| `market_delta_1m` | `ΔK` on a 60-second visible pair |
| `fundamental_delta` | `ΔF` from two independent `db.fundamental()` calls |
| `response_delta` | `ΔK − ΔF` (additive residual, not a slope) |
| `response_beta` | **NOT_YET_IMPLEMENTED.** No proxy slope from one interval. |

```text
response_delta  ≠  response_beta
UNDERREACTION ≠ TRADE
OVERREACTION ≠ TRADE
```

Reconciliation (exact rationals, no float tolerance):

```text
basis_delta = response_delta = market_delta_1m − fundamental_delta
```

or the payload is `RECONCILIATION_FAILED` and the contradictory numbers are nulled.

---

## Part VI–VII — Liquidity and order-book Greeks

These require `FULL_ORDER_BOOK` or `TRADE_TICK`. The warehouse has 1-minute OHLC.

| Object | Status | Forbidden substitutes |
|--------|--------|------------------------|
| `microprice` | **NOT_CONSTRUCTIBLE** | high/low, midpoint, VWAP-from-candle |
| `order_book_imbalance` | **NOT_CONSTRUCTIBLE** | candle volume |
| `signed_flow_lambda` | **NOT_CONSTRUCTIBLE** | candle volume / signed candle return |
| `price_impact_lambda` | **NOT_CONSTRUCTIBLE** | candle return |
| `psi_resilience` | **NOT_CONSTRUCTIBLE** | volume as queue recovery |

```text
OHLC ≠ ORDER BOOK
CANDLE RETURN ≠ SIGNED FLOW
HIGH/LOW ≠ MICROPRICE
VOLUME ≠ QUEUE STATE
MORE DERIVATION ≠ MORE INFORMATION
```

V4C `value` for every one of these is `None`. There is no calculation path that turns a candle into a book.

---

## Part VIII — Basis Greeks

| Memo | V4 | Status |
|------|----|--------|
| `B_t = K_t − F_t` | `market_fundamental_basis` | **Implemented** as exact E4 rational `(K n − wins×10000) / n` |
| `ΔB` | `basis_delta` | **Implemented** |
| Standardized `Z_B` | `standardized_basis` | **NOT_YET_IMPLEMENTED** |
| Half-life `T_{1/2}` | `basis_half_life` | **NOT_YET_IMPLEMENTED** |

The half-life warning in the memo is already a V4 design constraint: we will not later label “F moved toward K” as market mean reversion. That estimator does not exist yet, so it cannot lie.

---

## Part IX — Residual Greeks

The memo’s research philosophy **is** V4B’s residual design:

```text
COMMON RESPONSE     →  not stored as a single global Δ
EXPECTED RESPONSE   →  E[M | core_v1]
OBSERVED RESPONSE   →  M
OBSERVED − EXPECTED →  R
```

**Implemented:** residual of each V4B measurement against `E[M | core_v1]`, eligibility `measurement_available_at_i < t` and `game_i ≠ game_t`. Insufficient support → `null`, not `0`.

```text
Rᵐ ≠ CAUSAL RESIDUAL
Rᵐ ≠ MARKET ERROR
Rᵐ ≠ EDGE
```

`R` means only: this measurement was unusual in the current `core_v1` cell. It does not mean the market responded irrationally.

**Not implemented:** residual-Γ, residual-ν, residual families beyond V4B `R^M`, or

```text
R_t = ΔK_t − E[ΔK_t | G_t, τ_t, F_t, σ_t, L_t, O_t]
```

`L_t` and book `O_t` are absent. The central residual of §28 is therefore **architecturally named and empirically incomplete**.

---

## Generation 1 candle objects (§19–20)

| Memo V1 object | V4 | Notes |
|----------------|----|-------|
| Event identity / mapping / timestamps | V1 warehouse + PIT | **Implemented** outside Greeks. |
| Missing-candle / interval integrity | `TIME_GAP` when interval ≠ 60s | **Implemented.** |
| Quarter / clock / score | V2 `O_t` | **Implemented.** |
| Possession as state | NBA capability `REAL` | **Data only.** |
| Pre-game strength as Greek conditioner | — | **Not** in `core_v1`. |
| OHLC / range / returns | `candle_range`, `market_delta_1m`, `absolute_return` | **Implemented.** |
| Close-to-close vol | absolute variation, not `σ_CC` stdev | **Different identity.** |
| High-low realized vol | range exists; not a separate `σ_HL` estimator | Range ≠ σ. |
| Directional efficiency | `directional_efficiency` | **Implemented.** |
| MAE / MFE vs `P_0` | — | **Not implemented.** Would still be candle path ≠ fill. |
| True flow / queue / OFI / impact | catalog | **NOT_CONSTRUCTIBLE.** |

```text
CANDLE PATH ≠ TRADE PATH
HIGH/LOW TOUCH ≠ EXECUTABLE FILL
```

---

## Generation 2 order books (§21)

Declared clocks exist (`event_available_at`, `trade_available_at`, `book_snapshot_available_at`) and stay **null**. V4C does not compute them.

`market_delta_1s` is a **different identity** from `market_delta_1m`. Same informal name, different regime and resolution. They are not interchangeable.

---

## Database design (§22–24)

ROLLER already separates layers the way the memo asks:

```text
warehouse raw / canonical
    → PIT I(t)          db.observation()     O_t has no Greeks
    → F_t               db.fundamental()     V4A
    → measurements      db.greeks()          V4B
    → architecture      db.greeks(..., C)    V4C catalog
```

`dataset()` rejects `v4b_*` and `v4c_*`. Greeks are query-time. They do not leak into `O_t`.

Every mapped measurement is indexed by:

```text
MeasurementIdentity =
    measurement_name
  + measurement_class
  + definition_version
  + information_regime
  + resolution
  + conditioning_schema
```

That is §23, implemented. Candle Delta is not future second-level Delta. A Class II sensitivity is not a Class IV surface.

Conditional Greeks (§24) are only as rich as `core_v1`. The memo’s Q4 × 120–180s × possession × liquidity cell is **not** the current conditioner.

---

## Research hierarchy (§25–26)

| Tier | Memo items | V4 |
|------|------------|----|
| **1 Build now** | Probability Δ, score Δ, theta, gamma, candle vol, basis, residual Δ | **Yes, with the identity caveats above.** Gamma is temporal. Vega is abs-variation. Score Δ is path, not surface. |
| **2 When F improves** | Event Δ, possession Δ, state Vega, response β, basis half-life, gamma surface | **Catalogued. Not measured.** |
| **3 With books** | Spread, depth, OBI, microprice, λ, Ψ | **NOT_CONSTRUCTIBLE.** |
| **4 Institutional layer** | Residual Γ/ν, cross-Greeks, surfaces, regime detection | **Catalogued. Cross-Greeks are architectural only.** |

Cross-Greeks (`∂²K/∂F∂L`, etc.) are `NOT_YET_IMPLEMENTED` / architectural only. V4 will not multiply two V4B numbers and call it a cross-Greek.

---

## Lossless contract (what “lossless” actually means)

V4 is lossless **inside the objects it is allowed to compute**.

### Lossless today

1. **V4A `F_t`** — exact `{numerator, denominator}` = `{wins, n}`. No float probability as the stored value.
2. **V4B rationals** — `Fraction` arithmetic. `F_e4 = (wins × 10000) / n`. Never floor division. Runtime reconciliation of `ΔK − ΔF`.
3. **V4C overlay** — copies those integers. `source = V4B_CANONICAL_RESULT`. `transformation = LOSSLESS_METADATA_MAPPING`. `V4C_EMPIRICAL_COMPUTATION_COUNT = 0`.
4. **Default API** — `db.greeks(id)` is publicly identical to `schema_version="4.0.0-B"`.
5. **Identity firewall** — a later 1-second or book object cannot silently overwrite a 1-minute identity.

### Not lossless (and not claimed)

The memo’s full desk is **not** a lossless compression of current data into every Greek name. That would be the failure mode V4C exists to prevent: manufacturing microstructure from OHLC, possession delta from `possessions=REAL`, no-event theta from an unchanged score, `σ_K` from Σ\|ΔK\|, or `∂²F/∂S²` from `ΔF_t − ΔF_{t-1}`.

Those are **not missing values**. They are **forbidden substitutions**.

---

## What a Jump-like process would do next (V4 already encodes this)

The memo’s validation ladder is the operating rule, not a future slogan:

```text
RAW OBSERVATION
      ↓
DEFINE OBJECT          ← V4C identity + registry
      ↓
MEASURE ONLY IF
  data ∧ regime ∧ PIT ∧ approved definition
  ∧ implemented definition ∧ unique identity ∧ no proxy
      ↓
ESTIMATE UNCERTAINTY   ← V4B support / MAD; effective_n still null
      ↓
TEST TEMPORAL / OOS / REGIME / EXECUTION
      ↓
ONLY THEN consider economic value
```

V4 stops before economic value. On purpose.

```text
SEARCH FOR:
  STRUCTURAL REPLICATION
  STATE-CONDITIONAL STABILITY
  INDEPENDENT SUPPORT

NOT:
  A DATABASE OF CLEVER GREEK NAMES
```

---

## Central residual — honest status

The memo’s one-object reduction:

```text
R_t = ΔK_t − E[ΔK_t | G_t, τ_t, F_t, σ_t, L_t, O_book]
```

V4’s implemented object:

```text
R^M_t = M_t − E[M_t | core_v1]
```

where `M` is a V4B measurement and `core_v1` is `{period, clock bucket, score-margin bucket}`.

That is the right *shape* and the wrong *conditioning set* relative to the full desk. The missing conditioners are not filled with candles.

---

## Versions and API

| Field | Value |
|-------|--------|
| `state_schema_version` | `2.0.0` |
| `measurement_schema_version` | `3.0.0` |
| `fundamental_schema_version` | `4.0.0-A` |
| `greek_schema_version` | `4.0.0-B` |
| `greek_architecture_version` | `4.0.0-C` |

Authoritative taxonomy: [`config/greek_v4c_registry.json`](../config/greek_v4c_registry.json).

```text
V4A  WHAT COULD HAVE BEEN KNOWN?
V4B  WHAT CAN CURRENT DATA ACTUALLY MEASURE?
V4C  WHICH OBJECTS ARE VALID, UNDER WHICH REGIME,
     AND WHICH MUST REMAIN NULL?
```

---

## Final principle

The eventual goal is not a warehouse of Greek names.

It is a measurement system that can ask:

```text
What should have been measurable here?
What was actually measured?
Does the difference stay null until the information regime exists?
```

ROLLER V4 implements that discipline.

It does **not** implement the full Jump-style desk.

It **does** implement Generation-1 empirical Greeks without loss, and it **does** refuse to convert architectural ambition into synthetic microstructure.

```text
OLD OBJECT          NEW OBJECT (V4)

PRICE TOUCH         STATE
    ↓                   ↓
ENTRY RULE          F_t  (knowable)
    ↓                   ↓
FORWARD OUTCOME     K_t  (visible close)
                        ↓
                    EXPECTED M | core_v1
                        ↓
                    OBSERVED M
                        ↓
                    GREEK DECOMPOSITION (candle identities only)
                        ↓
                    CONDITIONAL RESIDUAL
                        ↓
                    CATALOG OF WHAT MUST STAY NULL
                        ↓
                    STRUCTURAL REPLICATION  (not started as trading)

Δ/Γ/Θ/VEGA/Λ/Ω/Ψ/B/R ≠ EDGE
PURE THETA ≠ NO-EVENT THETA
CANDLE PATH ≠ EXECUTABLE PATH
LIVE EXECUTION = FALSE
```
