STEP ID: INGEST-A3-S1
WATERFALL: DATA-INGEST
TITLE: Landing-wide identity rejoin (doubleheader G1/G2 + AZ/ARI)
STATUS: COMPLETE
DATE: 2026-08-27

OBJECTIVE: Map every Kalshi `KXMLBGAME` event that has a unique StatsAPI PBP
game on the same official date, without inventing `gamePk`.

SCOPE: Identity join + offline `rejoin-landing` CLI. No Data-Real writes. No W9.
No invented L2. No HHMM-based disambiguation.

INPUTS: Landed StatsAPI envelopes + Kalshi discovery envelopes.

OUTPUTS:
- Identity `W2.IDENTITY.1.2.0`
- Ingest `INGEST.2.1.2`
- CLI `rejoin-landing`
- Pairs `runs/rejoin-20260827T114739Z/game_market_pairs.json`

CODE CHANGES:
- `kalshi_event_team_and_game` slices observed `G1`/`G2` or trailing `2`
- Official `game_number` from StatsAPI schedule and PBP `gameNumber`
- Observed `AZ`↔`ARI` alias (both strings from catalogs)
- Offline landing walker `rejoin_landing`

DATA CHANGES: no raw overwrite. New run dir only.

TESTS: identity/join/rejoin unit tests; `cargo test -p momento-research-event -p momento-research-ingest --offline`

VALIDATION: clippy `-D warnings` on event + ingest + ingest-app. Rejoin measured 4,143 mapped games, 8,286 mapped pairs, 0 ambiguous.

KNOWN LIMITATIONS:
- 2023–2024 Kalshi UNAVAILABLE
- Spring-training PBP has no `KXMLBGAME`
- Extra `*2` tickers without a game-2 PBP stay UNMATCHED
- Postponements with date mismatch stay UNMATCHED (fail-closed)

LOOKAHEAD / DATA LEAKAGE REVIEW: identity only; no labels; no fills.

NEXT STEP: matched-trades skip-existing on rejoined MAPPED pairs, then CTO-W4→W5→W6→W7→W8. Do not start W9.

FINAL STATUS: COMPLETE
