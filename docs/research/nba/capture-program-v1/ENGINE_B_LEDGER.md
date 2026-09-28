# Engine B — execution ledger

Research schema for capture-program v1. Identifier `ENGINE_B_NBA_EXECUTION_LEDGER`.

Every FIRST-80 opportunity (taken or skipped) is an **episode**. Events
are append-only. Do not overwrite. Do not silently upgrade observation
status.

Primary object:

```text
EV_realized
```

Win rate is a diagnostic. Gross 80/40 path labels are not realized P&L.

---

## Observation status (hard)

Every quantity that could be mistaken for a fill, a fee, or a stop
execution carries exactly one of:

```text
OBSERVED      exchange or system recorded it
ESTIMATED     derived from candles, research fee formula, or proxy
SIMULATED     generated from an explicit assumption
UNAVAILABLE   not in the dataset; must remain unavailable
```

Promotion is forbidden:

```text
UNAVAILABLE ↛ SIMULATED ↛ ESTIMATED ↛ OBSERVED
```

A validator **FAIL** if any field is upgraded. Same-bar 1-minute candle
limitation is labeled `SAME_BAR_1M_LIMITATION`, never hidden.

---

## Episode

Required identifiers:

- `episode_id` (stable, unique)
- `event_id`, `ticker` when known
- `game_date` when known
- `engine_a_intent`: `ENTER` | `SKIP` | `UNAVAILABLE`
- `created_utc`

Optional link to frozen research: `first80_trade_id` =
`{event_id}|{ticker}|first80`.

---

## Event taxonomy

Append in causal order. Missing stages are explicit `UNAVAILABLE` events,
not omitted stages that look like they did not happen.

| `event_type` | Meaning |
| --- | --- |
| `MARKET_BEFORE_ENTRY` | Top of book / last print before order intent |
| `ORDER_SUBMITTED` | Client order id, side, price, qty, post-only flag |
| `ORDER_ACKNOWLEDGED` | Exchange ack or reject |
| `BOOK_DURING_REST` | Snapshot or delta while resting (or UNAVAILABLE) |
| `FILL` | Observed fill: price, qty, remaining, fee if provided |
| `NO_FILL` | Rest ended without a fill (cancel, expiry, never submitted) |
| `POST_ENTRY_PATH_SAMPLE` | Path after a fill (book or candle; status labeled) |
| `STOP_TOUCH` | First time a stop **trigger** is observed (bid ≤ 40, etc.) |
| `STOP_FILL` | Actual reduce/exit fill(s) |
| `NO_STOP` | Held without stop trigger through settlement window |
| `EXIT_EXECUTION` | Any non-stop exit (should be rare under Engine A) |
| `SETTLEMENT` | Contract resolution YES/NO |
| `NET_REALIZED_PNL` | Cash in minus cash out minus **observed or estimated** fees |
| `CONNECTION` / `ERROR` | Connectivity; never silently repaired |

`STOP_TOUCH` ≠ `STOP_FILL`. A wick on a 1-minute candle is at most
`STOP_TOUCH` with `ESTIMATED` status.

---

## \(EV_{\text{realized}}\) definition

For an episode with at least one `FILL`:

```text
EV_realized = cash_received
            − cash_paid
            − entry_fees
            − exit_fees
            − other_observed_fees
```

Each fee term has its own status:

- `OBSERVED` if the exchange reported it
- `ESTIMATED` only if labeled `RESEARCH_PUBLISHED_SCHEDULE_ESTIMATE`
- `UNAVAILABLE` otherwise — then `EV_realized` itself is `UNAVAILABLE`
  or explicitly `PARTIAL`

Do not report theoretical +1R/−2R as `EV_realized`.

Gross research R-units remain:

```text
survive close-path 40 → +1 R
hit close-path 40     → −2 R
EV_gross = 1 − 3q
```

Those are **path labels**, stored separately from `EV_realized`.

---

## Leakage

- Decision timestamps ≥ feature timestamps for any research derived from
  the ledger.
- Settlement may be used only as an outcome after the path is classified.
- Do not use future fills to rewrite earlier `NO_FILL`.
- Paper/unarmed episodes may be all-`UNAVAILABLE` for L2 and private fills.
  That is valid.

---

## Schema files

JSON Schema: `apps/nba-data/scripts/capture_program_v1/schema/episode.schema.json`

Validator: `apps/nba-data/scripts/capture_program_v1/validate.py`

Warehouse episodes: `.../momento_capture_program_v1/episodes/`

This milestone ships the schema, validator, and empty episode store. It
does not subscribe to Kalshi WebSocket.
