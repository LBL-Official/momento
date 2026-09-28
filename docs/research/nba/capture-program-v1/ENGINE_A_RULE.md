# Engine A — intended production rule (not live)

Research specification. Identifier `ENGINE_A_NBA_80_40`.

This is **not** a live NBA strategy. Momento has no `momento-strategy-nba`
crate. Kalshi post-only entry and reduce-only IOC exist in the trading
engine for **MLB FIRST01** (80→81 maker, 50% entry-VWAP stop), which is a
**different** stop than NBA 40¢. Do not copy MLB stop semantics onto NBA
by accident.

This document freezes the **intended** NBA 80/40 rule if a later milestone
authorizes paper or live NBA execution. It does not arm trading.

---

## Rule

```text
FIRST valid 80 opportunity
        ↓
maker-only resting order at 80¢ YES
        ↓
Risk Decision Engine limits
        ↓
predefined stop logic (see below)
        ↓
hold survivors to settlement
```

No ML filter. V1–V4 did not produce one that beat hold-all under frozen
OOS and economic gates.

One logical position per game. First 80 only. Later 80 crosses are not
re-entries.

---

## Entry

- Signal: first tradable `yes_bid_close ≥ 80¢` after a prior tradable
  close `< 80¢` inside the game-day window (frozen audit definition).
- Order: post-only GTC buy YES at **80¢**. Submit ≠ fill.
- Fill is **unknown** until an exchange fill event is recorded in Engine B
  as `OBSERVED`.
- Candle `yes_bid_close ≥ 80` remains `ESTIMATED` maker-fill evidence only.

---

## Stop — research scenarios, live TBD

Candles cannot prove a 40.00 IOC fill. Until Engine B records stop fills,
two **research scenarios** stay on the scoreboard and must not be mixed:

| Scenario | Candle proxy | Frozen result | Status |
| --- | --- | --- | --- |
| Close-stop | later `yes_bid_close ≤ 40¢` | 73.98% / +0.2195 R gross | ESTIMATED path |
| Wick-stop | later `yes_bid_low ≤ 40¢` | 69.02% / +0.0707 R gross | ESTIMATED path |
| Conservative | HIGH fill confidence + wick-stop | 69.28% / +0.0784 R gross | ESTIMATED path |

A live NBA stop, if later authorized, must be specified as an **executable
order** (likely reduce-only IOC sell YES), with trigger and fill recorded
separately in Engine B (`STOP_TOUCH` vs `STOP_FILL`). Do not assume the
fill price equals 40.00. Do not assume MLB 50% VWAP is the NBA stop.

Until that specification is authorized, Engine A’s live stop is
**UNAVAILABLE**.

Candle-structure liquidation scenarios (40¢ = trigger, not fill) are in
[`FIRST80_LIQUIDATION_MODEL_V1.md`](../../ncaab/FIRST80_LIQUIDATION_MODEL_V1.md).
NBA Model B (stop-minute bid close) averages **34.13¢** (+2.86¢ EV);
Model C (bid low) **30.60¢** (+1.94¢). Gross EV crosses zero at
**23.13¢** average exit before fees. Not a live stop spec.

---

## Position and Risk (propose only)

These are research proposals. They are **not** written into the Risk
engine or live config in this milestone.

- Strategy proposes; Risk approves; execution submits. No bypass.
- One position per game.
- Maker-only entry. No taker chase of 80.
- Concurrent NBA exposure: unknown live. Audit unlimited baseline observed
  **max 8** simultaneous first-80s; cap=5 accepted 1,192 / skipped 38
  (gross +1R/−2R sim, not fills).
- Bankroll fraction for weekly-capacity research: **5% of current equity
  per trade** (see WEEKLY_CAPACITY.md). This is **not** live MLB 12.5%
  and must not be copied into `config/` or strategy code here.
- Kill switch, if NBA is ever armed, follows existing live-desk policy:
  no new entries; cancel eligible resting entries; preserve
  position-management.

---

## Hold to settlement

Survivors are held to contract settlement. No take-profit. No V3/V4
dynamic REDUCE/EXIT policy. Sequential management is blocked until
Engine B has sub-minute book and fill data.

---

## What Engine A will not do

- Select trades with a classifier
- Infer fills from candles
- Invent fees
- Submit live NBA orders
- Use presence of API keys as live enablement
