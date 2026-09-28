# Systimo data model

CSV is SSOT. Atomic write: temp → validate → `os.replace`, plus `fcntl.flock`.

```text
research/systimo/
  registry/     systems.csv connections.csv interfaces.csv datasets.csv governance.csv schemas.csv
  state/        health_snapshots.csv connection_events.csv
  queries/      queries.csv answers.csv sources.csv
  artifacts/    index.csv + immutable files
  actions/      actions.csv action_runs.csv
  agents/       agents.csv agent_runs.csv
  generated/    tree.json graph.json
```

`connection_events` and `health_snapshots` are append-only.
Primary keys, foreign keys, and enums are enforced in
`ROLLER/roller/systimo/store/schema.py`.

`systems.csv` is Systimo’s registered truth. The 19-bracket YAML is
discovered evidence, not auto-repaired from this store.
