# Momento Systems — Master Development Roadmap

**Status:** Canonical tracker. Not a flat TODO pile.
**Locked:** 2026-09-15.
**Notion:** readable copy only. This file is source of truth.
The 16-row mirror is
[`MOMENTO_SYSTEMS_PROGRAM_BOARD.md`](MOMENTO_SYSTEMS_PROGRAM_BOARD.md).

The 19-system tournament bracket (15 tournament + 4 infrastructure) is the ownership architecture in
[`docs/momento/ARCHITECTURE.md`](../momento/ARCHITECTURE.md).
This file is the sequential capability roadmap. They are not the same
document.

October 1, 2026 is the NBA/NCAAB **dual-market ingest + Autoingest**
milestone. It is not “everything finished.”

Bring Polymarket 1-minute candles in **before October 1 as an
ingestion/data capability**. Do not build Terminito, Fluctuations, or
Relative Value HFT on assumed Kalshi↔Polymarket↔PBP synchronization.

```text
ROLLER = measure
SUPERASI = A Base → B Debase → Final → ITI
VITAL = execution
AUTOINGEST = acquisition + validation
AUTOJEST = Autoingest dashboard (not Jump, not Vital)
TERMINITO = later probability / MCS / fluctuations
```

---

## Absolute refusals

- Do not start warehouse Phase 21 or Confirm & Run cutover.
- Do not start W9.
- Do not change live FIRST01 / 80/81/83/89.
- Do not treat Polymarket as Kalshi TOB.
- Do not merge Kalshi and Polymarket into one quote.
- Do not invent missing minutes, OHLC, bid/ask, L2, fills, or PIT.
- `CANDLE OBSERVATION ≠ EXECUTABLE FILL`.
- Candle-path EV is not a fill. Missing is never `$0`.
- Do not remount Autojest inside Jump or Vital.
- Do not give agentic traders live bankroll before the research → paper ladder.

Governing warehouse: `research/warehouse_refactor/PLAN.md`.
Polymarket basis: `ROLLER/docs/DATA_LINEAGE.md`.
DATA-INGEST plane: `docs/research/architecture-decisions/ADR-0021-continuous-ingestion-plane.md`.

---

## What exists today

- ROLLER NBA desk Phases 0–20 complete. Confirm & Run still CSV.
  Historical L2/tick remain `DATA_REQUIRED`. PBP↔candle PIT remains
  `OPERATION_REQUIRED`.
- NCAAB sequential desk is gated in `research/warehouse_refactor/NCAAB_PLAN.md`.
  Same PIT / L2 honesty.
- Polymarket 1-minute last-trade history already lands for NBA / NCAAB / WNBA
  via `ROLLER/scripts/ingest_polymarket.py`. Basis is `LAST_TRADE_PRINT`.
  Bid/ask are not invented. Settlement still comes from Kalshi, never from
  Polymarket price. Joint Kalshi + Polymarket in one question is
  `OPERATION_REQUIRED`.
- DATA-INGEST already exists. Autoingest / Autojest is the operator control
  plane on top of that plane, not a second warehouse.
- SuperASI A → B → Final → ITI is implemented and research-only. Correcting
  A/B and “ITI Robust Optimized” are later tracks, not silent live retunes.
- Vital owns MLB 001 execution. Browser never submits.
  Observe-only live unit desk: `frontend/vital-terminal` `:5180#/live`.
  Stack map: [`MOMENTO_LAYOUT.md`](MOMENTO_LAYOUT.md).
  Operator read: [`research/vital/LIVE_SERVICE_DESK.md`](../../research/vital/LIVE_SERVICE_DESK.md).

---

## Naming

- **Autoingest** — automated acquisition + validation program.
- **Autojest** — its dashboard. New Vite surface. Not remounted in Jump or Vital.

---

## Dependency order

```text
Vital + ROLLER (now)
        ↓
Polymarket 1m ingest ready (before Oct 1)
        ↓
Autoingest + Autojest (before / around Oct 1)
        ↓
Kalshi + Poly + PBP intersection (explicit PIT op, after ingest trustworthy)
        ↓
ROLLER 1m realism audit
        ↓
SuperASI A/B correction (original design; no invented realism)
        ↓
Correlation Programming (ROLLER N, anti-overfit)
        ↓
ITI Robust Optimized
        ↓
Terminito X / Y / multiple MCS
        ↓
Ontologic Z + Fluctuations
        ↓
same-game Relative Value (Todd Klein normalization)
        ↓
Long-term hold EV
        ↓
Cloud Momento (interfaces first, not dump local FS)
        ↓
Agentic traders (research → paper → limited live; Vital only)
```

```text
                         MOMENTO
                            │
            ┌───────────────┼────────────────┐
            │               │                │
          ROLLER          VITAL           SUPERASI
            │               │                │
            │               │          A → B → Final
            │               │                │
            │               │               ITI
            ▼               │                │
      POLYMARKET 1m         │                │
            │               │                │
            ▼               │                │
   KALSHI + POLY + PBP      │                │
            │               │                │
            ▼               │                │
      REALISM AUDIT         │                │
            │               │                │
            ▼               │                │
    CORRELATION PROGRAM     │                │
            └──────────┬────┴────────────────┘
                       ▼
                   TERMINITO
                       │
          ┌────────────┼────────────┐
          │            │            │
      Ontologic X  Ontologic Y  Fluctuations
          └───────┬────┘            │
                  ▼                 │
             Ontologic Z            │
                  └────────┬────────┘
                           ▼
                    Relative Value
                           │
                           ▼
                 Long-Term Hold EV
                           │
                           ▼
                    Cloud Momento
                           │
                           ▼
                    Agentic Traders
                           │
                         VITAL
```

---

## October 1, 2026 — what “ready” means

Claim only what data can support:

- Kalshi 1-minute `TRADABLE_YES_BID` coverage for NBA/NCAAB season start
  (existing warehouse contract).
- Polymarket 1-minute `LAST_TRADE_PRINT` ingest operational and scheduled.
  No fabricated minutes.
- PBP present where the source has it. Unlinked games stay unlinked.
- Game / market identity without reminting.
- Autoingest statuses: `READY`, `DATA_REQUIRED`, `INGEST_RUNNING`,
  `INGEST_FAILED`, `STALE`, `PARTIAL`, `VALIDATED`.
  “Last run succeeded” is not truth.
- Validation of usable rows, markets, games, gaps, freshness.

Do **not** mark these as October 1 done unless a later authorized phase
actually ships them:

- PBP↔candle PIT (today `OPERATION_REQUIRED`)
- Joint Kalshi + Polymarket quote merge
- Terminito / Fluctuations / RV HFT
- Autojest as a live trading console

---

## Programs

Each card: purpose, timing, depends-on, out.

### 1. Vital

**Purpose:** Execution infrastructure. MLB 001 first.
**Timing:** Now.
**Depends-on:** Existing engine + Risk + `mlb_factory_v1`.
**Out:** Second engine. Second Risk. Browser submit. Invented fills.
Live FIRST01 / 80/81/83/89 changes. Autojest remounted in Vital.

### 2. ROLLER completion

**Purpose:** Research measurement truth.
**Timing:** Now.
**Depends-on:** NBA Phases 0–20 (complete). NCAAB/MLB same contracts
where data exists.
**Out:** Reopen NBA 0–20 as incomplete. Phase 21. Confirm & Run cutover.
Invented coverage. Candle path as a fill.

### 3. Polymarket 1-minute

**Purpose:** Second prediction-market observation source for NBA/NCAAB
(and existing WNBA last-trade history).
**Timing:** Operational before October 1, 2026.
**Depends-on:** Existing `ingest_polymarket.py` + `LAST_TRADE_PRINT` contract.
**Out:** Invented TOB. Polymarket satisfying `yes_bid_close`. Fabricated
minutes. OHLC invention. FIRST80 locks on Polymarket.

Preserve on every observation: market identity, event identity, game
identity, timestamp, price, source, observation type, availability / PIT
metadata, gaps, provenance.

### 4. Kalshi + Polymarket + PBP intersection

**Purpose:** Same-game research row with explicit identity, clocks, PIT
availability, and same-minute ambiguity.
**Timing:** Immediately after Polymarket ingest is trustworthy. Not
assumed complete on October 1.
**Depends-on:** Program 3. ROLLER game/market identity. PBP sequence
where present.
**Out:** Assumed synchronization. Merged quote. Phase 21. Confirm & Run
cutover. Invented PIT.

```text
                    SAME GAME
                       │
          ┌────────────┼────────────┐
          │            │            │
         PBP         KALSHI      POLYMARKET
          └────────────┼────────────┘
                       │
                  ROLLER TIME
                       │
                POINT-IN-TIME
                       │
                 RESEARCH ROW
```

Intersection ≠ synchronization by assumption. The dataset must answer:
what did Kalshi and Polymarket actually show at the same point in the
game, given information available at that time?

### 5. Autoingest + Autojest

**Purpose:** Automated data-acquisition and validation control plane.
**Timing:** Before / around October 1, 2026.
**Depends-on:** ADR-0021 DATA-INGEST. Programs 2 and 3.
**Out:** Second warehouse. “Last run succeeded” as coverage. Live
trading console. Remount inside Jump or Vital.

Sources: NBA / NCAAB / MLB Kalshi, Polymarket, and PBP.

Dashboard must show: source, sport, league, date range, last successful
ingest, current ingest, rows, markets, games, gaps, errors, validation,
freshness, coverage — plus the statuses listed in the October 1 section.

### 6. ROLLER 1-minute realism audit

**Purpose:** Make 1-minute candle research as realistic as the
observation permits.
**Timing:** High priority after dual-market ingest is trustworthy.
**Depends-on:** Programs 2–4 where they exist. Existing Kalshi 1m now.
**Out:** Treating a candle as a fill. Inventing path order the minute
cannot support.

Audit: touch, cross, break, reversal, bounce, recovery, max/min, entry
reference, exit reference, jump-through, same-minute events, missing
minutes, stale observations, bid/ask semantics, last-trade semantics,
path ordering.

### 7. SuperASI A/B correction

**Purpose:** Restore the original A Base / B Debase design.
**Timing:** High priority after realism audit can feed it.
**Depends-on:** Program 6. Existing SuperASI research path.
**Out:** Manufacturing realism the data cannot support. Changing live
80/81. Mode D. Invented A–F from a headline EV.

ROLLER measures. SuperASI identifies and cleans assumptions that are
not realistic enough for the intended research interpretation.

### 8. Correlation Programming

**Purpose:** Inside a defined ROLLER N universe, which feature states
associate with the observed outcome distribution, and does that survive
overfit controls?
**Timing:** After clean ROLLER / SuperASI.
**Depends-on:** Programs 6 and 7.
**Out:** In-sample-only “edges.” Selecting features only because they
look good in TRAIN.

Partition by feature class / store (market, game, PBP, price, time,
state). Graph: feature → value/bucket → N → W → L → rate → uncertainty
→ OOS. Require train/validation/OOS, minimum N, cardinality controls,
multiple-testing awareness, period/game stability, permutation/null
where appropriate.

### 9. ITI Robust Optimized

**Purpose:** Creatively search more optimal entry/exit structures for a
trade measured in ROLLER and verified in SuperASI A/B.
**Timing:** After corrected A/B.
**Depends-on:** Program 7.
**Out:** Max historical PNL search. Live signal. Changing factory 80/81.

Optimization includes base result, robustness, OOS, perturbation,
sensitivity, coverage, replication.

### 10. Terminito — Ontologic X / Y / multiple MCS

**Purpose:** Probabilistic event-state engine.
**Timing:** After the data foundation (programs 3–8).
**Depends-on:** Dual-market ingest + realism + correlation where used.
**Out:** Live Kalshi signal. Averaging X and Y and calling it Z.
Invented sportsbook calendars.

- **X** — calibrated sportsbook-derived event distribution (vig handled
  explicitly, then MCS).
- **Y** — same event structure from Momento assumptions + game state +
  features + logic, not sportsbook odds.
- **Multiple MCS** — winner, spread, total, player, period, next-event,
  contract-specific, on the same game.

### 11. Terminito — Ontologic Z

**Purpose:** Calibrate X and Y as a joint distribution and joint event
universe. Not an average.
**Timing:** After X and Y exist.
**Depends-on:** Program 10.
**Out:** Blind blend. Invented “true odds” without a stated calibration.

### 12. Terminito — Fluctuations

**Purpose:** `P(K_{t+1} | K_t, state, action)` as a Markov price chain.
**Timing:** After Terminito foundation.
**Depends-on:** Programs 10–11. ROLLER 1m realism.
**Out:** Using last-trade as if it were executable. Live HFT from this
module before dual-market PIT exists.

Given time, action, and score/game state: expected contract change
distribution, then transition probabilities.

### 13. Relative Value HFT

**Purpose:** Same-game cross-venue relative value (Kalshi ↔ Polymarket
first).
**Timing:** After both venues are mature and point-in-time aligned.
**Depends-on:** Programs 4, 8, 11, 12.
**Out:** Broad cross-sport RV first. Copying NQ/ES numbers. Building on
unaligned clocks.

Todd Klein normalization (conceptual, not the futures example numbers):

```text
(Wing Price / Base Price) × Beta     → relative scaling factor
(Base Price − Base Anchor) × scale   → expected Wing displacement
Wing Price − expected Wing           → RV deviation
then convert to that venue's tick / contract unit
```

Choose wing, base, beta, anchor, and unit per market pair.

### 14. Long-term hold EV

**Purpose:** Long-duration contracts (example: championship) and 4–6%
fluctuation capture. Terminal outcome ≠ optimal holding strategy.
**Timing:** Later research track.
**Depends-on:** Terminito + Fluctuations + Z when used.
**Out:** Treating terminal settlement as the only monetization path.

Framework: long-duration contracts, fundamental probability, EV, hold /
opportunity cost, fluctuation capture, time decay, liquidity, exit
probability, terminal payoff, path-based monetization.

### 15. Cloud Momento

**Purpose:** Remove local-only as a single point of failure once research
and execution are economically meaningful.
**Timing:** After interfaces stabilize.
**Depends-on:** Clear ownership of ROLLER warehouse, Autoingest, Vital.
**Out:** Dumping the local filesystem into a bucket.

Need: durable storage, backups, reproducible environments, remote
compute, scheduled research, redundant ingest, centralized logs,
versioned datasets, secure credentials, disaster recovery, execution
failover planning.

### 16. Agentic traders

**Purpose:** Agents that use the programs, hold a bankroll slice, create
and manage bots through Vital, and report by email and text.
**Timing:** Final major layer.
**Depends-on:** Programs 1–15 mature enough to consume honestly.
**Out:** Skipping the ladder. Browser submit. Invented fills. Unbounded
capital. Starting here because it is exciting.

Ladder: research agent → paper trader → simulated capital → limited live
capital → autonomous. Hard risk limits and kill switch.

Each agent: id, bankroll allocation, risk limits, allowed markets,
allowed programs, research access, trading permissions, bot permissions,
decision history, performance, expected performance, drawdown, kill.

Report: trades created/exited, positions, PNL, expected PNL, risk,
errors, unusual behavior, rationale/provenance, bot state.

---

## Priority board

| # | Program | Timing |
| --- | --- | --- |
| 1 | Vital | Now |
| 2 | ROLLER completion | Now |
| 3 | Polymarket 1m | Before Oct 1 |
| 4 | Kalshi + Poly + PBP intersection | After #3 is trustworthy |
| 5 | Autoingest + Autojest | Before / around Oct 1 |
| 6 | ROLLER 1m realism audit | High priority |
| 7 | SuperASI A/B correction | High priority |
| 8 | Correlation Programming | After clean ROLLER / SuperASI |
| 9 | ITI Robust Optimized | After corrected A/B |
| 10 | Terminito X / Y / MCS | After data foundation |
| 11 | Terminito Z | After X / Y |
| 12 | Terminito Fluctuations | After Terminito foundation |
| 13 | Relative Value HFT | After dual-market PIT |
| 14 | Long-term hold EV | Later research track |
| 15 | Cloud Momento | After interfaces stabilize |
| 16 | Agentic traders | Final major layer |

---

## Related

- `research/warehouse_refactor/PLAN.md` — NBA warehouse 0–20 (complete)
- `research/warehouse_refactor/NCAAB_PLAN.md` — NCAAB desk
- `research/warehouse_refactor/MLB_PLAN.md` — MLB desk
- `.cursor/rules/14-warehouse-refactor.mdc`
- `.cursor/rules/16-vital.mdc`
- `.cursor/rules/17-momento-roadmap.mdc`
- `ROLLER/docs/DATA_LINEAGE.md`
- `docs/research/architecture-decisions/ADR-0021-continuous-ingestion-plane.md`
- `AGENTS.md`
