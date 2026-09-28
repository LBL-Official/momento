# Momento Systems — Program Board

Canonical narrative: [`MOMENTO_SYSTEMS_ROADMAP.md`](MOMENTO_SYSTEMS_ROADMAP.md).
This board is the 16-row tracker Notion should mirror. Do not invent
completion dates. Repo is source of truth.

Status values here are tracker states, not live trading states.

| # | Name | Purpose | Timing | Status | Depends-on |
| --- | --- | --- | --- | --- | --- |
| 1 | Vital | Execution infrastructure / MLB 001 | Now | In progress | Existing engine + Risk + `mlb_factory_v1` |
| 2 | ROLLER completion | Research measurement truth | Now | NBA 0–20 complete; NCAAB/MLB sequential | Warehouse contracts; no Phase 21 |
| 3 | Polymarket 1m | Second prediction-market data source (`LAST_TRADE_PRINT`) | Before Oct 1, 2026 | Ingest exists; harden / schedule | `ROLLER/scripts/ingest_polymarket.py` |
| 4 | Kalshi + Poly + PBP intersection | Same-game PIT research row (explicit op, not merged quote) | After #3 is trustworthy | Not started | #3; game/market identity |
| 5 | Autoingest + Autojest | Automated acquisition + validation; Autojest dashboard | Before / around Oct 1, 2026 | Not started | ADR-0021; #2; #3 |
| 6 | ROLLER 1m realism audit | Make 1m candle research as realistic as observations permit | High priority | Not started | #2–#4 as available |
| 7 | SuperASI A/B correction | Restore original A Base / B Debase | High priority | Implemented; correction pending | #6 |
| 8 | Correlation Programming | Feature-state vs W/L without overfit | After clean ROLLER / SuperASI | Not started | #6; #7 |
| 9 | ITI Robust Optimized | Robust entry/exit search, not max historical PNL | After corrected A/B | Not started | #7 |
| 10 | Terminito X / Y / MCS | Sportsbook MCS + Momento MCS + multiple conditional states | After data foundation | Not started | #3–#8 |
| 11 | Terminito Ontologic Z | Joint calibration of X and Y (not an average) | After X / Y | Not started | #10 |
| 12 | Terminito Fluctuations | `P(K_{t+1}\|K_t,state,action)` Markov price chain | After Terminito foundation | Not started | #10; #11; #6 |
| 13 | Relative Value HFT | Same-game Kalshi↔Polymarket; Todd Klein normalization | After dual-market PIT | Not started | #4; #8; #11; #12 |
| 14 | Long-term hold EV | Long-duration fluctuation / EV strategies | Later research track | Not started | Terminito + Fluctuations + Z |
| 15 | Cloud Momento | Remove local-only SPOF after interfaces stabilize | After interfaces stabilize | Not started | Clear ownership of warehouse, ingest, Vital |
| 16 | Agentic traders | Research → paper → limited live → autonomous via Vital | Final major layer | Not started | #1–#15 mature enough to consume honestly |

October 1, 2026 claims only: Kalshi 1m yes-bid coverage, Polymarket 1m
last-trade ingest scheduled, PBP where the source has it, identity
without reminting, Autoingest validation statuses. Not PIT merge, not
Terminito, not RV, not Autojest as a live console.
