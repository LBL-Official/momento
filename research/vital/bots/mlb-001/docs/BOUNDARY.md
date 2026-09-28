# MLB Bot 001 — isolated boundary

Package: `roller.vital.mlb_001`
Folder: `research/vital/bots/mlb-001`

```text
metadata/     identity
source/       fingerprints (pointers, moved=false)
config/       live.toml pointer
deployment/   momento-live.service pointer
runtime/      desired / observed / confirmed
logs/         local observe
events/       append-only
execution/    fills / trades ledger
docs/         this ownership boundary
pointers/     boundary.json
```

Frontend: `frontend/vital-terminal` `#/bots/mlb-001`
API: `/vital/bots/mlb-001`

No second engine. No RDS invented. No trade reconstruction in Phase 2.
