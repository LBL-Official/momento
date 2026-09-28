# BDR — Barrier Defense Router

```text
LIVE EXECUTION = FALSE
CANDLE PATH ≠ FILL
17 SYSTEMS ≠ 18
BDR = hedging_analysis write-up library on :5190
Ballhog = hedging_analysis product Frontend on :5192
```

Research library for the 80→40 barrier-defense / synthetic-exit program.

- Catalog: `research/bdr/CATALOG.json`
- Program: `docs/research/BDR_80_40_BARRIER_DEFENSE.md`
- Engineer brief: `docs/research/DUAL_LEG_MAKER_LOCK_POSITION_MANAGEMENT.md`
- Mandate: `docs/research/BDR_LIQUIDATION_CORRIDOR.md` (80 → Dynamic Exit Corridor)
- Thesis: `docs/research/BDR_ACQUISITION_CORRIDOR.md` (75 → Acquisition Corridor)
- Follow-on: `docs/research/BDR_77_RIDGE.md` (77 ridge / EV surface; `#/bdr/77-ridge`)
- Follow-on: `docs/research/BDR_STAGED_ACQUISITION.md` (77 arms / confirmation / manifold; `#/bdr/staged-acquisition`)
- API: `GET /momento/bdr`, `GET /momento/bdr/{slug}`
- UI: `http://127.0.0.1:5190/#/bdr` — dashboard of every catalog document. Click a card.

Not a new Momento system. Not a live order router. Does not change FIRST01.
