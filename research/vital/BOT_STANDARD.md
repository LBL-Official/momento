# Vital Bot Standard — naming and isolation

Dated: 2026-09-14. Phase 2 naming lock. Phases 3–5 implemented 2026-09-14.

```text
ONE BOT  =  ONE FOLDER  =  ONE PACKAGE
```

Bot 001 is the first implementation. Bot 002 must not live inside
`mlb-001` and must not reuse a miscellaneous `mlb/` dump.

## bot_id

```text
{sport}-{nnn}
```

Examples: `mlb-001`, `mlb-002`, `nba-001`.

Rules:

- sport is lowercase `[a-z][a-z0-9]+`
- ordinal is exactly three digits, `>= 001`
- `mlb`, `nba`, `vital`, `jump` are **not** bot ids (sport dumps)

Grandfathered alias (Bot 001 only): `mlb-bot-one` → `mlb-001`.

## Display

```text
{SPORT} Bot {NNN}
```

`mlb-001` → `MLB Bot 001`.

## Locations

| Kind | Path |
| --- | --- |
| Disk folder | `research/vital/bots/{bot_id}/` |
| Isolated Python package | `ROLLER/roller/vital/{sport}_{nnn}/` |
| Shared control plane | `ROLLER/roller/vital/` |
| Shared dashboard | `frontend/vital-terminal` |
| API | `/vital/bots/{bot_id}` |

`ROLLER/roller/vital/bots.py` is the registry module. It is **not** a
bot folder. Isolated packages must not be named `roller.vital.bots`.

## Forbidden

- Copying `apps/trading-engine` or `strategies/mlb` into a bot folder
- A second worker that submits to Kalshi
- Putting Bot 002 files under `research/vital/bots/mlb-001/`
- Using `strategies/mlb` as the Vital bot identity

Worker and strategy stay **pointers** until a later accepted phase
moves them. Phase 1 CONFLICT stands: execution today is
`momento-live.service`.

## Owner-authorized exception: `nba-001` (2026-09-26)

NBA Bot 001 has its own worker, `momento-nba-001.service`
(`/usr/local/bin/momento-nba-001`, crates `apps/nba-001` +
`strategies/nba`, state `/var/lib/momento/nba-001`). It is not a second
submitter: this build links no submission adapter and its Kalshi
transport sends GET only. The worker does not import `strategies/mlb`
or the MLB 41/42→40 logic and does not touch `momento-live.service`.

Its desk is `#/execution/nba` on `:5190` (`/momento/execution/nba/*`),
not `/vital/bots/nba-001`, and it has no isolated
`ROLLER/roller/vital/nba_001/` package. The disk folder stays
`research/vital/bots/nba-001/`.

The repository now contains an NBA order adapter usable only against
fixtures and the Kalshi demo (production orders compiled out). The
deployed build does not contain it. Deploying an adapter build to the
production host, or compiling production orders in, is not covered by
this exception. It needs a resolved execution contract
(`strategy/execution_contract.json`), verified routing and funds, and
explicit owner approval.

## Control plane (Phase 3)

Every Vital bot exposes `/vital/bots/{bot_id}` surfaces:

```text
status, configuration, strategy, positions, orders,
risk, heartbeat, logs, events, controls
```

Plus `plane`, `boundary`, `worker` (Phase 4), `pipeline` (Phase 5).

Frontend does not own trading logic. `POST /commands` is fail-closed.
`POST /start` ≠ `ENABLE_LIVE_TRADING`.

## Worker (Phase 4)

Canonical runtime is `momento-live.service` →
`/usr/local/bin/momento-trading-engine`. Vital-down is valid. Do not
create a Jump worker or a second submitter.

## Pipeline (Phase 5)

```text
Kalshi WS → strategies/mlb → crates/risk → live.rs submit_approved
  → Kalshi Create V2 → fill
```

Do not retune 80/81/83/89. Do not invent fills. Fill ≠ trade.

## Trades (Phase 6)

```text
ONE ROW  =  ONE CONFIRMED MARKET
Host Position wins. Confirmed Kalshi ticker is the fallback.
```

`JUMP_CATALOG` fills without a ticker stay observation only. Do not
group them. Do not invent CLOSED / PnL from sparse Kalshi rows.
Missing bankroll or an open trade → `UNAVAILABLE`, never `$0` / `0%`.

Optional read-only Kalshi observe: `POST /vital/bots/{id}/kalshi/observe`.
It reuses Jump `sync_kalshi`. It does not submit. Dashboard GET does
not pull.
