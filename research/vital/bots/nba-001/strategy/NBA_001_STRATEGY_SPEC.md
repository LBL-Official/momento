# NBA Bot 001 strategy specification

Version `nba-001-v0`. Policy sha256 `18338c397f4b95af917c0d9b1e8c9f6e99e66ddb0b486c3a42f17d1d7161ec1a`.

Decision status: `PROVISIONAL`. Candidate: locked 2Q slice, conservative 80/40 scenario. The 1.5% mean weekly net claim is `UNSUPPORTED`. Fill basis: `FILL_UNAVAILABLE`. `SELECTED_FOR_PAPER_TEST` is not assigned. `LIVE EXECUTION` is false. This desk does not submit.

Canonical id `nba-001`. Alias `nba-first80-001`. Display name NBA Bot 001. Series `KXNBAGAME`. Machine rules: `strategy/policy.json`. The hash above is the sha256 of that file's bytes.

## Source manifest

Recorded in `analysis/SOURCE_MANIFEST.json` before ranking. Confirmation outcomes were not opened (`SEALED_UNSPENT`, A N=97, B N=70).

| Path | sha256 |
| --- | --- |
| `ROLLER/roller/choosin_texas/locks.py` | `5c0a1e5f21e5897f8fb3f4b50c18c51c6199e99e9b02ba9014ed1572a63c34b0` |
| `ROLLER/roller/choosin_texas/locks_asked_six.py` | `0339d8b867764d556485c16432b37ddea7aec7e8c3975d3d591e51e5cbb1ae6a` |
| `ROLLER/roller/choosin_texas/locks75.py` | `1297d3a7a61ca8b25840998131de8c8628a79a613be4e769c44c0805f08385bb` |
| `ROLLER/roller/choosin_texas/locks77.py` | `0c4a09cff68ba226aec012c7bd21d11990b3d5e091708d388cd1b62e81841797` |
| `ROLLER/roller/choosin_texas/locks81.py` | `50b400fbe27d492047a03febfdd8c0520fd2e79dba52f6e50d3566e208c70567` |
| `ROLLER/roller/choosin_texas/locks83.py` | `11b37736b4859f365284a6d71be7369ca2c541d3064c025b332e9fac29a6be98` |
| `ROLLER/roller/austin/locks.py` | `05dca042db7d7957fc0cd910b71afce23d9e591e172f8722b10a48a1c363bc1a` |
| `ROLLER/roller/nba_8040_reverse_features/locks.py` | `9cad4c35fd20cae3cde33eabf0654aa8004d42cba79cb0ed6e04e6e7ddb50213` |
| `research/choosin_texas/library/nba_2q_regular_8040_1lot_2026_27/book.json` | `4da5fdd3a48d2a5513ab6e9452657a790514fbef389a05d0385cfaba009b8cf6` |
| `research/austin/experiments/AUSTIN_CONFIRMATION_GATE_V1/MANIFEST.json` | `1669c236defa15b2b4362b8033269a753336000a1e115f0890baec0a4fbdffad` |
| `research/austin/experiments/AUSTIN_CONFIRMATION_GATE_V1/confirmation_cohort_audit.json` | `0698c43671897e974afbc241b4850e6bd0b630831d8d31ca19f83f192d999477` |
| `ROLLER/roller/research/first80.py` | `ba895f677938b8e1a33c2eb5d5a9835e8312a007ad207bcfee25f3f32eecb44f` |
| `deploy/momento-live.service` | `e405d99a39e623fbf6417956570ae782f5de78d657b27674cf8097a4b536f8de` |

`research/vital/bots/mlb-001/` tree sha256 `31602ac1adfe73b3e233ee1cc8ee1c7cd01e651d6e9d193b49a52a3ead91d3a8` (22 files). That tree is not an NBA input.

## Cohorts

Ranking tape: NBA 2Q∪3Q FIRST80, N=604, S=450/604, window 2025-10-10 through 2026-06-13. Inside it: 2Q N=314, 3Q N=290. The provisional candidate uses the 2Q rows only.

`nba_2q_regular` is N=280, S=218/280, dates 2025-10-22 through 2026-04-12, `tape_season` 2025-26, `measure_season` 2026-27. Those rows are not 2026–27 games and are not pooled into 604.

Out of the pool: asked-six 1182, derived four 936, NBA FULL 1230, jump-filtered 1208, path-FE, and the sealed confirmation sets.

## Observable

The signal is one one-minute tradable YES bid close at or above 80 during the slice. The live wording of this rule waits until that close exists. A close above 80 does not prove a maker fill at 80. In the conservative scenario that close is `INFEASIBLE_MAKER`. The stop is the first later close at or below 40, sold at that close, not at 40 when the close gapped through. That print is still not a fill.

## Sizing and slots

Research bankroll 2,000,000 cents. At a decision, equity is settled cash plus reserves plus open YES marked at the latest tradable YES bid at or before the timestamp. A missing bid is `MARK_UNAVAILABLE`. A bid older than 180 seconds is `STALE_MARK`. Either blocks the entry and is never stored as $0.

Expenditure cap is 4% of equity. Contract count starts at `budget // entry_price` and falls until notional plus entry fee fits the cap and free cash. One contract that does not fit is a skip. At most five lifecycles. `pending`, `partial`, `unknown`, `open`, and `working` occupy a slot. One entry per game. Same-timestamp signals sort by `game_id` UTF-8 bytes. No re-entry.

## State transitions

| From | Event | To |
| --- | --- | --- |
| flat | eligible close, slot free, mark fresh, one contract fits | working entry |
| flat | missing or stale mark, full slots, or cash short | flat, signal skipped |
| working entry | maker acknowledgement not observed | unknown, slot still occupied |
| working entry | candle-path entry assumed in research replay only | open |
| open | first later close at or below 40 | working exit |
| open | no such close | open until settlement |
| working exit or open | terminal fill, cancel, or settlement | flat, slot released |
| open | hedge attempt on the same game | same lifecycle, not a new slot |

Unknown, partial, and pending are not flattened by a retry. New exposure stops until reconciliation says the order was found, not found, or is still ambiguous.

## Fees and fills

Selection fee is the Kalshi schedule read 2026-09-22: model fee rounded up to $0.000001, then non-direct-member cash aligned up to the next cent. Maker multiplier for `KXNBAGAME` is `UNAVAILABLE`. The bound uses multiplier 1. Settlement is not charged a matched-order fee. Half-away rounding is not the venue rule and is not this policy.

Three layers stay labeled: candle-path theoretical, conservative executable scenario, observed fills `UNAVAILABLE`.

## Systems

This specification is the decision record for the provisional candidate. Choosin Texas and Austin supply the locked 604 tape and are not rescanned. Ballhog, TK Ultra, and DRE are monitoring contracts on this pass: no stored outcome artifact entered the ranking, and DRE Phase 5 is `NO_POLICY_FROZEN`. Path-FE, confirmation A/B, asked-six, and the derived four are unused. Vital MLB 001 is a reference implementation on another series. It is not this bot.

## Failure policy

This runtime is `NOT_DEPLOYED`. `execution_authorized` is false. A future adapter would reuse the existing engine, risk, order, and position types. It would not copy the MLB worker and would not inherit 80/81/89 or 12.5% as NBA defaults. If an order state is unknown, the adapter stops new exposure and reconciles. It does not invent a fill. It does not start `momento-live.service`.

## October 3

`testing/OCTOBER_3_PROTOCOL.md` is registered before any October 3 outcome. The 2026-09-22 lookup did not find a `KXNBAGAME` slate for that date. Missing schedule and markets stay `UNAVAILABLE`. The run does not submit.

## Conclusion

The prespecified 90% lower bound on the conservative 2Q book is 0.170730%, below 1.5%. The point estimate is 0.763762%. The mean target is unsupported. Fills were not observed, so the candidate stays a provisional paper specification on this desk and is not armed.
