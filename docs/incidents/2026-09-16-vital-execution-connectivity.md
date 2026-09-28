# Vital Execution Connectivity — 2026-09-16

```text
VITAL EXECUTION CONNECTIVITY
        RESOLVED

AWS HOST
        PASS

momento-live.service
        RUNNING

MLB 001
        RUNNING

VITAL HOST OBSERVATION
        FUNCTIONAL

VITAL CONTROL
        CONTROL_DISABLED
        (correct until explicitly armed)

TRADING LOGIC
        UNCHANGED

RISK
        UNCHANGED

KALSHI SUBMIT
        UNCHANGED

REMAINING / REPAIRED
        Shared :8791 API could be blocked by long-running
        ROLLER warehouse execution. Warehouse compile/execute
        now run as sync threadpool handlers so /vital/* and
        /health stay on the event loop.
```

## What was not true

Moving MLB 001 “to Vital” did not stop the production worker. There is
no second Vital engine. Execution remained:

```text
momento-live.service
  → /usr/local/bin/momento-trading-engine
  → strategies/mlb → crates/risk → Kalshi Create V2
```

Vital owns the management boundary (identity, AWS observe, fail-closed
control, ledger). Jump reads Vital. Jump does not talk to the host.

## Independent host proof (read-only SSM)

| Fact | Value |
| --- | --- |
| Instance | `i-0f0849d5829476c31` |
| Service | `momento-live.service` |
| State | active / running |
| PID | `1101134` |
| Started | 2026-09-16 20:00:11 UTC |
| Live armed | yes |
| Kill | not tripped |

Dashboard `UNREAD` during this window was **not** host-down. A
`POST /warehouse-research/execute` ran as `async def` with blocking
research on the asyncio loop, so `/vital/*` and `/health` could not
answer.

## Repair

- Warehouse compile/execute are ordinary `def` handlers (threadpool).
- `/research-query/execute` already returned 202; unchanged.
- Test: `ROLLER/tests/test_vital_api_isolation.py`
- No MLB 001 / Risk / Kalshi submit change.
- `VITAL_AWS_CONTROL` stays unset unless an operator arms it.

## Lock

```text
Research can become slow.
Execution observability cannot become unavailable because research is slow.
```
