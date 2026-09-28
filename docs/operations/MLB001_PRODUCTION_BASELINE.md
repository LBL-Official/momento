# MLB 001 production baseline

Frozen 2026-09-17. This is the recover-from artifact, not the
2026-09-13 binary and not the 2026-09-16 recon-only binary.

```text
09-13 production behavior
        +
09-16 fill-ingest fix
        +
09-16 reconciliation fix
        +
09-17 leftover-fill ignore
        +
09-17 automated desk housekeeping
        ↓
current factory bot
        =
PRODUCTION BASELINE
```

Jump/Vital did not take over execution. They observe
`momento-live.service`. Browser does not submit.

## Identity

| Field | Value |
|---|---|
| Service | `momento-live.service` |
| Host | `i-0f0849d5829476c31` |
| Region | `us-east-1` |
| Execution | factory engine (`apps/trading-engine` + `strategies/mlb` + Risk) |
| Status | live-armed |
| Reconciliation | Healthy |
| Order submission | enabled |
| SHA-256 | `66ca5420273779b6706e873c4a6640ef4fd603dd0bb02e9d044ee18077c2f3fd` |
| Artifact | `s3://momento-paper-artifacts-895492487332/m10/mlb-001-production-baseline/momento-trading-engine` |
| Machine record | [`deploy/mlb001-production-baseline.json`](../../deploy/mlb001-production-baseline.json) |

Strategy unchanged: 80 → 81, maker 80–83, lock 89, cap 5, Create V2.

Quiet while no 80→81 is correct. Do not restart, retune, or clear
persist to “make it trade.”

## Not this object

`s3://…/m10/momento-trading-engine` SHA `fb939b62…` is the 2026-09-03
binary that traded on 2026-09-13. It predates fill-ingest and recon.
Keep it as history. Do not recover from it.

`8dd481e3…` is the 2026-09-16 recon baseline. It predates leftover
ignore. Host backup: `momento-trading-engine.8dd481e3.bak`.

## Three protections

**1. Process recovery.** systemd `Restart=always`, `RestartSec=5`,
`StartLimitIntervalSec=300`, `StartLimitBurst=10`,
`RestartPreventExitStatus=78`. Crash restarts the process. Exit 78
(preflight fail-closed) stays down. Start ≠ armed ≠ submit.

**2. State recovery.** Every heartbeat runs `run_desk_housekeeping`
inside `momento-live.service` (no second writer): reconcile unknowns
→ adopt occupancy (drop known reservations on Settled; keep UNKNOWN)
→ refresh held → ingest fills (skip already-complete orders; leftover
rows `DuplicateIgnored`) → sync working orders →
`finish_housekeeping_gates` → `housekeeping_ok`. Ambiguous clears
only if no live uncertainty. No force-Healthy path. No auto-flatten.

**3. Binary recovery.** Install this SHA from the baseline prefix onto
an ARM64 host. Verify `file` + digest. Atomic rename. Restart the
existing unit. Require last `housekeeping_ok recon=Healthy
order_submission=enabled unknown=false` + same SHA. Else leave
trading blocked and restore the previous `.bak`.

```text
new ARM64 host
      ↓
install exact known-good artifact
      ↓
start momento-live.service
      ↓
housekeeping
      ↓
Healthy → trade when 80→81 exists
```

No Mac cross-compile. No guessing which binary was live.

Recover:

```text
deploy/mlb001-recover-baseline.sh
```

New code still builds on a throwaway ARM64 Amazon Linux host
(`docs/operations/MLB001_ARM64_DEPLOY.md`). After a new SHA is
observed Healthy, freeze it here and replace the baseline prefix.
Do not overwrite `m10/momento-trading-engine` (`fb939b62…`).
