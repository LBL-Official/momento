# TK Ultra — Relative Value Hedging

Research desk. Not Vital. Not Ballhog. Not a 20th system.

```text
LIVE EXECUTION = FALSE
CANDLE PATH ≠ FILL
GENERIC_RV ≠ BINARY_COMPLEMENT_V0
```

TK Ultra answers whether the hedge instrument is cheap or rich, and which
gross route is better on paper. Ballhog answers when / how much. Position
Management is `NOT_IMPLEMENTED`.

Library: `research/tk_ultra/`
Spec: `research/tk_ultra/TK_ULTRA_V0_SPEC.md`

```text
browser :5190/#/tk-ultra
  → ROLLER research API :8791
  → /momento/tk-ultra
    → GET  /momento/tk-ultra
    → GET  /momento/tk-ultra/assess          (GENERIC_RV)
    → GET  /momento/tk-ultra/health
    → GET  /momento/tk-ultra/sources
    → GET  /momento/tk-ultra/positions
    → GET  /momento/tk-ultra/state/{trade_id}
    → POST /momento/tk-ultra/assess          (BINARY_COMPLEMENT_V0)
    → GET  /momento/tk-ultra/ballhog-context/{trade_id}
```

HTTP 200 is not a fill. `execution_enabled` is false. Live feed
`UNAVAILABLE`. Missing is `UNAVAILABLE`, never `$0`.

The manual calculator is `GENERIC_RV` (`tk_relative_value_v1`, NQ/ES letter
ticks −247.92). FIRST80 A/B YES uses `BINARY_COMPLEMENT_V0`. Do not run
`(wing/base)*beta` on complementary YES contracts.

## Surfaces

| Piece | Path / port |
|---|---|
| Dashboard | `frontend/momento-systems` `:5190/#/tk-ultra` |
| API | `ROLLER/scripts/terminal_api.py` `:8791` `/momento/tk-ultra/*` |
| Domain | `ROLLER/roller/tk_ultra/` |
| Legacy desk | `ROLLER/roller/momento/tk_ultra.py` |
| Ballhog sibling | `:5192` (optional, in-process `handle_intent`) |
| BDR library | `:5190/#/bdr` |

## Run

```text
python3 ROLLER/scripts/terminal_api.py
cd frontend/momento-systems && npm run dev
```

Open `http://127.0.0.1:5190/#/tk-ultra`.

## Do not

- Remount the shell inside `frontend/roller-terminal` or Choosin Texas.
- Restyle as Ballhog.
- Recompute expected B, residual, route edge, or runway in React.
- Call TK Ultra from Ballhog as an upstream.
- Invent fills, L2, or zero missing fees.
- Mix N=604 / 936 / 1182.
- Treat this as program 13 RV HFT.
- Change live FIRST01 / 80/81/83/89.
- Start W9 or warehouse Phase 21.
- Submit.
