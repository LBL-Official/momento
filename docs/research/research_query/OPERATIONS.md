# Generic Entry operations

`operation_semantics_version = 1.1.0`

Candle-close language only. **CANDLE PATH ≠ FILL.** Never high/low, ticks, or L2.

Existing Touch operations (First / Second / Third / Fourth / Nth) are unchanged: prior tradable `yes_bid_close` < P and current ≥ P. Period and clock are post-event PBP snap filters (Interpretation A). Untradable bars neither create nor reset crossings.

The **nine** operations below were previously `OPERATION_REQUIRED`. They now execute on the existing full-scan engine. Indexes must reproduce these detectors; they must not redefine them.

| Op | Class | Candle-close rule | Canonical observation |
| --- | --- | --- | --- |
| Cross | Event | UP: prior < P ≤ current; DOWN: prior > P ≥ current; default BOTH | First matching cross (v1) |
| Break | Event | UP: prior < P and current > P; DOWN: prior > P and current < P | First matching break. `79→80` is Cross, not Break |
| Reversion | Event | Cross P, then later cross back to the original side (ordered). `79→81→80` is not complete | Event 2 timestamp |
| Bounce | Event | Up: prior < P, current ≥ P, next < P. Down: prior > P, current ≤ P, next > P | Confirmation-candle (`next`) timestamp |
| Recovery | Event | Adverse excursion away from P, then return cross. Equality at P does not invent a side | Return-cross timestamp |
| Above | State | current > P (equality false) | First eligible tradable bar |
| Below | State | current < P (equality false) | First eligible tradable bar |
| Maximum Touch | Extremum | running max of tradable close over the full game/ticker series ≥ P | First bar where running max ≥ P; then snap + period/clock |
| Minimum Touch | Extremum | running min of tradable close over the full game/ticker series ≤ P | First bar where running min ≤ P; then snap + period/clock |

## Bounce

`next` is the next tradable candle from `tradable_sequence()`, not the next raw CSV row.

- `79→80→79` YES; `81→80→81` YES; `79→81` NO; `79→80→81` NO
- Missing next tradable bar → `UNCONFIRMED`, not a bounce
- UI direction up/down restricts approach; omitted = BOTH

## Recovery

Anchor: AND with a prior entry → that entry bar. Standalone → first tradable close.

- `anchor_close > P`: adverse = later close < P; recovery = later cross back to ≥ P
- `anchor_close < P`: adverse = later close > P; recovery = later cross back to ≤ P
- `anchor_close == P`: no side. Standalone Recovery is INVALID unless an explicit direction is supplied

Direct move to P without an adverse excursion does not count.

## Exit WIN / LOSS

Tagged drafts (`outcome: win|loss` or `win_hold` / `loss_hold`) evaluate two books independently on bars strictly later than entry. The earlier timestamp classifies `WIN_EXIT` or `LOSS_EXIT`. Same-minute WIN and LOSS → `TIE_EXCLUDED`. Empty side cannot fire. Hold-to-expiration uses Kalshi settlement only.

Untagged legacy path conditions keep `path_true`.

WIN prices may not be under the first entry `priceCents` (`priceFrom` if band-only). LOSS prices may not be over it. Equality is allowed.

Path WIN% uses classified `WIN_EXIT` + `LOSS_EXIT` only. `TIE_EXCLUDED` is not in that denominator. Terminal YES% uses `yes / terminal_available`; missing W is not NO and is not N.

## Terminal Efficiency vs official W

Base TE scopes reported N (leading means `point_differential > 0`; missing score fails closed). TE WIN/LOSS uses exact-timestamp equality (`AMBIGUOUS`). Generic tagged exits use calendar-minute ties (`TIE_EXCLUDED`). Same path can therefore classify differently.

Official W is an overlay (FIRST80 `expiration_result_yes` + asked-six CSV W + binary complement), not a box score and not path WIN. Hold-YES fires only when neither path barrier hit. An earlier `LOSS_EXIT` is not overwritten by later settlement YES.

## Exit-path operations (post-entry)

Post-entry, tradable `yes_bid_close` only. Bars are strictly later than the entry bar. No high/low, ticks, L2, or fills. **CANDLE PATH ≠ FILL.**

| Family | Locked rule | Timestamp |
| --- | --- | --- |
| Bounce | Same geometry as entry Bounce: up `prior < P ≤ current` and next tradable `< P`; down mirrored. Missing next = does not fire | Confirmation (`next`) bar |
| Revert | Same as entry Reversion: cross P, then later cross back to the original side. `79→81→80` is not complete | Event-2 bar |
| Maximum Move | First post-entry bar where running max(close) ≥ P | That bar |
| Minimum Move | First post-entry bar where running min(close) ≤ P | That bar |
| Never Reach | Complement of Reach: no later close crosses P. Resolves at hold-to-settlement if present, else last post-entry tradable bar. Does not fire mid-path on a miss | Resolve bar / settlement clock |

On close-only series, Maximum / Minimum Move coincide with Reach / Drop-to on a single barrier. Named ops still execute; they are not hidden aliases.

`prior` for Bounce / Revert / Never Reach starts as the entry close. Untradable bars are skipped (`tradable_sequence()`).
