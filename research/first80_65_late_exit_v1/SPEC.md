# FIRST80→65 late-game exit comparison V1

Research only. `LIVE EXECUTION = FALSE`. Candle path ≠ fill.

## Authoritative baseline

| Field | Value |
| --- | --- |
| Strategy | FIRST80 entry, 65¢ stop, else settlement |
| Universe | Choosin Texas derived four |
| N | 936 |
| Membership | NBA Q2 314, NBA Q3 290, NCAAB H1_2 193, NCAAB H2_1 139 |
| Ledger | `research/first80_asked_six_chatgpt_export/first80_asked_six.csv` |
| T65 touches | `research/choosin_texas/t60_band/touches.json` |
| Paired reconstruction | `ROLLER/roller/choosin_texas/paired_replay.py` |
| Locks | `ROLLER/roller/choosin_texas/locks.py` / `docs/research/lebronner/TABLES.md` |
| Entry signal | Minute-close `yes_bid` first touch ≥ 80¢ (ledger `timestamp`) |
| Observation basis | Historical candle `yes_bid_close` path |
| Stop lock | 421 T65 stops, 515 survivors, 185 SETTLEMENT_YES∧T65 |
| Date range | game_date 2025-10-10 … 2026-06-13 |
| Authorized split | IN_SAMPLE ≤2025-12-31; VALIDATION ≤2026-03-15; else OOS |

Nominal economics at an exact 80¢ entry: settlement +20¢ (+25% on capital); exact 65¢ exit −15¢ (−18.75% on capital). Actual modeled entry/exit prices are used when they differ. A threshold crossing is not a fill at the threshold. “Did not stop” is not a win; settlement is joined from the ledger.

NBA windows stay Q2 and Q3. NCAAB windows stay H1 second 10 (`H1_2`) and H2 first 10 (`H2_1`). Sports stay separate. Combined view is derived and labeled.

## Frozen candidates (identical entries)

- **P0** — Baseline: existing 65¢ path stop, else settlement.
- **P1** — Partial at 6:00 remaining: close 50% of still-open size at the first eligible observation at/after final regulation 6:00; keep 65¢ stop and settlement on the remainder.
- **P2** — Full exit at 6:00 remaining.
- **P3** — Full exit at 3:00 remaining.

NBA final regulation period = Q4 (period 4). NCAAB = H2 (period 2). Timed marks are absolute clocks, not a scaled conversion.

### Precedence and mechanics

1. Retain the baseline 65¢ stop before each timed intervention.
2. If `t65_ts` is before the timed mark, the trade is already flat; timed policy equals P0.
3. Timed exits apply to every still-open position, including eventual winners.
4. Observation: first warehouse candle with `available_at ≥` the first PBP stamp where `period == final` and `remaining_s ≤ mark`. Missing mark or missing bar → timed exit `MARK_UNAVAILABLE` / `PRICE_UNAVAILABLE`; that trade falls back to P0 for the timed leg.
5. Integer contracts: timed half uses `qty // 2`; remainder is `qty - timed`. Never oversell.
6. Duplicate exits forbidden. Residual after P1 may still stop at 65 or settle.
7. Overtime: timed marks are regulation-only (Q4/H2). Stops in OT remain on the residual path. Missing regulation marks do not invent OT timed exits.
8. Gap through 65¢: record the observable first `yes_bid_close ≤ 65`, not a forced 65¢ fill.

Candidates are frozen before comparative ranking. No grid search over clocks, stops, or exit fractions.

## Output layers

- **A. Historical price-path comparison** — candle proxies; labeled `CANDLE_PATH_NOT_FILL`.
- **B. Execution-aware replay** — inventory only. Depth, fees, fills, queue: `UNAVAILABLE` on this cohort (see execution validation diagnostics). Achievable execution returns stay `UNAVAILABLE`.
- **C. Hypothetical stress** — among P0 losers: 80% ordinary modeled stop; 20% replaced with −45% of invested capital (44¢ exit at exact 80¢ entry). Scenario inputs, not measured facts. Not combined with invented slippage.

## Sizing

- Start bankroll $20,000 (configurable).
- Each entry: 6% of batch-start bankroll as entry premium.
- Update basis only after 10 completed trades (partial exits are not completions).
- Chronological by entry timestamp. Cash constrained. Existing positions keep original quantity.
- Historical chronology reported in full. A 160-trade / 16-batch window is the first 160 completions when available; not cherry-picked. Resampling, if any, is separately labeled and preserves game/day dependence.

## Selection rule

Whether earlier exposure reduction improves net economics and downside enough to justify surrendered upside. Status must be one of:

`BASELINE PREFERRED` | `CANDIDATE FOR PROSPECTIVE VALIDATION` | `INSUFFICIENT EXECUTION DATA TO SELECT`

Do not claim an optimal live policy from a small in-sample improvement.

## Absolute

Do not edit `first80.py`, live FIRST01/80/81/83/89, `book.json`, warehouse Phase 21, W9, `momento-live.service`, or `VITAL_AWS_CONTROL`. Do not open sealed Austin confirmation cohorts.
