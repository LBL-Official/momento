# VOLATILITY NORMALIZATION FAILS AS A RECOVERY MECHANISM

**QUIET DOES NOT MEAN REVERSION**

```
H2 OPENING ADVERSE-DELTA NORMALIZATION

RESULT: NEGATIVE

An adverse price movement exceeding a contract's
own first-half volatility regime does not demonstrate
a systematic temporary component.

Volatility normalization does not predict price recovery.
The contract frequently remains at its newly repriced level.

Restricting the event to bounded score deterioration,
proportional margin changes, or the first qualifying
shock does not rescue the hypothesis.

The apparent unconditional +0.14¢ R5 is economically
small, dispersion-heavy, and reverses OOS.

NO ENTRY RULE AUTHORIZED
NO FADE RULE AUTHORIZED
NO NORMALIZATION-BUY RULE AUTHORIZED

CLOSE_5 = DESCRIPTIVE OBSERVATION
CLOSE_5 ≠ AUTHORIZED CONDITION
CLOSE_5 → REQUIRES INDEPENDENT REPLICATION

DO NOT HUNT A PROFITABLE SUBSET

LIVE EXECUTION = FALSE
```

This is a clean negative. It answers the hypothesis rather than
failing to find a profitable threshold.

## Rejected causal chain

```
abnormal adverse price shock
  → temporary dislocation
  → volatility normalization
  → price recovery
```

Broken at multiple points (candle path, not fills):

1. Vol does not preferentially normalize after the shock
   (45.6% < 53.6% ordinary adverse).
2. Unconditional R5 +0.14¢ vs control +0.00¢ is trivial
   (sd 8.5¢, median 0) and reverses OOS.
3. Object C is the wrong sign:
   vol_norm R5 = −0.50¢; elevated-vol R5 = +0.69¢.
   The mechanism predicted the reverse.

## Frozen interpretation

**QUIET TAPE = NEW PRICE ACCEPTANCE**

The abnormal adverse delta appears to incorporate information.
When subsequent volatility subsides, the market does not
mechanically return toward the pre-shock price; it appears to
stabilize around the newly repriced probability.

Continued movement ≠ reversion. The positive R5 in the
still-volatile group is continued path dynamics, not
normalization bounce.

Score filters make the result stronger, not weaker:

```
ALL PRIMARY SHOCKS                  +0.14¢ R5
1–4 PT DETERIORATION                −0.06¢ R5
+ 25–50% PROPORTIONAL DETERIORATION −0.49¢ R5
FIRST SHOCK IN GAME                 −0.45¢ R5
```

The more specifically the original theoretical event is
approximated, the less evidence there is for recovery.

Tables: `REPORT.md`. Object definition: `SPEC.md`.
