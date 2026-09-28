# Systimo Orchestra query contract

Product name Orchestra is `system_orchestration`, lifecycle DECLARED.
There is no Orchestra application. Orchestra queries Systimo only.

```text
GET /systimo/orchestra/context/{trade_id}
POST /systimo/query  query_type=ORCHESTRA_CONTEXT
```

Schema `systimo.orchestra_context.v0`. Namespaces: Austin, Choosin, Ballhog,
TK Ultra, Positman, Drevo, execution boundary, Vital, Jump.
Partial failure is `UNAVAILABLE`. `control=DENY`. `query_only=true`.
