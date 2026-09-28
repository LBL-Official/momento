# Jump lineage model

Two graphs. Do not collapse them.

## System graph (Systimo)

Who depends on whom. CSV connections. Query type `path_back` walks
incoming edges from Jump (or another start) toward sources.

Example:

```text
Jump → Ballhog → Austin
Jump → TK Ultra → Choosin Texas
Jump → ROLLER warehouse pointer
```

## Data lineage (`JumpLineage`)

Which exact dataset/result generated this value, as far as registered
APIs expose.

```text
lineage_id
result_system = jump
result_resource
result_timestamp
parents[]     system_id, resource_id, schema, dataset_id, universe_id
source_files[]
source_tables[]
source_rows[]
identity_keys[]
transformations[]
query_id
```

Never invent warehouse row ids. If Austin returns a `trade_id` /
`ticker` and ROLLER has not matched a parquet row, lineage stops at the
Austin trade identity.

SHOW SOURCE (`GET /jump/data/lineage/{resource_id}`) returns product,
model, universe, dataset, file/table when known, row identity keys,
timestamp, source basis, and upstream parents.

## Deepest current resolution

| Layer | Exposed |
|---|---|
| Jump context | composition only |
| Austin | trade_id, ticker, query_at as_of, universe 604 |
| Choosin | STATIC prior, universe 936 |
| Ballhog / TK Ultra | read of their outputs; parents Austin + Choosin |
| ROLLER | table pointer + filtered rows (`internal_game_id`, ticker, `available_at <= as_of`) |
| File / parquet row id | only when the warehouse query actually returned that row |
