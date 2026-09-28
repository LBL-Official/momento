# PBP reconstruction

```text
committed artifact
  → checksum verify (fail closed)
  → W2 ingest_path / reconstruct_paths
  → ordered CanonicalMlbEvent
  → W2 replay → MlbGameState sequence
  → coverage + anomalies
```

Malformed events are retained as ingest malformed/duplicates, never silently replaced.

W3 does not download. DATA-INGEST owns landing.
