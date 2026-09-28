# MLB Historical Event–Market Backtesting & Research Engine

## Final Development Plan

**Status:** Canonical blueprint (2026-08-26)  
**Sport-first:** MLB is the reference implementation for NBA, WNBA, NHL, NCAAB  
**Reset notice:** [`BACKTESTING_ENGINE_RESET.md`](BACKTESTING_ENGINE_RESET.md)

This document is the **complete** development plan. It replaces “extend the FIRST01
candlestick backtester” with a new platform: historical event-market reconstruction
and simulation. FIRST01 is the first **strategy plugin**, not the platform.

---

## North Star

Build a deterministic, tick/event-level historical engine capable of answering:

> **At any point during an MLB game, exactly what was happening in the game, what had
> happened immediately beforehand, what was happening in the Kalshi market/order book,
> how the market had arrived at that state, what the event-derived probability/state
> implied, what FIRST01 would have done, what happened afterward, and what historical
> information could have predicted the outcome?**

The resulting MLB engine is the **reference implementation** for other sports.

---

## Strategic decisions

| Decision | Meaning |
|----------|---------|
| Replace, do not extend | Old candle FIRST01 runner is LEGACY_V1 |
| `GameMarketEpisode` is primary | Trades are downstream of state |
| FIRST01 is a plugin | Engine must not hard-code FIRST01 into the data layer |
| Same schema live ↔ historical | Forward-feed requires `HistoricalState` ≡ live state interface |
| Research ≠ production | Nothing discovered automatically changes production |
| No waterfall skipping | Interesting later layers wait for proven earlier layers |
| Observability honesty | Never fabricate L2; mark TOP_OF_BOOK / CANDLESTICK / MODELED |

### Governance pipeline (mandatory)

```text
RESEARCH → CANDIDATE → VALIDATED → SUPERVISED → APPROVED → PRODUCTION
```

No silent model replacement. No automatic production mutation.

### Downward waterfall (never reverse)

```text
RAW TRUTH
   ↓
SYNCHRONIZED TRUTH
   ↓
STATE
   ↓
PATH
   ↓
TRANSITION
   ↓
STRATEGY REPLAY
   ↓
LABEL
   ↓
RESEARCH
   ↓
MODEL
   ↓
RISK
   ↓
EXECUTION
```

---

# WATERFALL 0 — Architectural foundation

Before importing historical data, establish platform contracts.

### Core entities

```text
Sport
League
Season
Game
Team
Market
Contract
Event
PBPEvent
MarketEvent
GameState
MarketState
StateTransition
GameMarketEpisode
Signal
Order
Fill
Position
Outcome
Feature
Label
Experiment
Model
ModelVersion
ResearchRun
Artifact
```

### Critical principle

The fundamental research object is:

```text
GameMarketEpisode
```

—not a trade.

A trade is merely one possible downstream consequence of a state.

### Invariants (Phase 1 must encode)

1. Every raw record has provenance: `source`, `source_record_id`, `source_timestamp`,
   `ingestion_timestamp`, `raw_file`, `checksum`, `schema_version`.
2. Normalized transforms are versioned; they never overwrite raw.
3. Internal `GameId` is canonical; tickers are aliases.
4. Synchronization confidence is never silently upgraded to EXACT.
5. Observability level is explicit on every market path.

---

# WATERFALL 1 — Immutable raw data lake

Acquire and preserve **all available 2025–2026 MLB historical data**.

### Kalshi (deepest available)

```text
market metadata
market lifecycle
contract metadata
trades
quotes
best bid / best ask
bid size / ask size
order-book levels / changes
timestamps
settlement
market status
```

**Do not silently substitute candles for ticks.**

### MLB (most granular available)

```text
game metadata
pitch-by-pitch PBP
inning / half inning / outs / score / runners
batter / pitcher / pitch count / pitch result
base advancement / runs / reviews / substitutions
game status
```

### Immutability

Once ingested: **never rewrite historical truth.**  
If a parser improves, create a **new normalized version**.

---

# WATERFALL 2 — Canonical identity engine

Deterministic mapping:

```text
MLB Game
       ↕
Internal GameId
       ↕
Kalshi Market
       ↕
Team A contract
Team B contract
```

Must handle: naming, abbreviations, home/away, postponements, doubleheaders,
market creation differences, canceled markets, missing markets, settlement mapping.

Ticker strings are **not** the primary identity.

---

# WATERFALL 3 — Time synchronization engine

Synchronize into a common timeline:

```text
Kalshi timestamp
MLB timestamp
PBP timestamp
game clock
event sequence
```

Every match receives a classification:

```text
EXACT | WITHIN_1S | WITHIN_3S | WITHIN_5S | AMBIGUOUS | UNMATCHED
```

Never pretend synchronization is exact when it is not.

Every synchronized observation retains:

```text
event_timestamp
market_timestamp
synchronization_delta
synchronization_method
synchronization_confidence
```

---

# WATERFALL 4 — MLB event state engine

Canonical `GameState` at every meaningful point:

```text
GameState
├── inning / half inning / outs
├── score / score differential
├── runners / batter / pitcher
├── balls / strikes / pitch count
├── batting order position
├── base/out state
├── home/away
├── game status
└── remaining event opportunity
```

Preserve both **raw baseball time** and **event time**.

Event theta incorporates remaining opportunity (at minimum outs remaining),
extensible toward plate appearances, batters faced, run opportunities, leverage.

**Do not replace** the actual baseball clock/state with a synthetic metric.  
**Derive** synthetics from the actual event.

---

# WATERFALL 5 — MLB PBP state transition engine

Snapshots are not enough. For every transition:

```text
State(t-1) → Event → State(t)
```

Record: previous state, event, new state, event timestamp, sequence number, PBP source.

This is the actual event stream.

---

# WATERFALL 6 — Kalshi market state engine

Per Team A / Team B contract:

```text
MarketState
├── best bid / ask / sizes / spread
├── last trade / trade size / volume
├── depth / imbalance / liquidity
├── quote intensity / trade intensity
├── price velocity / acceleration
└── market status
```

Observability:

| Reality | Mark |
|---------|------|
| Full L2 | preserve book |
| Top-of-book only | `observability = TOP_OF_BOOK` |
| Candles only | `observability = CANDLESTICK` |

**Never fabricate unavailable order-book information.**

---

# WATERFALL 7 — Team A / Team B coupled market model

Reconstruct both contracts simultaneously for every game.

Starting references (all preserved):

```text
market inception
first observation
first trade
game start
first meaningful quote
```

Including first observed prices, bid/ask, liquidity, creation time, game-start price.

---

# WATERFALL 8 — Complete path engine

For every observation point `t`, reconstruct:

```text
START → EVENT PATH → MARKET PATH → STATE TRANSITIONS → CURRENT OBSERVATION
```

At e.g. 80.4¢ we must know **how the market got there**. That path is preserved.
This is what separates the new engine from the old backtester.

---

# WATERFALL 9 — Event Greeks / event dynamics

Empirical sporting-event quantities (not assumed financial formulas):

```text
Event Theta | Event Delta | Event Gamma
Event Volatility | Event Alpha | Event Beta
```

Examples:

- **ΘE** — how rapidly uncertainty/opportunity changes as remaining opportunity is consumed  
- **ΔE** — sensitivity of outcome probability to score/outs/base/inning/PBP  
- **ΓE** — change in that sensitivity  
- **VE** — conditional outcome uncertainty given state  
- **αE/βE** — empirical event-probability ↔ market relationship  

Every Greek: `value`, `timestamp`, `window`, `method`, `version`.

---

# WATERFALL 10 — Market Greeks

```text
Market Theta | Market Delta | Market Gamma
Market Volatility | Market Alpha | Market Beta
```

Across price, spread, depth, liquidity, order-book imbalance.

Central relationship (to discover empirically):

```text
MarketDynamics = F(EventState, EventDynamics, MarketState)
Θ_M = f(Θ_E, State, Liquidity, OrderBook)
```

---

# WATERFALL 11 — Threshold transition engine

First-touch events at:

```text
20% 30% 40% 50% 60% 70% 80% 81% 83% 89% 90% 95%
```

Per contract: first_touch timestamp/price, preceding/following price,
time since previous threshold.

FIRST01 anchor: `FIRST_80`. Entire hierarchy retained for research.

---

# WATERFALL 12 — The first-80 state vector

At the exact first 80% transition, capture:

- Starting conditions (Team A/B start prices, spread, liquidity)
- Current market state (prices, bid/ask, depth, imbalance)
- Entire price path (open → 50 → 60 → 70 → 80)
- Entire event path (start → inning/score/outs/runners/PBP)
- Event Greeks and Market Greeks
- Context (inning, outs, runners, differential, remaining opportunity)

This is the canonical **80% transition signature**.

---

# WATERFALL 13 — FIRST01 strategy plugin

Only now replay FIRST01.

Ask: *Given the historical state stream, what would FIRST01 have done?*  
Not: *What parameters produce the best historical result?*

Frozen baseline (control):

```text
one canonical opportunity per GameId
sticky first_80
81 confirmation
maker entry
80–83 entry range
GAME_LOCK ≥ 89
50% entry-VWAP stop
one lifecycle consumed per game
```

Strategy is a **plugin**. The historical data layer must not hard-code FIRST01.

---

# WATERFALL 14 — Execution simulation

```text
Signal → Order → Queue/liquidity → Fill → Position → Exit
```

Eventually support: maker probability, partial fills, queue assumptions,
available liquidity, spread, slippage, latency, cancellation, IOC behavior.

Where evidence does not support an assumption: mark **`MODELED`**, not historical fact.

---

# WATERFALL 15 — Outcome / label engine

Every first-80 episode receives future labels:

| Family | Examples |
|--------|----------|
| Price | hit 81/83/89/90/95 |
| Adverse | −5/−10/−20/−30¢, −50% |
| Horizons | 1s … 60m, settlement |
| Trade | stop, settle W/L, MFE, MAE, time to adverse/favorable, P&L |

These are training labels for the future prediction engine.

---

# WATERFALL 16 — Loser classification engine

| Class | Dimensions |
|-------|------------|
| 1 Temporal | when 80/entry/50%; remaining event time |
| 2 Event | inning, outs, score, runners, PBP sequence |
| 3 Price | start, trajectory, velocity, acceleration, thresholds |
| 4 Market | liquidity, spread, depth, imbalance, book changes |
| 5 Combined | Price + Event + PBP + Orderbook + Theta |

Search for statistically distinct loser cohorts (motivated by live desk losses).

---

# WATERFALL 17 — Advanced ML / XGBoost / Monte Carlo

Only after the deterministic dataset is trustworthy.

Predict e.g. P(50% adverse), P(hit 89 first), P(settle W/L), P(fill), E[P&L], E[MAE/MFE].

Candidates: XGBoost, GBM, logistic, survival, Monte Carlo, calibration, ensembles.

**ML never becomes the source of truth.** Reconstructed historical state is.

---

# WATERFALL 18 — Hyperparameterization

Only after the baseline research engine works.

May investigate entry/confirm/range/lock/stop thresholds, time windows,
event/market/liquidity/PBP filters.

Every experiment: versioned, reproducible, OOS + walk-forward tested.  
FIRST01 canonical baseline remains the **control**.

---

# WATERFALL 19 — Validation / anti-overfitting

Mandatory for every candidate:

```text
train | validation | OOS | walk-forward | regime analysis
```

Where appropriate: purged temporal CV, embargo, bootstrap, Monte Carlo, CIs.

Detect: look-ahead, survivorship, leakage (future PBP/quotes), duplicate GameIds/
opportunities, timestamp collisions, missing data.

---

# WATERFALL 20 — Research reporting (Google Drive)

Drive is a first-class output. Example layout:

```text
MLB Research/
├── 2025/ … 2026/
│   ├── Raw Data/
│   ├── Normalized Data/
│   ├── State Reconstruction/
│   ├── Market Reconstruction/
│   ├── FIRST01/
│   ├── Loss Analysis/
│   ├── Orderbook Research/
│   ├── ML/
│   └── Runs/<run_id>/
├── Models/
├── Experiments/
├── Dashboards/
└── Reports/
```

Each run: immutable artifact directory.

---

# WATERFALL 21 — Google Sheets reporting

Sheets = human research **index**, not the database.

Auto-report per run: run summary, FIRST01 metrics, 80% transition stats,
loss cohorts, orderbook, model results, data quality — with Drive artifact links.

---

# WATERFALL 22 — Deep research artifacts

Machine + human readable per run, including:

```text
run_manifest.json
data_inventory.json
game_inventory.csv / market_inventory.csv
synchronization_report.csv
game_state.parquet / market_state.parquet / state_transitions.parquet
first80_episodes.parquet / first80_summary.csv
first01_trades.csv / loss_classification.csv
orderbook_features.parquet
event_greeks.parquet / market_greeks.parquet
labels.parquet / model_results.csv / validation_report.json
README.md / research_report.md / loss_analysis.md / …
```

---

# WATERFALL 23 — Research dashboard

Select sport/season/date/game/team/market/80% episode/loss class/inning/out/score
and inspect game state ↔ market state ↔ first 80% ↔ trade simulation ↔ future path ↔ outcome.

Losing trade drill-down:

> What the game was doing → what the market was doing → how price arrived at 80% → what happened next.

---

# WATERFALL 24 — Model registry / governance

Every model: id, version, dataset, features, hyperparams, train/val/OOS windows,
metrics, approval status, deployment status.

Statuses: RESEARCH → CANDIDATE → VALIDATED → SUPERVISED → APPROVED → PRODUCTION.

---

# WATERFALL 25 — Future production bridge

```text
Historical State Engine → Prediction → Risk Decision Engine → Algorithmic Execution
```

Live must consume the **same state schema** historical replay produces:

```text
HistoricalState ── Replay
                └─ Live
```

Avoid `backtest_state ≠ live_state`.

---

# WATERFALL 26 — Live → research feedback

```text
LIVE GAME → LIVE STATE → LIVE MARKET → EXECUTION → RESULT
    → RAW ARCHIVE → RESEARCH DB → MODEL RE-EVALUATION
```

Production observations become additional data.  
Production does **not** automatically rewrite the model.

---

# MLB completion criteria

MLB is **not** “done” when a P&L table exists. Complete only when all gates pass:

### Data
- [ ] 2025–2026 MLB + Kalshi + PBP inventoried  
- [ ] Raw immutable; provenance complete  

### Reconstruction
- [ ] Canonical GameId; Team A/B mapping  
- [ ] Game-state, PBP sequence, market-state  
- [ ] Time sync; state transitions; observability classification  

### Market
- [ ] Starting Team A/B prices; opening-state definitions  
- [ ] Complete price/quote/(L2 if any)/liquidity paths  

### Event
- [ ] Inning/half/outs/score/runners/batter-pitcher/PBP  
- [ ] Event theta + event dynamics  

### Market ↔ event
- [ ] Market Greeks; α/β framework  
- [ ] Event→market response; market→event timing  

### FIRST01 plugin
- [ ] One-trade-per-game; first-80; 81; entry; fill sim; lock; stop; settlement; P&L  

### Research
- [ ] First-80 dataset; pre/post paths; W/L classes; MAE/MFE; horizons; cohorts  

### ML
- [ ] Feature warehouse; baselines; XGBoost; Monte Carlo  
- [ ] Temporal validation; walk-forward; leakage detection; calibration; registry  

### Reporting
- [ ] Drive + Sheets automation; manifests; research/loss/model/DQ reports  

### Reproducibility
- [ ] Same input → same output; versioned transforms/features/models  

---

# Cursor development order (one layer at a time)

```text
PHASE 1   Repository / architecture / contracts
PHASE 2   Raw data ingestion + immutable storage
PHASE 3   Identity + market/game mapping
PHASE 4   MLB PBP reconstruction
PHASE 5   Kalshi reconstruction
PHASE 6   Timestamp synchronization
PHASE 7   Canonical GameState
PHASE 8   Canonical MarketState
PHASE 9   StateTransition engine
PHASE 10  Complete path reconstruction
PHASE 11  Event theta / event dynamics
PHASE 12  Market theta / market dynamics
PHASE 13  Threshold / first-80 engine
PHASE 14  FIRST01 replay plugin
PHASE 15  Execution/fill simulation
PHASE 16  Outcome + label engine
PHASE 17  Research/loser classification
PHASE 18  Orderbook research
PHASE 19  ML / XGBoost / Monte Carlo
PHASE 20  Hyperparameterization
PHASE 21  OOS / walk-forward validation
PHASE 22  Google Drive / Sheets reporting
PHASE 23  Cloud research dashboard
PHASE 24  Supervised prediction interface
PHASE 25  Risk Decision Engine interface
PHASE 26  Algorithmic Execution interface
PHASE 27  Live feedback loop
```

**Critical rule:** Do not skip forward because a later layer is interesting.  
Do not start tuning FIRST01 before RAW → SYNC → STATE → PATH → TRANSITION exist.

---

# Ultimate architecture

```text
                 ┌───────────────────────┐
                 │   IMMUTABLE RAW DATA  │
                 └───────────┬───────────┘
                             ↓
                 ┌───────────────────────┐
                 │  EVENT/MARKET TRUTH   │
                 └───────────┬───────────┘
                             ↓
                 ┌───────────────────────┐
                 │ SYNCHRONIZED STATE    │
                 └───────────┬───────────┘
                             ↓
                 ┌───────────────────────┐
                 │ COMPLETE STATE PATH   │
                 └───────────┬───────────┘
                             ↓
                 ┌───────────────────────┐
                 │   FIRST01 / STRATEGY  │
                 └───────────┬───────────┘
               ┌─────────────┴─────────────┐
               ↓                           ↓
        EVENT INTELLIGENCE           MARKET INTELLIGENCE
               │                           │
               └─────────────┬─────────────┘
                             ↓
                 ┌───────────────────────┐
                 │ PREDICTION / ML       │
                 └───────────┬───────────┘
                             ↓
                 ┌───────────────────────┐
                 │ HYPERPARAMETERIZATION │
                 └───────────┬───────────┘
                             ↓
                 ┌───────────────────────┐
                 │ OOS / WALK-FORWARD    │
                 └───────────┬───────────┘
                             ↓
                 ┌───────────────────────┐
                 │ SUPERVISED CANDIDATE  │
                 └───────────┬───────────┘
                             ↓
                 ┌───────────────────────┐
                 │ RISK DECISION ENGINE  │
                 └───────────┬───────────┘
                             ↓
                 ┌───────────────────────┐
                 │ ALGORITHMIC EXECUTION │
                 └───────────┬───────────┘
                             ↓
                           LIVE
                             │
                             └────→ RAW DATA
```

After MLB passes reconstruction, replay, validation, reporting, and reproducibility
gates: extract sport-agnostic interfaces; build NBA/WNBA/NHL/NCAAB as **adapters**,
not five independent systems.

---

## Immediate next step

**Waterfall 0 is complete** (recon + governance baseline). Living roadmap:
[`BACKTEST_ENGINE_WATERFALL.md`](BACKTEST_ENGINE_WATERFALL.md).

**Next (CEO authorization required):** `W1-A1-S1` — lake catalog schema
(docs + fixtures), then remaining Waterfall 1 S-steps one at a time.

This plan’s “Phase 1 contracts” were delivered as Waterfall 0 documentation.
Do not skip to FIRST01 retuning, ML, or production changes.
