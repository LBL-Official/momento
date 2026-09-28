# Feature dictionary

Every predictor is computed from information with source timestamp
`≤ ENTRY_DECISION_TIME`. Targets are never features.

`entry_time_precision = 1m_candle`. Entry-bar OHLC is `SAME_BAR_1M`.

## Identity / labels

| Name | Kind |
| --- | --- |
| observation_id | metadata |
| game_id / event_id / nba_game_id / ticker / team / team_code / opponent | metadata |
| game_date / dataset_split / season_phase | metadata |
| first_80_timestamp / entry_decision_time | decision |
| Y_40_CLOSE / Y_40_WICK | TARGET_ONLY |
| eventual_winner (`expiration_result_yes`) | TARGET_ONLY diagnostic |
| alignment_confidence / alignment_model | quality |

## A. Time (causal, if aligned)

| Name | Definition |
| --- | --- |
| quarter | PBP period at snap (1–4, 5+ OT) |
| game_seconds_elapsed | Regulation 12:00 periods + 5:00 OT consumed |
| game_seconds_remaining | Current period remaining + unused regulation; future OT unknown |
| period_seconds_remaining | Parsed from `clock` |
| half | 1 if period ≤ 2 else 2 |
| early_game / mid_game / late_game / flag_Q4 / flag_OT | Analytical labels, not substitutes for continuous time |

## B. Score state

| Name | Definition |
| --- | --- |
| team_score / opponent_score | From PBP at snap |
| score_differential | team − opponent |
| absolute_score_differential | abs |
| total_points | team + opponent |
| points_per_game_minute | total / (elapsed/60) if elapsed ≥ 60s |
| team_share_of_total_points | team / total if total > 0 |
| lead_size | max(diff, 0) |
| deficit_size | max(−diff, 0) |
| team_is_leading / team_is_trailing / game_is_tied | Boolean |

## C. Lead path / comeback / decay

| Name | Definition |
| --- | --- |
| number_of_lead_changes | Times the unique leader among {team, opp} changed |
| number_of_ties | Score became equal |
| time_since_last_lead_change_s / time_since_last_tie_s | Game seconds |
| lead_changes_last_5m / last_10m | Game-minute windows; null if insufficient elapsed |
| current_lead_duration_s | How long the current leader has held the lead |
| maximum_team_lead / maximum_team_deficit | Path extrema (deficit as positive magnitude) |
| lead_range | max_lead − (−max_deficit) |
| score_differential_mean / stdev / trend / velocity | Trend = OLS slope vs elapsed; velocity = Δdiff last 2 game min |
| distance_from_max_lead / distance_from_max_deficit | Current vs extrema |
| comeback_magnitude | current_diff − historical_min_diff |
| maximum_deficit_overcome | max(0, −historical_min_diff) if now leading, else 0 if still below; stored as −min if min<0 |
| points_scored_since_max_deficit / time_since_max_deficit_s | From the action of historical min diff |
| lead_decay | max(0, historical_max_lead − current_lead) |
| path_state | STABLE_LEAD / EXPANDING_LEAD / COLLAPSING_LEAD / RECENT_COMEBACK / LATE_COMEBACK / VOLATILE_BACK_AND_FORTH / OTHER / GAME_NOT_STARTED |

## D. Game volatility and scoring runs

Windows are **game minutes**, not wall minutes, and only if elapsed covers them.

| Name | Definition |
| --- | --- |
| score_diff_stdev_{2,5,10}m / range / abs_change | |
| lead_change_frequency / tie_frequency | Counts in window |
| scoring_burst_intensity | Max |Δdiff| over 60s rolling in window |
| team_scoring_rate_diff | Team minus opp points per minute in window |
| scoring_run_imbalance | Last run points signed for team |
| last_scoring_run_team / points / duration_s | |
| largest_prior_run_team / points | Completed runs before current |
| net_score_change_last_{2,5,10}m | |

## E. Market path (V1-compatible, joined)

Candle windows use `end_period_ts ≤ ENTRY_DECISION_TIME` only.

| Name | Definition |
| --- | --- |
| distance_above_80_cents | bid_close − 80 |
| momentum / vol / range / up_count / down_count at 1/5/15m | Same construction as Path Engine V1 |
| spread_cents | ask_close − bid_close at entry |
| volume_hundredths | Entry candle |
| dist_from_recent_high / low | 15m window |
| minutes_from_{50,60,70}_to_80 | Minutes since last bid_close below that level; null if never |
| market_acceleration | (ΔP_1m) − (ΔP_prior_1m) |

## F. Game–market relationship

Requires both 5 game-minute score momentum and 5 market-minute momentum.

| Category | Quantitative rule |
| --- | --- |
| ALIGNED_UP | score_mom ≥ +3 and market_mom ≥ +3¢ |
| ALIGNED_DOWN | score_mom ≤ −3 and market_mom ≤ −3¢ |
| GAME_IMPROVING_MARKET_FLAT | score_mom ≥ +3 and \|market_mom\| ≤ 2¢ |
| GAME_WORSENING_MARKET_FLAT | score_mom ≤ −3 and \|market_mom\| ≤ 2¢ |
| MARKET_LEADING_GAME | market_mom ≥ +5¢ and score_mom ≤ 0 |
| GAME_LEADING_MARKET | score_mom ≥ +5 and market_mom ≤ 0 |
| MIXED / INSUFFICIENT | otherwise / missing window |

## Leakage

`expiration_result_yes`, post-entry wick/close labels, and any PBP action
after the snap are TARGET_ONLY or unused. Leakage audit fails the run if a
predictor’s maximum source timestamp exceeds entry.
