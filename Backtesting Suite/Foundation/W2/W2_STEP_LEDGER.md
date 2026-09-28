# W2 Step Ledger

**Capability:** ENGINE COMPLETE / HISTORICAL COVERAGE INCOMPLETE

CTO-W2-A1-S1 schema+FIXTURE → crate W2-A4 (event) + W2-A5 (state) + fixtures in synthetic.rs
CTO-W2-A1-S2 adapters → crate W2 adapter.rs (MlbEventAdapter)
CTO-W2-A2-S1 identity graph → crate W2-A2
CTO-W2-A2-S2 official pk map → BLOCKED (crate W2-A2-S7)
CTO-W2-A3-S1 PBP license gate → BLOCKED (no download this run)
CTO-W2-A4-S1 reconstruct GameState from authorized historical PBP → BLOCKED (no files)
CTO-W2-A5-S1 UNAVAILABLE event-state labeling → crate coverage.rs + identity kalshi: prefix


| ID | Status | Objective | Result | Blockers |
|---|---|---|---|---|
| W2-A1-S1 | Complete | Inventory every MLB/PBP source in repo, env, collectors | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A1-S2 | Complete | Authoritative source hierarchy (no auto-substitution) | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A1-S3 | Complete | Source provenance contract | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A1-S4 | Complete | Timestamp semantics (five clocks) | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A1-S5 | Complete | Authoritative event definition | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A1-S6 | Complete | Missing-data behavior | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A1-S7 | Complete | Duplicate-event behavior | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A1-S8 | Complete | Corrected/amended PBP behavior | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A1-S9 | Complete | Source conflict behavior | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A1-S10 | Complete | Document W2 source contract | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A2-S1 | Complete | Identity schema | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A2-S2 | Complete | Normalization of source ids | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A2-S3 | Complete | Mapping engine (no invented maps) | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A2-S4 | Complete | Duplicate detection | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A2-S5 | Complete | Collision detection | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A2-S6 | Complete | Missing ID behavior | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A2-S7 | Complete | Source crosswalk (Kalshi alias vs official) | COMPLETE (crosswalk engine). Real mapped counts depend on collected PBP. | none for engine |
| W2-A2-S8 | Complete | Season validation | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A2-S9 | Complete | Team validation | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A2-S10 | Complete | Game uniqueness + deterministic IDs | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A3-S1 | Complete | Source discovery (local only) | COMPLETE (empty inventory, not a fake lake) | none for discovery; historical ingest blocked separately (CTO-W2-A4-S1) |
| W2-A3-S2 | Complete | Ingestion contract / envelope | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A3-S3 | Complete | Raw source reference | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A3-S4 | Complete | StatsAPI-shaped parser | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A3-S5 | Complete | Schema validation | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A3-S6 | Complete | Malformed event handling | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A3-S7 | Complete | Duplicate handling | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A3-S8 | Complete | Ordering | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A3-S9 | Complete | Provenance on every event | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A3-S10 | Complete | Ingestion report | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A4-S1 | Complete | Event schema | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A4-S2 | Complete | Game + clock fields | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A4-S3 | Complete | Score / runners / PA | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A4-S4 | Complete | Event types | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A4-S5 | Complete | Optional pitch/review/substitution | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A4-S6 | Complete | Provenance + observability | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A4-S7 | Complete | Serialize | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A4-S8 | Complete | Deserialize | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A4-S9 | Complete | No magic sentinels | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A4-S10 | Complete | Tests | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A5-S1 | Complete | State schema | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A5-S2 | Complete | Transition function | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A5-S3 | Complete | Invariant system | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A5-S4 | Complete | Replay | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A5-S5 | Complete | Edge cases | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A5-S6 | Complete | Extra innings | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A5-S7 | Complete | Walk-offs | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A5-S8 | Complete | Reviews/amendments | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A5-S9 | Complete | Substitutions + scoring | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A5-S10 | Complete | Invalid states fail closed | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A6-S1 | Complete | Innings/outs remaining fields | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A6-S2 | Complete | Outs elapsed | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A6-S3 | Complete | Current inning/half/outs | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A6-S4 | Complete | PA position slot | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A6-S5 | Complete | Event sequence | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A6-S6 | Complete | Time since start/previous (when sourced) | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A6-S7 | Complete | Opportunity count/fraction/delta | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A6-S8 | Complete | Regulation vs extra innings | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A6-S9 | Complete | No invented theta value | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A6-S10 | Complete | Document empirical Event Theta later | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A7-S1 | Complete | Ordered sequence type | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A7-S2 | Complete | last N events | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A7-S3 | Complete | last N plate appearances | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A7-S4 | Complete | last N scoring | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A7-S5 | Complete | last N pitching changes | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A7-S6 | Complete | last N reviews | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A7-S7 | Complete | event-type transitions | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A7-S8 | Complete | time between events | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A7-S9 | Complete | scoring bursts | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A7-S10 | Complete | lead changes | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A8-S1 | Complete | Deterministic ordering | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A8-S2 | Complete | State replay | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A8-S3 | Complete | State serialization | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A8-S4 | Complete | State restoration | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A8-S5 | Complete | Duplicate handling | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A8-S6 | Complete | Malformed PBP | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A8-S7 | Complete | Inning transitions | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A8-S8 | Complete | Extra innings / walk-offs / reviews | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A8-S9 | Complete | Runner + scoring validation | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A8-S10 | Complete | Validation summaries | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A9-S1 | Complete | Coverage vocabulary | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A9-S2 | Complete | Season/date/GameId rows | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A9-S3 | Complete | PBP/pitch/timestamp/score flags | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A9-S4 | Complete | Runner/batter/pitcher flags | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A9-S5 | Complete | Final outcome flag | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A9-S6 | Complete | Reconstruction valid/warnings | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A9-S7 | Complete | 2025 MISSING_HISTORICAL_SOURCE | COMPLETE as reporting of absence | none |
| W2-A9-S8 | Complete | 2026 Kalshi-only honesty | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A9-S9 | Complete | CSV mirror | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A9-S10 | Complete | Do not claim synthetic as history | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A10-S1 | Complete | WATERFALL_2_MLB_EVENT_RECONSTRUCTION.md | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A10-S2 | Complete | W2_ARCHITECTURE.md | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A10-S3 | Complete | W2_DATA_DICTIONARY.md | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A10-S4 | Complete | W2_VALIDATION.md | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A10-S5 | Complete | W2_COVERAGE.md | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A10-S6 | Complete | W2_STEP_LEDGER.md | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A10-S7 | Complete | W2_COMPLETION_REPORT.md | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A10-S8 | Complete | W1 dependency note (no W1 file edits) | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
| W2-A10-S9 | Complete | Google local artifacts | COMPLETE (local artifacts). Sheets cell publish: GOOGLE_PUBLISH_PENDING | none for local artifacts; Sheets MCP is an external publish gate, not a PBP gate |
| W2-A10-S10 | Complete | Completion gate | COMPLETE (engine/contract; historical PBP still missing) | none for engine; historical reconstruction blocked on data |
