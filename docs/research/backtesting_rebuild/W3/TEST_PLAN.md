# Test plan

All synthetic streams are `SYNTHETIC_TEST_FIXTURE`.

| # | Case | Where |
|---|------|--------|
| 1 | nine-inning catalog | `nine_inning_catalog` |
| 2 | extra-inning walkoff apply | `extra_inning_and_inning_transition` |
| 3 | rain/postponement | `rain_postponement_not_a_played_game` + 4 skipped Postponed |
| 4 | suspended classifier | `classify_schedule_status("Suspended")` |
| 5–8 | scoring, stolen base, inning transition | catalog + `inning_transition` |
| 9 | near timestamps | W2 synthetic seq timestamps |
| 10 | missing optional | `DataField::Unavailable` |
| 11 | malformed | `ingest_bytes` fail closed |
| 12 | duplicate event | `statsapi_envelope_duplicate_play_json` |
| 13–14 | ambiguous/unmapped | identity tests + real 2/4 counts |
| 15–17 | no-lookahead, final, determinism | W2 replay helpers |
| 18–20 | checksum, uncommitted gate, idempotent real run | gate + `real_collect_manifest_*` |
