# V4A fundamental probability

```text
F_t = documented empirical estimator of Pr(home wins | I_t)
F_t ≠ TRUTH
K_t ≠ F_t
K_t - F_t ≠ EDGE
```

## What `F_t` is

`fundamental_win_probability_empirical_v1` is the prior-only win rate among historical states that:

1. match the configured `core_v1` condition (period, elapsed-clock bucket, home score-margin bucket),
2. have `state_available_at < observation_cutoff`,
3. have `result_available_at < observation_cutoff`,
4. are **not** the current game.

```text
F_t = wins / n
```

Exact integers `probability_wins` / `probability_n`. `value` is `{numerator, denominator}` when support passes.

## What `F_t` is not

True probability, fair value, intrinsic value, market price, or edge. A disagreement with `yes_bid_close` is model disagreement, not inefficiency.

## Information consumed

From `O_t`: period, remaining ISO clock (converted to elapsed seconds), home−away score differential.

From other games: terminal `home_win` and `result_available_at`.

## Information not consumed

Current game terminal outcome, future games, future seasons, end-of-season ratings, market `yes_bid_close`, possession, pre-game `win_pct_pre`, V2 horizon labels, V3 responses.

## Historical corpus

`pbp_last_per_clock_bucket_v1`: last PBP event per `(internal_game_id, period, clock_bucket)`, joined to that game’s `home_win`. Optional file `derived/v4a_fundamental_state_corpus.csv` is always re-filtered at query time. Not a public `dataset()`.

## PIT boundary

`available_at < cutoff` is unchanged. Outcome eligibility uses `result_available_at < cutoff`, not `games.available_at`. Equality is hidden.

## Current-game exclusion

`internal_game_id` of the observation is excluded by identity, even if its result is already known.

## Comparable states

Same `conditioning_schema_version` and same `condition_id`. Schemas are not mixed.

## Insufficient support

`value = null`, `status = INSUFFICIENT_SUPPORT`. Never 0.50, never K, never a global average.

## What the number represents

Among prior, eligible, same-bucket home states **in that sport’s corpus**, the fraction of those games the home team won. NBA uses 4×12:00, WNBA 4×10:00, NCAAB 2×20:00. NCAAB rows require `p5_vs_p5=1`. Sports are never mixed in one corpus. It is an estimator, not the probability generating the next game.
