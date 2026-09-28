# Operations

Keep-alive tonight: Kalshi MLB backfill + `mlb_canonical_catchup.sh` + MLB orderbook loop + `caffeinate`.
Do not start a second backfill. Do not ingest MLB canonical while `ingest.lock` exists.

After candles ≥ trades and backfill exits, catchup runs `python -m roller.mlb.ingest` then rebuilds MLB indexes.
If MLB golden N ≠ 554, stop and report. Do not edit the fixture.

Schedules (local time):

- 00:00 AUTO ROLLER VERIFY (`scripts/auto_roller_verify.sh` → `--fast`)
- 02:00 AUTO ROLLER INGEST (`scripts/auto_roller_ingest.sh` → `--skip-indexes` while Foundation backfill owns ingest)

Catch-up: late launchd start records `MISSED_SCHEDULE`.
