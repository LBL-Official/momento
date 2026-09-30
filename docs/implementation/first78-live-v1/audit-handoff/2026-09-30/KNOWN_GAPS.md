# Known gaps (challenge these)

## Unresolved owner decisions (block ARMED)

See `docs/implementation/first78-live-v1/UNRESOLVED_CHECKLIST.md`.

- `emergency_floor_cents` unnamed. Replay `Some(1)` in `strategies/nba/tests/live_v1.rs` is **TEST_ONLY**, not policy.
- Session boundary / 8-trade count unnamed (shadow: Los_Angeles day, increment on admit).
- Entry reprice timing/lifetime unnamed (shadow 1000 ms).
- Deterioration comparator unnamed (shadow: any opponent mid2 above post-trigger low).
- Hedge timeout / retry limits unnamed.
- Exposure / drawdown limits unnamed.

## Engineering blockers

- NCAAB 2026–27 P5 manifest `EVIDENCE_INCOMPLETE` (`research/vital/bots/nba-001/ncaab/`).
- `FRACTIONAL_FILLS_UNSUPPORTED`. Host MLB journal still records `fill_fractional_unrepresentable`.
- Production orders compiled out (`PRODUCTION_ORDERS_COMPILED=false`). Deployed build has **no** submission adapter.
- ESPN mappings file is an empty array; name-join is refused.
- V1 supervisor not installed. Host remains FIRST78_67 SHADOW.
- Host `execution_contract.json` digest ≠ repo `execution_contract.json` digest.

## Retirement

MLB/WNBA `momento-live.service` still **Live**, **enabled**, `order_submission=enabled`. Heartbeat `open_*=0` is not a signed inventory. Stop **BLOCKED**. Sole-bot baseline **not** asserted.

## Defects / unsupported behavior to probe

- After a refused/unsent hedge, `manage` can enqueue a replacement while residual remains (tests settle only after `emergency`).
- V1 `Complete` trusts caller P&L + reconciliation id once orders look settled — not live cash-flow proof.
- Host `ROUTE_CONFLICT` (series index 3 vs market 0) remains on FIRST78_67.
- Systimo projection is UNAVAILABLE until `v1_control_room.json` exists (V1 not running).
- Performance bounds unpublished.
- Linear/Sunsama/Drevo: observe-only; down must not block. Delivery **not CONNECTED**.

## Release blockers (not a date)

1. Owner names price protection and the other blanks.
2. Signed whole-account recon + sole-bot after MLB/WNBA drain.
3. Reviewed V1 shadow deploy (production still compiled out) + hash compare.
4. P5 evidence or accept NCAAB-blocked.
5. Fractional fill story.
6. Genuine-signal canary — not a synthetic production order.
