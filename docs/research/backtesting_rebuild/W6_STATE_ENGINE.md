# W6 — Canonical MLB State Engine

**Status:** IMPLEMENTED (research / backtesting infrastructure)  
**Grant:** 2026-08-26  
**Crate:** `momento-research-state`  
**CLI:** `momento-research-w6 --reconstruct`  
**Not:** W7 price-path packaging, FIRST01 replay, outcome labeling, ML, execution simulation, Kalshi network.

---

## Purpose

W6 is the single authoritative MLB **game-truth** layer for downstream research.

```
raw PBP
  → canonical ordered game events (W2/W3)
  → canonical pre-event state
  → event transition
  → canonical post-event state
  → next state
```

A consumer may ask “what exactly was the game state at timestamp T?” and receive only information that was knowable at T.

W5 owns event ↔ market **synchronization**. W6 does **not** duplicate that join. W6 exposes `state_at_or_before(T)` so W5/W7 can attach a market observation at T to the canonical baseball state at/before T.

W7 will join:

```
GameId → MarketId → market observation at T
  → synchronized PBP/game state at T
  → state vector / previous state / transition
  → price path before/after T
```

W6 does **not** attach prices to `GameState`. Join keys are `GameId`, canonical timestamp, `state_seq`, `state_id`.

---

## Schema

### GameState

`GameState[n]` is the complete canonical state **immediately after** canonical event `n`.  
`GameState[0]` is the explicit pre-game / start state (not a playable event timestamp).

Identity: `GameId` (W2 canonical), season, game date, home/away, game number (doubleheaders remain separate games), game status.

Time: source timestamp, canonical timestamp (same as source when present), event sequence, inning/half id, schema/reconstruction versions.

Situation: inning, half, scores, run differential, outs before/after, independent 1st/2nd/3rd occupancy with player id when the source supplies it, batter, pitcher, count, PA lifecycle, event type/kind/description.

Unavailable source fields are `DataField::Unavailable { reason }`. Handedness, batting-order slot, and remaining game time are **not fabricated**.

### StateTransition

```
StateTransition[n] = previous_state + event + resulting_state
```

Includes score/out/base/batter/pitcher/inning/half/count deltas, runner-slot change flags, substitution/review/amendment/delay/walk-off indicators, and source provenance (`source_event_id`, raw file when present, parser version).

Identities are hashes, never random:

```
state fingerprint = sha256(canonical baseball fields)
state_id          = sha256(GameId, state_seq, fingerprint)
transition_id     = sha256(GameId, previous_state_id, source_event_id, resulting_state_id)
```

Retrieval timestamps and dataset generation timestamps **never** enter these hashes.

---

## Event semantics

W6 wraps W3 `replay()` / `apply()`. It does not reimplement outs/score/inning arithmetic.

Canonical event types come from W3 `MlbEventType` (play, substitution, review, amendment, inning markers, walk-off, game start/end, etc.).

Event kind classification:

| Kind | When |
|------|------|
| `GAME_START` / `GAME_END` | `GameStart`, `GameEnd`/`WalkOff` |
| `REVIEW` / `AMENDMENT` | those event types |
| `SUBSTITUTION` | pitcher/batter/defensive substitution events |
| `DELAY` / `RESUMPTION` | status enter/leave `Delayed` |
| `GAME_STATUS_TRANSITION` | other status changes |
| `ORDINARY` | all other plays |

Walk-off: pre-walk-off state → scoring event → **terminal** `Final`. No synthetic next inning. Extra innings are generic (`inning > 9`); a runner-on-second extra-inning state is represented only when the **source occupancy** shows it.

Personnel changes are transitions. The resulting state carries the new pitcher/batter/runner identity.

---

## Timestamp semantics

- Authoritative event time is the W3 source/canonical PBP timestamp when `Observed`.
- `GameStart` from StatsAPI ingest often has **UNAVAILABLE** wall time (`game start wall time not in envelope`). Untimed events do not participate in time lookup.
- Scheduled game time is **not** used as the first playable event timestamp.
- Pre-game (`state_seq = 0`) is never returned by `state_at_or_before`.

---

## Ordering

Deterministic canonical order:

```
source sequence > canonical_order > source_event_id > event_id
```

Never retrieval time. Duplicate `event_id`, `source_event_id`, or sequence → **fail closed**.

---

## Replay

```
replay_game / reconstruct(events) → ReconstructedGame
state_at_event(GameId, event_sequence)
state_at_or_before(T)
previous_event / next_event   // diagnostic; next is never applicable state
```

Repeated reconstruction of the same immutable source is canonical-equivalent (fingerprints and identities match).

---

## `state_at_or_before(T)` / lookahead

Returns the latest **timed** canonical state with `canonical_timestamp <= T`. Same timestamps break ties with **later source sequence**.

If none exist: `NO_STATE` (with diagnostic `next_event_*` only). **Never** the first later event.

A market timestamp strictly before event E must not receive the post-E state. Remaining game time is always `UNAVAILABLE` (would require lookahead).

---

## Validation (fail closed)

Typed `W6Error::Validation` includes GameId, event id, sequence, and reason. Impossible states are not repaired.

Checks include: score never decreases (W3), outs 0..=3, duplicate runner identities, count range, walk-off terminal/no next inning, sequence integrity, GameId uniqueness in a batch.

---

## PA lifecycle

Where source granularity permits:

```
PA_START → PITCH* → PA_RESULT → PA_END
```

StatsAPI landing is **play-level**. Pitch-level count transitions are recorded only when pitch events exist. Otherwise count uses the source play count when present, else `UNAVAILABLE`. The engine does **not** infer count from text.

---

## Derived intrinsic fields (allowed)

Run differential, absolute differential, bases bitmask, RISP, outs remaining in the half, total outs elapsed, occupancy/count/score/base-out identifiers, elapsed ms from the first timed event.

**Not in W6:** implied probability, Greeks, 80% buckets, strategy labels, trade outcomes, predictive/ML features, market prices.

---

## Provenance

Every state/transition traces to: GameId, source dataset, source event id/index, source timestamp, canonical timestamp, parser/normalization versions, reconstruction version.

---

## Artifacts

```
Backtesting Suite/Foundation/W6/
  state.sqlite          # gitignored; canonical store
  schema.sql
  game_states/          # index + sample; full rows in sqlite
  state_transitions/
  validation/
  manifests/w6_manifest.json
  reconstruction_report.json
```

Generation timestamp lives in the **manifest only**.

---

## Known limitations

1. Play-level PBP: most games have no pitch-by-pitch count path. StatsAPI landing emits play results (`FIELD_OUT`, `STRIKEOUT`, …), not `PITCH`/`BALL`/`STRIKE` rows.
2. Handedness / batting-order slot: UNAVAILABLE in StatsAPI play payload as ingested.
3. Runner identity: StatsAPI `runners[]` is a **movement log**. W3 ingest (W6 compatibility) keeps the last remaining base per player; scoring/out movements remove the runner. Occupied bases with empty ids were not observed in the 2026-08-26 landing run.
4. Extra-inning Manfred runner: never invented; only source occupancy.
5. Game remaining time: UNAVAILABLE.
6. W6 does not load Kalshi observations (W5).
7. Personnel substitutions, delays, and amendments are **not** separate StatsAPI play rows in this ingest (`substitutions=0`, `delays=0`, `amendments=0`). `hasReview=true` is recorded when present (3,205).
8. `StolenBase` W3 mapping also absorbs caught-stealing labels.
9. **23 games** fail closed with `FINAL_TIE`: StatsAPI `abstractGameState=Final` but reconstructed score is tied (typically suspended/shortened). Not repaired.
10. Landing count (3,848) exceeds the 1,684 W5 MATCHED-trade cohort. W6 reconstructs all PBP landing files. Overlap with mapped pairs: **2,377 / 2,377**.

Measured reconstruction (run `w6-20260827T064141Z`): 3,825 successful games; 293,775 events/transitions; 297,600 states (including pre-game); 290 extra-inning games; 326 walk-off flags.

W3 synthetic walk-off **fragments** that jump score without intermediate plays cannot replay from pre-game; full landing games do not use those fragments.

---

## W7 readiness

W6 exposes `StateJoinKey { game_id, canonical_timestamp, state_seq, state_id, event_id }`.

**Do not start W7** in the W6 grant. W7 EventMarketPath is implemented separately; W6 remains game-truth only.
