# MLB 001 ARM64 deploy

Operator runbook. This is not a second engine and not Vital control.

```text
WATCHING  ≠  SIGNAL  ≠  SUBMIT  ≠  FILL
RUNNING   ≠  HEALTHY EXECUTION  ≠  order_submission=enabled
start     ≠  armed              ≠  submit
```

Build on a throwaway **ARM64 Amazon Linux 2023** host in `us-east-1`.
Do not Mac-cross-compile (`ring` will fail). Do not enable
`VITAL_AWS_CONTROL`. Do not edit `live.toml`. Do not hand-edit
`live-runtime.json`. Do not invent fills.

## Build

Stage the working tree that contains the intended recon fix (not
`origin` if it lacks the change). Exclude `target/`, frontends, and
warehouses. Include `config/live.toml` so `live_host` tests can load
it.

On the builder:

```text
deploy/mlb001-arm64-build.sh /path/to/tree /tmp/mlb001-engine
```

Require:

- `cargo test -p momento-positions --test tracker`
- `cargo test -p momento-trading-engine --test live_host fill`
- `file` is ARM aarch64 ELF
- recorded SHA256

Copy a **new** build to a short-lived S3 prefix the live instance can
read. After the live SHA is confirmed Healthy, freeze it as the
production baseline
(`docs/operations/MLB001_PRODUCTION_BASELINE.md`). Do not overwrite
`s3://…/m10/momento-trading-engine` (`fb939b62…`, 2026-09-13 history).

To recover the current factory bot, do not rebuild and do not install
`fb939b62…`:

```text
deploy/mlb001-recover-baseline.sh
```

## Atomic install

On `i-0f0849d5829476c31` only, via operator SSM/SCP:

```text
deploy/mlb001-atomic-deploy.sh <sha256> s3://…/momento-trading-engine
```

Host steps:

```text
/usr/local/bin/momento-trading-engine.new   # copy + chmod 0755
file + sha256 verify aarch64 and expected digest
cp -a current momento-trading-engine.<old8>.bak
mv -f .new over /usr/local/bin/momento-trading-engine
systemctl restart momento-live.service
```

Never write the running path in place. Keep
`RestartPreventExitStatus=78`.

## Observe — not “process up”

First housekeeping can print `preflight recon=Ambiguous` (persist
load). That is expected.

Success, in order:

1. Last `momento housekeeping_ok recon=Healthy order_submission=enabled unknown=false`
2. heartbeat `reconciliation=healthy` `unknown_orders=0` `order_submission=enabled`
3. Momento LS `/observe`: `source=ssm`, fresh `observed_at`, same new
   SHA, `reconciliation=Healthy`, `authorized_to_submit=true`

`recon_cleared` is sufficient if persist started Ambiguous. It is not
required when persist is already Healthy.

HTTP 200 / systemd `active` is not success.

If the last housekeeping_ok / heartbeat is not Healthy: leave trading
blocked, restore the `.bak` binary, restart, stop. Do not patch persist.

A trade still requires a real 80→81 YES bid, maker 80–83, lock 89,
cap 5, Create V2.

## Process vs trading health

`Restart=always` with `StartLimitIntervalSec=300` /
`StartLimitBurst=10` recovers a crashed process. Exit 78 still stays
down (preflight fail-closed). Automatic restart never skips recon.

Vital `#/live` flags trading-health. It does not auto-flatten.

Needles: `recon_cleared`, `order_submission=blocked`,
`reconciliation=ambiguous`.
