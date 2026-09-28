# MLB Bot 001 — Phase 2 Isolated Folder Foundation

Dated: 2026-09-14.

Phase 1 ACCEPTED. This file is Phase 2.

```text
PHASE 2  isolated folder + identity + naming
PHASE 3  backend control plane     see BOT_001_PHASE3.md
PHASE 4  worker contract           see BOT_001_PHASE4.md
PHASE 5  pipeline facts            see BOT_001_PHASE5.md
```

No crate move. No second worker. No trade reconstruction. No RDS.
No `VITAL_AWS_CONTROL`. No SuperASI migration.

## What was added

| Path | Role |
| --- | --- |
| `ROLLER/roller/vital/mlb_001/` | Isolated Python package for Bot 001 only |
| `ROLLER/roller/vital/mlb_001/identity.py` | Canonical identity / factory / host pointers |
| `ROLLER/roller/vital/mlb_001/boundary.py` | Folder tree + pointer map (`moved=false`) |
| `ROLLER/roller/vital/naming.py` | `{sport}-{nnn}` convention for 001, 002, … |
| `ROLLER/roller/vital/versions.py` | Re-exports Bot 001 tokens (compat) |
| `research/vital/bots/mlb-001/docs/` | Bot-local ownership + boundary |
| `research/vital/bots/mlb-001/pointers/boundary.json` | Machine-readable map |
| `research/vital/BOT_STANDARD.md` | Naming lock |
| `ROLLER/tests/test_vital_bot_001_phase2.py` | Isolation tests |

Disk tree now includes `docs/` and `pointers/` on every seed
(`store.py` `TREE_DIRS`).

## Identity

```text
bot_id     mlb-001
alias      mlb-bot-one
package    roller.vital.mlb_001
folder     research/vital/bots/mlb-001
```

Vital `get_bot("mlb-001")` and `get_bot("mlb-bot-one")` resolve to the
same record. `mlb-002` is `BOT_NOT_FOUND`. `mlb` is not a bot id.

## Naming

```text
mlb-001 → MLB Bot 001 → roller.vital.mlb_001 → research/vital/bots/mlb-001
mlb-002 → MLB Bot 002 → roller.vital.mlb_002 → research/vital/bots/mlb-002
```

Bot 002 is not a child of the Bot 001 folder.

## Pointers (not copies)

```text
worker     apps/trading-engine
strategy   strategies/mlb
config     config/live.toml
deployment deploy/momento-live.service
frontend   frontend/vital-terminal
api        /vital/bots/mlb-001
backend    ROLLER/roller/vital
```

Phase 1 CONFLICT stands: execution today remains
`momento-live.service`. Phase 2 does not relocate it.

## Acceptance checklist

- [x] Isolated folder exists (`research/vital/bots/mlb-001/` + package)
- [x] Identity is canonical (`mlb-001` / `mlb-bot-one`)
- [x] Naming convention established (`BOT_STANDARD.md`)
- [x] Ownership explicit (bot-local `docs/OWNERSHIP.md`)
- [x] No accidental coupling to another bot (`mlb-002` not found / not nested)
- [x] Vital identifies Bot 001 independently
- [x] Engine and strategy not copied
- [x] No production submit path added

## STOP

```text
PHASE 2
ISOLATED FOLDER COMPLETE
        ↓
ACCEPT / REJECT
        ↓
STOP
```

Operator authorized Phases 3–5 on 2026-09-14 without a separate
Phase 2 ACCEPT record. Phase 2 isolation still holds.

Phase 6 trade row: `research/vital/BOT_001_PHASE6.md`.
Do not move `apps/trading-engine` or `strategies/mlb`.
