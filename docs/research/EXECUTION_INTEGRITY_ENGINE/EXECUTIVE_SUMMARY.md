# EIE + DRE_BASELINE_V1 — executive summary

Research only. **LIVE_EXECUTION_CHANGED = False.**

Universe `A1_UNIVERSE_V1` · A1 hash `d7d2e9e55d9a426a` · EIE hash `049d8ba4efe1816d`.

## The law

```text
L1 observed state     ≠  L2 observable opportunity
L2 opportunity        ≠  L3 modeled execution
L3 modeled execution  ≠  L4 actual execution
```

A gap-through (`23→75`) is L2 `THRESHOLD_CROSSING` + `GAP_THROUGH`.
It is **not** an E1 fill at 40.

## Answers

**Q1 — Payoff structure (E1, H=40 exact).**  
Hedge only when the first post-entry A2 close **occupies** 40. Otherwise 80→40. Path classes and contributions are in `PAYOFF_STRUCTURE.md`.

**Q2 — Expectancy by evidence level (FULL, ¢/trade).**

| Layer | NBA | NCAAB P5 | Strength |
|---|---:|---:|---|
| L1 hold (settlement only) | 2.8455 | 3.3564 | Observed resolution |
| L3 fallback 80→40 | 4.3902 | 4.3551 | Model A stop |
| L3 E1 conservative | 4.3252 | 4.1331 | Modeled, not actual |
| L3 theoretical @40 | 5.1707 | 4.3551 | Illegal promotion |
| L4 actual | NOT_AVAILABLE | NOT_AVAILABLE | None |

**Q3 — Where EV comes from.** See decomposition. Do not treat V1’s extra EV as hedge alpha.

**Q4 — Sensitivity.** E2 q/partial interpolates E1 toward 80→40. E3/E4 unavailable.

**Q5 — Edge that disappears upward.** NBA theoretical − E1 = gap fiction (0.845528¢). That increment is L2 crossings promoted to fills.

**Q6 — Robust enough for deterioration calculus?** **80→40 (fallback) is the robust causal book.** E1 at H=40 does not beat it. Do not differentiate a fictional V1 lock. L4 does not exist yet.

Do not implement A2 hedging in FIRST01 from this layer.
