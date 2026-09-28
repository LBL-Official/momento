# W2 Data Dictionary

Transform versions: `PARSER_VERSION=W2.PBP.1.0.0`, `NORMALIZATION_VERSION=W2.NORM.1.0.0`, `SCHEMA_VERSION=W2.EVENT.1.0.0`, `STATE_MACHINE_VERSION=W2.STATE.1.0.0`, `EVENT_TIME_DEFINITION_VERSION=W2.EVENT_TIME.1.0.0`, `REMAINING_OUTS_DEFINITION_VERSION=v1-regulation-54`.

Unknown baseball fields use `DataField::Unavailable { reason }`. Never `-1`, `999`, or empty string as sentinels.

| Field | Layer | Observability | Notes |
|-------|-------|---------------|-------|
| canonical_game_id | identity | DERIVED | Hash of observed source + source_game_id |
| mlb_game_pk | identity | OBSERVED or UNMAPPED | Never invented |
| kalshi event_ticker | identity | OBSERVED alias | Not an official MLB id |
| sequence | event | OBSERVED/DERIVED | Canonical order |
| source_timestamp | event | OBSERVED or UNAVAILABLE | Not collector time |
| inning, half, outs | state | OBSERVED from PBP | Game clock |
| score home/away | state | OBSERVED | Score at t, not eventual winner |
| runners | state | OBSERVED or UNAVAILABLE | No invented advancement |
| batter, pitcher | state | OBSERVED or UNAVAILABLE | Source player ids |
| balls, strikes | state | OBSERVED or UNAVAILABLE | |
| outs_elapsed | event_time | DERIVED v1 | From inning/half/outs |
| regulation_outs | event_time | DERIVED | Constant 54 |
| regulation_outs_remaining | event_time | DERIVED | max(0, 54 − elapsed) |
| actual_outs_remaining | event_time | UNAVAILABLE at t | Some(0) only if status=Final (knowable at t) |
| extra_inning_state | event_time | DERIVED | inning > 9 |
| event_opportunity_* | event_time | DERIVED | Integer fraction consumed/54 |
| event_theta | event_time | NOT_COMPUTED | Later empirical (W9) |
| winner / final_score | outcome | OUTCOME_LABEL | Forbidden on replay-at-t state |
| yes_bid / L2 / starting_price | market | W1/W3 | Not W2 |

CSV mirror: `Backtesting Suite/Foundation/W2/w2_data_dictionary.csv` after `run_w2`.
