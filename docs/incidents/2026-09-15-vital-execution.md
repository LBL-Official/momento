# Vital Execution Incident Report

Dated: 2026-09-16 (America/Los_Angeles 2026-09-15 evening).

Read-only host proof on `i-0f0849d5829476c31`. No production restart. No
`VITAL_AWS_CONTROL`. Trading logic unchanged.

## MLB 001

STATUS:
**BLOCKED — RISK CAP FULL ON FIVE STALE PENDING SLOTS**

Today (America/Los_Angeles 2026-09-15, journal since 2026-09-15 07:00 UTC)
the factory path **did** see valid 80→81 books and **did** emit `Build`.
No limit order reached Kalshi. Create V2 was never called.

Not: bot down. Not: no 80→81 today. Not: Vital rewrote 80/81.

The earlier line “HEALTHY — NO QUALIFYING FILL / NO SIGNAL” is **wrong
for today**. It used a late 16/20 book sample and treated
`open_desk_positions=0` as an empty cap. That field is tracker fills.
Risk occupancy is `open_slots`, and it was **5 all day**.

Vital ownership did **not** stop or replace the factory unit. The same
`momento-live.service` PID has been running since **2026-09-03 08:13:16 UTC**,
before Vital ownership docs (2026-09-13). Engine pointer remains
`apps/trading-engine`. `moved: false`.

## Failure Location

```text
AWS           confirmed (process alive)
→ systemd     active, 0 restarts
→ process     /usr/local/bin/momento-trading-engine PID 442826
→ market data healthy (96,687 MLB YES bid updates since 2026-09-13)
→ strategy    mlb_strategy=active; last sampled book 16/20, not 80→81
→ Risk        healthy now (0 open desk slots, kill Armed/not_tripped)
              848 PositionLimitExceeded since 2026-09-13 (cap=5 desk)
              while fills that day occupied slots — expected then
→ Kalshi      no submit_refused; last confirmed fills 2026-09-13
→ Vital       observe gap: local VITAL_BOT_STATE_DIR unset
```

Exact layer for “valid bets today, no limit orders”:

```text
market data   26,452 MLB YES bid updates today
              1,368 ≥80; 1,205 ≥81; 594 in 80–83 below ask
strategy      audit First80Observed 14 / First81Confirmed 13 after 07:00Z
              (12 MLB first-80, 11 MLB confirm-81, 2 WNBA)
              Build reached Risk (436 decide_entry; 29 entry_gate=resumed)
Risk          PositionLimitExceeded × 436; 0 other reject reasons
              heartbeat open_desk_positions=0  (15,646)
              heartbeat open_slots=5           (15,646)
submit        0 submit_to_ack; 0 submit_refused
Kalshi        last tracker fill still 2026-09-13T00:10:56Z
```

Not: bot down. Not: wrong Kalshi env. Not: missing secret. Not: Vital
rewrote 80/81. Not: “no qualifying signal today.”

## Root Cause

Supported by evidence only:

1. The factory bot is the **same live process** that traded on 2026-09-13
   (HOU@TB 81¢, LAD@MIA 82¢, CIN@MIL 82¢). Vital added a management
   folder and pointers. It did not move the binary or change
   `deploy/momento-live.service`.
2. Current heartbeat: `mode=Live`, `production_auth=true`,
   `market_data=healthy`, `order_submission=enabled`,
   `open_desk_positions=0`, `unknown_orders=0`, `kill_switch=not_tripped`.
3. A late book sample `…MIAAZ-MIA bid=16 ask=20` is not the day. Today
   printed 594 YES bids in 80–83 below the ask. First-80 then confirm-81
   fired on CLE, LAD, DET, MIL, NYY, SF, ATL, KC, SD, BAL, MIA, LAA
   (and two WNBA books). Several of those first-80 prints were already
   above 83 (pause, then resume if the book returned to 80–83).
4. `open_desk_positions=0` is **not** an empty Risk cap. Risk persist
   has `pending_new_slots=5` and `reservations=5`. Heartbeat
   `open_slots=5` for every sample today. Cap is 5. Every `Build` today
   was `PositionLimitExceeded`. `adopt_fill_authoritative_occupancy`
   will not drop a pending slot unless the tracker position is Settled
   or has `filled_quantity>0`. These five are still `Building` / 0 fill.
5. The five reservations are **old entry orders**, not today’s games:

   | local Working entry | ticker | limit |
   | --- | --- | --- |
   | client `…7337` | `KXMLBGAME-26SEP131410CINMIL-MIL` | 82¢ |
   | client `…2132` | `KXMLBGAME-26SEP111915PHIATL-PHI` | 80¢ |
   | client `…5977` | `KXMLBGAME-26SEP121915CWSSTL-STL` | 81¢ |
   | client `…3945` | `KXMLBGAME-26SEP041915DETCLEG2-CLE` | 83¢ |
   | client `…7279` | `KXMLBGAME-26SEP051915AZHOU-HOU` | 81¢ |

   `occupancy_sync n=11` all day. Kalshi `get_order` returns **Filled
   filled=7** for those Working rows (`occupancy_held_venue_filled` ×
   172,117). The occupancy path **must not invent a fill** from order
   status. `ingest_fills` is `GET …/fills?limit=100` with no cursor;
   `fill_applied` today = **0**. Tracker last fill remains 2026-09-13.
   Six additional Working rows are liquidations on already-Settled
   positions; they are not the five pending slots.
6. Risk is rejecting as specified for a full desk. The desk is full of
   **stale pending reservations**, not five live tracker fills. Do not
   lower the cap. Do not invent fills. Recon of those five venue-filled
   orders is required before a new Create V2 is legal.
6. Vital execution `observed.json` said `host state path unset` because
   `VITAL_BOT_STATE_DIR` is unset locally. SSM inspect already saw
   `/var/lib/momento/state/live-runtime.json`. That is an
   **OBSERVABILITY** defect, not an execution stop.

## Evidence

- Host inspect 2026-09-16: unit active, user `momento`, cwd `/var/lib/momento`,
  `MOMENTO_KALSHI_ENV=production` on the running PID, secret **path present**
  (`/dev/shm/momento-kalshi-live.json`), `KILL` file absent.
- Host `live.toml`: `mode=live`, `enabled=true`, `ENABLE_LIVE_TRADING`,
  not `research_iti`, min/preferred 80, max 83.
- Binary `/usr/local/bin/momento-trading-engine` sha256
  `fb939b622483553a5cb7d9c066944c5ec0065290d2eae9d478e71f078e9e00f8`
  (6,003,472 bytes). Not a symlink.
- Journal since 2026-09-13: 54,647 heartbeats; 0 `submit_refused`;
  0 auth/TLS/DNS marks in the compact inspect window.
- Ledger last fills: 2026-09-13. Disk Kalshi book 2026-09-16T04:49:13Z:
  production `fill_n=107`, `position_n=0`, top-level 3931¢.
- Pre/post-Vital: repo unit/config match the running host env **names**
  and paths. Identity-only diffs (Vital folder, `bot.json`) are not an
  execution break.

## Repair

- Execution observe: if SSM/inspect confirms `live-runtime.json` exists,
  host **presence** is `CONFIRMED`. Fill **body** stays
  `OBSERVATION_UNAVAILABLE` until `VITAL_BOT_STATE_DIR` is set. Missing
  is never `[]` / `$0`.
- ITI worker label: binary is `momento-trading-engine-demo`, not the
  factory name.
- Version token `vital_v1.1.2`.
- Incident tests in `ROLLER/tests/test_vital_execution_incident.py`.

## Trading Logic Changes

**NONE**

## Demo Bots

All five are isolated `research_iti` units on `momento-demo@{id}.service`.
`MOMENTO_KALSHI_ENV=demo`. `live.enabled=false`. Not factory 80/81.
Demo engine binary exists (not a symlink; **different** sha256 from the
factory binary: `06bafb9ce974cabcb9cd088ec530477cb69f271aa846ba08beff23946d8ad0ee`).
`open_slots=0` is idle occupancy, not a block.

| BOT | ENVIRONMENT | RUNTIME | MARKET DATA | STRATEGY | RISK | ORDER ATTEMPT | KALSHI RESPONSE | VITAL OBSERVATION |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mlb-002 | DEMO | `momento-demo@mlb-002` active since 2026-09-15 20:34 UTC | `demo_heartbeat` NBA `KXNBAGAME` games=3 | ITI 65 / Q4 NBA | Armed, open_slots=0 | none in last 60 lines | Demo book fill_n=0 | RUNNING_DEMO |
| mlb-003 | DEMO | active 20:34 UTC | NBA games=3 | ITI 65 / Q4 NBA | Armed, 0 | none | fill_n=0 | RUNNING_DEMO |
| mlb-004 | DEMO | active 20:34 UTC | NBA games=3 | ITI 65 / Q4 NBA | Armed, 0 | none | fill_n=0 | RUNNING_DEMO |
| mlb-005 | DEMO | active 20:34 UTC | MLB `KXMLBGAME` games=54 | ITI 20 | Armed, open_slots=1 | none in last 60 | fill_n=0 | RUNNING_DEMO |
| atp-001 | DEMO | active 22:06 UTC | ATP `KXATPMATCH` games=1 | ITI 65 | Armed, 0 | none | fill_n=0 | RUNNING_DEMO |

Demo shm secret file was present for `atp-001` at inspect time; other units
had `MOMENTO_KALSHI_SECRET_FILE` in the process env (path present to the
process) even if the tmpfs file had already been rotated.

## End-to-End Demo Result

```text
KALSHI DEMO CREATE V2        FAIL
VITAL BOT EXECUTION PATH     NOT PROVEN
ITI BOT QUALIFYING SIGNAL    NOT REQUIRED
FACTORY 80/81 DEMO           NOT EXPECTED
```

Authorized M8 fixture `apps/sandbox-validate` (2026-09-16), demo secret
`momento/kalshi/demo` (environment tag `demo`; credential present; path
valid; then deleted):

- host `https://external-api.demo.kalshi.co`
- REST balance HTTP 200, 2000¢
- WS connected
- **STEP 9 — FAILED:** Create V2 `unexpected HTTP 404` `not_found`
- cancel not reached
- production origin refused by the fixture
- binary exit 0 (fixture reports the reject; it does not treat 404 as a
  successful ack)

Do **not** “fix” this by changing Create V2, adding `exchange_index`, or
turning ITI bots into factory 80/81. That is a STOP condition.

## Production Result

MLB 001 today (LA 2026-09-15):

- runtime: confirmed healthy (same PID since 2026-09-03)
- strategy: **80→81 fired**; Build reached Risk
- Risk: **cap full** — `open_slots=5` on five stale pending entries
  (Sep 4–13). Tracker fills on those five = 0. Kalshi `get_order`
  reports Filled/7. 436 `PositionLimitExceeded`. Cap not lowered.
- order path: enabled; **0 Create V2** (`submit_to_ack=0`); last
  applied fill 2026-09-13
- next legal step: recon those five venue-filled entries through the
  existing fill ingest / settlement path. Do not invent fills. Do not
  restart production. Do not change 80/81/83/89.

## Tests

`ROLLER/.venv/bin/python -m pytest` on:

`test_vital_execution_incident.py`
`test_vital_execution.py`
`test_vital_observe.py`
`test_vital_aws.py`
`test_vital_ownership.py`
`test_vital_bot_001_phase2.py`
`test_vital_jump_handoff.py`
`test_vital_control.py`

**71 passed.**

`cargo` was not required for the observe/label repair (Python only).
`momento-sandbox-validate` was run against Kalshi DEMO (see End-to-End).
