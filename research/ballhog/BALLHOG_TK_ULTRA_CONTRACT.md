# Ballhog ↔ TK Ultra contract

Siblings. Not `Ballhog → TK Ultra → action`.

Ballhog emits `BallhogHedgeIntent` (`ballhog.hedge_intent.v1`).
TK Ultra may display that intent as **SIBLING CONTEXT — NOT MODEL INPUT**.
TK Ultra math does not consume Ballhog.

## Do not

- Modify `GET /momento/tk-ultra/assess` (`GENERIC_RV`).
- Call `/momento/tk-ultra/assess` from the Ballhog frontend or package.
- Import `roller.ballhog.adapters` from TK Ultra.
- Import TK Ultra relationship/route/budget from Ballhog.
- Teach TK Ultra ρ\* internals.
- Recompute wing / base / β in Ballhog.
- Fake a Position Management compositor.
- Add a mandatory localhost self-HTTP call between the two.

## Intent fields

Desired risk transformation only:

- `q_dir`, `q_hedge`, `rho`, `rho_star`
- `quantity_to_neutralize` (q\*), `residual_exposure_target` (Δ\*)
- `risk_intent`, `hedge_feasibility`
- `timing_state` / `urgency`
- `intent_status`: `NO_HEDGE` if `q_star==0`, `UNRESOLVED` if `q_star`
  is null, else `HEDGE_REQUESTED`
- `alpha_before` (Austin `a_t`), `alpha_ci` (Austin bootstrap, labeled)
- `acceptable_hedge_price_region` (35–45 counterfactual, not a limit)
- `economic_constraints.positive_robust_portfolio_ev`
- `provenance` (Austin 604, Choosin 936, policy version)
- `execution_enabled=false`, `live_execution=false`
- `explanation` copied from the two-stage decision

TK Ultra `GENERIC_RV` still needs only `wing_price, base_price, beta,
wing_anchor, base_anchor` for the legacy assess. Missing wing is
`SOURCE_UNAVAILABLE` there.

`BINARY_COMPLEMENT_V0` uses TK Ultra's own Austin/Choosin adapters and
optional in-process `handle_intent`. Ballhog down → sibling `UNAVAILABLE`;
assessment continues.

Position Management remains `NOT_IMPLEMENTED`.
