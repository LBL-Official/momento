# FIRST78 Live V1 implementation handoff

Repository folder: `docs/implementation/first78-live-v1/`

Branch: `feat/first78-live-v1-overnight-sizing`

Read in this order:

1. `SPECIFICATION.txt` — primary strategy/deployment contract, including P5-vs-P5 NCAAB eligibility, overnight sizing, 50-trade objectives and October handoff.
2. `MOMENTO_LIVE_BOT_001_LEDGER_STATE_MACHINE_V1.md` — supplied detailed ledger schema and state-machine implementation specification, preserved as received.
3. `STATUS.md` — implemented foundation, validation limits and remaining integration work.

The primary specification governs conflicting or omitted strategy/accounting
requirements in the companion document. In particular, NCAAB remains verified
P5 vs P5; resizing is only 01:00–03:00 America/Los_Angeles; and deposits are not
realized trading profit. Read section 109 for accounting definitions.

Repository review must resolve companion schema/state-machine ambiguities before
implementation. For example, if original_open_qty already excludes direct sales,
subtracting direct_exit_qty again in section 8.9 would double-count those sales.
The companion is an implementation input, not evidence of tested or deployed code.

Live order submission remains disabled pending readiness and explicit authorization.
