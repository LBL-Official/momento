# TK Ultra V0 — ownership lock

```text
LIVE EXECUTION = FALSE
CANDLE PATH ≠ FILL
GENERIC_RV ≠ BINARY_COMPLEMENT_V0
asked-six 1182 ≠ derived four 936 ≠ NBA 604
Ballhog sibling ≠ model input
Position Management = NOT_IMPLEMENTED
NOT PROGRAM 13 RV HFT
```

TK Ultra is the Relative Value Hedging frontend (`relative_value_hedging`).
It is not an 18th or 20th system. It is not Ballhog. It is not Vital.

Named for TK. Source letter: `research/tk_ultra/SOURCE_LETTER.md`.

## Ownership

| Piece | Owner |
|---|---|
| Rich / cheap / route | TK Ultra |
| When / q* / ρ* / Δ* | Ballhog |
| Current vs target | Position Management (`NOT_IMPLEMENTED`) |
| Trade prior 80/40 | Choosin Texas (N=936, STATIC) |
| Historical query | Austin (N=604, `persist=False`) |

Siblings share identity fields. They do not share adapters. Ballhog does
not call `/momento/tk-ultra/assess`. TK Ultra does not import
`roller.ballhog.adapters` or `BallhogState`.

## Modes

- `GENERIC_RV` — `tk_relative_value_v1` futures ratio. Manual calculator.
  `GET /momento/tk-ultra/assess` unchanged.
- `BINARY_COMPLEMENT_V0` — FIRST80 A/B YES. Structural `β = -1`. Complementary
  anchors must sum to 100. `POST /momento/tk-ultra/assess`.

Do not run `(wing/base)*beta` on A/B YES.

## Surfaces

| Piece | Path |
|---|---|
| Dashboard | `frontend/momento-systems` `:5190/#/tk-ultra` |
| HTTP | `/momento/tk-ultra/*` on `:8791` |
| Domain package | `ROLLER/roller/tk_ultra/` |
| Legacy desk | `ROLLER/roller/momento/tk_ultra.py` |
| Library | `research/tk_ultra/` |

## Absolute

- Missing is `UNAVAILABLE`, never `$0`.
- Fees / slippage / depth / fill stay `UNAVAILABLE` unless a real model exists.
- Do not mix N=604 and N=936.
- Do not fabricate L2 or treat candle path as a fill.
- Do not silently normalize complementary anchors.
- Relationship RV does not auto-copy A_bid / B_ask.
- Do not edit `first80.py`, live FIRST01 / 80/81/83/89, `book.json`.
- Do not start W9 or warehouse Phase 21.
- Do not submit.
