# DRE — Dynamic Risk Engine

Post-entry hold-reason research desk. Not Vital. Not crates/risk.
Not a Choosin Texas page.

```text
LIVE EXECUTION = FALSE
CANDLE PATH ≠ FILL
PRESERVE αP > 0, THEN ΔP → ΔP*(Xt)
Δ↓ ⇏ α↑
```

Aim (research, not a live rule): hold risk when compensated by
demonstrated alpha; reduce it when deterioration makes the exposure
inefficient. Do not blindly force delta to zero.

SSOT: `research/dre/PORTFOLIO_OBJECTIVE_V1.md`
Library: `research/dre/`
Desk page: `http://127.0.0.1:5191/#/objective`

Forward feed is only Choosin Texas (Trade Breakdown, N=936) and
Austin (Position Stratification, N=604). `/dre` wraps those two
packages. Missing is `UNAVAILABLE`, never `$0`. Do not invent `Λα`.

```text
browser :5191
  → ROLLER research API :8791
  → /dre
    → /dre/health
    → /dre/upstream/trade-breakdown   (Choosin Texas universe integers)
    → /dre/upstream/stratum           (Austin N=604)
    → /dre/experiments
    → /dre/experiments/{id}
```

HTTP 200 is not a fill. Hold reason intact stays UNKNOWN unless an
artifact says otherwise. Phase 3 is not an execution policy.

## Surfaces

| Piece | Path / port |
|---|---|
| Dashboard | `frontend/dynamic-risk-engine` `:5191` |
| Objective | `:5191/#/objective` |
| API | `ROLLER/scripts/terminal_api.py` `:8791` `/dre/*` |
| Inspect | `ROLLER/roller/dre/` |
| Library | `research/dre/` |
| Artifacts | `ROLLER/roller/austin/experiments/` |

Austin query stays on Choosin Texas `#/austin`. Choosin `#/austin/risk`
is a pointer to this desk.

## Run

```text
python3 ROLLER/scripts/terminal_api.py
cd frontend/dynamic-risk-engine && npm run dev
```

Open `http://127.0.0.1:5191/`.

## Do not

- Remount the shell inside `frontend/roller-terminal`.
- Call `/vital`, `/jump/bots`, or invent fills.
- Treat Phase 3 downfall as a reduce/exit rule.
- Mix N=604 / 936 / 1182.
- Promote `frontend/dre-v2` … `dre-v7` into the product UI.
- Change live FIRST01 / 80/81/83/89.
- Start W9 or warehouse Phase 21.
