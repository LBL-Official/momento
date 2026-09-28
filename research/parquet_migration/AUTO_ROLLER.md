# AUTO ROLLER

Local research warehouse jobs. Not live trading.

| Job | Local clock | CLI |
| --- | --- | --- |
| AUTO ROLLER VERIFY | 00:00 | `python -m roller.auto_roller.verify` |
| AUTO ROLLER INGEST | 02:00 | `python -m roller.auto_roller.ingest` |

02:00 is two in the morning, not midnight.

Verify is the guardian: warehouse → indexes → reference → optimized → diff.
A sentinel N/hash change is FAILED. Goldens are not auto-updated.

Ingest wraps existing pipelines. It will not start a second Kalshi backfill or NCAAB
`download-all`. It will not run `mlb.ingest` while Foundation `ingest.lock` is held.

Install (after dry-run):

```text
chmod +x scripts/auto_roller_*.sh
scripts/auto_roller_install.sh
scripts/auto_roller_status.sh
```

If the Mac slept through the hour, launchd may run the job on wake. The wrapper
adds `--missed-schedule`. That is recorded as `MISSED_SCHEDULE`, not as "ran at 02:00".

UI: same ROLLER terminal, secondary nav **Auto Roller**. Buttons POST to
`/auto-roller/verify` and `/auto-roller/ingest`.
