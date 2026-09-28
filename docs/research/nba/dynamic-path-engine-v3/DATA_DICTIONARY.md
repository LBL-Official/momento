# Data dictionary (selected)

`trade_id` = `{event_id}|{ticker}|first80` (same construction as V1/V2 observation_id).

## Trade universe

entry_decision_time, first_40_close_ts, Y_40_CLOSE, Y_40_WICK, time_to_40_s,
censored, dataset_split, maker_fill_confidence.

## Panel row

state_timestamp = 1m candle `end_period_ts`.
alive_above_40 = 1 (by construction).
minutes_since_entry, minutes_to_contract_close.
barrier_event_this_interval = next-minute close-path 40.
H_40_5M / 10M / 15M: future-only.

## Market features (≤ state_timestamp)

bid/ask close, spread, estimated_mid (ESTIMATED),
distance_to_40_cents, distance_to_80_cents, distance_from_entry_cents,
norm_position = (K−40)/(80−40) using bid_close cents,
rolling 1/3/5/10/15m momentum and candle-vol proxy,
MAE/MFE since entry, path_efficiency, consecutive up/down,
time_spent_below_70/60/50, velocity_toward_40.

Volatility labeled `1-MINUTE CANDLE VOLATILITY PROXY`.

## Game features

Only when PBP snap at `state_timestamp` has alignment HIGH or MEDIUM.
Otherwise UNAVAILABLE. Never infer tip from Kalshi open.

## Event-response categories (algorithmic)

SHOCK_AND_RECOVERY, SHOCK_AND_CONTINUATION, GRADUAL_DECAY,
STABLE_PATH, OSCILLATORY_PATH, INSUFFICIENT.
