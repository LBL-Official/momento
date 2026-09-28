# Systimo connection contract

A connection is a registered tunnel:

```text
source_system_id → target_system_id
transport, permission, lifecycle, health, capability, adapter
```

Austin stays one canonical source with separately governed edges:

```text
                    Austin_604
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
       Ballhog      TK Ultra       Jump
```

Choosin 936 fans out the same way. Do not register Austin → Ballhog → TK Ultra.

Lifecycle: `DECLARED` | `IMPLEMENTED` | `DEPRECATED` | `DISABLED`.
Health: `HEALTHY` | `DEGRADED` | `UNAVAILABLE` | `MISCONFIGURED` | `STALE` | `UNKNOWN`.
Permission: `READ` | `QUERY` | `WRITE` | `CONTROL` | `DENY`. Default DENY for writes.

Jump Austin/Choosin research-context routes are QUERY, persist=False / STATIC.
Jump data-plane tunnels (Austin replay/trade/universe, Ballhog, TK Ultra,
ROLLER identity/observations/PBP/settlement, Systimo catalog) are also
QUERY. Jump never owns those datasets.
Position Management edges stay DECLARED / UNAVAILABLE / DENY.
Missing L2 or unread observe is UNAVAILABLE, never `$0`, never `RUNNING` for data edges.

`path_back` walks incoming connections from Jump (or another start)
toward canonical sources. That is the system graph, not row-level
lineage.
