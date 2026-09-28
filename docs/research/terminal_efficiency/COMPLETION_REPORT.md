# Base Terminal Efficiency — Completion Report

**Object:** Base Terminal Efficiency (empirical measurement layer)  
**Semantics / schema:** 1.0.0  
**Code:** `base_te_v1.0.0`  
**Date:** 2026-09-09  

Base TE is **not** an ML model, not XIB/MCD, not a strategy, and not a fill.

---

## 1. What was inspected

Phase 0 recon: [RECON.md](RECON.md). ROLLER warehouse, I(t), `tradable_sequence`, `snap_events`, `run_path`, `settled_yes`, generic `_classify_exits` (not reused), XIB package (untouched).

## 2. What was implemented

Phases 0–6 of the isolated Base TE layer:

- Observation panel: one row per `(ticker, tradable yes_bid_close bar)` after first aligned game-state
- Path store per ticker
- WIN/LOSS books as **query parameters** (not baked WIN 90 / LOSS 40)
- Kalshi settlement YES / NO / MISSING
- Empirical counts (no alpha / edge / predicted probability)
- Versioned manifest

## 3. Files created

| Path | Role |
|------|------|
| `docs/research/terminal_efficiency/RECON.md` | Phase 0 |
| `docs/research/terminal_efficiency/DATA_CONTRACT.md` | Phase 1 |
| `docs/research/terminal_efficiency/README.md` | Phase 1 |
| `docs/research/terminal_efficiency/COMPLETION_REPORT.md` | this file |
| `ROLLER/roller/base_terminal_efficiency/*` | package |
| `ROLLER/tests/test_terminal_efficiency_pit.py` | Phase 2 |
| `ROLLER/tests/test_terminal_efficiency_exits.py` | Phase 4 |
| `ROLLER/tests/test_terminal_efficiency_settlement.py` | Phase 5 |
| `ROLLER/tests/test_terminal_efficiency_builder.py` | Phase 3 + reconciliation + empirical |

## 4. Files intentionally not changed

- `ROLLER/roller/research/first80.py` (imported `settled_yes` only)
- `ROLLER/roller/research_query/**`
- `ROLLER/tests/test_research_executor_phase4.py`
- `ROLLER/tests/test_population_expansion_phase6.py`
- `apps/terminal-efficiency/**`
- `frontend/roller-terminal/**`
- `crates/research-engine/**`
- live trading, Risk, FIRST01, W9
- XIB docs (`CURRENT_STATE.md`, `TERMINAL_EFFICIENCY_RECON.md`, `POINT_IN_TIME_DATA_CONTRACT.md`, model cards)
- `game_state_features.csv`

## 5. Data sources

NBA 2025–26 ROLLER canonical: `kalshi_candles`, `pbp`, `games`. `kalshi_markets.csv` **absent**.

## 6. Observation schema

See [DATA_CONTRACT.md](DATA_CONTRACT.md). Identity includes **ticker** (`BTE_{game}_{ticker}_{compact}_V{schema}`). Statuses: OBSERVED / DERIVED / UNAVAILABLE / AMBIGUOUS.

## 7. PIT contract

```text
available_at < observation_ts
```

Then `snap_events` on the filtered list (`event_timestamp <= t`). Equality excluded. Future score / price / PBP / vol / path / terminal cannot change entry-state fields.

## 8. Leakage tests

`tests/test_terminal_efficiency_pit.py` — pass.

## 9. Score-path definitions

Level = last I(t) scores. Path = `(0, …)` after each scoring increment. `0→10→20` ≠ `0→5→20`.

## 10. Volatility

`SCORE_PATH_VOLATILITY_V1`: sample stdev (ddof=1) of scoring increments; min 3; else UNAVAILABLE.  
`MARKET_PRICE_VOLATILITY_V1`: sample stdev of `yes_bid_close` first diffs; min 3 bars; recent = last 5 diffs if ≥3 else UNAVAILABLE.

## 11. Market-path definitions

LEVEL `yes_bid_close` E4 (`tradable_yes_bid_close`). Not a probability. Not a fill.  
DISPLACEMENT `K_t − K_0`. TRAVEL `Σ|ΔK|`. RANGE `max−min`.  
`50→60→50` → displacement 0, travel 2000 E4 (20¢).

## 12–14. WIN / LOSS / tie

Independent books wrapping `run_path`. `exit_ts > entry_ts`. First subsequent exit. Exact timestamp → `AMBIGUOUS` / `TIE_EXACT_TIMESTAMP`. Invalid side → `INVALID_SEMANTICS`. Game clock without snap → `DATA_REQUIRED` (not Reach-only). Not generic minute `TIE_EXCLUDED`.

## 15. Settlement

`settled_yes` import. Missing ≠ NO. No box-score inference. Current warehouse → `TERMINAL_MISSING`.

## 16. Missing-data behavior

UNALIGNED / UNAVAILABLE / TERMINAL_MISSING / DATA_REQUIRED / AMBIGUOUS / INVALID_SEMANTICS. Never silent 0 / false / NO.

## 17. Versioning / manifest

`SEMANTICS_VERSION` 1.0.0 · `CODE_VERSION` `base_te_v1.0.0`.  
Tree: `ROLLER/data/nba/2025_2026/derived/base_terminal_efficiency/1.0.0/`.  
Stale checksums → `DATA_REQUIRED`.

## 18. Test results

| Suite | Result |
|-------|--------|
| Base TE pit / exits / settlement / builder | **25 passed** |
| `test_research_query_engine` + harden + increment2 | **45 passed** |
| `test_research_executor_phase4` + `test_population_expansion_phase6` | **17 passed** |

Protected tests were not rewritten.

## 19. Reconciliation

Fixture: last tradable close matches `yes_bid_close`; team/opponent/total/diff match I(t)-visible PBP (half-open). Warehouse smoke: 1 ticker, 130 observations, all `TERMINAL_MISSING`.

## 20. Current coverage

| Item | Value |
|------|-------|
| League / season | NBA 2025–2026 |
| Warehouse games / candle rows / PBP rows | 1,362 / 6,165,183 / 780,137 |
| Full-panel build | **not run** (CLI exists; smoke `--max-tickers 1` → 130 rows) |
| Settlement file | absent |

```text
python -m roller.base_terminal_efficiency.cli build --league NBA --season 2025-2026
```

## 21. Known limitations

- Full dense panel not materialized in this session (warehouse load is large).
- `kalshi_markets` empty → no YES/NO terminals.
- On-disk candles lack quality-flag columns; `quality()` still applies.
- Game-clock exits need a snap function; without it the book is `DATA_REQUIRED`.
- Dashboard / five-screen UI not wired (isolation).
- `git_sha` is best-effort from repo root.

## 22. Explicit non-goals (confirmed)

No ML, XGBoost, SHAP, alpha, edge, predicted probability, EV, Kelly, Sharpe, fills, L2, ticks, fees, slippage, Phase 7, spread/O-U/team-total fabrication.

## 23. Isolation confirmation

| Surface | Status |
|---------|--------|
| XIB/MCD | untouched |
| FIRST80 | untouched (import `settled_yes` only) |
| research_query | untouched |
| frontend | untouched |
| live trading / Risk / FIRST01 / W9 | untouched |
| crates/research-engine | untouched |
| Phase 7 | not started |

## 24. Future ingestion

Spread, O/U, team totals, Polymarket TOB, L2, ticks: `DATA_REQUIRED` until canonical sources exist. Same architecture; do not invent them.
