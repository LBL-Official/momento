# Rewrite Boundary

**Rule:** The new historical engine must not accidentally alter production behavior.  
**Classification date:** 2026-08-26.

Legend:

| Label | Meaning |
|-------|---------|
| **PRESERVE** | Keep as-is; seed or frozen reference |
| **WRAP** | Keep, add adapters/versioning around it without changing meaning |
| **REPLACE** | New implementation becomes canonical; old remains for regression until proven equivalent |
| **DEPRECATE** | Stop extending as the platform; do not delete in this rebuild |
| **UNTOUCHED** | Production / safety surface — research tasks must not modify |

---

## 1. UNTOUCHED (production freeze)

| Path | Why |
|------|-----|
| `strategies/mlb/**` | Live FIRST01 |
| `strategies/wnba/**` | Same machine |
| `crates/risk/**` | Risk Decision Engine |
| `crates/execution/**` | Order submission lifecycle |
| `crates/positions/**` | Fill-authoritative tracker |
| `crates/pnl/**` | Realized P&L |
| `apps/trading-engine/**` | Live/paper host |
| `config/live.toml`, `config/paper.toml` | Live gates |
| `deploy/momento-live.service`, `momento-paper.service`, `m10-fetch-secret.sh`, `m9-prod-auth-validate.sh`, `user-data.sh` | Production/paper ops |
| `crates/kalshi/src/{production,venue,transport,auth,ws,sandbox,secret,http}.rs` | Trading/auth transport |
| `apps/prod-auth-validate`, `apps/sandbox-validate` | Milestone auth |
| Live 80/81/83/89/50% constants and tests | Behavioral freeze |

`crates/core/**` is **shared**. Allowed later: additive types used only by research, behind feature/module boundaries that cannot change money, `can_attempt_entry`, or `MarketEvent` 80/81 meaning. **Default: treat core financial behavior as UNTOUCHED.**

---

## 2. PRESERVE (do not rewrite truth)

| Asset | Why |
|-------|-----|
| `Backtesting Suite/Data-Real/**` raw gzip + published parquet + manifests | Immutable seed lake. New parsers → new version dirs, never overwrite |
| SHA-256 checksums in manifests | Reproducibility |
| FIRST01 v1 rule definition | Plugin control baseline |
| Live vs research lifecycle audits | One-trade-per-game semantics |
| `docs/desk/2026-08-25-loss-review.md` | Motivation for path reconstruction |
| Integer cents / hundredths qty convention | Financial safety |
| Research isolation from risk/execution/mlb crates | Safety |
| `PublicMarketClient` historical endpoints | Official Kalshi public data |
| Manifest note that historical L2 is unavailable | Honesty |

---

## 3. WRAP (extend without changing meaning)

| Asset | How |
|-------|-----|
| `crates/research-data` lake layout | Keep `raw/orderbook/trades/manifests`; add provenance envelope v2 **beside** v1; add EVENT-domain dirs later |
| `RawMarketEvent` | Wrap with richer provenance; do not strip payload |
| `GameId`/`MarketId` hashes | Keep as Kalshi aliases; wrap with a new identity graph that also holds MLB ids |
| `DailyManifest` | Keep; add coverage types (`PARTITION` vs `LIFETIME`) rather than silently redefining COMPLETE |
| `NormalizedSource` | Keep enum; stop putting candles in a type named orderbook without an observability field on the row |
| `apps/research-collector` | Keep Kalshi collect; wrap schedule/catalog; do not point it at live trading |
| `deploy/momento-research-collector.*` | Keep isolated timer; new engine collector is a separate unit later |
| Drive/Sheets IDs and CSV mirrors | Keep LEGACY_V1; wrap with a new reporting schema rather than overwriting P&L meaning |
| `momento-kalshi` public_data.rs | Wrap for additional public GETs if documented; do not touch order POST |

---

## 4. REPLACE (new platform; old stays as LEGACY_V1)

| Asset | Replacement role |
|-------|------------------|
| Candle FIRST01 **platform** (`research-backtest` pipeline as the way MLB research is “done”) | New reconstruction engine + plugin runner |
| Primary artifact = trade/opportunity CSV | `StateTransition` + `GameMarketEpisode` |
| `ReplayItem::{Trade,Orderbook}` as the only timeline | Dual-domain timeline + sync metadata |
| `validate-mlb` / frequency reconcile as **completion criteria** for MLB research | Keep as FIRST01-plugin regression on candle lake only |
| `CONSERVATIVE_MAKER` as implied historical live equivalence | Explicit MODELED execution plugin; never silent |
| `ResearchSport::{Mlb,Wnba}` as the core sport enum | Generic `Sport`/`League` with MLB adapter first |
| `apps/replay-engine` stub | Future composition root for the new engine (not live) |

Until the new engine can replay FIRST01 **rules** equivalently (not fills: candles still cannot prove maker fills), keep LEGACY_V1 tests green.

---

## 5. DEPRECATE (stop extending; do not delete)

| Asset | Reason |
|-------|--------|
| Treating `orderbook.parquet` candles as books | Naming lie; freeze schema 1.0.0; new normalize version |
| Mixing PIT `RestSnapshot` into historical paths without flags | Collection-time book ≠ game-time book |
| Sheets as the experiment control plane for “is MLB research done?” | Becomes a report view |
| `Backtesting Suite/Data` demo COMPLETE flags | Easy to confuse with real data; keep for e2e tests only |
| `crates/prediction` stub as if it were a model | Replace later in ML waterfalls, not now |
| Stale sentence in `FIRST01_live_entry_state_machine.md` about new opportunity after complete | Docs-only correction is allowed; **not** a strategy change |

**Do not delete** LEGACY crates, Runs/, Data-Real, or FIRST01 tests.

---

## 6. Dependency matrix (research vs production)

```text
                    PRODUCTION                         RESEARCH (current)
Strategy            strategies/mlb                     research-strategies (copy)
Risk                crates/risk                        not used (must not fold into FIRST01 counts)
Execution           crates/execution + kalshi venue    research-execution (MODELED)
Position            crates/positions                   research-execution position sim
Data                live WS                            research-data Kalshi REST
Identity            kalshi hash + host bindings        same hash, no MLB pk
Config              live.toml                          sheet overrides / CLI
```

**Allowed coupling:** research reads `momento-core` types and Kalshi **public** HTTP.

**Forbidden coupling:** research writes live config, submits orders, calls Risk to “make backtest look like live frequency,” or patches `strategies/mlb` to make reconstruction easier.

---

## 7. What “rebuild” means operationally

- **New crates/modules** for the historical engine (names to be chosen in Waterfall 1 contracts), **or** a clearly versioned subtree under `crates/research-data` that does not break schema 1.0.0 readers.
- LEGACY_V1 remains importable.
- Production binaries (`momento` live/paper) must not gain research-only dependencies that change startup, gates, or order paths.

---

## 8. Explicit non-goals of the rebuild (until a later waterfall)

- NBA / WNBA / NHL / NCAAB adapters as implementation (interfaces only)
- FIRST01 retune
- Auto-promotion of models into Risk
- Destructive lake migration
- Inventing L2 from candles
