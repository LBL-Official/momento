# NBA Bot 001 evidence report

Replay date 2026-09-22. Rules are `analysis/SELECTION_PROTOCOL.md`. Machine output is `analysis/replay_summary.json`. Protected-file hashes matched the source manifest before and after the replay. Confirmation outcomes were not opened.

`LIVE EXECUTION` is false. Nothing was submitted.

## Decision

`PROVISIONAL`. Candidate `q2`: the same 80/40 rule on the locked 2Q slice, conservative executable scenario.

`SELECTED_FOR_PAPER_TEST` was not assigned. The length-4 lower bound is below 1.5%, and the fill basis is `FILL_UNAVAILABLE`.

The 1.5% mean weekly net claim on the chosen candidate is `UNSUPPORTED`. The interval is not a snooping correction. These locks were already explored, which limits the claim even if a later bound had cleared.

| Candidate | Entries | Point mean | 90% lower bound (block 4) | Weeks at or above 1.5% |
| --- | ---: | ---: | ---: | ---: |
| union | 248 | 0.352439% | −0.285135% | 16 / 36 |
| q2 | 151 | 0.763762% | 0.170730% | 12 / 36 |
| q3 | 100 | −0.411118% | −0.741485% | 7 / 36 |

The 2Q lower bound is strictly above the union lower bound, so the protocol keeps `q2`. The 3Q bound is not. Block lengths 1 and 8 are sensitivity only. For `q2` they are 0.143393% and 0.406840%. Selection uses block 4, seed 604, 2,000 resamples, 36 Monday weeks.

The week-rate column is the observed count. It was not a prespecified test, so it is not a support claim.

## Layers

Candle-path theoretical and the conservative scenario are separate. Observed fills are `UNAVAILABLE`.

Conservative scenario, maker multiplier 1 because the `KXNBAGAME` maker multiplier is `UNAVAILABLE`. Entry only when the triggering close is 80 cents. A higher close is `INFEASIBLE_MAKER` (351 of 604 rows). Stop exit is the first later tradable YES bid close at or below 40, at that close, plus the taker fee. Every stop in this run resolved on that close (`FIRST_CLOSE_AT_OR_BELOW_40`: union 72, q2 38, q3 34). No stop used the post-entry minimum proxy. Settlement has no matched-order fee.

Five signals were `STALE_MARK` on the union (a bid older than 180 seconds) and were not entered. They were not marked at $0. Ending cash, q2: 2,587,171 cents. Union: 2,212,681 cents. q3: 1,704,601 cents. Starting cash: 2,000,000 cents.

q2 realized cents by phase: preseason 48,052; regular season 789,169; playoffs −138,435; finals −111,615.

Theoretical candle path (entry at the observed bid, exit at 40 when `t40`, else settlement): union ending cash 4,110,334 cents, 587 entries, 15 stale skips, 2 slot skips. Seven weeks have a missing mark, so that layer's lower bound is `UNAVAILABLE` and is not the selection bound. It is not a fill.

## Hedge

Diagnostic only. Not a ranking input. Opponent-YES fills credited: 0 (`FILL_UNAVAILABLE`).

Path counts on the 604 tape: 443 favorite closes at or below 42 after entry; 442 of those have a favorite close at or below 40 at the trigger print or on a later print; 1 stayed without that close and is the held-to-settlement path. A theoretical hedge fill was not added to any candidate's return.

## What this does not say

The bound does not make q2 a live rule. Prior exploration of the 604 lock remains. Warehouse order-book and tick history are absent. Ballhog, TK Ultra, and DRE Phase 5 did not supply an outcome artifact for this ranking.
