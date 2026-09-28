# TK Ultra ↔ Ballhog sibling contract

Hooking up means shared identity + optional sibling display + merge-ready
schemas. It does **not** mean `Ballhog → TK Ultra → action`.

```text
Austin 604 ──► Ballhog Austin adapter ──► Ballhog ──► BallhogHedgeIntent
Austin 604 ──► TK Ultra Austin adapter ──► TK Ultra ──► TKUltraRVAssessment
Choosin 936 ─► Ballhog Choosin adapter ─► Ballhog
Choosin 936 ─► TK Ultra Choosin adapter ─► TK Ultra
BallhogHedgeIntent ──► Position Management (NOT_IMPLEMENTED)
TKUltraRVAssessment ──► Position Management (NOT_IMPLEMENTED)
```

## What TK Ultra may read

In-process `roller.ballhog.api.handle_intent(trade_id, as_of)` only.
Contract: `ballhog.hedge_intent.v1`.

HTTP `/ballhog/intent/...` is not required. Do not add a localhost self-HTTP
loop for architectural appearance.

## What TK Ultra must not read

- `roller.ballhog.adapters.austin`
- `roller.ballhog.adapters.choosin`
- `BallhogState`
- Ballhog as evidence for relationship / route / budget math

Ballhog unavailable → `sibling_context = UNAVAILABLE`. Assessment continues.
Math is identical with or without the sibling.

## Display

Label: `SIBLING CONTEXT — NOT MODEL INPUT`.

Compact fields: intent / q* / ρ* / decision. Optional counterfactual quantity
economics may stamp `quantity_source=BALLHOG_CONTEXT` on the backend. That is
not TK’s chosen q*. Do not persist it as such.

## Do not

- Call `/momento/tk-ultra/assess` from Ballhog.
- Teach Position Management to merge intent + assessment.
- Invent fills, L2, λ, or a live order.
