# Momento Live Bot 001 — Live Ledger Schema & State-Machine Specification V1

Status: **IMPLEMENTATION SPEC — READY FOR REPOSITORY REVIEW**
Strategy: `MOMENTO_FIRST78_LIVE_V1`
Bot: `nba-001` / Live Bot 001
Execution authorization: **OFF until readiness gate passes**
Primary markets: `KXNBA`, `KXNCAAB`

---

# 1. Purpose

This document freezes the data model and deterministic state machines for the first production version of Momento's live NBA/NCAAB FIRST78 strategy.

The system must make every future trade reconstructable without manual historical reconstruction.

After 20, 50, 100, and 200 completed trades, Momento must be able to answer:

- What was the true live net EV per initial contract?
- How much edge was lost to fees?
- How much edge was lost to entry execution?
- How much edge was lost to exit execution?
- What percentage of trades required adverse exits?
- What was the mean adverse exit-equivalent price?
- How many opportunities were missed?
- How many entries were blocked because eligibility could not be proven?
- How much capital was deployed?
- Which sizing epoch applied to each trade?
- Did the bot ever exceed policy constraints?
- Did live realized EV remain near the +1.5¢ planning assumption?
- Did the first 50 completed trades produce at least $1,000 net profit / $21,000 ending bankroll?
- Was mean adverse exit-equivalent price at least 50¢?

Midpoints create strategy signals.
Orders create intent.
Fills create positions.
Settlements and executed exits create P&L.

Never substitute one for another.

---

# 2. Frozen Strategy Policy

## 2.1 Authorized entry markets

- NBA: `KXNBA`
- NCAAB: `KXNCAAB`

## 2.2 Authorized entry windows

### NBA

Only the third quarter:

`period == 3`

### NCAAB

Only the first ten minutes of the second half:

`period == 2`

and:

`600 <= clock_seconds <= 1200`

using the normalized sports-state clock.

## 2.3 FIRST78 rule

Observe both mutually exclusive winner contracts from game start.

For each contract:

`mid = (best_bid + best_ask) / 2`

The first in-game occurrence of either side reaching or exceeding 78¢ is authoritative.

If either side first reaches 78¢ before the authorized entry window, the game is permanently ineligible.

A later return to 78¢ does not restore eligibility.

## 2.4 Entry ladder

At valid FIRST78:

`BUY selected YES @ 0.78 POST_ONLY`

Allowed maker ladder:

`78, 79, 80, 81, 82`

Maximum entry price:

`82¢`

If selected midpoint reaches or exceeds 86¢ with zero filled entry quantity:

- cancel all entry orders,
- classify as `MISSED_ENTRY`,
- never re-enter that event.

## 2.5 Position sizing

Starting bankroll:

`$20,000`

Initial-position budget:

`6% of active sizing-epoch bankroll`

The 6% budget includes entry fees.

Never permit:

`filled premium + filled entry fees + worst-case cost of open entry orders > trade_budget`

## 2.6 Daily trade cap

Maximum initiated positions:

`8`

combined across NBA and NCAAB per trading day.

The capacity reservation must be atomic.

## 2.7 Sizing epochs

Ten completed, fully reconciled trades create:

`RESIZE_PENDING = TRUE`

Sizing does not change immediately.

Automatic sizing updates may occur only:

`01:00 <= local time < 03:00`

timezone:

`America/Los_Angeles`

Until the next successful resize commit, later trades continue using the prior sizing epoch.

A sizing epoch may therefore contain more than ten trades.

## 2.8 Exit trigger and hedge logic

If holding Team A YES, Team B YES is the candidate complementary hedge.

Before hedge functionality is permitted, contract metadata must prove that the pair is mutually exclusive and exhaustive under identical settlement semantics.

Trigger:

`opponent_mid >= 0.36`

At trigger:

`BUY opponent YES @ 0.35 POST_ONLY`

Target hedge quantity:

`current_unhedged_original_qty`

### Recovery branch

If opponent price falls after the 36¢ trigger, the passive hedge may ratchet downward:

`35 -> 34 -> 33 -> ... -> 25`

This is the recovery hedge ladder.

### Adverse branch

If opponent price rises after the 36¢ trigger while the passive hedge remains incomplete:

- cancel stale passive hedge,
- transition to emergency direct exit of remaining unhedged original quantity.

Do not chase the hedge downward while the opponent is becoming more expensive.

### 25¢ recovery boundary

If opponent midpoint falls to 25¢ and the complementary hedge remains incomplete:

- cancel remaining hedge orders,
- directly exit remaining original exposure using the authorized taker-capable fallback.

## 2.9 Partial hedge invariant

`hedge_target_qty = original_open_qty - already_matched_hedge_qty`

Never hedge more than remaining unhedged original quantity.

## 2.10 Exit-equivalent price

Direct original exit at price `x`:

`exit_equivalent = x`

Complementary hedge purchase at price `h`:

`gross_exit_equivalent = 1 - h`

Fee-adjusted complementary exit:

`net_exit_equivalent = 1 - h - hedge_fee_per_contract`

Primary quality target:

`mean gross adverse exit-equivalent >= 0.50`

Also record net exit-equivalent independently.

---

# 3. Data Storage Principles

Use an append-only event journal plus normalized current-state tables.

The event journal is the audit source.

Current-state tables are projections derived from authoritative events.

Required properties:

- deterministic replay,
- idempotency,
- crash recovery,
- exchange reconciliation,
- immutable fill records,
- immutable settlement records,
- policy versioning,
- sizing-epoch versioning,
- provider timestamps,
- exchange timestamps,
- receive timestamps,
- no reliance on frontend state.

Recommended SQL backend:

PostgreSQL for production.

SQLite may be used only for deterministic unit/replay fixtures, not as the assumed production authority if existing Momento infrastructure already uses another canonical database.

Use integer cents / integer half-cents where practical rather than binary floating point.

Use `NUMERIC`/decimal for monetary values.

All wall-clock timestamps should be UTC.

All local maintenance-window calculations use `America/Los_Angeles`.

---

# 4. Canonical Enumerations

## trade_state

- `WATCHING`
- `INELIGIBLE_PRIOR78`
- `ENTRY_SIGNALLED`
- `ENTRY_WORKING`
- `PARTIAL_ENTRY`
- `POSITION_OPEN`
- `MISSED_ENTRY`
- `HEDGE_TRIGGERED`
- `HEDGE_WORKING`
- `PARTIAL_HEDGE`
- `RECOVERY_HEDGE`
- `EMERGENCY_DIRECT_EXIT`
- `DIRECT_EXIT_WORKING`
- `SETTLEMENT_PENDING`
- `RECONCILIATION_REQUIRED`
- `COMPLETED`
- `ABORTED`

## eligibility_status

- `UNKNOWN`
- `ELIGIBLE`
- `INELIGIBLE_PRIOR78`
- `INELIGIBLE_WINDOW`
- `INELIGIBLE_DATA_GAP`
- `INELIGIBLE_EVENT_MAPPING`
- `INELIGIBLE_DAILY_CAP`
- `INELIGIBLE_OTHER`

## order_leg

- `ENTRY`
- `HEDGE`
- `DIRECT_EXIT`

## liquidity_role

- `MAKER`
- `TAKER`
- `UNKNOWN`

## provider_status

- `HEALTHY`
- `DEGRADED`
- `STALE`
- `DOWN`
- `AMBIGUOUS`

## reconciliation_status

- `PENDING`
- `MATCHED`
- `MISMATCH`
- `RESOLVED`
- `MANUAL_REVIEW`

## execution_mode

- `REPLAY`
- `SIMULATION`
- `PAPER`
- `SHADOW_LIVE`
- `CANARY_LIVE`
- `LIVE`

---

# 5. SQL-Like Schema

The repository implementation may use SQLAlchemy, SQLModel, Django ORM, raw SQL, Rust SQL bindings, or the project's existing canonical persistence layer, but the logical schema below must be preserved.

## 5.1 `strategy_policy_versions`

```sql
CREATE TABLE strategy_policy_versions (
    policy_version              TEXT PRIMARY KEY,
    strategy_id                 TEXT NOT NULL,
    created_at                  TIMESTAMPTZ NOT NULL,
    config_hash                 TEXT NOT NULL,
    execution_authorized        BOOLEAN NOT NULL DEFAULT FALSE,

    nba_entry_period            SMALLINT NOT NULL DEFAULT 3,
    ncaab_entry_period          SMALLINT NOT NULL DEFAULT 2,
    ncaab_clock_max_s           INTEGER NOT NULL DEFAULT 1200,
    ncaab_clock_min_s           INTEGER NOT NULL DEFAULT 600,

    first78_threshold_cents     NUMERIC(6,3) NOT NULL DEFAULT 78.000,
    entry_max_cents             NUMERIC(6,3) NOT NULL DEFAULT 82.000,
    missed_entry_mid_cents      NUMERIC(6,3) NOT NULL DEFAULT 86.000,

    hedge_trigger_cents         NUMERIC(6,3) NOT NULL DEFAULT 36.000,
    hedge_initial_bid_cents     NUMERIC(6,3) NOT NULL DEFAULT 35.000,
    recovery_floor_cents        NUMERIC(6,3) NOT NULL DEFAULT 25.000,

    allocation_pct              NUMERIC(8,6) NOT NULL DEFAULT 0.060000,
    max_daily_trades            INTEGER NOT NULL DEFAULT 8,

    resize_min_completed_trades INTEGER NOT NULL DEFAULT 10,
    resize_timezone             TEXT NOT NULL DEFAULT 'America/Los_Angeles',
    resize_window_start         TIME NOT NULL DEFAULT '01:00:00',
    resize_window_end           TIME NOT NULL DEFAULT '03:00:00',

    modeled_net_ev_cents        NUMERIC(8,4) NOT NULL DEFAULT 1.5000,
    target_50_trade_bankroll    NUMERIC(14,2) NOT NULL DEFAULT 21000.00,
    target_50_trade_profit      NUMERIC(14,2) NOT NULL DEFAULT 1000.00,
    target_50_trade_return_pct  NUMERIC(8,4) NOT NULL DEFAULT 5.0000,
    target_adverse_exit_cents   NUMERIC(8,4) NOT NULL DEFAULT 50.0000
);
```

---

## 5.2 `sports_events`

```sql
CREATE TABLE sports_events (
    momento_event_id            TEXT PRIMARY KEY,
    sport                       TEXT NOT NULL,
    game_date                   DATE NOT NULL,

    home_team                   TEXT NOT NULL,
    away_team                   TEXT NOT NULL,

    kalshi_event_id             TEXT,
    espn_event_id               TEXT,

    scheduled_start_utc         TIMESTAMPTZ,

    mapping_status              TEXT NOT NULL,
    mapping_method              TEXT,
    mapping_verified            BOOLEAN NOT NULL DEFAULT FALSE,
    mapping_created_at          TIMESTAMPTZ,

    first_observation_at        TIMESTAMPTZ,
    last_observation_at         TIMESTAMPTZ,

    created_at                  TIMESTAMPTZ NOT NULL,
    updated_at                  TIMESTAMPTZ NOT NULL
);
```

Unique constraints should prevent one ESPN event from mapping to multiple active Momento events and one Kalshi event from mapping ambiguously.

---

## 5.3 `market_contracts`

```sql
CREATE TABLE market_contracts (
    contract_id                 TEXT PRIMARY KEY,
    momento_event_id            TEXT NOT NULL REFERENCES sports_events(momento_event_id),

    exchange                    TEXT NOT NULL DEFAULT 'KALSHI',
    series                      TEXT NOT NULL,
    ticker                      TEXT NOT NULL UNIQUE,

    team                        TEXT NOT NULL,
    side                        TEXT NOT NULL DEFAULT 'YES',

    complement_contract_id      TEXT,
    complement_verified         BOOLEAN NOT NULL DEFAULT FALSE,
    complement_verification_at  TIMESTAMPTZ,

    settlement_rule_hash        TEXT,
    created_at                  TIMESTAMPTZ NOT NULL
);
```

---

## 5.4 `sports_state_observations`

Append-only.

```sql
CREATE TABLE sports_state_observations (
    id                          BIGSERIAL PRIMARY KEY,
    momento_event_id            TEXT NOT NULL REFERENCES sports_events(momento_event_id),

    provider                    TEXT NOT NULL,
    provider_event_id           TEXT,

    game_status                 TEXT NOT NULL,
    period                      SMALLINT,
    clock_display               TEXT,
    clock_seconds               INTEGER,

    home_score                  INTEGER,
    away_score                  INTEGER,

    provider_timestamp          TIMESTAMPTZ,
    request_started_at          TIMESTAMPTZ,
    received_at                 TIMESTAMPTZ NOT NULL,

    age_ms                      INTEGER,
    provider_sequence           BIGINT,

    is_valid                    BOOLEAN NOT NULL,
    invalid_reason              TEXT,

    raw_payload_hash            TEXT
);
```

Indexes:

- `(momento_event_id, received_at DESC)`
- `(provider, received_at DESC)`

---

## 5.5 `market_quote_observations`

Persist all threshold-relevant observations and sufficient surrounding microstructure.

```sql
CREATE TABLE market_quote_observations (
    id                          BIGSERIAL PRIMARY KEY,
    contract_id                 TEXT NOT NULL REFERENCES market_contracts(contract_id),

    exchange_timestamp          TIMESTAMPTZ,
    received_at                 TIMESTAMPTZ NOT NULL,
    processed_at                TIMESTAMPTZ,

    bid_cents                   NUMERIC(8,4),
    ask_cents                   NUMERIC(8,4),
    mid_cents                   NUMERIC(8,4),
    spread_cents                NUMERIC(8,4),

    bid_size                    INTEGER,
    ask_size                    INTEGER,

    exchange_sequence           BIGINT,
    quote_age_ms                INTEGER,

    threshold_relevant          BOOLEAN NOT NULL DEFAULT FALSE,
    raw_payload_hash            TEXT
);
```

If deeper L2 data is available, store in a separate order-book snapshot table rather than bloating this row.

---

## 5.6 `event_eligibility`

One current row per event/policy version.

```sql
CREATE TABLE event_eligibility (
    momento_event_id            TEXT NOT NULL REFERENCES sports_events(momento_event_id),
    policy_version              TEXT NOT NULL REFERENCES strategy_policy_versions(policy_version),

    first78_seen                BOOLEAN NOT NULL DEFAULT FALSE,
    first78_contract_id         TEXT,
    first78_exchange_ts         TIMESTAMPTZ,
    first78_receive_ts          TIMESTAMPTZ,
    first78_mid_cents           NUMERIC(8,4),

    first78_period              SMALLINT,
    first78_clock_seconds       INTEGER,

    first78_window_valid        BOOLEAN,
    observation_history_complete BOOLEAN NOT NULL DEFAULT TRUE,

    eligibility_status          TEXT NOT NULL DEFAULT 'UNKNOWN',
    ineligibility_reason        TEXT,

    updated_at                  TIMESTAMPTZ NOT NULL,

    PRIMARY KEY (momento_event_id, policy_version)
);
```

Invariant:

Once `first78_seen = TRUE`, it may never revert to `FALSE`.

If a data gap could conceal a prior FIRST78 touch:

`observation_history_complete = FALSE`

and entry eligibility must not be granted.

---

## 5.7 `sizing_epochs`

```sql
CREATE TABLE sizing_epochs (
    sizing_epoch_id             BIGSERIAL PRIMARY KEY,
    policy_version              TEXT NOT NULL,

    epoch_number                INTEGER NOT NULL UNIQUE,

    effective_from              TIMESTAMPTZ NOT NULL,
    effective_until             TIMESTAMPTZ,

    starting_reconciled_equity  NUMERIC(14,4) NOT NULL,
    allocation_pct              NUMERIC(8,6) NOT NULL,
    trade_budget                NUMERIC(14,4) NOT NULL,

    completed_trades_at_start   INTEGER NOT NULL,
    completed_trades_in_epoch   INTEGER NOT NULL DEFAULT 0,

    resize_pending              BOOLEAN NOT NULL DEFAULT FALSE,
    resize_requested_at         TIMESTAMPTZ,

    source_reconciliation_id    BIGINT,

    committed_at                TIMESTAMPTZ NOT NULL,
    active                      BOOLEAN NOT NULL DEFAULT TRUE
);
```

Only one sizing epoch may be active.

---

## 5.8 `daily_capacity`

```sql
CREATE TABLE daily_capacity (
    trade_date_local            DATE PRIMARY KEY,
    timezone                    TEXT NOT NULL DEFAULT 'America/Los_Angeles',

    max_trades                  INTEGER NOT NULL DEFAULT 8,
    reserved_slots              INTEGER NOT NULL DEFAULT 0,
    initiated_trades            INTEGER NOT NULL DEFAULT 0,

    updated_at                  TIMESTAMPTZ NOT NULL
);
```

Capacity reservation must be transactional.

---

## 5.9 `trades`

```sql
CREATE TABLE trades (
    trade_id                    TEXT PRIMARY KEY,
    policy_version              TEXT NOT NULL,
    bot_id                      TEXT NOT NULL,
    execution_mode              TEXT NOT NULL,

    momento_event_id            TEXT NOT NULL,
    sport                       TEXT NOT NULL,
    series                      TEXT NOT NULL,

    selected_contract_id        TEXT NOT NULL,
    opponent_contract_id        TEXT NOT NULL,

    trade_state                 TEXT NOT NULL,
    eligibility_status          TEXT NOT NULL,

    signal_exchange_ts          TIMESTAMPTZ,
    signal_receive_ts           TIMESTAMPTZ,
    signal_processed_ts         TIMESTAMPTZ,

    signal_period               SMALLINT,
    signal_clock_seconds        INTEGER,

    signal_selected_bid_cents   NUMERIC(8,4),
    signal_selected_ask_cents   NUMERIC(8,4),
    signal_selected_mid_cents   NUMERIC(8,4),

    signal_opponent_bid_cents   NUMERIC(8,4),
    signal_opponent_ask_cents   NUMERIC(8,4),
    signal_opponent_mid_cents   NUMERIC(8,4),

    strategy_reference_cents    NUMERIC(8,4) NOT NULL DEFAULT 78.0000,

    sizing_epoch_id             BIGINT NOT NULL REFERENCES sizing_epochs(sizing_epoch_id),
    trade_budget                NUMERIC(14,4) NOT NULL,
    bankroll_before_trade       NUMERIC(14,4) NOT NULL,

    global_completed_trade_no   INTEGER,
    trade_no_in_sizing_epoch    INTEGER,

    initiated_at                TIMESTAMPTZ,
    completed_at                TIMESTAMPTZ,

    reconciliation_status       TEXT NOT NULL DEFAULT 'PENDING',
    reconciliation_notes        TEXT,

    created_at                  TIMESTAMPTZ NOT NULL,
    updated_at                  TIMESTAMPTZ NOT NULL
);
```

One event may produce at most one initiated FIRST78 trade for a given policy version.

---

## 5.10 `orders`

Append-only state revisions or immutable order records plus an order-event table.

```sql
CREATE TABLE orders (
    order_id                    TEXT PRIMARY KEY,
    client_order_id             TEXT NOT NULL UNIQUE,

    trade_id                    TEXT NOT NULL REFERENCES trades(trade_id),
    leg                         TEXT NOT NULL,

    contract_id                 TEXT NOT NULL,
    action                      TEXT NOT NULL,
    side                        TEXT NOT NULL,

    limit_price_cents           NUMERIC(8,4),
    requested_qty               INTEGER NOT NULL,

    post_only                   BOOLEAN NOT NULL,
    reduce_only                 BOOLEAN,

    submitted_at                TIMESTAMPTZ,
    exchange_ack_at             TIMESTAMPTZ,

    status                      TEXT NOT NULL,
    cancel_requested_at         TIMESTAMPTZ,
    cancelled_at                TIMESTAMPTZ,
    cancel_reason               TEXT,

    exchange_order_id           TEXT,

    created_at                  TIMESTAMPTZ NOT NULL,
    updated_at                  TIMESTAMPTZ NOT NULL
);
```

---

## 5.11 `order_events`

```sql
CREATE TABLE order_events (
    id                          BIGSERIAL PRIMARY KEY,
    order_id                    TEXT NOT NULL REFERENCES orders(order_id),
    trade_id                    TEXT NOT NULL REFERENCES trades(trade_id),

    event_type                  TEXT NOT NULL,
    exchange_status             TEXT,

    exchange_timestamp          TIMESTAMPTZ,
    received_at                 TIMESTAMPTZ NOT NULL,

    payload_hash                TEXT
);
```

---

## 5.12 `fills`

Immutable.

```sql
CREATE TABLE fills (
    fill_id                     TEXT PRIMARY KEY,
    exchange_fill_id            TEXT UNIQUE,

    trade_id                    TEXT NOT NULL REFERENCES trades(trade_id),
    order_id                    TEXT NOT NULL REFERENCES orders(order_id),

    contract_id                 TEXT NOT NULL,
    leg                         TEXT NOT NULL,

    fill_price_cents            NUMERIC(8,4) NOT NULL,
    fill_qty                    INTEGER NOT NULL,

    liquidity_role              TEXT NOT NULL,
    fee_amount                  NUMERIC(14,6) NOT NULL,

    exchange_timestamp          TIMESTAMPTZ,
    received_at                 TIMESTAMPTZ NOT NULL,

    created_at                  TIMESTAMPTZ NOT NULL
);
```

Never update a fill row.

Corrections must be represented as reconciliation events.

---

## 5.13 `position_snapshots`

Current projection plus periodic snapshots.

```sql
CREATE TABLE position_snapshots (
    id                          BIGSERIAL PRIMARY KEY,
    trade_id                    TEXT NOT NULL REFERENCES trades(trade_id),

    original_entry_qty          INTEGER NOT NULL,
    original_open_qty           INTEGER NOT NULL,

    entry_vwap_cents            NUMERIC(8,4),
    entry_fees_total            NUMERIC(14,6),

    hedge_filled_qty            INTEGER NOT NULL DEFAULT 0,
    hedge_vwap_cents            NUMERIC(8,4),
    hedge_fees_total            NUMERIC(14,6),

    matched_hedge_qty           INTEGER NOT NULL DEFAULT 0,
    remaining_unhedged_qty      INTEGER NOT NULL DEFAULT 0,

    direct_exit_qty             INTEGER NOT NULL DEFAULT 0,
    direct_exit_vwap_cents      NUMERIC(8,4),
    direct_exit_fees_total      NUMERIC(14,6),

    exchange_position_qty       INTEGER,
    local_position_qty          INTEGER,

    reconciliation_status       TEXT NOT NULL,

    captured_at                 TIMESTAMPTZ NOT NULL
);
```

---

## 5.14 `hedge_events`

```sql
CREATE TABLE hedge_events (
    id                          BIGSERIAL PRIMARY KEY,
    trade_id                    TEXT NOT NULL REFERENCES trades(trade_id),

    hedge_event_type            TEXT NOT NULL,

    exchange_timestamp          TIMESTAMPTZ,
    received_at                 TIMESTAMPTZ NOT NULL,

    original_bid_cents          NUMERIC(8,4),
    original_ask_cents          NUMERIC(8,4),
    original_mid_cents          NUMERIC(8,4),

    opponent_bid_cents          NUMERIC(8,4),
    opponent_ask_cents          NUMERIC(8,4),
    opponent_mid_cents          NUMERIC(8,4),

    period                      SMALLINT,
    clock_seconds               INTEGER,

    target_hedge_qty            INTEGER,
    remaining_unhedged_qty      INTEGER,

    reason                      TEXT
);
```

Event types include:

- `HEDGE_TRIGGERED`
- `RECOVERY_REPRICE`
- `ADVERSE_BRANCH`
- `RECOVERY_FLOOR_REACHED`
- `PARTIAL_HEDGE`
- `HEDGE_COMPLETE`
- `DIRECT_EXIT_REQUESTED`

---

## 5.15 `settlements`

Immutable authoritative settlement record.

```sql
CREATE TABLE settlements (
    trade_id                    TEXT PRIMARY KEY REFERENCES trades(trade_id),

    winning_contract_id         TEXT NOT NULL,
    selected_settlement_value   NUMERIC(4,2) NOT NULL,
    opponent_settlement_value   NUMERIC(4,2) NOT NULL,

    settlement_timestamp        TIMESTAMPTZ NOT NULL,
    verified_at                 TIMESTAMPTZ NOT NULL,

    source                      TEXT NOT NULL,
    raw_record_hash             TEXT
);
```

---

## 5.16 `trade_pnl`

One authoritative reconciled row per completed trade.

```sql
CREATE TABLE trade_pnl (
    trade_id                    TEXT PRIMARY KEY REFERENCES trades(trade_id),

    initial_contract_qty        INTEGER NOT NULL,

    entry_premium_total         NUMERIC(14,6) NOT NULL,
    entry_fees_total            NUMERIC(14,6) NOT NULL,

    hedge_premium_total         NUMERIC(14,6) NOT NULL DEFAULT 0,
    hedge_fees_total            NUMERIC(14,6) NOT NULL DEFAULT 0,

    direct_exit_proceeds_total  NUMERIC(14,6) NOT NULL DEFAULT 0,
    direct_exit_fees_total      NUMERIC(14,6) NOT NULL DEFAULT 0,

    settlement_proceeds_total   NUMERIC(14,6) NOT NULL DEFAULT 0,

    gross_pnl                   NUMERIC(14,6) NOT NULL,
    total_fees                  NUMERIC(14,6) NOT NULL,
    net_pnl                     NUMERIC(14,6) NOT NULL,

    gross_pnl_per_contract      NUMERIC(10,6) NOT NULL,
    net_pnl_per_contract        NUMERIC(10,6) NOT NULL,
    realized_ev_cents           NUMERIC(10,6) NOT NULL,

    entry_slippage_cents        NUMERIC(10,6),

    adverse_exit_flag           BOOLEAN NOT NULL DEFAULT FALSE,
    gross_exit_equiv_cents      NUMERIC(10,6),
    net_exit_equiv_cents        NUMERIC(10,6),

    return_on_entry_cash_pct    NUMERIC(10,6),

    bankroll_after_trade        NUMERIC(14,4) NOT NULL,

    calculated_at               TIMESTAMPTZ NOT NULL,
    reconciliation_id           BIGINT
);
```

---

## 5.17 `reconciliation_runs`

```sql
CREATE TABLE reconciliation_runs (
    reconciliation_id           BIGSERIAL PRIMARY KEY,

    run_type                    TEXT NOT NULL,
    started_at                  TIMESTAMPTZ NOT NULL,
    completed_at                TIMESTAMPTZ,

    exchange_balance            NUMERIC(14,4),
    local_balance               NUMERIC(14,4),

    exchange_open_orders        INTEGER,
    local_open_orders           INTEGER,

    exchange_positions          INTEGER,
    local_positions             INTEGER,

    status                      TEXT NOT NULL,
    discrepancy_count           INTEGER NOT NULL DEFAULT 0,

    details_json                JSONB
);
```

---

## 5.18 `system_events`

Append-only operational journal.

```sql
CREATE TABLE system_events (
    id                          BIGSERIAL PRIMARY KEY,

    event_type                  TEXT NOT NULL,
    severity                    TEXT NOT NULL,

    trade_id                    TEXT,
    momento_event_id            TEXT,

    component                   TEXT NOT NULL,

    occurred_at                 TIMESTAMPTZ NOT NULL,
    received_at                 TIMESTAMPTZ,

    message                     TEXT,
    data_json                   JSONB
);
```

Examples:

- `KALSHI_STREAM_GAP`
- `ESPN_STALE`
- `POSITION_MISMATCH`
- `ORDER_MISMATCH`
- `CLOCK_UNHEALTHY`
- `RESIZE_PENDING`
- `RESIZE_COMMITTED`
- `GLOBAL_KILL`
- `NO_NEW_ENTRIES`

---

# 6. Derived Metrics

Derived metrics should be generated from immutable authoritative rows, not manually stored unless needed as a materialized projection.

## 6.1 Entry VWAP

`sum(fill_price * qty) / sum(qty)` for `ENTRY` fills.

## 6.2 Entry slippage

`entry_vwap - 78¢`

Keep this distinct from strategy loss.

## 6.3 Hedge VWAP

`sum(hedge_fill_price * qty) / sum(hedge_qty)`

## 6.4 Gross exit-equivalent

For directly exited original contracts:

`direct_exit_price`

For exact-complement hedge contracts:

`100¢ - hedge_price`

For mixed exits:

quantity-weighted original-contract-equivalent VWAP.

## 6.5 Net exit-equivalent

Subtract actual exit/hedge fees per matched contract.

## 6.6 Live realized EV

`100 * sum(net_pnl dollars) / sum(initial_contract_qty)`

Result in cents per initial contract.

## 6.7 Adverse exit rate

`adverse_exit_count / completed_trade_count`

## 6.8 Mean adverse exit-equivalent

Mean or preferably contract-weighted mean of adverse exit-equivalent prices.

Dashboard should show both:

- trade-weighted mean,
- contract-weighted mean.

## 6.9 Portfolio return

`(reconciled_equity - 20000) / 20000`

## 6.10 50-trade objective

At N=50:

- target bankroll: `$21,000`
- target net profit: `$1,000`
- target return: `+5%`
- planning EV target: `+1.5¢/contract`
- approximate EV needed for the 5% target under the assumed sizing model: about `+1.31¢/contract`
- target gross mean adverse exit-equivalent: `>=50¢`

These are measurement targets only. They never alter execution behavior.

---

# 7. Event-Level State Machine

Every game begins in observation mode before the entry window.

```text
GAME_DISCOVERED
      |
      v
WATCHING
      |
      +-----------------------------------------+
      |                                         |
first 78 before valid window              first 78 inside valid window
      |                                         |
      v                                         v
INELIGIBLE_PRIOR78                        ENTRY_SIGNALLED
      |                                         |
      |                                         v
      |                                    ENTRY_WORKING
      |                                         |
      |                         +---------------+---------------+
      |                         |                               |
      |                   some fill                        no fill + mid>=86
      |                         |                               |
      |                         v                               v
      |                    PARTIAL_ENTRY                   MISSED_ENTRY
      |                         |
      |                         +---------> full/current fill
      |                                      |
      |                                      v
      +-------------------------------- POSITION_OPEN
                                             |
                                 +-----------+-----------+
                                 |                       |
                         opponent <36            opponent >=36
                                 |                       |
                                 |                       v
                                 |                HEDGE_TRIGGERED
                                 |                       |
                                 |                       v
                                 |                HEDGE_WORKING
                                 |                       |
                                 |          +------------+------------+
                                 |          |                         |
                                 |     hedge fills                 no/full fill
                                 |          |                         |
                                 |          v                         |
                                 |   PARTIAL_HEDGE                    |
                                 |          |                         |
                                 |          +-------------+-----------+
                                 |                        |
                                 |           opponent falls / rises
                                 |                        |
                                 |             +----------+----------+
                                 |             |                     |
                                 |             v                     v
                                 |       RECOVERY_HEDGE     EMERGENCY_DIRECT_EXIT
                                 |             |                     |
                                 |      fill / 25 floor               |
                                 |             |                     |
                                 |             +----------+----------+
                                 |                        |
                                 |                        v
                                 |              DIRECT_EXIT_WORKING
                                 |                        |
                                 +------------------------+
                                                          |
                                                  exposure removed
                                                          |
                                                          v
                                                 SETTLEMENT_PENDING
                                                          |
                                            reconcile fills/fees/settlement
                                                          |
                                         +----------------+----------------+
                                         |                                 |
                                      matched                         mismatch
                                         |                                 |
                                         v                                 v
                                     COMPLETED                 RECONCILIATION_REQUIRED
```

---

# 8. Detailed State Transition Specification

## 8.1 `WATCHING`

Entry conditions:

- event mapping valid,
- both Kalshi contracts known,
- both contracts subscribed,
- sports-state provider available enough to classify the authorized window,
- FIRST78 history still provably complete.

Actions:

- observe both contracts continuously from game start,
- maintain first-touch memory,
- persist threshold-relevant quote events.

Transitions:

### to `INELIGIBLE_PRIOR78`

Condition:

`first78 occurs before authorized window`

Persist first-touch data before transition.

### to `ENTRY_SIGNALLED`

Condition:

`first78 occurs inside authorized window`

and all entry safety gates pass.

### remain `WATCHING`

while no first78 occurs.

### to terminal ineligible state

if an observation gap means FIRST78 history can no longer be proven.

---

## 8.2 `ENTRY_SIGNALLED`

Atomic actions:

1. reserve daily trade-cap slot,
2. bind active sizing epoch,
3. compute trade budget,
4. create deterministic trade ID,
5. persist signal snapshot,
6. transition to `ENTRY_WORKING`,
7. create initial post-only entry intent at 78¢.

If capacity reservation fails:

do not create a trade position.

Persist a skipped opportunity record separately.

---

## 8.3 `ENTRY_WORKING`

Allowed active entry prices:

78–82¢ only.

Rules:

- post-only,
- quantity recalculated after every fill,
- no duplicate entry exposure,
- total filled + open worst-case acquisition cost must stay within budget.

Transitions:

### to `PARTIAL_ENTRY`

when `0 < filled_entry_qty < desired/current max`.

### to `POSITION_OPEN`

when no further entry quantity is being pursued and `filled_entry_qty > 0`.

### to `MISSED_ENTRY`

when selected midpoint reaches 86¢ or more with `filled_entry_qty == 0`.

### abort / reconciliation

if exchange state becomes ambiguous.

---

## 8.4 `PARTIAL_ENTRY`

Actions:

- recompute remaining budget,
- recompute remaining permitted quantity,
- continue authorized maker ladder no higher than 82¢.

If midpoint reaches 86¢ with partial fill:

do not mark `MISSED_ENTRY`.

Cancel unfilled remainder.

Transition to:

`POSITION_OPEN`

with actual filled quantity.

---

## 8.5 `POSITION_OPEN`

Maintain:

- original entry quantity,
- original open quantity,
- matched hedge quantity,
- remaining unhedged quantity.

Monitor opponent midpoint.

Transition to `HEDGE_TRIGGERED` when:

`opponent_mid >= 36¢`

for first time.

If game settles before hedge trigger:

transition to `SETTLEMENT_PENDING`.

---

## 8.6 `HEDGE_TRIGGERED`

Atomic actions:

1. persist hedge-trigger market snapshot,
2. verify complement relationship remains valid,
3. compute `target_hedge_qty = remaining_unhedged_qty`,
4. create post-only opposing-contract hedge at 35¢,
5. transition `HEDGE_WORKING`.

If complement verification fails:

do not place opposing contract hedge.

Transition directly to an authorized direct-exit path or operator-safe state according to final execution policy.

---

## 8.7 `HEDGE_WORKING`

Continuously update matched quantity.

Transitions:

### `PARTIAL_HEDGE`

if some but not all target quantity fills.

### exposure fully neutralized

if:

`matched_hedge_qty == original_open_qty`

Then remaining directional quantity is zero.

Continue to settlement/reconciliation accounting.

### `RECOVERY_HEDGE`

if opponent market moves lower than the current hedge level.

### `EMERGENCY_DIRECT_EXIT`

if opponent market moves adversely upward after trigger while the remaining hedge is not filling.

The production implementation must define the exact quote condition for detecting "adverse upward move" from live exchange state. It must not use a descending hedge bid while the opponent price is rising.

---

## 8.8 `RECOVERY_HEDGE`

Allowed opposing-contract maker prices:

`35 -> 34 -> ... -> 25`

Only move downward as opponent market price itself falls.

Never move a recovery bid lower because the opponent market is rising.

At each reprice:

- cancel prior open remainder,
- await/confirm cancellation state or use exchange-supported safe replace semantics,
- preserve already filled hedge quantity,
- create new remaining quantity only,
- use deterministic client order IDs.

Transitions:

### to completed hedge

if matched quantity reaches original open quantity.

### to `EMERGENCY_DIRECT_EXIT`

if adverse branch occurs.

### to `DIRECT_EXIT_WORKING`

if opponent reaches 25¢ and hedge remains incomplete.

---

## 8.9 `PARTIAL_HEDGE`

Invariant:

`remaining_unhedged_qty = original_open_qty - matched_hedge_qty - direct_exit_qty`

Every subsequent hedge or direct exit uses only `remaining_unhedged_qty`.

Never use original full quantity again.

Transition according to current opponent price:

- recovery -> `RECOVERY_HEDGE`
- adverse -> `EMERGENCY_DIRECT_EXIT`
- fully matched -> settlement path

---

## 8.10 `EMERGENCY_DIRECT_EXIT`

Actions:

1. cancel all remaining hedge orders,
2. confirm or reconcile hedge fills that may race with cancellation,
3. recompute remaining unhedged original quantity,
4. submit direct taker-capable exit only for remaining quantity,
5. transition to `DIRECT_EXIT_WORKING`.

Critical race case:

a hedge fill may arrive after cancel was requested.

Therefore direct exit quantity must be recomputed from authoritative exchange fills immediately before submission and after any late fill.

---

## 8.11 `DIRECT_EXIT_WORKING`

Continue until remaining unhedged quantity is zero or exchange reports final authoritative state.

If position state is ambiguous:

`RECONCILIATION_REQUIRED`

Never assume an order submission eliminated exposure.

Only fills do.

---

## 8.12 `SETTLEMENT_PENDING`

Use when:

- winning exposure is intentionally held,
- settlement-neutral complementary pair exists,
- direct exit has completed but settlement accounting is still needed,
- final exchange settlement record has not yet reconciled.

No trade becomes `COMPLETED` merely because the game ended.

---

## 8.13 `RECONCILIATION_REQUIRED`

Blocks new entry generation globally when mismatch severity is critical.

Triggers include:

- exchange position != local position,
- unknown live order,
- duplicate or unexplained fill,
- balance mismatch,
- ambiguous hedge quantity,
- settlement mismatch,
- crash recovery incomplete.

Exit/risk management must remain operational where possible.

Transition to prior/appropriate state only after authoritative exchange reconciliation.

---

## 8.14 `COMPLETED`

Requirements:

- no unmanaged open quantity,
- no unknown open order,
- all fills known,
- all fees known,
- settlement or direct-exit economics known,
- net P&L calculated,
- bankroll reconciled,
- trade checkpoint counters updated.

Only `COMPLETED` trades increment the completed-trade counter used for resizing and 20/50/100/200 checkpoints.

---

# 9. Sizing-Epoch State Machine

```text
ACTIVE_EPOCH
    |
    | completed reconciled trades < 10
    |
    +-------------------------+
                              |
                    completed count >=10
                              |
                              v
                        RESIZE_PENDING
                              |
              outside 01:00–03:00 PT
                              |
                              +----> remain old epoch
                              |
               inside authorized window
                              |
                    reconciliation clean?
                        /            \
                      no              yes
                      |                |
                      v                v
              RESIZE_DEFERRED   CALCULATE_NEW_EPOCH
                                         |
                                         v
                                  ATOMIC_COMMIT
                                         |
                                         v
                                    NEW_ACTIVE_EPOCH
```

Rules:

- never resize mid-trade,
- never resize partially,
- never infer balance from modeled P&L,
- use reconciled account equity,
- open positions retain the sizing epoch assigned at initiation.

---

# 10. Daily Capacity State Machine

Atomic transaction:

```text
read capacity
if initiated + reserved >= 8:
    reject
else:
    reserved += 1
    commit
```

On successful trade initiation:

`reserved -= 1`
`initiated += 1`

If entry attempt never becomes an initiated position and policy defines the slot as reusable:

release reservation deterministically.

Do not allow concurrent signal race to create trade 9.

---

# 11. ESPN / Sports-State State Machine

```text
UNKNOWN
  |
  v
DISCOVERED
  |
  v
MAPPED
  |
  +-----------------------------+
  |                             |
healthy                       failure/stale
  |                             |
  v                             v
HEALTHY                    DEGRADED/STALE
  |                             |
  |                             +----> NO_NEW_ENTRY
  |
  +----> valid clock/period feeds strategy
```

Key rule:

ESPN failure blocks new entry but must not disable Kalshi-side position management.

FIRST78 market history remains authoritative and continues to be recorded even if ESPN is stale.

If a FIRST78 touch happens during sports-state uncertainty, the touch still consumes the game's first-touch status.

---

# 12. Kalshi Stream State Machine

```text
DISCONNECTED
    |
    v
CONNECTING
    |
    v
SNAPSHOT_SYNC
    |
    v
LIVE
    |
    +---------------------------+
    |                           |
sequence continuity ok      gap/disconnect
    |                           |
    v                           v
   LIVE                    UNKNOWN_GAP
                                |
                          NO_NEW_ENTRY
                                |
                         fetch fresh state
                                |
                       reconcile orders/positions
                                |
                                v
                              LIVE
```

If a gap could have concealed FIRST78:

mark event:

`INELIGIBLE_DATA_GAP`

for entry purposes.

Do not assume no threshold touch occurred.

---

# 13. Position Guardian

Independent of strategy signal generation.

Poll/reconcile exchange position state on a separate cadence.

For every nonzero exchange position require:

- known trade ID,
- known contract,
- known quantity,
- known entry state,
- known hedge state,
- valid risk-management path.

If exchange reports unknown exposure:

`CRITICAL_POSITION_MISMATCH`

Actions:

- disable new entries,
- alert,
- reconcile,
- preserve ability to close exposure.

---

# 14. Order Guardian

Continuously compare exchange open orders against local order registry.

Detect:

- orphan exchange orders,
- locally open but exchange-missing orders,
- duplicate entry orders,
- duplicate hedge orders,
- wrong quantities,
- stale entry orders,
- stale hedge orders,
- unknown live order IDs.

Unknown live orders are critical.

A cancel request is not treated as cancellation until the exchange state confirms it.

---

# 15. P&L Calculation

For each trade:

## Entry cash

`sum(entry_fill_price * qty) + entry_fees`

## Hedge cash

`sum(hedge_fill_price * qty) + hedge_fees`

## Direct exit proceeds

`sum(direct_exit_fill_price * qty) - direct_exit_fees`

## Settlement proceeds

Actual exchange-settlement proceeds.

## Net P&L

Use actual cash flows and actual exchange fees.

Never infer realized P&L from midpoint.

## Realized EV cents/contract

`100 * net_pnl / initial_contract_qty`

---

# 16. 50-Trade Validation Scorecard

At exactly 50 `COMPLETED` trades freeze an immutable report.

Required fields:

## Capital

- starting bankroll
- ending reconciled bankroll
- net profit
- return %
- target ending bankroll `$21,000`
- target net profit `$1,000`
- target return `5%`

## EV

- gross P&L/contract
- total fees/contract
- net EV/contract
- model target `+1.5¢`
- approximate 50-trade business-plan EV requirement `+1.31¢`
- confidence/uncertainty interval

## Execution

- entry VWAP
- mean entry slippage vs 78¢
- maker-entry percentage
- taker-entry percentage
- mean signal-to-first-fill latency
- fill rate
- missed entries
- partial entry count

## Adverse exits

- adverse exit count
- adverse exit rate
- trade-weighted mean gross exit-equivalent
- contract-weighted mean gross exit-equivalent
- mean net exit-equivalent
- median adverse exit-equivalent
- worst adverse exit-equivalent
- count below 50¢
- rate below 50¢

## Risk

- max drawdown
- largest single-trade loss
- longest losing sequence
- peak bankroll
- minimum bankroll

## Operational

- feed outages
- stale ESPN incidents
- Kalshi reconnect incidents
- reconciliation mismatches
- guardian alerts
- duplicate-message incidents
- service restarts
- manual interventions

Do not reduce these into one artificial pass/fail score.

---

# 17. Required Frozen Checkpoints

Produce immutable snapshots after:

- 10 trades
- 20 trades
- 30 trades
- 40 trades
- 50 trades
- 100 trades
- 200 trades

The 10-trade snapshots align with resize eligibility.
The 20/50/100/200 snapshots are major research checkpoints.

---

# 18. Core Invariants

These must exist as executable assertions/tests, not comments only.

1. One game can produce at most one FIRST78 initiated strategy position.
2. Once FIRST78 is observed, it can never be forgotten.
3. A prior FIRST78 outside the authorized window permanently disqualifies the event.
4. An observation gap capable of hiding FIRST78 disqualifies entry.
5. NBA entry is Q3 only.
6. NCAAB entry is H2 first 10 minutes only.
7. Entry price may never exceed 82¢.
8. Zero fill + selected midpoint >=86¢ cancels the attempt.
9. Entry all-in cost including fees may never exceed 6% of active sizing-epoch bankroll.
10. Daily combined initiated positions may never exceed 8.
11. Daily-cap allocation is atomic.
12. Ten completed trades create `RESIZE_PENDING`, not an immediate resize.
13. Sizing changes only from 01:00–03:00 `America/Los_Angeles`.
14. Trades after the tenth completion but before resize use the old epoch.
15. Open positions never change sizing epoch.
16. Opponent 36¢ trigger creates hedge intent.
17. Recovery hedge ladder may move downward only while opponent price is falling.
18. Opponent deterioration never causes the hedge bid to move downward.
19. Hedge quantity may never exceed remaining unhedged original quantity.
20. Direct-exit quantity may never exceed remaining unhedged original quantity.
21. A cancel request is not a cancellation.
22. An order is not a fill.
23. A midpoint is not a fill.
24. A fill is not a settlement.
25. Exchange fills/positions/orders are authoritative for actual exposure.
26. Local state is authoritative for strategy intent and FIRST78 history.
27. Stale ESPN blocks new entry.
28. Stale ESPN never disables exchange-side risk management.
29. Unknown exchange exposure blocks new entry.
30. Unknown live orders block new entry.
31. Every nonzero position must have a guardian-managed exit path.
32. Every completed trade must have reconciled fees.
33. Every completed trade must have reconciled P&L.
34. Frontend state is never authoritative.
35. Policy constants must be versioned.
36. Every order must use deterministic idempotency identifiers.
37. Crash/restart may not erase FIRST78 state.
38. Crash/restart may not erase open-position state.
39. Crash/restart may not erase active sizing epoch.
40. Full live mode stays disabled until production readiness gate passes.

---

# 19. Exact Test Matrix

## FIRST78 eligibility

- NBA Q1 first78 -> permanently ineligible.
- NBA Q2 first78 -> permanently ineligible.
- NBA Q3 first78 -> eligible.
- NBA Q4 first78 -> ineligible.
- NCAAB H1 first78 -> permanently ineligible.
- NCAAB H2 19:59 first78 -> eligible.
- NCAAB H2 10:00 first78 -> eligible.
- NCAAB H2 09:59 first78 -> ineligible.
- one team touches 78 early, other side reaches 78 later -> ineligible.
- Kalshi data gap before window capable of hiding 78 -> ineligible.
- duplicate FIRST78 quote -> only one signal.

## Entry execution

- 78 full fill.
- 78 partial, 79 remainder.
- 78 partial, 79 partial, 80 remainder.
- partial ladder through 82 without budget breach.
- no fill then mid=86 -> cancel and missed.
- 77 -> 83 jump -> no illegal >82 order.
- 77 -> 87 jump -> missed, no chase.
- cancel request races with fill.
- duplicate fill event.
- out-of-order exchange event.

## Sizing

- $20,000 -> $1,200 max all-in budget.
- maker fee included.
- 78¢ quantity obeys budget.
- 82¢ quantity obeys budget.
- partial fills obey remaining-budget math.
- tenth completed trade at 4 PM -> no resize.
- trade 11 at 7 PM -> old size.
- resize at 1:15 AM with clean reconciliation -> new epoch.
- resize window with reconciliation mismatch -> defer.
- DST transition uses `America/Los_Angeles`.

## Hedge

- opponent 36 -> hedge 35.
- 35 full fill.
- 35 partial fill.
- opponent falls 36->34 -> recovery reprice.
- opponent falls 36->25 -> fallback direct exit if incomplete.
- opponent rises 36->37 -> emergency direct exit.
- partial hedge then rise -> direct exit remaining quantity only.
- hedge fill arrives after cancel request -> direct exit quantity recomputed.
- complement metadata invalid -> no opposing hedge.
- duplicate hedge fill -> no over-hedge.

## Daily capacity

- trade 1–8 accepted.
- trade 9 rejected.
- simultaneous two candidates for final slot -> only one accepted.
- unfilled missed attempt releases/reserves slot according to frozen policy.

## Recovery

- service crash while watching.
- crash after FIRST78 persistence before order send.
- crash with working entry.
- crash with partial entry.
- crash with live position.
- crash with working hedge.
- crash with partial hedge.
- crash during direct exit.
- AWS reboot.
- database reconnect.
- WebSocket disconnect/reconnect.
- ESPN outage.
- unknown exchange order at startup.
- unknown exchange position at startup.

Expected result after every recovery test:

- no duplicate position,
- no lost position,
- no forgotten first touch,
- no stale sizing epoch,
- no untracked order,
- no over-hedge,
- no unauthorized trade.

---

# 20. Build Order

Recommended implementation order for Bot 001:

1. migrations/schema,
2. immutable event journal,
3. sports-event mapping,
4. ESPN normalized adapter,
5. Kalshi market-state adapter,
6. FIRST78 eligibility engine,
7. sizing-epoch service,
8. daily-cap allocator,
9. trade state machine,
10. shadow entry router,
11. fill/order persistence,
12. Position Guardian,
13. Order Guardian,
14. reconciliation,
15. hedge state machine,
16. direct-exit path,
17. P&L calculator,
18. checkpoint/report generator,
19. AWS service supervision,
20. replay tests,
21. shadow-live tests,
22. canary deployment,
23. readiness report,
24. explicit live authorization.

---

# 21. Repository Output Requirements

When implementing, create or update canonical repository files for:

- strategy policy JSON/YAML,
- migrations,
- models,
- state-machine engine,
- ESPN provider,
- Kalshi adapter integration,
- sizing service,
- daily-cap service,
- execution router,
- hedge manager,
- guardians,
- reconciliation,
- P&L accounting,
- checkpoint reports,
- tests,
- AWS service/runbook.

Also produce:

- `MOMENTO_FIRST78_LIVE_V1_POLICY.json`
- `LIVE_LEDGER_SCHEMA.md`
- `LIVE_STATE_MACHINE.md`
- `LIVE_READINESS_REPORT.md`
- `DEPLOYMENT_RUNBOOK.md`
- `INCIDENT_RUNBOOK.md`
- `DISASTER_RECOVERY.md`

Do not alter historical research cohorts or backtests while implementing the live bot.

---

# 22. Completion Definition

This specification is considered implemented only when:

- schema migrations apply cleanly,
- deterministic replay reconstructs state,
- all state transitions are unit/integration tested,
- duplicate events are idempotent,
- restart recovery works,
- FIRST78 history survives restart,
- daily cap cannot race above 8,
- position sizing cannot exceed 6% all-in,
- sizing changes only in the overnight window,
- partial fills are accounted correctly,
- partial hedges cannot over-hedge,
- direct exit only closes remaining unhedged quantity,
- live exchange state reconciles to local state,
- stale feeds fail safely,
- 20/50/100/200 trade reports can be generated directly from the ledger,
- live-order submission remains gated until explicit authorization.

The core operational doctrine is:

**Never miss silently.  
Never size ambiguously.  
Never forget exposure.  
Never infer a fill.  
Never lose the audit trail.**
