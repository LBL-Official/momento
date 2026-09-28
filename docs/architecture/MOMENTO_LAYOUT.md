# Momento layout

Dated: 2026-09-16. Current facts. Not a rewrite. Not a second roadmap.

Canonical program tracker:
[`MOMENTO_SYSTEMS_ROADMAP.md`](MOMENTO_SYSTEMS_ROADMAP.md).
Vital ownership: [`research/vital/OWNERSHIP.md`](../../research/vital/OWNERSHIP.md).
Live observatory how-to: [`research/vital/LIVE_SERVICE_DESK.md`](../../research/vital/LIVE_SERVICE_DESK.md).

```text
WATCHING MLB  ≠  SIGNAL  ≠  SUBMIT  ≠  FILL
DESIRED       ≠  OBSERVED ≠  CONFIRMED
HTTP 200      ≠  RUNNING  ≠  HEALTHY EXECUTION
open_mlb_positions = 0    ≠  empty Risk cap
```

## Surfaces

| Surface | Port / unit | Role |
|---|---|---|
| ROLLER | `:5179` | Measure. Research questions, warehouse desk, Confirm & Run (still CSV). |
| SuperASI | same Vite as ROLLER | A Base → B Debase → Final → ITI. Research only. Not a live Kalshi signal. |
| Jump | same Vite as ROLLER | Operating terminal. Vital client. Does **not** SSM Bot One. |
| Vital | `:5180` | MLB 001 owner. Observe + fail-closed control. Live desk at `#/live`. |
| Systimo | `:5193` | System Maintenance Frontend. Connection registry. Not LS. API `/systimo` on `:8791`. |
| Momento LS | `:5181` | Direct observe of `momento-live.service`. Not Vital. API `:8792`. |
| Autojest | not built | Autoingest dashboard later. Not Jump. Not Vital. |

```text
ROLLER :5179     measure (research)
SUPERASI         A → B → Final → ITI  (research, not live signal)
JUMP             terminal; Vital client; does not SSM Bot One
VITAL :5180      MLB 001 owner; observe + fail-closed control
SYSTIMO :5193    System Maintenance Frontend; registers tunnels
MOMENTO LS :5181 direct observe of momento-live.service (API :8792)
LIVE UNIT        i-0f0849d5829476c31 · momento-live.service
ENGINE           apps/trading-engine · strategies/mlb · crates/risk
BASELINE SHA     66ca5420273779b6706e873c4a6640ef4fd603dd0bb02e9d044ee18077c2f3fd
                 (09-13 behavior + 09-16 fill-ingest + 09-16 recon
                  + 09-17 leftover ignore + housekeeping.
                  Not fb939b62. See docs/operations/MLB001_PRODUCTION_BASELINE.md)
KALSHI           Create V2 only after Risk
ITI DEMOS        momento-demo@{id}
```

## Execution path (factory)

```text
Kalshi WS
  → strategies/mlb (80 → 81, max 83, lock 89)
  → crates/risk
  → apps/trading-engine live.rs submit_approved
  → Kalshi Create V2
```

Vital does not submit. Browser does not submit. Jump does not submit.

Triple live gate: `mode=live` AND `live.enabled=true` AND
`confirmation=ENABLE_LIVE_TRADING`. Start ≠ live arm. Kill ≠ flatten.

## Momento LS observe path

```text
Momento LS :5181
  → /observe on :8792
  → read-only SSM
  → i-0f0849d5829476c31
  → momento-live.service
```

Not Vital. Not `/vital/*`. Does not submit. Does not set
`VITAL_AWS_CONTROL`. How-to: [`docs/operations/MOMENTO_LS.md`](../operations/MOMENTO_LS.md).

## Vital observe path

```text
Vital / Jump
  → observe_bot
  → inspect_mlb_001 (local ledger, else read-only SSM)
  → i-0f0849d5829476c31
  → momento-live.service
  → /var/lib/momento/state/live-runtime.json
```

Proof of talk: `observed.source=ssm`, matching `instance_id` /
`momento-live.service`, fresh `observed_at` (≤300s). Missing stamp is
`OBSERVATION_UNAVAILABLE`, not leftover `RUNNING`.

Control writes require `VITAL_AWS_CONTROL=1` and
`confirmation=VITAL_ENABLE_CONTROL`. Default unset.

## Bots on disk (2026-09-16)

| bot_id | Kind | Host unit | Notes |
|---|---|---|---|
| mlb-001 | grandfathered factory | `momento-live.service` | Production 80/81 |
| mlb-002 | ITI | `momento-demo@mlb-002` | NBA ITI, not factory MLB |
| mlb-003 | ITI | `momento-demo@mlb-003` | NBA ITI |
| mlb-004 | ITI | `momento-demo@mlb-004` | NBA ITI |
| mlb-005 | ITI | `momento-demo@mlb-005` | MLB Demo ITI 20/85/40 |

`momento-demo@mlb-001` must stay inactive.

## Incidents (do not collapse)

- **A** — ghost occupancy / Ambiguous recon / fill ingest.
  [`docs/incidents/2026-09-15-vital-execution.md`](../incidents/2026-09-15-vital-execution.md)
- **B** — Vital observe path / freshness.
  [`docs/incidents/2026-09-16-vital-mlb-001-connectivity.md`](../incidents/2026-09-16-vital-mlb-001-connectivity.md)

`open_slots=5` with `open_mlb_positions=0` is Incident A occupancy.
`reconciliation=Ambiguous` blocks new entries even when `open_slots=0`.

## Do not

- Start warehouse Phase 21, Confirm & Run cutover, or W9.
- Change live FIRST01 / 80/81/83/89.
- Remount Vital or Momento LS inside `frontend/roller-terminal`.
- Move `apps/trading-engine` or `strategies/mlb`.
- Treat candle path as a fill. Missing is never `$0`.
