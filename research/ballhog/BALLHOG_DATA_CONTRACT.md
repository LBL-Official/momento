# Ballhog data contract

Schema family: `ballhog.*.v1`. Integers for cents and quantities.
Missing is `UNAVAILABLE`, never `$0`. `q*=0` is the integer 0, not missing.

## Universes (stamp both)

| Field | Austin | Choosin Texas |
|---|---|---|
| universe | `choosin_nba_2q3q_604` | `derived_four_936` |
| N | 604 | 936 |
| PIT | query_at persist=False | STATIC prior |
| as_of path | historical reconstruction | none |

Never mix. Austin owns `a_t`. Ballhog does not relabel it.

## Used fields

- `a_t` = Austin `conditional_ev.conditional_ev_cents` (one unhedged A1)
  aliases: `austin_alpha_cents`, `austin_alpha_per_unit`
- `a_L` = Austin `ci_lower_cents` (existing 95% weighted bootstrap)
- `support`, `effective_sample_size`
- `alpha_delta_from_entry` = `state_change.ev_change` (not Λα)
- `weighted_T40_rate`, `weighted_survival_rate`
- Choosin `S` / ladder EV on N=936 as a separate estimand
- Every response: `research_unit_qty`, `q_dir`, `q_hedge`, `rho`
- Decision: `risk_intent`, `hedge_feasibility`, `decision_status`, `explanation`

## UNAVAILABLE

Live feed, fills, L2, fees, executable hedge, calibrated λ, Λα, MDP
policy, per-ticker Choosin path EV, BUY NO taker, current A2 hedge
price.

Header pills must name the missing source (`LIVE FEED UNAVAILABLE`,
`HEDGE PRINT UNAVAILABLE`). Zero quantities stay `0` / `0%`.

## Feed mode

`HISTORICAL` | `REPLAY` | `UNAVAILABLE`. Never `LIVE`.

No source stamp after `as_of`. Choosin STATIC has no path timestamp.

Position list stamps `default_as_of` = Austin replay-path midpoint
(`index // 2`) and `replay_available`. UX only. Not evidence.

## Surface cell

`THEORETICAL` / `CANDLE_PATH`. `fill_claimed=false`. Price grid 35–45
inclusive for `q > 0`. `q = 0` is a single no-hedge cell:
`hedge_price_cents=null`, `price_relevant=false`.

Aliases: `portfolio_ev_before`, `is_robust_positive`, `is_frontier`,
`is_admissible`. Adjacent frontier q also carries `delta_risk_removed`,
`delta_economic_ev_cost`, `marginal_ev_cost_per_unit_risk_removed`
(`None` if Δrisk=0).

## Decision

`decision_status`: `RESOLVED` | `POLICY_UNRESOLVED` | `UNAVAILABLE` | `SOURCE_UNAVAILABLE`

`hedge_feasibility`: `NOT_REQUESTED` | `ADMISSIBLE_HEDGE_AVAILABLE` |
`NO_ADMISSIBLE_HEDGE` | `POLICY_UNRESOLVED` | `SOURCE_UNAVAILABLE`

`q_dir` must be an integer in `[1, max_q_dir]`. Default 1. Floats and
`q_dir < 1` are `INVALID_QUANTITY`.

Reason codes fire only when the implemented rule fired.
