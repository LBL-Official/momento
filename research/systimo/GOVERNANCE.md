# Systimo governance

Default DENY. V0 research tunnels are QUERY only.

Jump may read Austin `query_at(persist=False)` and Choosin
`get_trade_context`. Jump may read Ballhog / TK Ultra outputs and ROLLER
warehouse pointers through registered QUERY tunnels. Jump may not write
those sources. Jump Drive adapters must not import
`roller.ballhog.adapters` or `roller.tk_ultra.adapters`. The data plane
calls public `handle_intent` / `handle_assess_v0` only.

APPLY allowlist:

- `REFRESH_CONNECTION`
- `RECHECK_HEALTH`
- `REBUILD_QUERY_INDEX`
- `REGENERATE_TREE`
- `EXPORT_ARTIFACT`
- `VALIDATE_SCHEMA`

No UI shell. No Kalshi. No live-service start/stop.

Austin `N=604` / Choosin `N=936` mismatch is `INTEGRITY_DRIFT`.
Do not update expected N. Stop and report.
