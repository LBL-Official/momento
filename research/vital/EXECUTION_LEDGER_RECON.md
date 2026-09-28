# Vital — MLB 001 Execution Ledger Recon

Dated: 2026-09-14.

Facts from the repository. Not a design essay. Not invented fills.

```text
ORDER  →  FILL / EXECUTION FACT  →  TRADE  →  REALIZED RESULT
```

Vital observes and records what already happened. It does not submit,
does not infer maker fills from candles, and is not a second OMS.

Do not edit `strategies/mlb`, `apps/trading-engine`, `crates/risk`,
`config/live.toml`, or `deploy/momento-live.service`.
Do not read `/dev/shm/momento-kalshi-live.json`.
Do not enable `VITAL_AWS_CONTROL` / `VITAL_ENABLE_CONTROL` for this slice.

---

## 1. Sources

| Source | Path / reader | What it actually holds | Authority |
| --- | --- | --- | --- |
| Host runtime | `/var/lib/momento/state/live-runtime.json` via `VITAL_BOT_RUNTIME_PATH` / `VITAL_BOT_STATE_DIR`. Parser: `ROLLER/roller/jump/dashboard/ledger.py`. | Atomic snapshot: `tracker.positions[]` with `fill_history[]`, lifecycle, `settlement_proceeds`, orders, risk occupancy. | **Authoritative for fills and logical trades** when readable. |
| Weekly snapshot | `/var/lib/momento/state/weekly-snapshot.json` | Bankroll / week bounds. No fills. | Observation for bankroll only. |
| Jump catalog | `research/jump/catalog/trades.jsonl` | Per-fill rows (`source=ledger` or `source=kalshi`). Current desk file: 139 rows, **0 reconciled**. | Observation. Duplicate-prone vs host (ID format mismatch). |
| Kalshi book | `research/jump/catalog/kalshi_book.json` | Snapshot counts + current positions. **No fill list.** | Not a fill source. |
| Bankroll history | `research/jump/catalog/bankroll_history.jsonl` | Account cents over time. | Account P&L, not per-trade. |
| Vital observe (before this ledger) | `ROLLER/roller/vital/observe.py` | Position **count** + aggregate day/week P&L. `/orders` is a stub. | Does not expose fills. |
| SSM inspect | `ROLLER/roller/vital/aws.py` `INSPECT_SHELL` | systemd, binary hash, journal, path existence. | Does **not** fetch `live-runtime.json`. This slice does not add that pull. |
| Strategy audit | `/var/lib/momento/state/audit.jsonl` | First80/81/89, GameLocked, StopTriggered. | Not fills. |
| In-memory tracker/risk audit | `crates/positions`, `crates/risk` | Order/fill/risk events. | Lost on restart. Not a Vital source. |

Engine persistence (`apps/trading-engine/src/live.rs`): there is **no
append-only host fill log**. Fills live inside `position.fill_history`.
The runtime file is overwritten atomically (~5s). That is why Vital
keeps its own ledger.

PNL formula already exists and must be reused, not recopied:

```text
crates/pnl PnlBreakdown::from_position
  ≡ ROLLER/roller/jump/dashboard/ledger.py realized_from_position
```

Realized P&L is **net of fees**. Gross is liquidation premiums +
settlement − entry premiums. Unrealized / live EV / Sharpe stay
`UNAVAILABLE`.

---

## 2. Domain types already on the host

### Fill (`crates/core/src/fill.rs` → `fill_history[]`)

| Field | JSON |
| --- | --- |
| `fill_id` | `FillId` (u128) |
| `venue_fill_id` | optional string |
| `client_order_id` | u128 |
| `venue_order_id` | optional |
| `quantity` | `{"qty": u32}` |
| `price` | `{"cents": u16}` |
| `premium` | `{"cents": i64}` |
| `fee` | `{"amount": {"cents": i64}, "kind": "Entry" \| "Liquidation"}` |
| `exchange_ts` | RFC3339 UTC |
| `side` | optional (`yes` / …) |

Kalshi mapping (`crates/kalshi/src/mapping.rs`): venue id =
`trade_id.or(fill_id)` → `FillId`. Live ingest ignores fills whose
`client_order_id` is unknown to the tracker.

### Position (`crates/core/src/position.rs`)

One `PositionId` per game. This is the logical trade.

Lifecycle: `Flat`, `Building`, `OpenPartial`, `OpenComplete`, `Holding`,
`StopTriggered`, `LiquidationActive`, `SettlementPending`, `Settled`.

Exits:

- `FeeKind::Liquidation` fills (reduce-only IOC)
- `settlement_proceeds` on `Settled`

There is no settlement clock on the position. Jump attributes settlement
P&L time from the last fill `exchange_ts`.

Open: `filled_quantity > 0` and lifecycle not `Flat` / `Settled`.

### Jump catalog row

| Field | Ledger-sourced | Kalshi-sourced |
| --- | --- | --- |
| `jump_trade_id` | SHA256 of ledger key | SHA256 of `ENV\|kalshi\|{id}` |
| `kalshi_fill_id` | 16-char host hash | UUID |
| `order_id` | usually null | UUID when present |
| `ticker` | usually null | Kalshi ticker |
| `qty` / `yes_price_cents` / `premium_cents` | often present | qty/price often present; premium often null |
| `fee_kind` | `Entry` / `Liquidation` | null |
| `result` | net cents on last fill of a closed position, else `UNAVAILABLE` | almost always `UNAVAILABLE` |
| `side` | usually null | usually null |

`jump_trade_id` is **one row per fill**, not a logical entry→exit trade.

---

## 3. The ten questions

1. **What constitutes an actual fill?**
   A venue execution recorded on a tracked MLB position
   (`fill_history` item), or a Kalshi `GET /portfolio/fills` row already
   persisted in the Jump catalog. A submitted order is not a fill. A
   candle print is not a fill. A position-count change is evidence, not
   a fill.

2. **What uniquely identifies a fill?**
   Host: Kalshi `trade_id` / `fill_id` → engine `FillId`
   (`fill_id` / `venue_fill_id`). Catalog: `kalshi_fill_id` or
   `jump_trade_id`. Ledger hashes and Kalshi UUIDs **do not match**
   today (0 reconciled rows). Do not invent a merge key.

3. **Can multiple fills belong to one logical trade?**
   Yes. The engine's logical trade is one `Position`. Several entry
   and liquidation fills belong to it.

4. **How are partial fills represented?**
   Separate fill rows. Order `quantities.filled` / `remaining`. Live
   ingest uses `PartialFill` for every entry fill.

5. **How are exits represented?**
   Liquidation fills and/or `settlement_proceeds`. Settlement is not a
   fill and has no own timestamp.

6. **How are open positions represented?**
   `filled_quantity > 0` and lifecycle ∉ {`Flat`, `Settled`}.

7. **What survives a runtime restart?**
   The host snapshot (if the file remains). Tracker/risk audit does
   not. Vital must persist an append-only ledger so history survives
   unread host and snapshot overwrite.

8. **Which source is authoritative?**
   Host `live-runtime.json` positions when readable.

9. **Which sources are merely observations?**
   Jump catalog, Kalshi book, bankroll history, Vital inspect
   heartbeat, systemd.

10. **Which facts cannot currently be established?**
    Resting orders; live EV; Sharpe; unrealized P&L; net P&L when fees
    are unknown; ticker on many ledger-only catalog rows; side on most
    catalog rows; SSM fill list; anything in
    `/dev/shm/momento-kalshi-live.json`.

---

## 4. Precedence locked for the ledger

```text
HOST_LEDGER readable  →  fills + position trades
host unread + CONFIRMED KXMLBGAME ticker → OPEN/PARTIAL candidate trades
JUMP_CATALOG ticker-null → fills only
neither + empty Vital ledger → OBSERVATION_UNAVAILABLE (null, not [])
neither + persisted Vital ledger → historical CONFIRMED
HOST_LEDGER readable with zero MLB positions → CONFIRMED []
```

Same venue id from both sources: one fill. Host wins quantity / price /
premium / fee. Catalog may supply ticker / `order_id` only when the
venue id matches exactly.

Vital may optionally observe Kalshi read-only through Jump
`sync_kalshi` (`POST /vital/bots/{id}/kalshi/observe`). GET does not
pull. Observe is not a submit. Vital does not fetch `live-runtime.json`
over SSM unless the operator explicitly enables host fetch.

---

## 5. Layers (do not collapse)

| Layer | Means | Existing / new |
| --- | --- | --- |
| ORDERS | Observed order objects | `/vital/bots/{id}/orders` — stub / observation only |
| POSITIONS | Current inventory | `/vital/bots/{id}/positions` — integer count |
| EXECUTION | Established fills | `/vital/bots/{id}/execution/fills` |
| TRADES | Entry → exit reconstructed from a host position | `/vital/bots/{id}/execution/trades` |
| PNL | Result only when facts suffice | on the trade; live EV stays `UNAVAILABLE` |
