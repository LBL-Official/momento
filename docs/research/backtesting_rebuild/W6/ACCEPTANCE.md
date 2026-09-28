# CTO-W6 ACCEPTANCE

**Status may become COMPLETE only with objective evidence.**

Canonical `GameState` and `StateTransition` exist; available MLB PBP
deterministically replays; `state_at_or_before(T)` never returns a future
state; provenance preserved; validation fail-closed; artifacts/manifests
written; workspace tests + clippy `-D warnings` pass.

## Prohibited (fail the waterfall)

Invent L2/prices; attach market paths to GameState; start W7; FIRST01 replay;
lookahead in `state_at_or_before`; silently repair impossible states.

See [../W6_STATE_ENGINE.md](../W6_STATE_ENGINE.md).
