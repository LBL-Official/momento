# Positman Ballhog × TK Ultra contract

Public handlers only:

- Ballhog `roller.ballhog.api.handle_intent`
- TK Ultra `roller.tk_ultra.api.handle_assess_v0`

Do not import `roller.ballhog.adapters` or `roller.tk_ultra.adapters`.

Match fields (exact): `trade_id`, `internal_game_id`, `event_id`,
`a_contract`, `b_contract`, `as_of`. Disagreement is `IDENTITY_MISMATCH`
or `STATE_TIME_MISMATCH`. Never invent IDs.

Quantity is Ballhog `q_star`. Route is TK Ultra `route_preference`.
