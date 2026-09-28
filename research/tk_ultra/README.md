# TK Ultra — Relative Value Hedging frontend

```text
LIVE EXECUTION = FALSE
CANDLE PATH ≠ FILL
GENERIC_RV ≠ BINARY_COMPLEMENT_V0
TK ULTRA = relative_value_hedging frontend on :5190
```

Named TK Ultra after TK, who shared this DV relative-value formula.

- Source letter: `research/tk_ultra/SOURCE_LETTER.md` (Louie Weinhaus, 27 Aug 2026)
- Recon: `research/tk_ultra/TK_ULTRA_V0_RECON.md`
- Spec: `research/tk_ultra/TK_ULTRA_V0_SPEC.md`
- Math: `research/tk_ultra/TK_ULTRA_BINARY_RV_MATH.md`
- Data: `research/tk_ultra/TK_ULTRA_DATA_CONTRACT.md`
- Sibling: `research/tk_ultra/TK_ULTRA_BALLHOG_CONTRACT.md`
- Engine: `ROLLER/roller/momento/relative_value.py` (`GENERIC_RV`)
- Domain: `ROLLER/roller/tk_ultra/` (`BINARY_COMPLEMENT_V0`)
- Desk API: `/momento/tk-ultra/*` on `:8791`
- UI: `http://127.0.0.1:5190/#/tk-ultra`
- How-to: `docs/operations/TK_ULTRA.md`

Not an 18th system. Not a live hedge. Does not submit. Does not invent a wing
price, L2, or residual. Missing = `UNAVAILABLE`. Ballhog is an optional
sibling, not model input. Position Management is `NOT_IMPLEMENTED`. This is
not roadmap program 13 RV HFT.

BDR `#/bdr` remains the write-up library. Ballhog `:5192` owns **when**
exposure should change. TK Ultra owns **whether the hedge instrument is
cheap or rich**, and which gross route is better on paper.
