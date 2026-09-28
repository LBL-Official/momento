# Systimo agent runtime

Deterministic workers. No tokens. No LLM.

| Agent | Queries | Allowlisted actions |
|---|---|---|
| Connection Manager | connections, health | REFRESH_CONNECTION, RECHECK_HEALTH |
| Health Manager | health | RECHECK_HEALTH |
| Schema Manager | drift, governance | VALIDATE_SCHEMA |
| Artifact Manager | artifacts | EXPORT_ARTIFACT |
| Dependency Manager | dependencies, reverse_dependencies, paths | REGENERATE_TREE |

Modes: OBSERVE (query) → PLAN (propose / dry-run) → APPLY (allowlist only).
Agent runs record query ids and proposed action ids. They do not auto-APPLY.
History is `agents.csv` + `agent_runs.csv`.
