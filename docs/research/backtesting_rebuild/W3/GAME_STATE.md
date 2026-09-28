# Game state

W2 state machine: `STATE_before + EVENT = STATE_after`.

In-progress `MlbGameState` must not carry winner, final_score, or future events (`assert_no_future_leakage`).

Inning transitions come from observed outs/half in source events, not synthetic `InningEnd` invented by W3. W2 may emit `InningEnd` when the source play sequence implies it.

Score/out/count/base inconsistencies **fail** (`EventError::Invariant`), not silent repair.
