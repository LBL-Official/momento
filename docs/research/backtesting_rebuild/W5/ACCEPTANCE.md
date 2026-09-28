# CTO-W5 ACCEPTANCE

**Status may become COMPLETE only with objective evidence.**

Bar:

- [x] ADR-0003 confidence never upgraded (`EXACT` only at lag 0)
- [x] Unmatched / one-sided streams retained (classified, not dropped)
- [x] `time_delta` only when both clocks exist
- [x] No invented PBP times from trades
- [x] No candle/PIT → L2; no trade → quote
- [x] `EXACT` has a written clock/boundary test
- [x] Production / Data-Real / FIRST01 untouched
- [x] Pre/post event states distinguishable; `AT_EVENT` explicit
- [x] Anti-lookahead tests
- [x] Cohort evaluated (actual counts in Foundation/W5 reports)
- [x] Workspace `cargo test` + `clippy -D warnings` (recorded at closeout)

## Prohibited (fail)

Skip W4; merge W6/W7 path engine into this crate; fabricate 1-second prices;
fill opening depth from candles; invent L2; start W6 automatically.
