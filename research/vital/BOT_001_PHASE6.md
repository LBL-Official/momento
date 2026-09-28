# MLB Bot 001 — Phase 6 One-Row-Per-Market Trades

Dated: 2026-09-14.

This file is Phase 6. It implements the trade-row contract locked in
`research/vital/BOT_001_PHASE1_RECON.md`.

```text
ONE ROW  =  ONE CONFIRMED MARKET
Host Position wins. Confirmed Kalshi ticker is the fallback.
```

## Grouping (FACT)

Authoritative grouping is the engine `Position` (one per game) when
`live-runtime.json` is readable.

```text
HOST_LEDGER readable                         → fills + position trades
host unread + CONFIRMED KXMLBGAME ticker     → OPEN/PARTIAL candidate trades
JUMP_CATALOG row with ticker null            → fill only (not grouped)
neither + no confirmed ticker + empty trades → OBSERVATION_UNAVAILABLE
```

Operator-accepted exception (2026-09-14): when the host is unread, Vital
may group fills that already have a CONFIRMED `KXMLBGAME` ticker
(`KALSHI_ACCOUNT`). That is not a merge of ledger hashes onto Kalshi
UUIDs. Ledger `JUMP_CATALOG` rows without a ticker stay fills. Those
rows are never CLOSED and never given invented PnL.

Optional read-only Kalshi observe: `GET /vital/bots/{id}/kalshi` (disk
book) and `POST /vital/bots/{id}/kalshi/observe` (Jump `sync_kalshi`,
PRODUCTION only). GET `/execution` does not pull. Observe is not a
submit and is not `ENABLE_LIVE_TRADING`.

## Contract fields

Integer cents and basis points. No `f64` money. PnL reuse remains
`crates/pnl` ≡ `realized_from_position`.

| Field | Closed + facts | Open / missing |
| --- | --- | --- |
| `market` | ticker | `UNAVAILABLE` |
| `game` | `{AWAY} @ {HOME} YES {SIDE}` from ticker | `UNAVAILABLE` |
| `entry_price_cents` | qty-weighted entry | `UNAVAILABLE` |
| `exit_price_cents` | qty-weighted exit | `UNAVAILABLE` if open |
| `amount_traded_cents` | entry premium | `UNAVAILABLE` |
| `amount_exited_cents` | liquidation + settlement | `UNAVAILABLE` if open |
| `bankroll_at_entry_cents` | in-week snapshot or history ≤ entry | `UNAVAILABLE` |
| `pct_bankroll_allocated_bp` | traded / bankroll | `UNAVAILABLE` |
| `pct_bankroll_returned_bp` | exited / bankroll | `UNAVAILABLE` if open |
| `pct_allocated_pnl_bp` | (exited − traded) / traded | `UNAVAILABLE` if open |

PARTIAL is open: observed liquidation fills stay on the existing
`exit_amount` fields; contract exit / returned / allocated PnL stay
`UNAVAILABLE`.

Bankroll rules:

- Factory `$50` is **not** bankroll-at-entry
- Current weekly snapshot is used only when entry is in that week
- Bankroll history after entry is future information
- Missing = `UNAVAILABLE`, never `$0` / `0%`

Ticker with no teams+side (`KXMLBGAME-TEST`) → `game` unavailable.
Two identity tickers on the same `game_id` → do not guess a side.

Package: `ROLLER/roller/vital/mlb_001/trade_row.py`,
`mlb_001/market.py`. Reconstruct stays in `reconcile.py`.
Frontend only renders: `frontend/vital-terminal` trade table.

## Acceptance checklist

- [x] One backend row per host Position / market
- [x] Catalog fills are not grouped into trades
- [x] Integer cents / basis points
- [x] Open / unread stay `UNAVAILABLE`, not `$0`
- [x] Bankroll-at-entry is observed, not factory
- [x] Existing `realized_from_position` reused
- [x] Fills remain drill-down
- [x] `apps/trading-engine` / `strategies/mlb` / Risk not edited
- [x] No `VITAL_AWS_CONTROL`

## STOP

```text
PHASE 6 COMPLETE
        ↓
STOP
        ↓
Do not start Phase 7+ (production / ITI / Jump client / hardening)
unless the operator explicitly asks.
```
