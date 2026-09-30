# Cursor implementation and release plan — October 3, 2026

Repository: `LBL-Official/momento`
Incoming branch: `feat/first78-live-v1-overnight-sizing`
Canonical folder: `docs/implementation/first78-live-v1/`
Owner targets: October 3 actual-account ~$20 launch; October 15 ~$20,000 funding.
Both are America/Los_Angeles dates, conditional on all release evidence below.

## Copy this instruction into Cursor

> Work in the existing Momento repository and finish NBA Bot 001 / NCAAB
> MOMENTO_FIRST78_LIVE_V1 using this implementation plan and its linked specs.
> First integrate `origin/feat/first78-live-v1-overnight-sizing` into the branch
> you are currently working on, preserving all existing work. Follow the Git
> procedure below; do not assume these changes are on main. Inspect the fetched
> commit and report its SHA. Read the entire primary specification, the capital
> amendment, this plan, the companion ledger spec and STATUS.md before coding.
>
> Implement, test, reconcile and deploy the full service to AWS. Retire MLB and
> WNBA execution completely using the drain-and-disable procedure below; do not
> orphan positions or disable shared infrastructure. The bot must use the exact
> authenticated, reconciled Kalshi account equity, expected to be $20.00 initially,
> and the same strategy and order lifecycle when funding reaches $20,000. Never
> substitute a configured $20 or $20,000 balance. Preserve the frozen 6% epoch and
> 01:00–03:00 Los Angeles resize contract. Implement complementary hedging,
> cancel/fill reconciliation and taker-capable residual direct exits, including
> the opponent-midpoint 25¢ recovery boundary as defined below.
>
> Execute the work in dependency order, maintain the acceptance matrix and
> evidence artifacts, fix failures, and continue through deployment when access,
> owner policy and readiness gates permit it. Do not stop at a skeleton, TODOs,
> unit tests, or a green service status. Do not represent a missing integration,
> fabricated fill, inferred fee or unverified balance as working. If a required
> credential or owner decision is missing, finish independent work, leave entries
> blocked, and name the exact blocker and evidence needed. Keep production orders
> disabled until the resolved contract, tests, account migration and release gates
> permit activation. Do not send synthetic production test orders. Produce the
> release report and the $20,000 promotion report specified below.

## 1. Governing contract and present starting point

Read in this order:

1. Repository `AGENTS.md`, applicable nested instructions and current architecture
   ownership/rules. User authorization to retire MLB/WNBA applies to the specific
   controlled migration here; do not generalize it to other services or strategies.
2. `SPECIFICATION.txt`, especially section 111 and its referenced amendment.
3. `OPERATIONS_AND_CAPITAL_V1.md` and this October 3 plan for current funding,
   launch, operations and retirement instructions.
4. `MOMENTO_LIVE_BOT_001_LEDGER_STATE_MACHINE_V1.md`, resolving documented conflicts
   against the primary spec. Do not double-subtract direct exits from exposure.
5. `STATUS.md`, `docs/operations/NBA_001.md`, `docs/momento/ARCHITECTURE.md`,
   `docs/momento/ARCHITECTURE_FREEZE_V0.md`, Systimo/Orchestra ownership,
   and the current execution contract under `research/vital/bots/nba-001/strategy/`.

Source locations:

| Responsibility | Starting point |
|---|---|
| Pure policy and sizing | `strategies/nba/src/live_v1.rs`, `sizing_epoch.rs` |
| Portfolio authority/performance | `strategies/nba/src/portfolio_v1.rs` |
| Existing lifecycle, fills, fees, exposure | Other `strategies/nba/src/` modules |
| V1 replay, WAL, ESPN, Kalshi normalization | `apps/nba-001/src/v1/` |
| Existing worker, execution and reconciliation | `apps/nba-001/src/{engine,lane,executor,venue,account,epoch_store}.rs` |
| Shared Kalshi client | `crates/kalshi/` |
| Build/deploy/service | `deploy/nba001-*`, `deploy/momento-nba-001.service` |
| Read-only AWS preflight | `deploy/nba001-v1-preflight.py` |

Current code is a **tested starting point, not a completed live bot**. Production
orders remain compiled out. `v1-replay` accepts fixture/caller evidence, not
verified live reconciliation. Replay WAL is not a production order outbox.
The normalizer is not a complete continuously supervised V1 runtime. Whole-contract
orders and whole-cent quotes do not establish production fractional compatibility.
`STATUS.md` lists these limitations; finish them rather than relabeling them.

Do not promise zero defects, zero bottlenecks, guaranteed fills or a riskless
$20,000 deployment. Convert those goals into measured limits, adversarial tests,
explicit failure behavior and observable release gates.

## 2. Bring the changes into Cursor's current branch

Run from the existing repository. Inspect outputs before continuing:

```sh
git remote -v
git branch --show-current
git status --short
git log -5 --oneline
git fetch origin
git log -5 --oneline origin/feat/first78-live-v1-overnight-sizing
git diff --stat HEAD...origin/feat/first78-live-v1-overnight-sizing
```

Confirm origin is `LBL-Official/momento`, not another checkout/fork. Record the
current branch and its SHA and the incoming branch's SHA in the development ledger.
If detached, resolve the intended working branch before merging. Preserve dirty
work in an explicitly identified WIP commit or separate worktree after reviewing
its contents; do not blanket stash, reset, clean, or commit unrelated files.
There was unrelated MLB research-ledger work in the author's checkout; it is not
part of this feature and must not be overwritten.

For a clean current branch, use a unique backup name, then merge **into that branch**:

```sh
git branch backup/pre-first78-2026-10-03 HEAD
git merge --no-ff --no-commit origin/feat/first78-live-v1-overnight-sizing
```

If already integrated, verify content/ancestry and skip the redundant merge. If
the backup name exists, choose a new name; never force-update it. Resolve conflicts
by understanding both branches. Preserve legacy collectors until retirement is
complete, integrate new CLI/module entries, and regenerate Cargo.lock with the
pinned toolchain when dependencies conflict. Never select “ours/theirs” wholesale.
Inspect the staged diff for credentials, unrelated changes, and policy regression.
Commit the reviewed merge, run baseline tests, and push the current working branch
through the repository's normal review workflow. Record the integration commit.
Do not cherry-pick the incoming branch's entire ancestry or overwrite the current
branch with the feature branch. Do not force-push.

Baseline commands (use `rust-toolchain.toml`, currently Rust 1.98.0):

```sh
cargo test --locked -p momento-strategy-nba -p momento-nba-001
cargo test --locked -p momento-kalshi
```

Format changed files and review formatting diffs; separate pre-existing global
format failures from new changes. Run repository-required checks for affected
components. Do not rewrite the entire repository merely to pass formatting.

## 3. Freeze unresolved behavior before enabling live execution

Create a versioned machine-readable V1 contract, human-readable decision record,
and policy hash. Resolve against the primary spec, existing exchange facts and
owner instructions; do not supply convenient arbitrary constants to unblock live.
Explicitly encode:

- NBA Q3; NCAAB H2 first ten minutes; verified **both teams P5**, current-season
  membership evidence and canonical team IDs. The older 2025–26 manifest is not
  sufficient for 2026–27. No automatic inclusion of every NCAAB game.
- Event-wide first midpoint touch >=78¢ with complete earlier history; no Q3/H2
  re-entry after an earlier touch; disqualification on uncertain history.
- Entry 78→79→80→81→82¢, post-only, precise reprice timing and lifetime; cancel
  unfilled remainder at selected midpoint >=86¢ or when eligibility ends.
- Unified NBA/NCAAB eight-trade cap and the exact trading-session boundary;
  admission/nonfill/partial-fill counting and reservation release semantics.
- Frozen fee-inclusive 6% sizing, completion definition, overnight epoch commits,
  available cash, routed collateral, pending reservations, hedge reserve and
  portfolio exposure/drawdown limits.
- Feed freshness and skew bounds, sequence handling, provider correction policy,
  time synchronization, reconnect history, exact half-cent/subpenny comparisons.
- Hedge ratchet, deterioration comparator, timeout/retry limits, exit execution
  controls, price protection and recovery escalation. Do not conflate trigger
  prices with executable prices or assume a market order guarantees a fill.
- Whether Drevo/Positman are required live inputs or recorded research observations.
  Their availability must not silently change the frozen strategy.

Keep an unresolved-field checklist. Any critical unresolved field blocks live
arming, not code completion or fixture/demo work. Document supported exchange
precision, fees, routing, minimum size, rate limits and supported order types
using official current Kalshi documentation and read-only account/market evidence.

## 4. Exact account capital and same logic at every balance

Implement a signed, paginated account reconciliation service using the existing
Kalshi transport. Retrieve authoritative cash, positions/valuation, orders, fills,
fees and settlements across all relevant shards/subaccounts. Parse dollar strings
and fixed-point contract quantities losslessly into checked integers; never cast
through floating point, assume cents when the API returns dollars, or silently
round fractional holdings away.

The initial expected balance is $20.00, but the input is **the actual account**.
Do not transfer funds automatically, fake a $20 snapshot, or replace an observed
$19.98/$20.01 with $20.00. Display the exact observed amount and any discrepancy.
If valid funding differs, size from the exact reconciled amount subject to all
risk gates; if the funding/ownership/equity evidence is inconsistent, block and
report. After retiring MLB/WNBA, verify a clean account and establish the baseline.

Define precisely from verified API semantics:

- cash, portfolio market value and total equity;
- spendable collateral per route, order reservations and hedge capacity;
- net external deposits/withdrawals;
- realized trading P&L, unrealized value and paired unsettled payout;
- snapshot consistency, freshness and reconciliation watermark.

Use `equity = cash + position value` only after confirming those source fields
are disjoint. Do not double-count a total portfolio value field. Available cash
is not a synonym for equity; global equity cannot spend collateral on a different
exchange shard without authorized funding/routing support.

Remove every V1 hardcoded reference-bankroll fallback, including UI, tests promoted
to configuration, admission, batch rollover and retry code. Persist a reconciled
baseline and sizing epoch atomically. Full replay/restart must not reset return,
trade count, loss limits or pending resizing. Initial $20 equity gives $1.20 entry
budget; $20,000 gives $1,200. Contract increments/fees may reduce executable size.
Below-minimum orders are skipped with an explicit reason, never rounded up.

Reconcile continuously, but retain frozen admission budgets until authorized
01:00–03:00 America/Los_Angeles rollover after at least ten final completions.
At October 15 funding, use the actual deposit and the same account feed. A deposit
is not profit and not an intraday resize command. If the ten-completion/window
requirements are not met, report pending promotion; do not invent a funding
exception. A changed capital policy requires a separately approved version.

The same binary must handle $20, $19.98, zero available cash, $20,000 and larger
supported values. No `if balance < ...` alternate strategy. Risk constraints and
integer sizing may change quantities; they must not change order safety behavior.

## 5. Finish the live feed and deterministic strategy path

Build a continuously supervised V1 runtime behind an explicit mode/config. Reuse
canonical Rust modules; do not create a second bot implementation in the docs.

- Discover permitted NBA/NCAAB winner markets and validate exact complements,
  rules, expirations, settlement conditions, IDs and exchange route. Reject
  mismatched rules, ambiguous games, duplicates, and unsupported precision.
- Resolve ESPN event and team IDs explicitly, including preseason and tournament
  cases. Name similarity alone is insufficient. Preserve raw evidence and match
  confidence/review. Refuse ambiguous joins rather than guessing home/away order.
- Subscribe before the game and maintain sequence-checked books for both contracts.
  Do not backfill missed FIRST78 history from a current snapshot. Reconnect may
  restore risk observation, but cannot repair unknown past eligibility.
- Poll/stream game status with bounded deadlines and backoff. Preserve provider
  time separately from receive time. Reject clock/score regressions pending
  correction/reconciliation. Handle suspended, delayed, canceled and overtime games.
- Join quotes and sports state by explicit IDs and freshness. Record both sides'
  executable quotes, midpoint and evidence at first touch. Test exact boundaries.
- Run one authoritative reducer/writer per portfolio. Entry claims, cash/hedge
  reservations, day count and epoch selection must be one durable transaction.
- Separate ingestion, order handling, reconciliation and telemetry queues. All
  queues are bounded. Backpressure must produce visible degradation and entry
  blocks, not silent event loss or unbounded memory.
- Tick timers even during low event volume; process account/fill/cancel evidence
  promptly. Heavy model requests, dashboard reads, alert delivery, Linear and
  Sunsama never block the exchange loop.

Shadow observations must be clearly labeled. Shadow quotes do not become fills;
keep hypothetical actions, demo execution and actual production outcomes distinct.

## 6. Finish order execution and the 25¢ exit correctly

Use existing audited order/exposure primitives, strengthened where needed.
Every order needs durable intent, deterministic client ID, policy/epoch/trade IDs,
confirmed route, economic reservation and an idempotent outbox state.

Order lifecycle must cover queued/sending/acknowledged/resting/partial/filled,
cancel-pending/canceled, expired/rejected, and unknown outcome. HTTP timeout means
unknown, not rejected. Reconcile by client ID and exchange ID before retry; retain
late-fill visibility after cancellation and across restarts. Fill-ID deduplication
must survive restart. Never replace a potentially live order blindly.

### Hedge and direct-exit semantics — do not confuse these prices

The existing design defines **25¢ as the opponent midpoint recovery boundary**
after the opponent >=36¢ hedge trigger. It is not a promise to sell the original
contract at 25¢ and is not a 25¢ limit order on the original. The owner's requested
“market order at 25 cents emergency sell” is implemented as an immediate,
taker-capable **sale of residual original YES when that trigger fires**.
If the owner means an original-contract price threshold instead, that is a policy
change and must be clarified before arming; do not silently reinterpret the spec.

1. With original A YES exposure, opponent B midpoint >=36¢ triggers HEDGE_PENDING.
2. Cancel unfilled original entry remainder and reconcile its final/late fills.
3. Place post-only B YES bid at 35¢ for reconciled unhedged A quantity, constrained
   by verified collateral. Do not count an acknowledged order as a hedge fill.
4. On B recovery, safely ratchet the passive hedge downward as specified, never
   above its prior limit, and never cross the ask under a maker label.
5. On B deterioration after trigger, cancel the passive hedge and use the
   authorized direct-exit fallback immediately; do **not** wait for 25¢.
6. If B midpoint reaches or crosses <=25¢ while a residual remains, cancel the
   passive hedge, reconcile any racing fills, then sell only the still-unhedged
   original A quantity through the taker-capable exit path.
7. Confirm current API support: use a native market order only if supported and
   authorized for this venue/route. Otherwise implement the documented marketable
   reduce-only IOC limit equivalent, with the owner-approved price-protection
   policy. Never invent a 1¢ floor or claim a protected IOC is a guaranteed fill.
8. Reconcile actual fills and remainder after each attempt. Bounded retries,
   freshness checks, updated depth, rate-limit budget and escalations are required.
   An IOC partial/nonfill leaves exposure and must remain monitored and reported.
9. Paired quantity is `min(current A long, current B long)`; residual original is
   `max(0, current A long − current B long)`. Original holdings already exclude
   direct sales. Do not subtract direct exits twice. If B exceeds A, raise an
   overhedge integrity incident and follow a separately authorized recovery path.
10. Never send an exit quantity derived from the original requested entry size.
    Use authoritative fills/holdings, including partial and late fills. Never
    declare flat from an order acknowledgement, cancel response or intended hedge.

Fixtures must cover 36→35→34→25, 36→38, a jump from >25 to <25, incomplete hedge,
fully paired inventory, canceled hedge then late fill, partial IOC, no bid,
paused/closed market, zero collateral, disconnect and simultaneous risk actions.
Test the same cases at one contract and thousands of contracts. Choose route-aware
hedge reserves so the $20 account can actually execute its admitted exit policy.

## 7. Durable ledgers, performance and Control Room

Implement execution and portfolio events with the envelope from the capital/ops
amendment. Wire a durable order outbox and durable alert/research outbox. Do not
reuse a replay log as a transactional exchange dispatcher without completing
recovery, intent reconciliation, checkpoints and failure tests.

Persist critical intent before sending. Use exclusive-writer/fencing controls,
atomic transactions, fsync semantics appropriate to the storage engine, versioned
migrations and verified backup/restore. Detect torn/corrupt logs and wrong policy
hashes; fail closed. Prove journal/account convergence after each crash point.
Hash chains alone do not prevent a privileged writer from rewriting history.
Protect production records with append-only permissions, anchored checkpoints
and configured retention/backup. Never include secrets or private signing keys.

Implement Orchestra's independent active incident set and portfolio states.
A cleared incident must not erase unrelated blocks. NO_NEW_ENTRIES cancels entry
remainders but preserves safe management. EXECUTION_LOCKED permits only explicitly
authorized, reconciled recovery actions, not blind liquidation from stale holdings.

Build Systimo projections and API/UI for:

- component health, heartbeat/last update, feed lag, policy/build identity,
  authorization state, active reasons and unresolved orders;
- exact starting/current funded equity, flows, cash, holdings, reserves, open risk,
  realized/unrealized/daily P&L, drawdown and epoch transition;
- trades/wins/stops, entries/hedges/direct exits, fee-inclusive actual-contract EV,
  slippage distributions and comparison to labeled research benchmarks;
- signal/order/fill funnel, p50/p95/p99 latency, partials, rejects, duplicates,
  stale intervals, reconciliation mismatches and recovery duration;
- as-of Drevo observations and separate Positman recommendations/actions with
  model/version/input evidence; unavailable is not healthy or zero.

P0 danger alerts must be immediate and durable. P1 degradation has configured
escalation. P2 rolling-performance findings produce deduplicated Linear issues
with evidence when that connector/outbox is configured. Linear failure cannot
block execution or erase a pending alert. Test alert delivery failure and retry.
Sunsama is a human scheduling integration only. Maintain the development ledger
for changes, tests, releases, rollbacks and observed production effects.

## 8. Retire MLB and WNBA completely without orphaning risk

The owner requests retirement as part of this migration. This plan is not proof
that a WNBA bot exists, that it is running, or that the named AWS host is current.
Discover all relevant hosts/services/workers, containers, schedules, cron jobs,
CI deploy jobs, supervisors, API credentials and account/subaccount ownership.
The known MLB unit is `momento-live.service`; inspect templated units too. There
is no verified standalone WNBA unit name in this handoff. Never invent one or use
broad wildcards to kill every Momento process.

Perform the following controlled sequence with an evidence log:

1. Verify AWS account, region, instance identity, bot ownership and current policy.
   Inspect the repository's control gates. Enable scoped authorized migration
   controls through the normal control path; do not bypass access controls or
   silently set a global flag merely to make a command succeed.
2. Put identified MLB/WNBA execution into NO_NEW_ENTRIES through their control
   interfaces; persist the migration intent and ensure no fresh admissions occur.
3. Enumerate and cancel their live unfilled entry orders by proven owner IDs.
   Reconcile final fills, cancel acknowledgements and any late fills.
4. Inventory residual positions and orders. Drain under their authorized risk
   policy or wait for settlement while keeping required risk management running.
   “Close the bots” does not authorize unbounded-price liquidation, fund transfers,
   or abandoning positions. Report any residual that prevents complete retirement.
5. Prove the old bots have no unresolved intents, live orders or unmanaged exposure;
   save final fills, settlements, fees, account snapshot and P&L checkpoint.
6. Stop and disable the exact identified execution units and associated restart
   mechanisms, timers/schedules/CI redeploys. Mask only those explicitly identified
   units if needed to prevent reboot restart. Keep required shared ingest, secrets,
   reconciliation, observability and NBA/NCAAB infrastructure operational.
7. Revoke/disable old bot-specific credentials only after proving they are not
   shared with the new bot or recovery paths. Never delete shared secrets blindly.
8. Verify inactive/disabled state, absent processes, no ongoing submissions,
   no scheduled resurrection, and restart/reboot persistence. Record command
   evidence and final ownership checks. Keep historical ledgers and source code.
9. Reconcile the whole account again, including manual/unknown activity. Only then
   assert NBA+NCAAB is the sole active bot and establish its initial funded baseline.

If migration cannot complete, report exactly which exposure/service remains and
keep the new bot blocked where collateral/ownership is uncertain. Do not claim
MLB/WNBA are fully closed just because their website pages are hidden.

## 9. Validation matrix — required evidence, not checkboxes

For every row store test command/scenario, code and policy hashes, inputs, observed
outputs, pass/fail, date and artifact location. Expected outcomes must be specified
before running the test. Test arithmetic and state properties, not only examples.

| Area | Required adversarial cases | Passing evidence |
|---|---|---|
| Identity/eligibility | Earlier touch, late attachment, halftime, exact Q3/H2 bounds, P5 vs non-P5, missing season, duplicate game | No unauthorized admission; reason and first-touch evidence retained |
| Capital | $20/$19.98/$20,000, no funds, missing/stale snapshot, deposit/withdrawal, wrong shard, overflow | Exact integer math; no fabricated equity; no budget/collateral breach |
| Epochs | 9/10/>10 completions, duplicate completion, DST, 01:00/03:00 boundaries, restart, construction in flight | No intraday resize; old admissions keep frozen budgets |
| Orders | Reject, timeout/unknown, duplicate delivery, cancel/fill race, amendment ambiguity, concurrent signals | No duplicate economic order; reservations match possible exposure |
| Fills | One/thousands/fractional, out-of-order and duplicate fill, missing/corrected fee | Exact deduped holdings and cash flows; unsupported evidence blocks |
| Exit | All paths in section 6, gap-through, no liquidity, partial IOC, paired position | Only reconciled residual sold; no oversell; exposure never hidden |
| Account | Unknown order/position, manual trade, pagination, partial API failure, correction | Whole-account reconciliation or explicit lock; no silent omission |
| Crash/storage | Crash before/after commit/send/ack, torn log, disk full, fsync error, two writers, restore | Recoverable intent; no duplicate send; corruption blocks safely |
| Feeds | Gap/reorder/duplicate, stale ESPN, corrected clock, disconnect while exposed | Entries block as required; recovery management and incidents persist |
| Dependencies | Website/Linear/Sunsama down, slow models, alert destination down | Execution independent; bounded queues and durable retries |
| Deployment | Wrong account/host, wrong hash, missing secret, reboot, rollback/schema mismatch | No unintended service or order mutation; recoverable validated release |
| Performance | Peak combined slate, burst fills/quotes, slow exchange, full disk, reconnect storm | Measured latency/memory/queue bounds and no lost critical events |

Use unit/property tests for fixed-point arithmetic, portfolio conservation and
residual invariants; deterministic recorded-feed replay; integration/fault-injection
tests; Kalshi demo end-to-end with permitted credentials; AWS shadow observation;
then a real-signal $20 canary. Demo success does not establish production fees,
liquidity, precision or routing. Never use fabricated market/position evidence to
pass a production gate. No new production position merely to test the API.

Run all affected Rust crates and existing regression suites. Test cross-compilation
for the actual host architecture and the release binary on the host. Document
ignored tests and missing real-environment evidence. Existing 170 local passing
tests in this handoff are a baseline, not proof of full V1 readiness.

## 10. Performance and bottleneck budget

Instrument end-to-end paths before optimizing. Version measurable SLOs from actual
strategy timing and exchange limits; illustrative dashboard latency is not an SLO.
Report p50/p95/p99 and maximum signal→durable intent→send→ack, fill→position update,
exit trigger→send, reconcile lag and recovery time. Use a monotonic clock for
elapsed times and UTC for audit, with monitored host clock synchronization.

Profile CPU, RSS, allocations, disk fsync latency, network RTT, queue depth and
age, websocket processing, ESPN cadence, API quota use and reconciliation pages.
Exercise peak expected slate plus documented burst headroom; $20,000 tests need
realistic partial-fill counts and order churn, not 1,000× duplicate signals.

No blocking REST/model/database/dashboard calls in the quote handler. Reserve
request capacity for cancellations, exits and reconciliation; admission requests
must not starve risk reduction. Prefer persistent connections and incremental
state; prevent reconnect/retry storms with bounded backoff/jitter. Use explicit
priority/fairness and bounded queues. Do not drop fills/orders to preserve quotes.
Prove slow storage fails safely; do not remove durability to improve a benchmark.

At larger size, test depth and slippage assumptions separately. A one-contract
canary cannot validate price impact for ~1,500 contracts. Do not “optimize” by
loosening price/risk limits. Report remaining bottlenecks and operating bounds;
absence of observed failures is not proof of unlimited capacity.

## 11. AWS deployment sequence

Known prior target: instance `i-0f0849d5829476c31`, region `us-east-1`; verify live
inventory before using it. Expected NBA unit: `momento-nba-001.service`; executable
`/usr/local/bin/momento-nba-001`; config `/etc/momento/nba-001.toml`; state
`/var/lib/momento/nba-001`; secret `/dev/shm/momento-kalshi-nba-001.json`.
These are starting references, not authorization to operate on a mismatched host.

1. Verify AWS caller/account and SSM host identity through read-only calls. Use
   `deploy/nba001-v1-preflight.py --expected-account <verified-account-id>` as a
   preliminary check; it intentionally never declares trading readiness. Missing
   access is a blocker, not a reason to search unrelated files for credentials.
2. Audit current unit, binary/hash, config, state, disk, memory, architecture,
   restart policy, network access, NTP, IAM, logs and other active services.
3. Build a reproducible release using the pinned Rust toolchain and reviewed commit.
   Review the existing ARM64 and atomic-deploy scripts before invoking them; adapt
   for actual architecture. Record binary digest and dependency/lockfile identity.
4. Create versioned config and resolved policy, provision least-privilege IAM and
   secret retrieval through the existing mechanism. Keep credentials out of git,
   prompts, artifacts and ordinary logs. Set restrictive secret-file permissions.
5. Back up and verify restore of state; design/test migrations and backward
   compatibility. Prepare rollback that stops admissions and reconciles before
   restoring an older binary. Never roll back a ledger to erase real exchange fills.
6. Complete old-bot retirement/account migration and record its gates. Deploy the
   new version atomically with production submission disabled. Verify service
   isolation, watchdog/restart behavior, disk alerts and durable state volume.
7. Run shadow with authentic market/account data, verify mappings and clock behavior,
   collect latency/recon evidence, test controlled disconnect/reboot recovery, and
   verify the Control Room plus alert destination. Missing eligible games means
   shadow evidence remains incomplete; it does not justify synthetic live orders.
8. Compare deployed code/policy/config hashes to the approved release. Only after
   all live gates pass, activate the permitted production adapter and runtime
   authorization through a reviewed release. Preserve explicit mode and gates;
   do not hide production capability in the default/demo build.
9. Immediately before arming, reconcile actual cash/equity/positions/orders/fees,
   prove sole-bot ownership and exact starting capital, check route/hedge reserve,
   verify no duplicate writer and confirm kill/alert/recovery paths.
10. Start the $20 canary only on a genuine eligible signal. Monitor the full
    lifecycle through actual final settlement/account reconciliation. If no signal
    occurs, report “armed and observing, no trade” separately from “executing.”

After deploy, prove laptop/Wi-Fi/Cursor/frontend absence does not stop the AWS
service. Do not induce an unprotected production failure while holding risk to
prove fault tolerance; use demo/shadow for destructive fault injection.

## 12. October 15 capital promotion

Funding $20,000 is external funding, not a software size override. Verify actual
receipt from the authenticated account feed. Do not initiate a bank deposit,
withdrawal or internal funds transfer from this plan. Record external-flow evidence
and preserve the original performance baseline.

Before allowing increased admissions, require:

- no unresolved P0; no unknown orders/positions or account mismatch;
- validated final fee/cash-flow accounting and real canary lifecycle evidence;
- passing partial/fractional/late-fill and crash/recovery tests at larger sizes;
- proven collateral routing and hedge capacity for every admitted position;
- documented larger-order liquidity, expected slippage and execution limits;
- sufficient measured performance headroom and working P0 alerts;
- an approved unchanged strategy/policy or separately reviewed version changes;
- the existing overnight/tenth-completion epoch gate, or a separately authorized
  amended capital policy—never an implicit date-based exception.

If any gate is incomplete on October 15, report “funded, increased sizing blocked”
and retain safe sizing/entry restrictions. Do not force promotion to meet a date.
Same code does not imply identical slippage or proportional returns across sizes.

## 13. Required Cursor deliverables and final report

Maintain `STATUS.md`, an implementation checklist, a resolved decision register,
and a release acceptance matrix in this folder. Save sanitized evidence under a
versioned release directory; keep large/raw/private account artifacts in the
approved controlled evidence store, referenced by immutable IDs and digests.

Deliver production code, exact fixtures/property/fault tests, pinned lockfile,
config schema and safe examples, market/team/membership evidence, durable ledger
migrations, Systimo projections, alert outbox integration, deploy/rollback scripts,
MLB/WNBA retirement evidence and AWS service/recovery evidence. Remove placeholder
success states and expose unsupported/missing facts as blockers.

Final report must include:

- incoming/integration/release commits and working branch; deployed binary,
  policy and config hashes; AWS account/region/instance and exact NBA unit;
- MLB/WNBA discovered units and final disabled state, residual orders/positions,
  final reconciliation IDs, and proof shared dependencies survived;
- exact account cash, position value, equity, available routed collateral,
  opening snapshot, epoch budget and funding discrepancy if any;
- test totals, ignored/unrun tests, failure-injection results, performance limits,
  demo/shadow/canary evidence and any unresolved policy or operational issues;
- execution mode, permission state, active incidents, whether a real trade occurred,
  fill/fee/settlement status and last authoritative reconciliation time;
- alert delivery proof, reboot/restart result, kill procedure, recovery/rollback
  commands verified for that release, and October 15 promotion gate status.

Use distinct terms: IMPLEMENTED, TESTED, CONNECTED, RECONCILED, DEPLOYED,
HEALTHY, ARMED and EXECUTING. Never collapse them into “done.” The deployment is
complete only when the corresponding evidence exists; otherwise state precisely
what remains blocked and leave the system in the documented safe state.
