# Reproduce W1

run_id: `w1-d7e5d472e86268dc`

```bash
cargo run -p momento-research-collector -- w1-foundation \
--lake "Backtesting Suite/Data-Real" \
--out "Backtesting Suite/Foundation/W1"
```

Idempotency: `canonical_catalog_body.json` and `lake_content_digest` must match on an unchanged lake.
`generated_at` may differ. Raw files under the lake must not change.
Default real lake is Data-Real, not the demo Data/ tree.
