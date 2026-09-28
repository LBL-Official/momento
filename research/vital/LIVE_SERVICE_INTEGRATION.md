# Vital Live-Service Integration Proof

Dated: 2026-09-16.

This is the control-plane acceptance suite. It is not MLB 001 Phase 6
(one-row-per-market trades in `BOT_001_PHASE6.md`). It does not start
W9, warehouse Phase 21, or a second execution engine.

```text
RUNNING  ≠  HEALTHY  ≠  EXECUTING
DESIRED  ≠  WRITTEN  ≠  OBSERVED  ≠  LOADED
```

Vital sits above the existing worker. It does not replace it.

```text
                    VITAL
              control plane
                    │
             desired state
                    │
             ┌──────▼──────┐
             │    AWS      │
             │ runtime     │
             └──────┬──────┘
                    │
          momento-live.service
                    │
          momento-trading-engine
                    │
              strategies/mlb
                    │
                  Risk
                    │
              Kalshi Create V2
```

Do not move `apps/trading-engine`, `strategies/mlb`, `config/live.toml`,
or `deploy/momento-live.service`.

---

## Suites

```text
A. PRODUCTION READ PROOF
   Vital → SSM → momento-live.service → runtime evidence

B. DEMO CONTROL PROOF
   Vital → write → systemd → demo service
   Vital → observe resulting state
   Never stop momento-live.service to prove this.

C. DEMO STRATEGY PROOF
   Vital → strategy → demo runtime → signal → Risk → DEMO submit

D. PRODUCTION STRATEGY LOAD PROOF
   Vital → versioned strategy/config
       → production runtime observes/loads it
       → Vital independently confirms
   STRATEGY_STATUS = LOADED, not LIVE, not TRADING
```

---

## Levels

| Level | What it proves |
| --- | --- |
| L1 Process | `momento-live.service` exists and is running |
| L2 Runtime | process / heartbeat / data activity continues over time |
| L3 Control | Vital can safely read and control a **demo** service |
| L4 Configuration | Vital can write a strategy / configuration (demo) |
| L5 Load | actual execution runtime loads what Vital created |
| L6 Evaluation | runtime evaluates the strategy |
| L7 Execution | strategy reaches signal → Risk → submit |
| L8 Exchange | order reaches exchange; ack / fill is observed |

L1–L7 plus a controlled DEMO L8 is enough to establish the
control / execution architecture. Production L8 is **not claimed**
by this suite. No production test order.

---

## Honesty chain

Each stage is independently evidenced:

```text
DESIRED
   ↓
WRITTEN
   ↓
OBSERVED
   ↓
LOADED
   ↓
EVALUATING
   ↓
SIGNALING
   ↓
RISK_APPROVED
   ↓
SUBMITTING
   ↓
ACKNOWLEDGED
   ↓
FILLED
```

If `SIGNALING = OBSERVATION_UNAVAILABLE`, the proof must not become
`RUNNING`. A single successful `systemctl is-active` is L1 only.

---

## Hard gate

```text
ACCEPTED ONLY IF

production service:
    process = CONFIRMED
    runtime heartbeat = CONFIRMED
    identity = CONFIRMED

Vital control:
    read = CONFIRMED
    demo write = CONFIRMED
    demo lifecycle = CONFIRMED

strategy:
    created = CONFIRMED
    persisted = CONFIRMED
    loaded_by_runtime = CONFIRMED
    evaluation = CONFIRMED

demo execution:
    signal → Risk → submit → exchange
    correlation = CONFIRMED

production:
    existing engine untouched
    existing strategy logic untouched
    no second worker
    no second execution engine
    no production test order
    L8 = NOT_CLAIMED
```

Unread stays `OBSERVATION_UNAVAILABLE`. Missing is not `$0`.
HTTP 200 is not `RUNNING`. `POST /start` is not `ENABLE_LIVE_TRADING`.

---

## API

```text
GET  /vital/bots/{id}/integration
POST /vital/bots/{id}/integration/demo-lifecycle
POST /vital/bots/{id}/integration/handshake
```

Demo lifecycle requires `VITAL_AWS_CONTROL=1` and
`confirmation=VITAL_ENABLE_CONTROL`. It refuses `mlb-001` and
`momento-live.service`.

---

## Code

```text
ROLLER/roller/vital/integration_proof.py
ROLLER/roller/vital/demo_control.py
ROLLER/tests/test_vital_live_service_integration.py
```
