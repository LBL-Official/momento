# Momento FIRST78: capital, control, and reporting contract

Owner amendment, September 30, 2026. This takes precedence over earlier fixed
$20,000 bankroll examples and October 10 launch targets in this folder.
Implementation status is in `STATUS.md`; requirements here are not deployment evidence.

## Capital and launch

October 3, 2026 is the target for a **$20 funded-account canary**, subject to
eligible markets, reconciliation, execution validation, and the live release gate.
October 8 Cursor availability is a handoff date, not a runtime dependency.
Do not assert that a game or eligible market will exist on a target date.

The bot obtains cash and position value from authenticated Kalshi account reads.
There is no hardcoded $20 or $20,000 sizing fallback. Missing, stale, future-dated,
inconsistent, or unowned account state blocks admissions. Persist the identified,
reconciled opening snapshot before the first order; restart restores it rather
than setting a new baseline. NBA and NCAAB share **one** allocation, daily cap,
reconciliation boundary, and account. Verify the exclusive-bot assumption:
manual trades or another bot's unknown orders/positions are an integrity incident.

Use the same production binary, policy, fee adapter, order state machine,
cancellation/reconciliation logic, retry rules, and telemetry at every balance.
There is no simplified $20 execution mode and no balance-based threshold switch.

- Acquisition budget is floor(6% × frozen epoch equity), in cents, including fees.
- $20 equity gives a $1.20 budget; $20,000 gives $1,200. These are examples.
- Size down to supported contract increments after fees, actual available cash,
  reservations, routing, and hedge collateral constraints. Below the minimum:
  emit `SIZE_BELOW_MINIMUM`, skip, and never round up or waive fees.
- Use actual filled quantity everywhere. Partial fills, late fills, uncertain
  submissions, cancel/fill races, rejected orders and idempotency are mandatory
  at both balances. Never retry an ambiguous submission with a fresh client ID.
- A $20 test validates common logic but cannot demonstrate $20,000 depth,
  queue position, slippage, latency under load, or market impact. Larger-size
  promotion requires liquidity and execution evidence; passing one-contract
  tests is not that evidence.

Account equity is monitored continuously. **Sizing still changes only in the
01:00–03:00 America/Los_Angeles window**, after at least ten fully reconciled
completions and no entry construction in flight, under the existing epoch rule.
An intraday deposit never changes active trade budgets. The current implementation
supports the normal epoch rollover only; an operator funding-change exception
must be separately specified and audited before it is implemented. Increasing
funding does not implicitly bypass the frozen-epoch contract.

Deposits/withdrawals are external flows, not strategy profits/losses. For an
identified initial snapshot:

`net total trading P&L = equity_now − equity_start − net external flows since start`

Equity includes cash plus the authoritative valuation of held contracts. Available
cash and order/hedge reserves are separate; never subtract reservations from
equity twice. Store the valuation source/time and display stale marks as stale.
Realized P&L, unrealized P&L, locked-but-unsettled value, fees, and settlements
remain separate projections. Reconcile trade cash flows to account changes.

The previous $20,000→$21,000 / +$1,000 objective is a **reference scenario**,
not the funded baseline or a requirement to earn $1,000 on $20. Preserve the
50-trade/deadline research scorecard, label capital regime on each trade, and
show actual funded return and flow-adjusted performance. Do not invent revised
dollar profit targets. Compare net EV per actual original entry contract;
never treat 1,000× funding as 1,000× expected realized returns.

## Independent execution service

AWS/systemd owns service availability. The bot does not depend on Wi-Fi on the
operator's laptop, Cursor, the Momento website, Linear, or Sunsama. Host/network
outages are still real: a lost AWS→Kalshi connection while exposed is P0.
A local laptop disconnect neither terminates the service nor authorizes a trade.

Boot: load and verify policy/config hashes → acquire exclusive writer lease →
connect authenticated exchange and game feeds → restore durable state → reconcile
all orders, positions, fees and account funds → declare healthy → observe signals.
Ambiguous recovered orders are reconciled before admission or replacement.

Runtime: signal → risk/authority admission → durable order intent → order send →
ack/fill/partial fill → position → Drevo/Positman observation → authorized
exit/hedge/settlement → reconciliation → final ledger accounting.

Orchestra owns permissions, policy identity, portfolio authority and kill controls.
Algorithmic Execution alone sends orders. Choosin/Austin/Ontologic provide versioned
inputs. Drevo emits observations; Positman emits recommendations. A recommendation
is never an executed action. Research components must not become undocumented
mandatory dependencies of the fixed FIRST78 policy or change it during validation.

## Portfolio authority

| State | Admissions | Existing exposure |
|---|---|---|
| PORTFOLIO_NORMAL | All ordinary gates apply | Continue authorized management |
| PORTFOLIO_CAUTION | Apply configured caution/exposure limits | Continue management |
| NO_NEW_ENTRIES | Block new entries; cancel unfilled entry remainders | Preserve exits/reconciliation |
| EXECUTION_LOCKED | Block new exposure and normal order dispatch | Only separately authorized, reconciled risk-reducing recovery actions |

Maintain independent active incident reasons. Clearing one reason does not clear
others. P0 resolution requires fresh reconciliation evidence; a green heartbeat
cannot erase a policy mismatch or unknown position. Journal every transition,
reason, evidence reference, actor and policy version. An entry kill is not a
process kill and must not silently orphan existing positions.

## Three ledgers and event envelope

All authoritative events have schema version, globally unique event ID, monotonic
sequence, UTC occurrence/receive/commit times, bot/run IDs, strategy/policy hash,
config hash, code commit/build, account identity reference, correlation/causation IDs,
trade/game/market/order/fill IDs when applicable, source sequence and evidence digest.
Use integer money/fixed-point contracts, not floating-point balances. Preserve raw
provider evidence in a separately controlled store; never journal credentials.

1. **Execution ledger:** signal and rejected eligibility evidence; exact first
   touch and ESPN state; budget reservation; intent; send/ack/unknown/reject;
   all fills and fee evidence; cancels/replacements; hedge and direct exit;
   settlement; reconciliation; corrections as new events.
2. **Portfolio ledger:** initial equity, cash, external flows, valuations, exposure,
   realized/unrealized P&L, fees, open risk, drawdown, reservation changes,
   epoch rollovers and authority transitions. Reference execution event IDs.
3. **Development ledger:** change rationale, owner/agent, commit, review, test
   results, artifact/build hash, migration, deployment, rollback and observed
   result. Link Linear/GitHub work to the affected policy and evidence.

Write critical intent durably before network submission. Publish projections only
after commit. Unknown send outcomes require lookup by stable client ID, not blind
resend. Durable order and alert outboxes must survive restart and deduplicate.
Reject or quarantine torn/corrupt logs. Local hash chaining detects accidental
corruption; it is **not** tamper-proof immutable storage. Production also requires
append-only access controls, externally anchored checkpoints and retention/backup
policies (e.g. appropriately configured S3 retention). Never rewrite history.
The new replay WAL is not the production transactional outbox.

## Systimo Control Room

One read-only projection should show independent states for NBA Bot 001, Kalshi,
ESPN, Choosin, Austin, Drevo, Positman, Ontologic X/Y, Orchestra and ledger/recon.
Use CONNECTED/STALE/DEGRADED/UNAVAILABLE/NOT_IMPLEMENTED; never fabricate HEALTHY.
Distinguish process running, system healthy, and authorized/executing.

Capital: starting funded equity, current equity, external flows, available cash,
realized/unrealized and daily P&L, open risk, open positions, hedge collateral,
current sizing epoch and pending overnight resize. Label timestamps and units.

Strategy: completed trades, wins/stops, win rate, average actual entry/stop/winner
fill, actual fees per contract, slippage, realized net EV, drawdown and capital
regime. Separate settlement winners, direct exits and complementary hedges.

Execution: eligible signals, orders, filled orders, partial fills, rejects,
duplicate orders, unresolved intents, ledger mismatches; signal→submit and
signal→ack latency (median/tails); entry and stop slippage distributions.
Use signed conventions: buy slippage = fill minus contemporaneous reference;
sell exit slippage = fill minus reference. Missing evidence is unavailable, not zero.
Retain signal time, trigger price, market sequence and fill time for attribution.

Drevo time series per position: model/version, as-of time, feature cutoff,
hazard λ(t), survival probability, trend/regime, confidence, neighbor count and
input evidence. Positman: holdings, available hedge, opponent price, delta/risk
estimate, recommendation, rationale, and separate authorization/action outcome.
Only expose metrics actually computed by validated models. Preserve what was
known **before** each outcome; retrospective estimates must be labeled separately.

## Alerts and improvement loop

| Level | Examples | Required response |
|---|---|---|
| P0 execution danger | Position mismatch, duplicate live order, unknown position, connection lost while exposed, irreconcilable ledger, risk breach, policy hash mismatch | Durable immediate alert; block new exposure; explicit recovery evidence |
| P1 operational degradation | ESPN/Kalshi stale, Drevo unavailable, high slippage, accumulating partials, abnormal latency, drawdown threshold | Alert and incident state; block entries where required; continue safe risk management |
| P2 performance/research | Rolling 20-trade EV or exit-quality deterioration | Durable research evidence; deduplicated Linear follow-up, no wake-up by default |

Thresholds, lookback, minimum samples, alert destinations and recovery rules must
be versioned configuration, not invented from illustrative values. Provider health
must not hide exposure-specific P0 escalation. P2 never changes strategy thresholds.

Alert/Linear workers consume committed ledger events through durable outboxes.
They are outside the signal→Kalshi path; failures queue retries with bounded
backoff and idempotency keys, while execution continues under its own authority.
Linear evidence includes trade IDs, policy/model versions, expected vs observed
metric, clock states, entries/exits, Drevo history and slippage distribution.
Dedup key includes strategy, metric and completed-trade window; link existing
issues rather than creating one per polling cycle. No integration is considered
working until delivery/retry/dedup tests and destinations are configured.

Human loop: Systimo evidence → Linear work → Sunsama scheduling → Cursor/code
review → GitHub → validated deployment → new observed evidence. Linear, Sunsama
and Cursor are never exchange gateways or mandatory runtime dependencies.

## Acceptance and release evidence

Require restart/reboot recovery; duplicate delivery; partial/late fills; ambiguous
send; cancel/fill race; missing fees; disconnect while exposed; stale/corrected
sports data; sequence gap; disk-full/fsync failure; conflicting policy hash;
unknown account activity; multi-shard collateral; deposits/withdrawals; $20 and
$20,000 same-policy tests; unsupported fractional fills; account/ledger convergence;
alert delivery failure; website/Linear outage independence. Verify actual AWS
service isolation and rollback before production changes.

NCAAB is **season-verified P5 vs P5 only**. NBA remains Q3; NCAAB H2 first ten
minutes. First touch is event-wide from full-game observation, not first observed
in the eligibility window. Unknown prior history disqualifies entry. Missing
current-season membership or market complement evidence blocks entry.
