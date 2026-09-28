# Systimo query engine

Structured `SystimoQuery` only. No LLM. No SQL textbox as the product.

Types: `systems`, `connections`, `dependencies`, `reverse_dependencies`,
`datasets`, `interfaces`, `health`, `artifacts`, `provenance`, `paths`,
`path_back`, `drift`, `governance`.

Each query writes `queries.csv` + `answers.csv` + `sources.csv`.
Capability map (`AUSTIN_QUERY_AT`, `CHOOSIN_TRADE_CONTEXT`, …) dispatches
to a registered adapter. Unregistered → `UNREGISTERED_INTERFACE` /
`UNAVAILABLE`.

Acceptance answers come from the CSV registry, not hardcoded UI copy.
`consumers-of-Austin` is `reverse_dependencies` with `system=austin`.
Choosin→Jump is `paths` with `from=choosin_texas` `to=jump`.
