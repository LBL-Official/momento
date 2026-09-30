# FIRST78 Live V1 — decision register

Policy: `MOMENTO_FIRST78_LIVE_V1`.
Contract: `research/vital/bots/nba-001/strategy/execution_contract_v1.json`.
This is not FIRST78_67 `execution_contract.json`.

## Resolved this session

| Decision | Status | Record |
|---|---|---|
| Drevo / Positman | RESOLVED | Research observations only. `UNAVAILABLE` when unread. They never block or change admissions, hedges, or exits. |
| 25¢ | RESOLVED | Opponent midpoint trigger from hedge-working or recovery. Sells residual original A YES on the taker-capable path. Not a 25¢ original limit. Not the successor of `EMERGENCY_DIRECT_EXIT`. |
| Capital | RESOLVED | Authenticated reconciled Kalshi equity only. V1 does not read `batch.rs` `REFERENCE_INITIAL_CENTS` or config `capital.reference_capital_cents`. `$20` / `$20,000` are examples. |
| Epoch | RESOLVED | Frozen 6%. Resize only `01:00–03:00` America/Los_Angeles after ≥10 final completions. |
| Windows | RESOLVED | NBA Q3 only. NCAAB H2 first ten minutes. Event-wide first midpoint ≥78. Incomplete history disqualifies. No window re-entry. |
| Entry | RESOLVED | 78→82 post-only. Cancel remainder at selected mid ≥86 or eligibility end. `SIZE_BELOW_MINIMUM` never rounds up. |
| Hedge | RESOLVED | B mid ≥36 → cancel A remainder → recon → post-only B YES @ 35 for reconciled unhedged A. Recovery ratchet down only. |
| Residual | RESOLVED | `paired = min(A,B)`, `residual = max(0, A−B)`. Overhedge is an integrity incident. |
| Production send | RESOLVED | Compiled out. `FRACTIONAL_FILLS_UNSUPPORTED` blocks ARMED. |

## Unresolved owner inputs (block ARMED)

| Field | Why it stays blank |
|---|---|
| `emergency_floor_cents` | Owner-named price protection. Tight can leave exposure; permissive can realize a large loss. Replay `Some(1)` is not policy. |
| Session boundary / 8-trade count | Shadow uses Los_Angeles calendar day and increments on admit. Owner has not named the count. |
| Entry reprice timing / lifetime | Shadow uses 1000 ms. |
| Deterioration comparator | Shadow: any opponent mid2 above the post-trigger low. |
| Hedge timeout / retry limits | Not named. |
| Exposure / drawdown limits | Not named. |

## Engineering (not an owner constant)

NCAAB both-teams P5 for 2026–27 is `EVIDENCE_INCOMPLETE`. See `research/vital/bots/nba-001/ncaab/P5_EVIDENCE.md`. Missing evidence blocks NCAAB admission. Do not guess inclusion.
