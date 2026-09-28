# Response surfaces

A V3 surface is a grouped conditional expectation, not a fitted model.

```text
E[Y_h | condition_id]
```

computed only from responses that satisfy:

```text
observation_time_i < t
AND
response_available_at_i < t
```

Rows include `surface_name`, `surface_version`, `measurement_name`, `conditioning_schema_version`, `condition_id`, `value` or `INSUFFICIENT_SUPPORT`, and support metadata.

Condition identifiers are hashes of `conditioning_schema_v1` plus ordered raw dimensions. The raw dimensions are stored beside the hash.

Do not call a surface predictive because it estimates a conditional mean.
