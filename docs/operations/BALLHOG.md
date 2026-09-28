# Ballhog — Hedging Analysis / exposure-removal optimizer

Research desk. Not Vital. Not `crates/risk`. Not a Choosin Texas page.
Not a 20th system.

```text
LIVE EXECUTION = FALSE
CANDLE PATH ≠ FILL
Austin a_t is not Ballhog alpha
THEORETICAL ≠ EXECUTABLE
```

Ballhog decides WHEN / q\* / ρ\* / Δ\* from Austin (N=604) and Choosin
Texas (N=936). Risk intent is independent of hedge feasibility.
`BEGIN_REDUCTION` + `NO_ADMISSIBLE_HEDGE` + `q*=0` means risk-off is
indicated, but no modeled 35–45 hedge preserves robust portfolio EV.
TK Ultra expresses that q\* economically. BDR `#/bdr` stays the
write-up library.

Library: `research/ballhog/`
Policy: `research/ballhog/policy/v1.yaml`

```text
browser :5192
  → ROLLER research API :8791
  → /ballhog
    → /ballhog/health
    → /ballhog/sources
    → /ballhog/positions
    → /ballhog/state/{trade_id}?as_of=&q_dir=
    → POST /ballhog/surface|frontier|decision|transitions
    → /ballhog/intent/{trade_id}
```

HTTP 200 is not a fill. `execution_enabled` is false. Live feed
`UNAVAILABLE`. Dual-leg lock `L(p)=20−p` is theoretical on every paired
unit.

The desk auto-loads Austin trade `f84fd059fc0e1429` at the replay-path
midpoint (`default_as_of`, UX only). Changing position uses that row's
stamp; it does not reuse the previous trade's `as_of`. `q_dir` is an
integer (`max_q_dir` from YAML, default 1).

## Surfaces

| Piece | Path / port |
|---|---|
| Dashboard | `frontend/ballhog` `:5192` |
| API | `ROLLER/scripts/terminal_api.py` `:8791` `/ballhog/*` |
| Inspect | `ROLLER/roller/ballhog/` |
| Library | `research/ballhog/` |
| TK Ultra sibling | `:5190/#/tk-ultra` |
| BDR library | `:5190/#/bdr` |

## Run

```text
python3 ROLLER/scripts/terminal_api.py
cd frontend/ballhog && npm run dev
```

Open `http://127.0.0.1:5192/`.

## Do not

- Remount the shell inside `frontend/roller-terminal` or Choosin Texas.
- Call `/vital`, `/momento/tk-ultra/assess`, or invent fills.
- Invent λ, Λα, L2, or BUY NO taker.
- Mix N=604 / 936 / 1182.
- Treat 35–45 as a live A2 trigger.
- Change live FIRST01 / 80/81/83/89.
- Start W9 or warehouse Phase 21.
