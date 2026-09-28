# Base Terminal Efficiency

**Empirical measurement layer. Not an ML model. Not XIB. Not a strategy.**

```text
XIB / MCD Terminal Efficiency V1     Base Terminal Efficiency (this document)
apps/terminal-efficiency             ROLLER/roller/base_terminal_efficiency
frozen 2024–25 predictive object     NBA 2025–26 observation panel
DO NOT MODIFY                        research measurement only
```

Base TE answers:

> Given an observed entry state, how had the game and market traveled to that point, which WIN/LOSS exit occurred first afterward, and how did the Kalshi contract settle?

It does not predict, score alpha, estimate edge, optimize EV, train, or execute.

---

## What it is

A point-in-time observation panel plus a per-ticker path store from which empirical conditional counts can be calculated.

```text
BASE TERMINAL EFFICIENCY

             ENTRY
               │
       ┌───────┴────────┐
       │                │
    GAME STATE       MARKET STATE
       │                │
       ├─ score         ├─ entry price (yes_bid_close)
       ├─ differential  ├─ price volatility
       ├─ score path    └─ price path
       ├─ score vol
       └─ scoring
             │
             ↓
       SUBSEQUENT PATH
             │
       ┌─────┴─────┐
       ↓           ↓
      WIN         LOSS
       │           │
       └─────┬─────┘
             ↓
        TERMINAL
         YES / NO / MISSING
```

## What it is not

- An ML / XGBoost / LightGBM / neural model
- XIB or MCD (those remain in `apps/terminal-efficiency`)
- A prediction, probability, alpha, or edge
- A fill or execution
- Frozen FIRST80
- A generic-query `PathOp`
- Live trading / Risk / FIRST01 / W9 / Phase 7
- Spread, O/U, team total, Polymarket TOB, L2, or ticks (those are `DATA_REQUIRED`)

---

## Entry-state families

| Family | What is stored | Notes |
|--------|----------------|--------|
| Score level | team / opponent / total points, differential | Last I(t)-visible PBP |
| Score path | increment list to entry | `0→10→20` ≠ `0→5→20` |
| Score volatility | `SCORE_PATH_VOLATILITY_V1` | UNAVAILABLE if &lt; 3 increments — never 0 |
| Market level | `yes_bid_close` integer E4 | Not a probability. Not a fill |
| Market path | K_0, displacement, travel, range | Travel ≠ displacement ≠ range |
| Market volatility | `MARKET_PRICE_VOLATILITY_V1` | UNAVAILABLE if &lt; 3 bars — never 0 |

## WIN / LOSS

Independent books. Evaluated as **query parameters** against the path store — not baked in as WIN 90 / LOSS 40.

- Exit timestamp strictly after entry. Entry bar cannot satisfy an exit.
- First subsequent exit wins.
- Exact same timestamp → `AMBIGUOUS` (`TIE_EXACT_TIMESTAMP`). Not generic-query minute `TIE_EXCLUDED`.
- Invalid side (WIN below entry, LOSS above entry) → `INVALID_SEMANTICS`. Not flipped.
- Game-clock book without PBP → `DATA_REQUIRED` / `UNAVAILABLE`. Not Reach-only relabeled.
- Hold-to-expiration is **Kalshi settlement**, not a candle path and not `HORIZON_WIN_E4`.

## Terminal settlement

`YES` / `NO` / `TERMINAL_MISSING` from `kalshi_markets` only. NBA file is currently absent → missing, not NO. No box-score inference.

## PIT contract

```text
available_at < observation_ts     (ROLLER I(t), half-open)
```

Then `snap_events` may use `event_timestamp <= observation_ts` on the **already filtered** list. Terminal and future bars never enter entry-state.

## Versioning

`SEMANTICS_VERSION = 1.0.0` · `SCHEMA_VERSION = 1.0.0` · `CODE_VERSION = base_te_v1.0.0`

Derived tree: `ROLLER/data/nba/2025_2026/derived/base_terminal_efficiency/1.0.0/`

Stale / corrupt / checksum-invalid → `DATA_REQUIRED`.

## Current coverage

NBA 2025–26 ROLLER candles + PBP. Kalshi markets not canonicalized. See [RECON.md](RECON.md) and [DATA_CONTRACT.md](DATA_CONTRACT.md).

```text
python -m roller.base_terminal_efficiency.cli build --league NBA --season 2025-2026
```

## Explicit non-goals

ML, SHAP, feature importance, predicted probability, alpha, EV, Kelly, Sharpe, fills, fees, slippage, L2, ticks, Phase 7, five-screen UI changes, fabricating spread/O-U/team totals.
