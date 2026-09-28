# DRE — Dynamic Risk Engine research library

Post-entry hold-reason research. Not Vital. Not `crates/risk`.
Not a Choosin Texas page. Not an execution policy.

```
LIVE EXECUTION = FALSE
CANDLE PATH ≠ FILL
THEORETICAL HEDGE ≠ EXECUTABLE HEDGE ≠ ECONOMICALLY BENEFICIAL HEDGE
Δ↓ ⇏ α↑
Phase 3 ≠ reduce / hedge / exit rule
asked-six 1182 ≠ derived four 936 ≠ NBA 604
```

## What we are aiming to do

Preserve demonstrated positive alpha first. Then choose the
**optimal amount of directional exposure** for the current state.
Do not blindly force delta to zero.

```
αP > 0
  ↓
observe Xt from Choosin Texas + Austin
  ↓
estimate remaining alpha
  ↓
measure current risk
  ↓
ΔP → ΔP*(Xt)
```

One sentence:

> Do not eliminate risk blindly; hold risk when compensated by
> demonstrated alpha, reduce risk when deterioration makes that
> exposure inefficient, and eliminate directional exposure when the
> marginal alpha no longer justifies the marginal risk.

SSOT: [`PORTFOLIO_OBJECTIVE_V1.md`](PORTFOLIO_OBJECTIVE_V1.md)
(9/2 DRE [R] V1). Calculus for `Λα = −dα/dt` is **not implemented**.
Do not invent that derivative.

## Forward feed

Bracket edge, not a new hop:

```
Choosin Texas  (Trade Breakdown)
      +
Austin         (Position Stratification)
      ↓
DRE            (hold reason / optimal exposure research)
```

| Upstream | System | Object today | N lock |
|---|---|---|---|
| Trade Breakdown | Choosin Texas `:5182` `/choosin-texas` | Frozen FIRST80 economics (`TradeBreakdown`) | derived four **936** |
| Position Stratification | Austin `#/austin` `/austin` | Neighborhood / stratum (`PositionStratum`) | NBA 2Q∪3Q **604** |

`/dre` wraps those two packages only. It does not query Austin,
does not rescan Choosin, does not call Vital, and does not invent
`Xt`, fills, L2, or live EV.

Missing upstream is `UNAVAILABLE`. Never `$0`.

## Current desk vs eventual engine

| Now | Not yet |
|---|---|
| Adapter + artifact viewer on `:5191` | Live `Xt` surface |
| Upstream integers from Choosin + Austin | `ΔP*(Xt)` calculator |
| Experiment reports (persistence / downfall / hazard research) | Executable hold / hedge / exit |
| `hold_reason_intact = UNKNOWN` unless an artifact says otherwise | Greek stack as production inputs |
| Phase 3 downfall language | Phase 3 as policy |

V7 and earlier DRE UIs are research artifacts, not this product.

## Surfaces

| Piece | Path |
|---|---|
| Objective SSOT | `research/dre/PORTFOLIO_OBJECTIVE_V1.md` |
| Greek stack memo | `research/dre/GREEK_STACK_V1.md` |
| How-to | `docs/operations/DRE.md` |
| Adapter | `ROLLER/roller/dre/` |
| Dashboard | `frontend/dynamic-risk-engine` `:5191` (`#/objective`) |
| API | `/dre/*` on `:8791` |
| Artifacts | `research/austin/experiments/` + `ROLLER/roller/austin/experiments/` |

## Do not

- Invent `Λα`, hazard rates, or optimal delta from this memo.
- Treat candle path as a fill or live EV.
- Promote Austin Phase 3 to a reduce / hedge / exit rule.
- Call `crates/risk` the Dynamic Risk Engine.
- Mix N=604 / 936 / 1182.
- Change live FIRST01 / 80/81/83/89, `first80.py`, `book.json`.
- Start W9 or warehouse Phase 21.
- Remount this inside `frontend/roller-terminal`.
