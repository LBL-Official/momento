# FIRST78 Live V1 — implementation checklist

- [x] Integrate incoming SHA `0ffd6ca` onto this main without touching unrelated dirty files.
- [x] Versioned V1 contract + decision register + unresolved checklist. 25¢ is a trigger. Drevo/Positman observe-only. No invented floor.
- [x] Paginated integer recon. V1 does not fall back to `$20` / `$20,000`. Legacy `batch.rs` constants isolated.
- [x] Supervised `first78_live_v1` run: discovery, explicit ESPN mappings only, bounded queues, one writer, production send compiled out.
- [x] Exit fixtures at 1 contract and thousands: deterioration ≠ 25¢ successor; 36→35→34→25; cancel-then-late-fill; no-bid / zero collateral; residual invariant.
- [x] Execution / portfolio / development ledgers, Orchestra states, durable order and alert outboxes, Systimo `/systimo/nba-001/v1`.
- [x] P5 2026–27 file present and fail-closed (`EVIDENCE_INCOMPLETE`).
- [x] MLB/WNBA drain-and-disable: fresh SSM inventory recorded; **STOP_BLOCKED** (`VITAL_AWS_CONTROL` unset; live unit still submitting-enabled; no signed GET inventory).
- [x] Acceptance matrix with predeclared outcomes; local tests recorded; live/demo/AWS rows marked unrun where evidence is missing.
- [x] AWS preflight run (account+SSM). Atomic shadow deploy **not** performed; production compiled out; host still FIRST78_67 SHADOW.
- [x] Genuine-signal $20 canary: blocked (`ARMED` false). Reports written.
- [x] Release report + October 15 promotion report using the honesty terms.
