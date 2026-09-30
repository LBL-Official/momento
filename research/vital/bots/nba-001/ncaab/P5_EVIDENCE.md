# NCAAB P5 membership — 2026–27 evidence

Status: `EVIDENCE_INCOMPLETE`.

The validator in `strategies/nba/src/p5.rs` accepts only `season=2026-27` and `status=VERIFIED` with non-empty verified rows that each carry a canonical id, ESPN team id, and evidence URL.

## Why this file is empty

- 2025–26 conference lists are not 2026–27.
- 2024+ realignment makes a frozen “Power 5” set (ACC / Big Ten / Big 12 / SEC / Pac-12) non-obvious. Pac-12 membership in 2026–27 is not the historical set.
- No current-season official membership page with ESPN ids was attached in this increment. Guessing teams would auto-include games.

## What is required to flip `VERIFIED`

For every admitted team:

- canonical id
- display name
- conference in the declared set
- ESPN team id
- `evidence_url` for 2026–27 membership
- `verified=true`

Both teams of a game must pass `both_p5`. Missing or unverified membership blocks NCAAB admission. NBA is unaffected.

Machine file: `p5_membership_2026_27.json`.
