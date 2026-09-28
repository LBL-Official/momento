# MLB 001 reuse matrix

NBA Bot 001 does not copy the MLB worker and does not inherit MLB defaults. The rows below are the pieces a future NBA policy adapter would call. Nothing in this matrix deploys a process or submits an order.

| Piece | MLB location | Reuse | NBA difference |
| --- | --- | --- | --- |
| Series discovery | `apps/trading-engine/src/live.rs` (`MLB_SERIES_TICKER = KXMLBGAME`) | Same engine, different series constant | NBA series is `KXNBAGAME`. Do not point discovery at `KXMLBGAME`. |
| Strategy plugin | `strategies/mlb` | Plugin boundary only | Do not copy the worker. Do not inherit 80/81/89. NBA entry in this policy is an 80 close, stop at the first later close at or below 40. |
| Risk configuration | `crates/risk` `RiskConfig::mlb_paper_experimental` | Risk types and the approve/reject gate | MLB paper defaults are 12.5%, max entry 83, bankroll snapshot $50, max 5. NBA research sizing is 4% of the 2,000,000-cent research mark, entry close 80, max 5 lifecycles. Those numbers stay in `policy.json`, not in the MLB factory. |
| Orders and positions | trading-engine order and position types | Same types behind an adapter | Client order id, market, side, price, quantity, and risk decision id stay required. Unknown state reconciles. It does not retry into a second position. |
| Vital package | `ROLLER/roller/vital/mlb_001` | Pattern for an isolated package later | This phase does not add `roller.vital.nba_001` and does not register a second submitter. |
| Disk ledger | `research/vital/bots/mlb-001/execution/` | Not read by NBA routes | NBA sessions do not retrieve these artifacts. Quad 4 and `/vital/bots/mlb-001` remain the MLB path. |
| Host unit | `deploy/momento-live.service` | Not reused as an NBA host | Do not start, stop, or reconfigure it. Do not set `VITAL_AWS_CONTROL`. No `aws001` unit is invented. |

Shared account cash, if both bots were ever live, would need account-level accounting so two bots cannot spend the same collateral. That accounting is not built here. Journals, order tags, and deployment targets stay separate.

The Quad 1 desk binds to the Momento shell on `:5190` and `/momento/execution/nba/*` on `:8791`. It does not open Vital `:5180` and it does not add a port.
