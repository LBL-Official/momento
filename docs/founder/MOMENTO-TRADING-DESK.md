# Momento Trading Desk

**Founder reference — algorithmic execution, architecture, and strategy**

Print this document. It is a desk briefing, not a marketing page and not a
promise that the first production order has already been accepted.

| Field | Value |
|---|---|
| Product | Momento |
| Venue | Kalshi (event contracts) |
| First sport | MLB |
| Current milestone | 10 — $50 production live MLB |
| Document date | 2026-08-24 |
| Audience | Founder / trading-desk review |

**One sentence:** Momento watches Kalshi YES bids on MLB games, proposes
maker-only entries after an 80→81 confirmation, lets Risk size and allow the
trade, then submits a signed production Create Order V2. Nothing else may
place an order.

**One caveat:** An accepted resting maker order is not a fill. Sitting on the
book waiting for a seller is expected.

---

# 1. What this desk is

Momento is a **production-grade algorithmic sports trading system**. It is
designed to trade MLB first, then NBA, NCAAB, and NFL, through Kalshi.

It is **not**:

- a discretionary click-trading UI
- a sportsbook
- a model that currently predicts game winners
- a system that chases price
- a system that invents Kalshi fees, mids, or settlement math

It **is**:

- a fail-closed execution desk
- a hierarchy: Strategy proposes → Risk approves → Execution submits →
  Position Tracker is fill-authoritative → P&L records what actually happened
- an experimental $50 MLB book with hard caps

If a trade goes wrong, the design requirement is: **you can reconstruct why**.

---

# 2. Desk charter (non-negotiables)

These are operating laws. They are encoded in types, Risk, and the live host.
Do not “temporarily” violate them to get a first fill.

1. **Never invent financial behavior.** If Kalshi docs do not specify it, code
   fails closed.
2. **Never silently change trading logic.**
3. **Never bypass the Risk Decision Engine.**
4. **Strategy never submits orders.** Only an `ApprovedTradeIntent` may reach
   Kalshi.
5. **Submit ≠ fill.** An HTTP 200 with `order_id` means the venue accepted an
   order. It does not mean you are filled.
6. **Requested exit price ≠ executable.** Liquidation hits the current YES
   bid; it does not assume the stop threshold was the fill price.
7. **No `f64` for money, prices, quantities, fees, or P&L.** Integer cents and
   dedicated domain types only.
8. **No hardcoded credentials.**
9. **Live is never the default.** Paper/replay cannot accidentally POST to
   production.
10. **Do not weaken a safety check to make a test pass.**
11. **Do not rewrite history** to make a strategy look profitable.
12. **No lookahead** in replay or backtest.
13. **Never hide errors** that affect trading state.
14. **Never silently recover** from inconsistent order/position state.
   UNKNOWN blocks new exposure until reconciliation.
15. **Prefer missing a trade over unintended exposure.**

### Live arming (all three required)

```text
mode = "live"
live.enabled = true
live.confirmation = "ENABLE_LIVE_TRADING"
```

Presence of API keys, a production hostname, AWS Secrets Manager, or
“this is the prod box” **must not** arm live by themselves.

Kill switch: block new entries, cancel eligible resting **entry** orders,
keep position-management (stop/liquidation) where appropriate, record the
event. Never silently disarm the kill switch.

---

# 3. Current experimental book

Runtime values live in `config/`, not in strategy source. Strategy must not
recompute bankroll.

| Parameter | Value | Meaning |
|---|---|---|
| Weekly snapshot | **$50.00** | Immutable for the Pacific week (Mon 00:00 America/Los_Angeles) |
| Allocation | **12.5%** (1250 bps) | Per MLB `GameId`, fee-inclusive economic budget |
| Max economic entry | **$6.25** | `$50 × 12.5%` via integer bps math |
| Positions | **1 per game** | One `PositionId` per `(StrategyId, GameId)` |
| Open cap | **5** MLB positions | Risk-enforced occupancy |
| Entry band | **80–83¢** inclusive | Maker-only YES bid join; 83 is a **ceiling**, not a target |
| Signal | **80 then same-side 81** | Qualifying price = best YES bid |
| Lock | **first YES bid ≥ 89¢** | Permanent **entry** lock. Does **not** flatten |
| Stop | **50% of entry-fill VWAP** | Observed on YES bid; exit is reduce-only IOC at best YES bid |
| Take-profit | **None** | Exits: stop path or Kalshi settlement only |
| First live order | **Must be a real 80→81** | No synthetic $0.01 / 1-contract test trade |

Liquidation proceeds are **not** recycled into that week’s entry capacity.

---

# 4. How the engine actually works

## 4.1 The only allowed control flow

```text
Kalshi production WebSocket (orderbook + private fills)
        │
        ▼
  Local in-memory YES/NO book
  best YES bid = highest YES level
  implied YES ask = $1 − best NO bid
        │
        ▼
  MarketEvent  (bid = YES bid, ask = YES ask, mid = None, last ignored)
        │
        ▼
  MLB strategy observe()
        │
        ├─ no signal ──────────────────────────────────► idle
        ├─ 89 lock ────────────────────────────────────► cancel remaining entries
        ├─ stop ───────────────────────────────────────► propose liquidation
        └─ 80→81 + maker_limit in 80–83, below ask
                    │
                    ▼
              TradeIntent
                    │
                    ▼
              Risk.decide_entry
                    │
                    ├─ reject (reason) ────────────────► log, no POST
                    └─ ApprovedTradeIntent + new ClientOrderId
                              │
                              ▼
                        live host submit_approved
                              │
                              ▼
                        KalshiVenue::submit_post_only
                        RSA-PSS signed POST
                        /trade-api/v2/portfolio/events/orders
                              │
                              ▼
                        Kalshi response
                        ack / reject / UNKNOWN
                              │
                              ▼
                        Position Tracker (fills only)
                              │
                              ▼
                        P&L (fills + fees + settlement)
                              │
                              ▼
                        Dashboard (observes; never authorizes)
```

If any box is skipped, that is a bug, not a shortcut.

## 4.2 Who is allowed to do what

| Component | May | Must not |
|---|---|---|
| Market data / book | Normalize quotes, fail closed on seq gap | Invent mid, synthesize 80/81 from stale data |
| Prediction crate | *Later:* emit a `Forecast` | Submit orders, size money, bypass 80/81 unless you explicitly redesign |
| MLB strategy | Emit `TradeIntent` / cancel / pause / stop directives | Call Kalshi, compute fees, invent quantity |
| Risk | Approve or reject; reserve budget; enforce 5-cap | Submit HTTP; mutate fills |
| Live host | Map approved intent → order; call venue | Approve its own exposure |
| Kalshi venue | Sign and POST/DELETE/GET | Create `PositionId`; treat timeout as failure |
| Position tracker | Apply fills, recon outcomes, settlement | Invent fills from submits |
| P&L | Ledger what happened | Invent mark-to-market or Kalshi fee formulas |
| Dashboard | Display and request confirmed controls | Be a trading authority |

## 4.3 Paper vs live (do not confuse them)

```text
apps/trading-engine
    ├─ PAPER host   → paper venue / no production POST
    └─ LIVE host    → ProductionTradingTransport only
                      (the path this $50 experiment uses)

crates/execution    → paper order lifecycle (Milestone 3)
                      Live production entry does NOT go through this crate.
```

**Live production entry path:**

`apps/trading-engine/src/live.rs` → `Risk.decide_entry` → `submit_approved` →
`KalshiVenue::submit_post_only`.

Paper execution in `crates/execution` is real software. It is **not** what
the armed EC2 live unit uses to create production orders.

---

# 5. Architecture of the codebase

## 5.1 Workspace map

```text
Momento/
  apps/
    trading-engine/     composition root (paper + live)
    replay-engine/      foundation only — no live venue
    sandbox-validate/   Kalshi demo checks (M8)
    prod-auth-validate/ production read-only auth (M9) — must not order
  crates/
    core/               money, IDs, intents, states, audit, venue traits
    risk/               exposure approval
    execution/          paper execution engine
    positions/          fill-authoritative tracker
    kalshi/             adapter, book, WS, signed HTTP, Create V2
    market-data/        normalization types (no 80/81 detection)
    prediction/         PLACEHOLDER — no model
    pnl/                P&L ledger from fills/fees/settlement
    sports/             sport IDs; MLB/NBA/NCAAB/NFL modules
  strategies/
    mlb/                80/81/89 + maker_limit + stop watch
    nba/ ncaab/ nfl/    stubs (boundary only)
  config/
    paper.toml          default; live gates off
    live.toml           all three live gates set
    development.toml    paper
  dashboard/            README only — not implemented
  docs/architecture/    engineer specs
  docs/founder/         this pack
```

Dependencies flow **inward** to `core`. Strategy must not depend on `kalshi`
or `execution`. Shared infrastructure (risk, venue, positions) is centralized.
Sports get their own strategy modules; they do not copy an execution engine.

## 5.2 Domain types that make the desk honest

Exact types in `crates/core`:

| Type | Representation | Example |
|---|---|---|
| `Money` | integer USD cents | `$6.25 = 625` |
| `Price` | integer contract cents, 0..=100 | `81` = 81¢ |
| `Contracts` | integer quantity | `7` |
| `Bps` | basis points | `12.5% = 1250` |
| `BasisPrice` | hundredths of a cent | `40.50¢ = 4050` (for 50% stop math) |
| `EconomicExposure` | fill **premium** in cents | fees are a separate `Fee` |

`$50 × 12.5% = $6.25` is `Money::checked_mul_bps`, not floating point.

`TradeIntent` means “I want this exposure.” It is **not** a Kalshi order.
`ApprovedTradeIntent` can only be constructed with a `RiskGrant` that only
the risk engine can mint. Execution refuses raw intents.

Every order carries: client id, market, side, price, quantity, type,
strategy id, reason, timestamp, risk decision id.

## 5.3 Identity

```text
one (StrategyId, GameId)  →  one PositionId
one approval              →  one new ClientOrderId
Kalshi order_id           →  VenueOrderId (only after venue evidence)
```

The Kalshi adapter **never** generates `PositionId`. Restart restores
strategy snapshots, tracker, risk reservations, venue id map, and
UNKNOWN client ids so the same `ClientOrderId` cannot be blindly posted twice.

## 5.4 Time

Always distinguish:

- exchange timestamp
- local receipt timestamp
- processing / submit / ack / fill timestamps

Never substitute laptop clock for exchange time without recording both.
Stale data, inverted bid/ask, or receipt-before-exchange: **no signal**.

---

# 6. MLB strategy — theory and mechanics

This is the **only live algorithm**. It is a *price-path / market-structure*
strategy, not a win-probability model.

## 6.1 The trading idea (why 80 / 81 / 83 / 89)

Kalshi MLB winner contracts are binary: YES pays $1 if that team wins.

The desk does **not** currently estimate P(win). It observes **where the
market is willing to bid YES**.

| Threshold | Role | Theory |
|---|---|---|
| **80¢ YES bid** | First trigger | The market has begun treating this side as a strong favorite. Momento records that moment (side, market, timestamps, bid/ask). A single 80 print is not enough to buy. |
| **81¢ same side, same market** | Confirmation | Requires the bid to *hold or advance* on the **same** candidate. Opposite-side 81 does not confirm and does not switch the horse. This is anti-flicker, not a second model. |
| **80–83¢ limit** | Maker entry band | Join the YES bid as a **maker**. Never take. Never rest at or through the ask. 83 is the most you will pay, not the price you aim for. **Never chase** if the bid walks above 83. |
| **>83¢** | Pause entry | Too expensive for this experiment. Pause is **not** a game lock. If price returns to 80–83 and 89 has not printed, entry may resume. |
| **89¢ YES bid** | Permanent GAME_LOCKED | The move already happened. Late entry is chasing. Lock **entry** forever for that game. **Do not liquidate because of 89.** Existing fills stay. Working entry cancels. |

**Qualifying observation is only best YES bid.** Not last trade. Not YES
ask. Not `(bid+ask)/2`. Kalshi has no official mid. Adapter `mid` stays
`None`. Ask exists on the quote solely so maker entry cannot cross.

## 6.2 Signal flowchart

```text
new quote (valid, not stale)
      │
      ├─ bid/ask missing or inverted ──────────► ignore
      ├─ WS book not ready / seq gap ──────────► no quote (fail closed)
      │
      ├─ YES bid ≥ 89¢ on relevant market ─────► GAME_LOCKED
      │                                            cancel remaining entries
      │                                            do not flatten
      │
      ├─ no first_80 yet
      │     ├─ bid < 80¢ ──────────────────────► keep watching
      │     └─ bid ≥ 80¢ ──────────────────────► record first_80
      │
      ├─ have first_80, not yet 81
      │     ├─ different side or market ───────► ignore for confirmation
      │     └─ same side ≥ 81¢ ────────────────► confirmed_81
      │
      └─ confirmed_81
            ├─ kill / UNKNOWN / working entry ─► no new Build
            ├─ maker_limit() is None ──────────► no entry
            └─ else ───────────────────────────► TradeIntent (MakerOnly,
                                                 RemainderOfApprovedBudget)
```

`maker_limit()`:

```text
limit = current YES bid
if limit not in [80, 83]  → None
if limit ≥ YES ask        → None   (never join at/through ask)
else                      → Some(limit)
```

Risk, not strategy, chooses **how many contracts** fit in remaining $6.25
after estimated fees.

## 6.3 Stop / liquidation (independent of 89)

Once there are **actual entry fills**:

1. Strategy emits `StopWatch` with VWAP of those fills (submitted size and
   unfilled limits do not count).
2. Stop threshold = **50% of that VWAP**, using integer hundredths of a cent
   (`81.00¢ → 40.50¢`). No `f64`.
3. Trigger: YES bid ≤ that threshold.
4. Host cancels remaining entries, then submits **reduce-only IOC sell YES**
   (`side=ask`, `post_only=false`, `reduce_only=true`,
   `time_in_force=immediate_or_cancel`) at the **current best YES bid**.
5. Partial liquidation retries until filled quantity is zero. UNKNOWN
   liquidation is reconciled, not blindly doubled.

89 lock **does not** fire this stop. No take-profit. No “cut it because I
feel like it.”

## 6.4 Phases (strategy state)

```text
Watching
  → First80Triggered
  → WaitingFor81Confirmation
  → EntryEligible
  → PositionBuilding     (partial fills; same PositionId)
  → PositionOpen         (remaining economic target ≈ 0)
  → GameLocked           (first 89; permanent entry lock)
```

`paused_above_max` can overlay EntryEligible when bid > 83. Persistence
(`MlbStrategy::snapshot` / restore) keeps first-80, first-89, and lock
across process restart.

## 6.5 What this strategy is *not* claiming

- It does not say “this team has 81% true win probability.”
- 81¢ is **market bid**, not a model output.
- Maker GTC can rest unfilled for a long time. That is not a broken bot.
- Edge, if any, is: *enter as maker in a confirmed high-YES region, size
  tiny, cap concentration, cut if the bid collapses vs your fill VWAP,
  never chase 89+.* Whether that edge exists in production is an empirical
  question after real fills and settlement — not something to bake into
  dashboards as “expected value.”

---

# 7. Prediction engines — placeholder and how they fit

## 7.1 Intended long-term architecture

The architecture rule (desk design, not current MLB runtime) is:

```text
Market Data
    ↓
Prediction Model Engine
    ↓
Strategy / Algorithmic Execution
    ↓
Risk Decision Engine
    ↓
Execution Engine
    ↓
Kalshi
```

**Today the Prediction box is empty.** MLB strategy consumes **quotes**, not
forecasts.

## 7.2 What exists in code

`crates/prediction`:

- crate exists so the workspace boundary is stable
- `Forecast { game_id, market_id }`
- `Forecast::unimplemented()`
- **No model. No probabilities. No `TradeIntent`.**
- Comment in source: probabilities are not money and must not be converted
  to `Price` via floating point

`crates/market-data` normalizes venue quotes. It explicitly does **not**
detect 80/81/89.

NBA / NCAAB / NFL strategy folders are stubs. They must not grow a private
execution stack.

Dashboard is not implemented. Replay engine prints a foundation message.

## 7.3 How a future model should plug in (do not implement until designed)

Correct insertion point:

```text
Kalshi book / other data sources
        ↓
  Feature pipeline (event-time only; no lookahead)
        ↓
  Model  →  Forecast { P(event), confidence, as-of exchange_ts }
        ↓
  Strategy  (still emits TradeIntent or silence)
        ↓
  Risk      (UNCHANGED — models never approve money)
        ↓
  Execution (UNCHANGED)
```

Rules for that future:

1. **A forecast is not a price.** Do not `f64` a probability into 81¢.
2. **A forecast is not an order.** Models must not call Kalshi.
3. **A forecast is not a risk override.** Even a 99% model goes through Risk.
4. **Keep fail-closed quotes.** If you still use 80/81 as a *gate*, missing
   YES bid still means no trade.
5. **Replay with as-of timestamps** so the model cannot see the final score.
6. **Audit the model version** on every `TradeIntent` (which weights, which
   snapshot of features).
7. Do not let the dashboard “click through” a model into live size.

Possible future roles for a model (product decisions, not current code):

| Role | Strategy still does | Risk still does |
|---|---|---|
| Filter | Only emit Build when model agrees with 80→81 | Caps, budget, kill |
| Sizing hint | Propose `NotMoreThan(Money)` vs full remainder | May shrink further |
| Side selection | Choose YES candidate before 80 trigger | Duplicate-game rules |
| Skip 80/81 | **Would be a new strategy** — do not silently replace MLB | Same gates unless you change config |

Until a spec exists, **do not replace 80/81 with a neural net in the live
host.** The $50 experiment is to prove *this* path, not a new one.

---

# 8. Risk — the authority over money

Risk answers: **are we allowed to take this exposure?** Strategy answers:
**do we want to propose it?**

`crates/risk` + `RiskConfig::mlb_paper_experimental()`:

- min entry 80¢, max 83¢
- 12.5% of weekly snapshot per game
- `max_open_positions = 5`

`decide_entry` (conceptual gates, in this order of intent):

```text
TradeIntent
  ├─ snapshot mismatch
  ├─ duplicate game / position identity
  ├─ kill switch tripped
  ├─ UNKNOWN / recon required          → no new exposure
  ├─ GAME_LOCKED
  ├─ paused above max price
  ├─ limit > 83 or < 80
  ├─ remaining game budget ≤ 0
     (original $6.25 − fill premium − entry fees − reservations)
  ├─ cannot size a whole contract after fees
  ├─ would open a 6th simultaneous MLB slot
  └─ else: reserve economic amount, mint ClientOrderId,
           emit ApprovedTradeIntent
```

Reservations: `used ≈ fill premium + entry fees + open reservations`.
UNKNOWN reservations stay until reconciliation. A zero-fill cancel /
NotFound can release a slot; GAME_LOCKED with open contracts still occupies
a slot.

Host also refuses Build if tracker recon is dirty, and refuses submit if
live gates are off or price > 83.

**There is no `if emergency { bypass_risk() }`.**

---

# 9. Talking to Kalshi

## 9.1 Environments

| | REST | WebSocket |
|---|---|---|
| Production | `https://external-api.kalshi.com` | `wss://external-api-ws.kalshi.com/trade-api/ws/v2` |
| Demo | demo hosts only | demo WS only |

Live unit must use **production** transport. Paper, scripted, and demo
transports exist for tests and M8. They must not be what `momento-live`
runs.

Auth: RSA-PSS SHA-256 over `timestamp + METHOD + path` (query stripped).
Headers: `KALSHI-ACCESS-KEY`, `KALSHI-ACCESS-TIMESTAMP`,
`KALSHI-ACCESS-SIGNATURE`. Credentials come from the production secret
mechanism (`MOMENTO_KALSHI_SECRET_FILE` via Secrets Manager fetch on the
box), not from git.

## 9.2 Market data (live)

- Authenticated WS: `orderbook_delta` on open MLB tickers + private `fill`
- Local book from snapshot then deltas
- Seq gap → disconnect, reconnect, resubscribe; **do not flatten**; **block
  new entry** until book is valid
- REST remains for discovery (~30s), timestamps, settlement, order recon,
  fill fallback
- Disconnect **clears** the book. The engine must not keep emitting 80/81
  from last stale quote

## 9.3 Production entry order (Create V2)

```text
POST /trade-api/v2/portfolio/events/orders

side            = bid          # buy YES
price           = 0.8000 … 0.8300
count           = N.00
time_in_force   = good_till_canceled
post_only       = true
reduce_only     = false
```

| HTTP | Meaning in Momento |
|---|---|
| 200/201 + `order_id`, fill_count = 0 | Working (may rest as maker) |
| 200/201 but immediate fill on post-only create | **Fail closed** — not treated as a resting maker |
| 400 | Rejected; release reservation; record reject |
| Timeout or 409 | **UNKNOWN** — no automatic retry |
| 401 | Auth failure — not an order reject, not a retry |

Idempotency: `client_order_id`. Duplicate POST of an already-UNKNOWN id is
refused as ambiguous.

## 9.4 Production liquidation order

```text
side            = ask
post_only       = false
reduce_only     = true
time_in_force   = immediate_or_cancel
price           = current best YES bid
```

Immediate create `fill_count` is **not** mapped into a domain fill. Fills
come from fill ingest / recon.

Amend is **not** sent. Production trading allowlist is GET `/trade-api/v2/…`,
POST create-order path, DELETE cancel path.

---

# 10. Positions, reconciliation, P&L

## 10.1 Fill authority

```text
submitted  ≠  working  ≠  filled
```

Remaining economic target = approved budget − **fill** premium − entry fees.
Never remaining = budget − submitted.

Late fills attach to the existing `PositionId` / `ClientOrderId`. Duplicate
`FillId` ignored. Cancel does not erase prior fills. Settlement is
authoritative and supplied from venue data; this crate does not invent
“$1 per YES” internally. A settled position cannot reopen.

## 10.2 UNKNOWN is a first-class state

```text
timeout / 409 / unclear transport
        ↓
    UNKNOWN
        ↓
    RECONCILE with venue
        ↓
   FOUND  /  NOT_FOUND  /  AMBIGUOUS
```

AMBIGUOUS and in-progress recon **block new exposure**. Timeout is not
NOT_FOUND and not FAILED. Blind retry is how you double a live order.

## 10.3 Position lifecycle (no take-profit)

```text
Flat → Building → OpenPartial → OpenComplete → Holding
    → StopTriggered → LiquidationActive
    → SettlementPending → Settled
```

Exit causes: `StopLoss` or `Settlement` only.

## 10.4 P&L

`crates/pnl` ledgers:

- entry cost (fill premiums)
- entry fees vs liquidation fees (separate, then summed)
- liquidation proceeds
- settlement proceeds (only if an authoritative settlement event exists)

**Realized P&L is None until** settlement or a flattening liquidation with
actual fills.

**Unrealized P&L is None** until a verified mark model exists. Do not
display `(bid+ask)/2` as P&L.

`ZeroFeeModel` / paper $0 fees are **not** Kalshi economics. Pre-trade fee
formula is still **unresolved** in official docs enough that Momento must
not invent a quadratic estimator. Fill fees, when Kalshi reports them, are
the evidence.

Never report theoretical maker P&L as realized P&L. Slippage = expected
limit vs actual fill price.

---

# 11. Audit, logs, dashboard

Required reconstructable chain:

```text
signal → risk decision → order → fill → position → exit → settlement → P&L
```

Append-only events. Do not overwrite history.

Heartbeat (live) should make these obvious: mode, live gates,
`production_auth`, market-data health, strategy/risk/recon health, unknown
order count, kill switch, open MLB slots vs cap 5, bankroll cents, per-game
cents, WS connected, books subscribed.

Dashboard (future React app, `dashboard/` stub):

- **Observability and confirmed controls only**
- Never trading authority
- Must distinguish PAPER vs LIVE in the chrome
- Show recon, kill switch, working/unknown orders, exposure vs $6.25 / 5-cap
- Destructive actions need explicit confirmation

---

# 12. Operations snapshot (how the live desk is supposed to run)

| Piece | Intended production shape |
|---|---|
| Compute | Existing live EC2 unit (paper unit must be inactive; they conflict) |
| Binary | `momento-trading-engine` with `MOMENTO_CONFIG=…/live.toml` |
| Secrets | `ExecStartPre` fetch → tmpfs secret file → process; delete on stop |
| State | Restored tracker / risk / unknown ids / strategy games |
| Kill | Kill-switch file / Risk trip; stop unit for immediate halt |
| First order proof | Natural 80→81 → POST → Kalshi ack — not a synthetic order |

If the live service is not running this binary and `live.toml`, you are not
looking at the audited desk.

---

# 13. Other sports and the rest of the platform

| Sport | Status |
|---|---|
| MLB | Live algorithm (this document) |
| NBA | Stub module + empty strategy folder |
| NCAAB | Stub |
| NFL | Stub |

Shared: core, risk, kalshi, positions, pnl. New sports add a **strategy**
and market-series mapping. They reuse Risk and venue. They do not fork
`submit_post_only`.

Replay: must be deterministic and lookahead-free. Foundation app only
today.

Milestones already done (for orientation): domain types, risk, paper
execution, Kalshi adapter, positions, MLB strategy, AWS paper deploy, demo
validation, production read-only auth. Current: live execution with
explicit arming.

---

# 14. What is proven vs what is still empirical

| Proven in source + tests + live wiring | Not proven until the world does it |
|---|---|
| WS book → YES bid → 80→81 → `maker_limit` | A real MLB tape printing that path |
| Risk budget / 5-cap / kill / UNKNOWN block | Kalshi **accepting** that first Create V2 |
| Signed POST shape to Create V2 | Kalshi **filling** the resting maker |
| Fail-closed 400 / timeout / immediate-fill | That your fill VWAP stop is economically good |
| No second live entry submit path in the host | Long-run edge after fees and settlement |

Do not estimate “percent chance it works.” The remaining uncertainty is
venue acceptance and market path, not a missing function — **provided** the
live host still matches the audited binary and config.

---

# 15. Founder review checklist (print and tick)

Use this in a weekly desk meeting.

**Control**

- [ ] Live still requires all three gates
- [ ] Paper unit cannot POST production
- [ ] Kill switch visible and not silently off
- [ ] Dashboard (when built) cannot approve exposure

**Money**

- [ ] Snapshot still $50 for this experiment (or you *consciously* recaptured)
- [ ] $6.25 / game and 5-cap still Risk-enforced
- [ ] No `f64` money in new code
- [ ] P&L still fill/settlement-based, not mark fantasy

**Strategy**

- [ ] Qualifying price still YES bid
- [ ] 80→81 same side; 89 still lock-not-flatten
- [ ] Maker 80–83, never cross ask, never chase
- [ ] No take-profit added “just for this week”
- [ ] Prediction models, if any, still cannot submit or bypass Risk

**Execution**

- [ ] Entry still post-only GTC; liquidation still reduce-only IOC
- [ ] Timeout still UNKNOWN, not auto-retry
- [ ] First production order still only from a natural 80→81

**People / process**

- [ ] Any trading-behavior change named, tested, and written down
- [ ] Unresolved Kalshi fee/mid/settlement items still not invented

---

# 16. Glossary

| Term | Meaning |
|---|---|
| YES | Kalshi contract that pays $1 if the named team/event happens |
| Maker | You add liquidity; someone else trades into you |
| Taker | You cross the spread / lift the ask |
| Post-only / `post_only` | Reject if the order would take |
| GTC | Rest until filled or cancelled |
| IOC | Immediate or cancel; remainder dies |
| Reduce-only | Cannot open/increase; only shrink a position |
| `TradeIntent` | Strategy wish |
| `ApprovedTradeIntent` | Risk-allowed wish; only this may submit |
| `ClientOrderId` | Our idempotency key, generated at approval |
| UNKNOWN | We do not know if the venue has the order |
| GAME_LOCKED | Permanent **entry** freeze after first 89¢ YES bid |
| Snapshot | Immutable weekly bankroll used for 12.5% math |
| Fill-authoritative | Positions exist from fills, not from submits |

---

# 17. Code map (if you re-open the repo)

| Topic | Path |
|---|---|
| Live loop, WS, submit | `apps/trading-engine/src/live.rs` |
| Paper vs live main | `apps/trading-engine/src/main.rs` |
| 80/81/89 + `maker_limit` | `strategies/mlb/src/quote.rs`, `strategy.rs`, `state.rs`, `stop.rs` |
| Risk | `crates/risk/src/engine.rs`, `config.rs` |
| Approval type | `crates/core/src/approval.rs`, `intent.rs` |
| Money / snapshot / stop basis | `crates/core/src/money.rs`, `snapshot.rs`, `basis.rs` |
| Book + seq gap | `crates/kalshi/src/book.rs` |
| Create V2 | `crates/kalshi/src/venue.rs`, `types.rs` |
| Sign | `crates/kalshi/src/http.rs`, `auth.rs` |
| Production allowlist | `crates/kalshi/src/production.rs` |
| Prediction stub | `crates/prediction/src/lib.rs` |
| P&L | `crates/pnl/src/lib.rs` |
| Live config | `config/live.toml` |
| Engineer specs | `docs/architecture/` |
| Simple live flowchart | `docs/architecture/live-order-path.md` |
| Unresolved (do not invent) | `docs/architecture/unresolved.md` |

---

# 18. How to read this as founder

You are not waiting on another milestone to “finish the algorithm.”

You are waiting on a **natural market path**:

```text
80  →  81  →  Risk approval  →  POST  →  Kalshi ack
```

Then, separately, a **fill**, then eventually **settlement**.

If you later add prediction models, they sit **above** strategy and **below**
market data. They do not become a second broker.

If you later add NBA, copy the *hierarchy*, not the 80/81 numbers, unless
that sport’s spec says so.

Until then: do not rewrite 80/81/89, do not raise $6.25, do not add a sixth
slot, and do not send a fake production order to feel better.

---

*End of founder desk briefing.*
