# ROLLER Terminal — Codebase Map

**Date:** 2026-09-07  
**Status:** Phase 0 archaeology complete — **no terminal UI implemented from this document**  
**Purpose:** Inventory of authoritative databases, research mathematics, and conflicts before any ROLLER Terminal adapter or frontend work.

```text
THIS MAP ≠ IMPLEMENTATION AUTHORIZATION
LIVE EXECUTION = FALSE
CANDLE PATH ≠ FILL
MEASUREMENT ≠ EDGE
FIRST80 = ONE RESEARCH OBJECT — NOT THE SYSTEM BOUNDARY
```

**Architecture correction (2026-09-07):** Build an interface to ROLLER as a rolling empirical database. BBALL1 is a universe. FIRST80 is the first deep research object inside BBALL1 — not a FIRST80 strategy dashboard. See `docs/research/roller_dashboard/RESEARCH_OBJECT_MODEL.md`.

```text
UNIVERSE → DATASET → POPULATION → RESEARCH OBJECT → MEASUREMENT → RESULT
```

---

## 0. Executive verdict

| Layer | What exists | Authoritative for |
|-------|-------------|-------------------|
| **`ROLLER/`** | Python PIT research DB (CSV) + `Roller` API | Point-in-time I(t), O_t, F_t, V4B/V4C Greeks, FIRST80 book objects (4.1.0-R) |
| **Warehouse scripts** (`apps/{nba,wnba,ncaab}-data/scripts/`) | Candle FIRST80 audits, barrier survival, EV, portfolio sims | Frozen 80→40 identities, path/barrier EV, bankroll sims |
| **`apps/research-api`** | Rust HTTP API | **MLB research-engine only** — not BBALL / not ROLLER |
| **Terminal today** | None for ROLLER | Must be built as research terminal over database + Research Objects |

**Critical gap:**

```text
ROLLER has:     database + PIT + FIRST80 objects + F_t + Greeks
ROLLER lacks:   HTTP API, universal Research Object runtime, generic path DSL,
                fees, EV, portfolio, jobs, vocabulary compiler
Warehouse has:  path EV, fees, portfolio, barrier ledgers (script-form, not a service)
Missing abstr.: Research Object contract (seeded in RESEARCH_OBJECT_MODEL.md)
```

BBALL1 is an **adapter/universe layer** over ROLLER + frozen warehouse bindings — not a TypeScript reimplementation, and not `db.research()` (raises).

---

## 1. Databases and warehouses

### 1.1 Existing Momento warehouse (read-only evidence)

| Sport | Path | Series |
|-------|------|--------|
| NBA | `Backtesting Suite/Data/NBA/2025-2026/warehouse/` | `KXNBAGAME` |
| WNBA | `Backtesting Suite/Data/WNBA/2025-2026/warehouse/` | `KXWNBAGAME` |
| NCAAB | `Backtesting Suite/Data/NCAAB/2025-2026/warehouse/` | `KXNCAAMBGAME` |

Layout: `raw/` → `normalized/` → `derived/` + `manifests/`.

Normalized assets (typical):

- `normalized/{sport}/candles_1m/*.parquet` — 1m YES bid/ask OHLC, integer **E4**
- `normalized/{sport}/games/*.parquet`
- `normalized/{sport}/markets/markets.parquet`
- PBP / trades / events as sport-specific

**Price unit:** integer E4 (ten-thousandths of a dollar). Candles are `CANDLESTICK_TOP_OF_BOOK`, not fills, not historical L2.

**Data caveats:**

- `Backtesting Suite/Data/WNBA` **manifests** were historically a DEMO FIXTURE; real candles live under the warehouse path after 2026-09-04 ingest.
- NCAAB Kalshi universe ≫ P5∩P5 PBP coverage (~16% MATCHED historically).
- Orderbook snapshots in ROLLER are **forward-only** (no historical L2 backfill).

### 1.2 ROLLER database (point-in-time layer)

| Item | Value |
|------|--------|
| Root | `ROLLER/` |
| Config | `ROLLER/roller.json` |
| DB version | `4.0.0-C` |
| Research objects | `4.1.0-R` |
| Storage | **CSV** under `ROLLER/data/{sport}/{season}/` (not SQLite/DuckDB) |
| Warehouse pointer | `ROLLER/config/sources.json` → `../Backtesting Suite/Data` |

```text
Existing warehouse (READ ONLY)
  → ROLLER ingest adapters
  → raw pointer + sha256
  → canonical CSV
  → derived D2D / team features / first80_triggers
  → public as_of choke point I(t)
```

**Sports in ROLLER V1 operational scope:**

| Sport | Season keys | NCAAB note |
|-------|-------------|------------|
| NBA | `2025-2026` (+ `2026-2027` declared) | — |
| WNBA | `2025`, `2026` | Split campaigns |
| NCAAB | `2025-2026` | Research D2D/features / FIRST80 default **`p5_vs_p5=1`** |

### 1.3 Declared ROLLER datasets (`roller.json`)

| Dataset | Role | Future info? |
|---------|------|--------------|
| `games` | Identity + scores + PIT timestamps | No (with care) |
| `pbp` | Monthly PBP CSV | Event-time availability |
| `kalshi_candles` | Monthly 1m candles E4 | Candle available_at |
| `kalshi_markets` | Settlement W | Masked until `result_available_at` |
| `kalshi_trades` | Trade **prints**, not fills | — |
| `kalshi_orderbook_snapshots` | Forward-only L2 | — |
| `first80_triggers` | Frozen FIRST80/T40 book | **Yes** — public `dataset()` refused |
| `team_features` | Pre-game rolling priors | — |
| `d2d_daily` | Day-to-day info states | — |
| `game_state_features` | Terminal-ish features | **Yes** — firewall |

**Observed on disk (NBA derived, 2026-09-07):** `team_game_features.csv`, `d2d_daily.csv`, `game_state_features.csv`. `first80_triggers.csv` is declared; presence depends on pipeline build.

### 1.4 Warehouse derived FIRST80 artifacts (outside ROLLER CSV)

Under `…/warehouse/derived/{nba|wnba|ncaab}/`:

| Artifact family | Examples |
|-----------------|----------|
| Execution audit (frozen identity) | `first80_execution_audit/` |
| Barrier survival ledgers | `first80_quarter_barrier_survival/`, `first80_p5_half_barrier_survival/` |
| Asked-six / path filters | `first80_asked_six_80_*` |
| Portfolio sims | `first80_q23_novapr_portfolio_sim/`, `first80_dual_sport_novapr_portfolio_sim/` |
| Fee / hedge research-day | `first80_realistic_exit_fee_audit_v1/`, `first80_*hedge*` |
| Parallel engines (not FIRST80 canon) | `dynamic_risk_engine_v*`, `momento_game_path_engine_v*`, `lebronner/` (FIRST75 archive), `superasi/` (rename of Lebronner; ROLLER +EV decomp) |

---

## 2. Tables / schemas (ROLLER)

Authoritative schema metadata: `ROLLER/config/schemas.json`.  
Identity: `ROLLER/meta/game_identity.csv`, `teams.csv`.

**Identity systems (do not invent a fourth):**

| ID | Meaning |
|----|---------|
| Production `GameId` | u128 SHA256 in `crates/kalshi/src/identity.rs` |
| Warehouse `game_id` | Same hash as hex |
| `event_ticker` | e.g. `KXNBAGAME-26JUN13NYKSAS` |
| `internal_game_id` | Readable alias `NBA_20251219_LAL_BOS` — must persist source IDs |

Crosswalk statuses: `MATCHED` / `UNMATCHED` / `AMBIGUOUS`. No silent upgrades.

---

## 3. Point-in-time functions

**Contract:** `I(t) = { x | available_at(x) < t }` (half-open).  
**Docs:** `ROLLER/docs/POINT_IN_TIME.md`.  
**Choke point:** `ROLLER/roller/point_in_time/filters.py` → `public_filter`.

| API | Module | Authority |
|-----|--------|-----------|
| `Roller.as_of` | `point_in_time/query.py` | Public factory |
| `Roller.dataset` | same | PIT table load; refuses future datasets |
| `Roller.observation` | → `state/observation.py` `assemble_observation` | **SoT for O_t** |
| `Roller.clock_snap` | → `state/clock_snap.py` | Last PBP ≤ snap under I(t) |
| `Roller.first80` | → `research/first80.py` `load_first80` | Masked book |
| `Roller.labels` | → `labels/engine.py` `build_labels` | L_{t→} only |
| `Roller.fundamental` | → `fundamental/estimator.py` | Prior-only F_t |
| `Roller.greeks` | → `v4b/` (+ optional V4C overlay) | Measurements ≠ O_t |
| `Roller.research` | raises `ResearchNotImplementedError` | Explicit stub |

Admin loaders (`roller.admin`) are unrestricted — **build only**, not research UI.

---

## 4. Authoritative research functions

### 4.1 FIRST80 / first touch / price lock

**There is no separate `price_lock` type.** The locked research object is **FIRST80** (and FirstReach(q) generalizations).

#### Inside ROLLER (research objects 4.1.0-R)

| Symbol | Path | Role |
|--------|------|------|
| `HIT80=8000`, `HIT40=4000`, `MAX_SPREAD_E4=1000` | `roller/research/quality.py` | Constants |
| `quality(...)` | same | Tradable-cross gate |
| `game_window(...)` | `roller/research/game_window.py` | `game_date` 16:00Z → +52h |
| `scan_ticker(...)` | `roller/research/first80.py` | FIRST80 + T40 scan |
| `build_first80_rows` / `write_first80` / `load_first80` | same | Book build + PIT mask |
| `settled_yes(...)` | same | Kalshi W (not box `home_win`) |
| Spec | `ROLLER/docs/RESEARCH_OBJECTS.md` | Normative |

**Definition (locked):**

```text
FIRST80 = first tradable yes_bid_close ≥ 80¢
          after a prior tradable close < 80¢
T40     = first later tradable yes_bid_close ≤ 40¢  (close path, not wick)
W       = Kalshi ticker expiration (result=yes or settlement_value_e4=10000)
One per event; same-timestamp multi-side → exclude / TIE_SAME_MINUTE
NCAAB FIRST80 corpora: p5_vs_p5=1 only
Candle path ≠ fill
```

#### Outside ROLLER (warehouse frozen identity — locked 2026-09-04)

| Role | Path |
|------|------|
| **Canonical scanner** | `apps/nba-data/scripts/nba_80_40_execution_audit.py` — `quality`, `scan`, `build_candidates` |
| WNBA wrapper | `apps/wnba-data/scripts/wnba_80_40_execution_audit.py` |
| NCAAB wrapper | `apps/ncaab-data/scripts/ncaab_80_40_execution_audit.py` |
| FirstReach(q) | `apps/nba-data/scripts/first75_slice_not40_given_w.py` — `first_tradable_reach` |
| Day lock doc | `docs/research/2026-09-04-FIRST80-RESEARCH-DAY-SUMMARY.md` |

**CONFLICT FLAG — dual FIRST80 homes:**

| Home | Status |
|------|--------|
| Warehouse audit scripts + `derived/*/first80_execution_audit/` | Historical frozen identities used by barrier/portfolio research |
| `ROLLER/roller/research/first80.py` | Intended PIT-aware reconstruction; must **not** silently diverge |

Dashboard rule: **do not pick one silently.** Adapter must declare which book is bound to a run (`warehouse_frozen_v1` vs `roller_4.1.0-R`) and fail if identities disagree under a reconciliation test.

**Asked-six (BBALL1-like mid-game slice):**

```text
ASKED_SIX = {Q2, Q3, H1_2, H2_1}
```

Defined in `ROLLER/roller/state/clock.py` and used in warehouse asked-six / dual-sport research. Closest named “BBALL1” universe in practice = NBA Q2∪Q3 + WNBA Q2∪Q3 + NCAAB P5 H1_2∪H2_1.

### 4.2 Path / stop / survival / terminal

| Capability | Authoritative location | Notes |
|------------|------------------------|-------|
| FIRST80→T40 close path | ROLLER `scan_ticker` + warehouse `scan` | Same rule family |
| Nested barriers 60/50/40 | `first80_quarter_barrier_survival.py` (NBA/WNBA), `first80_p5_half_barrier_survival.py` (NCAAB) | `first_close_touches`, identity halt |
| Gross path EV | `ev_stop_gross`, `ev_hold_gross`, `ev_touch_hold_gross` in barrier scripts | Often **fee_cents=0** |
| Γ_t trajectory on O_t | `ROLLER/roller/state/trajectory.py` | Not trading path EV |
| Generic stop-touch / arbitrary path DSL | **Absent** | Dashboard must not invent without a new versioned engine |
| Terminal YES/NO | `kalshi_yes_settled` / `expiration_result_yes` | Not box score alone |

### 4.3 EV / fees / returns

| Function | Path | Authority |
|----------|------|-----------|
| `quadratic_fee_e6(coef, contracts, price_e4)` | `nba_80_40_execution_audit.py` | Research fee estimate; **not** production `crates/risk` |
| `fees_for` / `summarize_trades` | same | Audit bookkeeping |
| Barrier EV helpers | barrier survival scripts | Gross +20/−40 style R |
| Slippage mix EV | `first80_q23_40_loser_slip20_ev.py` | Modeled loser mix |
| `fee_models.py` | `capture_program_v1/fee_models.py` | **Unit fork** (cents vs e4) — flag conflict |
| Production fees | `crates/risk/src/fees.rs` | Still `ZeroFeeModel` — **not** research SoT |

**ROLLER has no fee/EV/payout engine.** V4B `absolute_return` / market deltas are **path measurements**, not economic P&L.

### 4.4 Portfolio simulation

| Script | Role |
|--------|------|
| `apps/nba-data/scripts/first80_q23_novapr_portfolio_sim.py` | NBA Q2∪Q3 chronological bankroll |
| `apps/nba-data/scripts/first80_dual_sport_novapr_portfolio_sim.py` | NBA + NCAAB P5 H1_2∪H2_1 |
| `apps/nba-data/scripts/first80_dual_sport_portfolio_stress.py` | Overlap / correlation stress |
| `apps/ncaab-data/scripts/first80_p5_h12_h21_profit_likelihood.py` | NCAAB book + likelihood |

**Not BBALL1 FIRST80 portfolio SoT:** Game Path Engine v2/v4 portfolio modules, DRE portfolios.

**ROLLER has no portfolio simulator.**

### 4.5 Forward / OOS / train splits

| Source | Split |
|--------|-------|
| NBA/NCAAB audit `dataset_split` | IN_SAMPLE ≤2025-12-31; VALIDATION ≤2026-03-15; else OOS |
| WNBA audit | Overwrites dates (TRAIN ≤2025-10-31; VAL ≤2026-07-15) |
| Portfolio sims | Nov–Apr window projection (season analogs) |
| ROLLER | `as_of` / `end_of_day` for PIT — not the same as research train/OOS labels |

Dashboard must label TRAIN / VALIDATION / FORWARD / OOS separately and never merge unlabeled.

### 4.6 Fundamental / V4 Greeks

| Layer | SoT | Non-claim |
|-------|-----|-----------|
| F_t | `roller/fundamental/estimator.py` `estimate_fundamental` | Not truth, not edge |
| V4B numbers | `roller/v4b/measurements.py` | ExactRational; not O_t |
| V4C | `roller/v4c/` overlay | **Zero new numbers**; constructibility law |
| NOT_CONSTRUCTIBLE | `config/greek_v4c_registry.json` + docs | UI must show status, never coerce to 0 |

Reserved NOT_CONSTRUCTIBLE under current candle regime include: `microprice`, `order_book_imbalance`, `price_impact_lambda`, `signed_flow_lambda`, `psi_resilience`.

Legacy `roller/greeks/basis.py` stubs are **not** current SoT when V4A/V4B exist.

---

## 5. Backtest engines (inventory)

| Engine | Path | Use for dashboard? |
|--------|------|--------------------|
| Warehouse FIRST80 execution audit | `*_80_40_execution_audit.py` | Yes — identity |
| Barrier survival | `first80_*_barrier_survival.py` | Yes — path/survival |
| Asked-six path filters | `first80_asked_six_*` | Yes — conditional path studies |
| Portfolio sims | `first80_*_portfolio_sim.py` | Yes — portfolio page |
| Alpha decomposition | `research/first80_alpha_decomposition_v1/` | Research report, locked classification |
| Hedge / fee V1–V4 / hybrid | many `first80_*hedge*`, `a1_hybrid_hedge/` | Research-day; isolate |
| DRE v2–v7 | warehouse derived + scripts | **Not** FIRST80 canon |
| Game / path engines v1–v4 | `momento_*path_engine*` | Parallel; not FIRST80 barrier SoT |
| MLB research-replay FIRST01 | `crates/research-replay` | **MLB only** — never mix |
| `db.research()` | ROLLER | Stub — raises |

---

## 6. NBA / WNBA / NCAAB / P5 structures

| Dimension | Where |
|-----------|-------|
| NBA quarters Q1–Q4 | PBP + `clock_snap` / entry_slice |
| WNBA quarters | Same pattern; scan window may prefer `open_ts` |
| NCAAB halves → `H1_1` `H1_2` `H2_1` `H2_2` | `ncaab_pbp_align.entry_bucket` / ROLLER clock |
| P5 membership | `apps/ncaab-data/scripts/ncaab_pbp_espn_ingest.py` `P5_CODES`; ROLLER `config/conferences.json` |
| P5∩P5 FIRST80 freeze | `first80_p5_half_barrier_survival.load_frozen_p5_first80` (n≈721) |
| Full NCAAB FIRST80 | Execution audit / fee scripts (~thousands) — **not** BBALL1 default |

---

## 7. Existing APIs and frontends

| Surface | Serves | BBALL1? |
|---------|--------|---------|
| `from roller import Roller` | PIT Python library | Yes (library) |
| `apps/research-api` | MLB research-engine HTTP | **No** |
| `frontend/research-console` | MLB console | **No** |
| `frontend/nba-research-engine-v2` | Static GPE artifacts | Not FIRST80 SoT |
| `frontend/first80-*` | One-off audit UIs | Artifact viewers |
| ROLLER HTTP | **None** | Must be designed |

---

## 8. Duplicate or conflicting implementations (do not auto-resolve)

| # | Conflict | Guidance |
|---|----------|----------|
| 1 | ROLLER `scan_ticker` vs warehouse `scan` | Reconcile with identity tests; version the binding |
| 2 | Barrier survival triplicated per sport | Keep sport-specific; share formula, not silent merge |
| 3 | NCAAB full vs P5∩P5 | BBALL1 default = P5; full is separate universe flag |
| 4 | Fee e4 (`quadratic_fee_e6`) vs cents (`fee_models.py`) | Prefer audit + document units |
| 5 | Gross EV (fee=0) vs net fee audits | Label assumption on every result |
| 6 | Close-stop vs wick/low-stop | Primary = close ≤40; wick secondary |
| 7 | WNBA `open_ts` vs NBA `game_window_start` | Do not “unify” without re-freeze |
| 8 | Portfolio: Q23/dual-sport vs GPE/DRE | Asked-six bankroll = Q23/dual-sport |
| 9 | FIRST75 costed-as-80 (Lebronner) vs native FIRST80 | Separate research objects. SuperASI is the Lebronner rename and owns in-production EV stop-path decomp |
| 10 | MLB FIRST01 sticky bid vs basketball candle FIRST80 | Never share semantics |
| 11 | V3 `greeks/*` stubs vs V4B | Public API uses V4B |
| 12 | Docs mirrored in `docs/research/`, `research/`, warehouse derived | Prefer code + frozen parquet/CSV identity |
| 13 | `survive` ≠ `won` | Vocabulary must keep distinct concepts |

---

## 9. Data limitations (must surface in UI)

```text
CANDLE PATH ≠ EXECUTABLE FILL
OBSERVED TOUCH ≠ MAKER FILL
LOW PRINT ≠ TAKER STOP CONFIRMED
TRADE PRINT ≠ FILL
MEASUREMENT ≠ EDGE
F_t ≠ TRUE PROBABILITY
HISTORICAL SUPPORT ≠ FUTURE PERFORMANCE
NOT_CONSTRUCTIBLE ≠ 0
LIVE EXECUTION = FALSE (unless separate execution-validation framework)
```

Additional:

- No historical L2 → microstructure Greeks NOT_CONSTRUCTIBLE
- Possession-conditioned F not validated
- Generic barrier labels in `labels.json` are empty shells
- WNBA / NCAAB coverage and identity quality vary by season and MATCHED status

---

## 10. What the terminal must call (adapter sketch — not implemented)

```text
React UI  (ROLLER Terminal — not a FIRST80 strategy app)
  → Research API (new; not MLB research-api)
      → Vocabulary / Research Object compiler
      → ROLLER Python (PIT, O_t, F_t, Greeks, first80 as one object binding)
      → Warehouse research modules (barrier EV, fees, portfolio) via versioned bindings
      → Saved / Frozen / Locked-population store
```

**Phase 1:** explorer + Object Inspector over ROLLER (“What exists?”).  
**Phase 4+:** empirical path/terminal engines via explicit `definition_versions`.  
**Phase 7:** portfolio as consumer of Research Objects.

Do not place EV/portfolio math in TypeScript.

---

## 11. Vocabulary seeds (for future compiler — not a registry yet)

No versioned `research_vocabulary` registry exists today. Seed concepts that **must** map to existing math:

| Concept | Must NOT silently equal | Authoritative bind |
|---------|-------------------------|-------------------|
| `FIRST_PRICE_TOUCH` / FIRST80 | any price ≥ 80 without seen_below | `scan` / `scan_ticker` |
| `SURVIVE` / ¬T40 | `TERMINAL_YES` / W | barrier / T40 absence |
| `STOP` / T40 | wick-only touch | close ≤ HIT40 |
| `TERMINAL_YES` / W | box home_win | Kalshi settlement |
| `ASKED_SIX` | “mid-game” fuzzy | `{Q2,Q3,H1_2,H2_1}` |
| `CANDLE_1M` regime | BOOK / fill regime | V4C information regimes |

Ambiguous phrases (`big move`, `late`, `favorite`) must unresolved-clarify — never invent thresholds.

---

## 12. Recommended next steps

| Artifact | Path | Status |
|----------|------|--------|
| Phase 0 prompt | `docs/research/ROLLER_DASHBOARD_PHASE0_IMPLEMENTATION_PROMPT.md` | Spec |
| Research Object Model | `docs/research/roller_dashboard/RESEARCH_OBJECT_MODEL.md` | Done |
| Phase 0 execution | Authority, reconciliation, schema, vocabulary, adapters, API draft | **COMPLETE** — see `PHASE0_STATUS.md` |
| Phase 1 | Terminal foundation (“What exists?”) | **Blocked until Phase 0 accepted** |

**Do not start Phase 1 until Phase 0 is explicitly accepted.**  
Phase 1 first question: *What data exists at this point in time?* — not portfolio P&L.

---

## 13. Key document index

| Doc | Governs |
|-----|---------|
| `ROLLER/README.md` | Public `Roller` API overview |
| `ROLLER/docs/POINT_IN_TIME.md` | I(t) |
| `ROLLER/docs/RESEARCH_OBJECTS.md` | FIRST80 objects |
| `ROLLER/docs/STATE_MODEL.md` | O_t / labels |
| `ROLLER/docs/V4A_*.md` | F_t |
| `ROLLER/docs/V4B_*.md` / `V4C_*.md` / `ROLLER_V4_GREEKS.md` | Greeks constitution |
| `ROLLER/reports/roller_repository_audit.md` | Pre-V1 warehouse audit |
| `docs/research/2026-09-04-FIRST80-RESEARCH-DAY-SUMMARY.md` | Frozen FIRST80 day lock |
| `docs/research/FIRST80_*.md` | Hedge/fee research-day specs |
| This file | Dashboard archaeology map |

---

## 14. One-line principle for all subsequent work

```text
BUILD THE INTERFACE TO ROLLER, THE ROLLING EMPIRICAL DATABASE.
FIRST80 IS THE FIRST DEEP RESEARCH OBJECT IN BBALL1 —
NOT THE CONCEPTUAL BOUNDARY OF THE SYSTEM.

WORDS → VERSIONED VOCABULARY → RESEARCH OBJECT → EXISTING ENGINE
UI NEVER OWNS THE MATH
```
